#!/usr/bin/env bash
# The measurements in docs/finetune.md for one served proposer, with the unchanged harness.
#
#   PY=<project python> training/eval.sh <port> <model-name> <out-dir> [phrasings...]
#
# Runs, per phrasing (default: heldout paraphrase), on the TEST split:
#   python -m proven benchmark --extractor openweight --model <name> --phrasing P --n 110 --workers 4
#   python -m proven teach-sim --extractor openweight --model <name> --phrasing P --n 220
#   python training/by_cause.py --model <name> --phrasing P --n 220      (from the same cache)
# teach-sim's taught half is the benchmark's 110 closes, so it is answered from the cache.
set -uo pipefail
PORT=$1; NAME=$2; OUT=$3; shift 3
PHRASINGS=(heldout paraphrase)
[[ $# -gt 0 ]] && PHRASINGS=("$@")
PY=${PY:?set PY to the project python}
HERE=$(cd "$(dirname "$0")" && pwd)
export PROVEN_OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1
export PROVEN_CACHE_DIR=${PROVEN_CACHE_DIR:?set PROVEN_CACHE_DIR} PROVEN_ENV_FILE=${PROVEN_ENV_FILE:-/dev/null}
mkdir -p "$OUT"
for P in "${PHRASINGS[@]}"; do
  "$PY" -m proven benchmark --extractor openweight --model "$NAME" --phrasing "$P" --n 110 --workers 4 \
      > "$OUT/bench-$NAME-$P.txt" 2>&1
  "$PY" -m proven teach-sim --extractor openweight --model "$NAME" --phrasing "$P" --n 220 \
      > "$OUT/teach-$NAME-$P.txt" 2>&1
  "$PY" "$HERE/by_cause.py" --model "$NAME" --phrasing "$P" --n 220 --json "$OUT/cause-$NAME-$P.json" \
      > /dev/null 2> "$OUT/cause-$NAME-$P.err"
  tail -4 "$OUT/bench-$NAME-$P.txt"; tail -2 "$OUT/teach-$NAME-$P.txt"
done
