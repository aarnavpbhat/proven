# Fine-tuning a local proposer

Everything here lives outside the `proven/` package, which stays standard-library only.
Results, the leakage argument and the limits are in [`docs/finetune.md`](../docs/finetune.md).

| File | What it is |
|---|---|
| `build_dataset.py` | writes `train.jsonl` / `valid.jsonl` / `manifest.json` from train-split seeds only |
| `test_leakage.py` | asserts no test seed, HELDOUT phrase, PARAPHRASE_TEST phrase or test explanation is in the data, and that the prompt is the one `openweight.py` sends |
| `lora-config.yaml` | the `mlx_lm.lora` settings (LoRA rank 16 on 16 layers, lr 1e-4 cosine, batch 4, prompt masked) |
| `train.sh` | one training run; refuses to start while the GPU lock file exists |
| `serve.sh` | `mlx_lm.server` (+adapter) behind `mlx_proxy.py` on loopback |
| `mlx_proxy.py` | rewrites the request's `model` to `default_model` (mlx_lm.server would otherwise try to download a repo by that name) and logs latency and tokens |
| `by_cause.py` | teach-sim split by cause, for the held-out-cause ablation |

## Setup (once)

```sh
FT=/path/to/scratch/finetune                 # anywhere outside the repo
uv venv --python 3.12 $FT/venv
VIRTUAL_ENV=$FT/venv uv pip install mlx-lm   # 0.32.2 was used
export MLX_PY=$FT/venv/bin/python HF_HOME=$FT/hf
$FT/venv/bin/hf download mlx-community/Qwen2.5-3B-Instruct-4bit
PY=/path/to/proven/.venv/bin/python          # the project's own python (stdlib + pytest)
```

## Build the data and check it

```sh
$PY training/build_dataset.py --out $FT/data/full                            # 500 seen + 500 paraphrase(train) + 60 valid
$PY training/build_dataset.py --out $FT/data/ablation --exclude-keys ablation   # same, minus 4 causes
PROVEN_TRAINING_DATA=$FT/data/full:$FT/data/ablation $PY -m pytest training -q
```

## Train

```sh
training/train.sh mlx-community/Qwen2.5-3B-Instruct-4bit $FT/data/full     $FT/adapters/qwen3b-r1     250
training/train.sh mlx-community/Qwen2.5-3B-Instruct-4bit $FT/data/ablation $FT/adapters/qwen3b-ablate 250
```

## Serve and measure (the harness is unchanged)

```sh
training/serve.sh mlx-community/Qwen2.5-3B-Instruct-4bit 8090 $FT/adapters/qwen3b-r1 $FT/logs/req-r1.jsonl &
training/serve.sh mlx-community/Qwen2.5-3B-Instruct-4bit 8091 "" $FT/logs/req-base.jsonl &   # base, no adapter

export PROVEN_CACHE_DIR=/path/to/proven/.proven/cache PROVEN_ENV_FILE=/dev/null
export PROVEN_OPENAI_BASE_URL=http://127.0.0.1:8090/v1 M=proven-qwen2.5-3b-lora-r1
for P in heldout paraphrase; do
  $PY -m proven benchmark --extractor openweight --model $M --phrasing $P --n 110 --workers 4
  $PY -m proven teach-sim --extractor openweight --model $M --phrasing $P --n 220
done
$PY training/by_cause.py --model $M --phrasing heldout --n 220
```

Use the same commands with `PROVEN_OPENAI_BASE_URL=http://127.0.0.1:8091/v1` and
`M=proven-qwen2.5-3b-base` for the base model. The model name only keys Proven's proposal
cache; which weights answer is decided by the server on that port, so keep one name per
(base model, adapter) pair.

## Demo

```sh
training/serve.sh mlx-community/Qwen2.5-3B-Instruct-4bit 8090 $FT/adapters/qwen3b-r1
PROVEN_OPENAI_BASE_URL=http://127.0.0.1:8090/v1 PROVEN_OPENAI_MODEL=proven-qwen2.5-3b-lora-r1 \
  $PY -m proven serve       # pick the openweight extractor in the console
```
