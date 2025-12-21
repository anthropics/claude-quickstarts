#!/bin/bash
set -e

./start_all.sh
./novnc_startup.sh

python http_server.py > /tmp/server_logs.txt 2>&1 &

uvicorn computer_use_demo.api:app --host 0.0.0.0 --port 8501 > /tmp/fastapi_stdout.log 2>&1 &

echo "✨ Computer Use Demo is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"
echo "➡️  API available at http://localhost:8501"
echo "➡️  API docs at http://localhost:8501/docs"

# Keep the container running
tail -f /dev/null
