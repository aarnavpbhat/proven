"""Policy-gradient fine-tuning of a local proposer against the checker's own reward.

    $MLX_PY training/rl.py --model mlx-community/Qwen2.5-3B-Instruct-4bit \
        --init <sft-adapter-dir> --out <rl-adapter-dir> --steps 150 --samples 4

The policy is the base model plus a LoRA adapter (normally the supervised one). An episode
is one TRAIN-split close in paraphrase wording (`reward.episode` refuses test seeds): the
prompt is exactly the request `proven.openweight` sends, the action is the whole sampled
JSON reply, and the reward is `reward.score_reply` -- what the deterministic checker and a
simulated reviewer do with that reply. Nothing here reads a gold proposal.

THE UPDATE (RLOO: REINFORCE with a leave-one-out baseline)

For each close, K replies are sampled at temperature T. Reply i's advantage is its reward
minus the mean reward of the other K-1 replies to the same close, so a close on which every
sample scores the same contributes no gradient (and is skipped). The loss for a close is

    -(1/K) * sum_i  advantage_i * mean_t log pi(token_t | prompt, tokens_<t)

computed on the sampled tokens (and the end-of-turn token) only. `--batch` closes are
accumulated per optimizer step.

EVALUATION

Every `--eval-every` steps the greedy reply is scored on `--valid` train-split closes that
are never trained on (different seeds); the adapter with the best validation reward is the
one written to `--out`. The log (`rl-log.jsonl`) has one line per step and per evaluation.

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
from reward import episode, score_reply  # noqa: E402
import memguard  # noqa: E402

FIRST_RL_SEED_INDEX = 2000      # build_dataset.py uses the first ~1,100 train seeds


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
    outs = []
    for i in range(0, len(scenarios), chunk):
        part = scenarios[i:i + chunk]
        texts, _ = sample(model, tokenizer, [prompt_ids(tokenizer, s) for s in part], 0.0, max_tokens)
        outs += [score_reply(s, t) for s, t in zip(part, texts)]
    n = len(outs)
    labels = sum(o.labels for o in outs)
    return {"reward": round(sum(o.reward for o in outs) / n, 4),
            "parsed": sum(o.parsed for o in outs), "closes": n,
            "rules_decided_share": round(sum(o.rules_decided for o in outs) / labels, 4),
            "model_decided_share": round(sum(o.model_decided for o in outs) / labels, 4),
            "lessons": sum(o.lessons for o in outs), "unsafe": sum(o.unsafe for o in outs),
            "control_fails": sum(o.control_fails for o in outs),
            "traps": sum(o.traps for o in outs)}


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
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--max-tokens", type=int, default=700)
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
    end_token = next(iter(eos)) if not isinstance(eos, int) else eos

    train_seeds = seeds("train", FIRST_RL_SEED_INDEX + 20000)[FIRST_RL_SEED_INDEX:]
    valid = [episode(s, args.phrasing) for s in train_seeds[:args.valid]]
    pool = train_seeds[args.valid:]
    args.out.mkdir(parents=True, exist_ok=True)
    log = (args.out / "rl-log.jsonl").open("a", encoding="utf-8")

    def emit(row: dict) -> None:
        log.write(json.dumps(row) + "\n")
        log.flush()
        print(json.dumps(row), flush=True)

    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    start = time.time()
    base = evaluate(model, tokenizer, valid, args.max_tokens)
    emit({"event": "eval", "step": 0, "seconds": round(time.time() - start), **base})
    if args.eval_only:
        return 0
    best = base["reward"]
    save_adapter(model, args.init, args.out, {**config, "best_step": 0, "best_valid": base})

    optimizer = optim.Adam(learning_rate=args.lr)
    grad_fn = nn.value_and_grad(model, rloo_loss)
    cursor = 0
    for step in range(1, args.steps + 1):
        grads, used, rewards, skipped = None, 0, [], 0
        while used < args.batch:
            scenario = episode(pool[cursor % len(pool)], args.phrasing)
            cursor += 1
            ids = prompt_ids(tokenizer, scenario)
            model.eval()
            texts, tokens = sample(model, tokenizer, [ids] * args.samples, args.temp, args.max_tokens)
            rs = [score_reply(scenario, t).reward for t in texts]
            rewards += rs
            if max(rs) - min(rs) < 1e-6:
                skipped += 1
                if skipped >= 12:       # the policy is consistent here; move on
                    break
                continue
            k = len(rs)
            adv = [r - (sum(rs) - r) / (k - 1) for r in rs]
            rows = [ids + list(t) + [end_token] for t in tokens]
            width = max(len(r) for r in rows)
            batch = mx.array([r + [end_token] * (width - len(r)) for r in rows])
            starts = mx.array([len(ids)] * k)
            ends = mx.array([len(r) for r in rows])
            model.train()
            _, g = grad_fn(model, batch, starts, ends, mx.array(adv))
            grads = g if grads is None else tree_map(lambda a, b: a + b, grads, g)
            mx.eval(grads)
            used += 1
        if grads is not None:
            grads = tree_map(lambda a: a / used, grads)
            optimizer.update(model, grads)
            mx.eval(model.parameters(), optimizer.state)
        emit({"event": "step", "step": step, "closes_seen": cursor, "updated_on": used,
              "skipped": skipped, "mean_sample_reward": round(sum(rewards) / len(rewards), 4),
              "seconds": round(time.time() - start)})
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
