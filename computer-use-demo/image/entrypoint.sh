#!/bin/bash
set -e

./start_all.sh
./novnc_startup.sh

python http_server.py > /tmp/server_logs.txt 2>&1 &

# Ensure we're in the home directory and PYTHONPATH is set
cd $HOME
export PYTHONPATH=$HOME:$PYTHONPATH

# Verify the module can be imported before starting uvicorn
python -c "import computer_use_demo.api; print('Module import successful')" || echo "Warning: Module import test failed"

# Start FastAPI using python -m uvicorn for better module resolution
python -m uvicorn computer_use_demo.api:app --host 0.0.0.0 --port 8501 > /tmp/fastapi_stdout.log 2>&1 &

echo "✨ Computer Use Demo is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"
echo "➡️  API available at http://localhost:8501"
echo "➡️  API docs at http://localhost:8501/docs"

# Keep the container running
tail -f /dev/null
