"""Browser automation tool using Playwright for web interaction."""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, cast
from uuid import uuid4

from anthropic.types.beta import BetaToolUnionParam
from playwright.async_api import Browser, BrowserContext, Page

from .base import BaseAnthropicTool, ToolError, ToolResult

# Simple logging for debugging - removed, using print directly


OUTPUT_DIR = Path("/tmp/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Directory containing browser tool utility files (JS scripts)
BROWSER_TOOL_UTILS_DIR = Path(__file__).parent / "browser_tool_utils"


class BrowserOptions(TypedDict):
    display_width_px: int
    display_height_px: int


Actions = Literal[
    "navigate",
    "screenshot",
    "left_click",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "left_click_drag",
    "left_mouse_down",
    "left_mouse_up",
    "scroll",
    "scroll_to",
    "type",
    "key",
    "hold_key",
    "read_page",
    "find",
    "get_page_text",
    "wait",
    "form_input",
    "zoom",
]


class BrowserTool(BaseAnthropicTool):
    """
    A browser automation tool using Playwright for web interaction.

    Key actions for extracting content:
    - read_page: Extract structured DOM tree with element references (USE THIS for analyzing page structure)
    - get_page_text: Extract all text content from the page (USE THIS for reading articles/posts)
    - screenshot: Take a visual screenshot (only for visual confirmation, not for reading content)

    Navigation actions:
    - navigate: Go to a URL
    - find: Search for elements on the page

    Interaction actions:
    - left_click, right_click, double_click: Click elements
    - type: Enter text
    - scroll: Scroll the page
    """

    name: Literal["browser"] = "browser"
    api_type: Literal["browser_20250910"] = "browser_20250910"

    # Instance-level browser connection (recreated per request)
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _playwright = None

    def __init__(self, width: int = 1920, height: int = 1080):
        """Initialize the browser tool with specified viewport dimensions."""
        super().__init__()
        # Require environment variables if not provided as arguments
        if 'BROWSER_WIDTH' in os.environ:
            self.width = int(os.environ['BROWSER_WIDTH'])
        else:
            self.width = width

        if 'BROWSER_HEIGHT' in os.environ:
            self.height = int(os.environ['BROWSER_HEIGHT'])
        else:
            self.height = height
        self._initialized = False
        self._event_loop = None  # Track which event loop we're initialized in

    @property
    def options(self) -> BrowserOptions:
        """Return browser display options."""
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
        }

    def to_params(self) -> BetaToolUnionParam:
        """Convert tool to API parameters."""
        return cast(
            BetaToolUnionParam,
            {"name": self.name, "type": self.api_type, **self.options},
        )

    async def _ensure_browser(self) -> None:
        """Launch browser and ensure page is ready."""
        try:
            current_loop = asyncio.get_running_loop()
            if self._initialized and hasattr(self, "_event_loop"):
                if self._event_loop != current_loop:
                    self._initialized = False
                    self._browser = None
                    self._context = None
                    self._page = None
                    self._playwright = None
        except RuntimeError:
            pass

        if not self._initialized:
            if self._playwright is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()

            if self._browser is None:
                self._browser = await self._playwright.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        f"--display=:{os.environ.get('DISPLAY_NUM', '1')}",
                    ],
                )
                self._context = await self._browser.new_context(
                    viewport={"width": self.width, "height": self.height},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                self._page = await self._context.new_page()
                self._page.set_default_timeout(30000)

            self._initialized = True
            try:
                self._event_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._event_loop = None

    async def _execute_js_from_file(self, filename: str, *args) -> Any:
        """Load and execute JavaScript from a file."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        script_path = BROWSER_TOOL_UTILS_DIR / filename
        if not script_path.exists():
            raise ToolError(f"Script file not found: {filename}")

        script = script_path.read_text()

        # Special handling for browser_dom_script.js
        if filename == "browser_dom_script.js":
            # The DOM script defines window.__generateAccessibilityTree function
            # We need to inject it and then call it
            filter_type = args[0] if args else ""
            combined_expression = f"""
                (function() {{
                    {script}
                    return window.__generateAccessibilityTree('{filter_type}');
                }})()
            """
            return await self._page.evaluate(combined_expression)
        else:
            # For other scripts, wrap as a function and call with arguments
            escaped_args = ", ".join(json.dumps(arg) for arg in args)
            js_expression = f"({script})({escaped_args})"
            return await self._page.evaluate(js_expression)

    async def _take_screenshot(self) -> ToolResult:
        """
        Take a visual screenshot of the current page.
        NOTE: This only returns an image, not text content.
        Use read_page or get_page_text to extract actual content.
        """
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Save screenshot directly to file (like browser.py does with scrot)
            screenshot_path = OUTPUT_DIR / f"screenshot_{uuid4().hex}.png"
            await self._page.screenshot(path=str(screenshot_path), full_page=False)

            # Read the file and encode to base64
            screenshot_bytes = screenshot_path.read_bytes()
            image_base64 = base64.b64encode(screenshot_bytes).decode()

            return ToolResult(output="", error=None, base64_image=image_base64)
        except Exception as e:
            raise ToolError(f"Failed to take screenshot: {str(e)}") from e

    async def _zoom_screenshot(
        self, x: int, y: int, width: int, height: int
    ) -> ToolResult:
        """Take a screenshot of a specific region."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Take screenshot with clipping
            screenshot_path = OUTPUT_DIR / f"zoom_screenshot_{uuid4().hex}.png"
            await self._page.screenshot(
                path=str(screenshot_path),
                clip={"x": x, "y": y, "width": width, "height": height},
            )

            # Read the file and encode to base64
            screenshot_bytes = screenshot_path.read_bytes()
            image_base64 = base64.b64encode(screenshot_bytes).decode()

            return ToolResult(output="", error=None, base64_image=image_base64)
        except Exception as e:
            raise ToolError(f"Failed to take zoom screenshot: {str(e)}") from e

    async def _navigate(self, url: str) -> ToolResult:
        """Navigate to a URL."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Add protocol if missing
            if not url.startswith(("http://", "https://", "file://", "about:")):
                url = f"https://{url}"

            await self._page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(2)  # Wait for page to stabilize

            # Take screenshot after navigation
            return await self._take_screenshot()

        except Exception as e:
            raise ToolError(f"Failed to navigate to {url}: {str(e)}") from e

    async def _click(
        self,
        action: str,
        coordinate: Optional[tuple[int, int]] = None,
        ref: Optional[str] = None,
        text: Optional[str] = None,
    ) -> ToolResult:
        """Handle various click actions."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            button = "left"
            click_count = 1

            if action == "right_click":
                button = "right"
            elif action == "middle_click":
                button = "middle"
            elif action == "double_click":
                click_count = 2
            elif action == "triple_click":
                click_count = 3

            if coordinate:
                x, y = coordinate
                # Ensure the page has focus
                await self._page.bring_to_front()

                # Move mouse to position and click
                await self._page.mouse.move(x, y)
                await asyncio.sleep(0.01)  # Small delay to ensure mouse is positioned

                # Perform the click based on type
                await self._page.mouse.click(
                    x, y, button=button, click_count=click_count
                )
                return ToolResult(output=f"Clicked at ({x}, {y})", error=None)
            elif ref:
                # Use the browser_element_script.js to find and click element
                element_info = await self._execute_js_from_file(
                    "browser_element_script.js", ref
                )

                if not element_info.get("success", False):
                    raise ToolError(
                        element_info.get("message", "Failed to find element")
                    )

                # Get the coordinates from element_info
                click_x, click_y = element_info["coordinates"]

                # Move to element and click
                await self._page.mouse.move(click_x, click_y)
                await asyncio.sleep(0.1)
                await self._page.mouse.click(
                    click_x, click_y, button=button, click_count=click_count
                )
                return ToolResult(output=f"Clicked element with ref: {ref}", error=None)
            elif text:
                # Click on element containing text
                await self._page.click(
                    f"text={text}", button=button, click_count=click_count
                )
                return ToolResult(output=f"Clicked on text: {text}", error=None)
            else:
                raise ToolError(
                    "Either coordinate, ref, or text is required for click action"
                )

        except Exception as e:
            raise ToolError(f"Failed to perform {action}: {str(e)}") from e

    async def _type_text(self, text: str) -> ToolResult:
        """Type text into the focused element."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            await self._page.keyboard.type(text)
            return ToolResult(output=f"Typed: {text}", error=None)
        except Exception as e:
            raise ToolError(f"Failed to type text: {str(e)}") from e

    async def _press_key(
        self, key: str, hold: bool = False, duration: float = 0.01
    ) -> ToolResult:
        """Press a keyboard key or key combination."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Load the key map
            from .browser_tool_utils.browser_key_map import KEY_MAP

            # Handle key combinations (e.g., "cmd+a", "ctrl+c")
            if "+" in key:
                await self._page.keyboard.press(key)
                return ToolResult(output=f"Pressed key combination: {key}", error=None)

            # Map single key if needed
            key_info = KEY_MAP.get(key.lower())
            if key_info:
                key_to_press = key_info["code"] if "code" in key_info else key
            else:
                key_to_press = key

            if hold:
                await self._page.keyboard.down(key_to_press)
                await asyncio.sleep(duration)
                await self._page.keyboard.up(key_to_press)
                return ToolResult(
                    output=f"Held key '{key}' for {duration} seconds", error=None
                )
            else:
                await self._page.keyboard.press(key_to_press)
                return ToolResult(output=f"Pressed key: {key}", error=None)

        except Exception as e:
            raise ToolError(f"Failed to press key '{key}': {str(e)}") from e

    async def _scroll(
        self,
        coordinate: Optional[tuple[int, int]] = None,
        direction: Optional[str] = None,
        amount: Optional[int] = None,
    ) -> ToolResult:
        """Scroll the page or element."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            if not direction:
                direction = "down"
            if not amount:
                amount = 3  # Default scroll amount

            # Calculate scroll delta based on direction
            delta_x = 0
            delta_y = 0

            if direction == "up":
                delta_y = -amount * 100
            elif direction == "down":
                delta_y = amount * 100
            elif direction == "left":
                delta_x = -amount * 100
            elif direction == "right":
                delta_x = amount * 100

            if coordinate:
                x, y = coordinate
                await self._page.mouse.wheel(delta_x, delta_y)
            else:
                # Scroll the main page
                await self._page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")

            return ToolResult(
                output=f"Scrolled {direction} by {amount} units", error=None
            )

        except Exception as e:
            raise ToolError(f"Failed to scroll: {str(e)}") from e

    async def _scroll_to(self, ref: str) -> ToolResult:
        """Scroll to a specific element."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            element_info = await self._execute_js_from_file(
                "browser_element_script.js", ref
            )

            if not element_info["success"]:
                raise ToolError(element_info.get("message", "Failed to find element"))

            return ToolResult(output=f"Scrolled to element with ref: {ref}", error=None)

        except Exception as e:
            raise ToolError(f"Failed to scroll to element: {str(e)}") from e

    async def _drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int
    ) -> ToolResult:
        """Perform a drag operation."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            await self._page.mouse.move(start_x, start_y)
            await self._page.mouse.down()
            await self._page.mouse.move(end_x, end_y)
            await self._page.mouse.up()

            return ToolResult(
                output=f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})",
                error=None,
            )

        except Exception as e:
            raise ToolError(f"Failed to perform drag: {str(e)}") from e

    async def _mouse_down(self, x: int, y: int) -> ToolResult:
        """Press mouse button down."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            await self._page.mouse.move(x, y)
            await self._page.mouse.down()
            return ToolResult(output=f"Mouse down at ({x}, {y})", error=None)

        except Exception as e:
            raise ToolError(f"Failed to perform mouse down: {str(e)}") from e

    async def _mouse_up(self, x: int, y: int) -> ToolResult:
        """Release mouse button."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            await self._page.mouse.move(x, y)
            await self._page.mouse.up()
            return ToolResult(output=f"Mouse up at ({x}, {y})", error=None)

        except Exception as e:
            raise ToolError(f"Failed to perform mouse up: {str(e)}") from e

    async def _read_page(self, filter_type: str = "") -> ToolResult:
        """
        Extract the DOM tree with structured content and element references.
        USE THIS to analyze page structure and find specific elements.
        Returns a structured tree with text content, not just a screenshot.
        """
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Use the browser_dom_script.js from reference implementation
            dom_tree = await self._execute_js_from_file(
                "browser_dom_script.js", filter_type
            )

            # The script returns {pageContent: string}, extract just the pageContent
            if isinstance(dom_tree, dict) and "pageContent" in dom_tree:
                return ToolResult(output=dom_tree["pageContent"], error=None)
            elif isinstance(dom_tree, dict):
                dom_tree_json = json.dumps(dom_tree, indent=2)
            else:
                dom_tree_json = str(dom_tree)

            return ToolResult(output=dom_tree_json, error=None)

        except Exception as e:
            raise ToolError(f"Failed to read page: {str(e)}") from e

    async def _get_page_text(self) -> ToolResult:
        """
        Extract ALL text content from the current page.
        USE THIS to read articles, posts, or any text content.
        Returns the actual text, not a screenshot.
        Perfect for reading Reddit posts, articles, etc.
        """
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Use the browser_text_script.js from reference implementation
            result = await self._execute_js_from_file("browser_text_script.js")

            # Format the output like the reference implementation
            if isinstance(result, dict):
                output = f"""Title: {result.get("title", "N/A")}
URL: {result.get("url", "N/A")}
Source element: <{result.get("source", "unknown")}>
---
{result.get("text", "")}"""
                return ToolResult(output=output, error=None)
            else:
                return ToolResult(output=str(result), error=None)

        except Exception as e:
            raise ToolError(f"Failed to get page text: {str(e)}") from e

    async def _find(self, search_query: str) -> ToolResult:
        """Find elements on the page matching the search query using AI."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # First get the DOM tree for analysis
            dom_tree = await self._execute_js_from_file("browser_dom_script.js", "all")

            if isinstance(dom_tree, dict) and "pageContent" in dom_tree:
                dom_tree_json = dom_tree["pageContent"]
            else:
                dom_tree_json = json.dumps(dom_tree, indent=2)

            # Try to use Anthropic API if available
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    from anthropic import AsyncAnthropic

                    client = AsyncAnthropic(api_key=api_key)

                    prompt = f"""You are helping find elements on a web page. The user wants to find: "{search_query}"

Here is the accessibility tree of the page:
{dom_tree_json}

Find ALL elements that match the user's query. Return up to 20 most relevant matches, ordered by relevance.

Return your findings in this exact format (one line per matching element):

FOUND: <total_number_of_matching_elements>
SHOWING: <number_shown_up_to_20>
---
ref_X | role | name | type | reason why this matches
ref_Y | role | name | type | reason why this matches
...

If there are more than 20 matches, add this line at the end:
MORE: Use a more specific query to see additional results

If no matching elements are found, return only:
FOUND: 0
ERROR: explanation of why no elements were found"""

                    response = await client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=800,
                        temperature=1.0,
                        messages=[{"role": "user", "content": prompt}],
                    )

                    # Handle the response properly
                    first_content = response.content[0]
                    if hasattr(first_content, "text"):
                        response_text = first_content.text.strip()
                    else:
                        # Handle other content types if needed
                        response_text = str(first_content)
                    lines = [
                        line.strip()
                        for line in response_text.split("\n")
                        if line.strip()
                    ]

                    total_found = 0
                    elements = []
                    has_more = False
                    error_message = None

                    for line in lines:
                        if line.startswith("FOUND:"):
                            try:
                                total_found = int(line.split(":")[1].strip())
                            except (ValueError, IndexError):
                                total_found = 0
                        elif line.startswith("SHOWING:"):
                            pass
                        elif line.startswith("ERROR:"):
                            error_message = line[6:].strip()
                        elif line.startswith("MORE:"):
                            has_more = True
                        elif line.startswith("ref_") and "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 4:
                                elements.append(
                                    {
                                        "ref": parts[0],
                                        "role": parts[1],
                                        "name": parts[2] if len(parts) > 2 else "",
                                        "type": parts[3] if len(parts) > 3 else "",
                                        "description": parts[4]
                                        if len(parts) > 4
                                        else "",
                                    }
                                )

                    if total_found == 0 or len(elements) == 0:
                        return ToolResult(
                            output=error_message or "No matching elements found",
                            error=None,
                        )

                    message = f"Found {total_found} matching element{'s' if total_found != 1 else ''}"
                    if has_more:
                        message += f" (showing first {len(elements)}, use a more specific query to narrow results)"

                    # Format elements for output
                    elements_output = []
                    for el in elements:
                        element_str = f"- {el['ref']}: {el['role']}"
                        if el.get("name"):
                            element_str += f" {el['name']}"
                        if el.get("type"):
                            element_str += f" {el['type']}"
                        if el.get("description"):
                            element_str += f" - {el['description']}"
                        elements_output.append(element_str)

                    elements_str = "\n".join(elements_output)
                    return ToolResult(output=f"{message}\n\n{elements_str}", error=None)

                except Exception:
                    pass  # Failed to use AI for find, falling back to simple search

            # Fallback to simple text search if AI is not available
            elements = await self._page.query_selector_all(
                f"*:has-text('{search_query}')"
            )

            if not elements:
                return ToolResult(
                    output=f"No matching elements found for: {search_query}", error=None
                )

            # For simple fallback, just report count (no ref_ids without AI analysis)
            return ToolResult(
                output=f"Found {len(elements)} matching element{'s' if len(elements) != 1 else ''} (Note: AI-based search with ref_ids requires ANTHROPIC_API_KEY)",
                error=None,
            )

        except Exception as e:
            raise ToolError(f"Failed to find elements: {str(e)}") from e

    async def _form_input(self, ref: str, value: Any) -> ToolResult:
        """Fill a form field with a value."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Use the browser_form_input_script.js from reference implementation
            result = await self._execute_js_from_file(
                "browser_form_input_script.js", ref, value
            )

            if isinstance(result, dict) and not result.get("success", False):
                raise ToolError(result.get("message", "Failed to fill form field"))

            return ToolResult(
                output=f"Filled form field {ref} with value: {value}", error=None
            )

        except Exception as e:
            raise ToolError(f"Failed to fill form field: {str(e)}") from e

    async def _wait(self, duration: float) -> ToolResult:
        """Wait for a specified duration."""
        try:
            await asyncio.sleep(duration)
            return ToolResult(
                output=f"Waited for {duration} second{'s' if duration != 1 else ''}",
                error=None,
            )
        except Exception as e:
            raise ToolError(f"Failed to wait: {str(e)}") from e

    async def __call__(
        self,
        *,
        action: Actions,
        text: Optional[str] = None,
        ref: Optional[str] = None,
        coordinate: Optional[tuple[int, int]] = None,
        start_coordinate: Optional[tuple[int, int]] = None,
        scroll_direction: Optional[Literal["up", "down", "left", "right"]] = None,
        scroll_amount: Optional[int] = None,
        duration: Optional[float] = None,
        value: Optional[Any] = None,
        region: Optional[tuple[int, int, int, int]] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute browser actions.

        Parameters:
        - action: The action to perform
        - text: Text input for type, key, navigate, find actions
        - ref: Element reference for element-based actions
        - coordinate: (x, y) coordinates for mouse actions
        - start_coordinate: Starting point for drag actions
        - scroll_direction: Direction for scroll action
        - scroll_amount: Amount to scroll
        - duration: Duration for wait or hold_key actions
        - value: Value for form_input action
        - region: (x, y, width, height) for zoom screenshot
        """

        # Ensure browser is running for all actions
        await self._ensure_browser()

        if action == "navigate":
            if not text:
                raise ToolError("URL is required for navigate action")
            return await self._navigate(text)

        elif action == "screenshot":
            return await self._take_screenshot()

        elif action == "zoom":
            if not region:
                raise ToolError(
                    "Region (x, y, width, height) is required for zoom action"
                )
            x, y, w, h = region
            return await self._zoom_screenshot(x, y, w, h)

        elif action in [
            "left_click",
            "right_click",
            "middle_click",
            "double_click",
            "triple_click",
        ]:
            return await self._click(action, coordinate, ref, text)

        elif action == "type":
            if not text:
                raise ToolError("Text is required for type action")
            return await self._type_text(text)

        elif action == "key":
            if not text:
                raise ToolError("Key is required for key action")
            return await self._press_key(text)

        elif action == "hold_key":
            if not text:
                raise ToolError("Key is required for hold_key action")
            if not duration:
                duration = 1.0
            return await self._press_key(text, hold=True, duration=duration)

        elif action == "scroll":
            return await self._scroll(coordinate, scroll_direction, scroll_amount)

        elif action == "scroll_to":
            if not ref:
                raise ToolError("Element reference is required for scroll_to action")
            return await self._scroll_to(ref)

        elif action == "left_click_drag":
            if not start_coordinate or not coordinate:
                raise ToolError(
                    "Both start_coordinate and coordinate are required for drag action"
                )
            start_x, start_y = start_coordinate
            end_x, end_y = coordinate
            return await self._drag(start_x, start_y, end_x, end_y)

        elif action == "left_mouse_down":
            if not coordinate:
                raise ToolError("Coordinate is required for mouse_down action")
            x, y = coordinate
            return await self._mouse_down(x, y)

        elif action == "left_mouse_up":
            if not coordinate:
                raise ToolError("Coordinate is required for mouse_up action")
            x, y = coordinate
            return await self._mouse_up(x, y)

        elif action == "read_page":
            filter_type = text if text in ["interactive", ""] else ""
            return await self._read_page(filter_type)

        elif action == "get_page_text":
            return await self._get_page_text()

        elif action == "find":
            if not text:
                raise ToolError("Text is required for find action")
            return await self._find(text)

        elif action == "form_input":
            if not ref:
                raise ToolError("Element reference is required for form_input action")
            if value is None:
                raise ToolError("Value is required for form_input action")
            return await self._form_input(ref, value)

        elif action == "wait":
            if not duration:
                duration = 1.0
            return await self._wait(duration)

        else:
            raise ToolError(f"Unknown action: {action}")

    async def cleanup(self):
        """Cleanup method to ensure browser is closed properly."""
        # Clean up browser resources
        if self.cdp_url:
            # When connected to CDP server, just disconnect without closing tabs
            self._page = None
            self._context = None
            self._browser = None
        else:
            # For local browser, close everything
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        self._initialized = False


