"""The reviewer console's backend: the standard library's HTTP server and a JSON API.

No framework, no database, no auth, no queue. The console serves one reviewer on
their own machine, binds to 127.0.0.1, and keeps the only state it has — the
resolutions a reviewer records — in a JSON-lines file. Each of those choices is
a thing that can be added when a real deployment needs it, and none of them is
needed to find out whether the checks are worth deploying.

    GET  /                       the console
    GET  /api/config             versions, network status, extractors, policy, actions
    GET  /api/scenarios          the showcase and one held-out synthetic close per family
    GET  /api/scenario?id=       a scenario's ledger, explanation and (synthetic) ground truth
    GET  /api/ledger.csv?id=     a scenario's ledger as the CSV the upload accepts
    POST /api/verify             explanation + ledger -> report
    POST /api/benchmark          {split, n, phrasing} -> per-family results
    GET  /api/resolutions        resolutions recorded so far
    POST /api/resolutions        record one reviewer decision (optionally with a `learn` lesson)
    GET  /api/lexicon            lessons reviewers have taught, with where each came from
    POST /api/lexicon/remove     {id} -> forget one lesson (DELETE /api/lexicon?id= also works)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import traceback
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from proven import __version__, learned, netguard, showcase
from proven.evaluate import evaluate
from proven.extract import RuleExtractor
from proven.ledger import Ledger
from proven.llm import ClaudeExtractor, NetworkDisabled
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


def scenarios() -> list[dict]:
    out = [{"id": "showcase", "kind": "showcase",
            "title": f"{showcase.ENTITY} — October 2026 close"}]
    test_seeds = seeds("test", len(FAMILIES))
    for seed in test_seeds:
        family = generate(seed).family
        out.append({"id": f"syn-{seed:05d}", "kind": "synthetic", "family": family,
                    "title": f"Synthetic · {family.replace('_', ' ')}"})
    return out


def load_scenario(scenario_id: str) -> dict:
    if scenario_id == "showcase":
        return {"id": "showcase", "title": f"{showcase.ENTITY} — October 2026 close",
                "explanation": showcase.EXPLANATION, "ledger": showcase.ledger(),
                "ground_truth": None}
    if not scenario_id.startswith("syn-") or not scenario_id[4:].isdigit():
        raise BadRequest(f"unknown scenario {scenario_id!r}")
    scenario = generate(int(scenario_id[4:]))
    family = FAMILY_BY_NAME[scenario.family]
    return {"id": scenario_id, "title": f"Synthetic · {scenario.family.replace('_', ' ')}",
            "explanation": scenario.explanation, "ledger": scenario.ledger,
            "ground_truth": {"family": scenario.family, "requirement": family.requirement,
                             "labels": [label.to_dict() for label in scenario.labels]}}


class App:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.resolutions = data_dir / "resolutions.jsonl"
        self._lock = threading.RLock()
        self.lexicon: list[dict] = learned.apply(data_dir)   # the only place lessons are loaded

    # ── handlers ──
    def config(self) -> dict:
        claude_ok, reason = netguard.network_allowed(), ""
        if not claude_ok:
            reason = "network is off for this server (start it with --allow-network)"
        elif importlib.util.find_spec("anthropic") is None:
            claude_ok, reason = False, "the anthropic package is not installed (pip install anthropic)"
        return {"version": __version__,
                "network": {"allowed": netguard.network_allowed(), "guard_installed": netguard.installed()},
                "extractors": [{"id": "rules", "label": "Rules (offline)", "available": True, "reason": ""},
                               {"id": "claude", "label": "Claude (sends narrative only)",
                                "available": claude_ok, "reason": reason}],
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
        if extractor_id == "claude":
            extractor = ClaudeExtractor()
        elif extractor_id == "rules":
            extractor = RuleExtractor()
        else:
            raise BadRequest(f"unknown extractor {extractor_id!r}")
        try:
            with self._lock, learned.lexicon(self.lexicon):
                return run(text, book, extractor=extractor, network_allowed=netguard.network_allowed())
        except NetworkDisabled as exc:
            raise BadRequest(str(exc)) from None

    def benchmark(self, body: dict) -> dict:
        split = body.get("split", "test")
        phrasing = body.get("phrasing", "seen")
        if split not in ("test", "train") or phrasing not in ("seen", "heldout"):
            raise BadRequest("split must be test|train and phrasing seen|heldout")
        n = int(body.get("n", 220))
        if not 1 <= n <= 2000:
            raise BadRequest("n must be between 1 and 2000")
        # The benchmark measures the built-in lexicon; a reviewer's lessons never enter it.
        with self._lock, learned.lexicon([]):
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
            lesson = None
            if lesson_in is not None:
                lesson, case = self._teach(body, lesson_in, entry)
                entry.update({"lesson_id": lesson["id"], "case": case})
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.resolutions.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        out: dict = {"ok": True, "resolution": entry}
        if lesson is not None:
            out["lesson"] = lesson
            out["verdict_before"] = entry["case"]["verdict_before"]
            out["verdict_after"] = entry["case"]["verdict_after"]
        return out

    def _teach(self, body: dict, lesson_in: object, entry: dict) -> tuple[dict, dict]:
        """Validate, dry-run, store and activate one lesson. Returns (lesson, regression case)."""
        if not isinstance(lesson_in, dict):
            raise BadRequest("learn must be an object {triggers: [...], terms: [...]}")
        explanation, quote = str(body.get("explanation", "")), entry["quote"]
        if not explanation.strip() or not quote:
            raise BadRequest("a lesson needs the explanation text and the claim's quote, so it can "
                             "be re-run as a regression case")
        case: dict = {"explanation": explanation, "quote": quote}
        if body.get("ledger_csv"):
            case.update(ledger_csv=str(body["ledger_csv"]), entity=str(body.get("entity") or "Uploaded ledger"))
        elif body.get("scenario_id"):
            load_scenario(str(body["scenario_id"]))   # raises BadRequest if unknown
            case["scenario_id"] = str(body["scenario_id"])
        else:
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
        if after == "PASS" and before != "PASS" and lesson_in.get("confirm_pass") is not True:
            raise BadRequest(
                f"This lesson would turn the claim from {before} to PASS. Check that the matched "
                "transactions really are the stated cause, then send it again with confirm_pass: true.")
        try:
            learned.append(self.data_dir, lesson)
        except learned.LessonRefused as exc:
            raise BadRequest(f"Proven will not learn this: {exc}") from None
        self.lexicon = learned.apply(self.data_dir)
        case.update(verdict_before=before, verdict_after=after)
        return lesson, case

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
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": f"no such route {url.path}"})

        def do_POST(self):  # noqa: N802
            routes = {"/api/verify": app.verify, "/api/benchmark": app.benchmark,
                      "/api/resolutions": app.record,
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
                  data_dir: Path | str = ".proven") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(App(Path(data_dir))))


def serve(host: str = "127.0.0.1", port: int = 8765, allow_network: bool = False,
          data_dir: str = ".proven") -> None:
    if allow_network:
        netguard.allow_network()
    else:
        netguard.install()
    server = create_server(host, port, data_dir)
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
