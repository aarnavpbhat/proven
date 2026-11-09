"""Benchmark floors. These are regression tests, not evidence: the generator, the lexicon
and the checker share an author, and the README says so beside every number."""
import pytest

from proven.evaluate import evaluate, reward
from proven.synth import Label


@pytest.fixture(scope="module")
def seen():
    return evaluate("test", 220)


@pytest.fixture(scope="module")
def heldout():
    return evaluate("test", 220, phrasing="heldout")


@pytest.fixture(scope="module")
def paraphrase():
    return evaluate("test", 220, phrasing="paraphrase")


def test_paraphrase_tier_is_safe_and_as_hard_as_heldout(paraphrase):
    assert paraphrase["controls"]["fails"] == 0
    assert paraphrase["defects"]["unsafe_passes"] == 0
    assert paraphrase["coverage"]["decided_share"] < 0.3


def test_no_control_ever_fails(seen, heldout):
    # Aptio's kill criterion K3, applied under both phrasings.
    assert seen["controls"]["fails"] == 0
    assert heldout["controls"]["fails"] == 0


def test_no_defect_is_ever_passed(seen, heldout):
    # K2: the number no amount of coverage compensates for.
    assert seen["defects"]["unsafe_passes"] == 0
    assert heldout["defects"]["unsafe_passes"] == 0
    assert seen["defects"]["missed"] == 0


def test_every_family_meets_its_floor_on_seen_phrasing(seen):
    for row in seen["families"]:
        assert row["met_rate"] >= 0.9, row
        if row["evidence_recall"] is not None:
            assert row["evidence_recall"] >= 0.95, row


def test_coverage_is_reported_separately_and_collapses_on_unseen_phrasing(seen, heldout):
    assert seen["coverage"]["decided_share"] >= 0.85
    # The measured weakness of a lexical binder, kept as a test so that an
    # improvement shows up as a diff rather than as an unannounced number.
    assert heldout["coverage"]["decided_share"] < 0.3


def label(requirement: str, culprits=("T1",)) -> Label:
    return Label("q", "f", "defect" if requirement != "PASS" else "control", requirement, [],
                 list(culprits) if requirement != "PASS" else [], "A")


def test_reward_is_asymmetric():
    assert reward("PASS", set(), label("FAIL")) == -1.0           # unsafe pass
    assert reward("FAIL", set(), label("PASS")) == -0.5           # false alarm that fails
    assert reward("REVIEW", set(), label("PASS")) == 0.0
    assert reward("FAIL", {"T1"}, label("FAIL")) == 1.0           # right verdict, right evidence
    assert reward("FAIL", {"T9"}, label("FAIL")) == 0.5           # right verdict, wrong evidence
    assert reward("REVIEW", {"T1"}, label("FAIL")) == 0.25        # flagged, not decided
