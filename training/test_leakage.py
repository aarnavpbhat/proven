"""The training file contains nothing the benchmark measures on.

    python -m pytest training -q
    PROVEN_TRAINING_DATA=/path/to/data[:/path/to/ablation-data] python -m pytest training -q

Without `PROVEN_TRAINING_DATA` the checks run on a small dataset built into a temporary
directory by the same code; with it, they run on the real files that were trained on.
Standard library and pytest only.

Checked:
  * every row's seed is a train-split seed (seed % 5 != 0), and every row regenerates
    byte for byte from (seed, phrasing) in the manifest, so the manifest is truthful;
  * no HELDOUT phrase and no PARAPHRASE_TEST phrase appears anywhere in any message;
  * no test-split explanation (first 440 test seeds, every phrasing tier) appears;
  * the system and user messages are exactly what `OpenWeightExtractor` sends;
  * in an ablation dataset, no phrase of a held-out cause appears in any tier, and none of
    the ledger terms only that cause leaves appears in any target.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import build_dataset  # noqa: E402
from proven.openweight import OpenWeightExtractor  # noqa: E402
from proven.synth import (HELDOUT, PARAPHRASE_TEST, PARAPHRASE_TRAIN, PHRASINGS, WORLD,  # noqa: E402
                          cause_terms, generate, seeds, split_of)


def _dirs(tmp_path_factory) -> list[Path]:
    configured = os.environ.get("PROVEN_TRAINING_DATA")
    if configured:
        return [Path(p) for p in configured.split(":") if p]
    full = tmp_path_factory.mktemp("full")
    build_dataset.build(full, 40, 40, 10)
    ablation = tmp_path_factory.mktemp("ablation")
    build_dataset.build(ablation, 40, 40, 10, build_dataset.ABLATION_KEYS)
    return [full, ablation]


@pytest.fixture(scope="module")
def datasets(tmp_path_factory) -> list[tuple[dict, dict[str, list[str]]]]:
    out = []
    for directory in _dirs(tmp_path_factory):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        lines = {name: (directory / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 for name in manifest["files"]}
        out.append((manifest, lines))
    return out


def test_only_train_seeds_and_rows_match_the_manifest(datasets):
    for manifest, lines in datasets:
        assert manifest["split"] == "train"
        for name, rows in manifest["files"].items():
            assert len(rows) == len(lines[name])
            for row, line in zip(rows, lines[name]):
                assert row["seed"] % 5 != 0 and split_of(row["seed"]) == "train"
                assert row["phrasing"] in ("seen", "paraphrase")
                scenario = generate(row["seed"], phrasing=row["phrasing"])
                assert json.loads(line) == build_dataset.example(scenario)


def test_no_heldout_or_test_paraphrase_phrase(datasets):
    banned = [p.lower() for bank in (HELDOUT, PARAPHRASE_TEST) for v in bank.values() for p in v]
    for _manifest, lines in datasets:
        for rows in lines.values():
            for line in rows:
                text = " ".join(m["content"] for m in json.loads(line)["messages"]).lower()
                hits = [p for p in banned if p in text]
                assert not hits, hits


def test_no_test_explanation(datasets):
    test_texts = {generate(seed, phrasing=phrasing).explanation
                  for seed in seeds("test", 440) for phrasing in PHRASINGS}
    for _manifest, lines in datasets:
        for rows in lines.values():
            for line in rows:
                explanation = json.loads(json.loads(line)["messages"][1]["content"])["explanation"]
                assert explanation not in test_texts


def test_prompt_is_what_openweight_sends(datasets):
    manifest, lines = datasets[0]
    row = manifest["files"]["train"][0]
    scenario = generate(row["seed"], phrasing=row["phrasing"])
    sent: list[dict] = []

    def transport(url: str, headers: dict[str, str], body: bytes) -> bytes:
        sent.append(json.loads(body))
        return json.dumps({"choices": [{"message": {"content": '{"claims": []}'},
                                        "finish_reason": "stop"}]}).encode()

    extractor = OpenWeightExtractor(transport=transport, model="m", base_url="http://127.0.0.1:9/v1")
    extractor.propose(scenario.explanation, scenario.ledger)
    trained = json.loads(lines["train"][0])["messages"]
    assert sent[0]["messages"] == trained[:2]
    assert trained[2]["role"] == "assistant"


def test_ablation_never_shows_a_held_out_cause(datasets):
    events = {e.key: (spec, e) for spec in WORLD for e in spec.events}
    for manifest, lines in datasets:
        held = set(manifest["exclude_keys"])
        if not held:
            continue
        phrases = [p.lower() for key in held for p in
                   events[key][1].phrases + HELDOUT[key] + PARAPHRASE_TRAIN[key] + PARAPHRASE_TEST[key]]
        kept_terms = {t for key, (spec, e) in events.items() if key not in held for t in cause_terms(spec, e)}
        only_held = {t for key in held for t in cause_terms(*events[key])} - kept_terms
        assert only_held
        for rows in lines.values():
            for line in rows:
                messages = json.loads(line)["messages"]
                text = " ".join(m["content"] for m in messages).lower()
                assert not [p for p in phrases if p in text]
                terms = {t for c in json.loads(messages[2]["content"])["claims"] for t in c["search_terms"]}
                assert not terms & only_held
