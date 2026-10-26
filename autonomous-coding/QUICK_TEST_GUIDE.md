# Quick Testing Guide for Autonomous Coding Agent

## TL;DR - Fastest Test (5 minutes)

```bash
# 1. Set API key
export ANTHROPIC_API_KEY='your-key-here'

# 2. Activate venv
source .venv/bin/activate

# 3. Run quick test (3 iterations, minimal project)
python test_runner.py --use-minimal-spec --max-iterations 3

# 4. Watch the output and observe agent behavior
```

---

## Three Testing Modes

### Mode 1: Ultra-Quick Test (5-10 minutes)
**Best for:** First-time testing, understanding the workflow

```bash
python test_runner.py \
  --use-minimal-spec \
  --max-iterations 2 \
  --project-dir ./quick_test
```

**What happens:**
- Session 1: Agent creates 20-30 features for a simple Todo CLI app
- Session 2: Agent implements first 1-2 features
- **Cost:** ~$1-3 depending on model
- **Output:** `generations/quick_test/`

### Mode 2: Standard Test (30-60 minutes)
**Best for:** Validating full workflow, testing customizations

```bash
python autonomous_agent_demo.py \
  --project-dir ./standard_test \
  --max-iterations 5
```

**What happens:**
- Session 1: Agent creates 200 features for claude.ai clone
- Sessions 2-5: Agent implements ~5-10 features
- **Cost:** ~$10-20 depending on model
- **Output:** `generations/standard_test/`

### Mode 3: Full Run (Hours)
**Best for:** Building actual project, production validation

```bash
python autonomous_agent_demo.py \
  --project-dir ./my_real_project
  # No --max-iterations limit
```

**What happens:**
- Runs until all 200 features complete
- Auto-continues between sessions
- **Cost:** ~$50-150 depending on complexity
- **Time:** Several hours across multiple sessions

---

## Setup Checklist

### 1. Install Dependencies

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate

# Install packages
uv pip install -r requirements.txt

# Verify installation
python -c "import claude_code_sdk; print('SDK installed!')"
```

### 2. Set API Key

```bash
# Get your key from: https://console.anthropic.com/
export ANTHROPIC_API_KEY='sk-ant-...'

# Verify it's set
echo $ANTHROPIC_API_KEY | head -c 20
```

### 3. Check Claude Code CLI (Optional)

```bash
# Should already be installed
claude --version

# If not installed:
npm install -g @anthropic-ai/claude-code
```

---

## Monitoring the Test

### What to Watch For

**During Session 1 (Initialization):**
```
✅ Good signs:
  [Tool: Write] - Creating feature_list.json
  [Tool: Write] - Creating init.sh
  [Tool: Bash] - git init

⏱️  Slow/hanging? This is normal:
  - Generating 200 features takes 5-10 minutes
  - Watch for [Tool: ...] activity to confirm it's working
```

**During Session 2+ (Coding):**
```
✅ Good signs:
  [Tool: Read] - Reading feature_list.json
  [Tool: Bash] - npm install, npm run dev
  [Tool: puppeteer_navigate] - Testing in browser
  [Tool: Write] - Updating feature_list.json
  [Tool: Bash] - git commit

❌ Warning signs:
  [BLOCKED] - Security hook blocked a command
  [Error] - Tool execution failed
```

### Check Progress Anytime

```bash
# View current status
cat generations/test_project/claude-progress.txt

# Count completed features
cd generations/test_project
grep '"passes": true' feature_list.json | wc -l

# See recent commits
git log --oneline -10

# Check running processes
ps aux | grep node  # Dev server still running?
```

---

## Interrupting and Resuming

### Stop Gracefully

```bash
# Press Ctrl+C during any session
# Agent saves state to git before stopping
```

### Resume Later

```bash
# Run the EXACT same command
python test_runner.py --use-minimal-spec --max-iterations 3

# OR with more iterations
python test_runner.py --use-minimal-spec --max-iterations 5
```

**How resuming works:**
- Detects existing `feature_list.json`
- Skips initialization
- Continues from last checkpoint
- Uses fresh context window

---

## Testing Custom Projects

### Option 1: Edit Minimal Spec

```bash
# Edit the test spec
nano prompts/minimal_test_spec.txt

# Change project details:
# - Project name
# - Technology stack
# - Core features (keep it to 5-10 for quick testing)

# Run with custom spec
python test_runner.py --use-minimal-spec --max-iterations 3
```

### Option 2: Create Your Own Spec

```bash
# Copy template
cp prompts/minimal_test_spec.txt prompts/my_custom_spec.txt

# Edit it
nano prompts/my_custom_spec.txt

# Create project directory and copy spec
mkdir -p generations/my_project
cp prompts/my_custom_spec.txt generations/my_project/app_spec.txt

# Run
python autonomous_agent_demo.py \
  --project-dir generations/my_project \
  --max-iterations 3
```

---

## Inspecting Results

### Check Generated Code

```bash
cd generations/test_project

# View project structure
tree -L 2

# Read the code
cat *.py
cat README.md
```

### Run the Generated App

```bash
cd generations/test_project

# Use the init script created by agent
./init.sh

# Or manually:
pip install -r requirements.txt  # If Python project
npm install && npm run dev        # If Node.js project
```

### Review Feature Progress

```bash
# See all features
cat feature_list.json | jq '.'

# Count by status
echo "Total: $(jq 'length' feature_list.json)"
echo "Passing: $(jq '[.[] | select(.passes == true)] | length' feature_list.json)"
echo "Failing: $(jq '[.[] | select(.passes == false)] | length' feature_list.json)"
```

### Check Git History

```bash
# See all commits
git log --oneline

# See what changed in last commit
git show HEAD

# View specific file history
git log --follow feature_list.json
```

---

## Troubleshooting

### "Agent appears to hang on first run"

**This is normal!** The agent is writing 200 (or 20-30) features.

- Watch for `[Tool: Write]` activity
- Session 1 takes 5-20 minutes
- Be patient

### "Command blocked by security hook"

The agent tried to run something not in the allowlist.

```bash
# Check what was blocked (look in output for [BLOCKED] messages)

# Option 1: Add to allowlist (if safe)
nano security.py
# Add command to ALLOWED_COMMANDS

# Option 2: Ignore if not needed
# Agent will adapt and try different approach
```

### "API key not set"

```bash
# Check if set
echo $ANTHROPIC_API_KEY

# Set it in current shell
export ANTHROPIC_API_KEY='your-key-here'

# Set it permanently (optional)
echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### "High cost / running too long"

```bash
# Stop with Ctrl+C
# Check current spend (no built-in tracking yet)

# Reduce scope:
python test_runner.py --max-iterations 1  # Just one iteration

# Or use minimal spec:
python test_runner.py --use-minimal-spec --max-iterations 2
```

### "Feature tests not passing"

This is expected during testing! The agent works incrementally.

```bash
# Check progress
grep '"passes": true' generations/test_project/feature_list.json

# Let it continue if it's making progress
# Or investigate the last commit to see what failed
```

---

## Cost Estimation

### Approximate Costs (Sonnet 4.5)

| Test Mode | Duration | Input Tokens | Output Tokens | Cost |
|-----------|----------|--------------|---------------|------|
| Ultra-Quick (2 iter) | 5-10 min | ~50K | ~20K | $1-3 |
| Standard (5 iter) | 30-60 min | ~200K | ~80K | $10-20 |
| Full Run (50+ iter) | 3-6 hours | ~2M | ~800K | $50-150 |

**Variables affecting cost:**
- Project complexity
- Number of features
- Browser testing (screenshots, interactions)
- Error recovery attempts
- Model choice (Haiku cheaper, Opus more expensive)

---

## Next Steps After Testing

Once you've validated the agent works:

1. **Customize prompts** for your use case
2. **Add configuration system** for easier project setup
3. **Implement cost tracking** to monitor spend
4. **Add interactive mode** for approval workflows
5. **Create project templates** for common patterns

See the main README for productization roadmap.

---

## Quick Commands Reference

```bash
# Test with minimal project
python test_runner.py --use-minimal-spec --max-iterations 2

# Test with full project (limited)
python autonomous_agent_demo.py --max-iterations 5

# Check progress
cat generations/*/claude-progress.txt

# Count passing features
grep -r '"passes": true' generations/*/feature_list.json | wc -l

# View last commit
cd generations/test_project && git show HEAD

# Run generated app
cd generations/test_project && ./init.sh
```
