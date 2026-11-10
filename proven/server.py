"""The reviewer console's backend: the standard library's HTTP server and a JSON API.

No framework, no database, no auth, no queue. The console serves one reviewer on
their own machine, binds to 127.0.0.1, and keeps the only state it has — the
resolutions a reviewer records — in a JSON-lines file. Each of those choices is
a thing that can be added when a real deployment needs it, and none of them is
needed to find out whether the checks are worth deploying.

    GET  /                       the console
    GET  /api/config             versions, network status, extractors, policy, actions
    GET  /api/scenarios          the showcase, the hand-written Tidewater close, and one held-out
                                 synthetic close per family
    GET  /api/scenario?id=       a scenario's ledger, explanation and ground truth / answer key
    GET  /api/ledger.csv?id=     a scenario's ledger as the CSV the upload accepts
    POST /api/verify             {explanation, ledger, extractor, model} -> report (+ `usage` for a
                                 model extractor, + `answer_key` for the Tidewater close)
    POST /api/benchmark          {split, n, phrasing, extractor: rules|oracle} -> per-family results
                                 (offline only: a model extractor is refused here, it costs money)
    GET  /api/resolutions        resolutions recorded so far
    POST /api/resolutions        record one reviewer decision (optionally with a `learn` lesson)
    GET  /api/lexicon            lessons reviewers have taught, with where each came from
    POST /api/lexicon/remove     {id} -> forget one lesson (DELETE /api/lexicon?id= also works)
    POST /api/lexicon/check      {triggers, terms} -> the safety gate's impact report, nothing stored
    GET  /api/queue              what to confirm next across stored runs, ranked, with the gate's preview
    GET  /api/pending?key=       one stored run's inputs, to open it in the console

Every lesson passes the safety gate (`gate.py`) before it is stored: it is replayed against
a built-in regression set of synthetic train-split closes and the directory's own recorded
cases, and refused if it would pass an explanation known to be wrong or fail one known to
be right. A refusal returns 400 with the reason and the full `impact` report.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import traceback
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from proven import __version__, examples, extractors, gate, learned, netguard, showcase, teachqueue
from proven.budget import Budget, BudgetExceeded
from proven.evaluate import OracleExtractor, evaluate, requirement_met
from proven.ledger import Ledger
from proven.llm import MODEL as CLAUDE_MODEL, NetworkDisabled
from proven.openweight import DEFAULT_BASE_URL, is_loopback
from proven.report import run
from proven.synth import FAMILIES, FAMILY_BY_NAME, generate, seeds
from proven.verify import Policy

WEB = Path(__file__).resolve().parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
MAX_BODY = 4 * 1024 * 1024

#: The closed set of things a reviewer can conclude about one exception, carried over from
#: Aptio's review design.
#: The record *is* the decision — there is no form to fill in afterwards.
ACTIONS = (
    {"id": "confirm_defect", "label": "Confirm defect",
     "help": "The explanation is wrong. This is the product working.", "reduces_review": False},
    {"id": "fix_evidence", "label": "Wrong evidence",
     "help": "The explanation is right; Proven matched the wrong transactions.", "reduces_review": True},
    {"id": "fix_reading", "label": "Misread sentence",
     "help": "Proven read the account, amount or reason wrongly.", "reduces_review": True},
    {"id": "accept_convention", "label": "Accept convention",
     "help": "Rounding, wording or a booking convention Proven should learn.", "reduces_review": True},
    {"id": "out_of_scope", "label": "Out of scope",
     "help": "Judgement, not something the ledger can settle.", "reduces_review": False},
    {"id": "insufficient_evidence", "label": "Missing evidence",
     "help": "The ledger supplied does not contain what is needed.", "reduces_review": False},
)
ACTION_IDS = {a["id"] for a in ACTIONS}
#: The actions that say "Proven should have known this". Only these may carry a lesson.
TEACHING_ACTIONS = frozenset(a["id"] for a in ACTIONS if a["reduces_review"])
MIN_NOTE = 10


class BadRequest(ValueError):
    pass


class LessonBlocked(BadRequest):
    """The safety gate refused a lesson. Carries the gate's impact report for the reviewer."""

    def __init__(self, message: str, impact: dict):
        super().__init__(message)
        self.impact = impact


#: Benchmarks the console may run. Both are offline and free; a model extractor is a paid (or at
#: least slow) benchmark and stays on the command line, where `--usd-budget` guards it.
BENCHMARK_EXTRACTORS = ("rules", "oracle")
MODEL_EXTRACTORS = tuple(n for n in extractors.NAMES if n != "rules")


def probe_openweight() -> tuple[bool, str, list[str]]:
    """Is an OpenAI-compatible model server reachable at the configured address?

    Returns (reachable, reason, model ids). One short GET of /models, no proxy, nothing from a
    close. A non-loopback address is not probed unless the network was allowed."""
    base = (os.environ.get("PROVEN_OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    host = urlparse(base).hostname or ""
    if not is_loopback(host) and not netguard.network_allowed():
        return False, (f"{host} is not this machine; network is off for this server "
                       "(start it with --allow-network)"), []
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{base}/models", timeout=0.75) as response:
            data = json.loads(response.read())
        ids = [str(m["id"]) for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
        return True, "", ids
    except Exception as exc:  # noqa: BLE001 — any failure just means "not available"
        return False, f"no model server answered at {base} ({type(exc).__name__})", []


def scenarios() -> list[dict]:
    out = [{"id": "showcase", "kind": "showcase",
            "title": f"{showcase.ENTITY} — October 2026 close"},
           {"id": "tidewater", "kind": "example",
            "title": f"{examples.ENTITY} — October 2026 close (hand-written, with answer key)"}]
    test_seeds = seeds("test", len(FAMILIES))
    for seed in test_seeds:
        family = generate(seed).family
        out.append({"id": f"syn-{seed:05d}", "kind": "synthetic", "family": family,
                    "title": f"Synthetic · {family.replace('_', ' ')}"})
    return out


def answer_key(report: dict) -> list[dict]:
    """The Tidewater key set beside what Proven said about each keyed sentence.

    A sentence is matched by its exact quote; one Proven did not extract is MISSED, which is the
    right outcome for a NO_CLAIM sentence and a miss for anything else."""
    by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
    rows = []
    for k in examples.load().key:
        found = by_quote.get(k.quote)
        verdict = found["verdict"] if found else "MISSED"
        met = verdict == "MISSED" if k.requirement == "NO_CLAIM" else requirement_met(k.requirement, verdict)
        rows.append({"quote": k.quote, "requirement": k.requirement, "defective": k.defective,
                     "why": k.why, "culprits": list(k.culprits), "defect": k.defect,
                     "verdict": verdict, "met": met,
                     "claim_id": found["claim"]["claim_id"] if found else None})
    return rows


def load_scenario(scenario_id: str) -> dict:
    if scenario_id == "showcase":
        return {"id": "showcase", "title": f"{showcase.ENTITY} — October 2026 close",
                "explanation": showcase.EXPLANATION, "ledger": showcase.ledger(),
                "ground_truth": None}
    if scenario_id == "tidewater":
        close = examples.load()
        return {"id": "tidewater", "title": f"{examples.ENTITY} — October 2026 close",
                "explanation": close.commentary, "ledger": close.ledger, "ground_truth": None,
                "answer_key": [{"quote": k.quote, "requirement": k.requirement, "defective": k.defective,
                                "why": k.why, "culprits": list(k.culprits), "defect": k.defect}
                               for k in close.key]}
    if not scenario_id.startswith("syn-") or not scenario_id[4:].isdigit():
        raise BadRequest(f"unknown scenario {scenario_id!r}")
    scenario = generate(int(scenario_id[4:]))
    family = FAMILY_BY_NAME[scenario.family]
    return {"id": scenario_id, "title": f"Synthetic · {scenario.family.replace('_', ' ')}",
            "explanation": scenario.explanation, "ledger": scenario.ledger,
            "ground_truth": {"family": scenario.family, "requirement": family.requirement,
                             "labels": [label.to_dict() for label in scenario.labels]}}


class App:
    def __init__(self, data_dir: Path, build=extractors.build, probe=probe_openweight,
                 warm_gate: bool = False):
        self.build, self.probe = build, probe       # injectable, so tests never reach a model
        self.data_dir = data_dir
        self.resolutions = data_dir / "resolutions.jsonl"
        self._lock = threading.RLock()
        self.lexicon: list[dict] = learned.apply(data_dir)   # the only place lessons are loaded
        if warm_gate:   # build the gate's regression set now, so the first lesson does not wait
            threading.Thread(target=gate.regression_set, daemon=True).start()

    # ── handlers ──
    def config(self) -> dict:
        claude_ok, reason = netguard.network_allowed(), ""
        if not claude_ok:
            reason = "network is off for this server (start it with --allow-network)"
        elif importlib.util.find_spec("anthropic") is None:
            claude_ok, reason = False, "the anthropic package is not installed (pip install anthropic)"
        ow_ok, ow_reason, ow_models = self.probe()
        info = {
            "rules": {"label": "Rules (offline)", "available": True, "reason": "", "uses_model": False,
                      "default_model": "", "models": []},
            "claude": {"label": "Claude (sends narrative only)", "available": claude_ok, "reason": reason,
                       "uses_model": True, "models": [],
                       "default_model": os.environ.get("PROVEN_CLAUDE_MODEL") or CLAUDE_MODEL},
            "openweight": {"label": "Open-weight (local model server)", "available": ow_ok,
                           "reason": ow_reason, "uses_model": True, "models": ow_models,
                           "default_model": os.environ.get("PROVEN_OPENAI_MODEL")
                           or (ow_models[0] if ow_models else "")},
        }
        return {"version": __version__,
                "network": {"allowed": netguard.network_allowed(), "guard_installed": netguard.installed()},
                "extractors": [{"id": name, **info[name]} for name in extractors.NAMES],
                "benchmark_extractors": list(BENCHMARK_EXTRACTORS),
                "policy": Policy().to_dict(), "actions": list(ACTIONS),
                "learned": {"active": len(self.lexicon)}}

    def verify(self, body: dict) -> dict:
        text = str(body.get("explanation", ""))
        if not text.strip():
            raise BadRequest("the explanation is empty")
        if body.get("ledger_csv"):
            try:
                book = Ledger.from_csv(str(body["ledger_csv"]), entity=str(body.get("entity") or "Uploaded ledger"))
            except (ValueError, KeyError) as exc:
                raise BadRequest(f"could not read the ledger CSV: {exc}") from None
        elif body.get("scenario_id"):
            book = load_scenario(str(body["scenario_id"]))["ledger"]
        else:
            raise BadRequest("supply a scenario_id or a ledger_csv")
        extractor_id = body.get("extractor", "rules")
        if extractor_id not in extractors.NAMES:
            raise BadRequest(f"unknown extractor {extractor_id!r}; choose from {', '.join(extractors.NAMES)}")
        model = str(body.get("model") or "").strip() or None
        if extractor_id == "claude" and not netguard.network_allowed():
            raise BadRequest("the Claude extractor sends the narrative off this machine, and network is "
                             "off for this server (start it with --allow-network)")
        budget = Budget() if extractor_id != "rules" else None
        try:
            extractor = self.build(extractor_id, model=model, budget=budget,
                                   cache_dir=str(self.data_dir / "cache"))
        except ValueError as exc:
            raise BadRequest(str(exc)) from None
        if extractor_id == "openweight" and not getattr(getattr(extractor, "inner", extractor), "model", ""):
            raise BadRequest("choose a model for the open-weight extractor (or set PROVEN_OPENAI_MODEL)")
        try:
            with self._lock, learned.lexicon(self.lexicon):
                report = run(text, book, extractor=extractor, network_allowed=netguard.network_allowed())
        except (NetworkDisabled, BudgetExceeded) as exc:
            raise BadRequest(str(exc)) from None
        if budget is not None:
            report["usage"] = self._usage(extractor, budget)
            failed = [t["error"] for t in report["run"]["network"]["transmissions"] if t.get("error")]
            if failed and not report["claims"]:
                raise BadRequest(f"the {extractor_id} extractor returned nothing usable: {failed[0]}")
        if body.get("scenario_id") == "tidewater" and not body.get("ledger_csv"):
            report["answer_key"] = answer_key(report)
        with self._lock:     # claims waiting on a confirmation join the teaching queue
            teachqueue.record_run(self.data_dir, body, report)
        return report

    @staticmethod
    def _usage(extractor, budget: Budget) -> dict:
        """What the run spent, and what the proposal cache saved. A cached answer costs nothing."""
        inner = getattr(extractor, "inner", extractor)
        return {"extractor": extractor.name, "model": str(getattr(inner, "model", "")),
                **budget.to_dict(),
                "cache": {"hits": getattr(extractor, "hits", 0), "misses": getattr(extractor, "misses", 0)}}

    def benchmark(self, body: dict) -> dict:
        split = body.get("split", "test")
        phrasing = body.get("phrasing", "seen")
        extractor = body.get("extractor", "rules")
        if split not in ("test", "train") or phrasing not in ("seen", "heldout", "paraphrase"):
            raise BadRequest("split must be test|train and phrasing seen|heldout|paraphrase")
        if extractor in MODEL_EXTRACTORS:
            raise BadRequest(f"the console does not benchmark the {extractor} extractor: that is a paid or "
                             f"slow run. Use `python -m proven benchmark --extractor {extractor}` "
                             "(cached proposals are reused) instead")
        if extractor not in BENCHMARK_EXTRACTORS:
            raise BadRequest(f"extractor must be one of {', '.join(BENCHMARK_EXTRACTORS)}")
        try:
            n = int(body.get("n", 220))
        except (TypeError, ValueError):
            raise BadRequest("n must be a whole number") from None
        if not 1 <= n <= 2000:
            raise BadRequest("n must be between 1 and 2000")
        # The benchmark measures the built-in lexicon; a reviewer's lessons never enter it.
        with self._lock, learned.lexicon([]):
            if extractor == "oracle":
                result = evaluate(split, n, phrasing=phrasing, extractor_for=OracleExtractor)
                result["extractor"] = f"{OracleExtractor.name}/{OracleExtractor.version}"
                return result
            return evaluate(split, n, phrasing=phrasing)

    def record(self, body: dict) -> dict:
        action = body.get("action")
        note = str(body.get("note", "")).strip()
        if action not in ACTION_IDS:
            raise BadRequest(f"action must be one of {', '.join(sorted(ACTION_IDS))}")
        if len(note) < MIN_NOTE:
            raise BadRequest("a resolution needs a reason of at least 10 characters — "
                             "a decision nobody can re-read cannot become a regression test")
        lesson_in = body.get("learn")
        if lesson_in is not None and action not in TEACHING_ACTIONS:
            raise BadRequest("only Wrong evidence, Misread sentence and Accept convention can teach "
                             "Proven something; remove the lesson or choose one of those actions")
        entry = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "run_id": str(body.get("run_id", "")), "claim_id": str(body.get("claim_id", "")),
                 "quote": str(body.get("quote", "")), "verdict": str(body.get("verdict", "")),
                 "action": action, "note": note,
                 "seconds_on_claim": body.get("seconds_on_claim"),
                 "reduces_review": next(a["reduces_review"] for a in ACTIONS if a["id"] == action)}
        with self._lock:
            lesson = impact = None
            if lesson_in is not None:
                lesson, case, impact = self._teach(body, lesson_in, entry)
                entry.update({"lesson_id": lesson["id"], "case": case})
            else:
                case = self._case(body, entry["quote"])
                if case is not None:      # kept so the safety gate can replay this decision
                    entry["case"] = {**case, "verdict_before": entry["verdict"]}
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.resolutions.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        out: dict = {"ok": True, "resolution": entry}
        if lesson is not None:
            out["lesson"] = lesson
            out["verdict_before"] = entry["case"]["verdict_before"]
            out["verdict_after"] = entry["case"]["verdict_after"]
            out["impact"] = impact
        return out

    @staticmethod
    def _case(body: dict, quote: str) -> dict | None:
        """The inputs that let a decision be re-run later, or None if the request lacks them."""
        explanation = str(body.get("explanation", ""))
        if not explanation.strip() or not quote:
            return None
        case: dict = {"explanation": explanation, "quote": quote}
        if body.get("ledger_csv"):
            case.update(ledger_csv=str(body["ledger_csv"]), entity=str(body.get("entity") or "Uploaded ledger"))
        elif body.get("scenario_id"):
            load_scenario(str(body["scenario_id"]))   # raises BadRequest if unknown
            case["scenario_id"] = str(body["scenario_id"])
        else:
            return None
        return case

    def _teach(self, body: dict, lesson_in: object, entry: dict) -> tuple[dict, dict, dict]:
        """Validate, gate, dry-run, store and activate one lesson.

        Returns (lesson, regression case, the gate's impact report)."""
        if not isinstance(lesson_in, dict):
            raise BadRequest("learn must be an object {triggers: [...], terms: [...]}")
        quote = entry["quote"]
        if not str(body.get("explanation", "")).strip() or not quote:
            raise BadRequest("a lesson needs the explanation text and the claim's quote, so it can "
                             "be re-run as a regression case")
        case = self._case(body, quote)
        if case is None:
            raise BadRequest("a lesson needs the scenario_id or ledger_csv the claim was checked against")
        try:
            lesson = learned.make_entry(
                lesson_in.get("triggers"), lesson_in.get("terms"), note=entry["note"],
                run_id=entry["run_id"], claim_id=entry["claim_id"], quote=quote, action=entry["action"])
            before = learned.case_verdict(case, self.lexicon)
            after = learned.case_verdict(case, self.lexicon + [lesson])
        except learned.LessonRefused as exc:
            raise BadRequest(f"Proven will not learn this: {exc}") from None
        except (ValueError, KeyError) as exc:
            raise BadRequest(f"could not re-run the claim: {exc}") from None
        if before is None:
            raise BadRequest("this claim was not found when the sentence is re-read by the offline "
                             "rules, so a lesson about it could not be replayed; fix the sentence or "
                             "resolve it without teaching")
        impact = gate.impact(lesson, self.lexicon, gate.stored_cases(self.data_dir))
        impact["claim"] = {"quote": quote, "before": before, "after": after}
        if not impact["accepted"]:
            raise LessonBlocked(impact["refusal"], impact)
        if after == "PASS" and before != "PASS" and lesson_in.get("confirm_pass") is not True:
            raise LessonBlocked(
                f"This lesson would turn the claim from {before} to PASS. Check that the matched "
                "transactions really are the stated cause, then send it again with confirm_pass: true.",
                impact)
        try:
            learned.append(self.data_dir, lesson)
        except learned.LessonRefused as exc:
            raise BadRequest(f"Proven will not learn this: {exc}") from None
        self.lexicon = learned.apply(self.data_dir)
        case.update(verdict_before=before, verdict_after=after)
        return lesson, case, impact

    def check_lesson(self, body: dict) -> dict:
        """The gate's impact report for a lesson, without storing anything.

        With the claim's `explanation`, `quote` and `scenario_id` (or `ledger_csv`) the report
        also says what the lesson does to that claim."""
        try:
            lesson = learned.make_entry(body.get("triggers"), body.get("terms"))
        except learned.LessonRefused as exc:
            raise BadRequest(f"Proven will not learn this: {exc}") from None
        with self._lock:
            impact = gate.impact(lesson, self.lexicon, gate.stored_cases(self.data_dir))
            case = self._case(body, str(body.get("quote", "")))
            if case is not None:
                impact["claim"] = {"quote": case["quote"],
                                   "before": learned.case_verdict(case, self.lexicon),
                                   "after": learned.case_verdict(case, self.lexicon + [lesson])}
        return impact

    def queue(self) -> dict:
        with self._lock:
            return teachqueue.build_queue(self.data_dir, self.lexicon)

    def pending(self, key: str) -> dict:
        run = teachqueue.find_run(self.data_dir, key)
        if run is None:
            raise BadRequest(f"no stored run {key!r}")
        return {k: run.get(k, "") for k in ("key", "run_id", "explanation", "scenario_id",
                                             "ledger_csv", "entity", "extractor", "created_at")}

    def list_lexicon(self) -> dict:
        with self._lock:
            return {"entries": list(self.lexicon)}

    def forget(self, lesson_id: str) -> dict:
        with self._lock:
            try:
                gone = learned.remove(self.data_dir, lesson_id)
            except KeyError:
                raise BadRequest(f"no learned entry {lesson_id!r}") from None
            self.lexicon = learned.apply(self.data_dir)
            return {"ok": True, "removed": gone, "active": len(self.lexicon)}

    def list_resolutions(self) -> dict:
        if not self.resolutions.exists():
            return {"resolutions": []}
        lines = self.resolutions.read_text(encoding="utf-8").splitlines()
        return {"resolutions": [json.loads(line) for line in lines[-50:] if line.strip()]}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"proven/{__version__}"

        def log_message(self, fmt, *args):  # quieter than the default
            sys.stderr.write(f"[proven] {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")

        def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json")

        def _guard(self, fn):
            try:
                self._json(HTTPStatus.OK, fn())
            except LessonBlocked as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "impact": exc.impact})
            except BadRequest as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception:  # noqa: BLE001 — the reviewer sees a message, the log sees the trace
                traceback.print_exc()
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                           {"error": "Proven hit an internal error; the server log has the details."})

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise BadRequest("request too large (4 MB limit)")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                raise BadRequest("request body is not valid JSON") from None
            if not isinstance(data, dict):
                raise BadRequest("request body must be a JSON object")
            return data

        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path in STATIC:
                name, content_type = STATIC[url.path]
                self._send(HTTPStatus.OK, (WEB / name).read_bytes(), content_type)
            elif url.path == "/api/config":
                self._guard(app.config)
            elif url.path == "/api/scenarios":
                self._guard(lambda: {"scenarios": scenarios()})
            elif url.path == "/api/scenario":
                def one():
                    s = load_scenario(query.get("id", ""))
                    return {**s, "ledger": s["ledger"].to_dict()}
                self._guard(one)
            elif url.path == "/api/ledger.csv":
                try:
                    s = load_scenario(query.get("id", ""))
                except BadRequest as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send(HTTPStatus.OK, s["ledger"].to_csv().encode("utf-8"), "text/csv; charset=utf-8",
                           {"Content-Disposition": f'attachment; filename="{s["id"]}-ledger.csv"'})
            elif url.path == "/api/resolutions":
                self._guard(app.list_resolutions)
            elif url.path == "/api/lexicon":
                self._guard(app.list_lexicon)
            elif url.path == "/api/queue":
                self._guard(app.queue)
            elif url.path == "/api/pending":
                self._guard(lambda: app.pending(query.get("key", "")))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": f"no such route {url.path}"})

        def do_POST(self):  # noqa: N802
            routes = {"/api/verify": app.verify, "/api/benchmark": app.benchmark,
                      "/api/resolutions": app.record, "/api/lexicon/check": app.check_lesson,
                      "/api/lexicon/remove": lambda body: app.forget(str(body.get("id", "")))}
            handler = routes.get(urlparse(self.path).path)
            if handler is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "no such route"})
                return
            self._guard(lambda: handler(self._body()))

        def do_DELETE(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path != "/api/lexicon":
                self._json(HTTPStatus.NOT_FOUND, {"error": "no such route"})
                return
            lesson_id = parse_qs(url.query).get("id", [""])[0]
            self._guard(lambda: app.forget(lesson_id))

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8765,
                  data_dir: Path | str = ".proven", **app_options) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(App(Path(data_dir), **app_options)))


def serve(host: str = "127.0.0.1", port: int = 8765, allow_network: bool = False,
          data_dir: str = ".proven") -> None:
    if allow_network:
        netguard.allow_network()
    else:
        netguard.install()
    server = create_server(host, port, data_dir, warm_gate=True)
    mode = "ALLOWED (the Claude extractor may send narrative text)" if allow_network \
        else "OFF (enforced: outbound connections are refused)"
    print(f"Proven {__version__} — reviewer console at http://{host}:{server.server_address[1]}/")
    print(f"network: {mode}")
    print(f"resolutions: {Path(data_dir) / 'resolutions.jsonl'}")
    print(f"learned lexicon: {learned.path(data_dir)} ({len(learned.load(data_dir))} active)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
