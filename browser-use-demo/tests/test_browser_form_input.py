"""Form input integration tests using a local page and headless Chromium."""

import pytest
from playwright.async_api import async_playwright

from browser_use_demo.tools.browser import BrowserTool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_form_input_for_controls_with_and_without_selection() -> None:
    """Filling non-selectable inputs must still notify page event handlers."""
    cases = [
        ("email", "person@example.com", False),
        ("url", "https://example.com/path", False),
        ("color", "#123456", False),
        ("text", "plain text", True),
        ("search", "search terms", True),
        ("tel", "+1 555 0100", True),
        ("password", "password", True),
        ("textarea", "multiple\nlines", True),
    ]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            tool = BrowserTool()
            tool._page = page
            tool._initialized = True

            for input_type, value, supports_selection in cases:
                control = (
                    '<textarea id="field"></textarea>'
                    if input_type == "textarea"
                    else f'<input id="field" type="{input_type}">'
                )
                await page.set_content(
                    f'<label for="field">Test field</label>{control}'
                    "<script>"
                    "window.formEvents = [];"
                    "for (const type of ['input', 'change']) {"
                    "document.addEventListener(type, event => {"
                    "window.formEvents.push([event.type, event.target.value]);"
                    "});"
                    "}"
                    "</script>"
                )
                result = await tool(action="read_page", text="interactive")
                assert result.output is not None
                # Resolve the actual field reference registered by read_page.
                ref = await page.evaluate(
                    """() => Object.keys(window.__claudeElementMap).find(ref =>
                        window.__claudeElementMap[ref].deref() ===
                        document.getElementById('field'))"""
                )
                assert f"[ref={ref}]" in result.output, input_type
                assert ref is not None, input_type

                result = await tool(action="form_input", ref=ref, value=value)
                assert result.error is None, input_type
                assert await page.locator("#field").input_value() == value, input_type
                assert sorted(await page.evaluate("window.formEvents")) == [
                    ["change", value],
                    ["input", value],
                ], input_type
                assert await page.locator("#field").evaluate(
                    "element => document.activeElement === element"
                ), input_type
                if supports_selection:
                    assert await page.locator("#field").evaluate(
                        "element => [element.selectionStart, element.selectionEnd]"
                    ) == [len(value), len(value)], input_type
        finally:
            await browser.close()
