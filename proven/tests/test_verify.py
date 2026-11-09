"""Each check, with its negative controls. A control that must *not* produce a finding
is as important as a positive case, and is usually the one that catches a real problem."""
from proven.claims import ClaimProposal, admit
from proven.ledger import Account, Ledger, Transaction
from proven.report import run
from proven.verify import Policy, Verdict, verify_claim

LEGAL, MKT = "Legal & Professional Fees", "Marketing & Advertising"
CHART = (Account(LEGAL, ("legal", "legal costs")), Account(MKT, ("marketing", "marketing spend")))


def ledger(*extra: Transaction) -> Ledger:
    base = []
    for month in ("08", "09", "10"):
        base.append(Transaction(f"R{month}", f"2026-{month}-03", LEGAL, "Harbor & Vale LLP",
                                "General corporate retainer", 6000))
        base.append(Transaction(f"M{month}", f"2026-{month}-04", MKT, "Google Ads",
                                "Search ads", 9000))
    return Ledger("Co", "2026-09", "2026-10", CHART, tuple(base) + extra)


def series_b(amount: float, txn_id: str = "S1", account: str = LEGAL, day: str = "17",
             memo: str = "Series B financing — closing documents") -> Transaction:
    return Transaction(txn_id, f"2026-10-{day}", account, "Harbor & Vale LLP", memo, amount)


def check(text: str, book: Ledger, **proposal):
    return run(text, book)["claims"][0]


def codes(result) -> list[str]:
    return [f["code"] for f in result["findings"]]


# ── amount and direction ────────────────────────────────────────────────

def test_correct_rounded_explanation_passes():
    result = check("Legal costs rose $90K because of our funding round.", ledger(series_b(91_240)))
    assert result["verdict"] == "PASS", result["reason"]
    assert codes(result) == []


def test_wrong_amount_fails_and_cites_the_moving_transactions():
    result = check("Legal costs rose $150K because of our funding round.", ledger(series_b(91_240)))
    assert result["verdict"] == "FAIL" and codes(result) == ["WRONG_AMOUNT"]
    assert "S1" in result["findings"][0]["evidence"]


def test_near_miss_goes_to_review_not_fail():
    result = check("Legal costs rose $100K because of our funding round.", ledger(series_b(91_240)))
    assert result["verdict"] == "REVIEW" and codes(result) == ["WRONG_AMOUNT_NEAR"]


def test_wrong_direction_fails():
    result = check("Legal costs fell $91K because of our funding round.", ledger(series_b(91_240)))
    assert result["verdict"] == "FAIL" and "WRONG_DIRECTION" in codes(result)


def test_an_unsigned_decrease_is_not_a_contradiction():
    # The fourth false-positive class: magnitudes are quoted unsigned.
    book = ledger(Transaction("P1", "2026-09-10", LEGAL, "Meridian Legal Group",
                              "Patent dispute — settlement payment", 40_000))
    result = check("Legal costs fell $40K, reflecting the patent dispute settlement in September.", book)
    assert result["verdict"] == "PASS", result["reason"]


def test_percent_and_balance_are_checked():
    book = ledger(series_b(12_000))
    good = check("Legal costs rose 200% to $18K, due to the fundraise.", book)
    assert good["verdict"] == "PASS", good["reason"]
    bad = check("Legal costs rose 50% to $18K, due to the fundraise.", book)
    assert bad["verdict"] == "FAIL" and codes(bad) == ["WRONG_PERCENT"]


# ── attribution ──────────────────────────────────────────────────────────

def test_wrong_cause_fails_when_the_cited_cause_did_not_move():
    book = ledger(series_b(80_000),
                  Transaction("D9", "2026-09-12", LEGAL, "Meridian Legal Group", "Patent dispute — monthly", 5000),
                  Transaction("D10", "2026-10-12", LEGAL, "Meridian Legal Group", "Patent dispute — monthly", 5000))
    result = check("Legal costs rose $80K because of the patent litigation.", book)
    assert result["verdict"] == "FAIL" and codes(result) == ["WRONG_CAUSE"]
    assert "S1" in result["findings"][0]["evidence"]       # the real cause is cited


def test_partial_explanation_fails_unless_the_wording_is_hedged():
    book = ledger(series_b(50_000),
                  Transaction("L1", "2026-10-20", LEGAL, "Meridian Legal Group",
                              "Patent dispute — settlement payment", 40_000))
    unhedged = check("Legal costs rose $90K because of our funding round.", book)
    assert unhedged["verdict"] == "FAIL" and codes(unhedged) == ["PARTIAL_EXPLANATION"]
    assert unhedged["findings"][0]["evidence"] == ["L1"]
    hedged = check("Legal costs rose $90K, primarily due to our funding round.", book)
    assert hedged["verdict"] == "PASS", hedged["reason"]
    partly = check("Legal costs rose $90K, partly due to the patent dispute.", book)
    assert partly["verdict"] == "PASS", partly["reason"]


def test_a_cause_absent_from_the_ledger_is_review_never_fail():
    result = check("Legal costs rose $91K because of the trademark filings.", ledger(series_b(91_240)))
    assert result["verdict"] == "REVIEW" and codes(result) == ["REASON_NOT_FOUND"]
    assert "S1" in result["findings"][0]["evidence"]


def test_a_reason_matched_by_one_generic_word_is_review():
    # The mechanism behind every unsafe PASS measured on held-out phrasing.
    book = ledger(Transaction("D1", "2026-10-05", LEGAL, "Atlas Mutual", "D&O policy — annual premium", 30_000))
    result = check("Legal costs rose $30K because of the new breach policy.", book)
    assert result["verdict"] == "REVIEW" and codes(result) == ["WEAK_REASON_MATCH"]


def test_an_immaterial_movement_is_not_attributed():
    book = ledger(Transaction("X1", "2026-10-09", LEGAL, "Harbor & Vale LLP", "Copies", 400))
    result = check("Legal costs rose $400 because of printing.", book)
    attribution = next(c for c in result["checks"] if c["name"] == "attribution")
    assert not attribution["ran"] and result["verdict"] == "PASS"


# ── classification ───────────────────────────────────────────────────────

def test_misbooked_expense_is_flagged_and_reclassification_reconciles():
    book = ledger(series_b(45_000), series_b(45_000, "S2", MKT, "21", "Series B — investor rights"))
    result = check("Legal costs rose $90K because of our funding round.", book)
    assert result["verdict"] == "FAIL"
    assert codes(result) == ["WRONG_AMOUNT", "POSSIBLE_MISCLASSIFICATION"]
    finding = result["findings"][1]
    assert finding["evidence"] == ["S2"] and "agrees with the stated $90K" in finding["detail"]
    overlooked = check("Legal costs rose $45K because of our funding round.", book)
    assert overlooked["verdict"] == "REVIEW" and codes(overlooked) == ["POSSIBLE_MISCLASSIFICATION"]


def test_the_misbooked_expense_is_also_flagged_from_the_receiving_account():
    book = ledger(series_b(45_000), series_b(45_000, "S2", MKT, "21", "Series B — investor rights"))
    result = check("Marketing spend rose $45K because of the Series B announcement.", book)
    assert "POSSIBLE_MISCLASSIFICATION" in codes(result)


def test_a_cause_legitimately_touching_another_account_is_not_a_misclassification():
    # Negative control: the vendor's usual account is the one it is booked to.
    book = ledger(series_b(90_000),
                  Transaction("G1", "2026-10-22", MKT, "Google Ads", "Series B announcement ads", 3000))
    result = check("Legal costs rose $90K because of our funding round.", book)
    assert result["verdict"] == "PASS", result["reason"]


# ── the algebra and the guards ───────────────────────────────────────────

def test_no_account_means_review():
    result = check("Lab equipment rose $15K for the test rig.", ledger())
    assert result["verdict"] == "REVIEW" and codes(result) == ["ACCOUNT_NOT_FOUND"]


def test_pass_requires_a_check_that_ran():
    book = ledger(series_b(90_000))
    claim = admit(ClaimProposal(quote="Legal costs, because of the fundraise.",
                                driver_text="the fundraise"),
                  "Legal costs, because of the fundraise.", book, "C1", set())
    claim = claim.__class__(**{**claim.__dict__, "terms": ()})
    result = verify_claim(claim, book)
    assert result.verdict is Verdict.REVIEW


def test_support_resting_only_on_model_terms_is_review():
    book = ledger(Transaction("Z1", "2026-10-09", LEGAL, "Harbor & Vale LLP", "Closing binders", 90_000))
    text = "Legal costs rose $90K because of our funding round."
    claim = admit(ClaimProposal(quote=text, change_text="$90K", driver_text="our funding round",
                                driver_terms=("closing binders",), extractor="model"),
                  text, book, "C1", set())
    result = verify_claim(claim, book)
    assert result.verdict is Verdict.REVIEW
    assert [f.code for f in result.findings] == ["SUPPORT_RESTS_ON_MODEL_TERMS"]


def test_a_model_mapped_account_cannot_be_decided():
    book = ledger(series_b(90_000))
    text = "Lawyer bills rose $90K because of our funding round."
    claim = admit(ClaimProposal(quote=text, account=LEGAL, change_text="$90K",
                                driver_text="our funding round", extractor="model"),
                  text, book, "C1", set())
    result = verify_claim(claim, book)
    assert result.computed_verdict is Verdict.PASS and result.verdict is Verdict.REVIEW
    assert result.adjustments


def test_policy_is_applied_and_reported():
    book = ledger(series_b(91_240))
    strict = Policy(amount_rel_tolerance=0.0, amount_review_band=0.0)
    text = "Legal costs rose $85K because of our funding round."
    report = run(text, book, policy=strict)
    assert report["claims"][0]["verdict"] == "FAIL"
    assert report["run"]["policy"]["amount_rel_tolerance"] == 0.0


# ── model terms: never a FAIL; a PASS only when the policy allows and they are specific ──

def _travel(terms, policy=None):
    from proven import showcase
    from proven.extract import RuleExtractor

    class WithTerms:
        name, version = "fake", "0"

        def propose(self, text, book):
            return [ClaimProposal(**{**p.__dict__, "driver_terms": terms, "extractor": "model"})
                    if p.quote.startswith("Travel") else p
                    for p in RuleExtractor().propose(text, book)]

    report = run(showcase.EXPLANATION, showcase.ledger(), extractor=WithTerms(), policy=policy)
    return next(c for c in report["claims"] if c["claim"]["quote"].startswith("Travel"))


def test_model_terms_alone_never_fail_a_claim():
    # "flights" and "hotel" match recurring travel that did not move; before the guard
    # this was a confirmed WRONG_CAUSE decided by the model's vocabulary alone.
    for policy in (Policy(), Policy(model_terms_anchor=True)):
        claim = _travel(("flights", "hotel"), policy)
        assert claim["verdict"] == "REVIEW"
        assert [f["code"] for f in claim["findings"]] == ["REASON_FOUND_ONLY_BY_MODEL_TERMS"]


def test_specific_model_terms_pass_only_when_the_policy_allows():
    # The sentence says "fewer customer visits"; the ledger shows a company offsite. A model
    # that proposed "offsite" would be wrong about the cause, and the default keeps a person
    # in the loop. With the flag on, the term is specific and the movement is explained.
    assert _travel(("offsite",))["verdict"] == "REVIEW"
    allowed = _travel(("offsite",), Policy(model_terms_anchor=True))
    assert allowed["verdict"] == "PASS"
    assert allowed["reconstruction"]["driver"]["anchored_by_model_terms"] == ["offsite"]


def test_a_generic_model_term_is_not_specific():
    # "travel" is the account's own name; it must not anchor anything.
    claim = _travel(("travel", "entertainment"), Policy(model_terms_anchor=True))
    assert claim["verdict"] == "REVIEW"
