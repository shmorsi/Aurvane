#!/usr/bin/env bash
# Every Muse Spark run the protocols call for, in order, then the demo page is rebuilt.
#
#   export META_MODEL_API_KEY=...            # from the Meta Model API console
#   MODEL=<muse spark model id> PRICE=<usd per M input>,<usd per M output> bash scripts/run_muse_spark.sh
#
# Optional: CAP (USD, default 5, shared with every other real-model run through bench/results/spend.json)
#           BASE_URL (default https://api.meta.ai/v1)
# Each step is run once. A failed or partial run is kept and reported, never rerun to get a better number.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${META_MODEL_API_KEY:?set META_MODEL_API_KEY first}"
: "${MODEL:?set MODEL to the Muse Spark model id shown in your console}"
: "${PRICE:?set PRICE to the console price as in,out (USD per million tokens)}"
CAP="${CAP:-5}"
URL=(); [ -n "${BASE_URL:-}" ] && URL=(--base-url "$BASE_URL")

echo "1/5 connectivity check (one tiny call)"
python -m aurvane.models meta "$MODEL" ${BASE_URL:-}
echo "2/5 visual suite: 60 tasks with and without Aurvane (bench/vision/PROTOCOL.md)"
python -m aurvane.bench --provider meta --model "$MODEL" --price "$PRICE" --cap "$CAP" --suite vision "${URL[@]}"
echo "3/5 evidence locator: 60 pages"
python -m aurvane.evidence --provider meta --model "$MODEL" --price "$PRICE" --cap "$CAP" "${URL[@]}"
echo "4/5 text suite: the same 60 tasks as text (bench/PROTOCOL.md)"
python -m aurvane.bench --provider meta --model "$MODEL" --price "$PRICE" --cap "$CAP" "${URL[@]}"
echo "5/5 rebuild the demo page from the committed results"
python ui/build.py
echo "Done. Review bench/results/, then commit everything, including spend.json and any failed runs."
