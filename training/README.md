# Fine-tuning a local proposer

Everything here lives outside the `proven/` package, which stays standard-library only.
Results, the leakage argument, the negative finding from the ablation and the limits are in
[`docs/finetune.md`](../docs/finetune.md). Read that first: the single-world model below
largely memorised one world's vocabulary, and on the unseen-worlds suites, the comparison that
counts, the fine-tuned models lose to Claude Sonnet by a wide margin.

| File | What it is |
|---|---|
| `build_dataset.py` | writes `train.jsonl` / `valid.jsonl` / `manifest.json` from train-split seeds of the default world only; `--exclude-keys` builds the ablation set |
| `build_worlds_dataset.py` | the multi-world set: closes from every world under `worlds/train`, some default-world rows, validation from `worlds/dev`; drops any close that reuses a measured world's phrase word for word. `--teacher` rebuilds each claim's search terms as "guessable and true" |
| `teacher_terms.py` | a hosted model guesses search terms for every training-world phrase from the account names and the reason alone (network, spends money, budget-capped) |
| `test_targets.py` | the target rules: true teacher guesses first, no vendor-only word, no routine or account word |
| `test_leakage.py` | asserts no test seed, HELDOUT phrase, PARAPHRASE_TEST phrase or test explanation is in the data, and that the prompt is the one `openweight.py` sends |
| `lora-config.yaml` | the `mlx_lm.lora` settings (LoRA rank 16 on 16 layers, lr 1e-4 cosine, batch 2 with gradient accumulation 2, prompt masked) |
| `train.sh` | one training run under `memguard.py`; refuses to start while the lock named by `GPU_LOCK` exists |
| `memguard.py` | caps MLX memory and ends the job when free memory stays under a floor, so a 24 GB laptop fails instead of rebooting |
| `serve.sh` | `mlx_lm.server` (+adapter) behind `mlx_proxy.py` on loopback |
| `mlx_proxy.py` | rewrites the request's `model` to `default_model` (mlx_lm.server would otherwise try to download a repo by that name) and logs latency and tokens |
| `test_proxy.py` | the proxy's optional base-model repair wraps only bare claim objects |
| `latency.py` | summarises a request log written by `mlx_proxy.py` |
| `eval.sh` | benchmark, teach-sim and `by_cause.py` for one served proposer, both phrasing tiers |
| `by_cause.py` | teach-sim split by cause, for the held-out-cause ablation |
| `author_worlds.py` | asks a hosted model for one world file per industry and keeps the ones `proven/worlds.py` validates (network, spends money, budget-capped) |
| `industries-*.txt` | the industry lists: `train-a`, `train-b`, `train-c`, `dev`, and the disjoint `unseen` and `sealed` |
| `worlds/train`, `worlds/dev` | 147 training worlds and 4 dev worlds (every result in `docs/finetune.md` up to section 8b used the first 91; the 56 from `industries-train-d.txt` were added afterwards); the measured worlds live in `proven/examples/worlds/unseen/` (11) and `sealed/` (9) |
| `world_overlap.py` | audit of the vocabulary the measured worlds share with the training worlds |
| `warm_worlds.py` | fills the proposal cache for a world suite through a served or hosted proposer, several closes at a time |
| `batch_propose.py` | fills the same cache for a local MLX proposer in batches, without a server; `--taught-only`, `--constrain`, `--samples K` |
| `constrain.py`, `test_constrain.py` | constrained decoding: a byte-level automaton and a vocabulary-trie mask that make every reply admissible by construction |
| `consensus.py`, `repool.py` | pooling several sampled replies by a ledger-blind vote, and re-pooling saved samples offline |
| `hit_rate.py` | how often a cached proposer's blind terms find a true cause (what checkpoints and policies are compared on, dev worlds only) |
| `build_terms_dataset.py`, `two_stage.py` | a terms-only training set (one stated reason in, search terms out), and a proposer made of a copy model plus that term model |
| `breadth_cost.py` | what a wider term list costs: wrong claims a reviewer is shown as supported |
| `term_probe.py` | the same question for an untuned model asked for terms only: a way to choose a base model before training it |
| `lora_clip.py` | `mlx_lm.lora` with the gradient norm clipped (written for the 7B attempt) |
| `recall_experiment.py` | a rejected experiment: re-offering an account's confirmed words to the proposer (breaks the kill criteria with a weak proposer) |
| `compare_worlds.py` | one head-to-head table, with a per-world bootstrap interval, from the JSON files `teach-sim --worlds --json` writes |
| `reward.py` | the reward one reply earns on one close (the RL environment); standard library plus `proven` |
| `rl.py` | RLOO policy-gradient fine-tuning against that reward; implemented, no result claimed |

Run exactly one GPU job at a time, and keep scratch outside the repo and outside `/tmp`.

## Setup (once)

```sh
FT=/path/to/scratch/finetune                 # anywhere outside the repo
uv venv --python 3.12 $FT/venv
VIRTUAL_ENV=$FT/venv uv pip install mlx-lm   # 0.32.2 was used
export MLX_PY=$FT/venv/bin/python HF_HOME=$FT/hf
$FT/venv/bin/hf download mlx-community/Qwen2.5-3B-Instruct-4bit
PY=/path/to/proven/.venv/bin/python          # the project's own python (stdlib + pytest)
BASE=mlx-community/Qwen2.5-3B-Instruct-4bit
```

## Build the data and check it

```sh
$PY training/build_dataset.py --out $FT/data/full                            # 500 seen + 500 paraphrase(train) + 60 valid
$PY training/build_dataset.py --out $FT/data/ablation --exclude-keys litigation,migration,offsite,d_and_o
PROVEN_TRAINING_DATA=$FT/data/full:$FT/data/ablation $PY -m pytest training -q
```

## Train (single world, 500 iterations)

```sh
training/train.sh $BASE $FT/data/full     $FT/adapters/qwen3b-sft      500
training/train.sh $BASE $FT/data/ablation $FT/adapters/qwen3b-ablation 500
```

## Serve and measure (the harness is unchanged)

`serve.sh` takes `<hf-model> <port> <name> [<adapter-dir>] [<request-log>]`. The name only
keys Proven's proposal cache and is what the proxy reports on `/v1/models`; which weights
answer is decided by the server on that port, so keep one name per (base model, adapter) pair.

```sh
export PROVEN_CACHE_DIR=/path/to/proven/.proven/cache PROVEN_ENV_FILE=/dev/null
training/serve.sh $BASE 8090 proven-qwen3b-sft $FT/adapters/qwen3b-sft $FT/logs/req-proven-qwen3b-sft.jsonl &
training/eval.sh 8090 proven-qwen3b-sft $FT/results
```

`eval.sh` runs, per phrasing (heldout, paraphrase), `benchmark --n 110`, `teach-sim --n 220`
and `by_cause.py --n 220`, and writes `bench-`, `teach-` and `cause-<name>-<phrasing>` files.
Stop the server, then repeat with `proven-qwen3b-ablation` and its adapter, and with
`proven-qwen3b-base` and `""` as the adapter for the untuned model.

## Other worlds

```sh
$PY training/author_worlds.py --role train --model claude-sonnet-5-5 \
    --industries training/industries-train-a.txt --out training/worlds/train --usd-budget 8
$PY training/teacher_terms.py --worlds training/worlds/train training/worlds/dev --out $FT/teacher \
    --usd-budget 14                                                       # $10.14 when run
$PY training/build_worlds_dataset.py --out $FT/data/worlds2 --worlds training/worlds/train \
    --dev training/worlds/dev --per-world 34 --default 100 --valid 60 --teacher $FT/teacher   # 3,176 train rows
$PY training/world_overlap.py --train training/worlds/train training/worlds/dev
training/train.sh $BASE $FT/data/worlds2 $FT/adapters/qwen3b-worlds2 1200
```

The first multi-world adapter (`qwen3b-worlds`, gold targets, started from the single-world
adapter) and the second (`qwen3b-worlds2`, rebuilt targets, started from the base model) are
both reported. The measurement commands (`batch_propose.py --taught-only`, then
`teach-sim --worlds unseen|sealed`, `hit_rate.py`, `compare_worlds.py`) are in
[`docs/finetune.md`](../docs/finetune.md#how-to-reproduce).

## Demo

```sh
training/serve.sh $BASE 8090 proven-qwen3b-sft $FT/adapters/qwen3b-sft
PROVEN_OPENAI_BASE_URL=http://127.0.0.1:8090/v1 PROVEN_OPENAI_MODEL=proven-qwen3b-sft \
  $PY -m proven serve       # pick the openweight extractor in the console
```
