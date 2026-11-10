"""Policy-gradient fine-tuning of a local proposer against the checker's own reward.

    $MLX_PY training/rl.py --model mlx-community/Qwen2.5-3B-Instruct-4bit \
        --init <sft-adapter-dir> --out <rl-adapter-dir> --steps 150 --samples 4 \
        --worlds training/worlds/train --dev-worlds training/worlds/dev

The policy is the base model plus a LoRA adapter (normally the supervised one). An episode
is one TRAIN-split close in paraphrase wording (`reward.episode` refuses test seeds): the
prompt is exactly the request `proven.openweight` sends, the action is the whole sampled
JSON reply, and the reward is `reward.score_reply` -- what the deterministic checker and a
simulated reviewer do with that reply. No gold token enters the loss; the gold reply's
REWARD is used for one thing, deciding whether a close is worth sampling (below).

WORLDS

Without `--worlds` every close comes from the default world, as before. With it, the close
at screening position c comes from world `order[c % n]`, where `order` is a permutation of
the directory's worlds fixed by `--seed` (`reward.pick_world`): round-robin, so no world is
over-drawn and a run can be reproduced. Validation closes are dealt over `--dev-worlds`
(close i from world i % n; without `--dev-worlds` they come from the default world).
`reward.load_worlds` refuses the measured suites under `proven/examples/worlds/`, and in
worlds mode a close that states a measured world's phrase word for word is passed over, as
`build_worlds_dataset.py` does. Worlds mode draws seeds from index 6000 of the train split,
clear of that builder's (4000 to about 4520); the default world keeps 2000.

THE UPDATE (RLOO: REINFORCE with a leave-one-out baseline)

For a close worth training on, K replies are sampled at temperature T and the greedy reply
is added as one more rollout. Reply i's advantage is its reward minus the mean reward of
the other replies to the same close, so a close on which every reply scores the same
contributes no gradient. The step is plain SGD on a norm-clipped gradient. The loss for a
close is

    -(1/(K+1)) * sum_i  advantage_i * mean_t log pi(token_t | prompt, tokens_<t)

computed on the sampled tokens (and the end-of-turn token) only. At least `--batch` closes
with a gradient are accumulated per optimizer step (a probe group can yield one or two
more; they are used, and the gradient is the mean over closes).

WHERE THE TIME WENT, AND WHAT CHANGED

The first run (3B model, --batch 2 --samples 4 --screen 8 --max-tokens 700) took about
nine minutes a step. Its log shows 13 to 24 closes per step sampled and thrown away
because all five rewards were equal: about 34 generation calls for two closes of gradient.
Generation time is set by the number of calls and their longest reply, far more than by
rows per call, and the reward itself is 10 to 20 ms a reply (CPU), so the fixes are all
about making fewer, shorter calls:

  1. Headroom screen. "Greedy reward under 0.95" marked four closes in ten as hard, but
     the generator's own gold reply scores under 0.95 on four closes in ten too (a correct
     sentence the checker leaves in REVIEW scores 0 whatever is proposed). Those closes
     have nothing to learn and were the bulk of the waste. A close is now trained on only
     if the greedy reply the screen already produced scores at least `--headroom` under
     the gold reply's reward (`reward.ceiling`, about 20 ms of CPU per close against
     ~15 s per wasted generation call). `--headroom -1` restores the plain threshold.
  2. Probe, then commit. `--probe` (2) replies are sampled first; if every one scores
     exactly what the greedy reply scores, the close is dropped (`reward.worth_sampling`)
     and the other K-2 replies are never generated.
  3. Probes share a call. Up to `--probe-closes` (4) closes are probed in ONE generation
     call (4 x 2 = 8 rows, the width screening already uses), and the remaining K-2
     replies of the closes that survive share calls too. The old loop made one call per
     close.
  4. `--max-tokens` 448, not 700. The gold reply is about 250 tokens and at most about 330
     over 700 closes in the default, training and dev worlds (JSON length / 4), so 448
     leaves a third to spare; a call runs until its longest row stops, so one rambling
     sample at T=1 used to hold a whole call for 700 tokens. Replies cut off at the limit
     are counted (`truncated`) in step and eval rows: if evals show any, raise it.
  5. Replies whose advantage is exactly zero are not pushed through the model.

The greedy screening reply is still the extra rollout, so screening costs nothing extra
for a close that is trained on. Each step row logs `sec_screen`, `sec_sample` and
`sec_grad`, plus calls and closes at each stage, so the next run shows where time goes.

EVALUATION

Every `--eval-every` steps the greedy reply is scored on `--valid` train-split closes that
are never trained on (different seeds; with `--dev-worlds`, worlds no episode comes from);
the adapter with the best validation reward is the one written to `--out`, and
`rl-config.json` records `best_step`. The log (`rl-log.jsonl`) has one line per step and
per evaluation.

Seeds: episodes are drawn from train seeds after the ones `build_dataset.py` uses for the
supervised set, so RL sees closes the supervised stage did not.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import mlx.core as mx  # noqa: E402
import mlx.nn as nn  # noqa: E402
import mlx.optimizers as optim  # noqa: E402
from mlx.utils import tree_flatten, tree_map  # noqa: E402
from mlx_lm import load  # noqa: E402
from mlx_lm.generate import batch_generate  # noqa: E402
from mlx_lm.sample_utils import make_sampler  # noqa: E402
from mlx_lm.tuner.utils import load_adapters  # noqa: E402

from proven.llm import SYSTEM, payload  # noqa: E402
from proven.synth import seeds  # noqa: E402
import reward as env  # noqa: E402
from reward import score_reply  # noqa: E402
import memguard  # noqa: E402

FIRST_RL_SEED_INDEX = 2000      # build_dataset.py uses the first ~1,100 train seeds
FIRST_WORLD_RL_SEED_INDEX = 6000   # build_worlds_dataset.py uses 4000 to about 4520


def prompt_ids(tokenizer, scenario) -> list[int]:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": payload(scenario.explanation, scenario.ledger)}]
    return tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)


def sample(model, tokenizer, prompts: list[list[int]], temp: float, max_tokens: int):
    sampler = make_sampler(temp=temp) if temp > 0 else None
    kwargs = {"sampler": sampler} if sampler else {}
    out = batch_generate(model, tokenizer, prompts, max_tokens=max_tokens,
                         return_token_ids=True, **kwargs)
    return out.texts, out.token_ids


def rloo_loss(model, batch, starts, ends, weights):
    """batch: (K, L) token ids; reply tokens are positions [start, end) of each row."""
    inputs, targets = batch[:, :-1], batch[:, 1:]
    logits = model(inputs)
    steps = mx.arange(1, targets.shape[1] + 1)
    mask = mx.logical_and(steps >= starts[:, None], steps < ends[:, None])
    logp = -nn.losses.cross_entropy(logits, targets).astype(mx.float32) * mask
    per_reply = logp.sum(axis=1) / mx.maximum(mask.sum(axis=1), 1)
    return -(weights * per_reply).mean()


def evaluate(model, tokenizer, scenarios, max_tokens: int, chunk: int = 8) -> dict:
    model.eval()
    outs, truncated = [], 0
    for i in range(0, len(scenarios), chunk):
        part = scenarios[i:i + chunk]
        texts, tokens = sample(model, tokenizer, [prompt_ids(tokenizer, s) for s in part], 0.0, max_tokens)
        outs += [score_reply(s, t) for s, t in zip(part, texts)]
        truncated += sum(len(t) >= max_tokens for t in tokens)
    n = len(outs)
    labels = sum(o.labels for o in outs)
    return {"reward": round(sum(o.reward for o in outs) / n, 4),
            "parsed": sum(o.parsed for o in outs), "closes": n,
            "rules_decided_share": round(sum(o.rules_decided for o in outs) / labels, 4),
            "model_decided_share": round(sum(o.model_decided for o in outs) / labels, 4),
            "lessons": sum(o.lessons for o in outs), "unsafe": sum(o.unsafe for o in outs),
            "control_fails": sum(o.control_fails for o in outs),
            "traps": sum(o.traps for o in outs), "truncated": truncated}


def save_adapter(model, init: Path, out: Path, extra: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    weights = {k: v for k, v in tree_flatten(model.trainable_parameters())}
    mx.save_safetensors(str(out / "adapters.safetensors"), weights)
    shutil.copy(init / "adapter_config.json", out / "adapter_config.json")
    (out / "rl-config.json").write_text(json.dumps(extra, indent=1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("--init", required=True, type=Path, help="adapter to start from (mlx_lm format)")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--steps", type=int, default=150, help="optimizer steps")
    p.add_argument("--batch", type=int, default=2, help="closes per optimizer step")
    p.add_argument("--samples", type=int, default=4, help="sampled replies per close (K)")
    p.add_argument("--temp", type=float, default=0.8)
    p.add_argument("--lr", type=float, default=0.5, help="SGD step on the clipped gradient")
    p.add_argument("--clip", type=float, default=0.02, help="gradient-norm ceiling")
    p.add_argument("--screen", type=int, default=8, help="closes screened greedily at a time")
    p.add_argument("--hard-below", type=float, default=0.95,
                   help="a close is trained on only if the greedy reply scores below this")
    p.add_argument("--headroom", type=float, default=0.02,
                   help="and only if it scores at least this far under the gold reply's reward "
                        "(negative: do not look at the gold reward)")
    p.add_argument("--probe", type=int, default=2,
                   help="replies sampled before deciding whether a close gets all --samples")
    p.add_argument("--probe-closes", type=int, default=4, help="closes probed in one generation call")
    p.add_argument("--max-tokens", type=int, default=448)
    p.add_argument("--worlds", type=Path, default=None,
                   help="directory of training worlds; episodes go round them in a seeded order")
    p.add_argument("--dev-worlds", type=Path, default=None,
                   help="directory of dev worlds; validation closes are dealt evenly over them")
    p.add_argument("--valid", type=int, default=48)
    p.add_argument("--eval-every", type=int, default=25)
    p.add_argument("--phrasing", default="paraphrase")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--eval-only", action="store_true")
    args = p.parse_args(argv)

    memguard.install()
    mx.random.seed(args.seed)
    rng = random.Random(args.seed)
    model, tokenizer = load(args.model)
    model.freeze()
    load_adapters(model, str(args.init))
    eos = tokenizer.eos_token_ids
    eos = {eos} if isinstance(eos, int) else set(eos)
    turn_end = tokenizer.convert_tokens_to_ids("<|im_end|>")
    end_token = turn_end if turn_end in eos else next(iter(eos))

    train_worlds = env.load_worlds(args.worlds) if args.worlds else None
    dev_worlds = env.load_worlds(args.dev_worlds) if args.dev_worlds else None
    in_worlds = bool(train_worlds or dev_worlds)
    measured = env.measured_phrases() if in_worlds else frozenset()
    first = FIRST_WORLD_RL_SEED_INDEX if in_worlds else FIRST_RL_SEED_INDEX
    train_seeds = seeds("train", first + 20000)[first:]
    valid, taken = env.validation_closes(train_seeds, args.valid, args.phrasing, dev_worlds, measured)
    pool = train_seeds[taken:]
    args.out.mkdir(parents=True, exist_ok=True)
    log = (args.out / "rl-log.jsonl").open("a", encoding="utf-8")

    def emit(row: dict) -> None:
        log.write(json.dumps(row) + "\n")
        log.flush()
        print(json.dumps(row), flush=True)

    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    config["train_worlds"] = len(train_worlds or [])
    config["valid_worlds"] = sorted({s.world for s in valid})
    start = time.time()
    base = evaluate(model, tokenizer, valid, args.max_tokens)
    emit({"event": "eval", "step": 0, "seconds": round(time.time() - start), **base})
    if args.eval_only:
        return 0
    best = base["reward"]
    save_adapter(model, args.init, args.out, {**config, "best_step": 0, "best_valid": base})

    # Plain SGD on a norm-clipped gradient. Adam is wrong here: the supervised policy is so
    # peaked that the gradient is tiny, and Adam rescales it to a full-size step in every
    # one of 13M adapter weights (two such steps left the model unable to write JSON).
    optimizer = optim.SGD(learning_rate=args.lr)
    grad_fn = nn.value_and_grad(model, rloo_loss)
    cursor, hard_seen, greedy_sum, greedy_n = 0, 0, 0.0, 0
    queue: list = []                      # closes the greedy reply leaves headroom on
    probe = max(1, min(args.probe, args.samples))
    rows_per_call = max(args.screen, 1)   # the widest generation call the run makes

    def sample_closes(group: list, count: int) -> tuple[list[list], int]:
        """`count` sampled replies for every close in `group`, as few calls as fit:
        ([(reward, tokens), ...] per close, calls made)."""
        jobs = [g for g, _close in enumerate(group) for _ in range(count)]
        got: list[list] = [[] for _ in group]
        calls = 0
        for i in range(0, len(jobs), rows_per_call):
            part = jobs[i:i + rows_per_call]
            texts, tokens = sample(model, tokenizer, [group[g]["ids"] for g in part],
                                   args.temp, args.max_tokens)
            calls += 1
            for g, text, t in zip(part, texts, tokens):
                got[g].append((score_reply(group[g]["scenario"], text).reward, list(t)))
        return got, calls

    for step in range(1, args.steps + 1):
        grads, used, rewards, skipped, norm = None, 0, [], 0, 0.0
        sec = {"screen": 0.0, "sample": 0.0, "grad": 0.0}
        count = {"screened": 0, "calls": 0, "probed": 0, "truncated": 0}
        while used < args.batch:
            clock = time.time()
            while not queue:              # screen fresh closes with the greedy reply
                part = [s for s in (env.training_episode(pool, cursor + j, args.phrasing, train_worlds,
                                                         args.seed, measured)
                                    for j in range(args.screen)) if s is not None]
                cursor += args.screen
                if not part:
                    continue
                model.eval()
                prompts = [prompt_ids(tokenizer, s) for s in part]
                texts, tokens = sample(model, tokenizer, prompts, 0.0, args.max_tokens)
                count["calls"] += 1
                count["screened"] += len(part)
                for s, ids, text, t in zip(part, prompts, texts, tokens):
                    r = score_reply(s, text).reward
                    greedy_sum, greedy_n = greedy_sum + r, greedy_n + 1
                    top = env.ceiling(s) if args.headroom >= 0 and r < args.hard_below else None
                    if env.has_headroom(r, top, args.hard_below, max(args.headroom, 0.0)):
                        queue.append({"scenario": s, "ids": list(ids), "greedy": (r, list(t))})
            sec["screen"] += time.time() - clock

            clock = time.time()
            group, queue = queue[:args.probe_closes], queue[args.probe_closes:]
            hard_seen += len(group)
            count["probed"] += len(group)
            model.eval()
            sampled, calls = sample_closes(group, probe)      # one call for the whole group
            count["calls"] += calls
            kept = []
            for close, replies in zip(group, sampled):
                close["replies"] = [close["greedy"]] + replies
                if env.worth_sampling(close["greedy"][0], [r for r, _t in replies]):
                    kept.append(close)
                else:                     # every probe scored what the greedy reply scores
                    skipped += 1
                    rewards += [r for r, _t in close["replies"]]
            if kept and args.samples > probe:
                more, calls = sample_closes(kept, args.samples - probe)
                count["calls"] += calls
                for close, replies in zip(kept, more):
                    close["replies"] += replies
            sec["sample"] += time.time() - clock

            clock = time.time()
            for close in kept:
                ids = close["ids"]
                rs = [r for r, _t in close["replies"]]
                tokens = [t for _r, t in close["replies"]]
                rewards += rs
                count["truncated"] += sum(len(t) >= args.max_tokens for t in tokens)
                if not env.has_signal(rs):
                    skipped += 1
                    continue
                k = len(rs)
                adv = env.loo_advantages(rs)
                # a reply cut off at the token limit did not choose to stop: no end token for it
                rows = [ids + t + ([end_token] if len(t) < args.max_tokens else []) for t in tokens]
                model.train()
                for index in env.gradient_rows(adv, 2):   # two replies at a time keeps memory flat
                    part_rows = [rows[i] for i in index]
                    width = max(len(r) for r in part_rows)
                    batch = mx.array([r + [end_token] * (width - len(r)) for r in part_rows])
                    starts = mx.array([len(ids)] * len(part_rows))
                    ends = mx.array([len(r) for r in part_rows])
                    weights = mx.array([adv[i] for i in index]) * (len(part_rows) / k)
                    _, g = grad_fn(model, batch, starts, ends, weights)
                    grads = g if grads is None else tree_map(lambda a, b: a + b, grads, g)
                    mx.eval(grads)
                used += 1
            sec["grad"] += time.time() - clock
        if grads is not None:
            grads = tree_map(lambda a: a / used, grads)
            grads, norm = optim.clip_grad_norm(grads, args.clip)
            optimizer.update(model, grads)
            mx.eval(model.parameters(), optimizer.state)
        emit({"event": "step", "step": step, "closes_screened": cursor, "hard_closes": hard_seen,
              "greedy_reward_so_far": round(greedy_sum / max(greedy_n, 1), 4),
              "skipped": skipped, "mean_sample_reward": round(sum(rewards) / len(rewards), 4),
              "grad_norm": round(float(norm), 5), "seconds": round(time.time() - start),
              "closes_used": used, "screened": count["screened"], "probed": count["probed"],
              "generation_calls": count["calls"], "truncated": count["truncated"],
              "sec_screen": round(sec["screen"], 1), "sec_sample": round(sec["sample"], 1),
              "sec_grad": round(sec["grad"], 1)})
        mx.clear_cache()
        if step % args.eval_every == 0 or step == args.steps:
            result = evaluate(model, tokenizer, valid, args.max_tokens)
            emit({"event": "eval", "step": step, "seconds": round(time.time() - start), **result})
            if result["reward"] > best:
                best = result["reward"]
                save_adapter(model, args.init, args.out,
                             {**config, "best_step": step, "best_valid": result})
    emit({"event": "done", "best_valid_reward": best, "seconds": round(time.time() - start)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
