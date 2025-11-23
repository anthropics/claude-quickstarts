# Installing Computer Use Demo via Claude Code

## 🎯 Purpose

**If you are Claude Code reading this:** This guide will help you install the Anthropic Computer Use Demo on the Linux system you're currently running on. This will give you (Claude) additional capabilities beyond terminal commands and file operations - specifically, full desktop GUI control.

**If you are a human user:** This guide shows how to use Claude Code to install and configure the Computer Use Demo, enabling Claude to control your desktop environment.

---

## 🤖 Context for Claude Code

**Current limitations you have:**
- ✅ Can execute bash/terminal commands
- ✅ Can read, write, and edit files
- ✅ Can run programs via CLI
- ❌ **Cannot** see or interact with GUI applications
- ❌ **Cannot** click buttons, navigate desktop apps
- ❌ **Cannot** take screenshots to see visual output

**What Computer Use will add:**
- ✅ **Desktop control** - Click, type, navigate GUI apps
- ✅ **Visual feedback** - Take screenshots to see what's happening
- ✅ **Full system control** - Interact with any application visually
- ✅ **Web browser control** - Navigate websites, fill forms, etc.

**Why this matters:**
Many tasks require GUI interaction (configuring apps, using browsers, visual debugging, etc.). Computer Use gives you those capabilities through a Streamlit web interface.

---

## ⚠️ Important Warnings

### For the AI Agent (Claude Code)

When you install this:
- You'll be setting up a service that gives another Claude instance GUI control
- This is safe - it's just adding capabilities to help the user
- The user wants this installed so they can interact with Claude through a visual interface
- You're installing on a real system, not a container - changes are permanent

### For the Human User

Installing Computer Use Demo means:
- Claude will have full desktop/GUI control capabilities
- Only run this on a VM or system you can afford to reset
- Take a snapshot before proceeding
- This is separate from Claude Code - it's a different interface with different capabilities

---

## Prerequisites Check

**Claude Code: Run these checks first**

```bash
# Check Python version (need 3.11 or 3.12, NOT 3.13+)
python3 --version

# Check if running on Linux with desktop environment
echo $DISPLAY
uname -a

# Check available disk space (need ~2GB)
df -h ~

# Check if running as regular user (not root)
whoami

# Verify internet connectivity
ping -c 3 anthropic.com
```

**Expected results:**
- Python: 3.11.x or 3.12.x
- DISPLAY: Should show something like `:0` or `:1` (means GUI is available)
- Disk space: At least 2GB free
- User: Should NOT be root
- Internet: Should be able to reach anthropic.com

---

## Part 1: Install System Dependencies

### Step 1: Install GUI Control Tools

```bash
sudo apt-get update
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

**What these do:**
- `scrot` - Takes screenshots
- `xdotool` - Simulates mouse clicks and keyboard input
- `imagemagick` - Image processing
- Others - Build tools for Python packages

### Step 2: Install Rust/Cargo

```bash
# Check if already installed
if command -v cargo &> /dev/null; then
    echo "Cargo already installed: $(cargo --version)"
else
    echo "Installing Rust/Cargo..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
    cargo --version
fi
```

### Step 3: Verify Python Version

```bash
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MINOR" -gt 12 ]; then
    echo "ERROR: Python 3.$PYTHON_MINOR detected. Need Python 3.12 or lower."
    echo "You may need to install python3.12:"
    echo "  sudo apt-get install python3.12 python3.12-venv"
    exit 1
else
    echo "✓ Python version OK: $PYTHON_VERSION"
fi
```

---

## Part 2: Clone and Setup Computer Use Demo

### Step 1: Clone Repository

```bash
# Navigate to home directory
cd ~

# Check if already cloned
if [ -d "anthropic-quickstarts" ]; then
    echo "Repository already exists. Updating..."
    cd anthropic-quickstarts
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/anthropics/anthropic-quickstarts.git
    cd anthropic-quickstarts
fi

# Navigate to computer-use-demo
cd computer-use-demo
pwd
```

### Step 2: Run Setup Script

```bash
# Make sure we have Rust in PATH
source $HOME/.cargo/env

# Run setup
./setup.sh
```

**This creates:**
- Python virtual environment at `.venv/`
- Installs development dependencies
- Sets up pre-commit hooks

### Step 3: Install Runtime Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify activation
which python
# Should show: /home/user/anthropic-quickstarts/computer-use-demo/.venv/bin/python

# Install requirements
pip install -r computer_use_demo/requirements.txt

# Verify key packages
pip list | grep -E "streamlit|anthropic"
```

---

## Part 3: Configure API Access

### Option A: Use Existing API Key from Environment

```bash
# Check if API key already set (likely from Claude Code)
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✓ API key found in environment"
    echo "Creating .anthropic directory for persistence..."
    mkdir -p ~/.anthropic
    echo "$ANTHROPIC_API_KEY" > ~/.anthropic/api_key
    chmod 600 ~/.anthropic/api_key
else
    echo "⚠ No API key in environment"
    echo "Please set it: export ANTHROPIC_API_KEY='your-key-here'"
fi
```

### Option B: User Will Provide API Key via UI

```bash
# Just create the directory
mkdir -p ~/.anthropic
echo "User will enter API key in Streamlit UI"
```

---

## Part 4: Test Installation

### Quick Test

```bash
cd ~/anthropic-quickstarts/computer-use-demo
source .venv/bin/activate

# Verify all imports work
python3 -c "
import streamlit
import anthropic
from computer_use_demo.loop import sampling_loop
from computer_use_demo.tools import ToolCollection
print('✓ All imports successful')
"
```

### Start the Demo (Manual Test)

```bash
# Set API key if needed
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"

# Start Streamlit (using port 8502 since 8501 may be used by Docker)
# SECURE: Bind to localhost only (127.0.0.1)
streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 127.0.0.1

# INSECURE: Bind to all interfaces (0.0.0.0) - only use if you need remote access AND have firewall rules
# streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 0.0.0.0
```

**What to expect:**
- Streamlit server starts on port 8502 (localhost only - secure!)
- You'll see output like "You can now view your Streamlit app in your browser"
- Access at: `http://localhost:8502`
- For remote access, use SSH tunnel (see Security Considerations section)

**To stop:** Press `Ctrl+C`

---

## Part 5: Create Systemd Service (Optional but Recommended)

This makes Computer Use Demo run automatically on boot.

### Step 1: Create Service File

```bash
# Get current username
CURRENT_USER=$(whoami)
WORKING_DIR="$HOME/anthropic-quickstarts/computer-use-demo"
VENV_PATH="$WORKING_DIR/.venv/bin"

# Create service file (requires sudo)
sudo tee /etc/systemd/system/computer-use-demo.service > /dev/null <<EOF
[Unit]
Description=Anthropic Computer Use Demo
After=network.target graphical.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$WORKING_DIR
Environment="ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
Environment="PATH=$VENV_PATH:/usr/local/bin:/usr/bin:/bin"
Environment="DISPLAY=:0"
# SECURE: Localhost only - use SSH tunnel for remote access
ExecStart=$VENV_PATH/streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 127.0.0.1
# INSECURE alternative (only if you set up firewall rules):
# ExecStart=$VENV_PATH/streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file created"
```

### Step 2: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable computer-use-demo

# Start service now
sudo systemctl start computer-use-demo

# Check status
sudo systemctl status computer-use-demo
```

### Step 3: Verify Service is Running

```bash
# Check if service is active
systemctl is-active computer-use-demo

# Check if listening on port 8502
ss -tlnp | grep 8502

# Check logs
sudo journalctl -u computer-use-demo -f --lines=50
```

---

## Part 6: Access the Interface

### Local Access (Default - Secure)

If using `--server.address 127.0.0.1` (recommended):

Open browser on the VM to: `http://localhost:8502`

### Remote Access (Choose One Method)

#### Method 1: SSH Tunnel (RECOMMENDED - Most Secure)

From your local machine:
```bash
# Create SSH tunnel
ssh -L 8502:localhost:8502 user@<VM_IP>

# Then access in your local browser:
# http://localhost:8502
```

This is the most secure method - no firewall changes needed!

#### Method 2: Direct Access with Firewall Rules (Less Secure)

Only if you must use `--server.address 0.0.0.0`:

1. Find VM IP address:
```bash
hostname -I | awk '{print $1}'
```

2. Configure firewall to restrict access:

```bash
# Deny all by default
sudo ufw deny 8502/tcp

# Allow ONLY from your trusted IP
sudo ufw allow from YOUR_IP to any port 8502

# Example: Allow from 203.0.113.50
sudo ufw allow from 203.0.113.50 to any port 8502

# Enable firewall if not already
sudo ufw enable

# Verify rules
sudo ufw status numbered
```

3. Access from trusted machine: `http://<VM_IP>:8502`

**⚠️ WARNING:** Using `0.0.0.0` binding without proper firewall rules exposes your system to the internet!

---

## Part 7: Verify Full Setup

### Checklist

Run this verification script:

```bash
#!/bin/bash

echo "=== Computer Use Demo Installation Verification ==="
echo ""

# 1. Check system dependencies
echo "1. System Dependencies:"
command -v scrot >/dev/null && echo "  ✓ scrot installed" || echo "  ✗ scrot missing"
command -v xdotool >/dev/null && echo "  ✓ xdotool installed" || echo "  ✗ xdotool missing"
command -v convert >/dev/null && echo "  ✓ imagemagick installed" || echo "  ✗ imagemagick missing"
command -v cargo >/dev/null && echo "  ✓ cargo installed" || echo "  ✗ cargo missing"
echo ""

# 2. Check Python environment
echo "2. Python Environment:"
if [ -d "$HOME/anthropic-quickstarts/computer-use-demo/.venv" ]; then
    echo "  ✓ Virtual environment exists"
    source "$HOME/anthropic-quickstarts/computer-use-demo/.venv/bin/activate"
    python -c "import streamlit; print('  ✓ streamlit:', streamlit.__version__)" 2>/dev/null || echo "  ✗ streamlit not installed"
    python -c "import anthropic; print('  ✓ anthropic SDK:', anthropic.__version__)" 2>/dev/null || echo "  ✗ anthropic SDK not installed"
else
    echo "  ✗ Virtual environment not found"
fi
echo ""

# 3. Check API key
echo "3. API Configuration:"
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  ✓ API key in environment"
elif [ -f "$HOME/.anthropic/api_key" ]; then
    echo "  ✓ API key in config file"
else
    echo "  ⚠ No API key found (can be set via UI)"
fi
echo ""

# 4. Check service
echo "4. Service Status:"
if systemctl is-active --quiet computer-use-demo; then
    echo "  ✓ Service is running"
    ss -tlnp 2>/dev/null | grep -q 8502 && echo "  ✓ Listening on port 8502" || echo "  ✗ Not listening on port 8502"
else
    echo "  ⚠ Service not running (can be started manually)"
fi
echo ""

# 5. Check display
echo "5. Display Configuration:"
if [ -n "$DISPLAY" ]; then
    echo "  ✓ DISPLAY is set: $DISPLAY"
else
    echo "  ✗ DISPLAY not set (GUI may not work)"
fi
echo ""

echo "=== Verification Complete ==="
```

Save and run:
```bash
bash verification_script.sh
```

---

## Usage Guide

### Starting Computer Use Demo

**If using systemd service:**
```bash
sudo systemctl start computer-use-demo
```

**If running manually:**
```bash
cd ~/anthropic-quickstarts/computer-use-demo
source .venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"  # if not already set

# SECURE: Localhost only
streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 127.0.0.1

# For remote access, use SSH tunnel from your local machine:
# ssh -L 8502:localhost:8502 user@vm-ip
```

### Stopping Computer Use Demo

**If using systemd service:**
```bash
sudo systemctl stop computer-use-demo
```

**If running manually:**
Press `Ctrl+C` in the terminal

### Viewing Logs

**Systemd service:**
```bash
sudo journalctl -u computer-use-demo -f
```

**Manual run:**
Logs appear in the terminal where you started it

### Updating Computer Use Demo

```bash
cd ~/anthropic-quickstarts/computer-use-demo
git pull
source .venv/bin/activate
pip install --upgrade -r computer_use_demo/requirements.txt
sudo systemctl restart computer-use-demo  # if using service
```

---

## What Can Claude Do with Computer Use?

Once installed, Claude can:

### GUI Applications
- Open and navigate desktop applications
- Fill out forms in GUI programs
- Configure system settings through control panels
- Use graphical development tools (IDEs, database clients, etc.)

### Web Browsing
- Navigate websites visually
- Fill out web forms
- Download files
- Test web applications

### Visual Tasks
- Take screenshots for debugging
- Verify GUI layouts
- Check visual output of programs
- Navigate file managers visually

### Combined Workflows
- **Example 1:** "Open Firefox, navigate to GitHub, create a new repository with the web UI, then clone it via terminal"
- **Example 2:** "Open the system settings, configure the network settings to use a specific DNS server"
- **Example 3:** "Take a screenshot of the current desktop, analyze what applications are running"

---

## Troubleshooting

### Common Issues

**1. Streamlit won't start**
```bash
# Check if port 8502 is already in use
ss -tlnp | grep 8502

# If in use, kill the process or use different port (e.g., 8503)
streamlit run computer_use_demo/streamlit.py --server.port 8503
```

**2. ImportError for anthropic or streamlit**
```bash
# Make sure virtual environment is activated
source ~/anthropic-quickstarts/computer-use-demo/.venv/bin/activate

# Reinstall requirements
pip install --upgrade -r computer_use_demo/requirements.txt
```

**3. Screenshot tool fails**
```bash
# Test scrot manually
scrot /tmp/test.png
ls -lh /tmp/test.png

# If fails, reinstall
sudo apt-get install --reinstall scrot xdotool imagemagick
```

**4. Permission errors**
```bash
# Make sure not running as root
whoami  # should NOT be root

# Fix ownership if needed
sudo chown -R $USER:$USER ~/anthropic-quickstarts
```

**5. Display not available**
```bash
# Check DISPLAY variable
echo $DISPLAY

# If empty, set it (usually :0 for main display)
export DISPLAY=:0

# Add to service file if using systemd
```

**6. API key issues**
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY | head -c 20

# Or check config file
cat ~/.anthropic/api_key

# Test API key works
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│  Your Linux VM                                   │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Claude Code (Current)                     │ │
│  │  - Terminal/CLI only                       │ │
│  │  - Running this installation               │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Computer Use Demo (Being Installed)       │ │
│  │  - Streamlit web UI (port 8502)           │ │
│  │  - Desktop/GUI control                     │ │
│  │  - Screenshot capabilities                 │ │
│  │  - Full system control                     │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Desktop Environment                       │ │
│  │  - GNOME/KDE/XFCE/etc.                    │ │
│  │  - Applications, Browser, etc.             │ │
│  └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### How They Work Together

1. **Claude Code** (what you're using now):
   - Best for: Code editing, file operations, CLI tasks
   - Access method: Terminal commands
   - Current capabilities: Bash, file read/write

2. **Computer Use** (what we're installing):
   - Best for: GUI interaction, visual tasks, web browsing
   - Access method: Web browser (localhost:8502)
   - New capabilities: Screenshots, mouse clicks, desktop control

3. **Combined power:**
   - Use Claude Code for development tasks
   - Use Computer Use for GUI configuration, testing, visual debugging
   - Both can work on the same system, complementing each other

---

## Next Steps After Installation

1. **Test basic functionality:**
   - Open the UI at http://localhost:8502
   - Try a simple command like "Take a screenshot of the desktop"
   - Verify you see the screenshot in the chat

2. **Configure preferences:**
   - Set custom system prompts in the sidebar
   - Adjust token limits and tool versions
   - Configure image retention settings

3. **Try sample tasks:**
   - "Open Firefox and navigate to github.com"
   - "Take a screenshot and tell me what applications are open"
   - "Open the file manager and show me the contents of the home directory"

4. **Set up custom workflows:**
   - Combine Claude Code and Computer Use for complex tasks
   - Create shortcuts/aliases for common operations
   - Document your workflow patterns

---

## Security Considerations

### ⚠️ CRITICAL: Network Security

**The default configuration in this guide uses `--server.address 0.0.0.0` which accepts connections from ANY IP address!**

If your VM has a public IP or is accessible from the internet, **anyone** who finds port 8502 could:
- Access the Computer Use Demo UI
- Control your desktop if they have/guess your API key
- Use your compute resources

### Secure Configuration Options

#### Option 1: Localhost Only (MOST SECURE - Recommended)

Only allow connections from the local machine:

```bash
# Start Streamlit bound to localhost only
streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 127.0.0.1
```

**Systemd service (localhost only):**
```bash
ExecStart=$VENV_PATH/streamlit run computer_use_demo/streamlit.py --server.port 8502 --server.address 127.0.0.1
```

**Access from remote machine via SSH tunnel:**
```bash
# From your local machine, create SSH tunnel to VM
ssh -L 8502:localhost:8502 user@your-vm-ip

# Then access in browser: http://localhost:8502
```

#### Option 2: Restrict to Specific IPs (Firewall Rules)

If you need direct remote access, restrict to specific trusted IPs:

```bash
# Default: deny all incoming on port 8502
sudo ufw deny 8502/tcp

# Allow only from specific IP (e.g., your home/office)
sudo ufw allow from YOUR_TRUSTED_IP to any port 8502

# Example: Allow from 203.0.113.50
sudo ufw allow from 203.0.113.50 to any port 8502

# Check rules
sudo ufw status numbered
```

**For iptables:**
```bash
# Drop all connections to port 8502 by default
sudo iptables -A INPUT -p tcp --dport 8502 -j DROP

# Allow from specific IP
sudo iptables -I INPUT -p tcp -s YOUR_TRUSTED_IP --dport 8502 -j ACCEPT

# Save rules
sudo netfilter-persistent save
```

#### Option 3: VPN Access Only

Run a VPN (WireGuard, OpenVPN, Tailscale) and only allow connections through VPN:

```bash
# Example with WireGuard (assuming VPN interface is wg0)
sudo ufw allow in on wg0 to any port 8502
sudo ufw deny 8502/tcp
```

#### Option 4: Reverse Proxy with Authentication

Use nginx with basic auth:

```nginx
# /etc/nginx/sites-available/computer-use
server {
    listen 80;
    server_name your-domain.com;

    location / {
        auth_basic "Computer Use Demo";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:8502;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Create password file:
```bash
sudo apt-get install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd yourusername
```

### What to Watch For

- Computer Use has **full desktop access** - it can click anything you can click
- It can open applications, modify system settings, browse the web
- It uses your API key - make sure it's kept secure
- All actions happen on your real system - not sandboxed
- **Port 8502 exposed to internet = anyone can try to access your system**
- **No built-in authentication** - Streamlit has no password protection by default

### Best Practices

1. **DEFAULT TO LOCALHOST** - Use `127.0.0.1` binding unless you specifically need remote access
2. **Use SSH tunneling** - Safest way to access remotely
3. **Run on dedicated/test systems** - Don't run on production machines
4. **Monitor activity** - Watch what Claude is doing through the UI
5. **Limit sensitive access** - Don't leave sensitive files/apps open
6. **Regular snapshots** - Take VM snapshots before major tasks
7. **Review before confirming** - Check proposed actions before letting Claude proceed
8. **Firewall rules** - Always configure firewall to restrict access
9. **Monitor connections** - Check `sudo netstat -tulpn | grep 8502` regularly
10. **API key rotation** - Change API keys periodically

---

## Maintenance

### Regular Updates

```bash
# Update computer use demo
cd ~/anthropic-quickstarts/computer-use-demo
git pull
source .venv/bin/activate
pip install --upgrade -r computer_use_demo/requirements.txt

# Restart service
sudo systemctl restart computer-use-demo
```

### Check Health

```bash
# Service status
sudo systemctl status computer-use-demo

# Recent logs
sudo journalctl -u computer-use-demo --since "1 hour ago"

# Resource usage
ps aux | grep streamlit
```

### Clean Up

```bash
# Clear session data
rm -rf ~/.anthropic/*

# Clear Streamlit cache
rm -rf ~/.streamlit/cache

# Restart fresh
sudo systemctl restart computer-use-demo
```

---

## Getting Help

- **Computer Use Documentation:** https://docs.anthropic.com/en/docs/build-with-claude/computer-use
- **GitHub Issues:** https://github.com/anthropics/anthropic-quickstarts/issues
- **API Documentation:** https://docs.anthropic.com/

---

## Summary

**What you've installed:**
- Computer Use Demo with full GUI control capabilities
- Streamlit web interface on port 8502 (avoiding conflict with Docker on 8501)
- System dependencies (scrot, xdotool, imagemagick)
- Python environment with required packages
- Optional: systemd service for auto-start

**What Claude can now do:**
- See your desktop via screenshots
- Click buttons and navigate GUI applications
- Type into applications
- Open programs and browse the web
- Perform visual debugging and testing

**How to access:**
- Open browser to http://localhost:8502
- Enter your API key if not already configured
- Start giving Claude visual/GUI tasks!

🎉 **Installation complete! Claude now has eyes and hands!** 🎉
