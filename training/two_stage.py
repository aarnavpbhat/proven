"""A two-stage local proposer: one model copies the claim, another guesses its search terms.

    $MLX_PY training/two_stage.py --claims replies-<copy model>-<suite>.jsonl --suite unseen \
        --model <hf term model> [--adapter DIR] --name proven-two-stage [--samples 4 --temp 0.8]

Stage 1 is a saved run of a whole-close proposer (`batch_propose.py --replies`): its quote,
account, figures and stated reason are kept, its search terms are thrown away. Stage 2 asks
a term model (`build_terms_dataset.py`) the teacher's question for each distinct
(account, stated reason): the chart's account names and that one reason, nothing else. No
transaction, vendor or memo reaches either stage, so the pair is as blind as one proposer.
The rewritten replies go through the same `OpenWeightExtractor` and `CachedExtractor` path as
a live run under `--name`, and `teach-sim --extractor openweight --model <name>` then scores
them from the cache. With `--samples K` the greedy answer is pooled with K-1 sampled ones,
most-proposed first, and cut to `--max-terms`: a vote that never looks at the ledger.
The terms asked for are saved to `--terms` (JSON) so a run can be re-pooled without the GPU.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from repool import content_key  # noqa: E402
from teacher_terms import BRIEF, SYSTEM  # noqa: E402
from proven import worlds  # noqa: E402
from proven.cache import CachedExtractor  # noqa: E402
from proven.llm import payload  # noqa: E402
from proven.openweight import OpenWeightExtractor, parse_reply  # noqa: E402
from proven.synth import generate_split  # noqa: E402


def claims_of(text: str) -> list[dict]:
    """The claim objects of a stage-1 reply, or none if it does not parse."""
    try:
        data = parse_reply(text)
    except ValueError:
        return []
    items = data.get("claims") if isinstance(data, dict) else data
    return [c for c in items or [] if isinstance(c, dict)]


def vote(answers: list[list[str]], cap: int, min_votes: int = 1) -> list[str]:
    """Terms by how many answers proposed them; ties keep the greedy answer's order.

    With `min_votes` above 1 a term needs that many answers behind it, unless that would
    leave nothing, in which case every term stands."""
    counts: dict[str, int] = {}
    for terms in answers:
        for term in dict.fromkeys(terms):
            counts[term] = counts.get(term, 0) + 1
    ranked = [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    agreed = [t for t in ranked if counts[t] >= min_votes]
    return (agreed or ranked)[:cap]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--claims", required=True, type=Path, help="stage-1 replies (JSON lines)")
    p.add_argument("--model", default="", help="the term model; omit with --from-terms")
    p.add_argument("--adapter", default="")
    p.add_argument("--name", required=True, help="the model name the cache is keyed by")
    p.add_argument("--suite", default="dev")
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--samples", type=int, default=1)
    p.add_argument("--temp", type=float, default=0.8)
    p.add_argument("--max-terms", type=int, default=8)
    p.add_argument("--min-votes", type=int, default=1, help="drop a term fewer answers proposed")
    p.add_argument("--keep", action="store_true", help="pool stage 1's own terms in as one more answer")
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--terms", type=Path, default=None, help="save every answer here")
    p.add_argument("--from-terms", type=Path, default=None, help="re-pool saved answers; no model is loaded")
    p.add_argument("--cache-dir", default=os.environ.get("PROVEN_CACHE_DIR") or ".proven/cache")
    args = p.parse_args(argv)

    saved = {}
    for line in args.claims.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        saved[row["key"]] = (row.get("samples") or [row["reply"]])[0]
    closes, asks, missing = [], {}, 0
    for world in worlds.suite(args.suite):
        chart = "\n".join(f"- {spec.name}" for spec in world.specs)
        for phrasing in args.phrasings:
            split = generate_split("test", args.n, phrasing, world=world)
            for scenario in split[:len(split) // 2]:
                content = payload(scenario.explanation, scenario.ledger)
                text = saved.get(content_key(content))
                if text is None:
                    missing += 1
                    continue
                claims = claims_of(text)
                closes.append((scenario, content, claims, world.name))
                for claim in claims:
                    account, reason = claim.get("account") or "", claim.get("reason_text") or ""
                    if account and reason:
                        asks[f"{world.name}\t{account}\t{reason}"] = BRIEF.format(
                            chart=chart, items=f'1. [{account}] "{reason}"')
    print(f"{len(closes)} closes, {len(asks)} distinct (world, account, reason) asks, "
          f"{missing} closes with no stage-1 reply", flush=True)

    if args.from_terms:
        answers = json.loads(args.from_terms.read_text(encoding="utf-8"))
    else:
        from mlx_lm import load
        from mlx_lm.sample_utils import make_sampler

        import memguard
        from batch_propose import generate
        from term_probe import parse
        memguard.install()
        model, tokenizer = load(args.model, adapter_path=args.adapter or None)
        model.eval()
        keys = list(asks)
        prompts = [tokenizer.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": asks[k]}],
            add_generation_prompt=True, tokenize=True) for k in keys]
        answers = {k: [] for k in keys}
        start = time.time()
        for round_ in range(args.samples):
            sampler = make_sampler(temp=args.temp) if round_ else None
            for i in range(0, len(keys), args.batch):
                texts = generate(model, tokenizer, prompts[i:i + args.batch], 160, None, sampler)
                for key, text in zip(keys[i:i + args.batch], texts):
                    answers[key].append(parse(text))
            print(f"round {round_ + 1}/{args.samples} done, {time.time() - start:.0f}s", flush=True)
        if args.terms:
            args.terms.write_text(json.dumps(answers, ensure_ascii=False, indent=0), encoding="utf-8")

    replies: dict[str, str] = {}

    def transport(url: str, headers: dict, body: bytes) -> bytes:
        content = json.loads(body)["messages"][1]["content"]
        return json.dumps({"choices": [{"message": {"content": replies[content]},
                                        "finish_reason": "stop"}]}).encode("utf-8")

    extractor = CachedExtractor(OpenWeightExtractor(transport=transport, model=args.name,
                                                    base_url="http://127.0.0.1:8090/v1"), args.cache_dir)
    empty = unanswered = 0
    for scenario, content, claims, world_name in closes:
        out = []
        for claim in claims:
            key = f"{world_name}\t{claim.get('account') or ''}\t{claim.get('reason_text') or ''}"
            mine = answers.get(key)
            if mine is None and key in asks:
                unanswered += 1
            pool = list((mine or [])[:args.samples])
            if args.keep or not pool:        # a claim the term model never saw keeps what it had
                pool.append([t for t in claim.get("search_terms") or [] if isinstance(t, str)])
            out.append({**claim, "search_terms": vote(pool, args.max_terms, args.min_votes)})
        replies[content] = json.dumps({"claims": out}, ensure_ascii=False)
        empty += not extractor.propose(scenario.explanation, scenario.ledger)
    print(f"{len(closes)} closes stored as {args.name} (samples {args.samples}, max terms {args.max_terms}); "
          f"{empty} with no proposals, {unanswered} claims with no answer")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
