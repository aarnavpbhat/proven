"""The Claude extractor, against a fake client: what it sends, and what it may not get away with."""
import json
from types import SimpleNamespace

import pytest

from proven import llm, netguard
from proven.budget import Budget, BudgetExceeded
from proven.llm import ClaudeExtractor, NetworkDisabled
from proven.report import run
from proven.showcase import EXPLANATION, ledger


class FakeClient:
    def __init__(self, claims, stop_reason="end_turn", usage=None, model=None):
        self.requests = []
        self._claims, self._stop, self._usage, self._model = claims, stop_reason, usage, model
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        text = json.dumps({"claims": self._claims})
        return SimpleNamespace(stop_reason=self._stop, usage=self._usage,
                               model=self._model or kwargs["model"],
                               content=[SimpleNamespace(type="text", text=text)])


def usage(**fields):
    base = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation": None, "iterations": None,
            "output_tokens_details": None}
    return SimpleNamespace(**{**base, **fields})


def claim(quote, **fields):
    base = {"quote": quote, "account": "", "direction": "", "change_text": "", "percent_text": "",
            "prior_text": "", "current_text": "", "reason_text": "", "search_terms": []}
    return {**base, **fields}


LEGAL = "Legal costs rose $90K because of our Series B funding round."


@pytest.fixture
def network_on(monkeypatch):
    monkeypatch.setattr(netguard, "network_allowed", lambda: True)


def test_refuses_to_run_with_the_network_off():
    extractor = ClaudeExtractor(client=FakeClient([]))
    with pytest.raises(NetworkDisabled):
        extractor.propose(EXPLANATION, ledger())


def test_sends_only_the_narrative_and_the_chart(network_on):
    client = FakeClient([])
    extractor = ClaudeExtractor(client=client)
    extractor.propose(EXPLANATION, ledger())
    [request] = client.requests
    sent = json.dumps(request)
    for txn in ledger().transactions:
        assert txn.memo not in sent and txn.id not in sent
    assert "Harbor & Vale" not in sent
    assert request["model"] == "claude-opus-5-5" and request["fallbacks"] == "default"
    assert request["output_config"]["format"]["type"] == "json_schema"
    [record] = extractor.transmissions
    assert "transactions" in record["not_sent"] and record["bytes"] > 0


def test_the_output_schema_has_nowhere_to_put_a_verdict():
    fields = set(llm.SCHEMA["properties"]["claims"]["items"]["properties"])
    assert not fields & {"verdict", "status", "severity", "pass", "fail", "correct"}


def test_proposals_cross_the_same_boundary_as_the_rules(network_on):
    client = FakeClient([
        claim(LEGAL, account="Legal & Professional Fees", direction="up", change_text="$90K",
              reason_text="our Series B funding round", search_terms=["closing documents"]),
        claim("Legal costs rose $95K because of the lawsuit.", change_text="$95K"),   # invented
        claim("Contractor costs increased $22K due to the website redesign.",
              change_text="$99K"),                                                   # figure not stated
    ])
    report = run(EXPLANATION, ledger(), extractor=ClaudeExtractor(client=client), network_allowed=True)
    reasons = sorted(r["reason"] for r in report["rejected"])
    assert reasons == ["figure_not_in_quote", "quote_not_in_text"]
    [legal] = report["claims"]
    assert legal["verdict"] == "FAIL"           # decided by the ledger, not the model
    origins = {t["text"]: t["origin"] for t in legal["claim"]["terms"]}
    assert origins["closing documents"] == "model"
    assert report["run"]["network"]["transmissions"][0]["provider"] == "anthropic"


def test_a_refusal_produces_no_proposals(network_on):
    extractor = ClaudeExtractor(client=FakeClient([claim(LEGAL)], stop_reason="refusal"))
    assert extractor.propose(EXPLANATION, ledger()) == []
    assert extractor.transmissions[0]["stop_reason"] == "refusal"


def test_a_reply_cut_off_at_max_tokens_produces_no_proposals(network_on):
    extractor = ClaudeExtractor(client=FakeClient([claim(LEGAL)], stop_reason="max_tokens"))
    assert extractor.propose(EXPLANATION, ledger()) == []
    assert "max_tokens" in extractor.transmissions[0]["error"]


def test_request_shape_per_model(network_on):
    for model, fallback in (("claude-opus-5-5", True), ("claude-sonnet-5-5", True),
                            ("claude-haiku-5-5", False)):
        client = FakeClient([])
        ClaudeExtractor(client=client, model=model).propose(LEGAL, ledger())
        [request] = client.requests
        assert request["model"] == model
        assert request["output_config"]["effort"] == llm.EFFORT
        assert request["output_config"]["format"]["schema"] is llm.SCHEMA
        assert "thinking" not in request and "temperature" not in request
        assert request["messages"][-1]["role"] == "user"      # no prefill
        # Haiku 5.5 has no server-side fallback: send neither the parameter nor its beta.
        assert ("fallbacks" in request) is fallback and ("betas" in request) is fallback
        if fallback:
            assert request["fallbacks"] == "default"
            assert request["betas"] == ["server-side-fallback-2026-07-01"]


def test_fingerprint_follows_the_request_settings():
    assert ClaudeExtractor(effort="low").fingerprint != ClaudeExtractor(effort="medium").fingerprint
    assert ClaudeExtractor().fingerprint == ClaudeExtractor().fingerprint


def test_every_token_category_is_priced(network_on):
    spent = usage(input_tokens=1_000, output_tokens=2_000, cache_creation_input_tokens=300,
                  cache_read_input_tokens=4_000,
                  cache_creation=SimpleNamespace(ephemeral_5m_input_tokens=100,
                                                 ephemeral_1h_input_tokens=200),
                  output_tokens_details=SimpleNamespace(thinking_tokens=1_500))
    budget = Budget(max_tokens=10_000_000)
    extractor = ClaudeExtractor(client=FakeClient([], usage=spent), model="claude-sonnet-5-5",
                                budget=budget)
    extractor.propose(LEGAL, ledger())
    expected = (1_000 * 2.00 + 100 * 2.50 + 200 * 4.00 + 4_000 * 0.10 + 2_000 * 10.00) / 1e6
    [record] = extractor.transmissions
    assert record["usd"] == pytest.approx(expected)
    assert record["thinking_tokens"] == 1_500 and record["cache_read_tokens"] == 4_000
    assert budget.usd == pytest.approx(expected)
    assert budget.input_tokens == 1_000 + 300 + 4_000 and budget.output_tokens == 2_000


def test_haiku_long_prompts_use_the_second_rate_card():
    short = llm.price("claude-haiku-5-5", llm.usage_breakdown(usage(input_tokens=100_000)))
    long = llm.price("claude-haiku-5-5", llm.usage_breakdown(usage(input_tokens=100_001)))
    assert short == pytest.approx(0.01) and long == pytest.approx(100_001 * 0.50 / 1e6)


def test_a_fallback_is_priced_per_attempt_and_an_unknown_model_at_the_highest_rate():
    iterations = [SimpleNamespace(type="message", model="claude-opus-5-5", input_tokens=1_000,
                                  output_tokens=0, cache_creation_input_tokens=0,
                                  cache_read_input_tokens=0, cache_creation=None),
                  SimpleNamespace(type="fallback_message", model="claude-opus-4-8",
                                  input_tokens=1_000, output_tokens=500,
                                  cache_creation_input_tokens=0, cache_read_input_tokens=0,
                                  cache_creation=None)]
    tokens, usd, attempts = llm.cost("claude-opus-5-5", usage(input_tokens=1_000, output_tokens=500,
                                                              iterations=iterations))
    assert len(attempts) == 2 and tokens["input_tokens"] == 2_000
    assert usd == pytest.approx((1_000 * 4.00 + 1_000 * 5.00 + 500 * 25.00) / 1e6)
    _, unknown, _ = llm.cost("claude-new-model", usage(input_tokens=1_000_000))
    assert unknown >= max(rates[0] for rates in llm.PRICES.values())   # never under-counted


def test_terms_that_only_restate_the_account_are_dropped(network_on):
    book = ledger()
    account = next(a for a in book.accounts if a.aliases)
    alias = account.aliases[0]
    client = FakeClient([claim(LEGAL, account=account.name, reason_text="our Series B funding round",
                               search_terms=[alias, alias.upper() + "s", "closing documents"])])
    extractor = ClaudeExtractor(client=client)
    [proposal] = extractor.propose(EXPLANATION, book)
    assert proposal.driver_terms == ("closing documents",)
    assert extractor.transmissions[0]["dropped_terms"]
    assert not llm.restates_account("closing documents", account.name, book)
    assert not llm.restates_account(alias, "Not an account", book)


def test_the_benchmark_sends_each_close_once_with_workers():
    from proven.evaluate import evaluate

    class Empty:
        name, version, transmissions = "fake", "1", []

        def __init__(self):
            self.calls = 0

        def propose(self, text, book):
            self.calls += 1
            return []          # not cached, so a second call would be a second request

    extractor = Empty()
    evaluate("test", 6, extractor=extractor, workers=3)
    assert extractor.calls == 6


def test_the_dollar_budget_stops_the_next_request(network_on):
    spent = usage(input_tokens=1_000_000, output_tokens=0)
    extractor = ClaudeExtractor(client=FakeClient([], usage=spent), model="claude-opus-5-5",
                                budget=Budget(max_tokens=10**9, max_usd=3.0))
    extractor.propose(LEGAL, ledger())              # $4.00, over the cap after the fact
    with pytest.raises(BudgetExceeded):
        extractor.propose(LEGAL, ledger())
    assert len(extractor.transmissions) == 1
