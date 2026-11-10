"""Re-pool saved sampled replies under another policy, into the cache, without the GPU.

    python training/repool.py --replies replies-<name>-dev.jsonl --suite dev \
        --name proven-qwen3b-worlds-v4t3 --samples 4 --max-terms 3

`batch_propose.py --samples K --replies FILE` keeps every sampled reply. This script reads
that file, pools the first `--samples` replies of each close with `consensus.merge_votes`
(`--samples 1` is the greedy reply alone, with its terms cut to `--max-terms`) and stores
the result under `--name`, through the same `OpenWeightExtractor` and `CachedExtractor`
path as a live run. A pooling policy can then be chosen on the dev worlds for the price of
one sampling run, and scored once on the unseen worlds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import consensus  # noqa: E402
from proven import worlds  # noqa: E402
from proven.cache import CachedExtractor  # noqa: E402
from proven.llm import payload  # noqa: E402
from proven.openweight import OpenWeightExtractor, parse_reply, proposals_from  # noqa: E402
from proven.synth import generate_split  # noqa: E402


def content_key(content: str) -> str:
    """Names a close in a replies file (scenario ids repeat across worlds and phrasings)."""
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:16]


def proposals_of(text: str) -> list:
    try:
        return proposals_from(parse_reply(text))
    except ValueError:
        return []


def pooled_reply(texts: list[str], max_terms: int) -> str:
    """One reply, in the trained layout, from the vote over several (the first is greedy)."""
    merged = consensus.merge_votes([proposals_of(t) for t in texts], max_terms=max_terms)
    return json.dumps({"claims": [{
        "quote": m.quote, "account": m.account or "", "direction": m.direction or "",
        "change_text": m.change_text or "", "percent_text": m.percent_text or "",
        "prior_text": m.prior_text or "", "current_text": m.current_text or "",
        "reason_text": m.driver_text or "", "search_terms": list(m.driver_terms)} for m in merged]},
        ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replies", required=True, type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--suite", default="dev")
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--samples", type=int, default=4)
    p.add_argument("--max-terms", type=int, default=3)
    p.add_argument("--cache-dir", default=os.environ.get("PROVEN_CACHE_DIR") or ".proven/cache")
    args = p.parse_args(argv)

    saved: dict[str, list[str]] = {}
    for line in args.replies.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        saved[row["key"]] = row.get("samples") or [row["reply"]]
    closes = []
    for world in ([None] if args.suite == "default" else worlds.suite(args.suite)):
        for ph in args.phrasings:
            split = generate_split("test", args.n, ph, world=world) if world is not None \
                else generate_split("test", args.n, ph)
            closes += split[:len(split) // 2]
    replies: dict[str, str] = {}

    def transport(url: str, headers: dict, body: bytes) -> bytes:
        content = json.loads(body)["messages"][1]["content"]
        return json.dumps({"choices": [{"message": {"content": replies[content]},
                                        "finish_reason": "stop"}]}).encode("utf-8")

    extractor = CachedExtractor(OpenWeightExtractor(transport=transport, model=args.name,
                                                    base_url="http://127.0.0.1:8090/v1"), args.cache_dir)
    done = missing = short = 0
    for s in closes:
        content = payload(s.explanation, s.ledger)
        texts = saved.get(content_key(content))
        if not texts:
            missing += 1
            continue
        short += len(texts) < args.samples
        replies[content] = pooled_reply(texts[:args.samples], args.max_terms)
        extractor.propose(s.explanation, s.ledger)
        done += 1
    print(f"{done} closes pooled as {args.name} (samples {args.samples}, max terms {args.max_terms}); "
          f"{missing} had no saved reply, {short} had fewer samples than asked")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
