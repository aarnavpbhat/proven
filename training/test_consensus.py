"""Tests for test-time selection (`consensus.py`). No model, no MLX; candidates are built by hand.

    PROVEN_ENV_FILE=/dev/null python -m pytest -q training/test_consensus.py

`consensus.py` is loaded by path.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from proven.claims import ClaimProposal  # noqa: E402
from proven.evaluate import proposal_from_gold  # noqa: E402
from proven.synth import generate, generate_split, seeds  # noqa: E402
from proven.verify import Policy  # noqa: E402

_spec = importlib.util.spec_from_file_location("consensus", HERE / "consensus.py")
sel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sel)

ABSENT = ("zzgizmo", "qqwidget", "xxnothing")       # words in no memo of any world


def P(quote: str, *terms: str, **fields) -> ClaimProposal:
    return ClaimProposal(quote=quote, driver_terms=tuple(terms), **fields)


@pytest.fixture(scope="module")
def close():
    """A correct train close, its first label, and that label's gold proposal."""
    for seed in seeds("train", 40):
        scenario = generate(seed, phrasing="paraphrase")
        label = scenario.labels[0]
        gold = proposal_from_gold(label.gold)
        found = sel.support(gold, scenario.ledger, scenario.explanation)
        if label.requirement == "PASS" and len(found["matched_terms"]) >= 2:
            return scenario, label, gold
    raise AssertionError("no usable close")


# ── alignment and votes (ledger-blind) ───────────────────────────────────

def test_claims_are_aligned_by_exact_quote():
    out = sel.merge_votes([[P("A rose.", "x1a"), P("B fell.", "y1a")],
                           [P("B fell.", "y2a"), P("A rose.", "x2a")],
                           [P("A rose", "never")]])           # no full stop: another claim
    assert [p.quote for p in out] == ["A rose.", "B fell."]
    assert out[0].driver_terms == ("x1a", "x2a")
    assert out[1].driver_terms == ("y1a", "y2a")


def test_terms_are_ordered_by_votes_then_first_seen():
    out = sel.merge_votes([[P("q", "alpha", "beta")], [P("q", "gamma", "beta")],
                           [P("q", "gamma", "beta", "delta")]])
    assert out[0].driver_terms == ("beta", "gamma", "alpha", "delta")


def test_a_term_repeated_in_one_reply_is_one_vote():
    out = sel.merge_votes([[P("q", "alpha", "alpha", "alpha")], [P("q", "beta")], [P("q", "beta")]])
    assert out[0].driver_terms == ("beta", "alpha")


def test_terms_are_deduplicated_without_regard_to_case():
    out = sel.merge_votes([[P("q", "Cyber", "audit  fee")], [P("q", "cyber ", "Audit Fee", "CYBER")]])
    assert out[0].driver_terms == ("Cyber", "audit  fee".strip())
    assert len({t.lower() for t in out[0].driver_terms}) == 2


def test_the_cap():
    replies = [[P("q", *[f"term{i}{j}" for j in range(6)])] for i in range(4)]
    assert len(sel.merge_votes(replies)[0].driver_terms) == 8
    assert len(sel.merge_votes(replies, max_terms=3)[0].driver_terms) == 3
    assert sel.merge_votes(replies, max_terms=0)[0].driver_terms == ()


def test_fields_come_from_the_greedy_reply():
    greedy = P("q", "aaa", account="Insurance", change_text="$5K", driver_text="x", extractor="g")
    other = P("q", "bbb", account="Rent", change_text="$9K", driver_text="y", extractor="s")
    out = sel.merge_votes([[greedy], [other], [other]])
    assert out[0] == replace(greedy, driver_terms=("bbb", "aaa"))


def test_a_claim_missing_from_greedy_needs_half_the_candidates():
    seen_twice = [P("late", "aaa", account="Rent", change_text="$9K"),
                  P("late", "bbb", account="Rent", change_text="$8K"),
                  P("late", "aaa", account="Legal", change_text="$8K")]
    out = sel.merge_votes([[P("q", "zzz")], [seen_twice[0]], [seen_twice[1]], [seen_twice[2]]])
    assert [p.quote for p in out] == ["q", "late"]
    assert (out[1].account, out[1].change_text) == ("Rent", "$8K")     # most common, per field
    assert out[1].driver_terms == ("aaa", "bbb")
    # one of four is under half; two of four is exactly half
    assert [p.quote for p in sel.merge_votes([[P("q")], [P("late")], [], []])] == ["q"]
    assert [p.quote for p in sel.merge_votes([[P("q")], [P("late")], [P("late")], []])] == ["q", "late"]


def test_a_tie_between_field_values_goes_to_the_earliest_candidate():
    out = sel.merge_votes([[], [P("late", account="Rent")], [P("late", account="Legal")]])
    assert out[0].account == "Rent"


def test_empty_candidates(close):
    scenario, _label, gold = close
    for merged in (sel.merge_votes([]), sel.merge_votes([[]]), sel.merge_votes([[], [], []]),
                   sel.merge([], scenario.ledger, scenario.explanation),
                   sel.merge([[], []], scenario.ledger, scenario.explanation)):
        assert merged == []
    # an unparseable greedy reply: the samples' claim survives if half the candidates have it
    out = sel.merge([[], [gold]], scenario.ledger, scenario.explanation)
    assert [p.quote for p in out] == [gold.quote]


# ── the ledger's say ─────────────────────────────────────────────────────

def test_support_reports_what_the_checker_matched(close):
    scenario, label, gold = close
    mixed = replace(gold, driver_terms=gold.driver_terms + ABSENT[:1] + ("the", "ab"))
    found = sel.support(mixed, scenario.ledger, scenario.explanation)
    assert found["admitted"] and found["account"] == label.account
    assert set(found["matched_terms"]) <= set(found["matched_terms_any_period"]) <= set(gold.driver_terms)
    assert found["unmatched_terms"] == [ABSENT[0]]
    assert {"the", "ab"} <= set(found["dropped_terms"])
    assert found["transactions"] >= 1 and found["amount"] > 0
    assert found["share"] == pytest.approx(found["movement"] / found["change"], abs=1e-3)
    assert found["verdict"] in ("PASS", "FAIL", "REVIEW")
    assert found["waiting_on_model"] == (found["verdict"] == "REVIEW"
                                         and sel.MODEL_SUPPORT in found["findings"])


def test_support_of_a_quote_that_is_not_in_the_text(close):
    scenario, _label, gold = close
    found = sel.support(replace(gold, quote="Nothing like this was written."),
                        scenario.ledger, scenario.explanation)
    assert not found["admitted"] and found["rejection"] == "quote_not_in_text"
    assert found["verdict"] is None and found["matched_terms"] == []


def test_ledger_supported_terms_are_ranked_first(close):
    scenario, _label, gold = close
    found = sel.support(gold, scenario.ledger, scenario.explanation)
    good = found["matched_terms_any_period"][:2]
    # the absent words win the vote 3-1; the ledger still puts its own words first
    replies = [[replace(gold, driver_terms=ABSENT)], [replace(gold, driver_terms=ABSENT)],
               [replace(gold, driver_terms=ABSENT + (good[0],))],
               [replace(gold, driver_terms=(good[1], good[0]))]]
    blind = sel.merge_votes(replies)[0].driver_terms
    aware = sel.merge(replies, scenario.ledger, scenario.explanation)[0].driver_terms
    assert blind == ABSENT + (good[0], good[1])
    assert aware == (good[0], good[1]) + ABSENT
    assert sel.merge(replies, scenario.ledger, scenario.explanation, max_terms=2)[0].driver_terms \
        == (good[0], good[1])
    assert set(sel.merge_votes(replies, max_terms=2)[0].driver_terms) <= set(ABSENT)


def test_a_stop_word_is_never_counted_as_supported(close):
    scenario, _label, gold = close
    replies = [[replace(gold, driver_terms=("the", "of", gold.driver_terms[0]))]] * 2
    aware = sel.merge(replies, scenario.ledger, scenario.explanation)[0].driver_terms
    assert aware[0] == gold.driver_terms[0]


def test_merge_without_a_resolvable_account_falls_back_to_the_vote(close):
    scenario, _label, _gold = close
    replies = [[P("Not a sentence of this text.", "alpha", "beta")],
               [P("Not a sentence of this text.", "beta")]]
    assert sel.merge(replies, scenario.ledger, scenario.explanation) == sel.merge_votes(replies)


# ── over real closes ─────────────────────────────────────────────────────

def _noisy(scenario, rng: random.Random, k: int = 4) -> list[list[ClaimProposal]]:
    replies = []
    for _ in range(k):
        reply = []
        for label in scenario.labels:
            if rng.random() < 0.15:
                continue                                        # this reply missed the sentence
            gold = proposal_from_gold(label.gold)
            terms = [t.upper() if rng.random() < 0.2 else t
                     for t in gold.driver_terms if rng.random() < 0.6]
            terms += rng.sample(ABSENT + ("insurance", "the", "fees", "audit"), rng.randrange(0, 4))
            reply.append(replace(gold, driver_terms=tuple(terms)))
        if rng.random() < 0.2:
            reply.append(P("An invented sentence.", "invented"))
        rng.shuffle(reply)
        replies.append(reply)
    return replies


def test_property_over_real_closes():
    rng = random.Random(7)
    for scenario in generate_split("train", 30, "paraphrase"):
        replies = _noisy(scenario, rng)
        quotes = {p.quote for reply in replies for p in reply}
        proposed = {(p.quote, " ".join(t.lower().split())) for reply in replies for p in reply
                    for t in p.driver_terms}
        for cap in (8, 2):
            blind = sel.merge_votes(replies, cap)
            aware = sel.merge(replies, scenario.ledger, scenario.explanation, cap)
            assert [p.quote for p in blind] == [p.quote for p in aware]
            for merged in (blind, aware):
                assert len({p.quote for p in merged}) == len(merged)
                assert {p.quote for p in replies[0]} <= {p.quote for p in merged}
                for p in merged:
                    assert p.quote in quotes
                    assert len(p.driver_terms) <= cap
                    lowered = [" ".join(t.lower().split()) for t in p.driver_terms]
                    assert len(set(lowered)) == len(lowered)
                    assert all((p.quote, t) in proposed for t in lowered)
        # with room for every term, the ledger changes the order and nothing else
        wide_blind = sel.merge_votes(replies, 99)
        wide_aware = sel.merge(replies, scenario.ledger, scenario.explanation, 99)
        assert [sorted(p.driver_terms) for p in wide_blind] == [sorted(p.driver_terms) for p in wide_aware]


# ── the safety note, pinned ──────────────────────────────────────────────

def test_picked_terms_never_pass_or_fail_a_claim_under_the_default_policy():
    """Whatever terms are added, a claim's verdict stays or moves to REVIEW."""
    rng = random.Random(3)
    for phrasing in ("seen", "paraphrase"):
        for scenario in generate_split("train", 40, phrasing):
            replies = _noisy(scenario, rng)
            merged = {p.quote: p for p in sel.merge(replies, scenario.ledger, scenario.explanation)}
            for label in scenario.labels:
                gold = proposal_from_gold(label.gold)
                bare = sel.support(replace(gold, driver_terms=()), scenario.ledger, scenario.explanation)
                if label.quote not in merged:
                    continue
                picked = sel.support(replace(gold, driver_terms=merged[label.quote].driver_terms),
                                     scenario.ledger, scenario.explanation)
                assert picked["verdict"] in (bare["verdict"], "REVIEW")


def test_a_ledger_matched_term_can_take_a_correct_fail_away():
    """Seed 31, "seen": the sentence blames the D&O policy; the cyber policy moved. One sample
    in four guesses "cyber". The greedy reply and the checker FAIL the sentence; `merge` puts
    it in front of the reviewer as supported-by-model-terms. Never a PASS; a lost FAIL."""
    scenario = generate(31, phrasing="seen")
    label = scenario.labels[0]
    assert label.family == "wrong_cause"
    gold = proposal_from_gold(label.gold)
    replies = [[gold], [gold], [gold], [replace(gold, driver_terms=("cyber", "binder"))]]
    greedy = sel.support(gold, scenario.ledger, scenario.explanation)
    merged = sel.merge(replies, scenario.ledger, scenario.explanation)[0]
    picked = sel.support(merged, scenario.ledger, scenario.explanation)
    assert greedy["verdict"] == "FAIL" and "WRONG_CAUSE" in greedy["findings"]
    assert picked["verdict"] == "REVIEW" and picked["waiting_on_model"]
    # the cyber lines are in the prior month here (the account fell), hence "any period"
    assert "cyber" in picked["matched_terms_any_period"]


def test_teach_only_refuses_the_anchoring_policy():
    sel.assert_teach_only(None)
    sel.assert_teach_only(Policy())
    with pytest.raises(ValueError):
        sel.assert_teach_only(Policy(model_terms_anchor=True))

