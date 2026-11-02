#!/usr/bin/env bash
# Generates the Python gRPC client for the OpenShell gateway from the vendored
# protocol definitions. Run after changing third_party/openshell/proto.
set -euo pipefail
cd "$(dirname "$0")/.."
out=src/agentpolicy/_proto
python -m grpc_tools.protoc \
  -I third_party/openshell/proto \
  --python_out="$out" \
  --grpc_python_out="$out" \
  openshell.proto sandbox.proto datamodel.proto options.proto
echo "generated $(find "$out" -name "*_pb2*.py" | wc -l) files in $out"
