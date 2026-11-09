"""A hand-written close the generator did not produce.

`tidewater_ledger.csv` is a ledger typed by hand for a small coffee roaster (different company,
accounts, vendors and memo styles from `showcase.py` and `synth.py`), `tidewater_commentary.txt`
is the commentary a controller might write about it, and `tidewater_key.json` is the answer key,
written from the ledger before Proven was run on it. The key is not tuned to the checker.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from proven.ledger import Ledger

HERE = Path(__file__).parent
ENTITY = "Tidewater Coffee Roasters"


@dataclass(frozen=True)
class KeyedSentence:
    quote: str
    requirement: str            # PASS | FAIL | NOT_PASS | NO_CLAIM
    defective: bool
    why: str
    culprits: tuple[str, ...]
    defect: str | None = None


@dataclass(frozen=True)
class Close:
    ledger: Ledger
    commentary: str
    key: tuple[KeyedSentence, ...]


def load() -> Close:
    ledger = Ledger.from_csv((HERE / "tidewater_ledger.csv").read_text(encoding="utf-8"),
                             entity=ENTITY)
    commentary = (HERE / "tidewater_commentary.txt").read_text(encoding="utf-8").strip()
    raw = json.loads((HERE / "tidewater_key.json").read_text(encoding="utf-8"))
    key = tuple(KeyedSentence(s["quote"], s["requirement"], s["defective"], s["why"],
                              tuple(s["culprits"]), s.get("defect")) for s in raw["sentences"])
    return Close(ledger, commentary, key)
