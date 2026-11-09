"""The benchmark: per-family requirements over held-out synthetic closes, and the reward.

WHAT IS REPORTED, AND WHAT IS NEVER COMBINED

  * per family: how many claims met the family's requirement, whether the
    expected finding was raised, and whether the findings cited the culprit
    transactions (evidence recall and precision);
  * controls: the false-alarm rate (a correct explanation not passed) and,
    separately, the FAIL count on controls — Aptio's kill criterion K3 is that
    any negative control failing means the checker is not ready to be pointed
    at anybody's work;
  * defects: the catch rate and, separately, the unsafe-PASS count — a PASS on
    an explanation known to be wrong. K2 is the one number no amount of
    coverage compensates for;
  * coverage: the share of claims decided (PASS or FAIL) without a person.

There is no single quality score. A checker that decides 5% of claims and one
that decides 95% would look identical under one.

THE REWARD

`reward()` is the training signal the submission describes — "rewarding
accurate judgments backed by the right evidence" — written down so that the
deterministic checker can be scored by the same function a learned policy would
be. It is asymmetric on purpose: an unsafe PASS costs the most, a false FAIL on
a correct explanation costs half as much, and sending a correct explanation to
REVIEW costs nothing but earns nothing. Evidence quality scales the reward for a
correct flag.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from dataclasses import dataclass

from proven import __version__
from proven.claims import ClaimProposal
from proven.ledger import Ledger
from proven.report import Extractor, run
from proven.synth import FAMILIES, FAMILY_BY_NAME, Label, Scenario, generate_split
from proven.verify import Policy

UNSAFE_PASS = -1.0
FALSE_FAIL = -0.5


def requirement_met(requirement: str, verdict: str) -> bool:
    if requirement == "PASS":
        return verdict == "PASS"
    if requirement == "FAIL":
        return verdict == "FAIL"
    return verdict in ("FAIL", "REVIEW")      # NOT_PASS


def evidence_scores(cited: set[str], culprits: list[str]) -> tuple[float | None, float | None]:
    if not culprits:
        return None, None
    hits = len(cited & set(culprits))
    recall = hits / len(culprits)
    precision = hits / len(cited) if cited else 0.0
    return recall, precision


def reward(verdict: str, cited: set[str], label: Label) -> float:
    """In [-1, 1]. The signal a learned verifier or extractor would be trained on."""
    if label.requirement == "PASS":
        return 1.0 if verdict == "PASS" else FALSE_FAIL if verdict == "FAIL" else 0.0
    if verdict in ("PASS", "MISSED"):
        return UNSAFE_PASS
    base = 1.0 if requirement_met(label.requirement, verdict) else 0.25
    recall, precision = evidence_scores(cited, label.culprits)
    if recall is None:
        return base
    f1 = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return base * (0.5 + 0.5 * f1)


@dataclass
class _Tally:
    n: int = 0
    met: int = 0
    codes: int = 0
    missed: int = 0
    reward: float = 0.0
    recall_sum: float = 0.0
    precision_sum: float = 0.0
    evidence_n: int = 0

    def __post_init__(self) -> None:
        self.verdicts = {"PASS": 0, "FAIL": 0, "REVIEW": 0, "MISSED": 0}


def score_claim(label: Label, result: dict | None) -> dict:
    verdict = result["verdict"] if result else "MISSED"
    findings = result["findings"] if result else []
    codes = {f["code"] for f in findings}
    cited = {txn for f in findings for txn in f["evidence"]}
    recall, precision = evidence_scores(cited, label.culprits)
    return {"verdict": verdict, "met": requirement_met(label.requirement, verdict),
            "codes_hit": all(c in codes for c in label.expected_codes),
            "recall": recall, "precision": precision,
            "reward": reward(verdict, cited, label)}


class OracleExtractor:
    """Returns the generator's gold proposals: the ceiling a perfect model extractor reaches.

    Its search terms are admitted with origin "model", exactly as a real model's would be,
    so the guard treats it like any other model. It never sees the ledger."""

    name = "oracle"
    version = "0.1"

    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        return [proposal_from_gold(label.gold) for label in self.scenario.labels]


def proposal_from_gold(gold: dict) -> ClaimProposal:
    """A gold object (the JSON schema in llm.py) as the ClaimProposal llm.py would build."""
    return ClaimProposal(
        quote=gold["quote"], account=gold["account"] or None,
        change_text=gold["change_text"] or None, percent_text=gold["percent_text"] or None,
        prior_text=gold["prior_text"] or None, current_text=gold["current_text"] or None,
        driver_text=gold["reason_text"] or None,
        driver_terms=tuple(gold["search_terms"]), direction=gold["direction"] or None,
        extractor="oracle")


def evaluate(split: str = "test", n: int = 220, policy: Policy | None = None,
             phrasing: str = "seen", extractor=None, workers: int = 1,
             extractor_for: Callable[[Scenario], Extractor] | None = None) -> dict:
    """`extractor` defaults to the rules; `extractor_for` builds one per close (the oracle).
    With `workers` > 1 the extractor is called for every close up front, in parallel; that
    only helps one that caches its proposals."""
    scenarios = generate_split(split, n, phrasing)
    per_scenario = extractor
    if extractor is not None and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = list(pool.map(lambda s: extractor.propose(s.explanation, s.ledger), scenarios))
        # Reuse what was fetched: calling the extractor again would re-send every close
        # whose answer the cache does not keep (an empty one).
        per_scenario = _Prefetched(extractor, {id(s): p for s, p in zip(scenarios, fetched)})
    tallies: dict[str, _Tally] = defaultdict(_Tally)
    failures: list[dict] = []
    rejected: dict[str, int] = defaultdict(int)
    claims = decided = 0

    for scenario in scenarios:
        if isinstance(per_scenario, _Prefetched):
            per_scenario.current = id(scenario)
        report = run(scenario.explanation, scenario.ledger, policy=policy,
                     extractor=extractor_for(scenario) if extractor_for else per_scenario)
        for rejection in report["rejected"]:
            rejected[rejection["reason"]] += 1
        by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
        for label in scenario.labels:
            result = by_quote.get(label.quote)
            score = score_claim(label, result)
            tally = tallies[label.family]
            tally.n += 1
            tally.met += score["met"]
            tally.codes += score["codes_hit"]
            tally.reward += score["reward"]
            tally.verdicts[score["verdict"]] += 1
            if score["recall"] is not None:
                tally.evidence_n += 1
                tally.recall_sum += score["recall"]
                tally.precision_sum += score["precision"]
            claims += 1
            decided += score["verdict"] in ("PASS", "FAIL")
            if not score["met"] and len(failures) < 25:
                failures.append({"scenario_id": scenario.scenario_id, "family": label.family,
                                 "quote": label.quote, "verdict": score["verdict"],
                                 "reason": result["reason"] if result else "not extracted"})

    order = [f.name for f in FAMILIES] + ["control_distractor"]
    rows = []
    for name in order:
        tally = tallies.get(name)
        if not tally or not tally.n:
            continue
        family = FAMILY_BY_NAME[name]
        rows.append({
            "family": name, "kind": family.kind, "requirement": family.requirement,
            "expected_codes": list(family.expected_codes), "n": tally.n, "met": tally.met,
            "met_rate": round(tally.met / tally.n, 4),
            "codes_rate": round(tally.codes / tally.n, 4) if family.expected_codes else None,
            "evidence_recall": round(tally.recall_sum / tally.evidence_n, 4) if tally.evidence_n else None,
            "evidence_precision": round(tally.precision_sum / tally.evidence_n, 4) if tally.evidence_n else None,
            "verdicts": tally.verdicts, "mean_reward": round(tally.reward / tally.n, 4),
        })

    controls = [r for r in rows if r["kind"] == "control"]
    defects = [r for r in rows if r["kind"] == "defect"]
    control_n = sum(r["n"] for r in controls)
    defect_n = sum(r["n"] for r in defects)
    total_reward = sum(t.reward for t in tallies.values())
    return {
        "version": __version__, "split": split, "phrasing": phrasing,
        "extractor": f"{extractor.name}/{extractor.version}" if extractor else "rules/0.1",
        "scenarios": len(scenarios), "claims": claims,
        "policy": (policy or Policy()).to_dict(),
        "families": rows,
        "controls": {
            "n": control_n,
            "passed": sum(r["verdicts"]["PASS"] for r in controls),
            "false_alarms": control_n - sum(r["verdicts"]["PASS"] for r in controls),
            "fails": sum(r["verdicts"]["FAIL"] for r in controls),
        },
        "defects": {
            "n": defect_n,
            "caught": sum(r["met"] for r in defects),
            "flagged": defect_n - sum(r["verdicts"]["PASS"] + r["verdicts"]["MISSED"] for r in defects),
            "unsafe_passes": sum(r["verdicts"]["PASS"] for r in defects),
            "missed": sum(r["verdicts"]["MISSED"] for r in defects),
        },
        "coverage": {"claims": claims, "decided": decided,
                     "decided_share": round(decided / claims, 4) if claims else 0.0},
        "mean_reward": round(total_reward / claims, 4) if claims else 0.0,
        "rejected": dict(sorted(rejected.items())),
        "failures": failures,
    }


class _Prefetched:
    """Hands `run()` the proposals already fetched for the scenario being scored."""

    def __init__(self, inner, proposals: dict[int, list]):
        self.inner, self.proposals, self.current = inner, proposals, 0
        self.name, self.version = inner.name, inner.version

    @property
    def transmissions(self) -> list[dict]:
        return list(getattr(self.inner, "transmissions", []))

    def propose(self, text, ledger):
        return list(self.proposals[self.current])
