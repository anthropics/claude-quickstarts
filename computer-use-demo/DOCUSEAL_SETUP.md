# DocuSeal Template Builder Automation - Setup Guide

This guide provides step-by-step instructions for setting up and using the Claude Computer Use agent with DocuSeal template builder automation capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Development Setup](#development-setup)
6. [Usage Examples](#usage-examples)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)
9. [Architecture](#architecture)
10. [Security Considerations](#security-considerations)

---

## Overview

This implementation adds DocuSeal template builder automation to the Anthropic Computer Use demo. It provides:

- **Claude Skills** for DocuSeal automation knowledge
- **Hybrid Automation** combining API calls and browser automation
- **Coordinate Management** for normalized (0-1 range) field positioning
- **Natural Mouse Movement** for human-like drag-and-drop
- **REST API Client** for reliable field creation
- **Full Test Suite** for validation and integration testing

### Architecture Highlights

```
┌─────────────────────────────────────────────────┐
│    Claude Computer Use Agent                    │
│    (with DocuSeal Skill)                        │
└────────────┬────────────────────────────────────┘
             │
      ┌──────┴──────┐
      │  Controller  │ (Chooses Strategy)
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

---

## Prerequisites

### System Requirements

- **Docker** and **Docker Compose** (recommended) OR
- **Python 3.11+** for local development
- **4GB RAM** minimum (8GB recommended)
- **Linux, macOS, or Windows** with WSL2

### API Keys

1. **Anthropic API Key** - Get from [Claude Console](https://console.anthropic.com/)
2. **DocuSeal API Key** - Generate from DocuSeal admin panel (Settings > API Keys)

### DocuSeal Instance

You can either:
- Use the included Docker Compose stack (easiest)
- Connect to an existing DocuSeal instance
- Use DocuSeal Cloud

---

## Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone the repository** (if not already done):
   ```bash
   cd /path/to/claude-quickstarts/computer-use-demo
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` file** with your API keys:
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_key_here
   DOCUSEAL_API_KEY=your_docuseal_key_here  # Generate after DocuSeal starts
   SECRET_KEY_BASE=$(openssl rand -hex 32)  # Generate secure key
   ```

4. **Start the stack**:
   ```bash
   docker-compose up -d
   ```

5. **Access the interfaces**:
   - Claude Agent: http://localhost:8080
   - DocuSeal: http://localhost:3000
   - VNC: http://localhost:6080/vnc.html

6. **Generate DocuSeal API Key**:
   - Open DocuSeal at http://localhost:3000
   - Create an account / log in
   - Go to Settings > API Keys
   - Generate new API key
   - Update `.env` with the key and restart:
     ```bash
     docker-compose restart claude-agent
     ```

### Option 2: Local Development

1. **Set up Python environment**:
   ```bash
   cd computer-use-demo
   ./setup.sh
   ```

2. **Install dependencies**:
   ```bash
   pip install -r computer_use_demo/requirements.txt
   playwright install chromium
   ```

3. **Configure environment**:
   ```bash
   export ANTHROPIC_API_KEY="your_key_here"
   export DOCUSEAL_URL="http://localhost:3000"
   export DOCUSEAL_API_KEY="your_docuseal_key"
   ```

4. **Build Docker image**:
   ```bash
   docker build -t computer-use-demo:local .
   ```

5. **Run container**:
   ```bash
   docker run \
     -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
     -e DOCUSEAL_URL=$DOCUSEAL_URL \
     -e DOCUSEAL_API_KEY=$DOCUSEAL_API_KEY \
     -v $(pwd)/computer_use_demo:/home/computeruse/computer_use_demo/ \
     -v $(pwd)/skills:/home/computeruse/skills/ \
     -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
     -it computer-use-demo:local
   ```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key | - |
| `DOCUSEAL_URL` | Yes | DocuSeal instance URL | `http://docuseal:3000` |
| `DOCUSEAL_API_KEY` | Yes | DocuSeal API key | - |
| `WIDTH` | No | Display width | `1024` |
| `HEIGHT` | No | Display height | `768` |
| `API_PROVIDER` | No | API provider (anthropic/bedrock/vertex) | `anthropic` |
| `SECRET_KEY_BASE` | Yes* | DocuSeal encryption key | - |

*Required only if running DocuSeal

### Display Resolution

The recommended resolution is **1024x768 (XGA)**:
- Optimal token efficiency (tokens = width × height / 750)
- Good balance between detail and performance
- Compatible with Claude's spatial reasoning capabilities

To change resolution:
```bash
# In .env file
WIDTH=1280
HEIGHT=800
```

### DocuSeal Skill Configuration

The skill is automatically loaded from `/home/computeruse/skills/docuseal-drag-drop/`. Claude will use it automatically when:
- User mentions DocuSeal, templates, or document signing
- Task involves field creation or form automation
- Drag-and-drop operations are needed

No explicit skill invocation required - Claude's skill discovery handles this automatically.

---

## Development Setup

### Project Structure

```
computer-use-demo/
├── computer_use_demo/
│   ├── tools/
│   │   └── docuseal/           # DocuSeal integration
│   │       ├── __init__.py
│   │       ├── api_client.py   # REST API client
│   │       ├── controller.py   # Hybrid automation controller
│   │       ├── coordinates.py  # Coordinate conversion
│   │       └── human_cursor.py # Natural mouse movement
│   └── requirements.txt
├── skills/
│   └── docuseal-drag-drop/     # Claude skill
│       ├── SKILL.md            # Main skill instructions
│       ├── REFERENCE.md        # Detailed reference
│       ├── scripts/
│       │   ├── coordinate_validator.py
│       │   └── field_creator.py
│       └── examples/
│           └── field_templates.json
├── tests/
│   └── tools/
│       └── docuseal_test.py    # Unit tests
├── Dockerfile
├── docker-compose.yml
└── DOCUSEAL_SETUP.md          # This file
```

### Making Changes

1. **Edit Code Locally**:
   ```bash
   # Changes in computer_use_demo/ and skills/ are automatically mounted
   vim computer_use_demo/tools/docuseal/controller.py
   ```

2. **Restart Container** (if needed):
   ```bash
   docker-compose restart claude-agent
   ```

3. **View Logs**:
   ```bash
   docker-compose logs -f claude-agent
   ```

### Running Tests

```bash
# Run all tests
docker-compose exec claude-agent pytest

# Run specific test file
docker-compose exec claude-agent pytest tests/tools/docuseal_test.py

# Run with verbose output
docker-compose exec claude-agent pytest -v

# Run with coverage
docker-compose exec claude-agent pytest --cov=computer_use_demo.tools.docuseal
```

---

## Usage Examples

### Example 1: Create Simple Signature Template

**Prompt to Claude**:
```
Create a DocuSeal template with a signature field at the bottom left
and a date field at the bottom right. Template ID is "template_abc123".
```

**What Claude Does**:
1. Loads DocuSeal skill automatically
2. Validates template access via API
3. Creates signature field at (x=0.1, y=0.85, w=0.3, h=0.05)
4. Creates date field at (x=0.6, y=0.85, w=0.15, h=0.03)
5. Verifies creation (optionally with screenshot)

### Example 2: Create Contact Form

**Prompt to Claude**:
```
Add a two-column contact form to template "template_xyz789" with:
- First Name and Last Name in the first row
- Email and Phone in the second row
- Address in the third row (full width)
```

**Claude executes**:
```python
# Uses batch API call to create all fields at once
fields = [
    {"name": "First Name", "type": "text", "x": 0.1, "y": 0.2, "w": 0.35, "h": 0.03},
    {"name": "Last Name", "type": "text", "x": 0.55, "y": 0.2, "w": 0.35, "h": 0.03},
    # ... more fields
]
```

### Example 3: Validate Coordinates

**Direct Script Usage**:
```bash
# Inside container
python /home/computeruse/skills/docuseal-drag-drop/scripts/coordinate_validator.py \
  --x 0.5 --y 0.8 --w 0.2 --h 0.05 --show-warnings --verbose
```

### Example 4: Create Field via API Script

```bash
# Inside container
python /home/computeruse/skills/docuseal-drag-drop/scripts/field_creator.py \
  --template-id "template_123" \
  --field-json '{
    "name": "Client Signature",
    "type": "signature",
    "required": true,
    "areas": [{"x": 0.1, "y": 0.85, "w": 0.3, "h": 0.05, "page": 1}]
  }'
```

---

## Testing

### Unit Tests

Test coordinate validation, conversion, and utilities:
```bash
pytest tests/tools/docuseal_test.py::TestCoordinateValidation
```

### Integration Tests

Test full workflows (requires running DocuSeal instance):
```bash
# Set test environment
export DOCUSEAL_URL="http://localhost:3000"
export DOCUSEAL_API_KEY="test_key"

# Run integration tests
pytest tests/tools/docuseal_test.py -m integration
```

### Manual Testing Checklist

- [ ] Claude can access DocuSeal skill automatically
- [ ] API field creation works with valid coordinates
- [ ] Coordinate validator catches invalid inputs
- [ ] Browser automation can drag fields (if implemented)
- [ ] Screenshot verification works
- [ ] Multi-field batch creation succeeds
- [ ] Error handling provides clear messages

---

## Troubleshooting

### Issue: "DocuSeal URL not configured"

**Cause**: Missing `DOCUSEAL_URL` environment variable

**Solution**:
```bash
# Add to .env file
DOCUSEAL_URL=http://docuseal:3000

# Or export directly
export DOCUSEAL_URL="http://localhost:3000"

# Restart container
docker-compose restart claude-agent
```

### Issue: "API authentication failed"

**Cause**: Invalid or missing `DOCUSEAL_API_KEY`

**Solution**:
1. Open DocuSeal: http://localhost:3000
2. Go to Settings > API Keys
3. Generate new API key
4. Update `.env` file
5. Restart: `docker-compose restart claude-agent`

### Issue: "Coordinate validation failed"

**Cause**: Coordinates outside 0-1 range or exceed page boundaries

**Solution**:
```bash
# Validate coordinates first
python skills/docuseal-drag-drop/scripts/coordinate_validator.py \
  --x 0.9 --y 0.5 --w 0.2 --h 0.1

# Adjust coordinates to fit within page
# x + w must be <= 1.0
# y + h must be <= 1.0
```

### Issue: "Fields not appearing in UI"

**Possible Causes & Solutions**:

1. **API call succeeded but UI not updated**:
   - Wait 2-3 seconds and refresh browser
   - Check DocuSeal logs: `docker-compose logs docuseal`

2. **Coordinates place field off-screen**:
   - Validate coordinates are in visible range
   - Check margins: x >= 0.05, x+w <= 0.95

3. **Template ID incorrect**:
   - Verify template exists via API
   - Check logs for authentication errors

### Issue: "Container won't start"

**Check logs**:
```bash
docker-compose logs claude-agent
```

**Common causes**:
- Port conflicts (5900, 8501, 6080, 8080)
- Missing environment variables
- Insufficient Docker resources

**Solutions**:
```bash
# Check port usage
lsof -i :8080

# Free up ports or change in docker-compose.yml
ports:
  - "8081:8080"  # Use different host port

# Increase Docker resources
# Docker Desktop > Settings > Resources > Memory: 4GB+
```

### Issue: "Playwright browser not found"

**Solution**:
```bash
# Rebuild Docker image to install Playwright browsers
docker-compose build --no-cache claude-agent
docker-compose up -d
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f claude-agent
docker-compose logs -f docuseal

# Last 100 lines
docker-compose logs --tail=100 claude-agent
```

---

## Architecture

### Hybrid Automation Strategy

The controller intelligently chooses between three modes:

1. **API-First Mode** (Default for known coordinates)
   - Fastest and most reliable
   - Direct REST API calls
   - No browser interaction needed

2. **Browser-Visual Mode** (For discovery)
   - Take screenshots to identify elements
   - Calculate coordinates visually
   - Useful when positions unknown

3. **Hybrid Mode** (For verification)
   - Create via API
   - Verify visually via screenshot
   - Best of both worlds

### Decision Logic

```python
if has_exact_coordinates:
    if needs_verification:
        use_hybrid_mode()
    else:
        use_api_mode()
else:
    use_browser_mode()
```

### Coordinate System

**Why Normalized Coordinates?**
- Resolution independent
- Work across different devices
- Natural for AI percentage-based reasoning
- DocuSeal's native format

**Conversion Example**:
```python
# Normalized: x=0.5 means "50% from left"
# On 1000px wide page: 0.5 * 1000 = 500px

# Pixel coordinate (500, 600) on 1000x1200 page
# Normalized: (500/1000, 600/1200) = (0.5, 0.5)
```

---

## Security Considerations

### API Key Management

**DO**:
- Store keys in environment variables
- Use `.env` file (never commit to git)
- Rotate keys regularly
- Use separate keys for dev/staging/prod

**DON'T**:
- Hardcode keys in source code
- Commit `.env` to version control
- Share keys in plain text
- Use production keys in development

### Docker Security

```bash
# Use secrets in production
docker secret create docuseal_api_key /path/to/key

# Run as non-root (already configured)
USER computeruse

# Limit container capabilities
docker-compose.yml:
  security_opt:
    - no-new-privileges:true
```

### Network Isolation

The Docker Compose setup creates an isolated network:
- Services communicate via internal network
- Only necessary ports exposed to host
- Database not exposed externally

### Production Deployment

**Additional steps for production**:

1. **Use HTTPS**:
   ```yaml
   # docker-compose.yml
   nginx:
     volumes:
       - ./ssl:/etc/nginx/ssl:ro
   ```

2. **Secure Database**:
   ```yaml
   postgres:
     environment:
       - POSTGRES_PASSWORD=${STRONG_PASSWORD}
   ```

3. **Enable Firewall**:
   ```bash
   # Only allow necessary ports
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```

4. **Regular Updates**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

---

## Performance Optimization

### Token Usage

Screenshots are expensive:
- Formula: `tokens = (width * height) / 750`
- 1024x768 ≈ 1,050 tokens per screenshot
- Use API calls when possible to avoid screenshots

### Batch Operations

Create multiple fields in one API call:
```python
# Bad: 10 API calls
for field in fields:
    api.create_field(field)

# Good: 1 API call
api.create_fields_batch(fields)
```

### Caching

- Template structure cached between operations
- Coordinate validation cached
- Browser sessions reused when possible

---

## Additional Resources

- **DocuSeal Documentation**: https://docs.docuseal.co
- **DocuSeal API Reference**: https://docs.docuseal.co/api
- **Anthropic Computer Use Docs**: https://docs.anthropic.com/en/docs/build-with-claude/computer-use
- **Claude Skills Guide**: https://docs.anthropic.com/en/docs/build-with-claude/skills
- **GitHub Issues**: https://github.com/anthropics/anthropic-quickstarts/issues

---

## Support

For issues or questions:

1. Check this documentation first
2. Review troubleshooting section
3. Check existing GitHub issues
4. Create new issue with:
   - Error messages and logs
   - Steps to reproduce
   - Environment details (OS, Docker version, etc.)

---

**Last Updated**: 2025-01-27
**Version**: 1.0.0
