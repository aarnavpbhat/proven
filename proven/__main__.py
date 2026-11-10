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
    if result.get("rejected"):
        print("rejected proposals: " + ", ".join(f"{reason} {count}"
                                                 for reason, count in result["rejected"].items()))


def _teach_curves(args, proposer) -> int:
    """`teach-sim --order/--careless/--gate`: decided share against confirmations."""
    from proven import teachsim
    orders = ("arrival", "frequency") if args.order == "both" else (args.order or "frequency",)
    gates = {"off": (False,), "on": (True,), "both": (False, True)}[
        args.gate or ("both" if args.careless else "off")]
    checkpoints = tuple(int(c) for c in args.checkpoints.split(",") if c.strip())
    ok = True
    for order in orders:
        for use_gate in gates:
            result = teachsim.curve(args.n, args.phrasing, proposer, order=order, checkpoints=checkpoints,
                                    careless=args.careless, use_gate=use_gate, seed=args.seed, skew=args.skew,
                                    any_model_match=args.any_model_match)
            s = result["stats"]
            print(f"proposer={result['proposer']} phrasing={result['phrasing']} order={order} "
                  f"gate={'on' if use_gate else 'off'} careless={args.careless:g}"
                  f"{f' skew={args.skew:g}' if args.skew else ''}"
                  f"{' queue=any-model-match' if args.any_model_match else ''}; measured with the rules on "
                  f"{result['held_closes']} closes never taught from")
            print("confirmations  asks  careless  decided  reward  controls passed  control FAIL  unsafe PASS")
            for r in result["rows"]:
                print(f"{r['label']:>13}  {r['asks']:>4}  {r['careless_lessons']:>8}  {r['decided_share']:>7.1%}  "
                      f"{r['mean_reward']:>6.3f}  {r['controls_passed']:>7}/{r['controls']:<7}  "
                      f"{r['control_fails']:>12}  {r['unsafe_passes']:>11}")
            gate_note = (f"; gate: {s['gate_calls']} checks, {s['gate_ms'] / max(1, s['gate_calls']):.0f} ms each, "
                         f"refused {s['refused_wrong']} lesson(s) from wrong explanations and "
                         f"{s['refused_right']} from right ones") if use_gate else ""
            print(f"lessons from right explanations {s['careful']}, from wrong ones {s['careless']}; "
                  f"wrong explanations declined {s['declined_wrong']}{gate_note}\n")
            if use_gate or not args.careless:
                ok &= all(r["unsafe_passes"] == 0 and r["control_fails"] == 0 for r in result["rows"])
    return 0 if ok else 1


def _usage(extractor) -> None:
    budget = getattr(extractor, "budget", None)
    if budget is not None:
        usd_cap = "" if budget.max_usd is None else f" of ${budget.max_usd:.2f}"
        print(f"model usage: {budget.calls} request(s), {budget.input_tokens:,} input + "
              f"{budget.output_tokens:,} output tokens (budget {budget.max_tokens:,}); "
              f"${budget.usd:.4f}{usd_cap}; "
              f"cache {getattr(extractor, 'hits', 0)} hit(s)", file=sys.stderr)


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
    p.add_argument("--phrasing", default="both", choices=("seen", "heldout", "paraphrase", "both"))
    p.add_argument("--extractor", default="rules", help="rules (default) or a model extractor")
    p.add_argument("--model", default=None, help="model id for a model extractor")
    p.add_argument("--allow-network", action="store_true",
                   help="permit a model extractor to send narrative text off this machine")
    p.add_argument("--workers", type=int, default=1, help="parallel requests to a model extractor")
    p.add_argument("--token-budget", type=int, default=None,
                   help="stop sending requests after this many tokens (default 300,000)")
    p.add_argument("--usd-budget", type=float, default=None,
                   help="stop sending requests after this many US dollars (default $PROVEN_USD_BUDGET)")
    p.add_argument("--no-cache", action="store_true", help="do not reuse or store model proposals")
    p.add_argument("--anchor-model-terms", action="store_true",
                   help="experimental: let specific model-proposed terms support a PASS")
    p.add_argument("--suite", default=None, choices=("independent",),
                   help="score a hand-written suite against its answer key instead of synthetic closes")
    p.add_argument("--json", default=None, help="with --suite: also write the full result to this file")

    p = sub.add_parser("teach-sim", help="simulate a reviewer confirming model terms as lessons")
    p.add_argument("--n", type=int, default=440, help="closes: first half taught from, second half measured")
    p.add_argument("--phrasing", default="heldout", choices=("seen", "heldout", "paraphrase"))
    p.add_argument("--extractor", default="oracle", help="who proposes the terms: oracle (default) or a model extractor")
    p.add_argument("--model", default=None, help="model id for a model extractor")
    p.add_argument("--allow-network", action="store_true",
                   help="let a hosted model be called; without it only cached answers and loopback servers work")
    p.add_argument("--usd-budget", type=float, default=None)
    p.add_argument("--order", default=None, choices=("arrival", "frequency", "both", "hindsight"),
                   help="count the reviewer's time in confirmations, asking in this order "
                        "(both: arrival and frequency; hindsight: the bound, ranked by the measured half)")
    p.add_argument("--careless", type=float, default=0.0, metavar="P",
                   help="the reviewer also confirms terms on WRONG explanations with probability P; "
                        "reported without and with the safety gate")
    p.add_argument("--gate", default=None, choices=("off", "on", "both"),
                   help="replay each lesson through the safety gate before storing it "
                        "(default: off, or both with --careless)")
    p.add_argument("--seed", type=int, default=0, help="seed for the careless reviewer")
    p.add_argument("--skew", type=float, default=0.0,
                   help="draw closes whose phrases follow a Zipf law with this exponent (oracle only)")
    p.add_argument("--any-model-match", action="store_true",
                   help="queue every REVIEW claim whose model terms matched transactions, not only "
                        "those whose support rests on them (a harder test for --careless)")
    p.add_argument("--checkpoints", default="0,5,10,20,40",
                   help="report after these many confirmations (and after all of them)")
    p.add_argument("--suite", default=None, choices=("independent",),
                   help="teach from half of a hand-written suite (key-reading reviewer), measure the other half")
    p.add_argument("--json", default=None, help="with --suite: also write the full result to this file")

    p = sub.add_parser("generate", help="write a labelled synthetic dataset")
    p.add_argument("--split", default="train", choices=("test", "train"))
    p.add_argument("--n", type=int, default=1000)
    p.add_argument("--phrasing", default="seen", choices=("seen", "heldout", "paraphrase"))
    p.add_argument("--format", default="scenarios", choices=("scenarios", "chat"),
                   help="scenarios: labelled closes; chat: one {messages} training example per close")
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
        from proven.verify import Policy
        extractor = extractor_for = None
        if args.extractor == "oracle":
            from proven.evaluate import OracleExtractor
            extractor_for = OracleExtractor
        elif args.extractor != "rules":
            if args.allow_network:
                netguard.allow_network()
            else:
                netguard.install()      # loopback model servers still work; anything else is refused
            extractor = build(args.extractor, model=args.model, budget=Budget(args.token_budget, args.usd_budget),
                              cache_dir=None if args.no_cache else ".proven/cache")
        if args.suite:
            if args.extractor == "oracle":
                print("the oracle needs generator gold; a hand-written suite has none", file=sys.stderr)
                return 2
            from proven import independent
            try:
                policy = Policy(model_terms_anchor=True) if args.anchor_model_terms else None
                result = independent.benchmark(args.suite, extractor=extractor, policy=policy)
                print(independent.format_result(result))
                if args.json:
                    Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
            except (BudgetExceeded, RuntimeError) as exc:
                print(f"stopped: {exc}", file=sys.stderr)
                return 1
            finally:
                _usage(extractor)
            return 0
        try:
            for phrasing in (("seen", "heldout") if args.phrasing == "both" else (args.phrasing,)):
                policy = Policy(model_terms_anchor=True) if args.anchor_model_terms else None
                _print_benchmark(evaluate(args.split, args.n, policy=policy, phrasing=phrasing,
                                          extractor=extractor, workers=args.workers,
                                          extractor_for=extractor_for))
                print()
        except (BudgetExceeded, RuntimeError) as exc:
            if extractor is None:
                raise
            print(f"stopped: {exc}", file=sys.stderr)
            return 1
        finally:
            _usage(extractor)
    elif args.command == "teach-sim":
        from proven import teachsim
        proposer = None
        if args.extractor != "oracle":
            from proven import netguard
            from proven.budget import Budget
            from proven.extractors import build
            netguard.allow_network() if args.allow_network else netguard.install()
            proposer = build(args.extractor, model=args.model, budget=Budget(None, args.usd_budget))
        if args.order or args.careless or args.gate or args.skew or args.any_model_match:
            return _teach_curves(args, proposer)
        if args.suite:
            if proposer is None:
                print("teach-sim --suite needs a model proposer (e.g. --extractor claude)", file=sys.stderr)
                return 2
            from proven import independent
            out = independent.teach_and_measure(args.suite, proposer)
            print(independent.format_teach(out))
            if args.json:
                Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
            _usage(proposer)
            ok = all(r["summary"]["defects"]["unsafe_passes"] == 0 and r["summary"]["controls"]["fails"] == 0
                     for direction in out["directions"] for r in (direction["before"], direction["after"]))
            return 0 if ok else 1
        result = teachsim.simulate(args.n, args.phrasing, proposer)
        print(f"proposer={result['proposer']} phrasing={result['phrasing']}; "
              f"measured with the rules on {result['held_closes']} closes never taught from")
        print("taught  lessons  decided  reward  controls passed  control FAIL  unsafe PASS  defects caught")
        for r in result["rows"]:
            print(f"{r['taught_closes']:>6}  {r['lessons']:>7}  {r['decided_share']:>7.1%}  {r['mean_reward']:>6.3f}  "
                  f"{r['controls_passed']:>7}/{r['controls']:<7}  {r['control_fails']:>12}  "
                  f"{r['unsafe_passes']:>11}  {r['defects_caught']:>6}/{r['defects']}")
        ok = all(r["unsafe_passes"] == 0 and r["control_fails"] == 0 for r in result["rows"])
        return 0 if ok else 1
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
                row = scenario.to_chat() if args.format == "chat" else scenario.to_dict()
                handle.write(json.dumps(row) + "\n")
        print(f"wrote {args.n} {args.split} scenarios ({args.phrasing} phrasing, {args.format}) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
