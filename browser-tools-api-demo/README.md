# Claude Browser Tools API Demo

The browser-tools-api-demo is a complete reference implementation for the browser tools API, demonstrating how to implement each action using Playwright as the browser automation framework. It provides a containerized Streamlit interface showcasing every action supported by the browser tools API including navigation, DOM-based content extraction, and form manipulation.

## Overview of the browser tools API

The browser tools API enables Claude to interact with web browsers and web applications. This tool provides:

- **DOM access**: Read page structure with element references
- **Navigation control**: Browse URLs and manage browser history
- **Form manipulation**: Directly set form input values
- **Text extraction**: Get all text content from pages
- **Element targeting**: Interact with elements via ref or coordinate parameters
- **Smart scrolling**: Scroll to specific elements or in specific directions
- **Page search**: Find and highlight text on pages
- **Visual capture**: Take screenshots and capture zoomed regions

### browser tools API Advantages

- **Reliability**: Element-based targeting via the `ref` parameter works across different screen sizes and layouts, unlike pixel coordinates that break when windows resize
- **Direct DOM manipulation**: Provides structured visibility into page elements and their properties, enabling precise interactions with dynamic content, hidden elements, and complex web applications
- **Web-specific actions**: Built-in support for navigation, text extraction, and form completion

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your system
- Anthropic API key

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd browser-tools-api-demo
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env file and add your ANTHROPIC_API_KEY
   # Optionally adjust display resolution (defaults to 1920x1080)
   ```

### Running with Docker Compose

```bash
# For production use:
docker-compose up --build

# For development with file watching (auto-sync changes):
docker-compose up --build --watch
```

### Access the interfaces:
   - **Main UI**: http://localhost:8080 (Streamlit interface)
   - **NoVNC Browser View**: http://localhost:6080 (see the browser)
   - **VNC**: Connect any VNC client to localhost:5900

## Usage Examples

Once the demo is running, try these prompts in the Streamlit interface to see how the browser tools API takes actions:

- "Navigate to news.ycombinator.com and tell me the top 3 stories"
- "Go to google.com and search for 'Anthropic Claude'"
- "Visit wikipedia.org and find information about artificial intelligence"
- "Navigate to github.com and search for 'playwright'"

Note that the current playwright implementation hits CAPTCHAs when searching Google.com. To avoid this, we recommend that you specify the website in the prompt (ie. navigate to Anthropic.com and search for x). 

## Safety Considerations 

The browser tools API is a beta feature. Please be aware that the browser tools API poses unique risks that are distinct from standard API features or chat interfaces. These risks are heightened when using the tool to interact with the internet. To minimize risks, consider taking precautions such as:

1. Run the browser in an isolated virtual machine or container environment with minimal privileges to prevent direct system attacks or accidents.
2. Avoid giving the model access to sensitive data, such as account login information, to prevent information theft.
3. Consider an allowlist of domains to reduce exposure to malicious content.
4. Ask a human to confirm decisions that may result in meaningful real-world consequences as well as any tasks requiring affirmative consent, such as accepting cookies, executing financial transactions, or agreeing to terms of service.

In some circumstances, Claude will follow commands found in content even if it conflicts with the user's instructions. For example, instructions on webpages or contained in images may override user instructions or cause Claude to make mistakes. We suggest taking precautions to isolate Claude from sensitive data and actions to avoid risks related to prompt injection.

Finally, please inform end users of relevant risks and obtain their consent prior to enabling the browser tools API in your own products.


Finally, please inform end users of relevant risks and obtain their consent prior to enabling the browser tools API in your own products.

This demo runs a browser in a containerized environment. While isolated, please note:

- **Don't enter personal credentials or sensitive information** - This is a demonstration tool
- **Be cautious about the websites you visit** - Some sites may have anti-automation measures
- **Not for production use** - This demo is for learning and development purposes only

## Implementation Reference

This demo shows how to build browser automation with Claude using Playwright. All browser actions (navigate, click, type, scroll, form_input, etc.) are implemented as methods in [browser.py](browser_tools_api_demo)/tools/browser.py) using Playwright's async API.

### Key Files

- **[browser.py](browser_tools_api_demo/tools/browser.py)** - Main tool with all browser actions
- **[loop.py](browser_tools_api_demo/loop.py)** - Sampling loop for API calls and response handling
- **[streamlit.py](browser_tools_api_demo/streamlit.py)** - Chat UI
- **[browser_tool_utils/](browser_tools_api_demo/browser_tool_utils/)** - JavaScript utilities for DOM extraction, element finding, and form manipulation

### Core Patterns

**Element references:** JavaScript utilities generate `ref` identifiers for reliable element targeting across screen sizes (replacing brittle pixel coordinates).

**Tool setup:**
```python
browser_tool = BrowserTool(width=1280, height=800)

def to_params(self):
    return {
        "name": "browser",
        "type": "browser_20250910",
        "display_width_px": self.width,
        "display_height_px": self.height,
    }
```


### Modifying & Using as a Template

**To modify this demo:**
1. Edit `browser_tools_api_demo/tools/browser.py` to add features or change behavior
2. Rebuild the Docker image (volume mount allows live Python code updates)

**To use as a template for your own project:**
1. Copy [browser.py](browser_tools_api_demo/tools/browser.py) and [browser_tool_utils/](browser_tools_api_demo/browser_tool_utils/)
2. Adapt [loop.py](browser_tools_api_demo/loop.py) for your API integration
3. Build your UI or use [streamlit.py](browser_tools_api_demo/streamlit.py) as a starting point

## Architecture

```
┌──────────────────────────────────┐
│     Docker Container              │
│                                   │
│  ┌─────────────────────────────┐ │
│  │   Streamlit Interface       │ │  ← User interacts here
│  └──────────┬──────────────────┘ │
│             │                     │
│  ┌──────────▼──────────────────┐ │
│  │  Claude API + browser tools │ │  ← Claude controls browser
│  └──────────┬──────────────────┘ │
│             │                     │
│  ┌──────────▼──────────────────┐ │
│  │   Playwright + Chromium     │ │  ← Browser automation
│  └──────────┬──────────────────┘ │
│             │                     │
│  ┌──────────▼──────────────────┐ │
│  │   XVFB Virtual Display      │ │  ← Virtual display
│  └──────────┬──────────────────┘ │
│             │                     │
│  ┌──────────▼──────────────────┐ │
│  │   VNC/NoVNC Server          │ │  ← Visual access
│  └─────────────────────────────┘ │
└──────────────────────────────────┘
```

## How the browser tools API Differs from Computer Use

The browser tools API is specifically optimized for web automation with DOM-aware features like element targeting, page reading, and form manipulation. While it shares core capabilities with computer use (mouse/keyboard control, screenshots), the browser tools API adds web-specific actions like navigation control and DOM inspection. Computer use provides general desktop control with cursor tracking for any application, while the browser tools API focuses exclusively on browser-based tasks.

### New Actions Added to the browser tools API

The browser tools API includes web-optimized actions not available in computer use:

- **navigate**: Visit URLs or traverse browser history
- **read_page**: Extract DOM tree structure with element references
- **get_page_text**: Extract all text content from the page
- **find**: Search and highlight text on pages
- **form_input**: Set form element values directly
- **scroll_to**: Scroll elements into view
- **zoom**: Take zoomed screenshots of specific regions

### Computer Use Actions Removed from the browser tools API

Desktop-level actions that are not available in the browser tools API:

- **cursor_position**: Get the current (x, y) pixel coordinate of the cursor
- **mouse_move**: Move the cursor to specified coordinates without clicking

These actions are no longer relevant in the browser tools API as you typically interact with elements directly. The `ref` parameter enables reliable element-based tracking and replaces the need for cursor tracking.


## Troubleshooting

**Browser not visible?**
- Check that port 8080 is accessible
- Try refreshing the NoVNC page
- Ensure Docker has sufficient resources allocated

**API errors?**
- Verify your Anthropic API key is set correctly
- Check you're using a compatible model (Claude 4 models: claude-sonnet-4-20250514, claude-opus-4-20250514, or claude-boucle-eap)

**Browser actions failing?**
- Some websites may have anti-automation measures
- Try simpler websites first to test functionality
- Check the browser view to see what's happening

## Credits

Built with:
- [Anthropic Claude API](https://www.anthropic.com)
- [Playwright](https://playwright.dev)
- [Streamlit](https://streamlit.io)
- [NoVNC](https://novnc.com)
