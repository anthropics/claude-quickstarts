# Claude Quickstarts Development Guide

## Computer-Use Demo

### Setup & Development

- **Setup environment**: `./setup.sh`
- **Build Docker**: `docker build . -t computer-use-demo:local`
- **Run container**: `docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -v $(pwd)/computer_use_demo:/home/computeruse/computer_use_demo/ -v $HOME/.anthropic:/home/computeruse/.anthropic -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 -it computer-use-demo:local`

### Testing & Code Quality

- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Typecheck**: `pyright`
- **Run tests**: `pytest`
- **Run single test**: `pytest tests/path_to_test.py::test_name -v`

### Code Style

- **Python**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use isort with combine-as-imports
- **Error handling**: Use custom ToolError for tool errors
- **Types**: Add type annotations for all parameters and returns
- **Classes**: Use dataclasses and abstract base classes

## Customer Support Agent

### Setup & Development

- **Install dependencies**: `npm install`
- **Run dev server**: `npm run dev` (full UI)
- **UI variants**: `npm run dev:left` (left sidebar), `npm run dev:right` (right sidebar), `npm run dev:chat` (chat only)
- **Lint**: `npm run lint`
- **Build**: `npm run build` (full UI), see package.json for variants

### Code Style

- **TypeScript**: Strict mode with proper interfaces
- **Components**: Function components with React hooks
- **Formatting**: Follow ESLint Next.js configuration
- **UI components**: Use shadcn/ui components library

## Financial Data Analyst

### Setup & Development

- **Install dependencies**: `npm install`
- **Run dev server**: `npm run dev`
- **Lint**: `npm run lint`
- **Build**: `npm run build`

### Code Style

- **TypeScript**: Strict mode with proper type definitions
- **Components**: Function components with type annotations
- **Visualization**: Use Recharts library for data visualization
- **State management**: React hooks for state

# Building a Claude Computer Use Agent for DocuSeal Template Builder

## Overview

This comprehensive plan details how to create a specialized Claude computer use agent with custom drag-and-drop skills for automating the DocuSeal template builder. DocuSeal uses a normalized coordinate system (0-1 range) for field positioning, making it ideal for programmatic interaction. The latest Claude models (Claude 4 and Sonnet 3.7) now include native `left_click_drag` actions, dramatically improving drag-and-drop automation capabilities.

The plan synthesizes official documentation, production-ready frameworks, and proven implementation patterns to provide a complete roadmap from initial setup through deployment.

---

## 1. DocuSeal Template Builder: Technical Foundation

### How DocuSeal Works

**DocuSeal is an open-source document signing platform** (AGPLv3 licensed) that provides a WYSIWYG template builder for creating fillable, signable documents. The system enables drag-and-drop placement of 12+ field types including signatures, text, dates, checkboxes, and payment fields across PDF or DOCX documents.

**The drag-and-drop interface operates through three primary mechanisms**: visual UI dragging from a field panel, text tags embedded in documents (`{{Field Name;role=Signer;type=date}}`), or direct API calls with coordinate specifications. Fields can span multiple document pages and support extensive customization including validation patterns, default values, and styling preferences.

### Coordinate System Architecture

DocuSeal uses **normalized coordinates (0-1 range)** rather than pixels, making it exceptionally compatible with AI automation:

```javascript
{
  name: "Signature Box",
  type: "signature",
  areas: [{
    x: 0.403158,      // 40.3% from left edge
    y: 0.042117,      // 4.2% from top edge  
    w: 0.100684,      // 10% of page width
    h: 0.014236,      // 1.4% of page height
    page: 1,          // Page number
    attachment_uuid: "doc-uuid"
  }]
}
```

This coordinate system offers **three critical advantages for automation**: it scales across different screen resolutions without recalculation, aligns perfectly with Claude's percentage-based spatial reasoning, and eliminates pixel-specific accuracy requirements that plague traditional GUI automation.

### API Integration Points

**REST API endpoints provide comprehensive template management**:

- **POST /templates/pdf** - Create template from PDF with field definitions
- **PUT /templates/{id}** - Update existing template fields
- **POST /submissions** - Create signature request from template
- **GET /submissions/{id}/documents** - Retrieve completed documents

**Authentication uses API keys via X-Auth-Token header** or JWT tokens (HS256) for embedded builder integration. The embedded builder (`<docuseal-builder>` web component) supports extensive customization through data attributes and JavaScript events (load, change, save), enabling programmatic control and state monitoring.

### Integration Strategy

**For Claude automation, a hybrid approach proves most effective**: use browser automation (Playwright) for visual template building and verification, combined with direct API calls for reliable field creation and submission. The browser approach enables Claude to "see" what it's doing through screenshots, while API calls provide deterministic field placement without coordinate accuracy concerns.

---

## 2. Claude Skills System: Custom Capability Framework

### Skills Architecture

**Claude Skills represent modular knowledge packages** stored in `/mnt/skills/` that extend Claude's capabilities through a three-level progressive disclosure system. The metadata level (YAML frontmatter, ~50 tokens) loads at startup, the instruction level (SKILL.md) loads when task descriptions match, and supporting files load only as needed.

Skills activate **automatically based on description matching**—Claude autonomously determines when to apply skill knowledge without explicit invocation. Multiple skills compose together for complex workflows, making them ideal for packaging domain-specific expertise like drag-and-drop automation.

### File Structure Standards

```
docuseal-drag-drop-skill/
├── SKILL.md              # Main skill file with YAML frontmatter
├── REFERENCE.md          # Detailed coordinate mapping reference
├── scripts/
│   ├── coordinate_validator.py   # Validate normalized coordinates
│   └── field_creator.py           # API-based field creation
└── examples/
    └── template_examples.json     # Sample field configurations
```

**SKILL.md follows a precise format**:

```yaml
---
name: docuseal-template-builder
description: Automate DocuSeal template builder drag-and-drop operations using computer use tools and API. Use when creating document templates, adding merge fields (signature, text, date boxes), or positioning fields on PDFs.
version: 1.0.0
dependencies: python>=3.8, playwright
---

# DocuSeal Template Builder Automation

## When to Use This Skill
- Creating document templates with merge fields
- Positioning signature boxes, text fields, dates on PDF documents
- Automating DocuSeal template builder workflows
- Testing template creation processes

## Coordinate System
DocuSeal uses normalized coordinates (0-1 range):
- x: 0 (left) to 1 (right)  
- y: 0 (top) to 1 (bottom)
- w: width as decimal (0.2 = 20% of page width)
- h: height as decimal (0.05 = 5% of page height)

## Preferred Automation Approach
1. Use API calls for field creation (most reliable)
2. Use browser automation only for verification and complex workflows
3. Always validate coordinates are within 0-1 range

## API Field Creation Pattern
```python
import requests
response = requests.post(
    f"{DOCUSEAL_URL}/templates/{template_id}",
    headers={"X-Auth-Token": api_key},
    json={"fields": [{
        "name": "Client Signature",
        "type": "signature",
        "areas": [{"x": 0.5, "y": 0.8, "w": 0.2, "h": 0.05, "page": 1}]
    }]}
)
```

## Browser Automation Pattern (when needed)
For visual verification or when API unavailable:
1. Take screenshot to identify document canvas
2. Calculate normalized coordinates from visual inspection
3. Use left_click_drag to position field
4. Take screenshot to verify placement
5. Adjust if necessary

## Common Field Types and Recommended Sizes
- Signature: w=0.2, h=0.05
- Text input: w=0.25, h=0.03
- Date: w=0.15, h=0.03
- Checkbox: w=0.02, h=0.02

See REFERENCE.md for comprehensive field specifications.
```

### Best Practices for Custom Skills

**Focus and specificity determine skill effectiveness**. Keep each skill narrowly scoped to one capability—"docuseal-template-builder" rather than "document-processing". Write descriptions that include both WHAT (extract text from PDFs, fill forms) and WHEN (use when working with PDF files or when user mentions forms).

**Progressive disclosure optimizes token usage**: maintain SKILL.md under 500 lines as a "table of contents" pointing to detailed REFERENCE.md files. This ensures the main instructions remain concise while comprehensive documentation stays accessible.

**Include executable scripts for deterministic operations**. The coordinate_validator.py script provides reliable coordinate checking without consuming reasoning tokens, while field_creator.py offers a fallback when browser automation fails.

---

## 3. Claude Computer Use: Drag-and-Drop Capabilities

### Current State and Evolution

**Claude's computer use capability underwent significant enhancement** with the January 2025 release of `computer_20250124` for Claude 4 and Sonnet 3.7 models. The original version (`computer_20241022` for Claude 3.5) lacked native drag-and-drop support, requiring manual sequencing of mouse_move, left_click, mouse_move, and release actions.

**The enhanced version introduces native drag-and-drop** through the `left_click_drag` action, plus fine-grained controls (`left_mouse_down`, `left_mouse_up`), multiple click types (`double_click`, `triple_click`), and modifier key support (`hold_key`). These improvements transform drag-and-drop from a challenging workaround into a first-class capability.

### Technical Capabilities

**Available actions in computer_20250124**:

```json
// Native drag-and-drop
{"action": "left_click_drag", "start_coordinate": [100, 200], "coordinate": [500, 600]}

// Fine-grained control
{"action": "left_mouse_down", "coordinate": [100, 200]}
{"action": "mouse_move", "coordinate": [500, 600]}
{"action": "left_mouse_up"}

// With modifier keys  
{"action": "hold_key", "key": "shift"}
{"action": "left_click", "coordinate": [500, 300]}

// Wait for UI updates
{"action": "wait", "duration": 2}
```

**Screenshots consume significant tokens** (calculated as `tokens = (width_px * height_px) / 750`), making **resolution choice critical for performance**. Anthropic recommends XGA (1024x768) or WXGA (1280x800) as optimal—higher resolutions cause accuracy degradation through API image resizing while consuming more tokens.

### Known Limitations and Workarounds

**Spatial reasoning accuracy degrades with scale**—research shows up to 84% accuracy loss as grid complexity increases. Spreadsheet cell selection remains particularly unreliable; **keyboard navigation (arrow keys) proves far more effective** than mouse clicks for precise selection tasks.

**Coordinate hallucination occurs when Claude generates incorrect click positions**, particularly at higher resolutions or with small UI elements. The solution involves **implementing coordinate scaling directly in tools** rather than relying on API resizing, combined with validation loops that verify each action through screenshots.

**Timing issues plague actions that execute before UI loads**. The `wait` action provides explicit delays, but a more robust pattern involves screenshot-verify loops:

```python
async def click_with_retry(coordinate, max_retries=3):
    for attempt in range(max_retries):
        await click(coordinate)
        screenshot = await take_screenshot()
        if verify_success(screenshot):
            return
        await asyncio.sleep(1)
```

### Prompting Strategies for Reliability

**Explicit validation loops dramatically improve success rates**:

```
After each step, take a screenshot and carefully evaluate if you have achieved 
the right outcome. Explicitly show your thinking: "I have evaluated step X and 
found [result]." If not correct, analyze what went wrong and try again with 
corrections. Only when you confirm a step was executed correctly should you 
move on to the next one.
```

**Prefer keyboard shortcuts over mouse movements** whenever possible. Instead of dragging sliders, use arrow keys. Instead of clicking dropdowns and scrolling, use keyboard navigation. This preference aligns with Claude's stronger text-based reasoning compared to precise spatial manipulation.

**Enable extended thinking mode** (Claude 3.7/4) for complex spatial tasks:

```python
response = client.messages.create(
    thinking={"type": "enabled", "budget_tokens": 2000},
    messages=[...]
)
```

This allocates additional compute for spatial analysis before action generation, improving coordinate accuracy.

---

## 4. System Architecture and Implementation Strategy

### Recommended Architecture

**For DocuSeal automation, a hybrid single-agent architecture proves optimal**: one coordinating agent that intelligently chooses between browser automation (visual verification, complex workflows) and API calls (reliable field creation). This avoids multi-agent complexity while providing flexibility across automation scenarios.

```
┌─────────────────────────────────────────────────────┐
│         Claude Computer Use Agent                    │
│         (with DocuSeal Drag-Drop Skill)             │
└────────────┬────────────────────────────────────────┘
             │
      ┌──────┴──────┐
      │   Decision   │
      │    Logic     │
      └──────┬───────┘
             │
    ┌────────┴─────────┐
    │                   │
┌───▼──────────┐  ┌────▼──────────┐
│   Browser    │  │  DocuSeal API │
│  Automation  │  │     Client    │
│ (Playwright) │  │  (REST calls) │
└───┬──────────┘  └────┬──────────┘
    │                   │
    └────────┬──────────┘
             │
      ┌──────▼───────┐
      │   DocuSeal   │
      │   Instance   │
      └──────────────┘
```

**The agent operates through three modes**:

1. **API-First Mode**: Use for straightforward field creation with known coordinates
2. **Browser-Visual Mode**: Use when needing visual confirmation or discovering element positions
3. **Hybrid Mode**: Create fields via API, verify through browser screenshots

### Tool Integration Pattern

**Computer Use Tool** provides screenshot capture and mouse/keyboard control, while **Bash Tool** executes Python scripts for API interactions and coordinate validation. The **DocuSeal Skill** provides decision logic for choosing between approaches and field specification templates.

**Model Context Protocol (MCP) integration enables standardized tool access**. Create an MCP server exposing DocuSeal API operations (create_template, add_field, create_submission) alongside Playwright browser control (navigate, screenshot, element_inspect). This provides a unified interface regardless of hosting environment (Claude Desktop, Claude Code, or custom implementation).

### Environment Setup

**Containerized execution ensures consistency and security**:

```dockerfile
FROM anthropics/anthropic-quickstarts:computer-use

# Install DocuSeal dependencies
RUN pip install playwright requests pydantic

# Install Playwright browsers
RUN playwright install chromium

# Add DocuSeal skill
COPY skills/docuseal-drag-drop/ /mnt/skills/docuseal-drag-drop/

# Configure environment
ENV DOCUSEAL_URL=https://your-docuseal-instance.com
ENV DISPLAY_WIDTH=1024
ENV DISPLAY_HEIGHT=768
```

**Virtual display configuration** (X11 via Xvfb) enables GUI interaction in headless environments. The 1024x768 resolution balances token efficiency with sufficient detail for accurate element identification.

### Integration with Claude Skills

**The skill loads automatically when Claude detects DocuSeal-related tasks** through the metadata description. During execution, Claude accesses skill instructions for coordinate calculations, API patterns, and troubleshooting guidance without requiring explicit skill invocation.

**Scripts within the skill execute on-demand**:

```python
# Claude can execute this directly via bash tool
python /mnt/skills/docuseal-drag-drop/scripts/coordinate_validator.py \
  --x 0.5 --y 0.8 --w 0.2 --h 0.05
```

This provides **deterministic validation without consuming reasoning tokens**, offloading computation to efficient scripts.

---

## 5. Key GitHub Repositories and Resources

### Essential Starting Points

**anthropics/anthropic-quickstarts** (Official) - Start here for the foundational computer use implementation. The `/computer-use-demo` subdirectory contains the complete reference implementation including Docker configuration, coordinate scaling, agent loop, and tool handlers. This repository receives active maintenance from Anthropic and incorporates best practices as they emerge.

**showlab/computer_use_ootb** - Production-ready enhancement over Anthropic's demo that removes the single-display limitation, supports any resolution with optimized token usage, and includes remote control capabilities. The research team published analysis of Claude 3.5 Computer Use (arxiv.org/abs/2411.10323) demonstrating superior practical capabilities.

### Browser Automation Integration

**invariantlabs-ai/playwright-computer-use** - Connects Playwright to Claude's computer use specifically for web browser automation. For DocuSeal's web interface, this enables DOM-aware interactions that complement screenshot-based visual automation. The PlaywrightToolbox integration provides sync/async APIs compatible with existing agent frameworks.

**browser-use/browser-use** (63k+ stars) - Leading browser automation framework optimized for AI agents with ChatBrowserUse model achieving 3-5x speed improvements. Includes 500+ app integrations and cloud API for production deployment. Particularly valuable for form-filling workflows common in document signing.

**EmergenceAI/Agent-E** (1.1k+ stars) - DOM-aware automation using AG2 framework with explicit form-filling capabilities. DOM distillation and accessibility tree usage enable efficient element identification without pixel-perfect coordinate requirements.

### Natural Mouse Movement

**riflosnake/HumanCursor** - Simulates realistic human cursor movement patterns including natural drag-and-drop motions. The WebCursor module integrates with Selenium while SystemCursor works with pyautogui. For DocuSeal automation appearing human-like (important for testing real user workflows), this provides motion algorithms that avoid detection as bot activity.

**oxylabs/OxyMouse** - Implements sophisticated Bezier curve algorithms for smooth mouse movements with random coordinate generation. Useful for generating natural-looking drag paths between field palette and document canvas.

### Claude Agent Frameworks

**wshobson/agents** (18.9k+ stars) - Massive collection of 85 specialized agents, 63 plugins, and 47 skills with hub-and-spoke coordination. Demonstrates production-scale agent orchestration patterns applicable to complex DocuSeal workflows involving multiple document types.

**cloudflare/agents-starter** - Production deployment template with modern chat UI (React/Hono), tool integration, and Cloudflare Workers deployment. Provides edge computing capabilities for low-latency agent responses.

**GoogleCloudPlatform/agent-starter-pack** - Enterprise-grade templates with built-in CI/CD, observability, and Vertex AI evaluation. Includes ReAct pattern implementations and pre-configured monitoring ideal for production DocuSeal automation.

### DocuSeal Integration

**docusealco/docuseal** (10k+ stars) - Main repository providing the complete source code for understanding internal mechanics. Studying `app/javascript/template_builder` reveals drag-and-drop implementation details. The API controllers demonstrate expected request/response formats.

**docusealco/docuseal-python** - Official Python client for REST API integration. Use this for API-first automation mode, creating submissions programmatically without browser interaction.

**docusealco/docuseal-react-examples** - Real-world integration patterns showing JWT token generation, embedded builder configuration, and event handling. Valuable for understanding authentication flows when automating embedded builder.

### Development Tools

**winfunc/opcode** (18.4k+ stars) - Sophisticated desktop application for Claude Code with session versioning, visual timeline with checkpoints, instant session forking, and built-in project scanner. Rust/Tauri-based with professional UI ideal for development and debugging complex agent workflows.

**siteboon/claudecodeui** - Web/mobile interface for remote Claude Code access with responsive design, file explorer with syntax highlighting, Git integration, and WebSocket streaming. Enables testing agent behavior from mobile devices.

---

## 6. Step-by-Step Implementation Guide

### Phase 1: Environment Setup (Day 1)

**Set up the base computer use environment** using Anthropic's official quickstart as foundation:

```bash
# Clone the official quickstart
git clone https://github.com/anthropics/anthropic-quickstarts.git
cd anthropic-quickstarts/computer-use-demo

# Build the Docker container
docker build -t claude-docuseal-agent .

# Run with DocuSeal configuration
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e DOCUSEAL_URL=https://your-instance.com \
  -e DOCUSEAL_API_KEY=$DOCUSEAL_API_KEY \
  -v $(pwd)/skills:/mnt/skills \
  -p 5900:5900 -p 8080:8080 \
  claude-docuseal-agent
```

**Install additional dependencies** for DocuSeal integration:

```bash
# In the container or Dockerfile
pip install playwright requests python-dotenv pydantic
playwright install chromium
```

**Verify computer use basics** by testing screenshot capture, mouse clicks, and keyboard input with the Streamlit interface. Confirm the agent can successfully capture screenshots at 1024x768 resolution and execute basic mouse movements.

### Phase 2: Create DocuSeal Custom Skill (Day 2-3)

**Structure the skill directory** following Claude Skills best practices:

```bash
mkdir -p skills/docuseal-drag-drop/{scripts,examples,resources}
```

**Create SKILL.md** with comprehensive instructions (use the template from section 2 as starting point). Include the normalized coordinate system explanation, API patterns, browser automation fallback strategies, and common field specifications.

**Add coordinate validation script** (scripts/coordinate_validator.py):

```python
#!/usr/bin/env python3
import sys
import argparse

def validate_coordinates(x, y, w, h):
    """Validate DocuSeal normalized coordinates"""
    errors = []
    
    if not (0 <= x <= 1):
        errors.append(f"x={x} outside valid range [0,1]")
    if not (0 <= y <= 1):
        errors.append(f"y={y} outside valid range [0,1]")
    if not (0 < w <= 1):
        errors.append(f"w={w} outside valid range (0,1]")
    if not (0 < h <= 1):
        errors.append(f"h={h} outside valid range (0,1]")
    if x + w > 1:
        errors.append(f"x + w = {x+w} exceeds page width")
    if y + h > 1:
        errors.append(f"y + h = {y+h} exceeds page height")
    
    if errors:
        print("INVALID COORDINATES:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    else:
        print("✓ Coordinates valid")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--w", type=float, required=True)
    parser.add_argument("--h", type=float, required=True)
    args = parser.parse_args()
    
    validate_coordinates(args.x, args.y, args.w, args.h)
```

**Create API integration script** (scripts/field_creator.py):

```python
#!/usr/bin/env python3
import os
import sys
import json
import requests
import argparse

def create_field(template_id, field_config):
    """Create field via DocuSeal API"""
    url = os.getenv("DOCUSEAL_URL")
    api_key = os.getenv("DOCUSEAL_API_KEY")
    
    response = requests.put(
        f"{url}/api/templates/{template_id}",
        headers={
            "X-Auth-Token": api_key,
            "Content-Type": "application/json"
        },
        json={"fields": [field_config]}
    )
    
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
        sys.exit(0)
    else:
        print(f"ERROR: {response.status_code} - {response.text}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--field-json", required=True, 
                       help="Field configuration as JSON string")
    args = parser.parse_args()
    
    field_config = json.loads(args.field_json)
    create_field(args.template_id, field_config)
```

**Test the skill** by using Claude Code or Claude.ai with the skill installed. Ask Claude to "validate coordinates x=0.5, y=0.8, w=0.2, h=0.05" and verify it executes the validation script correctly.

### Phase 3: Implement Hybrid Automation Strategy (Day 4-5)

**Create the integration layer** that enables intelligent switching between browser and API modes:

```python
# tools/docuseal_controller.py
from playwright.async_api import async_playwright
import requests
import os

class DocuSealController:
    def __init__(self):
        self.base_url = os.getenv("DOCUSEAL_URL")
        self.api_key = os.getenv("DOCUSEAL_API_KEY")
        self.browser = None
        self.page = None
        
    async def init_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch()
        self.page = await self.browser.new_page()
        
    async def navigate_to_template(self, template_id):
        """Open template builder in browser"""
        url = f"{self.base_url}/templates/{template_id}"
        await self.page.goto(url)
        
    async def capture_screenshot(self):
        """Take screenshot for Claude to analyze"""
        screenshot = await self.page.screenshot()
        return screenshot
        
    def create_field_via_api(self, template_id, field_config):
        """Create field using REST API"""
        response = requests.put(
            f"{self.base_url}/api/templates/{template_id}",
            headers={"X-Auth-Token": self.api_key},
            json={"fields": [field_config]}
        )
        return response.json()
        
    async def verify_field_placement(self, field_name):
        """Check if field appears correctly in UI"""
        # Wait for field to render
        await self.page.wait_for_selector(
            f"[data-field-name='{field_name}']"
        )
        # Take screenshot for visual confirmation
        return await self.capture_screenshot()
```

**Integrate with computer use tool** by modifying the agent loop to include DocuSealController as an available tool. The agent can now choose between browser.screenshot(), browser.navigate(), and api.create_field() based on task requirements.

**Implement decision logic** in the system prompt:

```
When automating DocuSeal templates:
1. For creating fields with known coordinates: Use API (most reliable)
2. For discovering element positions: Use browser screenshots
3. For verification: Take browser screenshots after API calls
4. For complex workflows requiring visual feedback: Use browser automation

Always validate coordinates are in 0-1 range before creating fields.
```

### Phase 4: Enhanced Drag-and-Drop Implementation (Day 6-7)

**Implement natural mouse movement** for browser-based drag operations:

```python
# tools/human_cursor.py
import math
import random

class HumanCursor:
    @staticmethod
    def bezier_curve(start, end, control_points=2):
        """Generate Bezier curve points for natural movement"""
        points = []
        # Add slight randomization to control points
        controls = []
        for i in range(control_points):
            t = (i + 1) / (control_points + 1)
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            # Add random deviation
            x += random.uniform(-50, 50)
            y += random.uniform(-50, 50)
            controls.append((x, y))
            
        # Generate curve points
        for t in range(0, 101, 5):  # 20 steps
            t = t / 100.0
            # Bezier calculation with control points
            x, y = start
            # Simplified cubic Bezier
            if len(controls) >= 2:
                x = (1-t)**3 * start[0] + 3*(1-t)**2*t * controls[0][0] + \
                    3*(1-t)*t**2 * controls[1][0] + t**3 * end[0]
                y = (1-t)**3 * start[1] + 3*(1-t)**2*t * controls[0][1] + \
                    3*(1-t)*t**2 * controls[1][1] + t**3 * end[1]
            points.append((int(x), int(y)))
            
        return points
    
    @staticmethod
    async def drag_with_natural_motion(page, start, end):
        """Perform drag with human-like cursor path"""
        path = HumanCursor.bezier_curve(start, end)
        
        # Move to start
        await page.mouse.move(start[0], start[1])
        await page.mouse.down()
        
        # Follow the path
        for x, y in path:
            await page.mouse.move(x, y)
            # Small random delay
            await page.wait_for_timeout(random.uniform(10, 30))
            
        await page.mouse.up()
```

**For Claude's native computer use**, leverage the new `left_click_drag` action:

```python
async def claude_drag_field(start_coord, end_coord):
    """Use Claude's native drag action"""
    tool_input = {
        "action": "left_click_drag",
        "start_coordinate": start_coord,
        "coordinate": end_coord
    }
    
    # Claude executes this through computer use tool
    result = await computer_tool.execute(tool_input)
    
    # Verify with screenshot
    screenshot_result = await computer_tool.execute({
        "action": "screenshot"
    })
    
    return result, screenshot_result
```

**Implement validation loops** to ensure successful drag operations:

```python
async def drag_field_with_verification(field_type, target_coords, max_retries=3):
    """Drag field with automatic retry on failure"""
    for attempt in range(max_retries):
        # Take screenshot to locate field in palette
        screenshot = await take_screenshot()
        
        # Calculate field palette position (right side of screen)
        field_start = await locate_field_in_palette(field_type, screenshot)
        
        # Perform drag
        await claude_drag_field(field_start, target_coords)
        
        # Verify placement
        verification_screenshot = await take_screenshot()
        if verify_field_placed(verification_screenshot, target_coords):
            return True
            
        print(f"Attempt {attempt + 1} failed, retrying...")
        
    return False
```

### Phase 5: Testing and Validation (Day 8-9)

**Create test suite** covering core functionality:

```python
# tests/test_docuseal_automation.py
import pytest
from tools.docuseal_controller import DocuSealController

@pytest.mark.asyncio
async def test_coordinate_validation():
    """Test coordinate validator catches invalid inputs"""
    valid = validate_coordinates(0.5, 0.5, 0.2, 0.1)
    assert valid == True
    
    invalid = validate_coordinates(1.5, 0.5, 0.2, 0.1)
    assert invalid == False

@pytest.mark.asyncio  
async def test_api_field_creation():
    """Test field creation via API"""
    controller = DocuSealController()
    
    field_config = {
        "name": "Test Signature",
        "type": "signature",
        "areas": [{
            "x": 0.5,
            "y": 0.8,
            "w": 0.2,
            "h": 0.05,
            "page": 1
        }]
    }
    
    result = controller.create_field_via_api("test-template-id", field_config)
    assert result["success"] == True

@pytest.mark.asyncio
async def test_browser_screenshot():
    """Test browser initialization and screenshot capture"""
    controller = DocuSealController()
    await controller.init_browser()
    await controller.navigate_to_template("test-template-id")
    
    screenshot = await controller.capture_screenshot()
    assert screenshot is not None
    assert len(screenshot) > 0

@pytest.mark.asyncio
async def test_drag_drop_verification():
    """Test complete drag-drop with verification loop"""
    success = await drag_field_with_verification(
        field_type="signature",
        target_coords=[512, 600],  # Center-bottom of 1024x768
        max_retries=3
    )
    assert success == True
```

**Run automated evaluation** against real DocuSeal templates:

```bash
# Create 10 test templates
python scripts/create_test_templates.py --count 10

# Run agent on each template
python scripts/run_evaluation.py --test-suite test_templates/

# Analyze results
python scripts/analyze_results.py --results evaluation_results.json
```

**Metrics to track**:
- Success rate for field creation (target: >95%)
- Coordinate accuracy (target: within 2% of intended position)
- Time to complete template (baseline for optimization)
- API vs browser mode selection accuracy
- Retry rate (lower is better)

**Manual testing scenarios**:
1. Create signature field at specific position
2. Add multiple fields across different pages
3. Handle error cases (invalid coordinates, API failures)
4. Verify field properties (name, type, required status)
5. Complete end-to-end template creation workflow

### Phase 6: Production Deployment (Day 10)

**Containerize the complete solution**:

```dockerfile
FROM anthropics/anthropic-quickstarts:computer-use

# Install dependencies
RUN pip install playwright requests pydantic pytest
RUN playwright install chromium

# Copy skills and tools
COPY skills/ /mnt/skills/
COPY tools/ /app/tools/
COPY scripts/ /app/scripts/

# Set environment variables
ENV DISPLAY=:1
ENV DISPLAY_WIDTH=1024
ENV DISPLAY_HEIGHT=768

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python /app/scripts/health_check.py

ENTRYPOINT ["python", "/app/main.py"]
```

**Implement monitoring and observability**:

```python
# monitoring/agent_monitor.py
import mlflow
from datetime import datetime

class AgentMonitor:
    def __init__(self):
        mlflow.set_tracking_uri("http://mlflow-server:5000")
        
    def log_field_creation(self, method, success, duration, coordinates):
        """Log field creation attempt"""
        mlflow.log_metrics({
            "success": 1 if success else 0,
            "duration_seconds": duration,
            "coordinate_x": coordinates[0],
            "coordinate_y": coordinates[1]
        })
        mlflow.log_param("method", method)  # "api" or "browser"
        mlflow.log_param("timestamp", datetime.now().isoformat())
        
    def log_agent_session(self, task_description, total_steps, 
                          success, total_tokens, total_cost):
        """Log complete agent session"""
        with mlflow.start_run():
            mlflow.log_params({
                "task": task_description,
                "model": "claude-sonnet-3.7"
            })
            mlflow.log_metrics({
                "total_steps": total_steps,
                "success": 1 if success else 0,
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost
            })
```

**Set up error handling and alerting**:

```python
# monitoring/alerting.py
import requests

def send_alert(error_type, error_message, severity="high"):
    """Send alert on agent failures"""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    
    payload = {
        "text": f"🚨 Claude DocuSeal Agent Alert",
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error Type:* {error_type}\n*Severity:* {severity}\n*Message:* {error_message}"
            }
        }]
    }
    
    requests.post(webhook_url, json=payload)
```

**Deploy with orchestration**:

```yaml
# docker-compose.yml
version: '3.8'

services:
  claude-agent:
    build: .
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DOCUSEAL_URL=${DOCUSEAL_URL}
      - DOCUSEAL_API_KEY=${DOCUSEAL_API_KEY}
    ports:
      - "8080:8080"
      - "5900:5900"
    volumes:
      - ./logs:/app/logs
      - ./skills:/mnt/skills
    restart: unless-stopped
    
  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports:
      - "5000:5000"
    command: mlflow server --host 0.0.0.0
    
  docuseal:
    image: docuseal/docuseal:latest
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://db/docuseal
```

**Launch and verify**:

```bash
docker-compose up -d
docker-compose logs -f claude-agent

# Test end-to-end
curl -X POST http://localhost:8080/api/create-template \
  -H "Content-Type: application/json" \
  -d '{"pdf_url": "https://example.com/contract.pdf", "fields": [...]}'
```

---

## 7. Top 30 Prompts for Building This System

These prompts follow a logical sequence from environment setup through production deployment. Use them sequentially with a coding agent like Claude Code or Claude.ai.

### Setup and Foundation (Prompts 1-5)

**1. Environment Setup**
```
Set up a Docker development environment for Claude computer use based on Anthropic's official quickstart repository (anthropics/anthropic-quickstarts/computer-use-demo). Include Playwright, requests, and pydantic as additional dependencies. Configure for 1024x768 resolution. Provide the complete Dockerfile and instructions for building and running the container.
```

**2. Directory Structure**
```
Create a complete directory structure for a Claude agent that automates DocuSeal template builder operations. Include: skills/ for custom Claude skills, tools/ for DocuSeal integration code, scripts/ for utilities, tests/ for test suites, and monitoring/ for observability. Generate a tree view showing all directories and placeholder files with brief descriptions.
```

**3. Environment Configuration**
```
Create a comprehensive .env.example file for the DocuSeal automation agent with all required environment variables: Anthropic API key, DocuSeal URL and API key, display settings, model selection, and optional monitoring configurations. Include comments explaining each variable's purpose and example values.
```

**4. Dependency Management**
```
Create a complete requirements.txt file for the DocuSeal automation agent including: anthropic SDK, playwright, requests, pydantic for validation, pytest for testing, python-dotenv for configuration, and mlflow for monitoring. Pin versions appropriately and include all transitive dependencies needed for production deployment.
```

**5. Basic Agent Loop**
```
Implement the core agent loop for Claude computer use following Anthropic's best practices. The loop should: 1) Accept user task input, 2) Call Claude API with computer use tool, 3) Execute requested tool actions, 4) Return results to Claude, 5) Continue until task completion or max iterations. Include proper error handling, logging, and iteration limits. Use Claude Sonnet 3.7 model with computer_20250124 tool version.
```

### Claude Skill Development (Prompts 6-10)

**6. DocuSeal Skill YAML**
```
Create the YAML frontmatter for a Claude skill called "docuseal-template-builder" that teaches Claude how to automate DocuSeal's drag-and-drop template builder. Include: concise name (under 64 chars), comprehensive description covering WHAT it does and WHEN to use it (under 200 chars), version 1.0.0, and dependencies (python>=3.8, playwright). Optimize the description for Claude's skill discovery system.
```

**7. DocuSeal Skill Instructions**
```
Write the markdown instructions section of the DocuSeal automation skill (SKILL.md). Cover: 1) When to use this skill, 2) DocuSeal's normalized coordinate system (0-1 range) with detailed explanation, 3) Hybrid automation approach (API-first, browser for verification), 4) Complete API field creation pattern with code example, 5) Browser automation pattern with step-by-step instructions, 6) Common field types and recommended sizes, 7) Reference to supporting files. Keep under 500 lines for optimal performance.
```

**8. Coordinate Validation Script**
```
Create a Python script (coordinate_validator.py) for the DocuSeal skill that validates normalized coordinates. Accept --x, --y, --w, --h arguments. Validate: 1) All values in proper ranges (x,y in [0,1], w,h in (0,1]), 2) Field doesn't exceed page boundaries (x+w<=1, y+h<=1), 3) Coordinates are reasonable (no zero-dimension fields). Exit with code 0 for valid, code 1 for invalid with descriptive error messages. Include argparse and proper error handling.
```

**9. API Field Creation Script**
```
Create a Python script (field_creator.py) that creates DocuSeal fields via REST API. Accept --template-id and --field-json arguments. Read DOCUSEAL_URL and DOCUSEAL_API_KEY from environment. Make PUT request to /api/templates/{id} with fields array. Handle authentication via X-Auth-Token header. Provide detailed error messages for API failures including status codes. Return formatted JSON response on success.
```

**10. Skill Examples File**
```
Create an examples.json file for the DocuSeal skill containing 10 complete field configuration examples covering all common field types: signature, initials, text, date, number, checkbox, radio, select. Include proper coordinate positioning for typical document locations (header, footer, body). Each example should have name, type, areas array with normalized coordinates, and optional properties (required, default_value, validation_pattern). Format as valid JSON with comments explaining use cases.
```

### DocuSeal Integration (Prompts 11-15)

**11. DocuSeal Controller Class**
```
Implement a DocuSealController class that provides both browser automation (Playwright) and API methods for template manipulation. Include methods: init_browser(), navigate_to_template(template_id), capture_screenshot(), create_field_via_api(template_id, field_config), verify_field_placement(field_name). Use async/await patterns. Load configuration from environment variables. Include comprehensive docstrings and type hints. Handle errors gracefully with descriptive exceptions.
```

**12. Hybrid Decision Logic**
```
Implement intelligent decision logic that chooses between API and browser automation based on task requirements. Create a StrategySelector class with method choose_strategy(task_type, has_coordinates, needs_verification) that returns 'api', 'browser', or 'hybrid'. Define clear rules: API-first for known coordinates, browser for discovery and verification, hybrid for reliability. Include reasoning in log output explaining each decision.
```

**13. Browser Automation Helpers**
```
Create browser automation helper functions for DocuSeal template builder: locate_field_in_palette(field_type, screenshot) to find field icons in right panel, calculate_canvas_coordinates(normalized_coords, canvas_element) to convert 0-1 coords to pixels, wait_for_template_load() to ensure UI ready, verify_field_exists(field_name) to confirm successful creation. Use Playwright's locator API and include proper waits and error handling.
```

**14. API Client Implementation**
```
Implement a complete DocuSealAPIClient class wrapping all relevant REST endpoints: create_template_from_pdf(pdf_url), get_template(template_id), update_template_fields(template_id, fields), create_submission(template_id, submitters), get_submission(submission_id). Include authentication handling, request retries with exponential backoff, rate limiting respect, comprehensive error messages, and response validation with pydantic models.
```

**15. Authentication Flow**
```
Implement authentication handling for both API key and JWT token methods. Create get_api_headers() for standard API calls with X-Auth-Token, generate_builder_jwt(user_email, template_id) for embedded builder access using HS256, validate_jwt(token) for incoming tokens. Include expiration handling, token refresh logic, and secure secret management using environment variables or secret manager integration.
```

### Drag-and-Drop Implementation (Prompts 16-20)

**16. Human-Like Cursor Movement**
```
Implement a HumanCursor class with bezier_curve(start, end, control_points) method that generates natural mouse movement paths using cubic Bezier curves. Add random variations to control points for realism. Include drag_with_natural_motion(page, start, end) that executes the drag with small random delays between path points (10-30ms). Use Playwright's mouse API. Make parameters configurable (speed, randomness level).
```

**17. Native Drag Implementation**
```
Create a function claude_native_drag(computer_tool, start_coord, end_coord) that uses Claude Sonnet 3.7's left_click_drag action. Format tool_input properly with action type and coordinates. Include pre-drag screenshot for position verification, execute drag, post-drag screenshot for result verification. Return structured result with success boolean, screenshots, and execution time. Handle tool execution errors gracefully.
```

**18. Drag Verification Loop**
```
Implement drag_field_with_verification(field_type, target_coords, max_retries=3) that attempts drag operations with automatic retry on failure. For each attempt: 1) Capture screenshot, 2) Locate field in palette, 3) Execute drag, 4) Verify placement visually, 5) If failed, analyze error and adjust approach, 6) Retry with corrections. Use computer vision or coordinate checking for verification. Log each attempt with reasoning.
```

**19. Coordinate Conversion Utilities**
```
Create utility functions for coordinate conversion between DocuSeal's normalized format (0-1) and pixel coordinates: normalized_to_pixels(x, y, w, h, page_width, page_height), pixels_to_normalized(x_px, y_px, w_px, h_px, page_width, page_height), validate_and_convert(coords, target_format, dimensions). Include bounds checking, rounding strategies, and clear error messages for out-of-range values. Add unit tests for common conversions.
```

**20. Visual Field Detection**
```
Implement visual field detection using screenshot analysis: detect_fields_in_screenshot(screenshot) that identifies existing fields by looking for DocuSeal's field visual indicators (colored rectangles with field names). Return list of detected fields with approximate coordinates. Use OpenCV or PIL for image processing. Include confidence scoring for each detection. This enables Claude to understand current template state from screenshots.
```

### Testing and Validation (Prompts 21-25)

**21. Unit Test Suite**
```
Create comprehensive pytest unit tests for core components: test_coordinate_validation() covering valid/invalid coordinate ranges, test_api_field_creation() with mocked API responses, test_browser_initialization(), test_coordinate_conversion() with edge cases, test_strategy_selection() for decision logic. Use pytest fixtures for common setup (mock DocuSeal instance, test coordinates). Include parametrized tests for various field types and coordinate ranges. Aim for >90% code coverage.
```

**22. Integration Test Scenarios**
```
Create integration tests that run against a real DocuSeal instance: test_end_to_end_template_creation() creates complete template with multiple fields, test_hybrid_workflow() uses both API and browser methods, test_error_recovery() simulates API failures and verifies fallback to browser, test_concurrent_field_creation() for race conditions. Use pytest-asyncio for async tests. Include cleanup fixtures that delete test templates after execution.
```

**23. Test Template Generator**
```
Create a script generate_test_templates.py that generates diverse test templates for evaluation: simple single-page with 3-5 fields, complex multi-page with 20+ fields, edge cases (fields at boundaries, overlapping positions, all field types), real-world documents (contract, NDA, employment agreement). Accept --count and --type arguments. Output templates with ground truth (expected field positions) for automated validation. Save to tests/fixtures/ directory.
```

**24. Automated Evaluation Runner**
```
Implement evaluation pipeline run_evaluation.py that: 1) Loads test templates from fixtures directory, 2) Runs agent on each template creation task, 3) Compares results against ground truth, 4) Calculates metrics (success rate, coordinate accuracy, completion time, retry rate), 5) Generates detailed report with failure analysis. Support --parallel flag to run multiple evaluations concurrently. Output results to evaluation_results.json with timestamps and model version.
```

**25. Performance Benchmarking**
```
Create benchmark suite benchmark_agent.py measuring: time to create single field (API vs browser), token usage per operation type, cost per template creation, screenshot capture latency, retry frequency by field type, memory usage over long sessions. Compare performance across different Claude models (Sonnet 3.5, 3.7, 4). Generate comparison charts and identify optimization opportunities. Include statistical significance testing for performance differences.
```

### Monitoring and Production (Prompts 26-30)

**26. MLflow Integration**
```
Implement comprehensive MLflow tracking for agent operations: AgentMonitor class with methods log_field_creation(method, success, duration, coordinates), log_agent_session(task, steps, tokens, cost), log_error(error_type, traceback, context). Create custom metrics for DocuSeal-specific operations (field types created, coordinate accuracy scores). Set up experiment tracking with proper run organization (by date, model version, task type). Include artifact logging for screenshots and generated templates.
```

**27. Alerting System**
```
Create alerting system alert_manager.py that monitors agent health and sends notifications on: repeated failures (>3 in 10 minutes), coordinate validation errors, API authentication failures, browser crashes, high cost/token usage (>threshold), unusual latency. Support multiple alert channels (Slack webhook, email, PagerDuty). Include severity levels (info, warning, critical). Implement rate limiting to avoid alert spam. Add alert aggregation for related errors.
```

**28. Production Docker Compose**
```
Create complete docker-compose.yml for production deployment including: claude-agent service with health checks and auto-restart, mlflow-server for experiment tracking, docuseal instance for testing, nginx reverse proxy with SSL termination, postgresql database for MLflow backend, prometheus for metrics collection, grafana for visualization. Include volume mounts for persistence, network configuration, environment variable injection, resource limits (CPU, memory). Add monitoring stack for observability.
```

**29. Health Check Endpoint**
```
Implement comprehensive health check system health_check.py that verifies: 1) Anthropic API connectivity and rate limits, 2) DocuSeal API availability and authentication, 3) Browser automation functionality (can launch Chromium), 4) Virtual display running (X11 Xvfb), 5) Disk space and memory availability, 6) Skill files present and valid. Return HTTP status codes (200 healthy, 503 degraded, 500 unhealthy) with detailed JSON response explaining status of each component. Include timeout handling for external dependencies.
```

**30. Deployment and Operations Guide**
```
Create comprehensive DEPLOYMENT.md documentation covering: 1) Prerequisites (Docker, API keys, system requirements), 2) Configuration (environment variables, skill installation, volume mounts), 3) Deployment steps (build image, launch services, verify health), 4) Monitoring setup (MLflow, logs, alerts), 5) Backup procedures (skills, configurations, logs), 6) Troubleshooting (common errors, debug mode, log analysis), 7) Scaling considerations (concurrent agents, resource limits), 8) Security best practices (secrets management, network isolation, prompt injection protection), 9) Cost optimization (model selection, caching, resolution tuning), 10) Upgrade procedures (new Claude versions, skill updates). Include command examples and decision trees for common scenarios.
```

---

## Key Recommendations and Next Steps

**Start with the API-first approach** for maximum reliability. DocuSeal's normalized coordinate system (0-1 range) aligns perfectly with programmatic field creation, avoiding the complexity and error rates of pure GUI automation. Use browser automation primarily for visual verification and discovering element positions rather than as the primary interaction method.

**Leverage Claude 4 or Sonnet 3.7's enhanced computer use capabilities** with the native `left_click_drag` action rather than trying to work around limitations in older versions. The fine-grained mouse controls (`left_mouse_down`, `left_mouse_up`) and modifier key support transform drag-and-drop from challenging workaround to first-class capability.

**Implement comprehensive validation loops** that verify each action through screenshots before proceeding. The pattern of execute→screenshot→verify→retry provides robustness against Claude's spatial reasoning limitations and coordinate accuracy issues.

**Monitor token usage and costs carefully** as screenshot-heavy workflows consume significant tokens. The formula `tokens = (width * height) / 750` means a single 1024x768 screenshot costs ~1,050 tokens. Optimize by taking screenshots only when necessary for decision-making rather than after every minor action.

**Build evaluation infrastructure early** rather than manually testing each change. Automated evaluation against diverse test templates provides rapid feedback on improvements and prevents regressions. Track success rate, coordinate accuracy, completion time, and retry frequency as key metrics.

The combination of DocuSeal's automation-friendly architecture, Claude's advancing computer use capabilities, and the custom skill system creates a powerful foundation for reliable template automation. Following this implementation plan systematically will result in a production-ready agent capable of handling real-world document template creation workflows.

For questions or issues during implementation, consult the official Anthropic documentation (docs.anthropic.com/en/docs/build-with-claude/computer-use), the DocuSeal GitHub repository (github.com/docusealco/docuseal), and the computer use demo reference implementation (github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo).