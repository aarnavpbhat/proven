"""Ask a hosted model to write world files (see `proven/worlds.py`), and keep the valid ones.

    python training/author_worlds.py --role train --model claude-sonnet-5-5 \
        --industries training/industries-train-a.txt --out training/worlds/train --usd-budget 8

One request per industry. The reply is parsed, run through `proven.worlds.build` (which
drops phrases and accounts that break the generator's rules, and refuses thin worlds) and
written to `--out/<slug>.json` with the author recorded. The raw reply is kept under
`--raw` whether or not it validated. Spend is priced from the provider's usage figures,
capped by `--usd-budget` (no request is sent once it is reached) and appended to `--spend-log`.

The measured ("unseen") worlds are written by a different model from the training worlds,
from a disjoint list of industries; `training/world_overlap.py` audits what they share.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proven import env, worlds  # noqa: E402
from proven.llm import cost  # noqa: E402

SYSTEM = """You write fictional company data for testing an accounting tool. You answer with one JSON object and nothing else."""

BRIEF = """Write a "world" for a fictional {industry} company: the operating-expense accounts on its books, the vendors that bill each account every month, and the one-off events that make an account's spending jump in a given month. A month-end close generator will draw ledgers and variance commentary from it.

Return JSON of exactly this shape:

{{"slug": "kebab-case-name", "industry": "{industry}",
 "entities": [five fictional company names for this industry],
 "accounts": [eight accounts, each:
   {{"name": "Account Name As On The Chart",
    "aliases": [4-6 lowercase ways staff refer to the account, e.g. "fleet", "fleet costs", "fleet maintenance spend"],
    "narrative": [3 of those aliases, capitalised the way a sentence would open, e.g. "Fleet costs"],
    "recurring": [2-4 vendors billing this account EVERY month: {{"vendor": "...", "base": monthly dollars 800-30000, "memo": "what the books say"}}],
    "events": [exactly two one-off causes:
      {{"key": "one_word_or_snake_case id, unique in the whole file",
       "vendor": "who bills it",
       "memos": [two memo lines as they appear in the ledger],
       "cross_memo": "a memo for a related charge of the same cause that lands in a different account",
       "plain": [3 short noun phrases a writer would use that reuse the books' own words],
       "oblique": [16 noun phrases describing the same cause WITHOUT the books' words],
       "low": 10000-40000, "high": about twice low}}]}}]}}

Hard rules (a validator enforces them and throws away what fails):

1. Make the accounts fit the industry. At most three may be accounts every company has (rent, software, travel...); the rest should be specific to how a {industry} business spends money. Account names and aliases must not overlap between accounts.
2. events[0].vendor must be one of that account's recurring vendors (an existing vendor billing something extra). events[1].vendor must be a NEW vendor that appears nowhere in recurring.
3. Both memos of a cause and its cross_memo must share a distinctive tag of two or three words (for example "Reefer unit overhaul — compressor swap", "Reefer unit overhaul — labor", cross "Reefer unit overhaul — rental trailer"). The tag's words must not appear in the other cause's memos or vendor, in any recurring vendor or memo of the account, or in the account's own name and aliases. Each cause needs at least three such distinctive words across its memos (and its vendor name, if the vendor is new).
4. Every "plain" phrase must contain the tag words (e.g. "the reefer unit overhaul"), and none of the other cause's or the recurring lines' words.
5. Every "oblique" phrase must share NO word of three or more letters (also no plural or inflected form) with: the cause's own memos, vendor and cross_memo; the other cause's memos and vendor; the account's recurring vendors and memos. Describe what happened the way a controller would in conversation: by its purpose, its effect, who asked for it, where, what it replaced. Vary them: some terse (two or three words), some wordy, some oblique. Example for the overhaul above: "getting the cold-chain trailers back in service", "the refrigeration repairs", "fixing the cooling equipment that failed inspection".
6. Phrases are noun phrases that complete "…rose $20K due to ___". No commas, no semicolons, no month names, no dollar figures, no trailing period. Do not use the words "because", "due to", "driven by".
7. Memos should look like real ledger memos for this industry: {style}. Vendors are fictional but plausible. No real company names.
8. All text in English. Output the JSON object only."""

STYLES = (
    "short invoice descriptions separated with an em dash",
    "terse ERP export lines, some with a PO or work-order number",
    "plain-language descriptions a bookkeeper typed by hand",
    "vendor invoice titles with a project name first",
    "abbreviated AP entries (Inv, Svc, Qtr, Mnt) mixed with full words",
    "descriptions that name the site, vehicle, store or department involved",
)


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", required=True, choices=("train", "measure"))
    p.add_argument("--model", required=True)
    p.add_argument("--industries", required=True, type=Path, help="one industry per line")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--raw", type=Path, default=ROOT / ".proven" / "worlds-raw")
    p.add_argument("--usd-budget", type=float, required=True)
    p.add_argument("--spend-log", type=Path, default=None)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--max-tokens", type=int, default=40000)
    p.add_argument("--effort", default="low")
    args = p.parse_args(argv)

    env.load()
    import anthropic
    client = anthropic.Anthropic()
    industries = [line.strip() for line in args.industries.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#")]
    args.out.mkdir(parents=True, exist_ok=True)
    raw_dir = args.raw / args.role
    raw_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    state = {"usd": 0.0, "ok": 0, "refused": 0, "skipped": 0}

    def one(job: tuple[int, str]) -> None:
        index, industry = job
        stem = re.sub(r"[^a-z0-9]+", "-", industry.lower()).strip("-")
        raw_file = raw_dir / f"{stem}.{args.model}.json"
        if raw_file.exists():
            text = raw_file.read_text(encoding="utf-8")
        else:
            with lock:
                if state["usd"] >= args.usd_budget:
                    state["skipped"] += 1
                    return
            prompt = BRIEF.format(industry=industry, style=STYLES[index % len(STYLES)])
            try:
                # Thinking would otherwise spend the whole output allowance before any JSON.
                extra = ({"thinking": {"type": "between_tools"}} if "sonnet-5-5" in args.model
                         else {"thinking": {"type": "disabled"}} if "haiku" in args.model else {})
                with client.beta.messages.stream(model=args.model, max_tokens=args.max_tokens,
                                                 system=SYSTEM, output_config={"effort": args.effort},
                                                 **extra, messages=[{"role": "user", "content": prompt}]) as stream:
                    reply = stream.get_final_message()
            except Exception as error:  # noqa: BLE001 - one industry failing must not stop the rest
                print(f"{industry}: request failed: {type(error).__name__}: {str(error)[:200]}", flush=True)
                with lock:
                    state["refused"] += 1
                return
            text = "".join(b.text for b in reply.content if getattr(b, "type", "") == "text")
            _tokens, usd, _attempts = cost(args.model, reply.usage)
            with lock:
                state["usd"] += usd
            if reply.stop_reason != "end_turn" or not text.strip():
                print(f"{industry}: stopped with {reply.stop_reason}, {len(text)} characters; not kept "
                      f"(${usd:.2f})", flush=True)
                with lock:
                    state["refused"] += 1
                return
            raw_file.write_text(text, encoding="utf-8")
        try:
            data = extract_json(text)
            data["slug"] = stem
            data["industry"] = industry
            data["author"] = args.model
            _world, report = worlds.build(data, args.role)
        except (ValueError, KeyError, TypeError, worlds.WorldRefused) as error:
            print(f"{industry}: refused: {str(error)[:300]}", flush=True)
            with lock:
                state["refused"] += 1
            return
        (args.out / f"{stem}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
        print(f"{industry}: kept {report.accounts_kept} accounts, {report.oblique_kept} oblique phrases "
              f"(dropped {len(report.accounts_dropped)} accounts, {report.oblique_dropped} oblique, "
              f"{report.plain_dropped} plain)", flush=True)
        with lock:
            state["ok"] += 1

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, enumerate(industries)))
    line = (f"{time.strftime('%Y-%m-%d %H:%M')} author_worlds role={args.role} model={args.model} "
            f"worlds_ok={state['ok']} refused={state['refused']} skipped={state['skipped']} "
            f"usd={state['usd']:.2f}")
    print(line)
    if args.spend_log:
        with args.spend_log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
