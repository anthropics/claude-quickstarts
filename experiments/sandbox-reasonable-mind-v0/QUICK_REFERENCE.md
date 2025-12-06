# Claude Quickstarts - Quick Reference

## 🚀 Daily Development Commands

### Python Environment

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all Python tests
python -m pytest

# Run specific test file
python -m pytest agents/test_message_params.py

# Run specific test
python -m pytest agents/test_message_params.py::TestMessageParams::test_basic_params
```

### Watson Glaser TIS (Web Application)

```bash
cd watson-glaser-trainer

# Run tests (36 integration tests)
npm test

# Start development server
npm start  # http://localhost:8080

# Run all tests including Puppeteer
npm run test-all

# Open validation in browser
npm run validate
```

### Agent Demos

```bash
# Extended Thinking demo
python agents/extended_thinking_demo.py

# Scalability comparison
python agents/scalability_demo.py

# Neuro-symbolic integration
python agents/neuro_symbolic_integration.py

# Agent with message params
python agents/test_message_params.py
```

### Jupyter Notebooks

```bash
# Extended Thinking integration
jupyter notebook agents/extended_thinking_integration.ipynb

# Logic Foundation (Phase 1)
jupyter notebook agents/logic_foundation_demo.ipynb

# Agent demonstration
jupyter notebook agents/agent_demo.ipynb
```

### Autonomous Coding Agent

```bash
cd autonomous-coding

# Run autonomous agent (creates projects)
python autonomous_agent_demo.py --project-dir my-app

# Test security hooks
python test_security.py
```

---

## 📁 Project Structure

```text
claude-quickstarts/
├── .venv/                          # Python virtual environment
├── agents/                         # AI Agent framework
│   ├── agent.py                   # Main Agent class
│   ├── extended_thinking_demo.py  # Extended Thinking examples
│   ├── scalability_demo.py        # Architecture comparisons
│   ├── logic/                     # Neuro-symbolic reasoning
│   │   ├── epistemic.py          # Confidence calculation
│   │   ├── grounding.py          # Semantic parsing
│   │   ├── knowledge_base.py     # Fact storage
│   │   └── reasoning_agent.py    # Orchestration
│   ├── tools/                     # Agent tools
│   │   ├── extended_thinking.py  # Extended Thinking tool
│   │   ├── calculator_mcp.py     # MCP calculator
│   │   ├── mcp_tool.py           # MCP integration (fixed)
│   │   └── web_search.py         # Web search tool
│   └── utils/
│       ├── connections.py         # MCP connections (fixed)
│       └── history_util.py        # Message history
│
├── watson-glaser-trainer/         # Web-based TIS
│   ├── advanced.html             # Main application
│   ├── agent_profiles.js         # 10 agent profiles
│   ├── tests/
│   │   ├── integration_test.js   # 36 tests ✅
│   │   ├── puppeteer_test.js     # Browser automation
│   │   └── validation.html       # Browser tests
│   └── design/
│       └── design_tokens.json    # Design system
│
├── autonomous-coding/             # Autonomous code generation
│   ├── autonomous_agent_demo.py  # Main entry point
│   ├── agent.py                  # Agent logic
│   ├── security.py               # Security hooks
│   └── test_security.py          # Security tests ✅
│
├── data/                          # Phase 1 logic data
│   ├── argument_forms.json       # Valid/invalid forms
│   └── fallacies.json            # Fallacy database
│
└── computer-use-demo/             # Isolated (Docker)
    ├── Dockerfile                # Container config
    └── computer_use_demo/        # Demo code
```

---

## 🧪 Testing Status

### Python Tests

| Component          | Status    | Count | Notes                       |
|--------------------|-----------|-------|-----------------------------|
| Autonomous Coding  | ✅ Pass   | 4/4   | Security tests working      |
| Agents Framework   | ✅ Fixed  | -     | Circular import resolved    |
| Computer Use Demo  | ⚠️ Skip   | -     | Requires separate setup     |

### JavaScript Tests

| Component        | Status       | Count | Notes                           |
|------------------|--------------|-------|---------------------------------|
| Watson Glaser    | ✅ Pass      | 36/36 | Integration tests               |
| Puppeteer Tests  | ⚠️ Optional  | -     | Chrome launch issues on macOS   |

### Known Issues

- ✅ **Fixed**: Circular import (mcp_tool.py ↔ connections.py)
- ✅ **Fixed**: Extended Thinking notebook formatting
- ✅ **Fixed**: Puppeteer Chrome flags (now optional)
- ⚠️ **Skip**: computer-use-demo tests (requires Docker)

---

## 🔧 Environment Setup

### First Time Setup

```bash
# Run automated setup script
chmod +x setup.sh
./setup.sh
```

### Manual Setup

```bash
# 1. Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install --upgrade pip
pip install anthropic pytest pytest-asyncio

# 3. Setup Watson Glaser TIS
cd watson-glaser-trainer
npm install
cd ..

# 4. Configure pytest
# (setup.sh does this automatically)
```

### Environment Variables

```bash
# Required for agent demos
export ANTHROPIC_API_KEY='your-api-key-here'

# Optional for custom Chrome path
export PUPPETEER_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

---

## 🐛 Troubleshooting

### pytest collection errors

```bash
# Check test collection
python -m pytest --collect-only

# Should show only 4 tests from:
# - autonomous-coding/test_security.py
# - agents/test_message_params.py (if API key set)

# If seeing computer-use-demo errors:
# → Check pyproject.toml has testpaths configured
```

### Circular import errors

```bash
# Should be fixed, but if you see:
# ImportError: cannot import name 'MCPConnection' from partially initialized module

# Verify these files use TYPE_CHECKING:
# - agents/tools/mcp_tool.py
# - agents/utils/connections.py
```

### Puppeteer Chrome launch failure

```bash
# Normal on macOS Apple Silicon - use alternatives:
cd watson-glaser-trainer

# Option 1: Run integration tests only (recommended)
npm test  # Skips Puppeteer by default

# Option 2: Use manual browser testing
npm start
open http://localhost:8080

# Option 3: Set Chrome path
export PUPPETEER_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
npm run test-all
```

### npm vulnerabilities

```bash
# Check for security issues
cd watson-glaser-trainer
npm audit

# Currently: 0 vulnerabilities ✅
```

---

## 📊 Key Metrics

- **Python Tests**: 4 passing (autonomous-coding)
- **JavaScript Tests**: 36/36 passing (watson-glaser-trainer)
- **npm Vulnerabilities**: 0
- **Python Version**: 3.14.0
- **Node Version**: ≥18.0.0
- **Agent Profiles**: 10 (novice → professor-emeritus)
- **Fallacy Database**: 11 patterns (expanding to 25+)
- **Extended Thinking**: 4x/8x/16x/32x architectures
- **Logic Weight**: 75% (prioritizes deductive+inductive reasoning)

---

## 🎯 Next Steps

### Immediate (Done)

- ✅ Fix circular imports
- ✅ Configure pytest to skip computer-use-demo
- ✅ Fix notebook formatting errors
- ✅ Enhance Puppeteer compatibility

### Short-term

- [ ] Expand fallacy database from 11 to 25+ patterns
- [ ] Add CLI interface for logic engine
- [ ] Create golden test cases for practice
- [ ] Implement model-specific configs (Sonnet/Opus/Aurora)

### Medium-term

- [ ] Migrate Puppeteer tests to Playwright
- [ ] Add formal 80-item Watson-Glaser assessment
- [ ] Build analytics dashboard
- [ ] Implement local LLM support

### Long-term

- [ ] Full neuro-symbolic integration
- [ ] Production deployment (Vercel + Cloud Run)
- [ ] Multi-agent orchestration
- [ ] Teaching mode (system explains reasoning)

---

## 📚 Documentation

- `DEPLOYMENT_ARCHITECTURE.md` - Container vs bash/venv decision
- `IMPLEMENTATION_GAP_ANALYSIS.md` - Phase 1-4 gap analysis
- `ISSUES_RESOLVED.md` - Recent bug fixes
- `watson-glaser-trainer/README.md` - TIS documentation
- `autonomous-coding/README.md` - Autonomous agent guide
- `agents/logic/README.md` - Neuro-symbolic architecture

---

## 🤝 Contributing

```bash
# Create feature branch
git checkout -b feature/my-feature

# Run tests before committing
python -m pytest
cd watson-glaser-trainer && npm test

# Commit with descriptive messages
git commit -m "feat: add fallacy pattern detection"

# Push to branch
git push origin feature/my-feature
```

---

**Last Updated**: December 4, 2025  
**Branch**: wgt-test-dev  
**Status**: ✅ Development ready
