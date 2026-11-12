"""The independent suite: hand-written closes the generator did not produce, scored by a key.

`proven/examples/independent/` holds eight fictional companies, each with a chart of
accounts (`chart.json`), a general-ledger export (`ledger.csv`), month-end commentary
(`commentary.txt`) and an answer key (`key.json`). The set and its key were written and
committed before Proven was run on them; see `docs/independent.md` for the protocol.

The scoring uses the definitions of `evaluate.py`:

    decided          PASS or FAIL, over every keyed claim (a claim not extracted is undecided)
    passed, cause checked   a control PASS whose attribution check ran and was supported
                     (the rest passed on figures alone: no reason was read, or none was stated)
    controls passed  PASS on a correct explanation
    control FAIL     FAIL on a correct explanation            (kill criterion: must be 0)
    defects caught   FAIL on a wrong explanation
    defects flagged  FAIL or REVIEW on a wrong explanation
    unsafe PASS      PASS on a wrong explanation               (kill criterion: must be 0)
    not extracted    no admitted claim covers the keyed quote

MATCHING A KEYED CLAIM TO A CHECKED ONE. The key quotes a span of the commentary (a whole
sentence, or one clause when a sentence makes two claims). A checker claim covers a keyed
claim when their spans in the commentary overlap. Pairs are assigned one-to-one, preferring
a checker claim on the keyed account, then the larger overlap. A checker claim that lands on
a keyed claim but reads a different account is still scored (a PASS on a misread claim of a
wrong explanation is still an unsafe PASS) and is counted as `account_misread`.
"""
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from proven import learned
from proven.ledger import TOTAL, Account, Ledger, Transaction
from proven.report import Extractor, run
from proven.verify import Policy

HERE = Path(__file__).parent / "examples" / "independent"
SUITES = ("independent",)
MODEL_SUPPORT = ("SUPPORT_RESTS_ON_MODEL_TERMS", "REASON_FOUND_ONLY_BY_MODEL_TERMS")


@dataclass(frozen=True)
class KeyedClaim:
    """One hand-keyed claim of the independent suite and the answer it should get."""
    id: str
    quote: str
    account: str
    truth: str                  # CORRECT | WRONG
    defect: str | None
    why: str
    evidence: tuple[str, ...]
    ideal: str
    acceptable: tuple[str, ...]
    raw: dict = field(compare=False, repr=False, default_factory=dict)

    @property
    def correct(self) -> bool:
        return self.truth == "CORRECT"

    @property
    def family(self) -> str:
        return "control" if self.correct else str(self.defect)


@dataclass(frozen=True)
class Close:
    """One hand-written close: its ledger, commentary and keyed claims."""
    slug: str
    industry: str
    ledger: Ledger
    commentary: str
    claims: tuple[KeyedClaim, ...]
    non_claims: tuple[dict, ...]


def _ledger(folder: Path) -> tuple[Ledger, str]:
    chart = json.loads((folder / "chart.json").read_text(encoding="utf-8"))
    accounts = tuple(Account(a["name"], tuple(a["aliases"])) for a in chart["accounts"])
    reader = csv.DictReader(io.StringIO((folder / "ledger.csv").read_text(encoding="utf-8")))
    txns = tuple(Transaction(r["id"], r["date"], r["account"], r["vendor"], r["memo"],
                             float(r["amount"])) for r in reader)
    return Ledger(entity=chart["entity"], prior_period=chart["prior_period"],
                  current_period=chart["current_period"], accounts=accounts,
                  transactions=txns), chart["industry"]


def load(suite: str = "independent") -> list[Close]:
    """Load every close of the named hand-written suite."""
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}; choose from {', '.join(SUITES)}")
    manifest = json.loads((HERE / "suite.json").read_text(encoding="utf-8"))
    closes = []
    for slug in manifest["companies"]:
        folder = HERE / slug
        ledger, industry = _ledger(folder)
        key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
        claims = tuple(KeyedClaim(c["id"], c["quote"], c["account"], c["truth"], c["defect"],
                                  c["why"], tuple(c["evidence"]), c["ideal"],
                                  tuple(c["acceptable"]), c) for c in key["claims"])
        closes.append(Close(slug, industry, ledger,
                            (folder / "commentary.txt").read_text(encoding="utf-8"),
                            claims, tuple(key["non_claims"])))
    return closes


def _span(text: str, quote: str) -> tuple[int, int]:
    start = text.find(quote)
    return start, start + len(quote)


def match(close: Close, report: dict) -> tuple[dict[str, dict | None], list[dict]]:
    """Keyed claim id -> the checker claim scored for it (or None); and unmatched checker claims."""
    text = report["explanation"]
    pairs = []
    for k in close.claims:
        ks, ke = _span(text, k.quote)
        for i, c in enumerate(report["claims"]):
            cs, ce = c["claim"]["span"]
            overlap = min(ke, ce) - max(ks, cs)
            if overlap > 0:
                same = c["claim"]["account"] == (TOTAL if k.account == "TOTAL" else k.account)
                pairs.append((same, overlap, k.id, i))
    pairs.sort(reverse=True)
    assigned: dict[str, dict | None] = {k.id: None for k in close.claims}
    used: set[int] = set()
    for _same, _overlap, kid, i in pairs:
        if assigned[kid] is None and i not in used:
            assigned[kid] = report["claims"][i]
            used.add(i)
    extra = [c for i, c in enumerate(report["claims"]) if i not in used]
    return assigned, extra


_GAPS = (("no stated reason was read", "UNREAD:no_reason"),
         ("words outside the stated reason", "UNREAD:unread_words"),
         ("no direction word was read", "UNREAD:no_direction"),
         ("a figure in the sentence was not checked", "UNREAD:unchecked_figure"),
         ("a figure's role is ambiguous", "UNREAD:figure_role"),
         ("the stated reason contains a negation", "UNREAD:negation"),
         ("the sentence names more than one account", "UNREAD:two_accounts"),
         ("a number in the sentence was not read", "UNREAD:unread_number"),
         ("an amount is written in words", "UNREAD:worded_amount"),
         ("the sentence uses both a rise word", "UNREAD:rise_and_fall"))


def review_causes(result: dict | None) -> list[str]:
    """Why a claim is in REVIEW: its advisory finding codes, else what the unread guard
    withheld the PASS for, else that nothing could be checked. First entry is primary."""
    if result is None or result["verdict"] != "REVIEW":
        return []
    codes = [f["code"] for f in result["findings"] if f["severity"] == "advisory"]
    if codes:
        return codes
    causes = []
    for note in result["adjustments"]:
        if "was not read:" in note:
            for gap in note.split("was not read:", 1)[1].split(";"):
                gap = gap.strip()
                causes.append(next((c for prefix, c in _GAPS if gap.startswith(prefix)),
                                   "UNREAD:other"))
        elif "mapped by the model" in note:
            causes.append("ACCOUNT_MAPPED_BY_MODEL")
    return causes or ["NOTHING_CHECKED"]


def score(k: KeyedClaim, result: dict | None) -> dict:
    """Compare one claim's result with its key: verdict, cited evidence and whether it is safe."""
    verdict = result["verdict"] if result else "MISSED"
    findings = result["findings"] if result else []
    cited = sorted({t for f in findings for t in f["evidence"]})
    expected = TOTAL if k.account == "TOTAL" else k.account
    return {
        "id": k.id, "family": k.family, "truth": k.truth, "quote": k.quote,
        "verdict": verdict,
        "acceptable": verdict in k.acceptable,
        "ideal": verdict == k.ideal,
        "unsafe_pass": not k.correct and verdict == "PASS",
        "control_fail": k.correct and verdict == "FAIL",
        "checked_quote": result["claim"]["quote"] if result else None,
        "account_read": result["claim"]["account"] if result else None,
        "account_misread": bool(result) and result["claim"]["account"] != expected,
        "reason": result["reason"] if result else "not extracted",
        "direction_read": result["claim"]["direction"] if result else None,
        "reason_read": result["claim"]["driver"] if result else None,
        "attribution": next((ch["outcome"] or "skipped" for ch in result["checks"]
                             if ch["name"] == "attribution"), None) if result else None,
        "codes": [f["code"] for f in findings],
        "review_causes": review_causes(result),
        "evidence_recall": (len(set(cited) & set(k.evidence)) / len(k.evidence)
                            if k.evidence and result else None),
    }


def _tally(rows: list[dict]) -> dict:
    controls = [r for r in rows if r["truth"] == "CORRECT"]
    defects = [r for r in rows if r["truth"] == "WRONG"]
    primary: dict[str, int] = defaultdict(int)
    every: dict[str, int] = defaultdict(int)
    for r in controls:
        if r["review_causes"]:
            primary[r["review_causes"][0]] += 1
            for cause in set(r["review_causes"]):
                every[cause] += 1
    count = lambda rs, v: sum(r["verdict"] == v for r in rs)  # noqa: E731
    decided = sum(r["verdict"] in ("PASS", "FAIL") for r in rows)
    return {
        "claims": len(rows), "decided": decided,
        "decided_share": round(decided / len(rows), 4) if rows else 0.0,
        "not_extracted": count(rows, "MISSED"),
        "account_misread": sum(r["account_misread"] for r in rows),
        "controls": {"n": len(controls), "passed": count(controls, "PASS"),
                     "passed_cause_checked": sum(r["verdict"] == "PASS" and r["attribution"] == "supported"
                                                 for r in controls),
                     "review": count(controls, "REVIEW"), "fails": count(controls, "FAIL"),
                     "review_primary": dict(sorted(primary.items(), key=lambda kv: -kv[1])),
                     "review_any": dict(sorted(every.items(), key=lambda kv: -kv[1])),
                     "missed": count(controls, "MISSED")},
        "defects": {"n": len(defects), "caught": count(defects, "FAIL"),
                    "flagged": count(defects, "FAIL") + count(defects, "REVIEW"),
                    "unsafe_passes": count(defects, "PASS"), "missed": count(defects, "MISSED")},
    }


def benchmark(suite: str = "independent", *, extractor: Extractor | None = None,
              policy: Policy | None = None, lessons: list[dict] | None = None,
              companies: list[str] | None = None) -> dict:
    """Run every close of the suite and score it against the key."""
    rows: list[dict] = []
    per_company: dict[str, list[dict]] = {}
    spurious: list[dict] = []
    rejected: dict[str, int] = defaultdict(int)
    for close in load(suite):
        if companies is not None and close.slug not in companies:
            continue
        with learned.lexicon(lessons) if lessons is not None else nullcontext():
            report = run(close.commentary, close.ledger, extractor=extractor, policy=policy)
        for r in report["rejected"]:
            rejected[r["reason"]] += 1
        assigned, extra = match(close, report)
        scored = [dict(score(k, assigned[k.id]), company=close.slug) for k in close.claims]
        rows += scored
        per_company[close.slug] = scored
        for c in extra:
            spurious.append({"company": close.slug, "quote": c["claim"]["quote"],
                             "verdict": c["verdict"], "account": c["claim"]["account"]})
    families: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        families[r["family"]].append(r)
    name = f"{extractor.name}/{extractor.version}" if extractor is not None else "rules/0.1"
    return {
        "suite": suite, "extractor": name, "policy": (policy or Policy()).to_dict(),
        "lessons": len(lessons or []),
        "summary": _tally(rows),
        "companies": {slug: _tally(rs) for slug, rs in per_company.items()},
        "families": {fam: _tally(rs) for fam, rs in sorted(families.items())},
        "claims": rows,
        "spurious": spurious,
        "rejected": dict(sorted(rejected.items())),
    }


# ── a careful reviewer, reading the key ────────────────────────────────────

def teach(proposer: Extractor, companies: list[str], suite: str = "independent") -> list[dict]:
    """Lessons a reviewer who knows the answer would confirm, as in `teachsim.teach`.

    A claim is taught from only if the key says the explanation is correct, the checker
    sent it to REVIEW because its support rests on the model's terms, and confirming the
    model terms that matched transactions turns it into a PASS. The confirmed words are
    those `learned.trim_terms` keeps, as in `teachsim.teach`."""
    lessons: list[dict] = []
    known: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for close in load(suite):
        if close.slug not in companies:
            continue
        with learned.lexicon(lessons):
            report = run(close.commentary, close.ledger, extractor=proposer)
        assigned, _extra = match(close, report)
        for k in close.claims:
            result = assigned[k.id]
            if not k.correct or result is None or result["verdict"] != "REVIEW":
                continue
            if not any(f["code"] in MODEL_SUPPORT for f in result["findings"]):
                continue
            matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
            terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
            if not terms or not result["claim"]["driver"]:
                continue
            driver = result["claim"]["driver"]

            def verdict(words: list[str], driver: str = driver, key: str = k.id) -> str | None:
                with learned.lexicon(lessons + [learned.make_entry([driver], words)]):
                    after = run(close.commentary, close.ledger, extractor=proposer)
                again, _ = match(close, after)
                return again[key]["verdict"] if again[key] is not None else None

            try:
                _triggers, words = learned.validate([driver], terms)
                trimmed = learned.trim_terms(list(words), close.ledger,
                                             result["claim"].get("account"), verdict)
                entry = learned.make_entry([driver], trimmed.kept,
                                           quote=result["claim"]["quote"], action="simulated",
                                           note=f"independent teach {k.id}")
            except learned.LessonRefused:
                continue
            lesson_key = (tuple(entry["triggers"]), tuple(entry["terms"]))
            if lesson_key in known:
                continue
            if trimmed.verdict == "PASS":
                known.add(lesson_key)
                entry["provenance"]["keyed_claim"] = k.id
                lessons.append(entry)
    return lessons


def halves(suite: str = "independent") -> tuple[list[str], list[str]]:
    """The two fixed halves of the suite, by manifest order (alternating)."""
    slugs = [c.slug for c in load(suite)]
    return slugs[0::2], slugs[1::2]


def teach_and_measure(suite: str, proposer: Extractor) -> dict:
    """Teach from one half with `proposer`; measure the other half with the rules, both ways."""
    first, second = halves(suite)
    directions = []
    for taught, held in ((first, second), (second, first)):
        lessons = teach(proposer, taught, suite)
        directions.append({
            "taught": taught, "held": held,
            "lessons": [{"triggers": e["triggers"], "terms": e["terms"],
                         "from": e["provenance"].get("keyed_claim")} for e in lessons],
            "before": benchmark(suite, companies=held),
            "after": benchmark(suite, companies=held, lessons=lessons),
        })
    return {"suite": suite, "proposer": f"{proposer.name}/{proposer.version}",
            "directions": directions}


def format_teach(out: dict) -> str:
    """The teaching experiment as text: lessons from one half, measured on the other."""
    lines = [f"suite={out['suite']} proposer={out['proposer']}; lessons taught on one half, "
             f"measured with the rules on the other"]
    for d in out["directions"]:
        lines.append(f"\ntaught on {', '.join(d['taught'])} -> {len(d['lessons'])} lesson(s)")
        for e in d["lessons"]:
            lines.append(f"    {e['from']}: {e['triggers']} -> {e['terms']}")
        lines.append(f"measured on {', '.join(d['held'])}")
        for label in ("before", "after"):
            s = d[label]["summary"]
            lines.append(f"  {label:6s} decided {s['decided_share']:.1%}  controls passed "
                         f"{s['controls']['passed']}/{s['controls']['n']}  control FAIL "
                         f"{s['controls']['fails']}  caught {s['defects']['caught']}/{s['defects']['n']}  "
                         f"unsafe PASS {s['defects']['unsafe_passes']}  not extracted {s['not_extracted']}")
    return "\n".join(lines)


# ── printing ───────────────────────────────────────────────────────────────

def format_result(result: dict, *, detail: bool = True) -> str:
    """A suite result as text: the summary, then each claim when `detail` is set."""
    out = []
    s = result["summary"]
    out.append(f"suite={result['suite']} extractor={result['extractor']} lessons={result['lessons']} "
               f"anchor_model_terms={result['policy']['model_terms_anchor']}")
    header = f"{'':22s} {'n':>3s} {'decided':>8s} {'ctl pass':>9s} {'ctl FAIL':>8s} " \
             f"{'caught':>7s} {'flagged':>8s} {'unsafe':>6s} {'missed':>6s}"
    out.append(header)

    def line(name: str, t: dict) -> str:
        c, d = t["controls"], t["defects"]
        return (f"{name:22s} {t['claims']:3d} {t['decided_share']:8.1%} {c['passed']:4d}/{c['n']:<4d} "
                f"{c['fails']:8d} {d['caught']:3d}/{d['n']:<3d} {d['flagged']:8d} "
                f"{d['unsafe_passes']:6d} {t['not_extracted']:6d}")
    for slug, t in result["companies"].items():
        out.append(line(slug, t))
    out.append(line("ALL", s))
    out.append("")
    out.append(f"{'by family':22s}")
    for fam, t in result["families"].items():
        out.append(line(fam, t))
    out.append(f"\ncontrols passed with the stated cause checked against transactions: "
               f"{s['controls']['passed_cause_checked']} of {s['controls']['passed']}")
    out.append("controls in REVIEW, by primary cause: " + ", ".join(
        f"{k} {v}" for k, v in s["controls"]["review_primary"].items()))
    out.append(f"account misread on {s['account_misread']} matched claim(s); "
               f"{len(result['spurious'])} checker claim(s) on no keyed claim; "
               f"rejected proposals: {result['rejected'] or 'none'}")
    if detail:
        bad = [r for r in result["claims"] if r["unsafe_pass"] or r["control_fail"]]
        for r in bad:
            kind = "UNSAFE PASS" if r["unsafe_pass"] else "CONTROL FAIL"
            out.append(f"\n[{kind}] {r['id']} ({r['family']}): {r['quote']}\n    {r['reason']}")
    return "\n".join(out)
