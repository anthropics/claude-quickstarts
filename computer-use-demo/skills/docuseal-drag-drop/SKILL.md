---
name: docuseal-template-builder
description: Automate DocuSeal template builder drag-and-drop operations using computer use tools and API. Use when creating document templates, adding merge fields (signature, text, date boxes), or positioning fields on PDFs.
version: 1.0.0
dependencies: python>=3.8, playwright, requests
---

# DocuSeal Template Builder Automation

## When to Use This Skill

Use this skill when you need to:
- Create document templates with merge fields
- Position signature boxes, text fields, dates on PDF documents
- Automate DocuSeal template builder workflows
- Test template creation processes
- Add multiple fields to documents programmatically

## Coordinate System

DocuSeal uses **normalized coordinates** (0-1 range) rather than pixels:

- **x**: Horizontal position from 0 (left edge) to 1 (right edge)
- **y**: Vertical position from 0 (top edge) to 1 (bottom edge)
- **w**: Width as decimal (0.2 = 20% of page width)
- **h**: Height as decimal (0.05 = 5% of page height)

### Example Field Configuration

```json
{
  "name": "Client Signature",
  "type": "signature",
  "areas": [{
    "x": 0.403158,      // 40.3% from left
    "y": 0.042117,      // 4.2% from top
    "w": 0.100684,      // 10% of page width
    "h": 0.014236,      // 1.4% of page height
    "page": 1,          // Page number (1-indexed)
    "attachment_uuid": "doc-uuid"
  }]
}
```

## Preferred Automation Approach

Use this decision tree to choose the best automation method:

1. **API-First Mode** (Most Reliable)
   - Use when: You have exact coordinates for field placement
   - Advantages: Deterministic, fast, no coordinate accuracy issues
   - Method: REST API calls to create/update template fields

2. **Browser-Visual Mode** (For Discovery)
   - Use when: Need to identify element positions visually
   - Use when: Verifying field placement after API creation
   - Method: Screenshot analysis + computer use tools

3. **Hybrid Mode** (Recommended Default)
   - Create fields via API for reliability
   - Verify placement through browser screenshots
   - Adjust coordinates if needed based on visual feedback

## API Field Creation Pattern

Always validate coordinates before making API calls:

```python
# Step 1: Validate coordinates
python /home/computeruse/skills/docuseal-drag-drop/scripts/coordinate_validator.py \
  --x 0.5 --y 0.8 --w 0.2 --h 0.05

# Step 2: Create field via API
python /home/computeruse/skills/docuseal-drag-drop/scripts/field_creator.py \
  --template-id "abc123" \
  --field-json '{"name":"Signature","type":"signature","areas":[{"x":0.5,"y":0.8,"w":0.2,"h":0.05,"page":1}]}'
```

### API Endpoint Reference

- **Create Template**: `POST /api/templates`
- **Update Fields**: `PUT /api/templates/{id}`
- **Get Template**: `GET /api/templates/{id}`
- **Create Submission**: `POST /api/submissions`

Authentication: Use `X-Auth-Token` header with DocuSeal API key.

## Browser Automation Pattern

When visual interaction is needed:

### Step 1: Take Screenshot to Identify Canvas
```python
# Use computer tool to capture current state
screenshot = await computer_tool.screenshot()
```

### Step 2: Locate Field Palette
The field palette is typically on the right side of the screen containing draggable field types:
- Signature
- Initials
- Text
- Date
- Number
- Checkbox
- Radio
- Select
- Multi-select
- Image
- File
- Payment

### Step 3: Calculate Target Coordinates

If you have normalized coordinates (x, y, w, h) and need pixel coordinates:

```python
# For 1024x768 screen resolution
canvas_width = 800  # Approximate, varies by UI
canvas_height = 600
canvas_offset_x = 200
canvas_offset_y = 100

pixel_x = canvas_offset_x + (normalized_x * canvas_width)
pixel_y = canvas_offset_y + (normalized_y * canvas_height)
```

### Step 4: Perform Drag Operation

Use Claude's native `left_click_drag` action:

```json
{
  "action": "left_click_drag",
  "start_coordinate": [900, 300],  // Field palette position
  "coordinate": [600, 550]          // Target canvas position
}
```

### Step 5: Verify Placement

Always take a screenshot after drag to verify:
```python
verification_screenshot = await computer_tool.screenshot()
# Visually inspect if field appears at expected location
```

### Step 6: Retry if Needed

If placement is incorrect:
- Analyze what went wrong
- Adjust coordinates
- Retry drag operation

## Common Field Types and Recommended Sizes

| Field Type | Width (w) | Height (h) | Typical Use |
|------------|-----------|------------|-------------|
| Signature | 0.20 | 0.05 | Full signature boxes |
| Initials | 0.08 | 0.04 | Initial boxes |
| Text (short) | 0.15 | 0.03 | Names, emails |
| Text (long) | 0.40 | 0.03 | Addresses, descriptions |
| Date | 0.15 | 0.03 | Date fields |
| Number | 0.10 | 0.03 | Numeric inputs |
| Checkbox | 0.02 | 0.02 | Checkboxes |
| Radio | 0.02 | 0.02 | Radio buttons |

## Common Field Positions

### Document Headers (y: 0.05 - 0.15)
- Company logos, document titles, reference numbers

### Signature Blocks (y: 0.80 - 0.95)
- Bottom of documents for signatures and dates
- Typical signature: x=0.1, y=0.85, w=0.3, h=0.05
- Typical date: x=0.6, y=0.85, w=0.2, h=0.03

### Body Content (y: 0.20 - 0.75)
- Main form fields, text inputs, checkboxes
- Left column: x=0.1, w=0.35
- Right column: x=0.55, w=0.35

### Margins
- Left margin: x >= 0.05 (5% from left)
- Right margin: x + w <= 0.95 (5% from right)
- Top margin: y >= 0.05 (5% from top)
- Bottom margin: y + h <= 0.95 (5% from bottom)

## Error Handling

### Coordinate Validation Errors
If coordinate validator fails:
- Check all values are in proper ranges
- Ensure field doesn't exceed page boundaries
- Verify dimensions are reasonable (not too small)

### API Errors
If API call fails:
- Verify DOCUSEAL_URL and DOCUSEAL_API_KEY environment variables
- Check authentication token is valid
- Ensure template ID exists
- Verify JSON payload structure

### Browser Automation Errors
If drag operation fails:
- Take screenshot to debug
- Verify field palette is visible
- Check canvas is fully loaded
- Ensure coordinates are within viewport
- Try using keyboard navigation as fallback

## Validation Checklist

Before creating any field, verify:
- [ ] Coordinates are in 0-1 range
- [ ] Field doesn't exceed page boundaries (x+w<=1, y+h<=1)
- [ ] Field size is appropriate for type
- [ ] Field name is descriptive
- [ ] Page number is correct (1-indexed)
- [ ] Environment variables are set (DOCUSEAL_URL, DOCUSEAL_API_KEY)

## Advanced Features

### Multi-Page Documents
When adding fields to multi-page documents:
```json
{
  "areas": [
    {"x": 0.5, "y": 0.9, "w": 0.2, "h": 0.05, "page": 1},
    {"x": 0.5, "y": 0.9, "w": 0.2, "h": 0.05, "page": 3}
  ]
}
```

### Required Fields
Mark fields as required:
```json
{
  "name": "Signature",
  "required": true,
  "type": "signature",
  "areas": [...]
}
```

### Default Values
Set default values for text fields:
```json
{
  "name": "Country",
  "type": "text",
  "default_value": "United States",
  "areas": [...]
}
```

### Validation Patterns
Add regex validation for text fields:
```json
{
  "name": "Email",
  "type": "text",
  "validation_pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
  "areas": [...]
}
```

## Performance Tips

1. **Batch API Calls**: Create multiple fields in a single API call when possible
2. **Cache Screenshots**: Avoid taking unnecessary screenshots
3. **Use API Over Browser**: API is faster and more reliable for field creation
4. **Validate Before Creating**: Catch errors early with coordinate validation
5. **Resolution Optimization**: Use 1024x768 for optimal token efficiency

## Troubleshooting

### "Coordinate validation failed"
- Double-check your x, y, w, h values
- Ensure all are decimal numbers between 0 and 1
- Verify x+w and y+h don't exceed 1.0

### "API authentication failed"
- Check DOCUSEAL_API_KEY environment variable is set
- Verify API key is valid in DocuSeal admin panel
- Ensure using X-Auth-Token header (not Authorization)

### "Field not appearing in UI"
- Wait 2-3 seconds for UI to update after API call
- Refresh browser page if needed
- Verify template ID is correct
- Check field coordinates are within visible area

### "Drag operation failed"
- Ensure browser is focused (click on window first)
- Verify field palette is visible and not collapsed
- Use wait action between steps for UI to stabilize
- Try API method instead as fallback

## Reference Files

For detailed information, see:
- **REFERENCE.md**: Comprehensive field type specifications and coordinate examples
- **examples.json**: Ready-to-use field configuration templates
- **scripts/coordinate_validator.py**: Coordinate validation utility
- **scripts/field_creator.py**: API-based field creation utility

## Example Workflows

### Workflow 1: Create Simple Signature Template

```bash
# 1. Validate coordinates
python scripts/coordinate_validator.py --x 0.1 --y 0.85 --w 0.3 --h 0.05

# 2. Create signature field via API
python scripts/field_creator.py --template-id "template_123" --field-json '{
  "name": "Client Signature",
  "type": "signature",
  "required": true,
  "areas": [{"x": 0.1, "y": 0.85, "w": 0.3, "h": 0.05, "page": 1}]
}'

# 3. Create date field
python scripts/field_creator.py --template-id "template_123" --field-json '{
  "name": "Date Signed",
  "type": "date",
  "required": true,
  "areas": [{"x": 0.6, "y": 0.85, "w": 0.2, "h": 0.03, "page": 1}]
}'
```

### Workflow 2: Create Multi-Field Form with Verification

1. Create fields via API (batch operation)
2. Open template in browser
3. Take screenshot to verify all fields appear correctly
4. Adjust any misplaced fields
5. Take final screenshot for documentation

### Workflow 3: Complex Document with Multiple Pages

1. Analyze PDF structure (page count, key sections)
2. Plan field placement (header fields on page 1, signature on last page)
3. Validate all coordinates
4. Create all fields via API
5. Visual verification in browser
6. Test submission flow

## Best Practices

1. **Always use normalized coordinates (0-1 range)** - they scale properly
2. **Validate coordinates before API calls** - catch errors early
3. **Prefer API over browser automation** - more reliable and faster
4. **Take verification screenshots** - confirm successful field creation
5. **Use descriptive field names** - helps with debugging and maintenance
6. **Follow margin guidelines** - keep fields away from page edges
7. **Test submission flow** - ensure fields work correctly for end users
8. **Document field purposes** - add comments explaining complex layouts
9. **Use consistent sizing** - maintain visual harmony across similar fields
10. **Handle errors gracefully** - provide clear feedback on failures
