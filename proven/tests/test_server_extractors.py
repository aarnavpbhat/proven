"""The console's extractor choice, the Tidewater example and the offline benchmark selector.

No model is ever reached: the app is given a fake `build` that wraps the real open-weight
extractor around a canned transport (so the real budget and proposal cache are exercised) and
a fake probe for "is a model server running".
"""
import http.client
import json
import threading
import urllib.error

import pytest

from proven import extractors, netguard
from proven.cache import CachedExtractor
from proven.openweight import OpenWeightExtractor
from proven.server import create_server

LEGAL_LEDGER = {"scenario_id": "showcase",
                "explanation": "Legal costs rose $90K because of our Series B funding round."}


def reply(claims):
    return json.dumps({"choices": [{"message": {"content": json.dumps({"claims": claims})},
                                    "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 120, "completion_tokens": 30}}).encode()


GOOD = reply([{"quote": LEGAL_LEDGER["explanation"], "account": "Legal", "direction": "up",
               "change_text": "$90K", "percent_text": "", "prior_text": "", "current_text": "",
               "reason_text": "our Series B funding round", "search_terms": ["counsel"]}])


class Harness:
    """A server whose model extractors talk to canned transports."""

    def __init__(self, tmp_path, monkeypatch):
        self.sent = []                      # every (name, model) the server asked to build
        self.transport_reply = GOOD
        self.probe_result = (True, "", ["qwen3:4b", "llama3"])

        def transport(url, headers, body):
            if isinstance(self.transport_reply, Exception):
                raise self.transport_reply
            return self.transport_reply

        def build(name, *, model=None, budget=None, cache_dir=None):
            self.sent.append((name, model))
            if name == "rules":
                return extractors.build("rules")
            if name not in ("claude", "openweight"):
                raise ValueError(f"unknown extractor {name!r}")
            # The Claude path is faked with the same wire format; it is never a real request.
            inner = OpenWeightExtractor(transport=transport, model=model, budget=budget)
            inner.name = name
            return CachedExtractor(inner, cache_dir)

        monkeypatch.delenv("PROVEN_OPENAI_MODEL", raising=False)
        self.server = create_server("127.0.0.1", 0, tmp_path, build=build,
                                    probe=lambda: self.probe_result)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def __call__(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        conn.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                     headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def api(tmp_path, monkeypatch):
    harness = Harness(tmp_path, monkeypatch)
    yield harness
    harness.close()


def test_config_offers_every_extractor_and_says_why_one_is_unavailable(api):
    _, config = api("GET", "/api/config")
    by_id = {e["id"]: e for e in config["extractors"]}
    assert list(by_id) == list(extractors.NAMES)
    assert by_id["rules"]["available"] is True and by_id["rules"]["uses_model"] is False
    assert by_id["claude"]["available"] is False and "--allow-network" in by_id["claude"]["reason"]
    assert by_id["openweight"]["available"] is True
    assert by_id["openweight"]["models"] == ["qwen3:4b", "llama3"]
    assert by_id["openweight"]["default_model"] == "qwen3:4b"
    api.probe_result = (False, "no model server answered at http://127.0.0.1:11434/v1", [])
    _, config = api("GET", "/api/config")
    ow = next(e for e in config["extractors"] if e["id"] == "openweight")
    assert ow["available"] is False and "no model server" in ow["reason"]
    assert config["benchmark_extractors"] == ["rules", "oracle"]


def test_claude_is_refused_without_allow_network_and_is_never_built(api):
    status, error = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "claude"})
    assert status == 400 and "--allow-network" in error["error"]
    assert all(name != "claude" for name, _ in api.sent)


def test_claude_is_built_with_the_model_when_the_server_allows_the_network(api, monkeypatch):
    monkeypatch.setattr(netguard, "network_allowed", lambda: True)
    status, report = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "claude", "model": "m-test"})
    assert status == 200 and ("claude", "m-test") in api.sent
    assert report["usage"]["extractor"] == "claude" and report["usage"]["model"] == "m-test"


def test_openweight_runs_without_allow_network_and_reports_usage_and_cache(api):
    body = {**LEGAL_LEDGER, "extractor": "openweight", "model": "qwen3:4b"}
    status, report = api("POST", "/api/verify", body)
    assert status == 200 and report["claims"][0]["claim"]["extractor"] == "openweight"
    usage = report["usage"]
    assert (usage["extractor"], usage["model"]) == ("openweight", "qwen3:4b")
    assert (usage["calls"], usage["input_tokens"], usage["output_tokens"], usage["tokens"]) == (1, 120, 30, 150)
    assert usage["cache"] == {"hits": 0, "misses": 1} and usage["usd"] == 0
    assert report["run"]["network"]["transmissions"][0]["not_sent"]
    # Same text again: answered from the proposal cache, no request, no tokens.
    api.transport_reply = urllib.error.URLError("must not be called")
    status, again = api("POST", "/api/verify", body)
    assert status == 200 and again["usage"]["calls"] == 0 and again["usage"]["tokens"] == 0
    assert again["usage"]["cache"] == {"hits": 1, "misses": 0}
    assert again["claims"][0]["verdict"] == report["claims"][0]["verdict"]


def test_rules_report_has_no_usage(api):
    status, report = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "rules"})
    assert status == 200 and "usage" not in report


def test_model_extractor_problems_are_explained_not_500(api):
    status, error = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "openweight"})
    assert status == 400 and "model" in error["error"]
    api.transport_reply = urllib.error.URLError("connection refused")
    status, error = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "openweight", "model": "x"})
    assert status == 400 and "returned nothing usable" in error["error"] and "refused" in error["error"]
    status, error = api("POST", "/api/verify", {**LEGAL_LEDGER, "extractor": "gpt"})
    assert status == 400 and "openweight" in error["error"]


def test_tidewater_loads_with_its_answer_key(api):
    status, scenario = api("GET", "/api/scenario?id=tidewater")
    assert status == 200 and scenario["ground_truth"] is None
    assert scenario["explanation"].startswith("Tidewater Coffee Roasters")
    assert len(scenario["answer_key"]) == 11 and scenario["ledger"]["entity"] == "Tidewater Coffee Roasters"
    assert api("GET", "/api/ledger.csv?id=tidewater")[0] == 200


def test_tidewater_verdicts_come_back_beside_the_key(api):
    status, scenario = api("GET", "/api/scenario?id=tidewater")
    status, report = api("POST", "/api/verify", {"scenario_id": "tidewater",
                                                 "explanation": scenario["explanation"]})
    key = report["answer_key"]
    assert status == 200 and len(key) == 11
    by_quote = {c["claim"]["quote"]: c["verdict"] for c in report["claims"]}
    for row in key:
        assert row["verdict"] == by_quote.get(row["quote"], "MISSED")
        assert {"requirement", "why", "culprits", "met"} <= set(row)
    # A defect must never be passed, and the sentence with no claim must stay unextracted.
    assert not any(r["defective"] and r["verdict"] == "PASS" for r in key)
    no_claim = next(r for r in key if r["requirement"] == "NO_CLAIM")
    assert no_claim["verdict"] == "MISSED" and no_claim["met"] is True
    # A scenario that is not Tidewater, or an uploaded ledger, carries no key.
    _, showcase = api("POST", "/api/verify", LEGAL_LEDGER)
    assert "answer_key" not in showcase


def test_benchmark_offers_rules_and_oracle_and_the_paraphrase_tier(api):
    for extractor, name in (("rules", "rules/0.1"), ("oracle", "oracle/0.1")):
        status, result = api("POST", "/api/benchmark", {"split": "test", "n": 22, "phrasing": "paraphrase",
                                                       "extractor": extractor})
        assert status == 200 and result["extractor"] == name and result["phrasing"] == "paraphrase"
        assert result["defects"]["unsafe_passes"] == 0
    _, default = api("POST", "/api/benchmark", {"n": 22})
    assert default["extractor"] == "rules/0.1"


def test_benchmark_never_runs_a_model_extractor(api):
    for name in ("claude", "openweight"):
        status, error = api("POST", "/api/benchmark", {"n": 22, "extractor": name})
        assert status == 400 and "python -m proven benchmark" in error["error"]
    assert api("POST", "/api/benchmark", {"n": 22, "extractor": "gpt"})[0] == 400
    assert api("POST", "/api/benchmark", {"n": "lots"})[0] == 400
    assert api.sent == []       # nothing was built, so nothing could have been sent
