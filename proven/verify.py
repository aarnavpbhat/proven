"""Checking one claim against the ledger. Deterministic; makes no provider call.

WHAT IS CHECKED

    direction       did the account move the way the sentence says?
    change          by the stated amount, at the precision it was written to?
    percent         by the stated percentage?
    prior / current to the stated balances?
    attribution     do the transactions matching the stated reason account for
                    the movement — all of it, most of it, or part of it, as the
                    wording claims?
    classification  is an expense matching the reason booked to a different
                    account than its vendor normally uses — either missing from
                    this account or inflating it?

THE VERDICT ALGEBRA (Aptio's, unchanged)

    any CONFIRMED finding        -> FAIL    the explanation contradicts the books
    else any ADVISORY finding    -> REVIEW  a person must decide
    else no decisive check ran   -> REVIEW  an absence of findings is not a pass
    else                         -> PASS

Two asymmetries are deliberate. A possible misclassification is ADVISORY,
never CONFIRMED, because whether a booking is wrong is an accounting judgement
this product does not make. And a reason we could not find in the ledger is
REVIEW, never FAIL: the cause may be real and recorded in words we did not
search for. FAIL is reserved for contradictions that re-executing arithmetic
over the transactions establishes on its own.

THE MODEL GUARD

A model may help find evidence; it may never be the reason a claim passes. If
the stated reason is supported only through search terms a model proposed, or
the account was mapped only by a model, the claim goes to REVIEW and the
adjustment is recorded beside the verdict that would otherwise have stood.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from proven.claims import Claim, Strength, Term, _account_tokens, declared_terms, term_pattern
from proven.ledger import TOTAL, Contribution, Ledger, Transaction
from proven.money import Figure, compare, fmt_money, fmt_pct, fmt_signed

VERSION = "0.1"


@dataclass(frozen=True)
class Policy:
    """Every threshold that can change a verdict, declared in one place and shown to the reviewer."""

    amount_rel_tolerance: float = 0.05   # narrative rounding accepted without question
    amount_review_band: float = 0.10     # beyond tolerance but within this: a person decides
    materiality: float = 1000.0          # dollars; movements below this are not attributed
    full_share: float = 0.75             # "because of" must explain at least this much
    majority_share: float = 0.50         # "primarily" must explain at least this much
    partial_share: float = 0.10          # "partly" must explain at least this much
    wrong_cause_share: float = 0.25      # below this the stated reason is the wrong cause
    vendor_home_min_count: int = 3       # history needed before a vendor has a "usual" account
    vendor_home_min_share: float = 0.80  # and how consistent that history must be
    # Off by default: a model's search terms then support no verdict at all. When on, a
    # model term that is specific (see `_specific_model_terms`) may support a PASS. It
    # may never support a FAIL, with the flag on or off.
    model_terms_anchor: bool = False
    model_term_max_share: float = 0.25   # a specific term matches at most this share of the account

    def required_share(self, strength: Strength) -> float:
        return {Strength.FULL: self.full_share, Strength.MAJORITY: self.majority_share,
                Strength.PARTIAL: self.partial_share}[strength]

    def to_dict(self) -> dict:
        return asdict(self)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


CONFIRMED = "confirmed"
ADVISORY = "advisory"


@dataclass
class Finding:
    code: str
    severity: str
    summary: str
    detail: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Check:
    name: str
    ran: bool
    outcome: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClaimResult:
    claim: Claim
    verdict: Verdict
    computed_verdict: Verdict
    reason: str
    checks: list[Check]
    findings: list[Finding]
    reconstruction: dict
    adjustments: list[str]

    def evidence_ids(self) -> set[str]:
        return {txn for finding in self.findings for txn in finding.evidence}

    def to_dict(self) -> dict:
        return {
            "claim": self.claim.to_dict(),
            "verdict": self.verdict.value,
            "computed_verdict": self.computed_verdict.value,
            "reason": self.reason,
            "checks": [c.to_dict() for c in self.checks],
            "findings": [f.to_dict() for f in self.findings],
            "reconstruction": self.reconstruction,
            "adjustments": self.adjustments,
        }


# ── helpers ──────────────────────────────────────────────────────────────

def _describe(txn: Transaction) -> str:
    return f"{txn.vendor} {fmt_money(txn.amount)} on {txn.date} (“{txn.memo}”)"


def match_reason(ledger: Ledger, account: str, terms: list[Term]) -> dict[str, tuple[Transaction, Term]]:
    """Transactions in scope whose vendor or memo contains one of the terms."""
    patterns = [(term, term_pattern(term.text)) for term in terms]
    matched: dict[str, tuple[Transaction, Term]] = {}
    for txn in ledger.in_scope(account):
        for term, pattern in patterns:
            if pattern.search(txn.searchable):
                matched[txn.id] = (txn, term)
                break
    return matched


def _movement(ledger: Ledger, matched: dict[str, tuple[Transaction, Term]]) -> tuple[float, float]:
    prior = sum(t.amount for t, _ in matched.values() if t.period == ledger.prior_period)
    current = sum(t.amount for t, _ in matched.values() if t.period == ledger.current_period)
    return prior, current


def _movers(ledger: Ledger, account: str, direction: float, policy: Policy,
            exclude: set[str] = frozenset(), limit: int = 3) -> list[Contribution]:
    """The vendors whose movement, in the direction that matters, is material."""
    out = [c for c in ledger.contributions(account, exclude)
           if abs(c.change) >= policy.materiality and c.change * direction > 0]
    return out[:limit]


def _moving(ledger: Ledger, mover: Contribution) -> list[Transaction]:
    """The transactions behind a vendor's movement, largest first.

    Those with no counterpart (by memo) in the other period: a retainer billed
    in both months is not why the account moved, and citing it as evidence
    would send the reviewer to the wrong line. Falls back to every transaction
    in the period when nothing is new — the same bill, simply larger.
    """
    up = mover.change > 0
    here = ledger.current_period if up else ledger.prior_period
    there = ledger.prior_period if up else ledger.current_period
    txns = [ledger.txn(t) for t in mover.txn_ids]
    elsewhere = {t.memo for t in txns if t.period == there}
    moved = [t for t in txns if t.period == here and t.memo not in elsewhere]
    chosen = moved or [t for t in txns if t.period == here]
    return sorted(chosen, key=lambda t: -abs(t.amount))


def _mover_txns(ledger: Ledger, movers: list[Contribution]) -> list[str]:
    return [t.id for mover in movers for t in _moving(ledger, mover)]


def _movers_text(ledger: Ledger, movers: list[Contribution]) -> str:
    if not movers:
        return "no single vendor moved by more than the materiality threshold"
    parts = []
    for mover in movers:
        moved = _moving(ledger, mover)
        memo = f" (“{moved[0].memo}”)" if moved else ""
        parts.append(f"{mover.vendor} {fmt_signed(mover.change)}{memo}")
    return "; ".join(parts)


def _terms_text(terms: list[Term]) -> str:
    by_origin: dict[str, list[str]] = {}
    for term in terms:
        by_origin.setdefault(term.origin, []).append(term.text)
    return "; ".join(f"{', '.join(words)} ({origin})" for origin, words in by_origin.items())


def _compare_figure(name: str, code: str, actual: float, shown: str, stated: Figure,
                    policy: Policy, account: str, what: str,
                    unit: str = "$") -> tuple[Check, Finding | None]:
    outcome = compare(actual, stated, policy.amount_rel_tolerance, policy.amount_review_band)
    diff = abs(actual - stated.value)
    diff_text = f"{diff:.1f} points" if unit == "%" else fmt_money(diff)
    check = Check(name, True, outcome, f"stated {stated.text}; ledger {shown}")
    if outcome == "agree":
        return check, None
    precision = (f"±{stated.half_unit:g} points" if unit == "%"
                 else f"±{fmt_money(stated.half_unit)}")
    detail = (f"{account}: {what} is {shown}. The stated {stated.text} differs by {diff_text}, "
              f"outside the {policy.amount_rel_tolerance:.0%} tolerance and the {precision} "
              f"the figure was written to.")
    if outcome == "near":
        return check, Finding(f"{code}_NEAR", ADVISORY,
                              f"States {stated.text}; the ledger shows {shown} — close, "
                              f"but outside tolerance.", detail)
    return check, Finding(code, CONFIRMED, f"States {stated.text}; the ledger shows {shown}.", detail)


# ── the claim ────────────────────────────────────────────────────────────

def verify_claim(claim: Claim, ledger: Ledger, policy: Policy | None = None) -> ClaimResult:
    policy = policy or Policy()
    checks: list[Check] = []
    findings: list[Finding] = []
    decisive: list[str] = []

    if claim.account is None:
        findings.append(Finding(
            "ACCOUNT_NOT_FOUND", ADVISORY,
            "The sentence names no account in the chart of accounts.",
            f"None of the {len(ledger.accounts)} accounts' names or aliases occurs in this "
            f"sentence, so nothing in it can be checked. Map the wording to an account, "
            f"or add an alias to the chart."))
        for name in ("direction", "change", "attribution", "classification"):
            checks.append(Check(name, False, "", "no account to check against"))
        return _finish(claim, checks, findings, decisive, {}, policy)

    account = claim.account
    var = ledger.variance(account)
    change = var.change
    sign = 1.0 if change >= 0 else -1.0
    movers = _movers(ledger, account, sign, policy)
    recon: dict = {
        "account": account, "prior": round(var.prior, 2), "current": round(var.current, 2),
        "change": round(change, 2),
        "change_pct": None if var.change_pct is None else round(var.change_pct, 2),
        "movers": [m.to_dict() for m in ledger.contributions(account)[:6]],
    }
    where = f"{ledger.prior_period} {fmt_money(var.prior)} → {ledger.current_period} {fmt_money(var.current)}"

    # direction
    if claim.direction is None:
        checks.append(Check("direction", False, "", "no direction stated"))
    else:
        actual = 0 if abs(change) < 0.005 else (1 if change > 0 else -1)
        said = "rose" if claim.direction > 0 else "fell"
        if actual == claim.direction:
            checks.append(Check("direction", True, "agree", f"stated {said}; ledger {fmt_signed(change)}"))
            decisive.append("direction")
        else:
            moved = "did not move" if actual == 0 else ("rose" if actual > 0 else "fell")
            checks.append(Check("direction", True, "disagree", f"stated {said}; ledger {fmt_signed(change)}"))
            findings.append(Finding(
                "WRONG_DIRECTION", CONFIRMED,
                f"Says the account {said}; it {moved} ({fmt_signed(change)}).",
                f"{account}: {where}. Largest movements: {_movers_text(ledger, movers)}.",
                _mover_txns(ledger, movers)))

    # figures
    pct = var.change_pct
    figure_checks = (
        ("change", "WRONG_AMOUNT", claim.change, abs(change), fmt_signed(change),
         "the change", "$"),
        ("percent", "WRONG_PERCENT", claim.percent, None if pct is None else abs(pct),
         "" if pct is None else f"{pct:+.1f}%", "the percentage change", "%"),
        ("current", "WRONG_BALANCE", claim.current, var.current, fmt_money(var.current),
         f"the {ledger.current_period} balance", "$"),
        ("prior", "WRONG_BALANCE", claim.prior, var.prior, fmt_money(var.prior),
         f"the {ledger.prior_period} balance", "$"),
    )
    for name, code, stated, actual, shown, what, unit in figure_checks:
        if stated is None:
            if name in ("change", "percent"):
                checks.append(Check(name, False, "", f"no {name} stated"))
            continue
        if actual is None:
            checks.append(Check(name, False, "", "the prior period is zero; no percentage exists"))
            continue
        stated_abs = stated if name not in ("change", "percent") else Figure(
            stated.text, abs(stated.value), stated.half_unit)
        check, finding = _compare_figure(name, code, actual, shown, stated_abs, policy,
                                         account, what, unit)
        if name == "change":
            check.detail = f"stated {stated.text}; ledger {fmt_signed(change)} ({where})"
        checks.append(check)
        if finding is None:
            decisive.append(name)
        else:
            if finding.severity == CONFIRMED:
                finding.detail += f" Largest movements: {_movers_text(ledger, movers)}."
                finding.evidence = _mover_txns(ledger, movers)
            findings.append(finding)

    # attribution
    matched: dict[str, tuple[Transaction, Term]] = {}
    if claim.driver is None:
        checks.append(Check("attribution", False, "", "no reason stated"))
    elif not claim.terms:
        checks.append(Check("attribution", True, "not_found", "no searchable terms in the reason"))
        findings.append(Finding(
            "REASON_NOT_SEARCHABLE", ADVISORY,
            "The stated reason contains no term that can be searched for in the ledger.",
            f"“{claim.driver}” reduces to generic words only.",
            _mover_txns(ledger, movers)))
    elif abs(change) < policy.materiality:
        checks.append(Check("attribution", False, "",
                            f"movement {fmt_signed(change)} is below materiality "
                            f"({fmt_money(policy.materiality)})"))
    else:
        terms = list(claim.terms)
        anchored = [t for t in terms if t.origin != "model"]
        matched = match_reason(ledger, account, terms)
        matched_anchored = match_reason(ledger, account, anchored)
        specific = _specific_model_terms(claim, ledger, policy)
        matched_specific = match_reason(ledger, account, specific)
        attribution = _attribute(claim, ledger, policy, change, movers, matched,
                                 matched_anchored, terms, where, matched_specific)
        checks.append(attribution[0])
        recon["driver"] = attribution[1]
        recon["residual"] = attribution[1].get("residual") if attribution[1] else None
        if attribution[2]:
            findings.append(attribution[2])
        elif attribution[0].outcome == "supported":
            decisive.append("attribution")

    # classification
    if claim.driver is None or not claim.terms or account == TOTAL:
        checks.append(Check("classification", False, "",
                            "needs a stated reason and a single account"))
    else:
        found, reclassified = _classification(claim, ledger, policy)
        recon["reclassified_change"] = reclassified
        checks.append(Check("classification", True, "flagged" if found else "clear",
                            f"{len(found)} possible misclassification(s)" if found
                            else "no expense matching the reason is booked against its vendor's usual account"))
        findings.extend(found)

    return _finish(claim, checks, findings, decisive, recon, policy)


def _specific_model_terms(claim: Claim, ledger: Ledger, policy: Policy) -> list[Term]:
    """The model's terms that are particular enough to count as evidence for a PASS.

    Only when the policy allows it. A term is specific when it is not a word from the
    account's own name or aliases, and it matches no more than a small share of the
    account's transactions in scope: "insurance" in the Insurance account, or "policy"
    where every invoice is a policy, says nothing about which cause moved.
    """
    if not policy.model_terms_anchor:
        return []
    scope = ledger.in_scope(claim.account)
    if not scope:
        return []
    account_words = _account_tokens(claim.account, ledger)
    limit = max(1, int(policy.model_term_max_share * len(scope)))
    out = []
    for term in claim.terms:
        if term.origin != "model" or set(term.text.split()) & account_words:
            continue
        pattern = term_pattern(term.text)
        hits = sum(1 for t in scope if pattern.search(t.searchable))
        if 0 < hits <= limit:
            out.append(term)
    return out


def _attribute(claim, ledger, policy, change, movers, matched, matched_anchored, terms, where,
               matched_specific=None):
    matched_specific = matched_specific or {}
    prior, current = _movement(ledger, matched)
    driver_change = current - prior
    share = driver_change / change
    a_prior, a_current = _movement(ledger, matched_anchored)
    share_anchored = (a_current - a_prior) / change
    residual = change - driver_change
    required = policy.required_share(claim.strength)
    sign = 1.0 if change >= 0 else -1.0
    unexplained = _movers(ledger, claim.account, 1.0 if residual >= 0 else -1.0, policy,
                          exclude=set(matched))
    info = {
        "matched": [{"id": t.id, "term": term.text, "origin": term.origin, "period": t.period,
                     "amount": t.amount} for t, term in matched.values()],
        "prior": round(prior, 2), "current": round(current, 2),
        "change": round(driver_change, 2), "share": round(share, 4),
        "share_anchored": round(share_anchored, 4), "required_share": required,
        "residual": round(residual, 2),
    }
    wording = {Strength.FULL: "attributes the whole movement to it",
               Strength.MAJORITY: "attributes most of the movement to it",
               Strength.PARTIAL: "attributes part of the movement to it"}[claim.strength]

    if not matched:
        all_movers = _movers(ledger, claim.account, sign, policy)
        return (Check("attribution", True, "not_found", "no transaction matches the stated reason"),
                info,
                Finding("REASON_NOT_FOUND", ADVISORY,
                        f"No transaction in {claim.account} mentions the stated reason.",
                        f"Searched vendor and memo fields in {ledger.prior_period} and "
                        f"{ledger.current_period} for: {_terms_text(terms)}. The movement "
                        f"({fmt_signed(change)}) came from: {_movers_text(ledger, all_movers)}. "
                        f"The reason may be real and recorded in other words; a person should look.",
                        _mover_txns(ledger, all_movers)))

    def outcome(value: float) -> str:
        if value >= required or abs(change - value * change) <= policy.materiality:
            return "supported"
        return "wrong_cause" if value < min(policy.wrong_cause_share, required) else "partial"

    explained = (f"Transactions matching the reason moved {fmt_signed(driver_change)} "
                 f"({fmt_money(prior)} → {fmt_money(current)}), {fmt_pct(share)} of the "
                 f"{fmt_signed(change)} change")

    weak = _weak_binding(ledger, claim.account, terms)

    # The words written in the sentence do not bind on their own (nothing matched, or the
    # match is weak). Specific model terms, when the policy allows them, may then carry a
    # PASS by themselves; the weakly matched transactions are left out of that sum.
    if (weak or not matched_anchored) and matched_specific:
        s_prior, s_current = _movement(ledger, matched_specific)
        s_change = s_current - s_prior
        if outcome(s_change / change) == "supported":
            words = ", ".join(sorted({term.text for _t, term in matched_specific.values()}))
            info["anchored_by_model_terms"] = sorted({term.text for _t, term in matched_specific.values()})
            return (Check("attribution", True, "supported",
                          f"Transactions matching the reason moved {fmt_signed(s_change)} "
                          f"({fmt_money(s_prior)} → {fmt_money(s_current)}), "
                          f"{fmt_pct(s_change / change)} of the {fmt_signed(change)} change; "
                          f"the wording {wording} (needs {fmt_pct(required)}); found through "
                          f"model-proposed terms specific to this cause ({words})"),
                    info, None)

    if weak:
        unmatched, hit = weak
        return (Check("attribution", True, "weak_match",
                      f"only {', '.join(hit)} matched; {', '.join(unmatched)} found nothing"),
                info,
                Finding("WEAK_REASON_MATCH", ADVISORY,
                        f"Only part of the stated reason appears in the ledger: "
                        f"\u201c{', '.join(unmatched)}\u201d matches nothing.",
                        f"The words {', '.join(hit)} from \u201c{claim.driver}\u201d match "
                        f"{len(matched)} transaction(s), but {', '.join(unmatched)} appear in "
                        f"no vendor or memo in scope and no declared lexicon entry vouches for "
                        f"the match. The matched transactions may belong to a different cause, "
                        f"so this binding supports neither a pass nor a fail. Matched: "
                        f"{'; '.join(_describe(t) for t, _ in list(matched.values())[:3])}.",
                        list(matched)))

    if outcome(share_anchored) == "supported":
        note = "" if share <= 1.25 else (f"; other movements offset {fmt_signed(residual)}")
        return (Check("attribution", True, "supported",
                      f"{explained}; the wording {wording} (needs {fmt_pct(required)}){note}"),
                info, None)
    if matched_anchored and matched_specific:
        both = {**matched_anchored, **matched_specific}
        b_prior, b_current = _movement(ledger, both)
        if outcome((b_current - b_prior) / change) == "supported":
            words = ", ".join(sorted({term.text for _t, term in matched_specific.values()}))
            info["anchored_by_model_terms"] = sorted({term.text for _t, term in matched_specific.values()})
            return (Check("attribution", True, "supported",
                          f"{explained}; the wording {wording} (needs {fmt_pct(required)}); "
                          f"completed by model-proposed terms specific to this cause ({words})"),
                    info, None)
    if outcome(share) == "supported":
        model_terms = ", ".join(t.text for t in terms if t.origin == "model")
        return (Check("attribution", True, "model_only", explained),
                info,
                Finding("SUPPORT_RESTS_ON_MODEL_TERMS", ADVISORY,
                        "The reason is supported only through search terms a model proposed.",
                        f"{explained}, but only once the model's terms ({model_terms}) are "
                        f"included; with the terms written in the sentence and the declared "
                        f"lexicon it is {fmt_pct(share_anchored)}. Confirm those transactions "
                        f"belong to the stated reason.",
                        list(matched)))

    if not matched_anchored:
        # Every matched transaction was found through a term the model proposed, and those
        # transactions do not account for the movement. That may mean the stated cause is
        # wrong, or only that the model guessed the wrong words. A model's vocabulary is
        # never the reason a sentence fails.
        model_terms = ", ".join(t.text for t in terms if t.origin == "model")
        all_movers = _movers(ledger, claim.account, sign, policy)
        return (Check("attribution", True, "model_only", explained),
                info,
                Finding("REASON_FOUND_ONLY_BY_MODEL_TERMS", ADVISORY,
                        "The stated reason was found only through search terms a model proposed, "
                        "and those transactions do not account for the movement.",
                        f"{explained}, matched only by the model's terms ({model_terms}); no word "
                        f"written in the sentence or declared in the lexicon matched anything. "
                        f"This neither supports nor refutes the reason. The movement came from: "
                        f"{_movers_text(ledger, all_movers)}.",
                        list(matched) + _mover_txns(ledger, all_movers)))

    result = outcome(share)
    matched_ids = list(matched)
    if result == "wrong_cause":
        return (Check("attribution", True, "wrong_cause", explained), info,
                Finding("WRONG_CAUSE", CONFIRMED,
                        f"The stated reason moved {fmt_signed(driver_change)} — "
                        f"{fmt_pct(share)} of the {fmt_signed(change)} change.",
                        f"{explained}. The sentence {wording}. Terms searched: "
                        f"{_terms_text(terms)}. The movement came from: "
                        f"{_movers_text(ledger, unexplained)}.",
                        matched_ids + _mover_txns(ledger, unexplained)))
    return (Check("attribution", True, "partial", explained), info,
            Finding("PARTIAL_EXPLANATION", CONFIRMED,
                    f"The stated reason accounts for {fmt_signed(driver_change)} "
                    f"({fmt_pct(share)}) of the {fmt_signed(change)} change; "
                    f"{fmt_signed(residual)} is unexplained.",
                    f"{explained}. The sentence {wording}, which needs at least "
                    f"{fmt_pct(required)}. Unexplained movement: "
                    f"{_movers_text(ledger, unexplained)}.",
                    _mover_txns(ledger, unexplained)))


def _weak_binding(ledger: Ledger, account: str,
                  terms: list[Term]) -> tuple[list[str], list[str]] | None:
    """(unmatched written words, matched written words) when the binding is too weak to decide.

    Weak means: some words the writer used for the reason appear nowhere in
    scope, and no declared lexicon entry matched either. Measured on held-out
    phrasing, a single generic word ("policy", "coverage") binding to a
    different cause's invoices was the only mechanism behind every unsafe PASS
    and every false FAIL; this sends that case to a person instead.
    """
    scope = ledger.in_scope(account)
    def hits(term: Term) -> bool:
        pattern = term_pattern(term.text)
        return any(pattern.search(t.searchable) for t in scope)
    vouched = declared_terms()
    declared = [t for t in terms if t.origin in ("lexicon", "learned") or
                (t.origin == "quote" and t.text in vouched)]
    if any(hits(t) for t in declared):
        return None
    written = [t for t in terms if t.origin == "quote"]
    matched = [t.text for t in written if hits(t)]
    unmatched = [t.text for t in written if t.text not in matched]
    return (unmatched, matched) if matched and unmatched else None


def _classification(claim, ledger, policy):
    """Expenses matching the reason, booked against their vendor's usual account."""
    account = claim.account
    findings: list[Finding] = []
    patterns = [(term, term_pattern(term.text)) for term in claim.terms]
    stated = claim.change
    var = ledger.variance(account)
    reclassified_change = var.change

    for txn in ledger.in_scope(TOTAL, ledger.current_period):
        if txn.account == account or abs(txn.amount) < policy.materiality:
            continue
        term = next((t for t, p in patterns if p.search(txn.searchable)), None)
        if term is None:
            continue
        home = ledger.vendor_home(txn.vendor, txn.id, min_count=policy.vendor_home_min_count,
                                  min_share=policy.vendor_home_min_share)
        if home is None or home.account != account:
            continue
        reclassified_change += txn.amount
        findings.append(Finding(
            "POSSIBLE_MISCLASSIFICATION", ADVISORY,
            f"A {fmt_money(txn.amount)} {txn.vendor} expense matching the reason is booked "
            f"to {txn.account}.",
            f"{txn.id}: {_describe(txn)} matched “{term.text}”. {txn.vendor} books to "
            f"{account} in {home.count} of {home.total} other transactions.",
            [txn.id]))

    if findings:
        agreement = ""
        if stated is not None:
            verdict = compare(abs(reclassified_change), Figure(stated.text, abs(stated.value),
                              stated.half_unit), policy.amount_rel_tolerance,
                              policy.amount_review_band)
            agreement = (f" — which agrees with the stated {stated.text}" if verdict == "agree"
                         else f" (stated {stated.text})")
        findings[-1].detail += (f" Reclassified, {account} would change by "
                                f"{fmt_signed(reclassified_change)}{agreement}.")

    for txn in ledger.in_scope(account, ledger.current_period):
        if abs(txn.amount) < policy.materiality:
            continue
        home = ledger.vendor_home(txn.vendor, txn.id, min_count=policy.vendor_home_min_count,
                                  min_share=policy.vendor_home_min_share)
        if home is None or home.account == account:
            continue
        findings.append(Finding(
            "POSSIBLE_MISCLASSIFICATION", ADVISORY,
            f"A {fmt_money(txn.amount)} {txn.vendor} expense in this account usually books "
            f"to {home.account}.",
            f"{txn.id}: {_describe(txn)}. {txn.vendor} books to {home.account} in "
            f"{home.count} of {home.total} other transactions, and this one contributes "
            f"{fmt_signed(txn.amount)} to {account}'s {fmt_signed(var.change)} change.",
            [txn.id]))

    return findings, (None if reclassified_change == var.change else round(reclassified_change, 2))


def _finish(claim: Claim, checks: list[Check], findings: list[Finding], decisive: list[str],
            recon: dict, policy: Policy) -> ClaimResult:
    confirmed = [f for f in findings if f.severity == CONFIRMED]
    advisory = [f for f in findings if f.severity == ADVISORY]
    if confirmed:
        verdict, reason = Verdict.FAIL, confirmed[0].summary
    elif advisory:
        verdict, reason = Verdict.REVIEW, advisory[0].summary
    elif not decisive:
        verdict, reason = Verdict.REVIEW, "Nothing in this sentence could be checked against the ledger."
    else:
        verdict, reason = Verdict.PASS, _pass_reason(checks)

    computed = verdict
    adjustments: list[str] = []
    if claim.account_origin == "model" and verdict is not Verdict.REVIEW:
        verdict = Verdict.REVIEW
        adjustments.append(
            f"Would have been {computed.value}, but the account ({claim.account}) was mapped "
            f"by the model, not by an alias written in the sentence. Confirm the mapping.")
        reason = f"Account mapping proposed by the model; would otherwise be {computed.value}."

    return ClaimResult(claim=claim, verdict=verdict, computed_verdict=computed, reason=reason,
                       checks=checks, findings=findings, reconstruction=recon,
                       adjustments=adjustments)


def _pass_reason(checks: list[Check]) -> str:
    agreed = [c for c in checks if c.ran and c.outcome in ("agree", "supported")]
    names = {"direction": "direction", "change": "amount", "percent": "percentage",
             "current": "balance", "prior": "prior balance", "attribution": "stated reason"}
    listed = [names[c.name] for c in agreed if c.name in names]
    attribution = next((c for c in agreed if c.name == "attribution"), None)
    tail = f" {attribution.detail.split(';')[0]}." if attribution else ""
    return f"Agrees with the ledger: {', '.join(listed)}.{tail}"
