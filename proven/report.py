"""One verification run: explanation + ledger in, a reviewable report out.

The report leads with coverage — how many sentences stated a figure, how many
became checkable claims, how many reached a decision — and only then gives the
verdicts. A defect rate quoted without its denominator is the number that makes
an audit look better than it is, so the two are never merged into one score.

Every run records the hashes of its inputs, the versions of every stage, the
policy in force, and whether anything was transmitted off the machine.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

from proven import __version__
from proven.claims import ClaimProposal, Rejection, admit
from proven.extract import RuleExtractor, sentences, unextracted
from proven.ledger import TOTAL, Ledger
from proven.verify import VERSION as VERIFIER_VERSION
from proven.verify import Policy, Verdict, verify_claim


class Extractor(Protocol):
    """Anything that turns an explanation into claim proposals: the rule extractor or the Claude one."""
    name: str
    version: str

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]: ...


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ledger_summary(ledger: Ledger) -> dict:
    """Every account's prior, current and change, plus a total row, for the console's ledger table."""
    rows = []
    for name in ledger.account_names + [TOTAL]:
        var = ledger.variance(name)
        rows.append({"account": name, "prior": round(var.prior, 2),
                     "current": round(var.current, 2), "change": round(var.change, 2),
                     "change_pct": None if var.change_pct is None else round(var.change_pct, 2),
                     "total": name == TOTAL})
    return {"entity": ledger.entity, "prior_period": ledger.prior_period,
            "current_period": ledger.current_period, "accounts": rows,
            "transaction_count": len(ledger.transactions), "sha256": ledger.sha256()}


def run(text: str, ledger: Ledger, *, extractor: Extractor | None = None,
        policy: Policy | None = None, network_allowed: bool = False) -> dict:
    """Check an explanation against a ledger and return the full report as plain data.

    Extracts proposals, admits or rejects each, verifies the admitted claims, and
    records coverage, the unextracted sentences, the evidence transactions and the
    run record (input hashes, versions, policy, anything transmitted).
    """
    extractor = extractor or RuleExtractor()
    policy = policy or Policy()

    proposals = extractor.propose(text, ledger)
    taken: set[int] = set()
    results, rejected = [], []
    for proposal in proposals:
        admitted = admit(proposal, text, ledger, f"C{len(results) + 1}", taken)
        if isinstance(admitted, Rejection):
            rejected.append(admitted)
        else:
            results.append(verify_claim(admitted, ledger, policy))
    results.sort(key=lambda r: r.claim.start)
    for index, result in enumerate(results, start=1):
        result.claim = replace(result.claim, claim_id=f"C{index}")

    missed = unextracted(text, [(r.claim.start, r.claim.end) for r in results])
    counts = {v.value: 0 for v in Verdict}
    for result in results:
        counts[result.verdict.value] += 1
    decided = counts["PASS"] + counts["FAIL"]

    referenced: set[str] = set()
    for result in results:
        referenced |= result.evidence_ids()
        driver = result.reconstruction.get("driver") or {}
        referenced |= {m["id"] for m in driver.get("matched", [])}
        for mover in result.reconstruction.get("movers", []):
            referenced |= set(mover["txn_ids"])

    transmissions = list(getattr(extractor, "transmissions", []))
    return {
        "run": {
            "run_id": uuid.uuid4().hex[:12],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "explanation_sha256": _sha(text),
            "ledger_sha256": ledger.sha256(),
            "versions": {"proven": __version__, "verifier": VERIFIER_VERSION,
                         "extractor": f"{extractor.name}/{extractor.version}"},
            "policy": policy.to_dict(),
            "network": {"allowed": network_allowed, "transmissions": transmissions},
        },
        "explanation": text,
        "ledger": ledger_summary(ledger),
        "coverage": {
            "sentences": len(sentences(text)),
            "sentences_with_figures": len(missed) + len({r.claim.start for r in results
                                                          if r.claim.change or r.claim.percent
                                                          or r.claim.prior or r.claim.current}),
            "claims": len(results),
            "decided": decided,
            "decided_share": round(decided / len(results), 4) if results else 0.0,
            "verdicts": counts,
            "unextracted": len(missed),
            "rejected": len(rejected),
        },
        "claims": [r.to_dict() for r in results],
        "unextracted": [{"start": s.start, "end": s.end, "text": s.text} for s in missed],
        "rejected": [r.to_dict() for r in rejected],
        "transactions": {t: ledger.txn(t).to_dict() for t in sorted(referenced)},
    }
