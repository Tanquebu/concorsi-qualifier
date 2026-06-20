#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/max/projects/concorsi-qualifier
source .venv/bin/activate

LOG="data/pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p data
exec 1> >(tee -a "$LOG") 2>&1

RUN_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
PY="python pipeline_db_helper.py"

$PY init "$RUN_ID"

_step=""
_on_exit() {
  local code=$?
  if [ $code -ne 0 ]; then
    $PY done "$RUN_ID" error "$_step" "exit code $code" 2>/dev/null || true
  fi
  # Mantieni solo gli ultimi 14 log
  ls -t data/pipeline_*.log 2>/dev/null | tail -n +15 | xargs -r rm
}
trap '_on_exit' EXIT

# Esegue uno step: registra inizio/fine sul tracker separando gli errori
# dello step da eventuali errori del tracker stesso.
#   _run_step <step_name> <comando...>
_run_step() {
  local step="$1"; shift
  _step="$step"
  $PY start "$RUN_ID" "$step" 2>/dev/null || true
  "$@"                          # propaga il codice di uscita del comando Python
  local rc=$?
  if [ $rc -eq 0 ]; then
    $PY end "$RUN_ID" "$step" 2>/dev/null || true
  fi
  return $rc
}

echo "=== Pipeline avviata: $(date) ==="

echo "--- Collector ---"
_run_step collector python -m src.collector

echo "--- Extractor ---"
_run_step extractor python -m src.extractor

echo "--- OCR worker (se coda non vuota) ---"
_run_step ocr_worker python ocr_worker.py

echo "--- Matcher ---"
_run_step matcher python -m src.matcher

echo "--- Reporter ---"
_run_step reporter python -m src.reporter

echo "--- Notifier ---"
_run_step notifier python -m src.notifier --days 30

echo "=== Pipeline completata: $(date) ==="
$PY done "$RUN_ID" completed
