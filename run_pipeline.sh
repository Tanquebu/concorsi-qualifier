#!/usr/bin/env bash
set -euo pipefail
cd /home/max/projects/concorsi-qualifier
source .venv/bin/activate

LOG="data/pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p data

{
  echo "=== Pipeline avviata: $(date) ==="

  echo "--- Collector ---"
  python -m src.collector

  echo "--- Extractor ---"
  python -m src.extractor

  echo "--- Matcher ---"
  python -m src.matcher

  echo "--- OCR worker (se coda non vuota) ---"
  python ocr_worker.py

  echo "--- Notifier ---"
  python -m src.notifier --days 30

  echo "=== Pipeline completata: $(date) ==="
} 2>&1 | tee "$LOG"

# Mantieni solo gli ultimi 14 log
ls -t data/pipeline_*.log | tail -n +15 | xargs -r rm
