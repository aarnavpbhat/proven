"""Command line: `python -m proven <command>`.

    serve       the reviewer console (http://127.0.0.1:8765), network off by default
    showcase    run the demo close and print what Proven found
    verify      check an explanation file against a ledger CSV or JSON
    benchmark   per-family results on held-out synthetic closes
    generate    write a labelled synthetic dataset (JSON lines) for training
    replay      re-run every case a reviewer taught Proven from; non-zero if any verdict moved
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from proven import env, showcase
from proven.ledger import Ledger
from proven.report import run


def _print_report(report: dict) -> None:
    cov = report["coverage"]
    print(f"{report['ledger']['entity']}: {report['ledger']['prior_period']} → "
          f"{report['ledger']['current_period']}, {report['ledger']['transaction_count']} transactions")
    print(f"{cov['claims']} claims from {cov['sentences']} sentences; decided {cov['decided']} "
          f"({cov['decided_share']:.0%}); PASS {cov['verdicts']['PASS']}, FAIL {cov['verdicts']['FAIL']}, "
          f"REVIEW {cov['verdicts']['REVIEW']}; {cov['unextracted']} sentence(s) with figures not extracted\n")
    for claim in report["claims"]:
        print(f"[{claim['verdict']:6s}] {claim['claim']['quote']}")
        print(f"         {claim['reason']}")
        for finding in claim["findings"]:
            print(f"         - {finding['code']} ({finding['severity']}): {finding['detail']}")
            if finding["evidence"]:
                print(f"           evidence: {', '.join(finding['evidence'])}")
        print()
    for missed in report["unextracted"]:
        print(f"[NOT EXTRACTED] {missed['text']}")


def _print_benchmark(result: dict) -> None:
    print(f"split={result['split']} phrasing={result['phrasing']} scenarios={result['scenarios']} "
          f"claims={result['claims']}")
    print(f"{'family':26s} {'req':8s} {'n':>5s} {'met':>6s} {'recall':>7s}  verdicts")
    for row in result["families"]:
        recall = "" if row["evidence_recall"] is None else f"{row['evidence_recall']:.2f}"
        v = row["verdicts"]
        print(f"{row['family']:26s} {row['requirement']:8s} {row['n']:5d} {row['met_rate']:6.1%} "
              f"{recall:>7s}  P{v['PASS']} F{v['FAIL']} R{v['REVIEW']} M{v['MISSED']}")
    c, d = result["controls"], result["defects"]
    print(f"\ncontrols: {c['passed']}/{c['n']} passed, {c['false_alarms']} sent to review, "
          f"{c['fails']} failed (must be 0)")
    print(f"defects:  {d['caught']}/{d['n']} met requirement, {d['flagged']} flagged, "
          f"{d['unsafe_passes']} unsafe PASS (must be 0)")
    print(f"coverage: {result['coverage']['decided_share']:.1%} decided without a person;  "
          f"mean reward {result['mean_reward']:.3f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m proven", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the reviewer console")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--allow-network", action="store_true",
                   help="permit the Claude extractor to send narrative text off this machine")
    p.add_argument("--data-dir", default=".proven")

    sub.add_parser("showcase", help="run the demo close")

    p = sub.add_parser("verify", help="check an explanation against a ledger")
    p.add_argument("--ledger", required=True, help="ledger .csv (id,date,account,vendor,memo,amount) or .json")
    p.add_argument("--explanation", required=True, help="text file with the commentary")
    p.add_argument("--json", action="store_true", help="print the full report as JSON")

    p = sub.add_parser("benchmark", help="per-family results on synthetic closes")
    p.add_argument("--split", default="test", choices=("test", "train"))
    p.add_argument("--n", type=int, default=440)
    p.add_argument("--phrasing", default="both", choices=("seen", "heldout", "both"))
    p.add_argument("--extractor", default="rules", help="rules (default) or a model extractor")
    p.add_argument("--model", default=None, help="model id for a model extractor")
    p.add_argument("--allow-network", action="store_true",
                   help="permit a model extractor to send narrative text off this machine")
    p.add_argument("--workers", type=int, default=1, help="parallel requests to a model extractor")
    p.add_argument("--token-budget", type=int, default=None,
                   help="stop sending requests after this many tokens (default 300,000)")
    p.add_argument("--no-cache", action="store_true", help="do not reuse or store model proposals")

    p = sub.add_parser("generate", help="write a labelled synthetic dataset")
    p.add_argument("--split", default="train", choices=("test", "train"))
    p.add_argument("--n", type=int, default=1000)
    p.add_argument("--phrasing", default="seen", choices=("seen", "heldout"))
    p.add_argument("--out", required=True)

    p = sub.add_parser("replay", help="re-verify the cases reviewers taught lessons from")
    p.add_argument("--data-dir", default=".proven")

    args = parser.parse_args(argv)
    env.load()

    if args.command == "serve":
        from proven.server import serve
        serve(args.host, args.port, args.allow_network, args.data_dir)
    elif args.command == "showcase":
        _print_report(run(showcase.EXPLANATION, showcase.ledger()))
    elif args.command == "verify":
        raw = Path(args.ledger).read_text(encoding="utf-8")
        book = Ledger.from_dict(json.loads(raw)) if args.ledger.endswith(".json") else Ledger.from_csv(raw)
        report = run(Path(args.explanation).read_text(encoding="utf-8"), book)
        print(json.dumps(report, indent=2)) if args.json else _print_report(report)
    elif args.command == "benchmark":
        from proven import netguard
        from proven.budget import Budget, BudgetExceeded
        from proven.evaluate import evaluate
        from proven.extractors import build
        extractor = None
        if args.extractor != "rules":
            if args.allow_network:
                netguard.allow_network()
            extractor = build(args.extractor, model=args.model, budget=Budget(args.token_budget),
                              cache_dir=None if args.no_cache else ".proven/cache")
        try:
            for phrasing in (("seen", "heldout") if args.phrasing == "both" else (args.phrasing,)):
                _print_benchmark(evaluate(args.split, args.n, phrasing=phrasing,
                                          extractor=extractor, workers=args.workers))
                print()
        except (BudgetExceeded, RuntimeError) as exc:
            if extractor is None:
                raise
            print(f"stopped: {exc}", file=sys.stderr)
            return 1
        finally:
            budget = getattr(extractor, "budget", None)
            if budget is not None:
                print(f"model usage: {budget.calls} request(s), {budget.input_tokens:,} input + "
                      f"{budget.output_tokens:,} output tokens (budget {budget.max_tokens:,}); "
                      f"cache {getattr(extractor, 'hits', 0)} hit(s)", file=sys.stderr)
    elif args.command == "replay":
        from proven import learned
        results = learned.replay(args.data_dir)
        for r in results:
            note = "" if r["lesson_active"] else "  (its lesson has been removed)"
            print(f"[{'ok' if r['ok'] else 'CHANGED':7s}] {r['quote']}\n"
                  f"          lesson {r['lesson_id']}: {r['before']} -> {r['expected']} when taught; "
                  f"now {r['actual']}{note}")
        bad = [r for r in results if not r["ok"]]
        print(f"\n{len(results)} case(s), {len(bad)} changed")
        return 1 if bad else 0
    elif args.command == "generate":
        from proven.synth import generate_split
        with open(args.out, "w", encoding="utf-8") as handle:
            for scenario in generate_split(args.split, args.n, args.phrasing):
                handle.write(json.dumps(scenario.to_dict()) + "\n")
        print(f"wrote {args.n} {args.split} scenarios ({args.phrasing} phrasing) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
