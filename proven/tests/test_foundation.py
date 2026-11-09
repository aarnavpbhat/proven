"""The seams the model extractors share: .env, the budget, the cache, learned terms."""
import pytest

from proven import claims, env
from proven.budget import Budget, BudgetExceeded
from proven.cache import CachedExtractor
from proven.claims import ClaimProposal, anchored_terms
from proven.evaluate import evaluate
from proven.extract import RuleExtractor
from proven.showcase import EXPLANATION, ledger


def test_env_parse_and_real_environment_wins(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text("# note\nA_KEY=one\nexport B_KEY='two'\nEMPTY=\nC_KEY=three # trailing\n")
    assert env.parse(file.read_text()) == {"A_KEY": "one", "B_KEY": "two", "EMPTY": "",
                                           "C_KEY": "three"}
    monkeypatch.setenv("A_KEY", "from-shell")
    monkeypatch.delenv("B_KEY", raising=False)
    monkeypatch.delenv("C_KEY", raising=False)
    assert sorted(env.load(file)) == ["B_KEY", "C_KEY"]
    assert env.load(tmp_path / "missing") == []
    import os
    assert os.environ["A_KEY"] == "from-shell" and os.environ["B_KEY"] == "two"
    monkeypatch.delenv("B_KEY"), monkeypatch.delenv("C_KEY")


def test_budget_stops_before_the_next_request():
    budget = Budget(max_tokens=100)
    budget.check()
    budget.add(80, 30)
    with pytest.raises(BudgetExceeded):
        budget.check()
    assert budget.to_dict()["tokens"] == 110 and budget.calls == 1


class _Counting:
    name, version, model = "fake", "1", "m"

    def __init__(self, result):
        self.calls, self.result = 0, result

    def propose(self, text, book):
        self.calls += 1
        return list(self.result)


def test_cache_reuses_proposals_across_instances_and_skips_empty(tmp_path):
    proposal = ClaimProposal(quote="Travel fell $12K.", driver_terms=("airfare",), extractor="fake")
    inner = _Counting([proposal])
    first = CachedExtractor(inner, tmp_path)
    assert first.propose("text", ledger()) == [proposal]
    assert first.propose("text", ledger()) == [proposal]
    assert inner.calls == 1 and first.hits == 1

    again = _Counting([])
    second = CachedExtractor(again, tmp_path)
    assert second.propose("text", ledger()) == [proposal] and again.calls == 0
    second.propose("other text", ledger())
    second.propose("other text", ledger())
    assert again.calls == 2          # an empty result is retried, not remembered


def test_learned_entries_are_anchored_and_off_by_default():
    book = ledger()
    assert not claims.LEARNED
    before = anchored_terms("the all-hands trip to the lake", "Travel & Entertainment", book)
    assert all(t.origin == "quote" for t in before)
    claims.set_learned([("offsite", ("all-hands trip",), ("Offsite",))])
    try:
        after = anchored_terms("the all-hands trip to the lake", "Travel & Entertainment", book)
        assert ("offsite", "learned") in {(t.text, t.origin) for t in after}
        assert "offsite" in claims.declared_terms()
    finally:
        claims.set_learned([])


def test_benchmark_accepts_an_extractor():
    default = evaluate("test", 20)
    explicit = evaluate("test", 20, extractor=RuleExtractor(), workers=4)
    assert explicit["families"] == default["families"]
    assert explicit["extractor"].startswith("rules/")
    assert EXPLANATION
