# Puppeteer Test Troubleshooting

## Issue: Chrome Launch Failure on macOS

The Puppeteer tests may fail on macOS with Rosetta-related warnings and browser launch errors.

## Solutions

### Option 1: Use Playwright (Recommended)

Playwright has better macOS compatibility:

```bash
npm install --save-dev playwright
```

Then use `tests/playwright_test.js` instead (if created).

### Option 2: Specify Chrome Path

If you have Chrome installed:

```bash
export PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
npm run test-puppeteer
```

### Option 3: Use Chromium from Puppeteer

Reinstall Puppeteer with Chromium:

```bash
npm uninstall puppeteer
npm install puppeteer --force
```

### Option 4: Skip Browser Tests

Run only integration tests:

```bash
npm run test-integration
```

## Current Status

The enhanced Puppeteer configuration includes:
- Multiple compatibility flags (`--no-sandbox`, `--disable-setuid-sandbox`, etc.)
- Support for custom Chrome path via `PUPPETEER_EXECUTABLE_PATH`
- Single-process mode for better compatibility

## Alternative Testing

Use the manual browser testing approach:

```bash
# Start server
python3 -m http.server 8080

# Open in browser
open http://localhost:8080/advanced.html
```

Then manually verify:
1. Agent selector loads
2. Questions render
3. Answers can be selected
4. Neural evolution updates work
