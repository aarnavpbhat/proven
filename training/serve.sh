#!/usr/bin/env bash
# Serve a base model, optionally with a LoRA adapter, on loopback for Proven's openweight
# extractor: mlx_lm.server on <port>+100, and training/mlx_proxy.py on <port>.
#
#   MLX_PY=<venv>/bin/python training/serve.sh <hf-model> <port> [<adapter-dir>] [<request-log>]
#
# Then: PROVEN_OPENAI_BASE_URL=http://127.0.0.1:<port>/v1 python -m proven ... --extractor openweight --model <name>
# Stop with: kill the two PIDs this prints (or Ctrl-C if run in the foreground).
set -euo pipefail
MODEL=$1; PORT=$2; ADAPTER=${3:-}; LOG=${4:-}
MLX_PY=${MLX_PY:?set MLX_PY to the mlx-lm venv python}
HERE=$(cd "$(dirname "$0")" && pwd)
UPSTREAM=$((PORT + 100))
ARGS=(--model "$MODEL" --host 127.0.0.1 --port "$UPSTREAM" --max-tokens 2048 --temp 0)
[[ -n "$ADAPTER" ]] && ARGS+=(--adapter-path "$ADAPTER")
"$MLX_PY" -m mlx_lm.server "${ARGS[@]}" &
SERVER=$!
"$MLX_PY" "$HERE/mlx_proxy.py" --port "$PORT" --upstream "http://127.0.0.1:$UPSTREAM" ${LOG:+--log "$LOG"} &
PROXY=$!
echo "mlx_lm.server pid $SERVER on :$UPSTREAM, proxy pid $PROXY on :$PORT"
trap 'kill $SERVER $PROXY 2>/dev/null' INT TERM EXIT
wait
