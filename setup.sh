#!/bin/bash
# Setup script for Claude Quickstarts development environment

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CLAUDE QUICKSTARTS - DEVELOPMENT ENVIRONMENT SETUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo "📦 Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python ${PYTHON_VERSION} found"
else
    echo -e "${RED}✗${NC} Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Check Node.js version
echo ""
echo "📦 Checking Node.js installation..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js ${NODE_VERSION} found"
else
    echo -e "${YELLOW}⚠${NC} Node.js not found. Watson Glaser TIS requires Node.js 18+"
fi

# Create/activate venv
echo ""
echo "🐍 Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating new virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate venv
source .venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
python -m pip install --upgrade pip -q
echo -e "${GREEN}✓${NC} pip upgraded"

# Install Python dependencies
echo ""
echo "📚 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo -e "${GREEN}✓${NC} Dependencies from requirements.txt installed"
fi

# Install agents package in development mode
if [ -d "agents" ]; then
    pip install -e agents -q 2>/dev/null || echo -e "${YELLOW}⚠${NC} Agents package not installable (no setup.py)"
fi

# Add pytest config if not exists
echo ""
echo "🧪 Configuring pytest..."
if ! grep -q "\[tool.pytest.ini_options\]" pyproject.toml 2>/dev/null; then
    cat >> pyproject.toml << 'EOF'

[tool.pytest.ini_options]
pythonpath = "."
addopts = "-ra -q"
testpaths = [
    "autonomous-coding",
    "agents"
]
norecursedirs = [
    ".venv",
    "computer-use-demo",
    "watson-glaser-trainer",
    "node_modules",
    ".git"
]
EOF
    echo -e "${GREEN}✓${NC} pytest configuration added to pyproject.toml"
else
    echo -e "${GREEN}✓${NC} pytest already configured"
fi

# Setup Watson Glaser TIS
echo ""
echo "🧠 Setting up Watson Glaser TIS..."
if [ -d "watson-glaser-trainer" ]; then
    cd watson-glaser-trainer
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install -q
        echo -e "${GREEN}✓${NC} Node dependencies installed"
    else
        echo -e "${GREEN}✓${NC} Node dependencies already installed"
    fi
    
    cd ..
else
    echo -e "${YELLOW}⚠${NC} watson-glaser-trainer directory not found"
fi

# Run tests
echo ""
echo "🧪 Running test suite..."
echo ""

# Python tests
echo "━━━ Python Tests ━━━"
if python -m pytest --collect-only -q 2>&1 | grep -q "error"; then
    echo -e "${RED}✗${NC} Test collection has errors"
    python -m pytest --collect-only
else
    echo -e "${GREEN}✓${NC} Test collection successful"
    python -m pytest -q 2>&1 | tail -10
fi

# Watson Glaser tests
echo ""
echo "━━━ Watson Glaser Tests ━━━"
if [ -d "watson-glaser-trainer" ]; then
    cd watson-glaser-trainer
    npm test 2>&1 | tail -20
    cd ..
else
    echo -e "${YELLOW}⚠${NC} Skipping Watson Glaser tests"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SETUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 Quick Start Commands:"
echo ""
echo "  # Activate Python environment:"
echo "  source .venv/bin/activate"
echo ""
echo "  # Run Python tests:"
echo "  python -m pytest"
echo ""
echo "  # Run Watson Glaser TIS:"
echo "  cd watson-glaser-trainer && npm start"
echo ""
echo "  # Run specific agent demo:"
echo "  python agents/extended_thinking_demo.py"
echo ""
echo "  # Run Jupyter notebook:"
echo "  jupyter notebook agents/logic_foundation_demo.ipynb"
echo ""
echo "  # Check for issues:"
echo "  python -m pytest --collect-only  # Should show 4 tests"
echo "  cd watson-glaser-trainer && npm test  # Should pass 36/36"
echo ""
echo "📚 Documentation:"
echo "  - DEPLOYMENT_ARCHITECTURE.md  # Architecture decisions"
echo "  - IMPLEMENTATION_GAP_ANALYSIS.md  # Gap analysis"
echo "  - ISSUES_RESOLVED.md  # Recent fixes"
echo ""
echo -e "${GREEN}✓${NC} Environment ready for development!"
echo ""
