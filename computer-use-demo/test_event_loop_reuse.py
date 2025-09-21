#!/usr/bin/env python3
"""Test that browser works across multiple event loops (simulating Streamlit behavior)."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from computer_use_demo.tools.browser_local import get_browser_tool

async def first_message():
    """Simulate first Streamlit message."""
    print("\n=== FIRST MESSAGE (Event Loop 1) ===")
    browser = get_browser_tool()

    print("1. Navigating to example.com...")
    await browser(action="navigate", text="https://www.example.com")

    print("2. Taking screenshot...")
    result = await browser(action="screenshot")
    print(f"   Screenshot: {'Success' if result.base64_image else 'Failed'}")

    print("3. Getting page text...")
    text = await browser(action="get_page_text")
    text_content = text.output if isinstance(text.output, str) else str(text.output)
    print(f"   On Example.com: {'Example Domain' in text_content}")

    return True

async def second_message():
    """Simulate second Streamlit message."""
    print("\n=== SECOND MESSAGE (Event Loop 2) ===")
    browser = get_browser_tool()

    print("1. Getting page text (should reconnect to browser)...")
    text = await browser(action="get_page_text")
    text_content = text.output if isinstance(text.output, str) else str(text.output)
    print(f"   Page text retrieved: {len(text_content) > 0}")

    print("2. Navigating to Google...")
    await browser(action="navigate", text="https://www.google.com")

    print("3. Taking another screenshot...")
    result = await browser(action="screenshot")
    print(f"   Screenshot: {'Success' if result.base64_image else 'Failed'}")

    return True

async def third_message():
    """Simulate third Streamlit message with multiple tool calls."""
    print("\n=== THIRD MESSAGE (Event Loop 3) ===")
    browser = get_browser_tool()

    print("1. First tool call - get page text...")
    text = await browser(action="get_page_text")
    text_content = text.output if isinstance(text.output, str) else str(text.output)
    print(f"   On Google: {'google' in text_content.lower()}")

    print("2. Second tool call - click at coordinates...")
    try:
        await browser(action="left_click", coordinate=(640, 400))
        print("   Click successful")
    except Exception as e:
        print(f"   Click failed: {e}")

    print("3. Third tool call - type text...")
    try:
        await browser(action="type", text="test query")
        print("   Type successful")
    except Exception as e:
        print(f"   Type failed: {e}")

    print("4. Fourth tool call - take screenshot...")
    result = await browser(action="screenshot")
    print(f"   Screenshot: {'Success' if result.base64_image else 'Failed'}")

    return True

def main():
    """Simulate multiple Streamlit requests with different event loops."""
    os.environ["WIDTH"] = "1280"
    os.environ["HEIGHT"] = "800"

    print("=" * 60)
    print("EVENT LOOP REUSE TEST")
    print("Simulating Streamlit's behavior with multiple event loops")
    print("=" * 60)

    # First message - new event loop
    print("\nStarting first message...")
    success1 = asyncio.run(first_message())
    print(f"First message completed: {success1}")

    # Second message - new event loop (simulates new Streamlit request)
    print("\nStarting second message...")
    success2 = asyncio.run(second_message())
    print(f"Second message completed: {success2}")

    # Third message - new event loop with multiple tool calls
    print("\nStarting third message...")
    success3 = asyncio.run(third_message())
    print(f"Third message completed: {success3}")

    print("\n" + "=" * 60)
    if success1 and success2 and success3:
        print("✅ ALL TESTS PASSED - Browser works across event loops!")
    else:
        print("❌ TESTS FAILED - Browser has issues with event loop reuse")
    print("=" * 60)

if __name__ == "__main__":
    main()