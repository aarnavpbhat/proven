"""Verifies the independent answer keys against the ledgers, using CSV sums only.

Independent of the checker (imports nothing from `proven`). For every keyed claim it
recomputes the account's movement and the net movement of the transactions the key cites,
and asserts that the label follows from the arithmetic:

  CORRECT                 direction right; stated change within 7%, stated percent within
                          1.5 points (or 10% of it), stated balance within 3%; the cause's
                          transactions carry the share the wording claims (whole >= 75%,
                          most >= 50%), unless the key explains why a share is not the measure
  wrong_amount            direction right, some stated figure more than 15% off
  wrong_direction         stated direction opposite to the ledger's
  wrong_account           named account moved less than half the stated change, and the
                          cited cause transactions (in another account) carry the stated amount
  wrong_cause             amount right; the cause's transactions carry < 25% of the change
                          (or, with no cause transactions, other drivers carry > 75%)
  cause_too_small         amount right; the cause carries > 0 but less than the wording needs
  cause_in_other_period   amount right; every cause transaction is in the prior period
  contradicted_by_credit  the cause includes a credit and nets to < 25% of the stated change
  fabricated_cause        amount right; no cause transactions, and the cause's words appear
                          in no memo or vendor of the account (or of the ledger)

    python benchmarks/independent/check_key.py            # exit 1 on any violation
    python benchmarks/independent/check_key.py --annotate # also write ideal/acceptable verdicts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tb import ROOT, balances, load, net_change  # noqa: E402

DEFECTS = {"wrong_amount", "wrong_direction", "wrong_account", "wrong_cause", "cause_too_small",
           "cause_in_other_period", "contradicted_by_credit", "fabricated_cause"}
NEEDS = {"whole": 0.75, "most": 0.5, "part": 0.1}


def verdicts(truth: str) -> tuple[str, list[str]]:
    return ("PASS", ["PASS", "REVIEW"]) if truth == "CORRECT" else ("FAIL", ["FAIL", "REVIEW"])


def rel(stated: float, actual: float) -> float:
    return abs(stated - actual) / max(abs(actual), 1.0)


def check_company(slug: str) -> list[str]:
    errors: list[str] = []
    chart, rows = load(slug)
    commentary = (ROOT / slug / "commentary.txt").read_text(encoding="utf-8")
    key = json.loads((ROOT / slug / "key.json").read_text(encoding="utf-8"))
    bal = balances(chart, rows)
    ids = {r["id"] for r in rows}
    by_id = {r["id"]: r for r in rows}
    prior_p, current_p = chart["prior_period"], chart["current_period"]
    for item in key["non_claims"]:
        if item["quote"] not in commentary:
            errors.append(f"{slug} non-claim quote not verbatim: {item['quote'][:50]}")
    seen: set[str] = set()
    for c in key["claims"]:
        cid = c["id"]
        err = lambda msg: errors.append(f"{cid}: {msg}")  # noqa: E731
        if cid in seen:
            err("duplicate id")
        seen.add(cid)
        if c["quote"] not in commentary:
            err("quote is not verbatim in the commentary")
        for t in c["evidence"] + c["cause_txns"] + c.get("driver_txns", []):
            if t not in ids:
                err(f"cites unknown transaction {t}")
        if c["account"] == "TOTAL":
            prior = sum(p for p, _ in bal.values())
            current = sum(x for _, x in bal.values())
        elif c["account"] not in bal:
            err(f"unknown account {c['account']}")
            continue
        else:
            prior, current = bal[c["account"]]
        change = current - prior
        pct = change / abs(prior) * 100 if abs(prior) > 0.005 else None
        s = c["stated"]
        flat = abs(change) <= 0.02 * max(abs(prior), 1.0)
        actual_dir = "flat" if flat else ("up" if change > 0 else "down")
        dir_ok = s["direction"] == actual_dir or (s["direction"] in ("up", "down") and not flat and s["direction"] == actual_dir)
        if s["direction"] == "flat":
            dir_ok = flat
        offs = {}
        if "change" in s:
            offs["change"] = rel(s["change"], change)
        if "pct" in s and pct is not None:
            offs["pct"] = abs(s["pct"] - pct) / max(abs(pct), 1.0)
            offs["pct_points"] = abs(s["pct"] - pct)
        if "current" in s:
            offs["current"] = rel(s["current"], current)
        amount_ok = (offs.get("change", 0) <= 0.07 and offs.get("current", 0) <= 0.03
                     and (("pct" not in offs) or offs["pct_points"] <= 1.5 or offs["pct"] <= 0.10))
        amount_bad = (offs.get("change", 0) > 0.15 or offs.get("current", 0) > 0.15
                      or ("pct" in offs and offs["pct"] > 0.15 and offs["pct_points"] > 3))
        cause = net_change(chart, rows, c["cause_txns"]) if c["cause_txns"] else 0.0
        share = cause / change if abs(change) > 0.005 else 0.0
        driver = net_change(chart, rows, c.get("driver_txns", [])) if c.get("driver_txns") else 0.0
        driver_share = driver / change if abs(change) > 0.005 else 0.0
        need = NEEDS.get(c["strength"])
        truth, defect = c["truth"], c["defect"]
        ideal, acceptable = verdicts(truth)
        if "ideal" in c and (c["ideal"], c["acceptable"]) != (ideal, acceptable):
            err("ideal/acceptable verdicts do not follow from the truth label")
        if truth == "CORRECT":
            if defect is not None:
                err("a correct claim carries a defect")
            if not dir_ok:
                err(f"labelled correct but direction {s['direction']} vs ledger {actual_dir} ({change:+,.2f})")
            if not amount_ok:
                err(f"labelled correct but figures off: {offs} (ledger change {change:+,.2f}, pct {pct})")
            if need and c["cause_txns"] and "share_note" not in c and share < need:
                err(f"labelled correct but cause share {share:.0%} < {need:.0%} for '{c['strength']}'")
            if need and not c["cause_txns"] and "share_note" not in c:
                err("a correct claim with a cause cites no cause transactions and no share_note")
        elif truth == "WRONG":
            if defect not in DEFECTS:
                err(f"unknown defect {defect}")
            elif defect == "wrong_amount":
                if not dir_ok or not amount_bad:
                    err(f"wrong_amount but direction ok={dir_ok}, offs={offs}")
            elif defect == "wrong_direction":
                if dir_ok:
                    err("wrong_direction but the direction agrees")
            elif defect == "wrong_account":
                if "change" not in s or abs(change) > 0.5 * abs(s["change"]):
                    err(f"wrong_account but the named account moved {change:+,.2f}")
                cause_accounts = {by_id[t]["account"] for t in c["cause_txns"]}
                if c["account"] in cause_accounts or rel(s["change"], cause) > 0.10:
                    err(f"wrong_account cause {cause:+,.2f} in {cause_accounts}")
            elif defect == "contradicted_by_credit":
                credits = [t for t in c["cause_txns"] if by_id[t]["amount"] < 0 and by_id[t]["date"][:7] == current_p]
                if not credits or abs(cause) >= 0.25 * abs(s.get("change", change)) + 0.01 * abs(s.get("change", change)):
                    err(f"contradicted_by_credit but credits={credits}, cause net {cause:+,.2f}")
            else:
                if not dir_ok or not amount_ok:
                    err(f"{defect} needs the amount right: dir_ok={dir_ok}, offs={offs}")
                if defect == "fabricated_cause":
                    if c["cause_txns"]:
                        err("fabricated_cause cites cause transactions")
                    scope = [r for r in rows if c.get("absent_scope") == "ledger" or r["account"] == c["account"]]
                    for term in c.get("absent_terms", []):
                        hits = [r["id"] for r in scope if term.lower() in f"{r['vendor']} {r['memo']}".lower()]
                        if hits:
                            err(f"fabricated_cause term {term!r} appears in {hits[:3]}")
                    if not c.get("absent_terms"):
                        err("fabricated_cause lists no absent_terms")
                elif defect == "wrong_cause":
                    if c["cause_txns"] and share >= 0.25:
                        err(f"wrong_cause but the cause carries {share:.0%}")
                    if not c["cause_txns"] and driver_share <= 0.75:
                        err(f"wrong_cause with no cause transactions needs drivers > 75%, got {driver_share:.0%}")
                elif defect == "cause_too_small":
                    if not need or not (0 < share < need - 0.1):
                        err(f"cause_too_small but share {share:.0%} for '{c['strength']}'")
                elif defect == "cause_in_other_period":
                    periods = {by_id[t]["date"][:7] for t in c["cause_txns"]}
                    if periods != {prior_p}:
                        err(f"cause_in_other_period but cause periods are {periods}")
        else:
            err(f"unknown truth {truth}")
    return errors


def main(argv: list[str]) -> int:
    slugs = sorted(p.name for p in ROOT.iterdir() if (p / "key.json").exists())
    if "--annotate" in argv:
        for slug in slugs:
            path = ROOT / slug / "key.json"
            key = json.loads(path.read_text(encoding="utf-8"))
            for c in key["claims"]:
                c["ideal"], c["acceptable"] = verdicts(c["truth"])
            path.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    errors: list[str] = []
    n = {"CORRECT": 0, "WRONG": 0}
    for slug in slugs:
        errors += check_company(slug)
        for c in json.loads((ROOT / slug / "key.json").read_text(encoding="utf-8"))["claims"]:
            n[c["truth"]] += 1
    for e in errors:
        print("KEY ERROR", e)
    print(f"{len(slugs)} companies, {n['CORRECT'] + n['WRONG']} claims ({n['CORRECT']} correct, "
          f"{n['WRONG']} wrong): {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
