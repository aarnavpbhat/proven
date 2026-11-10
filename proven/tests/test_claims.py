"""The extraction boundary: what an extractor may and may not get past `admit()`."""
import pytest

from proven.claims import (ClaimProposal, Rejection, Strength, admit, anchored_terms,
                           read_sentence, split_reason, term_pattern)
from proven.extract import RuleExtractor, sentences
from proven.ledger import TOTAL
from proven.showcase import ledger as showcase_ledger

LEDGER = showcase_ledger()
TEXT = "Legal costs rose $90K because of our Series B funding round."


@pytest.mark.parametrize("sentence, strength, driver", [
    ("Legal rose $90K because of our funding round.", Strength.FULL, "our funding round"),
    ("Legal rose $90K, primarily due to the fundraise.", Strength.MAJORITY, "the fundraise"),
    ("Legal rose $90K, due mainly to the fundraise.", Strength.MAJORITY, "the fundraise"),
    ("Legal rose $90K, partly driven by the fundraise.", Strength.PARTIAL, "the fundraise"),
    ("Legal rose $90K, due in part to the fundraise; other items offset.", Strength.PARTIAL, "the fundraise"),
    ("Cloud rose 12% on higher AWS usage.", Strength.FULL, "higher AWS usage"),
    ("Legal rose $90K.", Strength.FULL, None),
])
def test_reason_and_strength_are_read_from_the_words(sentence, strength, driver):
    _head, found, read = split_reason(sentence)
    assert (found, read) == (driver, strength)


def test_direction_comes_from_the_head_not_the_reason():
    # "higher" inside the reason must not decide the direction of the account.
    reading = read_sentence("Travel fell $12K despite higher airfares due to fewer trips.", LEDGER)
    assert reading.direction == -1


def test_figure_roles():
    reading = read_sentence("Cloud hosting grew approximately 16% to $94.5K, due to usage.", LEDGER)
    assert reading.percent.text == "16%" and reading.current.text == "$94.5K"
    assert reading.change is None
    reading = read_sentence("Legal costs rose from $30K to $120K, due to the fundraise.", LEDGER)
    assert (reading.prior.value, reading.current.value) == (30_000, 120_000)
    reading = read_sentence("The $45K increase in recruiting fees was due to the search.", LEDGER)
    assert reading.change.value == 45_000 and reading.direction == 1


def test_account_resolution_prefers_the_longest_alias_and_knows_the_total():
    assert read_sentence(TEXT, LEDGER).account == "Legal & Professional Fees"
    assert read_sentence("Total operating expenses rose $1K.", LEDGER).account == TOTAL
    assert read_sentence("Lab equipment rose $1K.", LEDGER).account is None


def test_terms_carry_their_origin_and_drop_generic_words():
    terms = anchored_terms("our Series B funding round", "Legal & Professional Fees", LEDGER)
    by_text = {t.text: t.origin for t in terms}
    assert by_text["funding"] == "quote" and by_text["series b"] == "lexicon"
    assert "our" not in by_text
    # The account's own name is not evidence of a cause.
    terms = anchored_terms("higher legal work", "Legal & Professional Fees", LEDGER)
    assert terms == []


def test_term_matching_is_word_bounded():
    assert term_pattern("renewals").search("annual renewal — 2027")
    assert not term_pattern("app").search("apple store")
    assert not term_pattern("summit").search("devsummit 2026")
    assert term_pattern("d&o").search("d&o policy — annual premium")


def test_a_quote_that_is_not_in_the_text_is_rejected():
    proposal = ClaimProposal(quote="Legal costs rose $95K because of litigation.", extractor="model")
    result = admit(proposal, TEXT, LEDGER, "C1", set())
    assert isinstance(result, Rejection) and result.reason == "quote_not_in_text"


def test_a_figure_that_is_not_in_the_quote_is_rejected():
    proposal = ClaimProposal(quote=TEXT, change_text="$95K", extractor="model")
    result = admit(proposal, TEXT, LEDGER, "C1", set())
    assert isinstance(result, Rejection) and result.reason == "figure_not_in_quote"


def test_direction_and_strength_are_reread_not_trusted():
    proposal = ClaimProposal(quote=TEXT, change_text="$90K", direction="down",
                             driver_text="our Series B funding round", extractor="model")
    claim = admit(proposal, TEXT, LEDGER, "C1", set())
    assert claim.direction == 1 and claim.strength is Strength.FULL


def test_a_hallucinated_reason_is_dropped_and_model_terms_are_marked():
    proposal = ClaimProposal(quote=TEXT, change_text="$90K", driver_text="the lawsuit",
                             extractor="model")
    claim = admit(proposal, TEXT, LEDGER, "C1", set())
    assert any("not a span" in n for n in claim.notes)
    assert claim.driver == "our Series B funding round"      # the reason the sentence does state
    proposal = ClaimProposal(quote=TEXT, change_text="$90K", driver_text="our Series B funding round",
                             driver_terms=("closing documents",), extractor="model")
    claim = admit(proposal, TEXT, LEDGER, "C1", set())
    assert {"text": "closing documents", "origin": "model"} in [t.to_dict() for t in claim.terms]


def test_a_proposal_cannot_remove_the_reason_or_figure_the_sentence_states():
    """A model that leaves the reason out would otherwise get the claim checked on its amount alone."""
    claim = admit(ClaimProposal(quote=TEXT, extractor="model"), TEXT, LEDGER, "C1", set())
    assert claim.driver == "our Series B funding round"
    assert claim.change is not None and claim.change.text == "$90K"
    assert any("left out" in n for n in claim.notes)


def test_an_alias_in_the_sentence_overrides_a_model_mapping():
    proposal = ClaimProposal(quote=TEXT, account="Marketing & Advertising", change_text="$90K",
                             extractor="model")
    claim = admit(proposal, TEXT, LEDGER, "C1", set())
    assert claim.account == "Legal & Professional Fees" and claim.account_origin == "alias"


def test_a_model_mapping_is_kept_only_when_no_alias_exists_and_is_marked():
    text = "Lawyer bills rose $90K because of the fundraise."
    proposal = ClaimProposal(quote=text, account="Legal & Professional Fees", change_text="$90K",
                             driver_text="the fundraise", extractor="model")
    claim = admit(proposal, text, LEDGER, "C1", set())
    assert claim.account_origin == "model"


def test_a_sentence_asserting_nothing_is_not_a_claim():
    text = "Legal is an account."
    result = admit(ClaimProposal(quote=text), text, LEDGER, "C1", set())
    assert isinstance(result, Rejection) and result.reason == "no_assertion"


def test_sentences_never_split_on_a_decimal_point():
    parts = sentences("Cloud grew 16% to $94.5K. Legal rose $90K.\n- Travel fell $12K")
    assert [s.text for s in parts] == ["Cloud grew 16% to $94.5K.", "Legal rose $90K.", "Travel fell $12K"]


def test_rule_extractor_proposes_one_claim_per_assertion():
    text = "October commentary.\nLegal costs rose $90K because of our funding round.\nThanks."
    proposals = RuleExtractor().propose(text, LEDGER)
    assert len(proposals) == 1 and proposals[0].change_text == "$90K"


def test_bare_because_states_a_reason():
    # "because X grew" used to read as no reason at all, so the cause was never checked
    # and a wrong one passed on the amount alone.
    from proven.claims import split_reason
    _head, reason, _strength = split_reason("Marketing rose $8.8K because the sponsorship grew.")
    assert reason and "sponsorship" in reason
