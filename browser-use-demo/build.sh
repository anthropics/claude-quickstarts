#!/bin/bash
set -e

echo "🏗️  Building Browser Use Demo Docker image..."
docker build . -t browser-use-demo:latest

echo "✅ Build complete!"
echo ""
echo "To run the demo:"
echo "  docker run -e ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY \\"
echo "    -v \$(pwd)/browser_use_demo:/home/browseruse/browser_use_demo/ \\"
echo "    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \\"
echo "    -it browser-use-demo:latest"
echo ""
echo "Then open:"
echo "  - http://localhost:8501 for the Streamlit interface"
echo "  - http://localhost:8080 to see the browser"