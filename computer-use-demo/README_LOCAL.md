# Running Computer Use Demo Locally with Playwright

This guide explains how to run the Computer Use Demo locally using Playwright for browser automation instead of Docker.

## Setup

1. **Create and activate a virtual environment** (if not already done):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
```

2. **Install the package in development mode**:
```bash
pip install -e .
```

3. **Install Playwright browsers**:
```bash
python -m playwright install chromium
```

4. **Set your API key**:
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Running the Application

Use the local runner script:
```bash
python run_local.py
```

Or run directly with streamlit:
```bash
export USE_LOCAL_BROWSER=true
export PYTHONPATH=/Users/bassil/code/claude-quickstarts-private/computer-use-demo
streamlit run computer_use_demo/streamlit.py
```

## Features

- **Persistent Browser**: The browser instance stays alive between messages
- **Local Execution**: Runs on your local machine, not in Docker
- **Visual Feedback**: Browser runs in non-headless mode so you can see what's happening
- **Navigate Action**: Currently supports navigating to URLs

## How It Works

When you send a message:
1. The browser tool initializes (if not already running)
2. A Chromium browser window opens
3. Your action is executed (e.g., navigating to a URL)
4. A screenshot is taken and returned
5. The browser stays open for the next message

The browser maintains state between messages, so if you navigate to a page in one message, the next message continues from that same page.

## Troubleshooting

If you get import errors:
1. Make sure you're in the virtual environment
2. Install the package with `pip install -e .`
3. Set PYTHONPATH: `export PYTHONPATH=/Users/bassil/code/claude-quickstarts-private/computer-use-demo`

If Playwright browsers aren't installed:
```bash
python -m playwright install chromium
```

## Differences from Docker Version

- Runs locally on your machine
- Uses Playwright instead of xdotool
- Browser window is visible
- Faster startup time
- No need for Docker or VNC