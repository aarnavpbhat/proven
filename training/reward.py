"""The reward a proposer's reply earns on one close: the RL environment for `rl.py`.

Standard library plus the `proven` package only, so it can be tested without MLX.

WHAT IS REWARDED

A proposer never decides anything, so its reply is scored by what the deterministic
checker does with it. The guard sends every claim whose support rests on the model's own
search terms to REVIEW, so a reply cannot earn a PASS directly; what it can earn is a
lesson. The reward therefore plays the reviewer from `proven.teachsim` on the same close:

  1. the reply is parsed exactly as `proven.openweight` parses it (an unparseable reply is
     an empty proposal list);
  2. `teachsim.teach` confirms, as lessons, the terms that matched the ledger for the
     sentences the generator labels correct;
  3. with those lessons, the close is checked twice: once with the reply as the extractor
     (did it copy the sentences and figures so they are admitted?) and once with the rules
     (does the reason it marked work as a trigger the rule reader finds?);
  4. every labelled sentence is scored with `proven.evaluate.reward` (+1 right verdict,
     scaled by evidence quality for a flag; 0 for a correct sentence left in REVIEW; -0.5
     for a correct sentence failed; -1 for a wrong sentence passed or not extracted);
  5. a careless reviewer is also played: lessons are confirmed from every sentence in
     REVIEW on model terms, including the wrong ones. Any wrong sentence that PASSES under
     those lessons costs -1 (the terms would bind a wrong explanation to the ledger).

The close's reward is the mean over its sentences of
`0.5 * model-extractor reward + 0.5 * rules reward`, minus the careless-reviewer penalty.
It is in [-2, 1]; the generator's gold reply scores close to 1 on correct sentences.

Only train-split closes may be scored here (`episode` refuses a test seed).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proven import learned  # noqa: E402
from proven.claims import ClaimProposal  # noqa: E402
from proven.evaluate import score_claim  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.openweight import parse_reply, proposals_from  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import Scenario, generate  # noqa: E402
from proven.teachsim import MODEL_SUPPORT, teach  # noqa: E402

TRAP_PENALTY = 1.0


class Fixed:
    """An extractor that returns one already-made proposal list."""

    name = "openweight"
    version = "0.1"
    transmissions: list[dict] = []

    def __init__(self, proposals: list[ClaimProposal]):
        self.proposals = proposals

    def propose(self, text, ledger):
        return list(self.proposals)


def parse(reply: str) -> tuple[list[ClaimProposal], bool]:
    """(proposals, parsed). A reply the harness could not read proposes nothing."""
    try:
        return proposals_from(parse_reply(reply)), True
    except (ValueError, TypeError, KeyError):
        return [], False


def _careless_lessons(scenario: Scenario, proposer: Fixed) -> list[dict]:
    """Lessons a reviewer who confirms everything would add from this close."""
    report = run(scenario.explanation, scenario.ledger, extractor=proposer)
    lessons: list[dict] = []
    for result in report["claims"]:
        if result["verdict"] != "REVIEW":
            continue
        if not any(f["code"] == MODEL_SUPPORT for f in result["findings"]):
            continue
        matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
        terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
        try:
            lessons.append(learned.make_entry([result["claim"]["driver"]], terms,
                                              quote=result["claim"]["quote"],
                                              action="simulated", note="careless"))
        except learned.LessonRefused:
            continue
    return lessons


def _score(scenario: Scenario, lessons: list[dict], extractor) -> list[dict]:
    with learned.lexicon(lessons):
        report = run(scenario.explanation, scenario.ledger, extractor=extractor)
    by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
    return [score_claim(label, by_quote.get(label.quote)) for label in scenario.labels]


@dataclass
class Outcome:
    reward: float
    parsed: bool
    lessons: int
    labels: int
    model_decided: int
    rules_decided: int
    unsafe: int          # wrong sentences passed with the careful reviewer's lessons
    control_fails: int
    traps: int           # wrong sentences passed with the careless reviewer's lessons

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def score_reply(scenario: Scenario, reply: str) -> Outcome:
    proposals, parsed = parse(reply)
    return score_proposals(scenario, proposals, parsed)


def score_proposals(scenario: Scenario, proposals: list[ClaimProposal],
                    parsed: bool = True) -> Outcome:
    proposer = Fixed(proposals)
    lessons = teach([scenario], lambda _s: proposer)
    as_model = _score(scenario, lessons, proposer)
    as_rules = _score(scenario, lessons, RuleExtractor())
    careless = _careless_lessons(scenario, proposer)
    trapped = _score(scenario, lessons + careless, RuleExtractor()) if careless else as_rules
    n = len(scenario.labels)
    traps = sum(1 for label, s in zip(scenario.labels, trapped)
                if label.requirement != "PASS" and s["verdict"] == "PASS")
    total = sum(0.5 * m["reward"] + 0.5 * r["reward"] for m, r in zip(as_model, as_rules))
    reward = (total - TRAP_PENALTY * traps) / n if n else 0.0
    wrong = [i for i, label in enumerate(scenario.labels) if label.requirement != "PASS"]
    right = [i for i, label in enumerate(scenario.labels) if label.requirement == "PASS"]
    return Outcome(
        reward=round(reward, 4), parsed=parsed, lessons=len(lessons), labels=n,
        model_decided=sum(s["verdict"] in ("PASS", "FAIL") for s in as_model),
        rules_decided=sum(s["verdict"] in ("PASS", "FAIL") for s in as_rules),
        unsafe=sum(1 for i in wrong for s in (as_model[i], as_rules[i]) if s["verdict"] == "PASS"),
        control_fails=sum(1 for i in right for s in (as_model[i], as_rules[i])
                          if s["verdict"] == "FAIL"),
        traps=traps)


def episode(seed: int, phrasing: str = "paraphrase") -> Scenario:
    """A train-split close to act on. Test seeds are refused."""
    scenario = generate(seed, phrasing=phrasing)
    if scenario.split != "train":
        raise ValueError(f"seed {seed} is in the {scenario.split} split; RL uses train only")
    return scenario


def _selfcheck(n: int = 60) -> None:
    import json
    from proven.evaluate import proposal_from_gold
    from proven.synth import seeds
    rows = {"gold": [], "nothing": [], "garbled": [], "no_terms": []}
    for seed in seeds("train", 5000)[-n:]:
        scenario = episode(seed)
        gold = [proposal_from_gold(label.gold) for label in scenario.labels]
        rows["gold"].append(score_proposals(scenario, gold))
        rows["nothing"].append(score_proposals(scenario, []))
        rows["garbled"].append(score_reply(scenario, '{"claims": [{"quote": "x"'))
        bare = [proposal_from_gold({**label.gold, "search_terms": []}) for label in scenario.labels]
        rows["no_terms"].append(score_proposals(scenario, bare))
    for name, outs in rows.items():
        print(name, json.dumps({
            "mean_reward": round(sum(o.reward for o in outs) / len(outs), 3),
            "unsafe": sum(o.unsafe for o in outs), "control_fails": sum(o.control_fails for o in outs),
            "traps": sum(o.traps for o in outs), "lessons": sum(o.lessons for o in outs),
            "rules_decided": sum(o.rules_decided for o in outs),
            "labels": sum(o.labels for o in outs)}))


if __name__ == "__main__":
    _selfcheck()
