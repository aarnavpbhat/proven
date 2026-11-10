"""A simulated reviewer loop: what do confirmed lessons buy on closes never taught from?

The guard sends a claim to REVIEW when its support rests on the model's search terms
(`SUPPORT_RESTS_ON_MODEL_TERMS`). In the console a reviewer can confirm those terms as a
lesson. This module plays that reviewer over the synthetic benchmark:

  * on each TEACHING close, a claim is taught from only if the generator's label says the
    explanation is right, the claim sits in REVIEW for that one reason, and confirming the
    terms that matched ledger transactions turns it into a PASS;
  * the lesson is "the stated reason, verbatim -> those terms", trimmed by
    `learned.trim_terms` (no word that matches only routine lines that did not move, none
    the PASS does not need) and validated by `learned.make_entry`, as the console's would be;
  * the lessons are then measured on the HELD closes (the second half of the split),
    which no lesson was taught from.

WHAT THIS IS NOT. The simulated reviewer never confirms a wrong explanation, because it
reads the label; a person can. And the synthetic phrasings come from a finite pool, so the
curve saturates far sooner than real commentary would. It is an upper bound on a careful
reviewer, measured with the same kill criteria as the benchmark.
"""
from __future__ import annotations

import random
from collections.abc import Callable

from proven import learned
from proven.evaluate import OracleExtractor, score_claim
from proven.extract import RuleExtractor
from proven.report import Extractor, run
from proven.synth import Scenario, generate, generate_split

MODEL_SUPPORT = "SUPPORT_RESTS_ON_MODEL_TERMS"
STEPS = (0, 10, 20, 55, 110, 220)


def trimmed_lesson(scenario: Scenario, lessons: list[dict], result: dict, terms: list[str],
                   extractor: Extractor) -> tuple[dict, str | None] | None:
    """The lesson confirmed from one claim, with only the words `learned.trim_terms` keeps,
    and the claim's verdict with it; None when Proven would not learn it."""
    quote, driver = result["claim"]["quote"], result["claim"]["driver"]

    def verdict(words: list[str]) -> str | None:
        with learned.lexicon(lessons + [learned.make_entry([driver], words)]):
            after = run(scenario.explanation, scenario.ledger, extractor=extractor)
        return next((r["verdict"] for r in after["claims"] if r["claim"]["quote"] == quote), None)

    try:
        _triggers, words = learned.validate([driver], terms)
        trimmed = learned.trim_terms(list(words), scenario.ledger, result["claim"].get("account"),
                                     verdict)
        entry = learned.make_entry([driver], trimmed.kept, quote=quote, action="simulated",
                                   note="teachsim")
    except learned.LessonRefused:
        return None
    return entry, trimmed.verdict


def teach(pool: list[Scenario], proposer_for: Callable[[Scenario], Extractor]) -> list[dict]:
    """The lessons a label-reading reviewer would confirm, working through `pool` in order.

    A reviewer reading the label knows the explanation is right, not that every word the
    model proposed belongs to its cause: the confirmed words are those `learned.trim_terms`
    keeps (none that match only routine lines that did not move, none the PASS does not need)."""
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
            made = trimmed_lesson(scenario, lessons, result, terms, proposer_for(scenario))
            if made is None or made[1] != "PASS":
                continue
            entry = made[0]
            key = (tuple(entry["triggers"]), tuple(entry["terms"]))
            if key not in known:
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
             steps: tuple[int, ...] = STEPS, world=None) -> dict:
    """Teach from the first half of the test split, measure the second half with the rules.

    `proposer` is a model extractor (its answers should be cached); the default is the
    oracle, whose terms are the generator's gold ones and are treated as a model's."""
    scenarios = generate_split("test", n, phrasing, world=world)
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


WORLD_STEPS = (0, 10, 25, 50)
_COUNTS = ("claims", "decided", "controls", "controls_passed", "control_fails", "defects",
           "defects_caught", "unsafe_passes", "lessons")


def simulate_worlds(suite: str = "unseen", n: int = 100, phrasing: str = "heldout", proposer=None,
                    steps: tuple[int, ...] = WORLD_STEPS) -> dict:
    """`simulate` in every world of a suite, each taught and measured on its own: a lesson
    confirmed in one company's books is never carried to another's. The pooled rows add the
    counts up; the reward is weighted by claims."""
    from proven import worlds
    per_world = []
    for world in worlds.suite(suite):
        result = simulate(n, phrasing, proposer, steps, world=world)
        per_world.append({"world": world.name, "accounts": len(world.specs), "rows": result["rows"]})
    pooled = []
    for i, step in enumerate(per_world[0]["rows"]):
        rows = [w["rows"][i] for w in per_world]
        row = {"taught_closes": step["taught_closes"], **{k: sum(r[k] for r in rows) for k in _COUNTS}}
        row["decided_share"] = round(row["decided"] / row["claims"], 4)
        row["mean_reward"] = round(sum(r["mean_reward"] * r["claims"] for r in rows) / row["claims"], 4)
        shares = sorted(r["decided_share"] for r in rows)
        row["worst_world"], row["best_world"] = shares[0], shares[-1]
        pooled.append(row)
    return {"suite": suite, "phrasing": phrasing, "closes_per_world": n,
            "proposer": f"{proposer.name}/{proposer.version}" if proposer is not None else "oracle/0.1",
            "worlds": per_world, "rows": pooled}


# ── a reviewer's time, counted in confirmations ─────────────────────────

CHECKPOINTS = (0, 5, 10, 20, 40)
ORDERS = ("arrival", "frequency", "hindsight")


def skewed_split(n: int, phrasing: str, skew: float, seed: int = 0) -> list[Scenario]:
    """`n` test closes whose main sentence's phrase follows a Zipf law with exponent `skew`.

    The generator draws a cause's phrase uniformly; real commentary repeats a few phrases
    far more often than the rest. Each phrase of the tier gets a rank (a seeded shuffle) and
    weight 1 / rank**skew, and test closes are kept with probability weight / max weight, in
    seed order, until `n` are kept. Deterministic for a given (n, phrasing, skew, seed)."""
    from proven.synth import WORLD, phrases_for, seeds
    phrases = sorted({p for spec in WORLD for event in spec.events
                      for p in phrases_for(event, phrasing, "test")})
    rng = random.Random(seed)
    rng.shuffle(phrases)
    weight = {p: 1.0 / (rank + 1) ** skew for rank, p in enumerate(phrases)}
    out: list[Scenario] = []
    for s in seeds("test", 40 * n):
        scenario = generate(s, phrasing=phrasing)
        if rng.random() < weight.get(scenario.labels[0].gold["reason_text"], 0.0):
            out.append(scenario)
            if len(out) == n:
                break
    return out


def curve(n: int = 440, phrasing: str = "heldout", proposer=None, *, order: str = "frequency",
          checkpoints: tuple[int, ...] = CHECKPOINTS, careless: float = 0.0, use_gate: bool = False,
          seed: int = 0, max_asks: int | None = None, skew: float = 0.0,
          any_model_match: bool = False) -> dict:
    """Decided share on the untaught half after k confirmations, for one teaching order.

    The reviewer works down a queue of waiting claims (`teachqueue`), ranked by `order` and
    re-ranked after every lesson. Asked about a claim, it decides with the label:

      * a RIGHT explanation: it confirms the model's matched terms if that turns the claim
        into a PASS (the careful reviewer of `teach`, with the words `learned.trim_terms`
        keeps);
      * a WRONG explanation: with probability `careless` it confirms the terms anyway
        (trimmed the same way: the trim reads the ledger, never the label);
        otherwise it records "Confirm defect", which becomes a stored case for the gate.

    With `use_gate`, every confirmation goes through `gate.impact` (the train-split
    regression set plus the cases recorded so far in this run) and a refused lesson is not
    stored. Confirmations are the x-axis: one per lesson stored. Every question put to the
    reviewer, confirmed or not, is counted in `asks`.

    `order` "hindsight" ranks by the measured half itself: not a policy a reviewer could
    follow, but the bound on what any order of the same lessons reaches. `skew` > 0 draws
    the closes from `skewed_split` instead of the plain test split (oracle only: a model's
    proposals are cached for the plain split). `any_model_match` puts every REVIEW claim
    whose model terms matched transactions in the queue, not only those whose support rests
    on them: more wrong explanations for a careless reviewer to confirm."""
    from proven import gate, teachqueue
    if order not in ORDERS:
        raise ValueError(f"order must be one of {', '.join(ORDERS)}")
    if skew and proposer is not None:
        raise ValueError("a skewed population is generated afresh; use the oracle proposer with it")
    rng = random.Random(seed)
    scenarios = skewed_split(n, phrasing, skew) if skew else generate_split("test", n, phrasing)
    half = len(scenarios) // 2
    pool, held = scenarios[:half], scenarios[half:]
    proposer_for = (lambda s: proposer) if proposer is not None else OracleExtractor
    rules = RuleExtractor()
    labels = [{label.quote: label for label in s.labels} for s in pool]
    lessons: list[dict] = []
    cases: list = []
    known: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    asked: set[tuple] = set()
    ranker = teachqueue.Ranker()
    stats = {"asks": 0, "confirmations": 0, "careful": 0, "careless": 0, "refused_right": 0,
             "refused_wrong": 0, "declined_wrong": 0, "gate_ms": 0.0, "gate_calls": 0}
    refusals: list[dict] = []
    score = None
    if order == "hindsight":
        # Not a policy: it ranks by the measured half, which no reviewer can see. It is the
        # bound on what any ordering of the same lessons could reach.
        held_drivers = [(p.driver_text or "").lower() for s in held
                        for p in rules.propose(s.explanation, s.ledger) if p.driver_text]
        score = lambda trigger: sum(gate.fires(trigger, d) for d in held_drivers)  # noqa: E731

    def report_for(i: int) -> dict:
        with learned.lexicon(lessons):
            return run(pool[i].explanation, pool[i].ledger, extractor=proposer_for(pool[i]))

    reports = [report_for(i) for i in range(len(pool))]
    drivers = [[(c["claim"].get("driver") or "").lower() for c in r["claims"]] for r in reports]
    rows: list[dict] = []

    def checkpoint(label: str) -> None:
        rows.append({"confirmations": stats["confirmations"], "label": label, "asks": stats["asks"],
                     "lessons": len(lessons), "careless_lessons": stats["careless"],
                     **measure(held, lessons, lambda _s: rules)})

    checkpoint("0")
    wanted = {c for c in checkpoints if c > 0}
    while max_asks is None or stats["asks"] < max_asks:
        waiting = []
        for i, report in enumerate(reports):
            for position, item in enumerate(teachqueue.waiting_in(report, any_model_match=any_model_match)):
                key = (i, item["quote"])
                if key not in asked:
                    waiting.append(teachqueue.Waiting(key, i * 100 + position, item["quote"],
                                                      item["driver"], tuple(item["terms"])))
        if not waiting:
            break
        best = ranker.rank(waiting, "frequency" if score else order, score)[0]["members"][0]
        asked.add(best.key)
        stats["asks"] += 1
        i, quote = best.key
        label = labels[i].get(quote)
        right = label is not None and label.requirement == "PASS"
        if not right and rng.random() >= careless:
            stats["declined_wrong"] += 1
            cases.extend(gate.probes_for(pool[i].explanation, pool[i].ledger, [(quote, {
                "known": "wrong", "source": "case", "family": "confirm_defect", "phrasing": phrasing,
                "ref": pool[i].scenario_id})]))
            continue
        claim = next((r for r in reports[i]["claims"] if r["claim"]["quote"] == quote), None)
        if claim is None:
            continue
        made = trimmed_lesson(pool[i], lessons, claim, list(best.terms), proposer_for(pool[i]))
        if made is None:
            continue
        entry, verdict_after = made
        key = (tuple(entry["triggers"]), tuple(entry["terms"]))
        if key in known:
            continue
        if right and verdict_after != "PASS":
            continue
        if use_gate:
            verdict = gate.impact(entry, lessons, cases)
            stats["gate_ms"] += verdict["elapsed_ms"]
            stats["gate_calls"] += 1
            if not verdict["accepted"]:
                stats["refused_right" if right else "refused_wrong"] += 1
                refusals.append({"trigger": entry["triggers"][0], "terms": entry["terms"],
                                 "explanation_right": right,
                                 "family": label.family if label is not None else None,
                                 "blocking": verdict["blocking_count"],
                                 "example": verdict["blocking"][0] if verdict["blocking"] else None})
                continue
        known.add(key)
        lessons.append(entry)
        stats["confirmations"] += 1
        stats["careful" if right else "careless"] += 1
        if right:
            cases.extend(gate.probes_for(pool[i].explanation, pool[i].ledger, [(quote, {
                "known": "right", "source": "case", "family": "accept_convention",
                "phrasing": phrasing, "ref": pool[i].scenario_id, "expected": "PASS"})]))
        for j, lows in enumerate(drivers):
            if any(gate.touches(entry, low) for low in lows if low):
                reports[j] = report_for(j)
        if stats["confirmations"] in wanted:
            checkpoint(str(stats["confirmations"]))
    if rows[-1]["confirmations"] == stats["confirmations"] and len(rows) > 1:
        rows[-1]["label"] += " (all)"
    else:
        checkpoint("all")
    stats["gate_ms"] = round(stats["gate_ms"], 1)
    return {"phrasing": phrasing, "order": order, "careless": careless, "gate": use_gate, "seed": seed,
            "skew": skew, "any_model_match": any_model_match, "held_closes": len(held),
            "proposer": f"{proposer.name}/{proposer.version}" if proposer is not None else "oracle/0.1",
            "stats": stats, "refusals": refusals, "rows": rows}
