#!/usr/bin/env bash
# Singularity — spouštěč testů
set -euo pipefail

MODE="${1:-unit}"

case "$MODE" in
  unit)
    pytest tests/unit/ -v -m unit
    ;;
  integration)
    pytest tests/integration/ -v -m integration
    ;;
  chaos)
    pytest tests/chaos/ -v -m chaos
    ;;
  perf)
    pytest tests/perf/ -v -m perf
    ;;
  all)
    pytest tests/ -v
    ;;
  cov)
    pytest tests/ --cov=. --cov-report=term-missing
    ;;
  *)
    echo "Použití: $0 {unit|integration|chaos|perf|all|cov}"
    exit 1
    ;;
esac
