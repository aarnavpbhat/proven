"""Training targets for search terms: guessable and true, never a vendor's name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_worlds_dataset import cause_index, common_words, targets, tokens  # noqa: E402
from proven.synth import DEFAULT, cause_terms, generate_split  # noqa: E402

SPEC = DEFAULT.specs[0]                      # Legal & Professional Fees
FINANCING, LITIGATION = SPEC.events          # billed by a recurring vendor / by a new one
LEDGER = generate_split("train", 1, "seen")[0].ledger


def test_true_guesses_lead_and_vendor_words_never_appear():
    gold = cause_terms(SPEC, LITIGATION)
    assert "meridian" in gold                # the gold terms do name the new vendor
    out, hits = targets(SPEC, LITIGATION, gold, ["lawsuit", "settlement", "meridian", "patent dispute"],
                        LEDGER, 8)
    assert out[:2] == ["settlement", "patent dispute"] and hits == 2
    assert not tokens(" ".join(out)) & (tokens(LITIGATION.vendor) - {"legal"})
    assert out[-1] == "lawsuit"              # a miss is filler, after everything true


def test_routine_and_account_guesses_are_dropped():
    out, _ = targets(SPEC, FINANCING, cause_terms(SPEC, FINANCING),
                     ["retainer", "legal fees", "closing documents"], LEDGER, 8)
    assert "retainer" not in out and "legal fees" not in out
    assert out[0] == "closing documents"


def test_words_one_world_alone_uses_are_left_out_when_enough_remain():
    gold = cause_terms(SPEC, FINANCING)
    out, _ = targets(SPEC, FINANCING, gold, ["financing", "funding round", "term sheet", "investor"],
                     LEDGER, 8, common={"financing", "documents"})
    assert "series" not in out and "documents" in out
    short, _ = targets(SPEC, FINANCING, gold, [], LEDGER, 8, common=set())
    assert len(short) >= 3                   # never starved: gold words come back


def test_cap_and_index():
    out, _ = targets(SPEC, FINANCING, cause_terms(SPEC, FINANCING), [f"guess {i}" for i in range(12)], LEDGER, 8)
    assert len(out) == 8
    index = cause_index(DEFAULT)
    assert index["the fundraise"] == (SPEC, FINANCING)
    assert common_words([DEFAULT, DEFAULT], 2) and not common_words([DEFAULT], 2)
