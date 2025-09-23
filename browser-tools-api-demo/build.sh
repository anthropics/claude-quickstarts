#!/bin/bash
set -e

echo "🏗️  Building Browser Tools API Demo Docker image..."
docker build . -t browser-tools-api-demo:latest

echo "✅ Build complete!"
echo ""
echo "To run the demo:"
echo "  docker run -e ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY \\"
echo "    -v \$(pwd)/browser_tools_api_demo:/home/browsertoolsapi/browser_tools_api_demo/ \\"
echo "    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \\"
echo "    -it browser-tools-api-demo:latest"
echo ""
echo "Then open:"
echo "  - http://localhost:8501 for the Streamlit interface"
echo "  - http://localhost:8080 to see the browser"