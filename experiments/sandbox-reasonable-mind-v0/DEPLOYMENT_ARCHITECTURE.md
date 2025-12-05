# Deployment Architecture Recommendations

## Current System Analysis

### Project Components

1. **Watson Glaser TIS** (Web Application)
   - Pure HTML/CSS/JavaScript
   - No backend required
   - Runs in browser
   - Uses localStorage for persistence
   - **Deployment**: Static hosting (Vercel, Netlify, GitHub Pages, S3)

2. **Agents Framework** (Python Library)
   - Python 3.14 with venv
   - Anthropic SDK + MCP integration
   - Requires API keys (ANTHROPIC_API_KEY)
   - **Deployment**: Python environment (local, Lambda, Cloud Run)

3. **Autonomous Coding Agent** (Python Application)
   - Long-running process
   - Generates projects over multiple sessions
   - File system access required
   - **Deployment**: Server with persistent storage

4. **Computer Use Demo** (Isolated System)
   - Requires X11/VNC/desktop environment
   - Separate Docker container (already has Dockerfile)
   - **Deployment**: Docker container (security isolated)

5. **Logic Foundation** (Python Library/Notebook)
   - Jupyter notebook demonstrations
   - Can be extracted to library
   - **Deployment**: Same as Agents Framework

---

## Recommended Architecture

### Option 1: **Hybrid Approach** (RECOMMENDED)

```text
┌─────────────────────────────────────────────────┐
│ STATIC WEB (CDN)                                │
│ - Watson Glaser TIS                             │
│ - Served via Vercel/Netlify/GitHub Pages        │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ PYTHON SERVICES (Local/Cloud)                   │
│ Environment: Python 3.14 venv                   │
│ Components:                                     │
│   - Agents Framework                            │
│   - Logic Foundation                            │
│   - Autonomous Coding Agent                     │
│ Deployment: Direct on host or lightweight      │
│             container                           │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ ISOLATED CONTAINER (Docker)                     │
│ - Computer Use Demo ONLY                        │
│ - Full desktop environment                      │
│ - Network isolated                              │
└─────────────────────────────────────────────────┘
```

**Benefits**:

- Watson Glaser TIS runs independently (no backend needed)
- Python services use native performance (no container overhead)
- Only computer-use-demo containerized (it needs X11/VNC)
- Simple deployment and maintenance
- Fast iteration during development

---

### Option 2: **Full Container Approach**

```yaml
docker-compose.yml:
  - watson-glaser-tis (nginx serving static files)
  - agents-api (Python FastAPI/Flask wrapper)
  - computer-use-demo (existing Dockerfile)
```

**Benefits**:

- Reproducible environments
- Easy scaling
- Good for production deployment

**Drawbacks**:

- Overkill for current system
- Slower development iteration
- More complex setup

---

## Implementation Recommendation

### **Use bash/venv for main development** ✅

**Why:**

1. **Watson Glaser TIS** doesn't need containers (static files)
2. **Agents Framework** works great in venv (you already have `.venv`)
3. **Python 3.14** is already installed via Homebrew
4. **Fast iteration** - no rebuild cycles
5. **Native performance** - no virtualization overhead
6. **Simple debugging** - direct Python access

**When to containerize:**

- ☑️ Computer Use Demo (already has Dockerfile)
- ☐ Production deployment (optional, future)
- ☐ CI/CD pipelines (optional)
- ☐ Multi-tenant hosting (not needed now)

---

## Immediate Action Plan

### 1. Fix Python Environment (Current Priority)

```bash
# Update pyproject.toml with pytest config
cat >> pyproject.toml << 'EOF'

[tool.pytest.ini_options]
pythonpath = "."
addopts = "-ra -q"
testpaths = [
    "autonomous-coding",
    "agents"
]
EOF

# Run tests to verify
source .venv/bin/activate
python -m pytest autonomous-coding/ agents/
```

### 2. Watson Glaser TIS Deployment (Ready Now)

```bash
# Already working! Just deploy static files:
cd watson-glaser-trainer
npm test  # Verify (already passing 36/36)

# Deploy options:
# Option A: Vercel
vercel --prod

# Option B: Netlify
netlify deploy --prod --dir=.

# Option C: GitHub Pages
# Push to gh-pages branch

# Option D: Local serving
npm start  # http://localhost:8080
```

### 3. Agents Framework (Keep in venv)

```bash
# Already working after circular import fix
cd agents
source ../.venv/bin/activate
python extended_thinking_demo.py
python neuro_symbolic_integration.py
```

### 4. Computer Use Demo (Optional Container)

```bash
# Only if needed - this is the ONLY component that needs Docker
cd computer-use-demo
docker build -t computer-use-demo .
docker run -it computer-use-demo
```

---

## Development Workflow

### Daily Development (No Containers)

```bash
# Terminal 1: Python development
cd ~/Documents/GitHub/claude-quickstarts
source .venv/bin/activate
python -m pytest  # Run tests
python agents/agent_demo.py  # Test agents

# Terminal 2: Watson Glaser TIS
cd watson-glaser-trainer
npm start  # Live reload at localhost:8080

# Terminal 3: Jupyter notebooks
cd agents
jupyter notebook logic_foundation_demo.ipynb
```

### Production Deployment

```bash
# Watson Glaser: Static hosting (no container)
vercel --prod

# Agents: Could containerize if needed
# (But direct venv deployment is fine for now)
```

---

## File Structure Recommendation

```text
claude-quickstarts/
├── .venv/                      # Python venv (current setup ✅)
├── agents/                     # Python library
├── autonomous-coding/          # Python app
├── watson-glaser-trainer/      # Static web app (no backend)
├── computer-use-demo/          # Docker container (isolated)
├── pyproject.toml             # Python config
├── requirements.txt           # Python deps (if needed)
└── docker-compose.yml         # Optional, future use

# DON'T NEED:
├── ❌ Dockerfile              # Not needed for main system
├── ❌ .dockerignore           # Not needed yet
```

---

## Summary

**Answer: Use bash shell with Python venv** ✅

**Reasons:**

1. ✅ Already set up (`.venv` exists)
2. ✅ Python 3.14 installed via Homebrew
3. ✅ Watson Glaser TIS is static (no backend)
4. ✅ Faster development iteration
5. ✅ Simpler debugging
6. ✅ Native performance
7. ✅ No container overhead

**Only containerize:**

- Computer Use Demo (already has Dockerfile)
- Future production deployment (optional)

**Current status:**

- npm: ✅ 0 vulnerabilities
- Watson Glaser: ✅ 36/36 tests passing
- Agents Framework: ✅ Fixed circular import
- pytest: ⚠️ Needs config update (implementing now)
