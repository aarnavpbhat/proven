"""Three ways a correct sentence used to FAIL, found on the independent suite.

Each is a general reading rule, tested here on small ledgers of its own:

  * a figure belongs to the account its own clause names, not to the sentence's first
    account ("Paid social was up 72% ..., funded by pulling about $4K out of search");
  * a hedge may sit between a balance cue and its figure ("flat at about $9K"), and when a
    proposal and the deterministic reading put one figure in two roles, neither is checked
    and the claim cannot pass;
  * a reason that coordinates two causes, of which only one matched, cannot FAIL on the
    shortfall ("compute and warehouse usage" binding only the compute bill).
"""
from proven.claims import ClaimProposal, admit, read_sentence
from proven.ledger import Account, Ledger, Transaction
from proven.report import run


def _ledger(rows, accounts):
    txns = tuple(Transaction(f"T{i}", date, account, vendor, memo, amount)
                 for i, (date, account, vendor, memo, amount) in enumerate(rows, start=1))
    return Ledger("Test Co", "2026-09", "2026-10",
                  tuple(Account(name, tuple(aliases)) for name, aliases in accounts), txns)


ADS = _ledger([
    ("2026-09-05", "Paid Social", "SocialReach Ads", "Ad charges", 40000.00),
    ("2026-10-05", "Paid Social", "SocialReach Ads", "Ad charges", 68800.00),
    ("2026-09-07", "Paid Search", "SearchReach Ads", "Search campaigns", 18000.00),
    ("2026-10-07", "Paid Search", "SearchReach Ads", "Search campaigns", 14000.00),
], [("Paid Social", ["paid social"]), ("Paid Search", ["paid search", "search"])])

TOLLS = _ledger([
    ("2026-09-15", "Tolls", "TollLink", "Tolls 1st-15th", 4500.00),
    ("2026-09-28", "Tolls", "TollLink", "Tolls 16th-EOM", 4560.00),
    ("2026-10-15", "Tolls", "TollLink", "Tolls 1st-15th", 4600.00),
    ("2026-10-28", "Tolls", "TollLink", "Tolls 16th-EOM", 4600.00),
], [("Tolls", ["tolls"])])

HOSTING = _ledger([
    ("2026-09-03", "Hosting", "Nimbus Cloud", "Compute usage Sep", 42000.00),
    ("2026-10-03", "Hosting", "Nimbus Cloud", "Compute usage Oct", 63800.00),
    ("2026-09-04", "Hosting", "Glacier Data", "Capacity credits Sep", 10100.00),
    ("2026-10-04", "Hosting", "Glacier Data", "Capacity credits Oct", 19400.00),
], [("Hosting", ["hosting"])])


def _verdict(text, ledger, extractor=None):
    report = run(text, ledger, extractor=extractor)
    assert len(report["claims"]) == 1, report["claims"]
    return report["claims"][0]


class _One:
    name, version = "fixture", "0"

    def __init__(self, proposal):
        self.proposal = proposal

    def propose(self, text, ledger):
        return [self.proposal]


# ── a figure belongs to the account its clause names ─────────────────────

SOCIAL = "Paid social was up 72%, funded in part by pulling about $4K out of search."


def test_figure_in_another_accounts_clause_is_not_this_accounts_change():
    reading = read_sentence(SOCIAL, ADS)
    assert reading.account == "Paid Social"
    assert reading.change is None
    assert reading.percent is not None and reading.percent.text == "72%"


def test_two_account_sentence_goes_to_review_not_fail():
    result = _verdict(SOCIAL, ADS)
    assert result["verdict"] == "REVIEW"


def test_a_proposal_cannot_put_another_accounts_figure_on_this_claim():
    proposal = ClaimProposal(quote=SOCIAL, account="Paid Social", change_text="$4K",
                             percent_text="72%", extractor="fixture")
    claim = admit(proposal, SOCIAL, ADS, "C1", set())
    assert claim.change is None
    assert any("its clause names another account" in n for n in claim.notes)


def test_the_claims_own_figure_still_fails_when_wrong():
    text = "Paid social was up $9K, while search fell $4K."
    result = _verdict(text, ADS)
    assert result["verdict"] == "FAIL"        # +$28,800, not $9K
    assert result["claim"]["stated"]["change"]["text"] == "$9K"


# ── hedged balances, and one figure in two roles ─────────────────────────

FLAT = "Tolls were flat at about $9K."


def test_hedge_between_cue_and_figure_is_still_a_balance():
    reading = read_sentence(FLAT, TOLLS)
    assert reading.change is None
    assert reading.current is not None and reading.current.text == "$9K"
    assert read_sentence("Tolls fell from roughly $9K.", TOLLS).prior.text == "$9K"


def test_flat_at_about_is_not_a_failed_change():
    assert _verdict(FLAT, TOLLS)["verdict"] == "REVIEW"


def test_a_balance_with_a_hedge_that_is_wrong_still_fails():
    assert _verdict("Tolls rose to about $12K.", TOLLS)["verdict"] == "FAIL"


def test_one_figure_in_two_roles_is_checked_in_neither_and_cannot_pass():
    text = "Tolls rose $9.2K."
    proposal = ClaimProposal(quote=text, account="Tolls", current_text="$9.2K", extractor="fixture")
    claim = admit(proposal, text, TOLLS, "C1", set())
    assert claim.change is None and claim.current is None
    assert claim.figure_conflicts
    result = _verdict(text, TOLLS, _One(proposal))
    assert result["verdict"] == "REVIEW"      # never PASS on the proposal's relabelling


# ── a coordinated cause, only half of it found ───────────────────────────

SPLIT = "Hosting rose $31K due to higher compute and warehouse usage."


def test_one_of_two_coordinated_causes_unmatched_is_review_not_fail():
    result = _verdict(SPLIT, HOSTING)
    assert result["verdict"] == "REVIEW"
    assert [f["code"] for f in result["findings"]] == ["WEAK_REASON_MATCH"]


def test_a_single_cause_that_explains_too_little_still_fails():
    result = _verdict("Hosting rose $31K due to higher compute usage.", HOSTING)
    assert result["verdict"] == "FAIL"
    assert "PARTIAL_EXPLANATION" in [f["code"] for f in result["findings"]]


def test_both_coordinated_causes_found_but_short_still_fails():
    ledger = _ledger([
        ("2026-09-03", "Hosting", "Nimbus Cloud", "Compute usage Sep", 42000.00),
        ("2026-10-03", "Hosting", "Nimbus Cloud", "Compute usage Oct", 48000.00),
        ("2026-09-04", "Hosting", "Glacier Data", "Warehouse credits Sep", 10000.00),
        ("2026-10-04", "Hosting", "Glacier Data", "Warehouse credits Oct", 11000.00),
        ("2026-10-09", "Hosting", "Edge CDN", "Annual prepay", 24000.00),
    ], [("Hosting", ["hosting"])])
    result = _verdict(SPLIT, ledger)
    assert result["verdict"] == "FAIL"
