#!/usr/bin/env python3
"""Test that browser persists across multiple tool calls."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from computer_use_demo.tools.browser_local import get_browser_tool

async def test_browser_persistence():
    """Test that browser state persists across multiple tool instances."""

    os.environ["WIDTH"] = "1280"
    os.environ["HEIGHT"] = "800"

    print("=" * 50)
    print("BROWSER PERSISTENCE TEST")
    print("=" * 50)

    # First "request" - navigate to a page
    print("\n1. First request - navigating to example.com...")
    browser1 = get_browser_tool()
    await browser1(action="navigate", text="https://www.example.com")
    await asyncio.sleep(1)

    # Take screenshot to see state
    result1 = await browser1(action="screenshot")
    print(f"   Screenshot 1: {'Success' if result1.base64_image else 'Failed'}")

    # Get page text to verify we're on example.com
    text1 = await browser1(action="get_page_text")
    text1_content = text1.output if isinstance(text1.output, str) else str(text1.output)
    print(f"   Page contains 'Example Domain': {'Example Domain' in text1_content}")

    # Second "request" - should reuse same browser
    print("\n2. Second request - getting new tool instance...")
    browser2 = get_browser_tool()

    # Check if we're still on example.com without navigating
    print("   Checking if browser state persisted...")
    text2 = await browser2(action="get_page_text")
    text2_content = text2.output if isinstance(text2.output, str) else str(text2.output)

    if "Example Domain" in text2_content:
        print("   ✅ SUCCESS: Browser state persisted! Still on example.com")
    else:
        print("   ❌ FAILED: Browser state lost, not on example.com")

    # Navigate to a different page
    print("\n3. Navigating to Google from second instance...")
    await browser2(action="navigate", text="https://www.google.com")
    await asyncio.sleep(1)

    # Third "request" - should still have the Google page
    print("\n4. Third request - getting another tool instance...")
    browser3 = get_browser_tool()

    text3 = await browser3(action="get_page_text")
    text3_content = text3.output if isinstance(text3.output, str) else str(text3.output)

    if "google" in text3_content.lower():
        print("   ✅ SUCCESS: Browser persisted across all instances!")
    else:
        print("   ❌ FAILED: Browser state not maintained")

    # Test that we're using the same actual browser instance
    print("\n5. Verifying singleton pattern...")
    if browser1 is browser2 and browser2 is browser3:
        print("   ✅ SUCCESS: All instances are the same object (singleton working)")
    else:
        print("   ❌ FAILED: Different objects created")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)

    # Clean up
    print("\nClosing browser...")
    await browser3(action="close_browser")

if __name__ == "__main__":
    asyncio.run(test_browser_persistence())