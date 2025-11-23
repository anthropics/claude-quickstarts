# Running Computer Use Demo on Linux VM with Claude Code

This guide shows you how to run the Anthropic Computer Use Demo directly on your Linux VM, with Claude Code installed so the AI agent can control and use Claude Code for development tasks.

## ⚠️ CRITICAL SECURITY WARNING

Running this setup means **Claude will have direct control over your Linux VM**, including:
- Full filesystem access
- Ability to execute any shell commands
- Control over Claude Code to write/modify/delete code
- Access to your network and applications
- Ability to install packages, modify system settings, etc.

**ONLY run this on a dedicated, isolated VM that you can afford to reset!**

**Recommended precautions:**
- Use a fresh VM or take a snapshot before starting
- Don't store sensitive data on this VM
- Limit network access if possible
- Monitor what Claude is doing
- Keep your API keys separate (don't hardcode them)

---

## 🤖 Context for AI Agent (Claude)

**If you are Claude running in Computer Use mode, read this section carefully!**

### What This Setup Is

You are running in a **meta-AI configuration**:
- **Outer Layer (You):** Claude operating through the Computer Use API, controlling a Linux VM via GUI/bash tools
- **Inner Layer:** Claude Code CLI tool installed on the same VM that you can invoke for development tasks
- **Purpose:** You can use your computer control abilities to launch and interact with Claude Code for complex development workflows

### Your Capabilities in This Environment

**As Computer Use Claude, you can:**
1. **Control the desktop** - Click, type, navigate GUI applications
2. **Execute bash commands** - Run any shell command on the VM
3. **Take screenshots** - See what's currently displayed on screen
4. **Edit files** - Use the text editor tool to modify files
5. **Invoke Claude Code** - Run `claude` commands in the terminal to delegate coding tasks

**When to use Claude Code vs. doing it yourself:**
- **Use Claude Code for:** Complex coding tasks, multi-file refactoring, test generation, code review, documentation
- **Do it yourself for:** Simple GUI navigation, quick bash commands, file browsing, running applications

### System Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  User's Browser/Interface                           │
│  (Streamlit UI at localhost:8501)                   │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Computer Use API (You - Claude)                    │
│  - Model: claude-sonnet-4-5-20250929               │
│  - Tools: computer_20250124, bash_20250124, edit   │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Linux VM (Ubuntu 22.04)                            │
│  ┌──────────────────────────────────────────────┐  │
│  │  Desktop Environment (GNOME/KDE/XFCE)        │  │
│  │  - You can see and control this via screenshots│
│  │  - You can click buttons, type text, etc.    │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Terminal/Shell                               │  │
│  │  - You can execute bash commands here        │  │
│  │  - This is where you invoke Claude Code      │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Claude Code CLI                              │  │
│  │  - Command: 'claude <prompt>'                │  │
│  │  - Separate Claude instance for coding       │  │
│  │  - Uses same API key (from env var)          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Environment Variables You Should Know

```bash
# Your API key (already set if system is running)
echo $ANTHROPIC_API_KEY

# Screen resolution (if set)
echo $WIDTH $HEIGHT

# Python virtual environment for Computer Use Demo
# Located at: ~/anthropic-quickstarts/computer-use-demo/.venv
```

### File System Layout

```
/home/user/
├── anthropic-quickstarts/
│   └── computer-use-demo/
│       ├── computer_use_demo/       # Computer Use Demo source code
│       ├── .venv/                    # Python virtual environment
│       └── SETUP_VM_WITH_CLAUDE_CODE.md  # This guide
├── .anthropic/
│   ├── api_key                       # Stored API key
│   └── system_prompt                 # Custom system prompt (if any)
└── (user's project directories)      # Where you'll work on code
```

### How to Invoke Claude Code

**Basic syntax:**
```bash
claude "your prompt here"
```

**Interactive mode:**
```bash
cd /path/to/project
claude "refactor the authentication module to use JWT tokens"
# Claude Code will analyze, plan, and execute changes
```

**Best practices when using Claude Code:**
1. Always `cd` to the correct directory first
2. Be specific in your prompts
3. Review changes before confirming commits
4. Use for complex tasks (not simple file reads)

### Self-Healing and Troubleshooting

**If Claude Code command fails:**

1. **Check if Claude Code is installed:**
   ```bash
   which claude
   claude --version
   ```

2. **If not found, install it:**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

3. **Check API key is set:**
   ```bash
   echo $ANTHROPIC_API_KEY
   # If empty, set it:
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

4. **Check Node.js is installed:**
   ```bash
   node --version  # Should be v18 or higher
   npm --version
   ```

5. **If Node.js is missing:**
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

**If computer use tools fail:**

1. **Screenshot tool (scrot) not working:**
   ```bash
   sudo apt-get install --reinstall scrot xdotool imagemagick
   ```

2. **Can't execute bash commands:**
   - Check you're using the `bash` tool correctly
   - Verify you have permissions (use `sudo` if needed)
   - Check for syntax errors in commands

3. **File editing issues:**
   - Use absolute paths, not relative
   - Check file permissions before editing
   - Use `ls -la` to verify file exists

**If Python environment is broken:**

```bash
cd ~/anthropic-quickstarts/computer-use-demo
source .venv/bin/activate
pip install --upgrade -r computer_use_demo/requirements.txt
```

### Common Task Patterns

**Pattern 1: Create a new project with Claude Code**
```bash
# 1. Navigate to workspace
cd ~/projects

# 2. Use Claude Code to scaffold project
claude "create a new FastAPI project called 'my-api' with user authentication, database models, and tests"

# 3. Verify creation
ls -la my-api/
```

**Pattern 2: Debug existing code**
```bash
# 1. Navigate to project
cd ~/projects/my-app

# 2. Run tests to identify issues
pytest tests/ -v

# 3. Use Claude Code to fix
claude "the test_authentication.py tests are failing, please analyze and fix the issues"
```

**Pattern 3: Analyze and refactor**
```bash
# 1. Navigate to project
cd ~/projects/legacy-app

# 2. Use Claude Code for analysis
claude "analyze this codebase and suggest refactoring improvements for better maintainability"

# 3. Apply specific improvements
claude "refactor the database layer to use SQLAlchemy 2.0 async patterns"
```

### Coordination Between You and Claude Code

**Division of responsibilities:**

| Task | Who Should Do It | Why |
|------|-----------------|-----|
| Opening terminal | You (Computer Use) | GUI interaction |
| Navigating file system with GUI | You | Visual navigation |
| Running `claude` command | You | Bash execution |
| Writing/editing code | Claude Code | Specialized for coding |
| Running tests | Either | You: quick check, Claude Code: analyze results |
| Git operations | Claude Code | Better context for commits |
| Installing packages | You | System-level bash |
| Code review | Claude Code | Deep code analysis |
| Screenshot verification | You | Visual confirmation |

### Error Recovery Strategies

**When things go wrong:**

1. **Take a screenshot first** - See the current state
2. **Read error messages carefully** - Don't skip over details
3. **Check logs** - Many programs write to `/tmp/` or stdout
4. **Try simpler versions** - Break complex commands into steps
5. **Verify prerequisites** - Is the tool installed? Is the file there?
6. **Use `--help` flags** - Check command syntax
7. **Google is your friend** - Search for error messages if needed
8. **Reset if necessary** - Sometimes starting fresh is fastest

**Nuclear options (last resort):**
```bash
# Restart Computer Use Demo
sudo systemctl restart computer-use-demo

# Reinstall Claude Code
npm uninstall -g @anthropic-ai/claude-code
npm install -g @anthropic-ai/claude-code

# Reset Python environment
cd ~/anthropic-quickstarts/computer-use-demo
rm -rf .venv
./setup.sh
```

### Monitoring Your Own Performance

**Good signs you're working well:**
- ✅ Commands execute successfully on first try
- ✅ You're using the right tool for each job (Claude Code for coding, bash for simple tasks)
- ✅ You verify actions with screenshots when needed
- ✅ You handle errors gracefully with fallbacks

**Warning signs to watch for:**
- ⚠️ Repeatedly running the same failing command
- ⚠️ Using bash for complex coding tasks that Claude Code should handle
- ⚠️ Not checking if tools/files exist before using them
- ⚠️ Ignoring error messages

### Remember

- You are **not** running inside a Docker container - this is a real VM
- Changes you make are **persistent** - be careful!
- You have **full system access** - use it responsibly
- Claude Code is a **separate instance** - treat it as a specialized tool, not yourself
- The user is **watching** - explain what you're doing clearly

---

## Prerequisites

- **Linux VM** (Ubuntu 22.04 recommended)
- **Python 3.11 or 3.12** (NOT 3.13+)
- **Desktop environment** (GNOME, KDE, XFCE, etc.) - Claude needs a GUI to interact with
- **Anthropic API key** ([get one here](https://console.anthropic.com/))

---

## Part 1: System Setup

### 1. Update System and Install Dependencies

```bash
sudo apt-get update
sudo apt-get upgrade -y

# Install GUI control tools (required for computer use)
sudo apt-get install -y \
    scrot \
    xdotool \
    imagemagick \
    git \
    curl \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev
```

### 2. Verify Python Version

```bash
python3 --version
# Should show Python 3.11.x or 3.12.x
# If you have 3.13+, you'll need to install 3.12
```

### 3. Install Rust/Cargo (Required Dependency)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Verify installation
cargo --version
```

---

## Part 2: Install Computer Use Demo

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/anthropics/anthropic-quickstarts.git
cd anthropic-quickstarts/computer-use-demo
```

### 2. Run Setup Script

```bash
./setup.sh
```

This will:
- Create a Python virtual environment
- Install development dependencies
- Set up pre-commit hooks

### 3. Install Runtime Requirements

```bash
source .venv/bin/activate
pip install -r computer_use_demo/requirements.txt
```

---

## Part 3: Install Claude Code

### 1. Install Node.js (Required for Claude Code)

```bash
# Install Node.js 18 or higher
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify installation
node --version  # Should be v20.x.x or higher
npm --version
```

### 2. Install Claude Code CLI

```bash
# Install Claude Code globally
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### 3. Configure Claude Code

```bash
# Set up your API key for Claude Code
export ANTHROPIC_API_KEY="your_api_key_here"

# Add to your shell profile for persistence
echo 'export ANTHROPIC_API_KEY="your_api_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Test Claude Code

```bash
# Create a test directory
mkdir -p ~/test-claude-code
cd ~/test-claude-code

# Test Claude Code
claude "create a hello world python script"
```

---

## Part 4: Launch Computer Use Demo

### 1. Set Environment Variables

```bash
cd ~/anthropic-quickstarts/computer-use-demo
source .venv/bin/activate

export ANTHROPIC_API_KEY="your_api_key_here"

# Optional: set screen resolution
export WIDTH=1920
export HEIGHT=1080
```

### 2. Start Streamlit App

```bash
streamlit run computer_use_demo/streamlit.py --server.port 8501 --server.address 0.0.0.0
```

### 3. Access the Interface

- **From the VM itself:** Open browser to `http://localhost:8501`
- **From your host machine:** `http://<VM_IP_ADDRESS>:8501`

---

## Part 5: Using Claude to Control Claude Code

Once the Streamlit interface is running, you can give Claude instructions like:

### Example Prompts:

**Basic Claude Code usage:**
```
Open a terminal and use Claude Code to create a new Python project
with a Flask web server
```

**Multi-step development:**
```
Using Claude Code:
1. Create a new directory called 'my-api'
2. Initialize a Python project with FastAPI
3. Add endpoints for CRUD operations
4. Write tests for the endpoints
5. Create a README with setup instructions
```

**Debugging assistance:**
```
Navigate to /home/user/my-project, use Claude Code to analyze
the bug in main.py and fix it
```

**Code review:**
```
Use Claude Code to review all Python files in the current directory
and suggest improvements
```

---

## Configuration Options

### Model Selection

The default model is **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`). You can change this in the Streamlit sidebar.

Available models:
- `claude-sonnet-4-5-20250929` (latest, recommended)
- `claude-sonnet-4-20250514`
- `claude-opus-4-20250514`
- `claude-haiku-4-5-20251001`

### Tool Versions

The default tool version is `computer_use_20250124` which includes:
- `bash_20250124` - Latest bash tool
- `computer_20250124` - Latest computer control tool
- `str_replace_based_edit_tool` (July 2025) - Latest text editor

You can change this in the Streamlit sidebar under "Tool Versions".

### Custom System Prompt

Add additional instructions in the Streamlit sidebar under "Custom System Prompt Suffix". For example:

```
When using Claude Code, always:
- Use descriptive commit messages
- Add type hints to Python code
- Write docstrings for functions
- Run tests before committing
```

---

## Troubleshooting

### Computer Use Demo Issues

**Python version error:**
```bash
# If you have Python 3.13+, install 3.12
sudo apt-get install python3.12 python3.12-venv
# Edit setup.sh to use python3.12
```

**Cargo not found:**
```bash
source $HOME/.cargo/env
```

**Screen capture not working:**
```bash
sudo apt-get install --reinstall scrot xdotool imagemagick
```

### Claude Code Issues

**Command not found:**
```bash
# Reinstall globally
npm install -g @anthropic-ai/claude-code

# Check PATH
echo $PATH | grep npm
```

**API key not set:**
```bash
export ANTHROPIC_API_KEY="your_api_key_here"
echo 'export ANTHROPIC_API_KEY="your_api_key_here"' >> ~/.bashrc
```

**Permission errors:**
```bash
# Fix npm permissions
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## Advanced: Running as a Service

To run the Computer Use Demo as a systemd service:

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/computer-use-demo.service
```

### 2. Add Configuration

```ini
[Unit]
Description=Anthropic Computer Use Demo
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/anthropic-quickstarts/computer-use-demo
Environment="ANTHROPIC_API_KEY=your_api_key_here"
Environment="PATH=/home/your_username/anthropic-quickstarts/computer-use-demo/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/your_username/anthropic-quickstarts/computer-use-demo/.venv/bin/streamlit run computer_use_demo/streamlit.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable computer-use-demo
sudo systemctl start computer-use-demo

# Check status
sudo systemctl status computer-use-demo
```

---

## Security Best Practices

1. **Use a dedicated VM** - Never run this on a machine with sensitive data
2. **Snapshot regularly** - Take VM snapshots before major operations
3. **Monitor activity** - Watch what Claude is doing in real-time
4. **Limit network access** - Use firewall rules to restrict outbound connections
5. **Separate API keys** - Use different API keys for computer use vs. other projects
6. **Review code changes** - Always review code before committing/deploying
7. **Set resource limits** - Use cgroups or similar to limit CPU/memory/disk usage

---

## Example Workflows

### 1. Full Stack Development

```
Using Claude Code, build a todo app:
1. Create a React frontend with TypeScript
2. Build a FastAPI backend
3. Set up PostgreSQL database with Docker
4. Add authentication with JWT
5. Write tests for both frontend and backend
6. Create deployment configuration for production
```

### 2. Bug Investigation and Fix

```
Navigate to my project at /home/user/my-app.
Use Claude Code to:
1. Run the test suite and identify failing tests
2. Analyze the errors
3. Fix the bugs
4. Verify tests pass
5. Commit the fixes with a descriptive message
```

### 3. Code Refactoring

```
Use Claude Code to refactor the Python codebase in ~/my-project:
1. Add type hints to all functions
2. Split large files into smaller modules
3. Improve error handling
4. Add logging
5. Update documentation
```

---

## Stopping the Demo

### Quick Stop

Press `Ctrl+C` in the terminal running Streamlit

### If Running as Service

```bash
sudo systemctl stop computer-use-demo
```

### Reset State

```bash
# Clear session data
rm -rf ~/.anthropic/*

# Reset the demo
cd ~/anthropic-quickstarts/computer-use-demo
git reset --hard HEAD
git clean -fd
```

---

## Getting Help

- **Computer Use Demo Issues:** https://github.com/anthropics/anthropic-quickstarts/issues
- **Claude Code Issues:** https://github.com/anthropics/claude-code/issues
- **API Documentation:** https://docs.anthropic.com/
- **Computer Use Docs:** https://docs.anthropic.com/en/docs/build-with-claude/computer-use

---

## What's Next?

- Explore combining computer use with Claude Code for autonomous development
- Set up CI/CD pipelines that Claude can interact with
- Create custom system prompts for specific development workflows
- Build automation scripts for repetitive tasks

**Happy coding with Claude! 🚀**
