"""The lesson safety gate: bad lessons are refused with a reason, good ones pass, and the
regression set never touches the test split."""
import random
import time

import pytest

from proven import gate, learned, showcase
from proven.server import App, LessonBlocked
from proven.synth import FAMILIES, PHRASINGS

TRAVEL = "Travel fell $12K, reflecting fewer customer visits."


def lesson(triggers, terms):
    return learned.make_entry(list(triggers), list(terms))


# ── the regression set ──

def test_regression_set_is_train_split_only_and_covers_every_family_and_phrasing():
    probes, info = gate.regression_set()
    assert info["split"] == "train" and info["claims"] == len(probes) > 1000
    assert {int(p.ref[4:]) % 5 for p in probes} <= {1, 2, 3, 4}       # seed % 5 == 0 is test
    defect_families = {f.name for f in FAMILIES if f.kind == "defect"}
    assert {p.family for p in probes if p.known == "wrong"} == defect_families
    assert {p.phrasing for p in probes} == set(PHRASINGS)
    assert all(p.known == "right" for p in probes if p.family.startswith("control"))


def test_a_check_is_fast_once_the_set_is_built():
    gate.regression_set()
    started = time.perf_counter()
    report = gate.impact(lesson(["board coverage"], ["d&o"]), [])
    assert (time.perf_counter() - started) < 2.0 and report["elapsed_ms"] < 2000


def test_claims_the_lesson_does_not_touch_keep_their_verdict():
    """`touches` is what makes the check fast; it must never skip a claim the lesson changes."""
    probes, _info = gate.regression_set()
    candidate = lesson(["protecting our directors"], ["d&o", "liability"])
    untouched = [p for p in probes if not gate.touches(candidate, p.driver)]
    sample = random.Random(7).sample(untouched, 300)
    with learned.lexicon([]):
        before = [gate._verdict(p) for p in sample]
    with learned.lexicon([candidate]):
        after = [gate._verdict(p) for p in sample]
    assert before == after


# ── teeth ──

@pytest.mark.parametrize("triggers, terms, breaks", [
    # a vague reason bound to a neighbouring cause's invoices (the Sonnet failure in the README)
    (["the second location"], ["build-out", "progress billing"], "wrong"),
    # what a careless reviewer confirmed in the teaching simulation
    (["the second location"], ["build-out"], "wrong"),
    (["the new breach policy in september"], ["policy"], "wrong"),
    (["the senior leadership hire"], ["placement fee"], "right"),
    # overbroad triggers
    (["coverage"], ["premium"], "wrong"),
    (["trip"], ["flights"], "right"),
    (["senior"], ["placement"], "right"),
    # the right cause's account, the wrong cause's words
    (["the large experiment our ml team ran"], ["ec2", "aws"], "right"),
])
def test_bad_lessons_are_refused_in_plain_words(triggers, terms, breaks):
    report = gate.impact(lesson(triggers, terms), [])
    assert not report["accepted"] and report["blocking"]
    reg = report["regression"]
    if breaks == "wrong":
        assert reg["new_unsafe_passes"] > 0
        assert "known to be wrong pass" in report["refusal"]
    else:
        assert reg["new_control_fails"] > 0
        assert "known to be right" in report["refusal"]
    assert report["refusal"].startswith("Proven will not learn this:")
    assert report["blocking"][0]["quote"] in report["refusal"]


@pytest.mark.parametrize("triggers, terms", [
    (["board coverage"], ["d&o"]),
    (["the second location"], ["lease", "austin"]),
    (["college hiring season"], ["campus"]),
    (["the cutover to the new stack"], ["migration"]),
])
def test_right_lessons_are_accepted_and_report_what_they_decide(triggers, terms):
    report = gate.impact(lesson(triggers, terms), [])
    assert report["accepted"] and report["refusal"] is None and report["tested"]
    assert report["regression"]["newly_passed_right"] > 0
    assert report["regression"]["new_unsafe_passes"] == report["regression"]["new_control_fails"] == 0


def test_a_lesson_nothing_known_exercises_is_accepted_but_marked_untested():
    report = gate.impact(lesson(["the project"], ["services"]), [])
    assert report["accepted"] and not report["tested"]
    assert report["regression"]["touched"] == 0


def test_a_right_lesson_with_one_overbroad_word_is_refused_and_the_narrow_one_is_not():
    """"liability" is in the d&o memos, but a learned term also vouches for the written word
    "liability" everywhere, which fails correct sentences about liability cover."""
    assert not gate.impact(lesson(["protecting our directors"], ["d&o", "liability"]), [])["accepted"]
    assert gate.impact(lesson(["protecting our directors"], ["d&o"]), [])["accepted"]


def test_the_lessons_already_active_are_the_baseline():
    first = lesson(["the second location"], ["lease", "austin"])
    again = gate.impact(lesson(["the second location"], ["lease", "austin", "deposit"]), [first])
    assert again["accepted"] and again["regression"]["newly_passed_right"] == 0


# ── the data directory's own cases ──

def resolve(app, action, *, learn=None, note="Recorded by the gate tests."):
    body = {"run_id": "r1", "claim_id": "C7", "quote": TRAVEL, "verdict": "REVIEW", "action": action,
            "note": note, "explanation": showcase.EXPLANATION, "scenario_id": "showcase"}
    if learn is not None:
        body["learn"] = learn
    return app.record(body)


def test_a_confirmed_defect_becomes_a_case_no_lesson_may_pass(tmp_path):
    app = App(tmp_path)
    # Without that decision the careless lesson is untested by anything known, and goes in.
    assert app.check_lesson({"triggers": ["fewer customer visits"], "terms": ["offsite"]})["accepted"]
    resolve(app, "confirm_defect", note="Customer visits did not fall; the offsite did not recur.")
    cases = gate.stored_cases(tmp_path)
    assert [(c.known, c.quote) for c in cases] == [("wrong", TRAVEL)]
    with pytest.raises(LessonBlocked, match="known to be wrong pass") as refused:
        resolve(app, "fix_evidence", learn={"triggers": ["fewer customer visits"], "terms": ["offsite"],
                                            "confirm_pass": True})
    impact = refused.value.impact
    assert impact["cases"]["new_unsafe_passes"] == 1 and impact["blocking"][0]["source"] == "case"
    assert "a sentence you confirmed as a defect" in impact["refusal"]
    assert learned.load(tmp_path) == []


def test_a_recorded_lesson_returns_the_gate_report(tmp_path):
    app = App(tmp_path)
    saved = resolve(app, "fix_evidence", learn={"triggers": ["fewer customer visits"], "terms": ["flights", "hotel"]})
    assert saved["impact"]["accepted"] and saved["impact"]["claim"] == {
        "quote": TRAVEL, "before": "REVIEW", "after": "FAIL"}


def test_check_lesson_reports_the_claim_and_stores_nothing(tmp_path):
    app = App(tmp_path)
    report = app.check_lesson({"triggers": ["fewer customer visits"], "terms": ["offsite"],
                               "explanation": showcase.EXPLANATION, "quote": TRAVEL, "scenario_id": "showcase"})
    assert report["claim"] == {"quote": TRAVEL, "before": "REVIEW", "after": "PASS"}
    assert learned.load(tmp_path) == [] and not (tmp_path / "resolutions.jsonl").exists()
