"""Trial balance and vendor movements for one independent close, from the CSV alone.

Independent of the checker: reads the files with `csv`/`json` and sums. Used to write the
commentary and the answer key, and by `check_key.py` to verify the key's arithmetic.

    python benchmarks/independent/tb.py brightline [--account "Hosting & Infrastructure"]
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "proven" / "examples" / "independent"


def load(slug: str) -> tuple[dict, list[dict]]:
    folder = ROOT / slug
    chart = json.loads((folder / "chart.json").read_text(encoding="utf-8"))
    with open(folder / "ledger.csv", encoding="utf-8", newline="") as handle:
        rows = [dict(r, amount=float(r["amount"])) for r in csv.DictReader(handle)]
    return chart, rows


def balances(chart: dict, rows: list[dict]) -> dict[str, tuple[float, float]]:
    prior, current = chart["prior_period"], chart["current_period"]
    out: dict[str, list[float]] = {a["name"]: [0.0, 0.0] for a in chart["accounts"]}
    for r in rows:
        if r["date"][:7] == prior:
            out[r["account"]][0] += r["amount"]
        elif r["date"][:7] == current:
            out[r["account"]][1] += r["amount"]
    return {k: (round(v[0], 2), round(v[1], 2)) for k, v in out.items()}


def net_change(chart: dict, rows: list[dict], ids: list[str]) -> float:
    """Current-period amount of the given transactions minus their prior-period amount."""
    by_id = {r["id"]: r for r in rows}
    total = 0.0
    for txn_id in ids:
        r = by_id[txn_id]
        if r["date"][:7] == chart["current_period"]:
            total += r["amount"]
        elif r["date"][:7] == chart["prior_period"]:
            total -= r["amount"]
    return round(total, 2)


def main(argv: list[str]) -> None:
    slug = argv[0]
    only = argv[argv.index("--account") + 1] if "--account" in argv else None
    chart, rows = load(slug)
    prior, current = chart["prior_period"], chart["current_period"]
    bal = balances(chart, rows)
    tp = sum(p for p, _ in bal.values())
    tc = sum(c for _, c in bal.values())
    print(f"{chart['entity']}  {prior} -> {current}")
    for name, (p, c) in bal.items():
        if only and name != only:
            continue
        pct = f"{(c - p) / abs(p) * 100:+.1f}%" if abs(p) > 0.005 else "n/a"
        print(f"\n{name:32s} {p:12,.2f} {c:12,.2f} {c - p:+12,.2f} {pct}")
        vend: dict[str, list] = defaultdict(lambda: [0.0, 0.0, []])
        for r in rows:
            if r["account"] != name or r["date"][:7] not in (prior, current):
                continue
            v = vend[r["vendor"]]
            v[0 if r["date"][:7] == prior else 1] += r["amount"]
            v[2].append(r)
        for vendor, (vp, vc, txns) in sorted(vend.items(), key=lambda kv: -abs(kv[1][1] - kv[1][0])):
            print(f"    {vendor:34s} {vp:11,.2f} {vc:11,.2f} {vc - vp:+11,.2f}  ({len(txns)} txns)")
            if only or abs(vc - vp) > 0.15 * max(abs(c - p), 1000):
                for r in txns:
                    if len(txns) <= 8 or abs(r["amount"]) > 1500:
                        print(f"        {r['id']:12s} {r['date']} {r['amount']:11,.2f}  {r['memo']}")
    print(f"\n{'TOTAL':32s} {tp:12,.2f} {tc:12,.2f} {tc - tp:+12,.2f} {(tc - tp) / tp * 100:+.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
