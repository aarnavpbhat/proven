"""The hand-written Tidewater close: the files parse, and no sentence the key marks defective is
passed. This deliberately does NOT pin the other verdicts: the key was written before Proven ran,
and Proven disagrees with it on coverage (see the report in the commit message), which is
information, not something to tune away."""
import csv
import io

from proven.examples import HERE, load
from proven.report import run

REQUIREMENTS = {"PASS", "FAIL", "NOT_PASS", "NO_CLAIM"}


def test_ledger_parses_and_is_the_right_size():
    close = load()
    assert 60 <= len(close.ledger.transactions) <= 120
    assert (close.ledger.prior_period, close.ledger.current_period) == ("2026-09", "2026-10")
    header = next(csv.reader(io.StringIO((HERE / "tidewater_ledger.csv").read_text())))
    assert header == ["id", "date", "account", "vendor", "memo", "amount"]
    ids = [t.id for t in close.ledger.transactions]
    assert len(ids) == len(set(ids))
    assert any(t.amount < 0 for t in close.ledger.transactions)            # credit note / reversal


def test_key_matches_the_commentary_and_the_ledger():
    close = load()
    assert 8 <= len(close.commentary.splitlines()) <= 12
    for item in close.key:
        assert item.quote in close.commentary, item.quote
        assert item.requirement in REQUIREMENTS and item.why
        assert item.defective == (item.requirement in ("FAIL", "NOT_PASS"))
        for txn in item.culprits:
            assert close.ledger.txn(txn), txn
    assert {i.requirement for i in close.key} >= {"PASS", "FAIL", "NOT_PASS"}


def test_no_sentence_the_key_marks_defective_gets_pass():
    close = load()
    report = run(close.commentary, close.ledger)
    verdicts = {c["claim"]["quote"]: c["verdict"] for c in report["claims"]}
    for item in close.key:
        if item.defective and item.quote in verdicts:
            assert verdicts[item.quote] != "PASS", (item.quote, item.why)
        if item.requirement == "FAIL":
            assert item.quote in verdicts, f"defect not extracted: {item.quote}"
