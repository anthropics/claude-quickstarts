#!/usr/bin/env bash
set -e
# Run the streamlit app as a package so relative imports work
cd "$(dirname "$0")"
python -m computer_use_demo.streamlit "$@"
