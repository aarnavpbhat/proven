"""Gold proposals: what a perfect model extractor would return, and the ceiling it reaches."""
import json

import pytest

from proven.claims import Claim, admit
from proven.evaluate import OracleExtractor, evaluate, proposal_from_gold
from proven.llm import SCHEMA, SYSTEM, payload
from proven.synth import PHRASINGS, generate, generate_split

KEYS = set(SCHEMA["properties"]["claims"]["items"]["properties"])


def scenarios(per_phrasing: int = 110):
    for phrasing in PHRASINGS:
        for split in ("train", "test"):
            yield from generate_split(split, per_phrasing, phrasing)


def test_every_gold_proposal_is_admitted():
    count = 0
    for scenario in scenarios():
        taken: set[int] = set()
        for index, label in enumerate(scenario.labels):
            admitted = admit(proposal_from_gold(label.gold), scenario.explanation,
                             scenario.ledger, f"C{index + 1}", taken)
            assert isinstance(admitted, Claim), (scenario.scenario_id, label.gold, admitted)
            assert admitted.account == label.account and admitted.account_origin == "alias"
            assert admitted.driver == label.gold["reason_text"]
            assert any(t.origin == "model" for t in admitted.terms)
            count += 1
    assert count >= 1300       # 660 scenarios across 3 phrasings x 2 splits


def test_gold_has_exactly_the_schema_shape():
    for scenario in scenarios(20):
        for label in scenario.labels:
            gold = label.gold
            assert set(gold) == KEYS, gold
            assert gold["direction"] in ("up", "down")
            assert 3 <= len(gold["search_terms"]) <= 8, gold
            assert all(isinstance(t, str) and t for t in gold["search_terms"])
            for text_key in ("change_text", "percent_text", "reason_text"):
                assert gold[text_key] in label.quote or not gold[text_key]
            assert gold["quote"] == label.quote and gold["reason_text"] in label.quote


def test_gold_terms_describe_the_cause_the_sentence_states():
    # For a wrong_cause defect the sentence blames the decoy; the gold terms are the decoy's,
    # because the extractor reads the sentence and never sees the ledger.
    for seed in range(0, 600):
        scenario = generate(seed, phrasing="paraphrase")
        if scenario.family != "wrong_cause":
            continue
        label = scenario.labels[0]
        culprit_text = " ".join(f"{scenario.ledger.txn(t).vendor} {scenario.ledger.txn(t).memo}"
                                for t in label.culprits).lower()
        # culprits are the (true) event's transactions; no gold term may point at them
        assert not any(term in culprit_text for term in label.gold["search_terms"]), label.gold
        return
    pytest.fail("no wrong_cause scenario found")


def test_chat_example_uses_the_production_prompt_and_payload():
    scenario = generate(7, phrasing="paraphrase")
    row = scenario.to_chat()
    system, user, assistant = row["messages"]
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]
    assert system["content"] == SYSTEM
    assert user["content"] == payload(scenario.explanation, scenario.ledger)
    claims = json.loads(assistant["content"])["claims"]
    assert len(claims) == len(scenario.labels)
    assert [c["quote"] for c in claims] == sorted((c["quote"] for c in claims),
                                                  key=scenario.explanation.find)
    assert "TX-" not in user["content"]          # no transaction ever leaves the machine


def test_cli_writes_chat_jsonl(tmp_path):
    from proven.__main__ import main
    out = tmp_path / "chat.jsonl"
    assert main(["generate", "--split", "train", "--n", "5", "--phrasing", "paraphrase",
                 "--format", "chat", "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 5 and all(set(r) == {"messages"} for r in rows)


# The oracle: an extractor that returns the gold proposals. This is the ceiling a perfect
# model extractor reaches under the current guard, which never lets a claim PASS on terms
# only a model supplied. The numbers are measured, and kept as a test so that a change to
# the guard shows up as a diff rather than as an unannounced number.

@pytest.fixture(scope="module")
def oracle():
    return {p: evaluate("test", 220, phrasing=p, extractor_for=OracleExtractor)
            for p in PHRASINGS}


def test_oracle_is_safe_under_every_phrasing(oracle):
    for result in oracle.values():
        assert result["controls"]["fails"] == 0
        assert result["defects"]["unsafe_passes"] == 0
        assert result["defects"]["missed"] == 0


def test_oracle_matches_the_rules_on_seen_phrasing_and_is_capped_elsewhere(oracle):
    assert oracle["seen"]["coverage"]["decided_share"] >= 0.85
    # Measured ceiling: with model-only terms a correct claim can never PASS, so a perfect
    # extractor decides only what amount, direction and wrong-cause checks decide.
    for phrasing in ("heldout", "paraphrase"):
        assert oracle[phrasing]["coverage"]["decided_share"] < 0.25
        assert oracle[phrasing]["controls"]["passed"] == 0
