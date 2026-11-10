"""Which ledger words a lesson may keep: `learned.trim_terms` and where it is applied."""
from dataclasses import replace

import pytest

from proven import learned, showcase, teachqueue, teachsim, worlds
from proven.evaluate import OracleExtractor
from proven.extract import RuleExtractor
from proven.ledger import Account, Ledger, Transaction
from proven.report import run
from proven.server import App, BadRequest
from proven.synth import generate_split

ACCOUNT = "Facilities"


def book(routine_current: float = 4100.0) -> Ledger:
    """A routine monthly bill from one vendor, and a repair job from another in October."""
    return Ledger("Test Co", "2026-09", "2026-10", (Account(ACCOUNT),), (
        Transaction("T1", "2026-09-30", ACCOUNT, "Northgate Roofing Services", "Monthly gutter servicing", 4000.0),
        Transaction("T2", "2026-10-31", ACCOUNT, "Northgate Roofing Services", "Monthly gutter servicing",
                    routine_current),
        Transaction("T3", "2026-10-12", ACCOUNT, "Harbor Waterproofing Co", "Leak repair — membrane patch", 3000.0),
        Transaction("T4", "2026-10-20", ACCOUNT, "Harbor Waterproofing Co", "Leak repair — drain reroute", 9000.0),
    ))


def passes_with(*needed: str):
    """A stand-in for re-checking the claim: PASS when any of `needed` is among the words."""
    return lambda words: "PASS" if set(words) & set(needed) else "REVIEW"


# ── the rules ──

def test_a_word_that_matches_only_a_routine_line_that_did_not_move_is_dropped():
    out = learned.trim_terms(["leak", "roofing"], book(), ACCOUNT, passes_with("leak"))
    assert out.kept == ["leak"] and out.verdict == "PASS"
    assert out.dropped == [{"term": "roofing", "reason": learned.ROUTINE_ONLY}]


def test_a_word_the_pass_does_not_need_is_dropped_least_moved_first():
    # Both words match the repair; "membrane" matches less of it and is tried first.
    out = learned.trim_terms(["leak", "membrane"], book(), ACCOUNT, passes_with("leak", "membrane"))
    assert out.kept == ["leak"]
    assert out.dropped == [{"term": "membrane", "reason": learned.NOT_NEEDED}]


def test_a_lesson_with_nothing_left_is_refused():
    with pytest.raises(learned.LessonRefused, match="none of them names the stated cause"):
        learned.trim_terms(["roofing", "gutter"], book(), ACCOUNT, lambda _words: "PASS")


def test_a_routine_bill_that_moved_is_a_cause_and_keeps_its_word():
    out = learned.trim_terms(["roofing"], book(routine_current=9000.0), ACCOUNT, passes_with("roofing"))
    assert out.kept == ["roofing"] and out.dropped == []


def test_a_pass_that_rests_on_a_routine_word_is_reported_not_kept():
    out = learned.trim_terms(["leak", "roofing"], book(), ACCOUNT, passes_with("roofing"))
    assert out.kept == ["leak"] and out.verdict == "REVIEW"
    assert "does not pass" in learned.trim_text(out)


def test_a_lesson_that_does_not_pass_the_claim_is_left_as_it_is():
    out = learned.trim_terms(["leak", "roofing"], book(), ACCOUNT, lambda _words: "FAIL")
    assert (out.kept, out.dropped, out.verdict) == (["leak", "roofing"], [], "FAIL")


# ── where they apply ──

TRAVEL = "Travel fell $12K, reflecting fewer customer visits."


class FlightsAndOffsite:
    """The rule reader, with a model's guess of two words for the travel claim's reason."""

    name, version = "fake", "0"

    def propose(self, text, ledger):
        return [replace(p, driver_terms=("flights", "offsite")) if p.quote == TRAVEL else p
                for p in RuleExtractor().propose(text, ledger)]


def test_the_queue_suggests_only_the_words_that_survive(tmp_path):
    report = run(showcase.EXPLANATION, showcase.ledger(), extractor=FlightsAndOffsite())
    assert teachqueue.record_run(tmp_path, {"scenario_id": "showcase"}, report, []) == 1
    stored = teachqueue.load_runs(tmp_path)[0]["claims"][0]
    assert stored["terms"] == ["offsite"]
    assert [d["term"] for d in stored["dropped"]] == ["flights"]


def test_the_console_refuses_a_lesson_with_a_word_it_does_not_need(tmp_path):
    app = App(tmp_path)
    body = {"run_id": "r1", "claim_id": "C7", "quote": TRAVEL, "verdict": "REVIEW",
            "action": "accept_convention", "note": "The offsite is how this writer counts visits.",
            "explanation": showcase.EXPLANATION, "scenario_id": "showcase"}
    with pytest.raises(BadRequest, match="Teach the lesson with only “offsite”") as refused:
        app.record({**body, "learn": {"triggers": ["fewer customer visits"],
                                      "terms": ["offsite", "flights"], "confirm_pass": True}})
    assert refused.value.impact["trim"]["kept"] == ["offsite"]
    assert learned.load(tmp_path) == [] and not (tmp_path / "resolutions.jsonl").exists()
    saved = app.record({**body, "learn": {"triggers": ["fewer customer visits"], "terms": ["offsite"],
                                          "confirm_pass": True}})
    assert saved["verdict_after"] == "PASS"


# ── suite level ──

@pytest.mark.parametrize("index", [0, 1])
def test_oracle_teaching_in_a_sealed_world_is_safe_and_unchanged_by_the_trim(index, monkeypatch):
    """The oracle proposes only words of its own cause, so the trim must not cost it anything."""
    world = worlds.suite("sealed")[index]
    closes = generate_split("test", 100, "heldout", world=world)
    rules = RuleExtractor()
    trimmed = teachsim.teach(closes[:50], OracleExtractor)
    with_trim = teachsim.measure(closes[50:], trimmed, lambda _s: rules)

    def keep_all(terms, _ledger, _account, verdict, materiality=None):
        return learned.Trimmed(list(terms), [], verdict(list(terms)))

    monkeypatch.setattr(learned, "trim_terms", keep_all)
    untrimmed = teachsim.teach(closes[:50], OracleExtractor)
    without = teachsim.measure(closes[50:], untrimmed, lambda _s: rules)
    assert with_trim["unsafe_passes"] == 0 and with_trim["control_fails"] == 0
    # Every verdict count is the same; the reward may move a little, as fewer words cite
    # fewer transactions as evidence.
    counts = [k for k in with_trim if k != "mean_reward"]
    assert [with_trim[k] for k in counts] == [without[k] for k in counts]
    assert len(trimmed) == len(untrimmed)
