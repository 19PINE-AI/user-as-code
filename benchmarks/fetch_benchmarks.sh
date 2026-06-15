#!/usr/bin/env bash
# Fetch the third-party benchmark datasets used by the experiments.
# We do not redistribute these datasets; this script pulls them from their
# original sources into the paths the experiment scripts expect.
set -euo pipefail
cd "$(dirname "$0")"

LOCOMO_DST="locomo/data/locomo10.json"
LME_DST="longmemeval/data/longmemeval_oracle.json"
LOCOMO_URL="https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"

mkdir -p "$(dirname "$LOCOMO_DST")" "$(dirname "$LME_DST")"

echo "==> LOCOMO"
if [ -f "$LOCOMO_DST" ]; then
  echo "    already present: $LOCOMO_DST"
else
  echo "    downloading from $LOCOMO_URL"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$LOCOMO_URL" -o "$LOCOMO_DST"
  else
    wget -q "$LOCOMO_URL" -O "$LOCOMO_DST"
  fi
  echo "    saved -> $LOCOMO_DST"
fi

echo "==> LongMemEval"
if [ -f "$LME_DST" ]; then
  echo "    already present: $LME_DST"
else
  cat <<EOF
    LongMemEval is distributed by its authors (not via a direct download URL).
    1. Get the dataset from: https://github.com/xiaowu0162/LongMemEval
       (the repo links a Google Drive / Hugging Face release).
    2. Place the oracle split here:
       $(pwd)/$LME_DST
    Then re-run this script to verify.
EOF
fi

echo
echo "Done. Verify with:"
echo "  ls -lh $LOCOMO_DST $LME_DST"
