"""The demo is pinned: what the walkthrough says must be what the code does."""
from proven.report import run
from proven.showcase import EXPECTED, EXPLANATION, ledger


def test_every_showcase_sentence_gets_its_intended_verdict():
    report = run(EXPLANATION, ledger())
    claims = report["claims"]
    assert len(claims) == len(EXPECTED)
    for (prefix, verdict, codes), claim in zip(EXPECTED, claims):
        assert claim["claim"]["quote"].startswith(prefix)
        assert claim["verdict"] == verdict, (prefix, claim["reason"])
        assert [f["code"] for f in claim["findings"]] == list(codes), prefix


def test_showcase_coverage_and_the_unextracted_sentence():
    report = run(EXPLANATION, ledger())
    assert report["coverage"]["verdicts"] == {"PASS": 4, "FAIL": 3, "REVIEW": 2}
    assert report["coverage"]["decided"] == 7
    [missed] = report["unextracted"]
    assert "$1.2M" in missed["text"]


def test_the_legal_finding_names_the_misbooked_invoice():
    report = run(EXPLANATION, ledger())
    legal = report["claims"][0]
    misclass = legal["findings"][1]
    [txn_id] = misclass["evidence"]
    txn = report["transactions"][txn_id]
    assert txn["account"] == "Marketing & Advertising" and txn["amount"] == 45100
    assert "agrees with the stated $90K" in misclass["detail"]


def test_the_demo_ledger_is_pinned():
    # Any change to the demo's data changes this fingerprint; update it deliberately.
    book = ledger()
    assert len(book.transactions) == 78
    assert book.sha256() == "26ff2a271b2662436cf84463df91bcbb76049e1bfd142fdb86577950bba0ec41"
