#!/usr/bin/env python3
"""Visual test to verify coordinate clicks are actually working."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from computer_use_demo.tools.browser_local import BrowserTool

async def test_click_verification():
    """Test that coordinate clicks actually interact with page elements."""

    os.environ["WIDTH"] = "1280"
    os.environ["HEIGHT"] = "800"
    os.environ.setdefault("BROWSER_CDP_URL", "http://127.0.0.1:9223")

    browser = BrowserTool(width=1280, height=800)

    try:
        print("=" * 50)
        print("COORDINATE CLICK VERIFICATION TEST")
        print("=" * 50)

        # Navigate to a page with clickable buttons
        print("\n1. Navigating to example page with buttons...")
        await browser(action="navigate", text="https://www.w3schools.com/html/tryit.asp?filename=tryhtml_button_basic")
        await asyncio.sleep(3)

        print("\n2. Taking initial screenshot...")
        result = await browser(action="screenshot")
        print(f"   Screenshot: {'Success' if result.base64_image else 'Failed'}")

        # Read the page to find clickable elements
        print("\n3. Reading page structure...")
        page_result = await browser(action="read_page", text="interactive")
        if page_result.output:
            print("   Found interactive elements on page")

        # Try to click on a known button location
        print("\n4. Attempting to click button at specific coordinates...")
        # The W3Schools try-it editor has an iframe, let's try a simpler test page

        print("\n5. Navigating to simpler test page...")
        await browser(action="navigate", text="https://www.example.com")
        await asyncio.sleep(2)

        print("\n6. Getting page text before click...")
        text_before = await browser(action="get_page_text")
        print(f"   Page text length: {len(text_before.output) if text_before.output else 0}")

        # Click on the "More information..." link (usually at bottom of example.com)
        print("\n7. Clicking on 'More information' link coordinates...")
        # This link is typically around the middle-bottom of the page
        click_result = await browser(action="left_click", coordinate=(640, 500))
        print(f"   Click result: {click_result.output}")

        await asyncio.sleep(2)

        print("\n8. Checking if page changed after click...")
        text_after = await browser(action="get_page_text")

        if text_before.output != text_after.output:
            print("   ✅ SUCCESS: Page content changed after click!")
            print("   Coordinate clicks are working properly.")
        else:
            print("   ⚠️  WARNING: Page content unchanged after click.")
            print("   Coordinate clicks might not be working correctly.")

        # Alternative test with form input
        print("\n9. Testing click on Google search box...")
        await browser(action="navigate", text="https://www.google.com")
        await asyncio.sleep(2)

        # Click on search box (approximate center of page)
        print("   Clicking on search box...")
        await browser(action="left_click", coordinate=(640, 350))

        # Try typing
        print("   Typing test query...")
        await browser(action="type", text="playwright test")

        # Press Enter
        print("   Pressing Enter...")
        await browser(action="key", text="Return")

        await asyncio.sleep(2)

        # Check if we're on search results
        print("\n10. Checking if search was performed...")
        final_text = await browser(action="get_page_text")

        if "playwright test" in final_text.output.lower():
            print("   ✅ SUCCESS: Search query visible in results!")
            print("   Coordinate clicks and keyboard input working.")
        else:
            print("   ⚠️  Results unclear, taking final screenshot...")

        final_screenshot = await browser(action="screenshot")
        print(f"   Final screenshot: {'Success' if final_screenshot.base64_image else 'Failed'}")

        print("\n" + "=" * 50)
        print("TEST COMPLETE")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing browser...")
        await browser(action="close_browser")

if __name__ == "__main__":
    asyncio.run(test_click_verification())