# Browser Tool 

## Overview

The browser tool is an Anthropic tool that enables Claude to interact with web browsers and web applications through the Messages API. It provides the following features: 

* **DOM access**: Read page structure with element references  
* **Navigation control**: Browse URLs and manage browser history   
* **Form manipulation**: Directly set form input values   
* **Text extraction**: Get all text content from pages with   
* **Element targeting**: Interact with elements via ref or coordinate parameters   
* **Smart scrolling**: Scroll to specific elements with or in specific directions   
* **Page search**: Find and highlight text on pages with  
* **Visual capture**: Take screenshots with and capture zoomed regions

The browser tool advantages:

* **Reliability:** element-based targeting via the ref parameter works across different screen sizes and layouts, unlike pixel coordinates that break when windows resize.   
* **Direct DOM manipulation:** provides structured visibility into page elements and their properties, enabling precise interactions with dynamic content, hidden elements, and complex web applications  
* **Web-specific actions:** built-in support for navigation, text extraction, and form completion

---

## How browser tool differs from computer use

The browser tool is specifically optimized for web automation with DOM-aware features like element targeting, page reading, and form manipulation. While it shares core capabilities with computer use (mouse/keyboard control, screenshots), the browser tool adds web-specific actions like navigation control and DOM inspection. Computer use provides general desktop control with cursor tracking for any application, while the browser tool focuses exclusively on browser-based tasks.

### New actions added to the browser tool

The browser tool includes web-optimized actions not available in computer use:

* **navigate**: Visit URLs or traverse browser history  
* **read_page**: Extract DOM tree structure with element references  
* **get_page_text**: Extract all text content from the page  
* **find**: Search and highlight text on pages  
* **form_input**: Set form element values directly   
* **scroll_to**: Scroll elements into view  
* **zoom**: Take zoomed screenshots of specific regions

### Computer use actions removed from the browser tool

Desktop-level actions that not available in the browser tool:

* **cursor_position**: Get the current (x, y) pixel coordinate of the cursor  
* **mouse_move**: Move the cursor to specified coordinates without clicking

These actions are no longer relevant in the browser tool as you typically interact with the elements directly. The **ref** parameter enables reliable element-based tracking and replaces the need for cursor tracking.  

---

## Implementation Guide

### Tool Parameters

| Parameter | Required | Description |
|:----------|:---------|:------------|
| type | Yes | Tool version (browser_20250910) |
| name | Yes | Tool name (browser) |
| display_width_px | Yes | Display width in pixels |
| display_height_px | Yes | Display height in pixels |
| display_number | No | Display number for X11 environments |

### Example API Request
```python
import anthropic

client = anthropic.Anthropic().with_options(
    default_headers={
        "anthropic-beta": "browser-tools-2025-09-10",
    }
)

message = client.messages.create(
    model="{{model-name}}",
    max_tokens=1000,
    tools=[
        {
            "type": "browser_20250910",
            "name": "browser",
            "display_height_px": 768,
            "display_width_px": 1024,
        }
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Can you tell me what's on the front page of Anthropic.com?",
                }
            ]
        },
    ],
)
print(message)
```


## The browser tool actions reference

The browser tool supports the following actions.

### Navigation & Page Information

* **navigate**: Navigate to URL or use "back"/"forward" for history (requires text parameter)
* **screenshot**: Capture current browser viewport
* **read_page**: Get DOM tree structure; use text="interactive" to filter for interactive elements only
* **get_page_text**: Extract all text content from the page
* **find**: Search for text and highlight matches (requires text parameter)

### Mouse Actions

All mouse actions accept either ref (element reference) OR coordinate (x, y pixels):

* **left_click**: Click left mouse button (optional text for modifier keys to hold during click)
* **right_click**: Click right mouse button
* **middle_click**: Click middle mouse buttons
* **double_click**: Double-click left mouse button
* **triple_click**: Triple-click left mouse button
* **left_click_drag**: Drag from start_coordinate to coordinate (requires both coordinate parameters)
* **left_mouse_down**: Press and hold left mouse button (requires coordinate)
* **left_mouse_up**: Release left mouse button (requires coordinate)

### Scrolling

* **scroll**: Scroll in direction with specified amount (requires scroll_direction, scroll_amount, and coordinate parameters)
* **scroll_to**: Scroll element into view (requires ref parameter)

### Keyboard Actions

* **type**: Type text at current cursor position (requires text parameter)
* **key**: Press key or key combination (requires text parameter)
* **hold_key**: Hold key for specified duration (requires text and duration parameters)

### Advanced Actions

* **form_input**: Set form element value (requires ref and value parameters)
* **zoom**: Take zoomed screenshot of specific region
* **wait**: Wait for specified duration in seconds (requires duration, must be 0-100 seconds)
