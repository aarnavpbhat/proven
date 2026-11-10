"""Summarise a request log written by mlx_proxy.py: latency per close and tokens/sec.

    python training/latency.py <requests.jsonl> [--since <unix-time>]

One request is one close (openweight sends one request per explanation). "tokens/sec" is
completion tokens divided by the request's wall time, prompt processing included.
"""
from __future__ import annotations

import argparse
import json
import statistics


def summarise(path: str, since: float = 0.0) -> dict:
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    rows = [r for r in rows if r["at"] >= since and r["status"] == 200]
    seconds = [r["seconds"] for r in rows]
    out_tokens = [r["completion_tokens"] or 0 for r in rows]
    return {
        "requests": len(rows),
        "mean_seconds": round(statistics.mean(seconds), 2) if rows else None,
        "median_seconds": round(statistics.median(seconds), 2) if rows else None,
        "mean_prompt_tokens": round(statistics.mean(r["prompt_tokens"] or 0 for r in rows), 1) if rows else None,
        "mean_completion_tokens": round(statistics.mean(out_tokens), 1) if rows else None,
        "completion_tokens_per_second": round(sum(out_tokens) / sum(seconds), 1) if rows else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    parser.add_argument("--since", type=float, default=0.0)
    args = parser.parse_args()
    print(json.dumps(summarise(args.log, args.since), indent=1))


if __name__ == "__main__":
    main()
