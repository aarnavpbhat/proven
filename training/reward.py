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

WORLDS

`episode(seed, phrasing, world)` draws the close from an authored world; `load_worlds(dir)`
loads a directory of training or dev worlds (role "train": every oblique phrase is open to
the train split). It refuses a directory inside `proven.worlds.HERE` and any file whose slug
is a measured world's: the measured suites are never an RL episode or a validation close.
`measured_phrases()` reads those suites for one purpose, the one `build_worlds_dataset.py`
has: a close whose stated reason is word-for-word a measured world's phrase is not used.

COST (measured on CPU, gold proposals, 40 closes from four training worlds)

One call was 6.5 `report.run`s, about 35 ms. Three of them repeated work: the careless
reviewer's first look is the teaching reviewer's first look; the reply checked "with the
lessons" is the run that accepted the last lesson (or the first look, when there are none);
and the rules' runs depend only on the close and the lessons, so they are kept on the
scenario and shared by every reply to the same close. No reward value changes
(`test_reward.py` compares against the original on default and authored worlds).

HELPERS FOR `rl.py`

The decisions the training loop makes without a model live here so they can be tested
without MLX: which world an episode comes from (`pick_world`), validation closes spread over
dev worlds (`validation_closes`), whether a close has anything to learn (`has_headroom`),
whether to keep sampling it (`worth_sampling`), the leave-one-out advantages
(`loo_advantages`) and which replies carry gradient (`gradient_rows`).
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proven import claims, learned, worlds as _worlds  # noqa: E402
from proven.claims import ClaimProposal  # noqa: E402
from proven.evaluate import proposal_from_gold, score_claim  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.openweight import parse_reply, proposals_from  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import Scenario, World, generate  # noqa: E402
from proven.teachsim import MODEL_SUPPORT  # noqa: E402

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


def _report(scenario: Scenario, lessons: list[dict], extractor) -> dict:
    with learned.lexicon(lessons):
        return run(scenario.explanation, scenario.ledger, extractor=extractor)


def _model_terms(result: dict) -> list[str]:
    matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
    return sorted({m["term"] for m in matched if m["origin"] == "model"})


def _waiting_on_model(result: dict) -> bool:
    return result["verdict"] == "REVIEW" and any(f["code"] == MODEL_SUPPORT
                                                 for f in result["findings"])


def _teach(scenario: Scenario, proposer: Fixed) -> tuple[list[dict], dict, dict]:
    """`teachsim.teach([scenario], ...)`, also returning the runs it made anyway:
    (lessons, the report with no lessons, the report with all of them)."""
    lessons: list[dict] = []
    known: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    first = final = _report(scenario, [], proposer)
    labels = {label.quote: label for label in scenario.labels}
    for result in first["claims"]:
        quote = result["claim"]["quote"]
        label = labels.get(quote)
        if label is None or label.requirement != "PASS" or not _waiting_on_model(result):
            continue
        try:
            entry = learned.make_entry([result["claim"]["driver"]], _model_terms(result),
                                       quote=quote, action="simulated", note="teachsim")
        except learned.LessonRefused:
            continue
        key = (tuple(entry["triggers"]), tuple(entry["terms"]))
        if key in known:
            continue
        after = _report(scenario, lessons + [entry], proposer)
        if any(r["verdict"] == "PASS" for r in after["claims"] if r["claim"]["quote"] == quote):
            known.add(key)
            lessons.append(entry)
            final = after           # the run with exactly the lessons held so far
    return lessons, first, final


def _careless_lessons(report: dict) -> list[dict]:
    """Lessons a reviewer who confirms everything would add from this close."""
    lessons: list[dict] = []
    for result in report["claims"]:
        if not _waiting_on_model(result):
            continue
        try:
            lessons.append(learned.make_entry([result["claim"]["driver"]], _model_terms(result),
                                              quote=result["claim"]["quote"],
                                              action="simulated", note="careless"))
        except learned.LessonRefused:
            continue
    return lessons


def _scores(scenario: Scenario, report: dict) -> list[dict]:
    by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
    return [score_claim(label, by_quote.get(label.quote)) for label in scenario.labels]


def _rules_scores(scenario: Scenario, lessons: list[dict]) -> list[dict]:
    """What the rule reader's claims score under `lessons`. It depends on the close and on
    the lessons' triggers and terms only, so it is kept on the scenario: the K replies to
    one close mostly teach the same lessons (often none)."""
    cache = scenario.__dict__.setdefault("_rules_scores", {})
    key = tuple((tuple(e["triggers"]), tuple(e["terms"])) for e in lessons)
    if key not in cache:
        cache[key] = _scores(scenario, _report(scenario, lessons, RuleExtractor()))
    return cache[key]


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
    lessons, first, final = _teach(scenario, proposer)
    as_model = _scores(scenario, final)
    as_rules = _rules_scores(scenario, lessons)
    # the careless reviewer looks at the close with whatever lexicon is active outside;
    # normally none, and then that look is the teaching reviewer's first one
    unlearned = first if not claims.LEARNED else run(scenario.explanation, scenario.ledger,
                                                     extractor=proposer)
    careless = _careless_lessons(unlearned)
    trapped = _rules_scores(scenario, lessons + careless) if careless else as_rules
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


def episode(seed: int, phrasing: str = "paraphrase", world: World | None = None) -> Scenario:
    """A train-split close to act on, from `world` (the default one if None). Test seeds
    are refused in every world."""
    scenario = generate(seed, phrasing=phrasing, world=world)
    if scenario.split != "train":
        raise ValueError(f"seed {seed} is in the {scenario.split} split; RL uses train only")
    return scenario


# ── worlds ───────────────────────────────────────────────────────────────

def _inside(path: Path, folder: Path) -> bool:
    path, folder = path.resolve(), folder.resolve()
    return path == folder or folder in path.parents


@lru_cache(maxsize=1)
def measured_slugs() -> frozenset[str]:
    """Slugs of every measured world (read from the files; nothing is generated)."""
    return frozenset(str(json.loads(f.read_text(encoding="utf-8")).get("slug", "")).strip()
                     for f in sorted(_worlds.HERE.rglob("*.json")))


def load_worlds(folder: str | Path) -> list[World]:
    """The training or dev worlds in `folder`, in file-name order, loaded with role "train".

    Refused: a folder inside the measured suites (`proven.worlds.HERE`), a folder that
    holds them, a link that resolves there, and a copy of a measured world placed
    elsewhere (same slug)."""
    folder = Path(folder)
    if _inside(folder, _worlds.HERE) or _inside(_worlds.HERE, folder):
        raise ValueError(f"{folder} is in the measured suites; RL never reads those worlds")
    files = sorted(folder.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no world files in {folder}")
    out = []
    for file in files:
        if _inside(file, _worlds.HERE):
            raise ValueError(f"{file} resolves into the measured suites")
        world = _worlds.load(file, role="train")
        if world.name in measured_slugs():
            raise ValueError(f"{file}: {world.name!r} is a measured world; RL never uses it")
        out.append(world)
    return out


def measured_phrases() -> frozenset[str]:
    """Every way a measured world describes a cause, lower-cased. Read for one purpose:
    `leaks` drops a close that would state one of them word for word."""
    return frozenset(phrase for folder in sorted(_worlds.HERE.iterdir()) if folder.is_dir()
                     for world in _worlds.suite(folder.name, root=_worlds.HERE)
                     for phrase in _worlds.vocabulary(world)["phrases"])


def leaks(scenario: Scenario, measured: frozenset[str] | set[str]) -> bool:
    return any(label.gold["reason_text"].lower() in measured for label in scenario.labels)


@lru_cache(maxsize=16)
def world_order(n: int, seed: int) -> tuple[int, ...]:
    """The order worlds are visited in: a permutation of range(n) fixed by `seed`."""
    order = list(range(n))
    random.Random(f"world-order-{seed}").shuffle(order)
    return tuple(order)


def pick_world(worlds: list[World] | None, index: int, seed: int = 0) -> World | None:
    """Round-robin: episode `index` (the screening cursor) comes from the `index`-th world
    of a seeded order, so every world is visited once per len(worlds) episodes and a run is
    reproducible from --seed. None (the default world) when no worlds are given."""
    if not worlds:
        return None
    return worlds[world_order(len(worlds), seed)[index % len(worlds)]]


def training_episode(pool: list[int], cursor: int, phrasing: str,
                     worlds: list[World] | None = None, seed: int = 0,
                     measured: frozenset[str] | set[str] = frozenset()) -> Scenario | None:
    """The close at screening position `cursor`, or None if it states a measured phrase."""
    scenario = episode(pool[cursor % len(pool)], phrasing, pick_world(worlds, cursor, seed))
    return None if measured and leaks(scenario, measured) else scenario


def validation_closes(seeds: list[int], count: int, phrasing: str,
                      worlds: list[World] | None = None,
                      measured: frozenset[str] | set[str] = frozenset()) -> tuple[list[Scenario], int]:
    """(`count` closes, how many of `seeds` were consumed). With worlds, close i comes from
    world i % len(worlds), so the worlds' shares differ by at most one close. Seeds are
    taken in order; one whose close states a measured phrase is passed over."""
    out: list[Scenario] = []
    used = 0
    for seed in seeds:
        if len(out) == count:
            break
        used += 1
        scenario = episode(seed, phrasing, worlds[len(out) % len(worlds)] if worlds else None)
        if measured and leaks(scenario, measured):
            continue
        out.append(scenario)
    if len(out) < count:
        raise ValueError(f"only {len(out)} of {count} validation closes could be drawn")
    return out, used


# ── decisions the training loop makes without a model ────────────────────

SAME = 1e-6          # rewards are rounded to 4 places; closer than this is the same reward


def gold_proposals(scenario: Scenario) -> list[ClaimProposal]:
    return [proposal_from_gold(label.gold) for label in scenario.labels]


def ceiling(scenario: Scenario) -> float:
    """What the generator's own reply earns on this close. On about four closes in ten it
    is under 0.95 (a correct sentence the checker leaves in REVIEW scores 0 whatever the
    proposer writes), so "the greedy reply scores below 0.95" does not mean there is
    anything to learn."""
    return score_proposals(scenario, gold_proposals(scenario)).reward


def has_headroom(greedy: float, top: float | None, hard_below: float, margin: float = 0.02) -> bool:
    """Train on a close only if the greedy reply leaves something on the table: it scores
    under `hard_below`, and (when the gold reply's reward `top` is known) at least `margin`
    under that."""
    if greedy >= hard_below:
        return False
    return top is None or greedy < top - margin


def worth_sampling(greedy: float, probes: list[float]) -> bool:
    """After the first few sampled replies: go on only if one of them scored differently
    from the greedy reply. If they all match it, the leave-one-out advantages so far are
    all zero and the remaining samples would most likely be paid for and discarded."""
    return any(abs(r - greedy) > SAME for r in probes)


def has_signal(rewards: list[float]) -> bool:
    return len(rewards) > 1 and max(rewards) - min(rewards) > SAME


def loo_advantages(rewards: list[float]) -> list[float]:
    """Reward minus the mean reward of the other replies to the same close."""
    k = len(rewards)
    if k < 2:
        return [0.0] * k
    total = sum(rewards)
    return [r - (total - r) / (k - 1) for r in rewards]


def gradient_rows(advantages: list[float], width: int = 2) -> list[list[int]]:
    """Indices of the replies to push through the model, `width` at a time. A reply whose
    advantage is zero adds exactly nothing to the gradient, so it is left out."""
    keep = [i for i, a in enumerate(advantages) if abs(a) > 1e-9]
    return [keep[i:i + width] for i in range(0, len(keep), width)]


def reply_tokens_estimate(scenario: Scenario) -> float:
    """Tokens the gold reply needs, at about four characters a token (no tokenizer)."""
    return len(json.dumps({"claims": scenario.gold_claims()}, ensure_ascii=False)) / 4


def _selfcheck(n: int = 60) -> None:
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
