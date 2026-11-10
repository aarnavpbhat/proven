"""The independent suite: its key is sound, and the failures it found stay visible.

The first group checks the test set itself (offline, no checker involved in the labels):
the key loads, every quote is verbatim, every cited transaction exists, and the key's
arithmetic holds against the ledger CSVs (`benchmarks/independent/check_key.py`).

The second group pins what the checker does on the suite, and keeps each mechanism the
suite exposed as a regression test: the 12 unsafe PASSes of the unguarded rules (fixed by
the unread-content guard, f597068) and the 3 control FAILs (fixed after the suite was
seen, so these numbers are no longer blind). See docs/independent.md for the write-ups.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from proven import independent
from proven.claims import ClaimProposal
from proven.report import run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def closes():
    return independent.load()


@pytest.fixture(scope="module")
def rules_result():
    return independent.benchmark()


def _close(closes, slug):
    return next(c for c in closes if c.slug == slug)


def _keyed(closes, claim_id):
    for close in closes:
        for k in close.claims:
            if k.id == claim_id:
                return close, k
    raise KeyError(claim_id)


# ── the test set itself ──────────────────────────────────────────────────

def test_suite_shape(closes):
    assert len(closes) == 8
    claims = [k for c in closes for k in c.claims]
    assert len(claims) == 87
    assert sum(k.correct for k in claims) == 57
    assert {k.defect for k in claims if not k.correct} == {
        "wrong_amount", "wrong_direction", "wrong_account", "wrong_cause", "cause_too_small",
        "cause_in_other_period", "contradicted_by_credit", "fabricated_cause"}
    assert len({k.id for k in claims}) == len(claims)
    for close in closes:
        periods = {t.period for t in close.ledger.transactions}
        for period in (close.ledger.prior_period, close.ledger.current_period):
            count = sum(t.period == period for t in close.ledger.transactions)
            assert 80 <= count <= 250, (close.slug, period, count)
        assert len(periods) == 3


def test_quotes_are_verbatim(closes):
    for close in closes:
        for k in close.claims:
            assert k.quote in close.commentary, k.id
        for item in close.non_claims:
            assert item["quote"] in close.commentary, item["quote"]


def test_cited_transactions_exist(closes):
    for close in closes:
        ids = {t.id for t in close.ledger.transactions}
        for k in close.claims:
            cited = set(k.evidence) | set(k.raw["cause_txns"]) | set(k.raw.get("driver_txns", []))
            assert cited <= ids, (k.id, cited - ids)


def test_verdicts_follow_from_truth(closes):
    for close in closes:
        for k in close.claims:
            if k.correct:
                assert (k.ideal, k.acceptable) == ("PASS", ("PASS", "REVIEW")), k.id
            else:
                assert (k.ideal, k.acceptable) == ("FAIL", ("FAIL", "REVIEW")), k.id


def test_key_arithmetic_holds():
    sys.path.insert(0, str(ROOT / "benchmarks" / "independent"))
    try:
        import check_key
    finally:
        sys.path.pop(0)
    errors = [e for slug in independent.load() for e in check_key.check_company(slug.slug)]
    assert errors == []


def test_ledger_loader_matches_the_csv(closes):
    close = _close(closes, "keystone")
    assert close.ledger.variance("Subcontractors").change == pytest.approx(-29550.00)
    assert close.ledger.variance("Job Materials").change == pytest.approx(54311.35)


def test_cli_runs_the_suite(tmp_path, capsys):
    from proven.__main__ import main
    out = tmp_path / "rules.json"
    assert main(["benchmark", "--suite", "independent", "--json", str(out)]) == 0
    assert "suite=independent" in capsys.readouterr().out
    assert out.is_file()


# ── what the checker does on it (after fixes, no longer blind) ─────────────

def test_rules_result_as_measured(rules_result):
    """Pinned so that any change to these numbers is noticed and written up."""
    s = rules_result["summary"]
    assert s["claims"] == 87
    assert s["controls"]["passed"] == 0
    assert s["controls"]["fails"] == 0
    assert s["defects"]["caught"] == 13
    assert s["defects"]["unsafe_passes"] == 0
    assert s["not_extracted"] == 5
    assert s["controls"]["review_primary"] == {
        "UNREAD:no_reason": 41, "WEAK_REASON_MATCH": 4, "UNREAD:unchecked_figure": 4,
        "REASON_NOT_FOUND": 2, "UNREAD:unread_words": 1}


def test_no_unsafe_pass_with_rules(rules_result):
    assert rules_result["summary"]["defects"]["unsafe_passes"] == 0


def test_no_control_fail_with_rules(rules_result):
    assert rules_result["summary"]["controls"]["fails"] == 0


def _verdict(close, quote, extractor=None):
    report = run(close.commentary, close.ledger, extractor=extractor)
    assigned, _ = independent.match(close, report)
    k = next(k for k in close.claims if k.quote == quote)
    return assigned[k.id]["verdict"] if assigned[k.id] else "MISSED"


@pytest.mark.parametrize("claim_id", ["KMC-09", "KMC-11", "ER-11", "RB-07", "RB-10", "HPC-08",
                                      "KMC-03", "LL-04", "HPC-07", "NSF-10", "BRT-11"])
def test_unread_reason_does_not_pass(closes, claim_id):
    """A reason introduced by ', the', 'for', 'as', 'on our' or ', mostly' was not read, and
    the claim used to pass on its figures alone."""
    close, k = _keyed(closes, claim_id)
    assert _verdict(close, k.quote) != "PASS"


def test_unread_direction_does_not_pass(closes):
    """'ticked up' is not a direction word; the change was compared by magnitude only."""
    close, k = _keyed(closes, "BRT-06")
    assert _verdict(close, k.quote) != "PASS"


def test_flat_at_about_is_a_balance(closes):
    """'flat at about $9K': the hedge used to stop it being read as a balance."""
    close, k = _keyed(closes, "NSF-11")
    assert _verdict(close, k.quote) != "FAIL"


def test_second_accounts_figure_is_not_the_firsts(closes):
    """Two claims in one sentence: search's $4K used to be checked as paid social's change."""
    close, k = _keyed(closes, "LL-02")
    assert _verdict(close, k.quote) != "FAIL"


class _OneProposal:
    """A stand-in for a model proposal on one sentence, as Sonnet made it (offline)."""

    name, version = "fixture", "0"

    def __init__(self, proposal: ClaimProposal):
        self.proposal = proposal

    def propose(self, text, ledger):
        return [self.proposal]


def test_split_vendor_cause_does_not_fail(closes):
    """'compute and warehouse usage': the lexicon-vouched 'compute' bound one bill, the
    warehouse bill matched nothing, and the 70% share used to FAIL a correct sentence."""
    close, k = _keyed(closes, "BRT-02")
    proposal = ClaimProposal(
        quote=k.quote, account="Hosting & Infrastructure", change_text="$31k", percent_text="50%",
        driver_text="onboarding the Meridian Health account drove both compute and warehouse usage",
        driver_terms=("meridian health", "backfill"), extractor="fixture")
    assert _verdict(close, k.quote, _OneProposal(proposal)) == "REVIEW"


def test_balance_proposal_is_not_also_a_change(closes):
    """A proposal reads '$9K' as the balance; admit() used to keep the rules' reading of the
    same figure as the change too, which then FAILed."""
    close, k = _keyed(closes, "NSF-11")
    proposal = ClaimProposal(quote=k.quote, account="Tolls & Permits", current_text="$9K",
                             extractor="fixture")
    assert _verdict(close, k.quote, _OneProposal(proposal)) != "FAIL"
