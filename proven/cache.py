"""A disk cache for model proposals, so a benchmark is paid for once.

The key covers everything that determines a proposal: the extractor, its
version, its model, a fingerprint of its prompt, the explanation text and the
chart of accounts. Change any of them and the entry is not reused. Transactions
are not part of the key because a model extractor never sees them.

Empty results are not stored: an extractor returns nothing on a refusal or a
malformed reply, and those should be retried rather than remembered.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict
from pathlib import Path

from proven.claims import ClaimProposal
from proven.ledger import Ledger


class CachedExtractor:
    def __init__(self, inner, directory: str | Path = ".proven/cache"):
        self.inner = inner
        self.name = inner.name
        self.version = inner.version
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
        self._memory: dict[str, list[ClaimProposal]] = {}
        model = str(getattr(inner, "model", "")).replace("/", "_").replace(":", "_")
        self.path = Path(directory) / f"{inner.name}-{model or 'default'}.jsonl"
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._memory[entry["key"]] = [_proposal(p) for p in entry["proposals"]]

    @property
    def transmissions(self) -> list[dict]:
        return list(getattr(self.inner, "transmissions", []))

    @property
    def budget(self):
        return getattr(self.inner, "budget", None)

    def key(self, text: str, ledger: Ledger) -> str:
        material = json.dumps([
            self.inner.name, self.inner.version, getattr(self.inner, "model", ""),
            getattr(self.inner, "fingerprint", ""), text,
            [[a.name, list(a.aliases)] for a in ledger.accounts],
        ], ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        key = self.key(text, ledger)
        with self._lock:
            if key in self._memory:
                self.hits += 1
                return list(self._memory[key])
        proposals = self.inner.propose(text, ledger)
        with self._lock:
            self.misses += 1
            if proposals and key not in self._memory:
                self._memory[key] = list(proposals)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"key": key, "proposals": [asdict(p) for p in proposals]},
                                            ensure_ascii=False) + "\n")
        return proposals


def _proposal(data: dict) -> ClaimProposal:
    data = dict(data)
    data["driver_terms"] = tuple(data.get("driver_terms") or ())
    return ClaimProposal(**data)
