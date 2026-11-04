#!/usr/bin/env bash
# Every Muse Spark run the protocols call for, in order, then the demo page is rebuilt.
#
# Muse Spark on the Meta Model API:
#   export META_MODEL_API_KEY=...            # from the Meta Model API console
#   MODEL=<muse spark model id> PRICE=<usd per M input>,<usd per M output> bash scripts/run_muse_spark.sh
#
# Muse Spark Open (Meta open weights) on Baseten:
#   export BASETEN_API_KEY=...
#   PROVIDER=baseten PRICE=<in>,<out> bash scripts/run_muse_spark.sh   # MODEL defaults to meta-models/muse-spark-open-1026
#
# Optional: CAP (USD, default 5, shared with every other real-model run through bench/results/spend.json)
#           BASE_URL (default https://api.meta.ai/v1 for meta, https://inference.baseten.co/v1 for baseten)
#           SKIP_TEXT=1 to skip step 4 (the text suite) when time or budget is short
# Each step is run once. A failed or partial run is kept and reported, never rerun to get a better number.
set -euo pipefail
cd "$(dirname "$0")/.."
PROVIDER="${PROVIDER:-meta}"
case "$PROVIDER" in
  meta)    : "${META_MODEL_API_KEY:?set META_MODEL_API_KEY first}"
           : "${MODEL:?set MODEL to the Muse Spark model id shown in your console}" ;;
  baseten) : "${BASETEN_API_KEY:?set BASETEN_API_KEY first}"
           MODEL="${MODEL:-meta-models/muse-spark-open-1026}" ;;
  *)       echo "PROVIDER must be meta or baseten"; exit 2 ;;
esac
: "${PRICE:?set PRICE to the console price as in,out (USD per million tokens)}"
CAP="${CAP:-5}"
URL=(); [ -n "${BASE_URL:-}" ] && URL=(--base-url "$BASE_URL")

echo "1/5 connectivity check (one tiny call to $PROVIDER / $MODEL)"
if ! python -m aurvane.models "$PROVIDER" "$MODEL" ${BASE_URL:-}; then
  echo "Connectivity check failed. If the console shows a different base URL, rerun with BASE_URL=<it>."
  echo "Nothing was benchmarked, so this does not count as a run."; exit 1
fi
echo "2/5 visual suite: 60 tasks with and without Aurvane (bench/vision/PROTOCOL.md)"
python -m aurvane.bench --provider "$PROVIDER" --model "$MODEL" --price "$PRICE" --cap "$CAP" --suite vision "${URL[@]}"
echo "3/5 evidence locator: 60 pages"
python -m aurvane.evidence --provider "$PROVIDER" --model "$MODEL" --price "$PRICE" --cap "$CAP" "${URL[@]}"
if [ -z "${SKIP_TEXT:-}" ]; then
  echo "4/5 text suite: the same 60 tasks as text (bench/PROTOCOL.md)"
  python -m aurvane.bench --provider "$PROVIDER" --model "$MODEL" --price "$PRICE" --cap "$CAP" "${URL[@]}"
else
  echo "4/5 text suite: skipped (SKIP_TEXT set)"
fi
echo "5/5 rebuild the demo page from the committed results"
python ui/build.py
echo "Done. Review bench/results/, then commit everything, including spend.json and any failed runs."
