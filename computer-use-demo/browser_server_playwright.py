#!/usr/bin/env python3
"""Browser server using Playwright's persistent context for better coordination."""

import asyncio
import os
import sys
import signal
from pathlib import Path
from playwright.async_api import async_playwright

# Global variables to maintain browser state
playwright_instance = None
browser = None
context = None
page = None

async def start_browser():
    """Start and maintain a persistent Playwright browser."""
    global playwright_instance, browser, context, page

    print("[BrowserServer] Starting Playwright browser with persistent context...")

    # Get dimensions from environment
    width = int(os.environ.get("WIDTH", "1280"))
    height = int(os.environ.get("HEIGHT", "800"))

    try:
        # Start Playwright
        playwright_instance = await async_playwright().start()

        # Launch browser with persistent context
        # Using launch_persistent_context ensures the browser stays open and maintains state
        user_data_dir = Path("/tmp/playwright-persistent-context")
        user_data_dir.mkdir(exist_ok=True)

        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport={"width": width, "height": height},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={width},{height}",
                "--remote-debugging-port=9223",  # Different port to avoid conflicts
            ],
            ignore_default_args=["--enable-automation"],
        )

        print(f"[BrowserServer] Browser launched with viewport {width}x{height}")

        # Get or create a page
        if context.pages:
            page = context.pages[0]
            print("[BrowserServer] Using existing page")
        else:
            page = await context.new_page()
            print("[BrowserServer] Created new page")

        # Navigate to blank page
        await page.goto("about:blank")

        print("[BrowserServer] Browser ready with persistent context")
        print("[BrowserServer] CDP available on port 9223")
        print("[BrowserServer] Press Ctrl+C to stop")

        # Keep the browser running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[BrowserServer] Shutting down...")
    except Exception as e:
        print(f"[BrowserServer] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if context:
            await context.close()
        if playwright_instance:
            await playwright_instance.stop()
        print("[BrowserServer] Browser server stopped")

def main():
    """Main entry point."""
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n[BrowserServer] Received interrupt signal")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the async browser
    try:
        asyncio.run(start_browser())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()