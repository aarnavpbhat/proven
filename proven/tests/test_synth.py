"""The generator's own consistency: if these fail, the benchmark measures nothing."""
import pytest

import re

from proven.claims import LEXICON, STOPWORDS, anchored_terms, term_pattern
from proven.synth import (FAMILIES, HELDOUT, PARAPHRASE_TEST, PARAPHRASE_TRAIN, WORLD, generate,
                          generate_split, seeds, split_of)
from proven.showcase import ledger as showcase_ledger

LEDGER = LEXICON_LEDGER = showcase_ledger()   # any ledger carrying the chart will do for term derivation


def matches(phrase: str, account: str, text: str) -> bool:
    terms = anchored_terms(phrase, account, LEDGER)
    return any(term_pattern(t.text).search(text.lower()) for t in terms)


@pytest.mark.parametrize("spec", WORLD, ids=lambda s: s.name)
def test_every_phrase_binds_to_every_memo_of_its_own_event(spec):
    for event in spec.events:
        for phrase in event.phrases:
            for memo in event.memos:
                assert matches(phrase, spec.name, f"{event.vendor} {memo}"), (phrase, memo)
            assert matches(phrase, spec.name, event.cross_memo), (phrase, event.cross_memo)


@pytest.mark.parametrize("spec", WORLD, ids=lambda s: s.name)
def test_no_phrase_binds_to_the_other_event_or_to_recurring_spend(spec):
    a, b = spec.events
    for this, other in ((a, b), (b, a)):
        for phrase in this.phrases:
            for memo in other.memos:
                assert not matches(phrase, spec.name, f"{other.vendor} {memo}"), (phrase, memo)
            for item in spec.recurring:
                assert not matches(phrase, spec.name, f"{item.vendor} {item.memo}"), (phrase, item)


@pytest.mark.parametrize("spec", WORLD, ids=lambda s: s.name)
def test_heldout_phrases_share_no_word_with_their_own_event(spec):
    for event in spec.events:
        for phrase in HELDOUT[event.key]:
            for memo in event.memos:
                assert not matches(phrase, spec.name, f"{event.vendor} {memo}"), (phrase, memo)


def test_the_first_event_of_each_account_is_billed_by_a_recurring_vendor():
    for spec in WORLD:
        assert spec.events[0].vendor in {r.vendor for r in spec.recurring}, spec.name


def test_generation_is_deterministic():
    a, b = generate(123), generate(123)
    assert a.explanation == b.explanation and a.ledger.sha256() == b.ledger.sha256()
    assert generate(124).ledger.sha256() != a.ledger.sha256()


def test_splits_are_disjoint_and_balanced():
    test, train = seeds("test", 110), seeds("train", 110)
    assert not set(test) & set(train)
    assert all(split_of(s) == "test" for s in test)
    families = {generate(s).family for s in test[: len(FAMILIES)]}
    assert families == {f.name for f in FAMILIES}


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.name)
def test_labels_are_well_formed(family):
    scenario = generate(7, family)
    target = scenario.labels[0]
    assert target.family == family.name and target.quote in scenario.explanation
    if family.kind == "defect":
        assert target.culprits and all(scenario.ledger.txn(t) for t in target.culprits)
    else:
        assert target.culprits == []


# ── the paraphrase tier ──────────────────────────────────────────────────

EVENTS = [(spec, event) for spec in WORLD for event in spec.events]
LEXICON_WORDS = {w for _n, triggers, terms in LEXICON for phrase in (*triggers, *terms)
                 for w in re.findall(r"[a-z0-9&]+", phrase) if len(w) >= 5 and w not in STOPWORDS}


def test_paraphrase_covers_every_cause_in_both_splits():
    keys = {event.key for _s, event in EVENTS}
    assert set(PARAPHRASE_TRAIN) == keys and set(PARAPHRASE_TEST) == keys
    for key in keys:
        assert len(PARAPHRASE_TRAIN[key]) == 8 and len(PARAPHRASE_TEST[key]) == 4, key


def test_paraphrase_phrase_sets_are_disjoint_from_each_other_and_from_heldout():
    train = {p.lower() for ps in PARAPHRASE_TRAIN.values() for p in ps}
    test = {p.lower() for ps in PARAPHRASE_TEST.values() for p in ps}
    heldout = {p.lower() for ps in HELDOUT.values() for p in ps}
    seen = {p.lower() for spec in WORLD for e in spec.events for p in e.phrases}
    assert len(train) == 18 * 8 and len(test) == 18 * 4          # no duplicates inside a tier
    assert not train & test and not (train | test) & heldout and not (train | test) & seen


@pytest.mark.parametrize("spec", WORLD, ids=lambda s: s.name)
def test_paraphrase_phrases_share_no_word_with_the_lexicon_or_their_own_event(spec):
    for event in spec.events:
        own = [f"{event.vendor} {memo}" for memo in event.memos] + [event.cross_memo,
                                                                    event.vendor]
        for phrase in PARAPHRASE_TRAIN[event.key] + PARAPHRASE_TEST[event.key]:
            for text in own:
                assert not matches(phrase, spec.name, text), (phrase, text)
            terms = anchored_terms(phrase, spec.name, LEXICON_LEDGER)
            assert not [t for t in terms if t.origin == "lexicon"], (phrase, terms)
            words = set(re.findall(r"[a-z0-9&]+", phrase.lower()))
            assert not words & LEXICON_WORDS, (phrase, words & LEXICON_WORDS)


def test_paraphrase_phrases_do_not_trip_the_sentence_reader():
    from proven.claims import split_reason
    for phrases in (*PARAPHRASE_TRAIN.values(), *PARAPHRASE_TEST.values()):
        for phrase in phrases:
            assert split_reason(f"Cloud costs rose $10K due to {phrase}.")[1] == phrase, phrase


def test_paraphrase_splits_never_share_a_phrase():
    for split, allowed, banned in (("train", PARAPHRASE_TRAIN, PARAPHRASE_TEST),
                                   ("test", PARAPHRASE_TEST, PARAPHRASE_TRAIN)):
        used = {s.labels[i].gold["reason_text"] for s in generate_split(split, 120, "paraphrase")
                for i in range(len(s.labels))}
        assert used <= {p for ps in allowed.values() for p in ps}
        assert not used & {p for ps in banned.values() for p in ps}


def test_paraphrase_is_deterministic():
    a, b = generate(123, phrasing="paraphrase"), generate(123, phrasing="paraphrase")
    assert a.explanation == b.explanation
