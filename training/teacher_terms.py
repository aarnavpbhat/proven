"""Ask a hosted model to guess search terms, blind, for every cause phrase of the training worlds.

    python training/teacher_terms.py --worlds training/worlds/train --out <dir> \
        --model claude-sonnet-5-5 --usd-budget 20 --spend-log <file>

WHY. The generator's gold `search_terms` are the words a cause really left in the books,
vendor names included. Nothing in the request lets a proposer predict "Northgate" or
"Verity", so a model trained on those targets learns to emit ledger-looking words rather
than to reason from the sentence (docs/finetune.md, "What the first multi-world model got
wrong"). A teacher that sees exactly what the proposer sees (the account names and the
stated reason, never a transaction) gives terms that ARE predictable from the request.
`build_worlds_dataset.py --teacher` then keeps the teacher's terms that the cause's own
memos really contain ahead of the ones they do not: targets that are both guessable and true.

BLINDNESS. One request holds at most one phrase per cause, so the teacher cannot work out
a cause's book wording from a sibling phrase that uses it. It is shown account names and
reasons only. The measured suites are refused, as everywhere in training/.
"""
from __future__ import annotations

import argparse
import json
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

SYSTEM = "You propose ledger search terms. You answer with one JSON object and nothing else."

BRIEF = """A company's chart of operating-expense accounts:

{chart}

Below are reasons a controller gave for why an account's spending moved this month. For each, give 8 search terms: words or short phrases a bookkeeper would likely have typed in the vendor name or memo line of the transactions this particular cause produced: what the event, project or purchase is usually called, and the documents or services it involves. Memo lines rarely repeat a whole phrase, so give the key single words as well as phrases (for "the warehouse relocation": "relocation", "movers", "warehouse move", "freight"). Prefer the plain nouns a ledger would use over the controller's conversational wording. The terms must tell this cause's transactions apart from the account's routine, recurring spending: never the account's own name, and never what the account buys every month anyway. Do not invent vendor or company names.

{items}

Return JSON of exactly this shape, one entry per numbered reason: {{"1": ["term", ...], "2": [...]}}"""


def phrases_of(world) -> dict[tuple[str, str], list[str]]:
    """(account, cause key) -> its oblique phrases, in file order."""
    out = {}
    for spec in world.specs:
        for event in spec.events:
            out[(spec.name, event.key)] = list(dict.fromkeys(world.paraphrase_train[event.key]))
    return out


def chunks(world) -> list[list[tuple[str, str]]]:
    """Requests for one world: each a list of (account, phrase) with one phrase per cause."""
    bank = phrases_of(world)
    depth = max(len(v) for v in bank.values())
    return [[(account, phrases[i]) for (account, _key), phrases in bank.items() if i < len(phrases)]
            for i in range(depth)]


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--worlds", required=True, type=Path, nargs="+")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--usd-budget", type=float, required=True)
    p.add_argument("--spend-log", type=Path, default=None)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit-worlds", type=int, default=0)
    args = p.parse_args(argv)

    files = []
    for folder in args.worlds:
        if worlds.HERE.resolve() in folder.resolve().parents or folder.resolve() == worlds.HERE.resolve():
            raise SystemExit(f"{folder} is a measured suite; it may not be trained on")
        files += sorted(folder.glob("*.json"))
    if args.limit_worlds:
        files = files[:args.limit_worlds]
    env.load()
    import anthropic
    client = anthropic.Anthropic()
    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    state = {"usd": 0.0, "sent": 0, "failed": 0, "skipped": 0}
    extra = ({"thinking": {"type": "between_tools"}} if "sonnet-5-5" in args.model
             else {"thinking": {"type": "disabled"}} if "haiku" in args.model else {})

    def one(job: tuple[str, int, list[str], list[tuple[str, str]]]) -> None:
        slug, index, chart, items = job
        raw_file = raw_dir / f"{slug}.{index:02d}.json"
        if raw_file.exists():
            return
        with lock:
            if state["usd"] >= args.usd_budget:
                state["skipped"] += 1
                return
        prompt = BRIEF.format(chart="\n".join(f"- {name}" for name in chart),
                              items="\n".join(f'{i + 1}. [{account}] "{phrase}"'
                                              for i, (account, phrase) in enumerate(items)))
        try:
            with client.beta.messages.stream(model=args.model, max_tokens=6000, system=SYSTEM,
                                             output_config={"effort": "low"}, **extra,
                                             messages=[{"role": "user", "content": prompt}]) as stream:
                reply = stream.get_final_message()
            text = "".join(b.text for b in reply.content if getattr(b, "type", "") == "text")
            _tokens, usd, _attempts = cost(args.model, reply.usage)
            with lock:
                state["usd"] += usd
                state["sent"] += 1
            data = extract_json(text)
            answers = {}
            for i, (account, phrase) in enumerate(items):
                terms = [re.sub(r"\s+", " ", str(t)).strip().lower() for t in data.get(str(i + 1), [])]
                answers[f"{account}\t{phrase}"] = [t for t in dict.fromkeys(terms) if t][:10]
            raw_file.write_text(json.dumps(answers, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as error:  # noqa: BLE001 - one request failing must not stop the rest
            print(f"{slug} #{index}: {type(error).__name__}: {str(error)[:160]}", flush=True)
            with lock:
                state["failed"] += 1

    jobs = []
    loaded = {}
    for file in files:
        world = worlds.load(file, role="train")
        loaded[file.stem] = world
        chart = [spec.name for spec in world.specs]
        jobs += [(file.stem, i, chart, items) for i, items in enumerate(chunks(world))]
    print(f"{len(files)} worlds, {len(jobs)} requests", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, jobs))
    labelled = 0
    for slug in loaded:
        merged: dict[str, list[str]] = {}
        for part in sorted(raw_dir.glob(f"{slug}.[0-9][0-9].json")):
            merged.update(json.loads(part.read_text(encoding="utf-8")))
        (args.out / f"{slug}.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8")
        labelled += len(merged)
    line = (f"{time.strftime('%Y-%m-%d %H:%M')} teacher_terms model={args.model} worlds={len(files)} "
            f"requests={state['sent']} failed={state['failed']} skipped={state['skipped']} "
            f"phrases={labelled} usd={state['usd']:.2f}")
    print(line)
    if args.spend_log:
        with args.spend_log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
