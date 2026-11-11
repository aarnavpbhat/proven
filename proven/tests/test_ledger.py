import pytest

from proven.ledger import TOTAL, Account, Ledger, Transaction, Variance, default_aliases


def small() -> Ledger:
    accounts = (Account("Legal", ("legal",)), Account("Marketing", ("marketing",)))
    rows = (
        Transaction("T1", "2026-08-03", "Legal", "Firm A", "Retainer", 1000),
        Transaction("T2", "2026-09-03", "Legal", "Firm A", "Retainer", 1000),
        Transaction("T3", "2026-10-03", "Legal", "Firm A", "Retainer", 1000),
        Transaction("T4", "2026-10-09", "Legal", "Firm A", "Series B", 5000),
        Transaction("T5", "2026-10-10", "Marketing", "Firm A", "Series B misc", 2000),
        Transaction("T6", "2026-09-12", "Marketing", "Ads Co", "Ads", 300),
    )
    return Ledger("Co", "2026-09", "2026-10", accounts, rows)


def test_variance_uses_only_the_two_periods():
    ledger = small()
    var = ledger.variance("Legal")
    assert (var.prior, var.current, var.change) == (1000, 6000, 5000)
    assert var.change_pct == pytest.approx(500.0)
    assert ledger.variance(TOTAL).change == pytest.approx(5000 + 2000 - 300)


def test_contributions_are_by_vendor_largest_first():
    [first, *_] = small().contributions("Legal")
    assert first.vendor == "Firm A" and first.change == 5000


def test_vendor_home_excludes_the_transaction_under_suspicion():
    home = small().vendor_home("Firm A", "T5", min_count=3, min_share=0.8)
    assert home is not None and home.account == "Legal" and home.total == 4


def test_a_vendor_with_too_little_history_has_no_home():
    assert small().vendor_home("Ads Co", "none", min_count=3, min_share=0.8) is None


def test_unknown_accounts_and_duplicate_ids_are_refused():
    with pytest.raises(ValueError, match="chart of accounts"):
        Ledger("Co", "2026-09", "2026-10", (Account("Legal"),),
               (Transaction("T1", "2026-09-01", "Nope", "V", "", 1),))
    with pytest.raises(ValueError, match="duplicate"):
        Ledger("Co", "2026-09", "2026-10", (Account("Legal"),),
               (Transaction("T1", "2026-09-01", "Legal", "V", "", 1),) * 2)


def test_csv_round_trip_and_parentheses():
    ledger = small()
    again = Ledger.from_csv(ledger.to_csv())
    assert again.variance("Legal").change == ledger.variance("Legal").change
    text = "id,date,account,vendor,memo,amount\nA,2026-09-01,Legal,V,x,100\nB,2026-10-01,Legal,V,refund,(40)\n"
    parsed = Ledger.from_csv(text)
    assert parsed.variance("Legal").current == -40
    assert (parsed.prior_period, parsed.current_period) == ("2026-09", "2026-10")


def test_csv_without_required_columns_is_refused():
    with pytest.raises(ValueError, match="missing"):
        Ledger.from_csv("id,date,amount\n1,2026-09-01,4\n")


def test_hash_changes_with_content():
    a = small()
    rows = a.transactions[:-1] + (Transaction("T6", "2026-09-12", "Marketing", "Ads Co", "Ads", 301),)
    b = Ledger("Co", "2026-09", "2026-10", a.accounts, rows)
    assert a.sha256() != b.sha256()


def test_default_aliases_are_mechanical():
    aliases = default_aliases("Legal & Professional Fees")
    assert "legal" in aliases and "professional" in aliases and "legal & professional fees" in aliases


def test_a_new_account_has_no_percentage_change():
    # Nothing to divide by: the honest answer is "no percentage", never 0% or infinity.
    variance = Variance(prior=0, current=500)
    assert variance.change == 500 and variance.change_pct is None
