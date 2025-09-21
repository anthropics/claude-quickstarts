#!/usr/bin/env python3
"""Browser server that runs a persistent browser instance with CDP."""

import subprocess
import time
import signal
import sys
import os

def main():
    """Run a persistent Chrome instance with CDP enabled."""
    print("[BrowserServer] Starting Chrome with CDP enabled...")

    # Find Chrome/Chromium executable
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]

    chrome_exe = None
    for path in chrome_paths:
        if os.path.exists(path) or subprocess.run(["which", path], capture_output=True).returncode == 0:
            chrome_exe = path
            break

    if not chrome_exe:
        print("[BrowserServer] Error: Could not find Chrome/Chromium executable")
        sys.exit(1)

    print(f"[BrowserServer] Using Chrome at: {chrome_exe}")

    # Start Chrome with remote debugging
    cmd = [
        chrome_exe,
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=/tmp/chrome-user-data",
        "--disable-blink-features=AutomationControlled",
        "about:blank"
    ]

    try:
        # Start Chrome process
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Give Chrome a moment to start
        time.sleep(1)

        # Check if Chrome started successfully
        if process.poll() is not None:
            print("[BrowserServer] Error: Chrome failed to start")
            sys.exit(1)

        print("[BrowserServer] Chrome started with CDP on port 9222")
        print("[BrowserServer] CDP URL: http://127.0.0.1:9222")
        print("[BrowserServer] Browser server ready. Press Ctrl+C to stop.")

        # Keep running until interrupted
        process.wait()

    except KeyboardInterrupt:
        print("\n[BrowserServer] Shutting down...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[BrowserServer] Browser server stopped.")
    except Exception as e:
        print(f"[BrowserServer] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    main()