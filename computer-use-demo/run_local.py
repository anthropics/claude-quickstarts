#!/usr/bin/env python3
"""
Local runner for the computer use demo with Playwright browser.
This script runs the Streamlit app locally without Docker, using Playwright for browser automation.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add the current directory to Python path so imports work
sys.path.insert(0, str(Path(__file__).parent))

def setup_environment():
    """Set up environment variables for local execution."""
    # Set default display dimensions
    os.environ.setdefault("WIDTH", "1280")
    os.environ.setdefault("HEIGHT", "800")

    # Set API provider (can be overridden)
    os.environ.setdefault("API_PROVIDER", "anthropic")

    # Enable local browser mode
    os.environ["USE_LOCAL_BROWSER"] = "true"

    print("Environment configured for local execution:")
    print(f"  Display: {os.environ['WIDTH']}x{os.environ['HEIGHT']}")
    print(f"  API Provider: {os.environ['API_PROVIDER']}")
    print(f"  Browser Mode: Local (Playwright)")

def install_playwright_browsers():
    """Install Playwright browsers if not already installed."""
    print("\nChecking Playwright browsers...")
    try:
        subprocess.run(
            ["python", "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True
        )
        print("Playwright browsers are ready.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Playwright browsers: {e}")
        print("Please run: python -m playwright install chromium")
        sys.exit(1)

def start_browser_server():
    """Start the browser server in the background."""
    print("\nStarting browser server...")

    # Try the new Playwright server first, fallback to old one
    browser_server_path = Path(__file__).parent / "browser_server_playwright.py"
    use_playwright_server = browser_server_path.exists()

    if not use_playwright_server:
        browser_server_path = Path(__file__).parent / "browser_server.py"

    if not browser_server_path.exists():
        print(f"Warning: Browser server script not found at {browser_server_path}")
        print("The browser tool will launch its own browser for each session.")
        return None

    try:
        # Start browser server as a subprocess (non-blocking)
        process = subprocess.Popen(
            ["python", str(browser_server_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ}  # Pass environment variables including WIDTH/HEIGHT
        )

        # Give browser time to start
        if use_playwright_server:
            print("  Launching Playwright browser with persistent context...")
        else:
            print("  Launching Chrome browser...")
        time.sleep(3)  # Give a bit more time for Playwright

        # Check if process is still running
        if process.poll() is not None:
            print("Browser server failed to start")
            return None

        # Set the CDP endpoint
        if use_playwright_server:
            cdp_url = "http://127.0.0.1:9223"  # Playwright server uses port 9223
        else:
            cdp_url = "http://127.0.0.1:9222"  # Chrome CDP uses port 9222

        os.environ["BROWSER_CDP_URL"] = cdp_url
        print(f"\n✅ Browser server ready at {cdp_url}")

        return process

    except Exception as e:
        print(f"Error starting browser server: {e}")
        print("The browser tool will launch its own browser for each session.")
        return None

def run_streamlit(browser_process):
    """Run the Streamlit application."""
    print("\nStarting Streamlit application...")
    print("➡️  Open http://localhost:8501 in your browser to begin")
    print("\nPress Ctrl+C to stop the server\n")

    # Change to the correct directory
    os.chdir(Path(__file__).parent)

    # Set PYTHONPATH to include current directory
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)

    streamlit_path = Path(__file__).parent / "computer_use_demo" / "streamlit.py"

    try:
        subprocess.run(
            ["streamlit", "run", str(streamlit_path)],
            check=True,
            env=env
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
        sys.exit(1)
    finally:
        # Clean up browser server if running
        if browser_process:
            print("Stopping browser server...")
            browser_process.terminate()
            try:
                browser_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser_process.kill()
            print("Browser server stopped.")

def main():
    """Main entry point."""
    print("🚀 Computer Use Demo - Local Mode with Playwright")
    print("=" * 50)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  Warning: ANTHROPIC_API_KEY not set!")
        print("Please set your API key: export ANTHROPIC_API_KEY=your_key_here")
        print()

    setup_environment()
    install_playwright_browsers()

    # Start browser server
    browser_process = start_browser_server()

    # Run Streamlit (will clean up browser server on exit)
    run_streamlit(browser_process)

if __name__ == "__main__":
    main()