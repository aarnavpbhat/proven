#!/usr/bin/env bash
# Serve a base model, optionally with a LoRA adapter, on loopback for Proven's openweight
# extractor: mlx_lm.server on <port>+100, and training/mlx_proxy.py on <port>.
#
#   MLX_PY=<venv>/bin/python training/serve.sh <hf-model> <port> <name> [<adapter-dir>] [<request-log>]
#
# <name> is the model id the proxy reports on /v1/models; pass the same one to Proven
# (--model or PROVEN_OPENAI_MODEL). Then:
#   PROVEN_OPENAI_BASE_URL=http://127.0.0.1:<port>/v1 python -m proven ... --extractor openweight --model <name>
# Stop it with Ctrl-C, or kill the PIDs it prints.
set -euo pipefail
MODEL=$1; PORT=$2; NAME=$3; ADAPTER=${4:-}; LOG=${5:-}
MLX_PY=${MLX_PY:?set MLX_PY to the mlx-lm venv python}
HERE=$(cd "$(dirname "$0")" && pwd)
UPSTREAM=$((PORT + 100))
ARGS=(--model "$MODEL" --host 127.0.0.1 --port "$UPSTREAM" --max-tokens 2048 --temp 0)
[[ -n "$ADAPTER" ]] && ARGS+=(--adapter-path "$ADAPTER")
"$MLX_PY" "$HERE/memguard.py" mlx_lm.server "${ARGS[@]}" &
SERVER=$!
PROXY_ARGS=(--port "$PORT" --upstream "http://127.0.0.1:$UPSTREAM" --name "$NAME")
[[ -n "${REPAIR:-}" ]] && PROXY_ARGS+=(--repair-bare-objects)   # base-model measurement aid only
[[ -n "$LOG" ]] && PROXY_ARGS+=(--log "$LOG")
"$MLX_PY" "$HERE/mlx_proxy.py" "${PROXY_ARGS[@]}" &
PROXY=$!
echo "mlx_lm.server pid $SERVER on :$UPSTREAM, proxy pid $PROXY on :$PORT as $NAME"
trap 'kill $SERVER $PROXY 2>/dev/null' INT TERM EXIT
wait
