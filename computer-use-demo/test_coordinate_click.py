#!/usr/bin/env python3
"""Test script to debug coordinate clicking issues in browser_local.py"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from computer_use_demo.tools.browser_local import BrowserTool

async def test_coordinate_click():
    """Test coordinate clicking functionality"""

    # Set up environment
    os.environ["WIDTH"] = "1280"
    os.environ["HEIGHT"] = "800"

    # Create browser tool
    browser = BrowserTool(width=1280, height=800)

    try:
        print("1. Navigating to Google...")
        result = await browser(action="navigate", text="https://www.google.com")
        print(f"   Navigation result: {result.output[:100] if result.output else 'Screenshot taken'}")

        # Wait for page to load
        await asyncio.sleep(2)

        print("\n2. Taking screenshot to see current state...")
        screenshot_result = await browser(action="screenshot")
        print(f"   Screenshot taken: {'Success' if screenshot_result.base64_image else 'Failed'}")

        print("\n3. Attempting coordinate click on search box area...")
        print("   Clicking at coordinates (640, 400) - center of page")

        # Try clicking in the middle of the page (where search box typically is)
        click_result = await browser(action="left_click", coordinate=(640, 400))
        print(f"   Click result: {click_result.output}")

        # Try typing something
        print("\n4. Typing test text...")
        type_result = await browser(action="type", text="test search query")
        print(f"   Type result: {type_result.output}")

        # Take another screenshot to see if anything changed
        print("\n5. Taking final screenshot...")
        final_screenshot = await browser(action="screenshot")
        print(f"   Final screenshot: {'Success' if final_screenshot.base64_image else 'Failed'}")

        print("\n6. Reading page to check for interactive elements...")
        page_result = await browser(action="read_page", text="interactive")
        if page_result.output:
            import json
            try:
                page_data = json.loads(page_result.output)
                # Look for input elements
                print(f"   Found page data with {len(page_data.get('children', []))} top-level elements")
            except:
                print(f"   Page read result: {page_result.output[:200]}")

        print("\n7. Testing click with different coordinates...")
        # Try clicking on a specific coordinate that should be the search input
        click_result2 = await browser(action="left_click", coordinate=(640, 350))
        print(f"   Second click result: {click_result2.output}")

        print("\n8. Testing mouse movement and click separately...")
        # Test mouse down/up separately
        mouse_down_result = await browser(action="left_mouse_down", coordinate=(640, 350))
        print(f"   Mouse down result: {mouse_down_result.output}")

        await asyncio.sleep(0.5)

        mouse_up_result = await browser(action="left_mouse_up", coordinate=(640, 350))
        print(f"   Mouse up result: {mouse_up_result.output}")

        print("\nTest completed!")

    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        print("\nClosing browser...")
        await browser(action="close_browser")

if __name__ == "__main__":
    asyncio.run(test_coordinate_click())