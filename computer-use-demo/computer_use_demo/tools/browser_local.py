"""Local browser tool using Playwright for web automation."""

import asyncio
import base64
import os
from pathlib import Path
from typing import Literal, Optional, TypedDict, cast
from uuid import uuid4

from anthropic.types.beta import BetaToolUnionParam
from playwright.async_api import Browser, BrowserContext, Page

from .base import BaseAnthropicTool, ToolError, ToolResult


# Simple logging for debugging
def log(msg):
    print(f"[BrowserTool] {msg}")

OUTPUT_DIR = Path("/tmp/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class BrowserOptions(TypedDict):
    display_width_px: int
    display_height_px: int


class LocalBrowserTool(BaseAnthropicTool):
    """
    A tool that allows the agent to interact with a web browser locally using Playwright.
    Connects to a persistent browser server to maintain state across Streamlit requests.
    """

    name: Literal["browser"] = "browser"
    api_type: Literal["browser_20250910"] = "browser_20250910"

    # Instance-level browser connection (recreated per request)
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _playwright = None

    def __init__(self, width: int = 1280, height: int = 800):
        """Initialize the browser tool with specified viewport dimensions."""
        super().__init__()
        self.width = width
        self.height = height
        self._initialized = False
        # Get CDP URL from environment
        self.cdp_url = os.environ.get("BROWSER_CDP_URL")

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
            {
                "name": self.name,
                "type": self.api_type,
                **self.options
            },
        )

    async def _ensure_browser(self) -> None:
        """Connect to browser server and ensure page is ready."""
        if not self._initialized:
            # Start Playwright
            if self._playwright is None:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()

            # Connect to browser server or launch new browser
            if self._browser is None:
                if self.cdp_url:
                    # Connect to existing browser server via CDP
                    try:
                        log(f"Connecting to browser server at {self.cdp_url}")
                        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
                        log("Connected to browser server successfully")

                        # Get existing contexts/pages or create new ones
                        contexts = self._browser.contexts
                        if contexts:
                            # Reuse existing context
                            self._context = contexts[0]
                            log(f"Reusing existing context with {len(self._context.pages)} pages")

                            # Get existing page or create new one
                            if self._context.pages:
                                self._page = self._context.pages[0]
                                log("Reusing existing page")
                            else:
                                self._page = await self._context.new_page()
                                log("Created new page in existing context")
                        else:
                            # No existing context, create new one
                            log("Creating new context")
                            self._context = await self._browser.new_context(
                                viewport={"width": self.width, "height": self.height},
                                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            )
                            self._page = await self._context.new_page()
                            log("Created new page")

                        # Set default timeout
                        self._page.set_default_timeout(30000)

                    except Exception as e:
                        log(f"Failed to connect to browser server: {e}")
                        log("Falling back to launching new browser")
                        # Fallback to launching new browser
                        self._browser = await self._playwright.chromium.launch(
                            headless=False,
                            args=[
                                '--disable-blink-features=AutomationControlled',
                                '--disable-dev-shm-usage',
                                '--no-sandbox',
                            ]
                        )
                        # Create context and page for fallback browser
                        self._context = await self._browser.new_context(
                            viewport={"width": self.width, "height": self.height},
                            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                        self._page = await self._context.new_page()
                        self._page.set_default_timeout(30000)
                else:
                    # No browser server configured, launch directly
                    self._browser = await self._playwright.chromium.launch(
                        headless=False,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                        ]
                    )
                    # Create context and page
                    self._context = await self._browser.new_context(
                        viewport={"width": self.width, "height": self.height},
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    self._page = await self._context.new_page()
                    self._page.set_default_timeout(30000)

            self._initialized = True

    async def _take_screenshot(self) -> ToolResult:
        """Take a screenshot of the current page."""
        if self._page is None:
            raise ToolError("Browser not initialized")

        try:
            # Save screenshot directly to file (like browser.py does with scrot)
            screenshot_path = OUTPUT_DIR / f"screenshot_{uuid4().hex}.png"
            await self._page.screenshot(path=str(screenshot_path), full_page=False)

            # Read the file and encode to base64
            screenshot_bytes = screenshot_path.read_bytes()
            image_base64 = base64.b64encode(screenshot_bytes).decode()

            return ToolResult(
                output="",
                error=None,
                base64_image=image_base64
            )
        except Exception as e:
            raise ToolError(f"Failed to take screenshot: {str(e)}") from e

    async def __call__(
        self,
        *,
        action: Literal["navigate", "screenshot", "close_browser"],
        text: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute browser actions.

        Currently supported actions:
        - navigate: Navigate to a URL
        - screenshot: Take a screenshot of the current page
        - close_browser: Close the browser instance
        """

        # Ensure browser is running for all actions except close
        if action != "close_browser":
            await self._ensure_browser()

        if action == "navigate":
            if not text:
                raise ToolError("URL is required for navigate action")

            if self._page is None:
                raise ToolError("Browser not initialized")

            try:
                # Navigate to the URL
                await self._page.goto(text, wait_until="domcontentloaded")

                # Wait a bit for page to stabilize
                await asyncio.sleep(2)

                # Take and return screenshot
                return await self._take_screenshot()

            except Exception as e:
                raise ToolError(f"Failed to navigate to {text}: {str(e)}") from e

        elif action == "screenshot":
            return await self._take_screenshot()

        elif action == "close_browser":
            # When connected to CDP server, just disconnect without closing tabs
            if self.cdp_url:
                # Just clear references, don't close the actual browser/pages
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

            return ToolResult(output="Browser session closed successfully", error=None)

        else:
            raise ToolError(f"Unsupported action: {action}")

    async def cleanup(self):
        """Cleanup method to ensure browser is closed properly."""
        await self.__call__(action="close_browser")


def get_browser_tool(width: int = 1280, height: int = 720) -> LocalBrowserTool:
    """Create a new browser tool instance for each request."""
    # Always create a new instance to avoid event loop issues
    return LocalBrowserTool(width=width, height=height)


class BrowserTool20250910Local(LocalBrowserTool):
    """Browser tool implementation for local Playwright execution."""

    def __init__(self):
        """Initialize with default dimensions."""
        super().__init__(width=1280, height=720)
