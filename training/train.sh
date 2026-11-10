#!/usr/bin/env bash
# Train one LoRA adapter with mlx_lm.lora.
#
#   MLX_PY=<venv>/bin/python training/train.sh <hf-model> <data-dir> <adapter-dir> <iters>
#
# Writes <adapter-dir>/run-config.yaml (training/lora-config.yaml with iters and the cosine
# decay length set to <iters>), <adapter-dir>/train.log, and the adapter itself. Refuses to
# start while the shared GPU lock file exists.
set -euo pipefail
MODEL=$1; DATA=$2; ADAPTER=$3; ITERS=$4
MLX_PY=${MLX_PY:?set MLX_PY to the mlx-lm venv python}
LOCK=${GPU_LOCK:-}
if [[ -n "$LOCK" && -e "$LOCK" ]]; then echo "GPU lock $LOCK exists; not training" >&2; exit 2; fi
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$ADAPTER"
"$MLX_PY" -I - "$HERE/lora-config.yaml" "$ADAPTER/run-config.yaml" "$ITERS" <<'EOF'
import sys, yaml
src, dst, iters = sys.argv[1], sys.argv[2], int(sys.argv[3])
config = yaml.safe_load(open(src))
config["iters"] = iters
config["lr_schedule"]["arguments"][1] = iters
yaml.safe_dump(config, open(dst, "w"), sort_keys=False)
EOF
start=$(date +%s)
/usr/bin/time -l "$MLX_PY" "$HERE/memguard.py" mlx_lm.lora --config "$ADAPTER/run-config.yaml" \
    --model "$MODEL" --data "$DATA" --adapter-path "$ADAPTER" 2>&1 | tee "$ADAPTER/train.log"
echo "wall_seconds=$(( $(date +%s) - start ))" | tee -a "$ADAPTER/train.log"
