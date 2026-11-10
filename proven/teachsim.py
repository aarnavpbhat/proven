"""A simulated reviewer loop: what do confirmed lessons buy on closes never taught from?

The guard sends a claim to REVIEW when its support rests on the model's search terms
(`SUPPORT_RESTS_ON_MODEL_TERMS`). In the console a reviewer can confirm those terms as a
lesson. This module plays that reviewer over the synthetic benchmark:

  * on each TEACHING close, a claim is taught from only if the generator's label says the
    explanation is right, the claim sits in REVIEW for that one reason, and confirming the
    terms that matched ledger transactions turns it into a PASS;
  * the lesson is "the stated reason, verbatim -> those terms", validated by
    `learned.make_entry` exactly as the console's would be;
  * the lessons are then measured on the HELD closes (the second half of the split),
    which no lesson was taught from.

WHAT THIS IS NOT. The simulated reviewer never confirms a wrong explanation, because it
reads the label; a person can. And the synthetic phrasings come from a finite pool, so the
curve saturates far sooner than real commentary would. It is an upper bound on a careful
reviewer, measured with the same kill criteria as the benchmark.
"""
from __future__ import annotations

from collections.abc import Callable

from proven import learned
from proven.evaluate import OracleExtractor, score_claim
from proven.extract import RuleExtractor
from proven.report import Extractor, run
from proven.synth import Scenario, generate_split

MODEL_SUPPORT = "SUPPORT_RESTS_ON_MODEL_TERMS"
STEPS = (0, 10, 20, 55, 110, 220)


def teach(pool: list[Scenario], proposer_for: Callable[[Scenario], Extractor]) -> list[dict]:
    """The lessons a label-reading reviewer would confirm, working through `pool` in order."""
    lessons: list[dict] = []
    known: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for scenario in pool:
        with learned.lexicon(lessons):
            report = run(scenario.explanation, scenario.ledger, extractor=proposer_for(scenario))
        labels = {label.quote: label for label in scenario.labels}
        for result in report["claims"]:
            quote = result["claim"]["quote"]
            label = labels.get(quote)
            if label is None or label.requirement != "PASS" or result["verdict"] != "REVIEW":
                continue
            if not any(f["code"] == MODEL_SUPPORT for f in result["findings"]):
                continue
            matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
            terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
            try:
                entry = learned.make_entry([result["claim"]["driver"]], terms, quote=quote,
                                           action="simulated", note="teachsim")
            except learned.LessonRefused:
                continue
            key = (tuple(entry["triggers"]), tuple(entry["terms"]))
            if key in known:
                continue
            with learned.lexicon(lessons + [entry]):
                after = run(scenario.explanation, scenario.ledger, extractor=proposer_for(scenario))
            if any(r["verdict"] == "PASS" for r in after["claims"] if r["claim"]["quote"] == quote):
                known.add(key)
                lessons.append(entry)
    return lessons


def measure(pool: list[Scenario], lessons: list[dict],
            extractor_for: Callable[[Scenario], Extractor]) -> dict:
    out = {"claims": 0, "decided": 0, "controls": 0, "controls_passed": 0, "control_fails": 0,
           "defects": 0, "defects_caught": 0, "unsafe_passes": 0}
    total = 0.0
    for scenario in pool:
        with learned.lexicon(lessons):
            report = run(scenario.explanation, scenario.ledger, extractor=extractor_for(scenario))
        by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
        for label in scenario.labels:
            score = score_claim(label, by_quote.get(label.quote))
            out["claims"] += 1
            out["decided"] += score["verdict"] in ("PASS", "FAIL")
            total += score["reward"]
            if label.requirement == "PASS":
                out["controls"] += 1
                out["controls_passed"] += score["verdict"] == "PASS"
                out["control_fails"] += score["verdict"] == "FAIL"
            else:
                out["defects"] += 1
                out["defects_caught"] += score["met"]
                out["unsafe_passes"] += score["verdict"] == "PASS"
    out["decided_share"] = round(out["decided"] / out["claims"], 4) if out["claims"] else 0.0
    out["mean_reward"] = round(total / out["claims"], 4) if out["claims"] else 0.0
    return out


def simulate(n: int = 440, phrasing: str = "heldout", proposer=None,
             steps: tuple[int, ...] = STEPS) -> dict:
    """Teach from the first half of the test split, measure the second half with the rules.

    `proposer` is a model extractor (its answers should be cached); the default is the
    oracle, whose terms are the generator's gold ones and are treated as a model's."""
    scenarios = generate_split("test", n, phrasing)
    half = len(scenarios) // 2
    pool, held = scenarios[:half], scenarios[half:]
    proposer_for = (lambda s: proposer) if proposer is not None else OracleExtractor
    rules = RuleExtractor()
    rows = []
    for step in sorted({min(s, half) for s in steps}):
        lessons = teach(pool[:step], proposer_for)
        rows.append({"taught_closes": step, "lessons": len(lessons),
                     **measure(held, lessons, lambda _s: rules)})
    return {"phrasing": phrasing, "held_closes": len(held),
            "proposer": f"{proposer.name}/{proposer.version}" if proposer is not None else "oracle/0.1",
            "rows": rows}
