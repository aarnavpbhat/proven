"""The published seen / heldout numbers come from these exact scenarios. If this hash moves,
the README's results are no longer reproducible, so it must be a deliberate, announced change."""
import hashlib
import json

from proven.synth import generate

SEEDS = (0, 1, 2, 5, 7, 13, 23, 55, 100, 101, 250, 777, 1234, 2999)
EXPECTED = {
    "seen": "1fe5d33a97c1021a1c035a195b5cab15be7bfe48c889846438d9a8c4cb52e34a",
    "heldout": "87732353904258a6ac11f9608d5285da660cc3ce6b7f02a4555d7e634711f29c",
}


def digest(phrasing: str) -> str:
    parts = []
    for seed in SEEDS:
        s = generate(seed, phrasing=phrasing)
        parts.append({
            "id": s.scenario_id, "family": s.family, "explanation": s.explanation,
            "ledger": s.ledger.sha256(),
            "labels": [[l.quote, l.family, l.kind, l.requirement, l.expected_codes,
                        l.culprits, l.account] for l in s.labels],
        })
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def test_seen_scenarios_are_byte_identical():
    assert digest("seen") == EXPECTED["seen"]


def test_heldout_scenarios_are_byte_identical():
    assert digest("heldout") == EXPECTED["heldout"]
