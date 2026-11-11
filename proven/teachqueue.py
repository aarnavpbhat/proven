"""What to confirm next: the teaching queue, ranked by how many waiting claims a lesson reaches.

A claim WAITS for a reviewer when it sits in REVIEW only because its support rests on
the model's search terms (`SUPPORT_RESTS_ON_MODEL_TERMS`) and those terms matched
transactions. Confirming the terms teaches a lesson: the stated reason, verbatim, as the
trigger, and the model's matched terms as the ledger words. The lesson then applies to
every claim whose stated reason contains that phrase.

A reviewer's time is counted in confirmations, so the queue asks first for the lesson
that reaches the most waiting claims:

    arrival     the order the claims arrived in (what a reviewer working down a list does)
    frequency   most waiting claims whose stated reason the lesson's trigger fires on,
                ties broken by arrival

The ranking reads only what a reviewer sees (phrases, proposed terms); never a label.
`teachsim.curve` measures both orders; the console's queue (`GET /api/queue`) uses
frequency over the runs stored in the data directory.

STORAGE. When the console verifies with a model extractor and some claims wait, the run's
inputs and those claims are appended to `<data_dir>/pending.jsonl`; a later run of the same
text on the same ledger replaces it. A claim leaves the queue when a stored lesson already
fires on its reason, or when a resolution was recorded for it.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from proven import gate, learned

MODEL_SUPPORT = "SUPPORT_RESTS_ON_MODEL_TERMS"
PENDING_FILE = "pending.jsonl"
ORDERS = ("arrival", "frequency")

_lock = threading.RLock()


@dataclass(frozen=True)
class Waiting:
    """One claim waiting for a confirmation."""

    key: tuple                  # identifies the claim: (close, quote)
    arrival: int                # position in arrival order
    quote: str
    driver: str                 # the stated reason as written
    terms: tuple[str, ...]      # the model's terms that matched transactions
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def trigger(self) -> str:
        return " ".join(self.driver.lower().split())


def waiting_in(report: dict, *, any_model_match: bool = False) -> list[dict]:
    """The claims of one report that wait for a confirmation: quote, driver and terms.

    `any_model_match` widens it to every REVIEW claim whose model terms matched something,
    whatever the finding (the stress test for a careless reviewer in `teachsim.curve`)."""
    out = []
    for result in report["claims"]:
        driver = result["claim"].get("driver")
        if result["verdict"] != "REVIEW" or not driver:
            continue
        if not any_model_match and not any(f["code"] == MODEL_SUPPORT for f in result["findings"]):
            continue
        matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
        terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
        if terms:
            out.append({"quote": result["claim"]["quote"], "driver": driver, "terms": terms,
                        "claim_id": result["claim"]["claim_id"]})
    return out


class Ranker:
    """Ranks waiting claims; remembers which triggers fire on which reasons between calls."""

    def __init__(self) -> None:
        self._fires: dict[tuple[str, str], bool] = {}

    def fires(self, trigger: str, driver: str) -> bool:
        key = (trigger, driver)
        if key not in self._fires:
            self._fires[key] = gate.fires(trigger, driver)
        return self._fires[key]

    def rank(self, waiting: Iterable[Waiting], order: str = "frequency",
             score: Callable[[str], int] | None = None) -> list[dict]:
        """One row per distinct lesson (trigger, terms), best first.

        Each row: trigger, terms, `reach` (waiting claims the trigger fires on), `members`
        (the waiting claims that propose exactly this lesson, in arrival order). Frequency
        order breaks a tie in reach by how many claims propose exactly these terms (the
        model agreeing with itself across closes), then by arrival. `score` replaces reach
        with another value per trigger (the simulation's hindsight bound uses it)."""
        if order not in ORDERS:
            raise ValueError(f"order must be one of {', '.join(ORDERS)}")
        waiting = sorted(waiting, key=lambda w: w.arrival)
        groups: dict[tuple[str, tuple[str, ...]], list[Waiting]] = {}
        for item in waiting:
            groups.setdefault((item.trigger, item.terms), []).append(item)
        drivers: dict[str, int] = {}
        for item in waiting:
            low = item.driver.lower()
            drivers[low] = drivers.get(low, 0) + 1
        reach: dict[str, int] = {}
        rows = []
        for (trigger, terms), members in groups.items():
            if trigger not in reach:
                reach[trigger] = score(trigger) if score is not None else sum(
                    count for low, count in drivers.items() if self.fires(trigger, low))
            rows.append({"trigger": trigger, "terms": list(terms), "reach": reach[trigger],
                         "members": members, "arrival": members[0].arrival})
        if order == "frequency":
            rows.sort(key=lambda r: (-r["reach"], -len(r["members"]), r["arrival"]))
        else:
            rows.sort(key=lambda r: r["arrival"])
        return rows


# ── stored runs (the console) ────────────────────────────────────────────

def _path(data_dir: Path | str) -> Path:
    return Path(data_dir) / PENDING_FILE


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def close_key(explanation: str, scenario_id: str = "", ledger_csv: str = "") -> str:
    """Identifies a close: the text and the ledger it was checked against."""
    return _sha(json.dumps([explanation, scenario_id, _sha(ledger_csv) if ledger_csv else ""]))[:16]


def trim_waiting(claims: list[dict], case: dict, lexicon: list[dict]) -> list[dict]:
    """The waiting claims with the terms the console would let a reviewer confirm.

    Each claim's terms go through `learned.trim_case` on its own close, so the queue never
    suggests a word that matches only the account's routine lines or that the PASS does
    not need. A claim left with no word keeps an empty `terms` (the queue skips it) and
    says why in `dropped`."""
    out = []
    for item in claims:
        item = dict(item)
        try:
            trimmed = learned.trim_case({**case, "quote": item["quote"]}, [item["driver"]],
                                        list(item["terms"]), lexicon)
        except learned.LessonRefused as exc:
            item.update(terms=[], dropped=[{"term": t, "reason": str(exc)} for t in item["terms"]])
        except (ValueError, KeyError):
            pass        # the close cannot be re-read offline; keep the model's words as they are
        else:
            item["terms"] = trimmed.kept
            if trimmed.dropped:
                item["dropped"] = trimmed.dropped
        out.append(item)
    return out


def record_run(data_dir: Path | str, body: dict, report: dict,
               lexicon: list[dict] | None = None) -> int:
    """Store a model run's waiting claims, if any. Returns how many were stored.

    The claims' terms are trimmed (`trim_waiting`) with `lexicon`, the lessons active when
    the run was checked. A model run with nothing waiting is stored only if it replaces an
    earlier run of the same close (so a re-check after teaching empties that close's
    entries). A rules run is never stored."""
    if report["run"]["versions"]["extractor"].startswith("rules/"):
        # The rules propose no terms, so their run says nothing about what waits on a model's
        # words; it must not replace a stored model run (re-opening a queued close re-checks
        # it with the rules).
        return 0
    scenario_id = "" if body.get("ledger_csv") else str(body.get("scenario_id") or "")
    ledger_csv = str(body.get("ledger_csv") or "")
    case = {"explanation": report["explanation"], "scenario_id": scenario_id, "ledger_csv": ledger_csv,
            "entity": str(body.get("entity") or "Uploaded ledger")}
    claims = trim_waiting(waiting_in(report), case, lexicon or [])
    key = close_key(report["explanation"], scenario_id, ledger_csv)
    with _lock:
        if not claims and key not in {r["key"] for r in load_runs(data_dir)}:
            return 0
        entry = {"key": key, "run_id": report["run"]["run_id"],
                 "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "extractor": report["run"]["versions"]["extractor"],
                 "explanation": report["explanation"], "scenario_id": scenario_id,
                 "entity": str(body.get("entity") or "") if ledger_csv else "",
                 "ledger_csv": ledger_csv, "claims": claims}
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        with _path(data_dir).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    return len(claims)


def load_runs(data_dir: Path | str) -> list[dict]:
    """Stored runs, the latest per close, oldest first."""
    file = _path(data_dir)
    if not file.exists():
        return []
    latest: dict[str, dict] = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            key = str(entry["key"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        latest.pop(key, None)            # re-insert, so order follows the latest run
        latest[key] = entry
    return list(latest.values())


def find_run(data_dir: Path | str, key: str) -> dict | None:
    """The stored run with this key, or None."""
    return next((r for r in load_runs(data_dir) if r["key"] == key), None)


def _resolved(data_dir: Path | str) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(close key, quote) and (run id, quote) pairs a reviewer has already decided."""
    file = Path(data_dir) / learned.RESOLUTIONS_FILE
    by_close: set[tuple[str, str]] = set()
    by_run: set[tuple[str, str]] = set()
    if not file.exists():
        return by_close, by_run
    for line in file.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        quote = str(entry.get("quote", ""))
        by_run.add((str(entry.get("run_id", "")), quote))
        case = entry.get("case")
        if isinstance(case, dict) and case.get("explanation"):
            by_close.add((close_key(str(case["explanation"]), str(case.get("scenario_id") or ""),
                                    str(case.get("ledger_csv") or "")), quote))
    return by_close, by_run


def waiting_runs(data_dir: Path | str, lexicon: list[dict]) -> list[Waiting]:
    """Every stored claim still waiting: not resolved, and no stored lesson fires on it."""
    by_close, by_run = _resolved(data_dir)
    out: list[Waiting] = []
    for run in load_runs(data_dir):
        for item in run.get("claims", []):
            quote, driver = str(item.get("quote", "")), str(item.get("driver", ""))
            if (run["key"], quote) in by_close or (str(run.get("run_id")), quote) in by_run:
                continue
            low = driver.lower()
            if any(gate.fires(t, low) for entry in lexicon for t in entry["triggers"]):
                continue
            terms = tuple(sorted({str(t).lower() for t in item.get("terms", [])}))
            if not terms:
                continue
            out.append(Waiting((run["key"], quote), len(out), quote, driver, terms,
                               {"run": run, "claim_id": item.get("claim_id", "")}))
    return out


def _probe(item: Waiting) -> list[gate.Probe]:
    from proven.ledger import Ledger
    from proven.server import BadRequest, load_scenario
    run = item.extra["run"]
    try:
        if run.get("ledger_csv"):
            book = Ledger.from_csv(run["ledger_csv"], entity=run.get("entity") or "Uploaded ledger")
        else:
            book = load_scenario(run["scenario_id"])["ledger"]
    except (BadRequest, ValueError, KeyError):
        return []
    return gate.probes_for(run["explanation"], book, [(item.quote, {
        "known": "right", "source": "waiting", "family": "", "phrasing": "", "ref": run["key"]})])


def build_queue(data_dir: Path | str, lexicon: list[dict], *, limit: int = 20,
                preview: int = 8) -> dict:
    """The ranked queue across stored runs, with the gate's verdict on the top rows.

    For each previewed row, `unlocks` is how many of the claims it reaches the rules would
    decide (PASS or FAIL) once the lesson is stored, and `impact` is `gate.impact`."""
    waiting = waiting_runs(data_dir, lexicon)
    rows = Ranker().rank(waiting, "frequency")[:limit]
    cases = gate.stored_cases(data_dir)
    out = []
    for index, row in enumerate(rows):
        first: Waiting = row["members"][0]
        run = first.extra["run"]
        item = {"trigger": row["trigger"], "terms": row["terms"], "waiting": row["reach"],
                "proposing": len(row["members"]),
                "runs": len({m.key[0] for m in row["members"]}),
                "example": {"key": run["key"], "run_id": run.get("run_id", ""), "quote": first.quote,
                            "driver": first.driver, "scenario_id": run.get("scenario_id", ""),
                            "uploaded": bool(run.get("ledger_csv")), "entity": run.get("entity", ""),
                            "extractor": run.get("extractor", "")},
                "unlocks": None, "impact": None}
        if index < preview:
            try:
                lesson = learned.make_entry([first.driver], row["terms"])
            except learned.LessonRefused as exc:
                item["impact"] = {"accepted": False, "refusal": f"Proven will not learn this: {exc}",
                                  "tested": False, "new_unsafe_passes": 0, "new_control_fails": 0,
                                  "newly_passed_right": 0, "newly_failed_wrong": 0, "touched": 0,
                                  "cases_changed": 0, "elapsed_ms": 0.0}
                out.append(item)
                continue
            report = gate.impact(lesson, lexicon, cases)
            item["impact"] = summarize(report)
            reached = [w for w in waiting if gate.fires(row["trigger"], w.driver.lower())]
            probes = [p for w in reached for p in _probe(w)]
            with learned.lexicon(lexicon + [lesson]):
                item["unlocks"] = sum(1 for p in probes if gate._verdict(p) in ("PASS", "FAIL"))
        out.append(item)
    return {"items": out, "waiting": len(waiting), "runs": len(load_runs(data_dir))}


def summarize(report: dict) -> dict:
    """The parts of a gate report a queue row shows."""
    reg, cases = report["regression"], report["cases"]
    return {"accepted": report["accepted"], "refusal": report["refusal"], "tested": report["tested"],
            "new_unsafe_passes": reg["new_unsafe_passes"] + cases["new_unsafe_passes"],
            "new_control_fails": reg["new_control_fails"] + cases["new_control_fails"],
            "newly_passed_right": reg["newly_passed_right"],
            "newly_failed_wrong": reg["newly_failed_wrong"],
            "touched": reg["touched"], "cases_changed": len(cases["changed"]),
            "elapsed_ms": report["elapsed_ms"]}
