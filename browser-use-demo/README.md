# Claude Browser Use Demo

A containerized web automation demo showcasing Claude's ability to interact with web browsers using Playwright.

## Overview

This demo provides a Streamlit-based interface where you can interact with Claude to:
- Navigate websites
- Extract information from web pages
- Fill out forms
- Interact with web applications
- Take screenshots
- Read and analyze web content

Unlike the computer-use demo, this focuses specifically on browser automation, making it simpler and more focused on web-specific tasks.

## Features

- 🌐 **Browser Automation**: Full Chromium browser running in Docker container
- 👁️ **Visual Feedback**: See the browser through VNC/NoVNC interface
- 📝 **Content Extraction**: Extract text and structured data from websites
- 🎯 **Precise Interactions**: Click, type, scroll, and navigate with accuracy
- 🛠️ **Action Logging**: View tool usage inline with chat messages
- 🔒 **Secure**: Fully containerized environment with isolated browser

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your system
- Anthropic API key

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd browser-use-demo
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env file and add your ANTHROPIC_API_KEY
   # Optionally adjust display resolution (defaults to 1920x1080)
   ```

### Running with Docker Compose (Recommended)

```bash
# For production use:
docker-compose up --build

# For development with file watching (auto-sync changes):
docker-compose up --build --watch
```

### Running with Docker (Alternative)

1. **Build the Docker image**:
   ```bash
   docker build . -t browser-use-demo:latest
   ```

2. **Run the container**:
   ```bash
   docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
     -e BROWSER_WIDTH=1920 -e BROWSER_HEIGHT=1080 \
     -e WIDTH=1920 -e HEIGHT=1080 \
     -v $(pwd)/browser_use_demo:/home/browseruse/browser_use_demo/ \
     -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
     -it browser-use-demo:latest
   ```

4. **Access the interfaces**:
   - **Main UI**: http://localhost:8080 (Streamlit interface)
   - **NoVNC Browser View**: http://localhost:6080 (see the browser)
   - **VNC**: Connect any VNC client to localhost:5900

## Usage Examples

Once the demo is running, try these prompts in the Streamlit interface:

- "Navigate to news.ycombinator.com and tell me the top 3 stories"
- "Go to google.com and search for 'Anthropic Claude'"
- "Visit wikipedia.org and find information about artificial intelligence"
- "Navigate to github.com and search for 'playwright'"

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
│  │   Claude API + Browser Tool │ │  ← Claude controls browser
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

## Browser Actions

Claude can perform these browser actions:

- **navigate**: Go to a URL
- **screenshot**: Take a screenshot of the page
- **click**: Click on elements (left, right, double, triple clicks)
- **type**: Enter text in input fields
- **key**: Press keyboard keys
- **scroll**: Scroll the page
- **read_page**: Extract DOM structure and content
- **get_page_text**: Extract all text from the page
- **find**: Search for elements on the page
- **wait**: Wait for a specified duration

## Important Notes

### Content Extraction

To extract text content from web pages, Claude should use:
- `read_page`: Returns structured DOM with element references
- `get_page_text`: Returns all text content in readable format

The `screenshot` action only returns an image and cannot extract text.

### Security

This demo runs a browser in a containerized environment. While isolated, please:
- Don't enter personal credentials or sensitive information
- Be cautious about the websites you visit
- Remember this is a demonstration tool, not for production use

## Development

To modify the browser tool or add features:

1. Edit files in `browser_use_demo/tools/browser.py`
2. Rebuild the Docker image
3. The volume mount allows live code updates for the Python files

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

## License

This demo is provided as-is for demonstration purposes. See the main repository license for details.

## Credits

Built with:
- [Anthropic Claude API](https://www.anthropic.com)
- [Playwright](https://playwright.dev)
- [Streamlit](https://streamlit.io)
- [NoVNC](https://novnc.com)