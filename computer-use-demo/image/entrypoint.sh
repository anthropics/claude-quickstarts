#!/bin/bash
set -e

./start_all.sh
./novnc_startup.sh

echo "➡️  Open http://localhost:8000"

exec python -m uvicorn computer_use_demo.api.main:app --host 0.0.0.0 --port 8000 --log-level info
