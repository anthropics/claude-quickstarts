# DocuSeal Template Builder - Complete Reference

This document provides comprehensive technical specifications for DocuSeal template field types, coordinate calculations, and advanced configurations.

## Table of Contents

1. [Field Types Specification](#field-types-specification)
2. [Coordinate System Deep Dive](#coordinate-system-deep-dive)
3. [Common Layout Patterns](#common-layout-patterns)
4. [Field Properties Reference](#field-properties-reference)
5. [API Endpoint Reference](#api-endpoint-reference)
6. [Browser Automation Reference](#browser-automation-reference)

---

## Field Types Specification

### Signature Fields

**Use Case**: Full signature capture

**Recommended Dimensions**:
- Standard: `w=0.20, h=0.05`
- Large: `w=0.30, h=0.07`
- Compact: `w=0.15, h=0.04`

**Typical Placement**:
- Bottom left: `x=0.10, y=0.85`
- Bottom center: `x=0.40, y=0.85`
- Bottom right: `x=0.65, y=0.85`

**Properties**:
```json
{
  "name": "Client Signature",
  "type": "signature",
  "required": true,
  "areas": [{"x": 0.1, "y": 0.85, "w": 0.2, "h": 0.05, "page": 1}]
}
```

### Initials Fields

**Use Case**: Initial boxes for page acknowledgments

**Recommended Dimensions**: `w=0.08, h=0.04`

**Typical Placement**:
- Page corner: `x=0.85, y=0.92`
- Inline with text: `x=0.7, y=0.5`

**Properties**:
```json
{
  "name": "Initials",
  "type": "initials",
  "required": false,
  "areas": [
    {"x": 0.85, "y": 0.92, "w": 0.08, "h": 0.04, "page": 1},
    {"x": 0.85, "y": 0.92, "w": 0.08, "h": 0.04, "page": 2}
  ]
}
```

### Text Fields

**Use Case**: Text input (names, addresses, emails)

**Recommended Dimensions**:
- Short (names): `w=0.15, h=0.03`
- Medium (emails): `w=0.25, h=0.03`
- Long (addresses): `w=0.40, h=0.03`
- Multi-line: `w=0.50, h=0.10`

**Properties**:
```json
{
  "name": "Full Name",
  "type": "text",
  "required": true,
  "default_value": "",
  "validation_pattern": "^[A-Za-z\\s]+$",
  "areas": [{"x": 0.1, "y": 0.2, "w": 0.25, "h": 0.03, "page": 1}]
}
```

**Validation Patterns**:
- Name: `^[A-Za-z\\s]+$`
- Email: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$`
- Phone: `^\\+?[0-9\\s\\-\\(\\)]+$`
- Zip Code (US): `^\\d{5}(-\\d{4})?$`

### Date Fields

**Use Case**: Date inputs

**Recommended Dimensions**: `w=0.15, h=0.03`

**Typical Placement**:
- Near signatures: `x=0.6, y=0.85`
- Form fields: `x=0.1, y=0.3`

**Properties**:
```json
{
  "name": "Date Signed",
  "type": "date",
  "required": true,
  "default_value": "{{date}}",
  "areas": [{"x": 0.6, "y": 0.85, "w": 0.15, "h": 0.03, "page": 1}]
}
```

**Date Format Options**:
- `{{date}}` - Current date (auto-filled)
- Custom format via default_value

### Number Fields

**Use Case**: Numeric inputs (amounts, quantities)

**Recommended Dimensions**: `w=0.10, h=0.03`

**Properties**:
```json
{
  "name": "Quantity",
  "type": "number",
  "required": true,
  "default_value": "1",
  "validation_pattern": "^[0-9]+$",
  "areas": [{"x": 0.7, "y": 0.4, "w": 0.1, "h": 0.03, "page": 1}]
}
```

### Checkbox Fields

**Use Case**: Boolean options, agreements

**Recommended Dimensions**: `w=0.02, h=0.02`

**Typical Placement**: Inline with text labels

**Properties**:
```json
{
  "name": "I Agree",
  "type": "checkbox",
  "required": true,
  "areas": [{"x": 0.1, "y": 0.6, "w": 0.02, "h": 0.02, "page": 1}]
}
```

**Multiple Checkboxes** (vertical layout):
```json
{
  "name": "Options",
  "type": "checkbox",
  "areas": [
    {"x": 0.1, "y": 0.4, "w": 0.02, "h": 0.02, "page": 1},
    {"x": 0.1, "y": 0.45, "w": 0.02, "h": 0.02, "page": 1},
    {"x": 0.1, "y": 0.5, "w": 0.02, "h": 0.02, "page": 1}
  ]
}
```

### Radio Fields

**Use Case**: Single selection from multiple options

**Recommended Dimensions**: `w=0.02, h=0.02`

**Properties**:
```json
{
  "name": "Payment Method",
  "type": "radio",
  "required": true,
  "options": ["Credit Card", "Bank Transfer", "Check"],
  "areas": [
    {"x": 0.1, "y": 0.5, "w": 0.02, "h": 0.02, "page": 1},
    {"x": 0.1, "y": 0.55, "w": 0.02, "h": 0.02, "page": 1},
    {"x": 0.1, "y": 0.6, "w": 0.02, "h": 0.02, "page": 1}
  ]
}
```

### Select/Dropdown Fields

**Use Case**: Dropdown selection from predefined options

**Recommended Dimensions**: `w=0.20, h=0.03`

**Properties**:
```json
{
  "name": "Country",
  "type": "select",
  "required": true,
  "options": ["United States", "Canada", "United Kingdom", "Other"],
  "default_value": "United States",
  "areas": [{"x": 0.1, "y": 0.4, "w": 0.2, "h": 0.03, "page": 1}]
}
```

### Image Fields

**Use Case**: Image uploads (profile pictures, logos)

**Recommended Dimensions**: `w=0.15, h=0.15` (square)

**Properties**:
```json
{
  "name": "Profile Photo",
  "type": "image",
  "required": false,
  "areas": [{"x": 0.75, "y": 0.1, "w": 0.15, "h": 0.15, "page": 1}]
}
```

### File Attachment Fields

**Use Case**: Document uploads

**Recommended Dimensions**: `w=0.25, h=0.04`

**Properties**:
```json
{
  "name": "Supporting Documents",
  "type": "file",
  "required": false,
  "areas": [{"x": 0.1, "y": 0.7, "w": 0.25, "h": 0.04, "page": 1}]
}
```

### Payment Fields

**Use Case**: Payment processing integration

**Recommended Dimensions**: `w=0.30, h=0.05`

**Properties**:
```json
{
  "name": "Payment",
  "type": "payment",
  "required": true,
  "default_value": "100.00",
  "areas": [{"x": 0.35, "y": 0.8, "w": 0.3, "h": 0.05, "page": 1}]
}
```

---

## Coordinate System Deep Dive

### Normalized Coordinates Explained

DocuSeal uses normalized coordinates where all values are expressed as decimals between 0 and 1, representing percentages of the page dimensions.

#### Why Normalized Coordinates?

1. **Resolution Independence**: Works across different screen sizes
2. **PDF Scaling**: Maintains position regardless of PDF zoom level
3. **Consistent Positioning**: Same coordinates work on any device
4. **AI-Friendly**: Percentage-based reasoning is natural for language models

#### Coordinate Components

```
x: Horizontal position (0 = left edge, 1 = right edge)
y: Vertical position (0 = top edge, 1 = bottom edge)
w: Width (0.2 = 20% of page width)
h: Height (0.05 = 5% of page height)
```

#### Pixel to Normalized Conversion

If working with pixel coordinates from screenshots or measurements:

```python
# Given pixel coordinates and page dimensions
pixel_x = 400
pixel_y = 600
pixel_w = 200
pixel_h = 40
page_width = 1000
page_height = 1200

# Convert to normalized
normalized_x = pixel_x / page_width      # 0.4
normalized_y = pixel_y / page_height     # 0.5
normalized_w = pixel_w / page_width      # 0.2
normalized_h = pixel_h / page_height     # 0.033
```

#### Normalized to Pixel Conversion

When implementing browser automation:

```python
# Given normalized coordinates and screen resolution
normalized_x = 0.5
normalized_y = 0.8
screen_width = 1024
screen_height = 768
canvas_offset_x = 200  # Canvas starts 200px from left
canvas_offset_y = 100  # Canvas starts 100px from top
canvas_width = 800
canvas_height = 600

# Convert to pixel coordinates
pixel_x = canvas_offset_x + (normalized_x * canvas_width)   # 600
pixel_y = canvas_offset_y + (normalized_y * canvas_height)  # 580
```

---

## Common Layout Patterns

### Contract Signature Block

```json
{
  "fields": [
    {
      "name": "Client Name",
      "type": "text",
      "required": true,
      "areas": [{"x": 0.1, "y": 0.75, "w": 0.3, "h": 0.03, "page": 1}]
    },
    {
      "name": "Client Signature",
      "type": "signature",
      "required": true,
      "areas": [{"x": 0.1, "y": 0.82, "w": 0.3, "h": 0.05, "page": 1}]
    },
    {
      "name": "Date Signed",
      "type": "date",
      "required": true,
      "default_value": "{{date}}",
      "areas": [{"x": 0.1, "y": 0.90, "w": 0.15, "h": 0.03, "page": 1}]
    },
    {
      "name": "Company Representative",
      "type": "text",
      "required": true,
      "areas": [{"x": 0.6, "y": 0.75, "w": 0.3, "h": 0.03, "page": 1}]
    },
    {
      "name": "Company Signature",
      "type": "signature",
      "required": true,
      "areas": [{"x": 0.6, "y": 0.82, "w": 0.3, "h": 0.05, "page": 1}]
    },
    {
      "name": "Company Date",
      "type": "date",
      "required": true,
      "default_value": "{{date}}",
      "areas": [{"x": 0.6, "y": 0.90, "w": 0.15, "h": 0.03, "page": 1}]
    }
  ]
}
```

### Two-Column Form

```json
{
  "fields": [
    {
      "name": "First Name",
      "type": "text",
      "areas": [{"x": 0.1, "y": 0.2, "w": 0.35, "h": 0.03, "page": 1}]
    },
    {
      "name": "Last Name",
      "type": "text",
      "areas": [{"x": 0.55, "y": 0.2, "w": 0.35, "h": 0.03, "page": 1}]
    },
    {
      "name": "Email",
      "type": "text",
      "areas": [{"x": 0.1, "y": 0.27, "w": 0.35, "h": 0.03, "page": 1}]
    },
    {
      "name": "Phone",
      "type": "text",
      "areas": [{"x": 0.55, "y": 0.27, "w": 0.35, "h": 0.03, "page": 1}]
    }
  ]
}
```

### Multi-Page Agreement with Initials

```json
{
  "fields": [
    {
      "name": "Page Acknowledgment",
      "type": "initials",
      "required": true,
      "areas": [
        {"x": 0.85, "y": 0.92, "w": 0.08, "h": 0.04, "page": 1},
        {"x": 0.85, "y": 0.92, "w": 0.08, "h": 0.04, "page": 2},
        {"x": 0.85, "y": 0.92, "w": 0.08, "h": 0.04, "page": 3}
      ]
    },
    {
      "name": "Final Signature",
      "type": "signature",
      "required": true,
      "areas": [{"x": 0.35, "y": 0.85, "w": 0.3, "h": 0.05, "page": 4}]
    }
  ]
}
```

---

## Field Properties Reference

### Common Properties (All Field Types)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Field identifier (shown to users) |
| `type` | string | Yes | Field type (see Field Types above) |
| `areas` | array | Yes | List of area objects defining field positions |
| `required` | boolean | No | Whether field must be filled (default: false) |
| `default_value` | string | No | Pre-filled value |
| `description` | string | No | Help text for users |

### Area Object Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `x` | float | Yes | Horizontal position (0-1) |
| `y` | float | Yes | Vertical position (0-1) |
| `w` | float | Yes | Width (0-1) |
| `h` | float | Yes | Height (0-1) |
| `page` | integer | Yes | Page number (1-indexed) |
| `attachment_uuid` | string | No | Document identifier for multi-document templates |

### Type-Specific Properties

#### Text Fields
- `validation_pattern` (string): Regex pattern for validation
- `max_length` (integer): Maximum character length

#### Select/Multi-Select Fields
- `options` (array): List of available options
- `allow_custom` (boolean): Allow user-entered values

#### Number Fields
- `min_value` (float): Minimum allowed value
- `max_value` (float): Maximum allowed value

#### Date Fields
- `date_format` (string): Date display format

---

## API Endpoint Reference

### Base URL
```
https://your-docuseal-instance.com/api
```

### Authentication
```http
X-Auth-Token: your_api_key_here
```

### Create Template

**POST** `/templates`

```json
{
  "name": "My Template",
  "pdf_url": "https://example.com/document.pdf",
  "fields": [...]
}
```

### Update Template Fields

**PUT** `/templates/{id}`

```json
{
  "fields": [...]
}
```

### Get Template

**GET** `/templates/{id}`

Response:
```json
{
  "id": "template_123",
  "name": "My Template",
  "fields": [...],
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Create Submission

**POST** `/submissions`

```json
{
  "template_id": "template_123",
  "submitters": [
    {
      "email": "client@example.com",
      "role": "Signer"
    }
  ],
  "send_email": true
}
```

### Get Submission Status

**GET** `/submissions/{id}`

Response:
```json
{
  "id": "submission_456",
  "status": "completed",
  "completed_at": "2024-01-15T11:30:00Z"
}
```

---

## Browser Automation Reference

### DocuSeal UI Structure

```
┌─────────────────────────────────────────────────┐
│ Header (Toolbar)                                │
├─────────────────────────────┬───────────────────┤
│                             │  Field Palette    │
│                             │  ┌─────────────┐  │
│                             │  │ Signature   │  │
│   Document Canvas           │  │ Initials    │  │
│   (PDF Preview)             │  │ Text        │  │
│                             │  │ Date        │  │
│                             │  │ Number      │  │
│                             │  │ Checkbox    │  │
│                             │  │ ...more     │  │
│                             │  └─────────────┘  │
│                             │                   │
└─────────────────────────────┴───────────────────┘
```

### Field Palette Selectors

When using browser automation to locate field types:

```python
FIELD_SELECTORS = {
    "signature": "[data-field-type='signature']",
    "initials": "[data-field-type='initials']",
    "text": "[data-field-type='text']",
    "date": "[data-field-type='date']",
    "number": "[data-field-type='number']",
    "checkbox": "[data-field-type='checkbox']",
    "radio": "[data-field-type='radio']",
    "select": "[data-field-type='select']",
}
```

### Canvas Identification

The document canvas typically has these characteristics:
- Class: `.document-canvas` or `.pdf-canvas`
- Contains rendered PDF pages
- Responds to drop events for field placement

### Drag-and-Drop Workflow

1. **Locate source field** in palette (right side)
2. **Calculate target position** on canvas
3. **Execute drag operation** using `left_click_drag`
4. **Verify placement** with screenshot
5. **Configure field properties** via UI

### Wait Conditions

After drag operations, wait for:
- Field appearance on canvas
- Property panel to open
- Save confirmation

```python
# Wait for field to appear
await page.wait_for_selector(f"[data-field-name='{field_name}']")

# Wait for UI to stabilize
await page.wait_for_timeout(1000)  # 1 second
```

---

## Performance Optimization

### Batch Operations

Create multiple fields in a single API call:

```json
{
  "fields": [
    {...field1...},
    {...field2...},
    {...field3...}
  ]
}
```

### Caching Strategies

- Cache template structure between operations
- Reuse browser sessions for multiple field additions
- Store validated coordinates for reuse

### Token Efficiency

When using Claude computer use:
- Take screenshots only when needed for decisions
- Use API for known operations
- Prefer text-based verification over visual when possible

---

## Security Considerations

### API Key Management

- Store API keys in environment variables
- Never commit API keys to version control
- Rotate keys regularly
- Use separate keys for dev/prod

### Coordinate Validation

Always validate coordinates before:
- Making API calls
- Performing drag operations
- Accepting user input

### Input Sanitization

For text fields with user input:
- Validate against patterns
- Escape special characters
- Limit field lengths
- Sanitize before storage

---

## Troubleshooting Guide

### Issue: Fields not appearing after API call

**Possible Causes**:
- Invalid coordinates (outside 0-1 range)
- Missing required properties
- Invalid template ID
- Authentication failure

**Solutions**:
1. Validate coordinates with validator script
2. Check all required properties present
3. Verify template ID exists
4. Confirm API key is valid

### Issue: Drag operation fails in browser

**Possible Causes**:
- Field palette not visible
- Canvas not loaded
- Incorrect pixel coordinate calculation
- Browser not focused

**Solutions**:
1. Wait for page load completion
2. Click canvas to focus
3. Verify palette expanded
4. Use API method instead

### Issue: Coordinate accuracy problems

**Possible Causes**:
- Screen resolution mismatch
- Canvas offset not accounted for
- Rounding errors in conversion

**Solutions**:
1. Use recommended 1024x768 resolution
2. Account for canvas offset in calculations
3. Increase precision in conversions
4. Prefer API over browser automation

---

## Additional Resources

- **DocuSeal Documentation**: https://docs.docuseal.co
- **API Reference**: https://docs.docuseal.co/api
- **GitHub Repository**: https://github.com/docusealco/docuseal
- **Community Forum**: https://github.com/docusealco/docuseal/discussions

---

**Last Updated**: 2025-01-27
**Skill Version**: 1.0.0
