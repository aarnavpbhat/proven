"""Tool-verified test-time selection: K sampled proposer replies in, one proposal list out.

    merge_votes(candidates)                 self-consistency vote over the K replies
    merge(candidates, ledger, explanation)  the same, with the terms the ledger matches first
    support(proposal, ledger, explanation)  what the checker does with ONE claim's terms

Nothing here reads a label, a scenario or a lesson file. The inputs are the ones on the
user's machine at inference time: the replies, the explanation, the ledger, the checker.
(`_experiment`, at the bottom, is the exception and says so: it uses the generator's answer
key to BUILD simulated replies and to SCORE the outcome, never inside `merge`.)

SAFETY NOTE (read from the code, and checked by `_experiment` and `test_consensus.py`)

Choosing search terms because they match the ledger is the system looking for words that
fit. What stands between a ledger-matched term and a PASS:

  1. Origin. `claims.admit` (claims.py:608-617) gives every proposed term the origin
     "model". `verify._attribute` (verify.py:389) computes `share_anchored` from the
     written/lexicon/learned terms only, and under the default `Policy` a "supported"
     attribution is returned only on that share (verify.py:470). Support that needs the
     model's terms returns SUPPORT_RESTS_ON_MODEL_TERMS, ADVISORY, so REVIEW
     (verify.py:485-495). There is no coverage threshold a model term can clear by itself:
     the full/majority/partial shares (0.75/0.50/0.10) are applied to the anchored share.
  2. So with the default policy, the `driver_terms` that `merge` picks can move a claim
     only TOWARDS review, never to PASS and never to FAIL:
       FAIL -> REVIEW  the written words matched too little (WRONG_CAUSE / PARTIAL), and a
                       picked term matches the lines that really moved, so the total share
                       is "supported" and the finding becomes SUPPORT_RESTS_ON_MODEL_TERMS.
                       On a wrong explanation this takes a correct FAIL away and puts a
                       ready-to-confirm lesson in front of the reviewer instead.
       PASS -> REVIEW  `_classification` (verify.py:619) searches other accounts with every
                       term, model ones included, and may add POSSIBLE_MISCLASSIFICATION.
     `merge` makes the first of these MORE likely than the greedy reply or a blind vote
     does: a term one sample in K guessed for the wrong cause is exactly a term the ledger
     "supports". Seen, not assumed: appending the unstated cause's words to the gold
     reply on 400 train closes turned 69 of 177 defect FAILs into REVIEW in the "seen"
     phrasing and 0 of 108 in "paraphrase" and in "heldout" (there the written words bind
     nothing, so a wrong cause is already REVIEW); no verdict became PASS or FAIL.
     `test_consensus.py` pins one such close.
  3. The reviewer. A claim waiting on model terms becomes a PASS when a person confirms the
     matched terms as a lesson (`teachqueue`, `teachsim.teach`); the terms then have origin
     "learned" and anchor a PASS or a FAIL on every later close whose reason contains the
     trigger. `learned.validate` refuses only malformed or stop-word lessons. `gate.impact`
     refuses a lesson that passes a known-wrong claim, but only for phrases its regression
     set or the stored cases cover. Nothing guards a recurring vendor's words here: a term
     that matches the same retainer in both months moves the share by about nothing and
     is harmless for that reason, not because it is filtered.
     What `merge` changes is therefore what the reviewer is SHOWN: more claims reach
     "supported, confirm these terms", including wrong ones. The finding text still says
     "terms a model proposed"; after `merge` they are terms a model proposed AND the
     ledger selected, which is weaker evidence than the sentence suggests.
  4. `merge` CAN produce a PASS without a reviewer in two ways. Say so plainly:
       a. `Policy(model_terms_anchor=True)` (`--anchor-model-terms`). Specific model terms
          then carry a PASS by themselves (verify.py:363-386, 440-452, 475-484). Its guard
          (not an account word, matches at most 25% of the account's lines) was written for
          terms proposed blind. Ledger-selected terms defeat its purpose.
       b. A claim the greedy reply lacks and half the samples have is added. It is then
          admitted and checked like any other, and may PASS or FAIL on the words written in
          the sentence. That is the deterministic checker deciding, not the picked terms,
          but it is a verdict the greedy reply did not produce.

TEACH ONLY. Use `merge` output to fill the reviewer's queue under the default policy. Do
not check it under `model_terms_anchor=True` (`assert_teach_only` refuses that policy), and
do not read "the ledger supports this term" as evidence the explanation is right: it was
selected for that. `merge_votes` has neither problem beyond what any model reply has.

WHAT "SUPPORTED" MEANS. `merge` asks `verify.match_reason` whether a term matches a
transaction in the claimed account in either period, which is the scope the checker
searches (a decrease's cause is in the prior month). `support` also reports the
current-period matches on their own.
"""
from __future__ import annotations

import sys
from pathlib import Path

from collections import Counter  # noqa: E402
from dataclasses import replace  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proven.claims import STOPWORDS, Claim, ClaimProposal, Rejection, Term, admit  # noqa: E402
from proven.ledger import Ledger  # noqa: E402
from proven.verify import Policy, _movement, match_reason, verify_claim  # noqa: E402

MODEL_SUPPORT = "SUPPORT_RESTS_ON_MODEL_TERMS"
MIN_TERM_CHARS = 3            # `claims.admit` drops shorter proposed terms
_FIELDS = ("account", "change_text", "percent_text", "prior_text", "current_text",
           "driver_text", "direction", "extractor")


def assert_teach_only(policy: Policy | None) -> None:
    """Refuse the one policy under which picked terms decide a PASS with no reviewer."""
    if policy is not None and policy.model_terms_anchor:
        raise ValueError("merge() selects terms because they match the ledger; under "
                         "model_terms_anchor they could pass a claim with no reviewer. "
                         "Use its output with the default policy (teach only).")


def _norm(term: str) -> str:
    return " ".join(term.lower().split())


def _searchable(term: str) -> bool:
    """Would `claims.admit` keep this proposed term at all?"""
    low = _norm(term)
    return len(low) >= MIN_TERM_CHARS and low not in STOPWORDS


def _admit(proposal: ClaimProposal, ledger: Ledger, explanation: str) -> Claim | Rejection:
    return admit(proposal, explanation, ledger, "C1", set())


def _hits(ledger: Ledger, account: str, term: str) -> list:
    """Transactions in the account, either period, that the checker's matcher binds to `term`."""
    return [txn for txn, _term in match_reason(ledger, account, [Term(_norm(term), "model")]).values()]


# ── one claim ────────────────────────────────────────────────────────────

def support(proposal: ClaimProposal, ledger: Ledger, explanation: str,
            policy: Policy | None = None) -> dict:
    """What the ledger and the checker make of one claim's `driver_terms`. No labels.

    The claim is admitted by `claims.admit` and checked by `verify.verify_claim`, with
    whatever lexicon is active; terms are matched by `verify.match_reason`. Amounts cover
    the lines the MODEL's terms matched (the written words' own matches are in
    `share_anchored`):

      matched_terms             matched a line in the claimed account in the current period
      matched_terms_any_period  matched in either period (the scope the checker searches)
      unmatched_terms           admitted, matched nothing
      dropped_terms             not admitted as model terms: a stop word, under 3
                                characters, or already a written/lexicon term of the reason
      transactions, amount      current-period lines matched, and their total
      prior_transactions, prior_amount
      movement                  amount - prior_amount
      share                     movement / the account's change (None if it did not move)
      share_all_terms, share_anchored, required_share   from the checker's reconstruction
      verdict, computed_verdict, attribution, findings  the checker on this claim alone
      waiting_on_model          REVIEW with SUPPORT_RESTS_ON_MODEL_TERMS: what a reviewer
                                would be asked to confirm
    """
    proposed = [t for t in proposal.driver_terms if isinstance(t, str) and t.strip()]
    out: dict = {
        "quote": proposal.quote, "admitted": False, "rejection": None, "account": None,
        "account_origin": None, "change": None, "matched_terms": [],
        "matched_terms_any_period": [], "unmatched_terms": [], "dropped_terms": [],
        "transactions": 0, "amount": 0.0, "prior_transactions": 0, "prior_amount": 0.0,
        "movement": 0.0, "share": None, "share_all_terms": None, "share_anchored": None,
        "required_share": None, "verdict": None, "computed_verdict": None,
        "attribution": None, "findings": [], "waiting_on_model": False,
    }
    claim = _admit(proposal, ledger, explanation)
    if isinstance(claim, Rejection):
        out["rejection"] = claim.reason
        out["dropped_terms"] = [_norm(t) for t in proposed]
        return out
    out.update(admitted=True, account=claim.account, account_origin=claim.account_origin)

    model = [t for t in claim.terms if t.origin == "model"]
    kept = {t.text for t in model}
    out["dropped_terms"] = sorted({_norm(t) for t in proposed} - kept)

    if claim.account is not None:
        account = claim.account
        change = ledger.variance(account).change
        out["change"] = round(change, 2)
        for term in model:
            periods = {txn.period for txn, _t in match_reason(ledger, account, [term]).values()}
            if periods:
                out["matched_terms_any_period"].append(term.text)
            else:
                out["unmatched_terms"].append(term.text)
            if ledger.current_period in periods:
                out["matched_terms"].append(term.text)
        matched = match_reason(ledger, account, model)
        prior, current = _movement(ledger, matched)
        txns = [txn for txn, _t in matched.values()]
        out["transactions"] = sum(t.period == ledger.current_period for t in txns)
        out["prior_transactions"] = sum(t.period == ledger.prior_period for t in txns)
        out["amount"], out["prior_amount"] = round(current, 2), round(prior, 2)
        out["movement"] = round(current - prior, 2)
        out["share"] = round((current - prior) / change, 4) if abs(change) >= 0.005 else None
    else:
        out["unmatched_terms"] = [t.text for t in model]

    result = verify_claim(claim, ledger, policy)
    driver = result.reconstruction.get("driver") or {}
    codes = [f.code for f in result.findings]
    out.update(
        verdict=result.verdict.value, computed_verdict=result.computed_verdict.value,
        attribution=next((c.outcome for c in result.checks if c.name == "attribution" and c.ran),
                         None),
        findings=codes, share_all_terms=driver.get("share"),
        share_anchored=driver.get("share_anchored"), required_share=driver.get("required_share"),
        waiting_on_model=result.verdict.value == "REVIEW" and MODEL_SUPPORT in codes)
    return out


# ── K replies ────────────────────────────────────────────────────────────

def _align(candidates: list[list[ClaimProposal]]) -> tuple[list[str], dict[str, dict[int, ClaimProposal]]]:
    """(quotes in first-seen order, quote -> {candidate index: its first claim with that quote})."""
    order: list[str] = []
    by_quote: dict[str, dict[int, ClaimProposal]] = {}
    for index, candidate in enumerate(candidates):
        for proposal in candidate:
            holders = by_quote.setdefault(proposal.quote, {})
            if not holders:
                order.append(proposal.quote)
            holders.setdefault(index, proposal)
    return order, by_quote


def _base(holders: dict[int, ClaimProposal]) -> ClaimProposal:
    """The greedy reply's claim; without one, each field's most common value (earliest wins a tie)."""
    if 0 in holders:
        return holders[0]
    ordered = [holders[i] for i in sorted(holders)]
    fields = {}
    for name in _FIELDS:
        counts = Counter(getattr(p, name) for p in ordered)
        best = max(counts.values())
        fields[name] = next(getattr(p, name) for p in ordered if counts[getattr(p, name)] == best)
    return ClaimProposal(quote=ordered[0].quote, **fields)


def _votes(holders: dict[int, ClaimProposal]) -> list[tuple[str, int]]:
    """(term as first spelled, how many candidates proposed it), first-seen order."""
    spelling: dict[str, str] = {}
    count: Counter[str] = Counter()
    for index in sorted(holders):
        seen: set[str] = set()
        for raw in holders[index].driver_terms:
            if not isinstance(raw, str) or not _norm(raw):
                continue
            key = _norm(raw)
            spelling.setdefault(key, raw.strip())
            if key not in seen:
                seen.add(key)
                count[key] += 1
    return [(spelling[key], count[key]) for key in spelling]


def _merge(candidates: list[list[ClaimProposal]], ledger: Ledger | None,
           explanation: str | None, max_terms: int) -> list[ClaimProposal]:
    if not candidates:
        return []
    order, by_quote = _align(candidates)
    out: list[ClaimProposal] = []
    for quote in order:
        holders = by_quote[quote]
        if 0 not in holders and 2 * len(holders) < len(candidates):
            continue
        base = _base(holders)
        votes = _votes(holders)
        supported: set[str] = set()
        if ledger is not None and explanation is not None:
            claim = _admit(replace(base, driver_terms=()), ledger, explanation)
            if isinstance(claim, Claim) and claim.account is not None:
                supported = {term for term, _n in votes
                             if _searchable(term) and _hits(ledger, claim.account, term)}
        # sorted() is stable: equal rank keeps first-seen order (the greedy reply's first)
        ranked = sorted(votes, key=lambda tv: (tv[0] not in supported, -tv[1]))
        out.append(replace(base, driver_terms=tuple(t for t, _n in ranked[:max(0, max_terms)])))
    return out


def merge_votes(candidates: list[list[ClaimProposal]], max_terms: int = 8) -> list[ClaimProposal]:
    """Self-consistency, ledger-blind. candidates[0] is the greedy reply.

    Claims are aligned by exact quote. A claim is kept if the greedy reply has it, or at
    least half the candidates do; its fields are the greedy reply's (else the most common).
    Its terms are every candidate's, most-proposed first, de-duplicated without regard to
    case, at most `max_terms`."""
    return _merge(candidates, None, None, max_terms)


def merge(candidates: list[list[ClaimProposal]], ledger: Ledger, explanation: str,
          max_terms: int = 8) -> list[ClaimProposal]:
    """`merge_votes`, with the terms that match a transaction in the claimed account ranked
    before the ones that match nothing (votes order within each group).

    TEACH ONLY: see the safety note at the top of this module. The two functions return
    the same terms unless the cap binds; only then does the ledger decide what is kept."""
    return _merge(candidates, ledger, explanation, max_terms)


# ── an offline estimate, with simulated replies ──────────────────────────

_ABSENT = ("accrual", "true-up", "reclass", "catch-up", "one-off", "timing", "headcount",
           "pricing", "volume", "seasonal")


def _simulated(scenario, rng, k: int, keep: float, sibling: float) -> list[list[ClaimProposal]]:
    """K noisy replies to one close. USES THE ANSWER KEY (gold terms, and the other cause's
    terms in the same account), which is why it lives outside `merge`."""
    from proven.evaluate import proposal_from_gold
    from proven.synth import DEFAULT, cause_terms

    replies = []
    for _ in range(k):
        reply = []
        for label in scenario.labels:
            gold = list(label.gold["search_terms"])
            spec = next(s for s in DEFAULT.specs if s.name == label.account)
            others = [t for event in spec.events for t in cause_terms(spec, event) if t not in gold]
            terms = [t for t in gold if rng.random() < keep]
            if others and rng.random() < sibling:          # words of the cause NOT stated
                terms += rng.sample(others, min(len(others), rng.choice((1, 2))))
            if rng.random() < 0.2:                         # a word of the account's own name
                terms.append(rng.choice(label.account.lower().replace("&", " ").split()))
            if rng.random() < 0.3:                         # a word in no memo
                terms.append(rng.choice(_ABSENT))
            rng.shuffle(terms)
            reply.append(replace(proposal_from_gold(label.gold), driver_terms=tuple(terms),
                                 extractor="openweight"))
        replies.append(reply)
    return replies


def _experiment(n: int = 200, k: int = 4, seed: int = 0) -> None:
    import json
    import random

    import reward
    from proven.report import run
    from proven.synth import generate_split

    scenarios = generate_split("train", n, "paraphrase")
    anchor = Policy(model_terms_anchor=True)
    print(f"{n} train paraphrase closes, default world, K={k} SIMULATED replies per close")
    for keep, sibling in ((0.5, 0.15), (0.5, 0.4)):
        for cap in (8, 3):
            methods = {"gold": reward.gold_proposals, "greedy": None, "merge_votes": None, "merge": None}
            rows = {name: Counter() for name in methods}
            rng = random.Random(f"select-{seed}-{keep}-{sibling}")
            for scenario in scenarios:
                replies = _simulated(scenario, rng, k, keep, sibling)
                chosen = {"gold": reward.gold_proposals(scenario),
                          "greedy": [replace(p, driver_terms=p.driver_terms[:cap]) for p in replies[0]],
                          "merge_votes": merge_votes(replies, cap),
                          "merge": merge(replies, scenario.ledger, scenario.explanation, cap)}
                labels = {label.quote: label for label in scenario.labels}
                for name, proposals in chosen.items():
                    row = rows[name]
                    outcome = reward.score_proposals(scenario, proposals)
                    row["reward"] += outcome.reward
                    for key in ("unsafe", "control_fails", "traps", "lessons"):
                        row[key] += getattr(outcome, key)
                    fixed = reward.Fixed(proposals)
                    first = run(scenario.explanation, scenario.ledger, extractor=fixed)
                    anchored = run(scenario.explanation, scenario.ledger, extractor=fixed, policy=anchor)
                    for report, tag in ((first, "first"), (anchored, "anchor")):
                        for result in report["claims"]:
                            label = labels.get(result["claim"]["quote"])
                            if label is None:
                                continue
                            wrong = label.requirement != "PASS"
                            row[f"{tag}_unsafe"] += wrong and result["verdict"] == "PASS"
                            row[f"{tag}_control_fail"] += (not wrong) and result["verdict"] == "FAIL"
                            row[f"{tag}_defect_fail"] += wrong and result["verdict"] == "FAIL"
                            row[f"{tag}_defect_waiting"] += wrong and any(
                                f["code"] == MODEL_SUPPORT for f in result["findings"])
            print(f"\nkeep={keep} sibling={sibling} max_terms={cap}")
            for name, row in rows.items():
                print(f"  {name:12s}", json.dumps({"mean_reward": round(row["reward"] / n, 4),
                                                   **{key: int(row[key]) for key in sorted(row) if key != "reward"}}))


if __name__ == "__main__":
    _experiment()
