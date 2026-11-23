#!/usr/bin/env bash
# Run from the platform root. The isolated worker receives development inputs only.
set -euo pipefail
control=$(realpath "${1:?verified frozen CT2 model directory}")
pilot=$(realpath .data/mt-pilot)
for arm in frozen adapter; do
  model=$control
  manifest=$(realpath translator/control.json)
  if [[ $arm == adapter ]]; then
    model=$pilot/converted/ct2-int8
    manifest=$(realpath translator_pilot/compute/ct2-export.json)
  fi
  docker run --rm --network none --read-only --cpus 2 --memory 8g --cap-drop ALL \
    --security-opt no-new-privileges -e PYTHONPATH=/app \
    -v "$model:/model:ro" -v "$manifest:/release.json:ro" \
    -v "$pilot/dev.jsonl:/inputs/dev.jsonl:ro" \
    -v "$pilot/results/${arm}_dev.jsonl:/inputs/gpu.jsonl:ro" \
    -v "$PWD/translator_pilot/compute/parity.py:/parity.py:ro" \
    commondesk-mt:pilot python /parity.py > "$pilot/parity-$arm.json"
done
