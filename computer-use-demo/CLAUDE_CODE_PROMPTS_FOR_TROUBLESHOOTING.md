# Claude Code Prompts for Computer Use Demo Troubleshooting

This document contains optimized prompts you can give to Claude Code to automatically fix common Computer Use Demo issues.

---

## 🔧 Quick Fix: Suppress D-Bus Errors (Headless Operation)

**Symptom:** Seeing many errors like:
```
ERROR:dbus/bus.cc:408] Failed to connect to the bus: Could not parse server address
```

**Prompt for Claude Code:**

```
I'm running the Anthropic Computer Use Demo in headless mode (no physical desktop), and I'm seeing D-Bus connection errors flooding the logs. These errors are cosmetic but noisy.

Please fix this by:
1. Installing Xvfb (virtual X server) if not already installed
2. Updating the systemd service at /etc/systemd/system/computer-use-demo.service to:
   - Set DISPLAY=:99
   - Set DBUS_SESSION_BUS_ADDRESS=/dev/null to suppress D-Bus errors
   - Add ExecStartPre commands to start Xvfb on display :99
   - Keep the existing --server.port 8502 and --server.address settings
3. Reload systemd and restart the service
4. Verify it's working by checking the service status and recent logs

Current service file location: /etc/systemd/system/computer-use-demo.service
Python venv location: ~/anthropic-quickstarts/computer-use-demo/.venv
Working directory: ~/anthropic-quickstarts/computer-use-demo

Show me the changes you're making and confirm when complete.
```

---

## 🔒 Security Fix: Switch from 0.0.0.0 to Localhost Binding

**Symptom:** Computer Use Demo is accessible from any IP address (security risk)

**Prompt for Claude Code:**

```
The Computer Use Demo is currently binding to 0.0.0.0 which exposes it to the network. I need to secure this by binding to localhost only (127.0.0.1).

Please:
1. Check how Streamlit is currently bound using: sudo ss -tlnp | grep 8502
2. Update the systemd service at /etc/systemd/system/computer-use-demo.service to use --server.address 127.0.0.1
3. Keep port 8502
4. Add DBUS_SESSION_BUS_ADDRESS=/dev/null and Xvfb setup for headless operation
5. Reload systemd and restart the service
6. Verify it's now bound to 127.0.0.1 only
7. Show me how to access it via SSH tunnel from my local machine

Working directory: ~/anthropic-quickstarts/computer-use-demo
Python venv: ~/anthropic-quickstarts/computer-use-demo/.venv
```

---

## 🌐 Security Fix: Add Firewall Rules (Keep 0.0.0.0 binding but restrict IPs)

**Symptom:** Need remote access via IP but want to restrict to specific trusted IPs

**Prompt for Claude Code:**

```
I'm running Computer Use Demo with --server.address 0.0.0.0 for remote access, but I need to restrict access to only my trusted IP address.

Please:
1. Check if ufw (firewall) is installed, install if needed
2. Configure ufw to:
   - Deny all incoming connections to port 8502 by default
   - Allow connections ONLY from IP: [YOUR_TRUSTED_IP_HERE] to port 8502
   - Allow SSH (port 22) with rate limiting to prevent lockout
3. Enable the firewall
4. Show me the active firewall rules
5. Test that the service is still accessible from the allowed IP
6. Provide the exact command I should use to add additional trusted IPs in the future

Current port: 8502
Replace [YOUR_TRUSTED_IP_HERE] with my actual IP when you find it or ask me for it.
```

---

## 🖼️ Fix Screenshot Cursor Warning

**Symptom:** "scrot: Failed to get mouse cursor image" warning

**Prompt for Claude Code:**

```
I'm seeing "scrot: Failed to get mouse cursor image" warnings when Computer Use Demo takes screenshots. The screenshots still work but I want to suppress this warning.

This is a cosmetic issue - scrot can't capture the mouse cursor in headless/VNC environments but screenshots still work.

Please:
1. Verify scrot is installed and working: scrot /tmp/test.png
2. Check if the warning is just cosmetic (file is created successfully)
3. Add a note to the troubleshooting documentation explaining this is safe to ignore
4. Optionally: Check if there's a scrot flag to suppress cursor capture warnings

Location: ~/anthropic-quickstarts/computer-use-demo
```

---

## 🚀 Complete Headless Setup (All-in-One Fix)

**Symptom:** Multiple issues - D-Bus errors, accessibility concerns, want secure remote access

**Prompt for Claude Code:**

```
I need to set up the Anthropic Computer Use Demo for optimal headless operation with security best practices.

Requirements:
- Suppress D-Bus errors (cosmetic noise from headless operation)
- Use Xvfb for virtual X server
- Bind to localhost (127.0.0.1) for security
- Port 8502 (8501 is used by Docker)
- Enable systemd service for auto-start
- Show me how to access remotely via SSH tunnel

Please:
1. Install required packages: xvfb
2. Create/update systemd service at /etc/systemd/system/computer-use-demo.service with:
   - User: $(whoami)
   - WorkingDirectory: $HOME/anthropic-quickstarts/computer-use-demo
   - Environment variables: ANTHROPIC_API_KEY, DISPLAY=:99, DBUS_SESSION_BUS_ADDRESS=/dev/null
   - ExecStartPre: Start Xvfb on :99 (kill existing first)
   - ExecStart: Streamlit with --server.port 8502 --server.address 127.0.0.1
   - Restart policy: always
3. Enable and start the service
4. Verify it's running and bound correctly
5. Show me:
   - Service status
   - How to check logs
   - SSH tunnel command for remote access
   - How to verify security (port binding)

Current setup:
- Repo: ~/anthropic-quickstarts/computer-use-demo
- Python venv: ~/anthropic-quickstarts/computer-use-demo/.venv
- API key: Use $ANTHROPIC_API_KEY environment variable
```

---

## 🔍 Diagnostic: Check Current Configuration

**Prompt for Claude Code:**

```
I need a complete diagnostic of my Computer Use Demo installation to understand the current state and identify any issues.

Please check and report:
1. Service status: systemctl status computer-use-demo
2. How Streamlit is bound: sudo ss -tlnp | grep 8502 (listening on 0.0.0.0 or 127.0.0.1?)
3. Recent service logs: sudo journalctl -u computer-use-demo -n 50
4. Firewall rules: sudo ufw status numbered (if ufw is installed)
5. Active connections: sudo ss -tnp | grep 8502
6. DISPLAY environment: Check what DISPLAY the service is using
7. D-Bus configuration: Check DBUS_SESSION_BUS_ADDRESS setting
8. Xvfb status: ps aux | grep Xvfb
9. Security assessment: Is the service exposed to the network?
10. Recommendations: What should be fixed?

Create a summary report with:
- Current state (secure/insecure, working/broken)
- Issues found
- Recommended actions
- Priority (critical/high/medium/low)
```

---

## 📝 Create Firewall Rules for Multiple Trusted IPs

**Prompt for Claude Code:**

```
I need to allow multiple trusted IPs to access Computer Use Demo on port 8502 while blocking all other connections.

Trusted IPs to allow:
- [IP_1] - My home network
- [IP_2] - My office network
- [IP_3] - My VPN exit node

Please:
1. Install ufw if not present
2. Set default policy: deny incoming, allow outgoing
3. Allow SSH (port 22) with rate limiting
4. Deny all traffic to port 8502 by default
5. Add allow rules for each trusted IP above to port 8502
6. Enable the firewall
7. Show me the final rules with: sudo ufw status numbered
8. Test that the service is accessible from allowed IPs
9. Provide a template command for adding more IPs later

Port: 8502
Service: computer-use-demo

Replace [IP_X] placeholders with actual IPs or ask me for them.
```

---

## 🚫 Fix Chrome Sandbox Error (Running as Root)

**Symptom:** Error message: "Running as root without --no-sandbox is not supported"

**Prompt for Claude Code:**

```
I'm seeing this error from the Computer Use Demo:
"ERROR:zygote_host_impl_linux.cc:101] Running as root without --no-sandbox is not supported"

This means the systemd service is running as root, which is insecure and causes Chrome to fail.

Please fix this by:
1. Check what user the computer-use-demo service is running as: sudo systemctl show computer-use-demo | grep User
2. If it's running as root or not set:
   - Update the systemd service at /etc/systemd/system/computer-use-demo.service
   - Change User= to use my current username ($(whoami))
   - Ensure all paths use /home/USERNAME not /root
3. Verify file permissions: ensure the venv and working directory are owned by the correct user
4. Reload systemd and restart the service
5. Verify it's now running as non-root user
6. Test that the error is gone by checking recent logs

Service location: /etc/systemd/system/computer-use-demo.service
Working directory: ~/anthropic-quickstarts/computer-use-demo

Show me what changes you're making and confirm when the service is running as a non-root user.
```

---

## 🔄 Restart and Reset: Nuclear Option

**Prompt for Claude Code:**

```
The Computer Use Demo is misbehaving and I need a clean restart.

Please:
1. Stop the computer-use-demo service
2. Kill any stray Xvfb or Streamlit processes
3. Clear any temporary files or caches
4. Restart the service
5. Verify it started correctly
6. Show me:
   - Service status
   - Recent logs (last 20 lines)
   - Port binding status
   - Any errors

Location: ~/anthropic-quickstarts/computer-use-demo
Service: computer-use-demo

If restart doesn't fix issues, suggest next troubleshooting steps.
```

---

## 🔑 Update API Key in Service

**Prompt for Claude Code:**

```
I need to update the ANTHROPIC_API_KEY in the Computer Use Demo systemd service.

Please:
1. Check the current service configuration
2. Update /etc/systemd/system/computer-use-demo.service to use the environment variable from my current shell ($ANTHROPIC_API_KEY)
3. Ensure the API key is NOT hardcoded in the service file (use the environment variable)
4. Reload systemd daemon
5. Restart the service
6. Verify the service is running with the new key
7. Remind me to also update ~/.anthropic/api_key for persistence

Do NOT display the actual API key in your output for security.
```

---

## 📊 Performance Check: Monitor Resource Usage

**Prompt for Claude Code:**

```
I want to monitor the Computer Use Demo's resource usage and performance.

Please check and report:
1. CPU and memory usage of Streamlit process
2. CPU and memory usage of Xvfb process (if running)
3. Disk space used by ~/anthropic-quickstarts/computer-use-demo
4. Disk space used by ~/.anthropic directory
5. Number of active connections to port 8502
6. Log file sizes
7. Any processes consuming excessive resources

Provide recommendations if:
- Memory usage > 2GB
- CPU usage consistently > 50%
- Disk space > 5GB
- Too many log files accumulating

Create a performance summary report.
```

---

## 🔧 Migrate from Docker to VM-Based Setup

**Prompt for Claude Code:**

```
I'm currently running Computer Use Demo in Docker but want to migrate to a VM-based installation.

Current Docker setup uses port 8501.
Target VM setup should use port 8502.

Please help me:
1. Verify the VM-based installation is complete at ~/anthropic-quickstarts/computer-use-demo
2. Ensure it's configured for port 8502 (not 8501)
3. Set up systemd service for auto-start
4. Configure for headless operation (Xvfb + D-Bus suppression)
5. Bind to localhost for security
6. Show me how to:
   - Stop the Docker container
   - Start the VM-based service
   - Access both if I want to run them simultaneously (different ports)
   - Migrate any configuration from Docker to VM

Provide a migration checklist and rollback plan.
```

---

## 🎯 Usage Tips for These Prompts

### How to Use:

1. **Copy the entire prompt** from the relevant section above
2. **Paste directly into Claude Code** via terminal or chat
3. **Replace placeholders** like `[YOUR_TRUSTED_IP_HERE]` with actual values
4. **Let Claude Code execute** - it will read files, make changes, and verify

### Prompt Design Principles Used:

- ✅ **Specific context**: Exact file paths, service names, ports
- ✅ **Clear objectives**: What needs to be fixed and why
- ✅ **Step-by-step**: Ordered list of actions to take
- ✅ **Verification**: Always asks for confirmation and testing
- ✅ **Safety**: Asks for review before applying changes
- ✅ **Documentation**: Requests explanation of what was done

### Best Practices:

1. **Review changes**: Claude Code will show you what it's doing - review before confirming
2. **One issue at a time**: Use specific prompts rather than combining multiple fixes
3. **Keep context**: Mention current state, working directory, and any custom configurations
4. **Test after changes**: Verify the fix worked before moving to the next issue
5. **Backup first**: Take VM snapshot before major changes

### Customization:

You can extend these prompts by adding:
- Your specific error messages
- Custom file paths
- Additional requirements
- Logging preferences
- Monitoring needs

---

## 📚 Related Documentation

- Main installation guide: `SETUP_COMPUTER_USE_FROM_CLAUDE_CODE.md`
- Security considerations: See Security section in installation guide
- Official docs: https://docs.anthropic.com/en/docs/build-with-claude/computer-use

---

## 🆘 Emergency Recovery Prompt

**When everything is broken:**

```
Something is seriously wrong with the Computer Use Demo and I need to diagnose and fix it.

Current symptoms: [DESCRIBE WHAT'S BROKEN]

Please:
1. Run full diagnostic (service status, logs, processes, ports, firewall)
2. Identify root cause
3. Propose fix with step-by-step plan
4. Show me rollback steps in case fix makes things worse
5. Create a backup of current configuration before changing anything
6. Execute the fix
7. Verify everything works
8. Document what went wrong and how you fixed it

Location: ~/anthropic-quickstarts/computer-use-demo
Be thorough - I need this working ASAP but don't want to break it further.
```

---

*Last updated: 2025-11-23*
*Compatible with: Computer Use Demo (Claude Sonnet 4.5, computer_use_20250124 tools)*
