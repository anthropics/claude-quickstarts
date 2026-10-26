"""
Configuration management for Autonomous Agent.

Config is loaded from (in order of precedence):
1. Command-line arguments
2. Local .autonomous-agent.yaml
3. Global ~/.config/autonomous-agent/config.yaml
4. Built-in defaults
"""

import os
from pathlib import Path
from typing import Any

import yaml

# Default configuration
DEFAULT_CONFIG = {
    "model": "claude-opus-4-5-20251101",
    "auto_continue_delay": 3,
    "max_turns": 1000,
    "security": {
        "sandbox_enabled": True,
        "allowed_commands": [
            # File inspection
            "ls", "cat", "head", "tail", "wc", "grep", "find",
            # File operations
            "cp", "mkdir", "chmod", "mv", "rm",
            # Directory
            "pwd", "cd",
            # Node.js
            "npm", "npx", "node", "yarn", "pnpm",
            # Python
            "python", "python3", "pip", "uv", "pytest",
            # Version control
            "git",
            # Process management
            "ps", "lsof", "sleep", "pkill",
            # Common tools
            "curl", "wget", "jq", "tree",
            # Shell utilities
            "echo", "touch", "env", "which", "basename", "dirname",
        ],
    },
    "cost_limits": {
        "warn_at_usd": 10.0,
        "stop_at_usd": 50.0,
    },
}

CONFIG_FILENAME = "autonomous-agent.yaml"
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "autonomous-agent"
LOCAL_CONFIG_FILE = Path(f".{CONFIG_FILENAME}")


def find_config_file() -> Path | None:
    """Find the config file to use."""
    # Check local directory first
    if LOCAL_CONFIG_FILE.exists():
        return LOCAL_CONFIG_FILE

    # Check global config
    global_config = GLOBAL_CONFIG_DIR / "config.yaml"
    if global_config.exists():
        return global_config

    return None


def load_config() -> dict[str, Any]:
    """Load configuration from file, merged with defaults."""
    config = DEFAULT_CONFIG.copy()

    config_file = find_config_file()
    if config_file:
        with open(config_file) as f:
            user_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, user_config)

    # Environment variable overrides
    if api_key := os.environ.get("ANTHROPIC_API_KEY"):
        config["api_key"] = api_key

    if model := os.environ.get("AUTONOMOUS_AGENT_MODEL"):
        config["model"] = model

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def init_config(global_config: bool = False) -> Path:
    """Create a new config file with defaults."""
    if global_config:
        config_dir = GLOBAL_CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
    else:
        config_path = LOCAL_CONFIG_FILE

    config_content = f"""# Autonomous Agent Configuration
# https://github.com/anthropics/claude-quickstarts/autonomous-coding

# Claude model to use
model: {DEFAULT_CONFIG['model']}

# Seconds to wait between sessions
auto_continue_delay: {DEFAULT_CONFIG['auto_continue_delay']}

# Security settings
security:
  sandbox_enabled: true
  # Add project-specific commands here
  allowed_commands:
    - ls
    - cat
    - head
    - tail
    - grep
    - npm
    - node
    - git
    - python
    - python3
    - pytest
    # Add more as needed for your project
    # - docker
    # - kubectl
    # - make

# Cost controls (USD)
cost_limits:
  warn_at_usd: 10.0
  stop_at_usd: 50.0
"""

    config_path.write_text(config_content)
    return config_path


def get_allowed_commands(config: dict[str, Any] | None = None) -> set[str]:
    """Get the set of allowed bash commands."""
    if config is None:
        config = load_config()
    return set(config.get("security", {}).get("allowed_commands", DEFAULT_CONFIG["security"]["allowed_commands"]))
