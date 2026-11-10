"""Other worlds: the loader's rules, and that the measured suite is fit to measure with."""
import json
from pathlib import Path

import pytest

from proven import teachsim, worlds
from proven.claims import anchored_terms, term_pattern
from proven.evaluate import OracleExtractor
from proven.extract import RuleExtractor
from proven.ledger import Ledger
from proven.synth import DEFAULT, HELDOUT, PARAPHRASE_TEST, PARAPHRASE_TRAIN, cause_terms, generate, generate_split

UNSEEN = worlds.suite("unseen")
TRAINING = Path(__file__).resolve().parents[2] / "training" / "worlds"


def as_json(world=DEFAULT) -> dict:
    """The default world written as a world file, oblique phrases in tier order."""
    return {"slug": "roundtrip", "entities": list(world.entities), "accounts": [
        {"name": s.name, "aliases": list(s.aliases), "narrative": list(s.narrative),
         "recurring": [{"vendor": r.vendor, "base": r.base, "memo": r.memo} for r in s.recurring],
         "events": [{"key": e.key, "vendor": e.vendor, "memos": list(e.memos), "plain": list(e.phrases),
                     "oblique": list(HELDOUT[e.key] + PARAPHRASE_TEST[e.key] + PARAPHRASE_TRAIN[e.key]),
                     "low": e.low, "high": e.high, "cross_memo": e.cross_memo} for e in s.events]}
        for s in world.specs]}


def test_the_default_world_survives_the_loader_whole():
    world, report = worlds.build(as_json())
    # The loader is stricter than the default world's own tests (an oblique phrase may not
    # bind to the sibling cause or fire the built-in lexicon), which costs it one account.
    assert report.accounts_kept >= 8 and report.plain_dropped == 0
    kept = {s.name for s in world.specs}
    assert [s.name for s in world.specs] == [s.name for s in DEFAULT.specs if s.name in kept]
    for spec in world.specs:
        for event in spec.events:
            assert set(world.heldout[event.key]) <= set(HELDOUT[event.key] + PARAPHRASE_TEST[event.key])


def test_a_phrase_that_uses_the_books_words_is_not_oblique():
    data = as_json()
    data["accounts"][0]["events"][1]["oblique"].insert(0, "the patent matter")
    world, report = worlds.build(data)
    assert "the patent matter" not in world.heldout["litigation"]
    assert report.oblique_dropped >= 1


def test_a_thin_world_is_refused():
    data = as_json()
    data["accounts"] = data["accounts"][:3]
    with pytest.raises(worlds.WorldRefused):
        worlds.build(data)


def test_a_cause_billed_by_the_wrong_kind_of_vendor_drops_its_account():
    data = as_json()
    data["accounts"][0]["events"][1]["vendor"] = data["accounts"][0]["recurring"][0]["vendor"]
    world, _report = worlds.build(data)
    assert "Legal & Professional Fees" not in {s.name for s in world.specs}


def test_the_generator_is_unchanged_for_the_default_world():
    a, b = generate(123), generate(123, world=DEFAULT)
    assert a.explanation == b.explanation and a.ledger.sha256() == b.ledger.sha256()
    assert a.scenario_id == "syn-00123" and a.world == "default"


def test_the_unseen_suite_has_enough_worlds_and_their_tiers_are_disjoint():
    assert len(UNSEEN) >= 8
    for world in UNSEEN:
        assert len(world.specs) >= worlds.MIN_ACCOUNTS
        for spec in world.specs:
            for event in spec.events:
                tiers = (world.heldout[event.key], world.paraphrase_test[event.key],
                         world.paraphrase_train[event.key])
                assert len(tiers[0]) == 2 and len(tiers[1]) == 4 and len(tiers[2]) >= 2
                flat = [p.lower() for tier in tiers for p in tier]
                assert len(flat) == len(set(flat))
                assert len(cause_terms(spec, event)) >= 2


@pytest.mark.parametrize("world", UNSEEN, ids=lambda w: w.name)
def test_unseen_oblique_phrases_do_not_bind_to_their_own_cause(world):
    ledger = Ledger(world.name, "2026-09", "2026-10", world.chart, ())
    for spec in world.specs:
        for event in spec.events:
            rows = [f"{event.vendor} {m}".lower() for m in event.memos] + [event.cross_memo.lower()]
            for phrase in world.heldout[event.key] + world.paraphrase_test[event.key]:
                terms = anchored_terms(phrase, spec.name, ledger)
                assert not any(term_pattern(t.text).search(row) for t in terms for row in rows), phrase


@pytest.mark.parametrize("world", UNSEEN, ids=lambda w: w.name)
def test_unseen_worlds_never_fail_a_control_or_pass_a_defect(world):
    """Rules alone, and rules taught by the oracle: the checker must stay safe in books it
    was not written around, or a proposer's score there means nothing."""
    for phrasing in ("seen", "heldout"):
        closes = generate_split("test", 44, phrasing, world=world)
        taught = teachsim.teach(closes[:22], OracleExtractor)
        for lessons in ([], taught):
            result = teachsim.measure(closes[22:], lessons, lambda _s: RuleExtractor())
            assert result["control_fails"] == 0 and result["unsafe_passes"] == 0, (phrasing, result)
    assert teachsim.measure(generate_split("test", 44, "seen", world=world), [],
                            lambda _s: RuleExtractor())["decided_share"] > 0.5


def test_measured_and_training_worlds_share_no_industry_vendor_or_memo():
    if not TRAINING.is_dir():
        pytest.skip("training worlds are not in this checkout")
    files = sorted(TRAINING.glob("*/*.json"))
    assert len(files) >= 40
    train_names = {f.stem for f in files}
    assert not train_names & {w.name for w in UNSEEN}
    authors = {json.loads(f.read_text(encoding="utf-8"))["author"] for f in files}
    unseen_authors = {json.loads(f.read_text(encoding="utf-8"))["author"]
                      for f in sorted((worlds.HERE / "unseen").glob("*.json"))}
    assert not authors & unseen_authors, "the measured worlds must have a different author"
    memos = set()
    for f in files:
        world = worlds.load(f, role="train")
        memos |= {m.lower() for s in world.specs for e in s.events for m in e.memos}
    for world in UNSEEN:
        for spec in world.specs:
            for event in spec.events:
                assert not {m.lower() for m in event.memos} & memos
