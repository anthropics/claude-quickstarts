# GitHub Pages Deployment Guide

Quick guide to deploy Watson Glaser TIS to GitHub Pages.

## Prerequisites

- Repository pushed to GitHub (✓ completed)
- Admin access to repository settings

## Deployment Steps

### 1. Enable GitHub Pages

1. **Navigate to Repository Settings**

   ```
   https://github.com/slittyjuice-source/claude-quickstarts/settings
   ```

2. **Go to Pages Section**
   - Left sidebar → Click "Pages"

3. **Configure Source**
   - Source: Deploy from a branch
   - Branch: `watson-glaser-tis-standalone`
   - Folder: `/watson-glaser-trainer` (or `/root` and navigate to subdirectory)
   - Click "Save"

4. **Wait for Deployment**
   - GitHub will build and deploy (usually 1-3 minutes)
   - Green checkmark appears when ready
   - URL will be displayed at top of Pages settings

### 2. Access Your Site

Your site will be available at:

```
https://slittyjuice-source.github.io/claude-quickstarts/watson-glaser-trainer/advanced.html
```

Or if you deployed from root:

```
https://slittyjuice-source.github.io/claude-quickstarts/advanced.html
```

### 3. Custom Domain (Optional)

If you want a custom domain like `watson-glaser.example.com`:

1. **Add CNAME Record in DNS**

   ```
   Type: CNAME
   Name: watson-glaser (or @)
   Value: slittyjuice-source.github.io
   ```

2. **Configure in GitHub Pages**
   - In Pages settings, enter custom domain
   - Save and wait for DNS check
   - Enable "Enforce HTTPS"

### 4. Verify Deployment

Test these URLs after deployment:

- Main app: `/advanced.html`
- Agent profiles: `/agent_profiles.js` (should download/show)
- Tests: `/tests/validation.html`
- Design tokens: `/design/design_tokens.json`

### 5. Update Links (if needed)

If your deployment URL differs from the docs:

1. Update README.md with actual URL
2. Update INSTALL.md references
3. Commit and push changes

## Troubleshooting

### 404 Error

**Problem**: Page not found

**Solutions**:

- Wait 5-10 minutes for GitHub to propagate
- Check branch name is correct
- Verify folder path in settings
- Ensure `advanced.html` exists in published directory

### Blank Page

**Problem**: Page loads but is blank

**Solutions**:

- Open browser console (F12) to check errors
- Verify `agent_profiles.js` loads correctly
- Check CORS/mixed content warnings
- Clear browser cache and reload

### Files Not Loading

**Problem**: JavaScript/CSS not loading

**Solutions**:

- Check paths are relative (not absolute)
- Verify file names match exactly (case-sensitive)
- Check GitHub Pages build log for errors

### Custom Domain Not Working

**Problem**: Custom domain shows certificate error

**Solutions**:

- Wait 24-48 hours for DNS propagation
- Verify CNAME record is correct
- Try "Remove custom domain" then re-add
- Ensure "Enforce HTTPS" is enabled

## Alternative: Deploy from Main Branch

If you want to merge into main and deploy from there:

```bash
# Merge standalone into main
git checkout main
git merge watson-glaser-tis-standalone
git push origin main

# Then configure GitHub Pages to deploy from main branch
```

## Alternative: Netlify Deployment

If GitHub Pages doesn't work:

### Quick Deploy

1. **Drag & Drop**
   - Go to <https://app.netlify.com/drop>
   - Drag `watson-glaser-trainer/` folder
   - Get instant live URL

### Git Deploy

1. **Connect Repository**

   ```bash
   # Install Netlify CLI
   npm install -g netlify-cli
   
   # Login
   netlify login
   
   # Deploy
   cd watson-glaser-trainer
   netlify deploy --prod
   ```

2. **Configuration**
   - Build command: (leave empty)
   - Publish directory: `.`
   - Branch: `watson-glaser-tis-standalone`

3. **Custom Domain**
   - Add domain in Netlify dashboard
   - Update DNS with Netlify nameservers

## Alternative: Vercel Deployment

For Vercel deployment:

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd watson-glaser-trainer
vercel --prod

# Follow prompts
```

## Post-Deployment Checklist

After deployment, verify:

- [ ] Main page loads: `advanced.html`
- [ ] Can select agent profile
- [ ] Can generate questions
- [ ] Extended Thinking works
- [ ] localStorage persists data
- [ ] All 5 question types work
- [ ] Developer view switches
- [ ] Background mode functions
- [ ] Tests page accessible: `/tests/validation.html`
- [ ] No console errors (F12)

## Maintenance

### Update Deployment

To update after code changes:

```bash
# Make changes
git add .
git commit -m "Update: description"
git push origin watson-glaser-tis-standalone

# GitHub Pages auto-deploys
# Wait 2-3 minutes, then hard refresh browser
```

### Monitor

- GitHub Actions tab shows build status
- Pages settings shows last deployment time
- Check "Visit site" link to verify live version

## Support

If deployment issues persist:

1. Check [GitHub Pages documentation](https://docs.github.com/en/pages)
2. Review [GitHub status](https://www.githubstatus.com/)
3. Open issue in repository
4. Try alternative platform (Netlify/Vercel)

---

**Estimated Time**: 5-10 minutes (excluding DNS propagation)  
**Cost**: Free  
**SSL**: Automatic (Let's Encrypt)
