"""The open-weight extractor, against a fake transport (no model, guard on)."""
import json
import urllib.error

import pytest

from proven import extractors, netguard
from proven.cache import CachedExtractor
from proven.llm import NetworkDisabled
from proven.openweight import OpenWeightExtractor, is_loopback, parse_reply, strip_thinking
from proven.report import run
from proven.showcase import EXPLANATION, ledger

LEGAL = "Legal costs rose $90K because of our Series B funding round."


def claim(quote, **fields):
    base = {"quote": quote, "account": "", "direction": "", "change_text": "", "percent_text": "",
            "prior_text": "", "current_text": "", "reason_text": "", "search_terms": []}
    return {**base, **fields}


def reply(content, usage=None):
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": content},
                                    "finish_reason": "stop"}],
                       "usage": usage or {"prompt_tokens": 120, "completion_tokens": 30}}).encode()


class Fake:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, url, headers, body):
        self.requests.append((url, headers, json.loads(body)))
        item = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(item, Exception):
            raise item
        return item


GOOD = reply(json.dumps({"claims": [claim(
    LEGAL, account="Legal", direction="up", change_text="$90K",
    reason_text="our Series B funding round", search_terms=["counsel", "S-1"])]}))


def test_parses_proposals_and_marks_extractor():
    extractor = OpenWeightExtractor(transport=Fake(GOOD), model="m")
    [p] = extractor.propose(EXPLANATION, ledger())
    assert (p.quote, p.account, p.direction, p.change_text) == (LEGAL, "Legal", "up", "$90K")
    assert p.driver_text == "our Series B funding round" and p.driver_terms == ("counsel", "S-1")
    assert p.extractor == "openweight" and p.percent_text is None


def test_request_shape_and_nothing_from_the_ledger_is_sent():
    fake = Fake(GOOD)
    extractor = OpenWeightExtractor(transport=fake, model="qwen3:4b", api_key="k")
    extractor.propose(EXPLANATION, ledger())
    url, headers, body = fake.requests[0]
    assert url == "http://127.0.0.1:11434/v1/chat/completions"
    assert headers["Authorization"] == "Bearer k"
    assert body["temperature"] == 0 and body["response_format"]["type"] == "json_schema"
    assert body["reasoning_effort"] == "none"
    sent = json.dumps(body)
    for txn in ledger().transactions:
        assert txn.id not in sent and txn.memo not in sent
    [record] = extractor.transmissions
    assert record["host"] == "127.0.0.1" and record["loopback"] is True
    assert record["bytes"] > 0 and len(record["payload_sha256"]) == 64
    assert record["input_tokens"] == 120 and "error" not in record


def test_think_blocks_and_fences_are_stripped():
    assert strip_thinking('<think>a {b}</think>\n{"claims": []}') == '{"claims": []}'
    assert strip_thinking('<think>never closed {"claims": [1]}') == ""
    inner = json.dumps({"claims": [claim(LEGAL)]})
    for content in (f"<think>hmm\n{{not json}}</think>{inner}", f"```json\n{inner}\n```",
                    f"Here you go: {inner} Done."):
        assert len(parse_reply(content)["claims"]) == 1
    extractor = OpenWeightExtractor(transport=Fake(reply(f"<think>x</think>{inner}")), model="m")
    assert len(extractor.propose(EXPLANATION, ledger())) == 1


@pytest.mark.parametrize("content", ["", "I cannot help", '{"claims": "no"}', "{broken",
                                     "<think>only thinking"])
def test_malformed_reply_yields_nothing_and_is_recorded(content):
    extractor = OpenWeightExtractor(transport=Fake(reply(content)), model="m")
    assert extractor.propose(EXPLANATION, ledger()) == []
    assert "error" in extractor.transmissions[0]


def test_garbage_transport_and_connection_errors_do_not_raise():
    for bad in (b"not json", b"{}", urllib.error.URLError("refused"), ConnectionRefusedError("x"),
                urllib.error.HTTPError("u", 500, "boom", {}, None)):
        extractor = OpenWeightExtractor(transport=Fake(bad), model="m")
        assert extractor.propose(EXPLANATION, ledger()) == []
        assert extractor.transmissions[0]["error"].startswith("request failed")


def test_odd_field_types_are_tolerated():
    weird = {"claims": [{"quote": LEGAL, "direction": "sideways", "search_terms": [1, "ok", None],
                         "change_text": 5}, "junk", {"quote": ""}]}
    extractor = OpenWeightExtractor(transport=Fake(reply(json.dumps(weird))), model="m")
    [p] = extractor.propose(EXPLANATION, ledger())
    assert p.direction is None and p.driver_terms == ("ok",) and p.change_text is None


def test_falls_back_to_json_mode_when_schema_is_rejected():
    fake = Fake(urllib.error.HTTPError("u", 400, "bad", {}, None), GOOD)
    extractor = OpenWeightExtractor(transport=fake, model="m")
    assert len(extractor.propose(EXPLANATION, ledger())) == 1
    assert [r[2]["response_format"]["type"] for r in fake.requests] == ["json_schema", "json_object"]
    assert extractor.transmissions[0]["response_format"] == "json_object"


def test_loopback_works_with_the_guard_on():
    assert netguard.installed() and not netguard.network_allowed()
    for url in ("http://127.0.0.1:11434/v1", "http://localhost:8080/v1", "http://[::1]:9/v1"):
        extractor = OpenWeightExtractor(transport=Fake(GOOD), model="m", base_url=url)
        assert extractor.loopback and extractor.propose(EXPLANATION, ledger())


def test_non_loopback_is_refused_unless_network_allowed(monkeypatch):
    fake = Fake(GOOD)
    extractor = OpenWeightExtractor(transport=fake, model="m", base_url="https://api.example.com/v1")
    assert not extractor.loopback
    with pytest.raises(NetworkDisabled):
        extractor.propose(EXPLANATION, ledger())
    assert fake.requests == []
    monkeypatch.setattr(netguard, "network_allowed", lambda: True)
    assert extractor.propose(EXPLANATION, ledger())
    [record] = extractor.transmissions
    assert record["host"] == "api.example.com" and record["loopback"] is False
    assert "reasoning_effort" not in fake.requests[0][2]


def test_is_loopback():
    assert all(map(is_loopback, ("127.0.0.1", "127.1.2.3", "localhost", "::1", "[::1]")))
    assert not any(map(is_loopback, ("example.com", "10.0.0.5", "8.8.8.8")))


def test_registry_wiring(tmp_path):
    assert "openweight" in extractors.NAMES
    built = extractors.build("openweight", model="qwen2.5:7b", cache_dir=str(tmp_path))
    assert isinstance(built, CachedExtractor) and built.name == "openweight"
    assert built.inner.model == "qwen2.5:7b" and built.inner.fingerprint
    assert "openweight-qwen2.5_7b" in built.path.name
    assert isinstance(extractors.build("openweight", model="m", cache_dir=None), OpenWeightExtractor)


def test_end_to_end_through_the_pipeline_with_guard_on():
    extractor = OpenWeightExtractor(transport=Fake(GOOD), model="m")
    report = run(EXPLANATION, ledger(), extractor=extractor)
    assert [c["claim"]["quote"] for c in report["claims"]] == [LEGAL]
    assert report["run"]["versions"]["extractor"] == "openweight/0.1"
    assert report["run"]["network"]["transmissions"][0]["loopback"] is True
