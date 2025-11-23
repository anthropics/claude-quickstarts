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
