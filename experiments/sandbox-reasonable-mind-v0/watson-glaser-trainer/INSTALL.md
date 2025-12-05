# Installation & Deployment Guide

Complete guide for installing, running, testing, and deploying the Watson Glaser Test Intelligence System.

## 📋 Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Requirements

### For Users (Running the Application)

- **Browser**: Modern web browser
  - Chrome 90+
  - Firefox 88+
  - Safari 14+
  - Edge 90+
- **JavaScript**: Must be enabled
- **LocalStorage**: ~10MB available (default: 5-10MB)

### For Developers (Testing & Development)

- **Node.js**: 16.x or higher
- **npm**: 8.x or higher (comes with Node.js)
- **Git**: For version control
- **Text Editor**: VS Code, Sublime, etc.

## Installation

### Option 1: Direct Download

1. **Download the ZIP**

   ```bash
   # Download from GitHub
   curl -L https://github.com/slittyjuice-source/claude-quickstarts/archive/refs/heads/watson-glaser-tis-standalone.zip -o watson-glaser-tis.zip
   
   # Extract
   unzip watson-glaser-tis.zip
   cd watson-glaser-tis-standalone/watson-glaser-trainer
   ```

2. **Open in Browser**

   ```bash
   # macOS
   open advanced.html
   
   # Linux
   xdg-open advanced.html
   
   # Windows
   start advanced.html
   ```

### Option 2: Git Clone

1. **Clone Repository**

   ```bash
   git clone https://github.com/slittyjuice-source/claude-quickstarts.git
   cd claude-quickstarts
   git checkout watson-glaser-tis-standalone
   cd watson-glaser-trainer
   ```

2. **Verify Files**

   ```bash
   ls -la
   # Should see:
   # - advanced.html
   # - agent_profiles.js
   # - README.md
   # - etc.
   ```

### Option 3: npm Package (Coming Soon)

```bash
npm install watson-glaser-tis
npx watson-glaser-tis
```

## Running Locally

### Method 1: Direct Browser (Simplest)

**Pros**: No server needed, instant start  
**Cons**: Limited debugging, CORS restrictions for some features

```bash
cd watson-glaser-trainer
open advanced.html
```

### Method 2: Python HTTP Server (Recommended)

**Pros**: Proper MIME types, better debugging  
**Cons**: Requires Python

```bash
cd watson-glaser-trainer

# Python 3
python3 -m http.server 8080

# Python 2 (if you still have it)
python -m SimpleHTTPServer 8080

# Open browser to:
# http://localhost:8080/advanced.html
```

### Method 3: Node.js HTTP Server

**Pros**: Fast, modern, good for development  
**Cons**: Requires Node.js

```bash
cd watson-glaser-trainer

# Using http-server (install if needed)
npx http-server . -p 8080

# Using live-server (with auto-reload)
npx live-server --port=8080

# Open browser to:
# http://localhost:8080/advanced.html
```

### Method 4: VS Code Live Server

**Pros**: Auto-reload, integrated debugging  
**Cons**: Requires VS Code

1. Install "Live Server" extension
2. Right-click `advanced.html`
3. Select "Open with Live Server"

## Testing

### Quick Test

```bash
# Open validation interface
open tests/validation.html

# Follow the checklist to verify all features
```

### Automated Tests

1. **Install Test Dependencies**

   ```bash
   npm install
   ```

2. **Run Tests**

   ```bash
   # Puppeteer tests (automated browser testing)
   npm run test-puppeteer
   
   # Integration tests
   node tests/integration_test.js
   
   # All tests
   npm test
   ```

3. **View Test Results**

   ```bash
   # Check screenshots (if tests ran)
   ls -la tests/screenshots/
   ```

### Manual Testing

Follow the guide in `tests/manual_test.md`:

```bash
# View the manual test guide
cat tests/manual_test.md

# Or open in browser
open tests/manual_test.md
```

### Browser Compatibility Testing

Test in multiple browsers:

```bash
# Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome advanced.html

# Firefox
/Applications/Firefox.app/Contents/MacOS/firefox advanced.html

# Safari
open -a Safari advanced.html
```

## Deployment

### Option 1: GitHub Pages (Free, Easy)

1. **Enable GitHub Pages**

   ```bash
   # Settings > Pages > Source > main branch > /watson-glaser-trainer
   ```

2. **Access Your Site**

   ```
   https://slittyjuice-source.github.io/claude-quickstarts/watson-glaser-trainer/advanced.html
   ```

3. **Custom Domain (Optional)**
   - Add CNAME file
   - Configure DNS

### Option 2: Netlify (Free, Easy, CDN)

1. **Deploy via Git**

   ```bash
   # Connect GitHub repo to Netlify
   # Build command: (leave empty)
   # Publish directory: watson-glaser-trainer
   ```

2. **Or Drag & Drop**
   - Drag `watson-glaser-trainer` folder to Netlify

3. **Custom Domain**
   - Configure in Netlify dashboard

### Option 3: Vercel (Free, Fast)

1. **Install Vercel CLI**

   ```bash
   npm install -g vercel
   ```

2. **Deploy**

   ```bash
   cd watson-glaser-trainer
   vercel
   ```

3. **Production**

   ```bash
   vercel --prod
   ```

### Option 4: CloudFlare Pages (Free, CDN)

1. **Connect Repository**
   - Sign in to CloudFlare Pages
   - Connect GitHub repo

2. **Configure Build**
   - Build command: (none)
   - Output directory: watson-glaser-trainer

3. **Deploy**
   - Automatic on git push

### Option 5: Static Hosting (AWS S3, Google Cloud Storage)

**AWS S3:**

```bash
# Install AWS CLI
aws s3 sync watson-glaser-trainer/ s3://your-bucket-name/ --acl public-read

# Enable static website hosting in S3 console
```

**Google Cloud Storage:**

```bash
# Install gcloud CLI
gsutil -m cp -r watson-glaser-trainer/* gs://your-bucket-name/

# Set bucket to public
gsutil iam ch allUsers:objectViewer gs://your-bucket-name
```

### Option 6: Self-Hosted Server

**Nginx Configuration:**

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/watson-glaser-tis/watson-glaser-trainer;
    index advanced.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**Apache Configuration:**

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /var/www/watson-glaser-tis/watson-glaser-trainer
    DirectoryIndex advanced.html
    
    <Directory /var/www/watson-glaser-tis/watson-glaser-trainer>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
```

## Configuration

### Agent Profiles

Edit `agent_profiles.js` to customize:

```javascript
{
    id: "custom-agent",
    name: "Custom Agent",
    stage: "Custom Stage",
    neuralParams: {
        adaptationRate: 0.20,      // 0.01-0.30
        explorationFactor: 0.30,   // 0.10-0.50
        memoryRetention: 0.90,     // 0.50-0.95
        confidenceThreshold: 0.75, // 0.50-0.90
        creativityBoost: 0.25      // 0.10-0.40
    },
    achievements: [
        { year: "2024", title: "Custom Achievement" }
    ]
}
```

### UI Customization

Edit `design/design_tokens.json`:

```json
{
    "colors": {
        "primary": "#667eea",
        "success": "#48bb78",
        "error": "#f56565"
    },
    "spacing": {
        "base": 8
    }
}
```

### Performance Tuning

For slower devices:

```javascript
// In advanced.html, change default layers
const tis = new AdvancedTestIntelligenceSystem();
// Change in constructor: layers=4 instead of 8
```

## Troubleshooting

### Installation Issues

**Problem**: Can't clone repository

```bash
# Solution: Use HTTPS instead of SSH
git clone https://github.com/slittyjuice-source/claude-quickstarts.git
```

**Problem**: npm install fails

```bash
# Solution: Clear cache and retry
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Runtime Issues

**Problem**: Blank white screen

- Check browser console for errors (F12)
- Ensure JavaScript is enabled
- Try incognito/private mode
- Clear browser cache

**Problem**: LocalStorage quota exceeded

```javascript
// Clear in browser console
localStorage.clear();
```

**Problem**: Slow performance

- Reduce to 4x layers in background mode
- Clear neural bank (> 50 patterns)
- Close other browser tabs
- Restart browser

### Testing Issues

**Problem**: Puppeteer tests fail

```bash
# Install Chrome/Chromium
npm install puppeteer --save-dev

# Or use system Chrome
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
```

**Problem**: Tests timeout

```bash
# Increase timeout in test file
page.waitForSelector('#element', { timeout: 30000 });
```

### Deployment Issues

**Problem**: 404 on GitHub Pages

- Check Pages settings: Source branch and folder
- Wait 5-10 minutes for propagation
- Ensure `advanced.html` is in published directory

**Problem**: CORS errors

- Use proper HTTP server, not file:// protocol
- Check server CORS headers
- Enable CORS in deployment config

## Verification Checklist

After installation/deployment, verify:

- [ ] Page loads without errors
- [ ] Can select agent profile
- [ ] Questions generate correctly
- [ ] Can answer questions
- [ ] Feedback displays
- [ ] Metrics update
- [ ] LocalStorage saves/loads
- [ ] Background mode works
- [ ] View mode switches
- [ ] All tests pass

## Support

For installation help:

1. Check this guide
2. Review [Troubleshooting](#troubleshooting)
3. Check [GitHub Issues](https://github.com/slittyjuice-source/claude-quickstarts/issues)
4. Open a new issue with:
   - OS and browser version
   - Installation method used
   - Error messages
   - Steps already tried

## Updates

Stay updated:

```bash
# Pull latest changes
git pull origin watson-glaser-tis-standalone

# Check for new versions
git fetch --tags
git tag -l
```

---

**Last Updated**: December 2024  
**Installation Guide Version**: 1.0
