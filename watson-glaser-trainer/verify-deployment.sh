#!/bin/bash
# Deployment Verification Script for Watson Glaser TIS
# This script verifies that all required files are present and the system is ready to deploy

set -e  # Exit on any error

echo "🔍 Watson Glaser TIS - Deployment Verification"
echo "=============================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track verification status
ERRORS=0
WARNINGS=0

# Function to check if file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        ((ERRORS++))
        return 1
    fi
}

# Function to check if directory exists
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ (MISSING)"
        ((ERRORS++))
        return 1
    fi
}

# Function to check file size (warn if suspiciously small)
check_file_size() {
    if [ -f "$1" ]; then
        SIZE=$(wc -c < "$1" | tr -d ' ')
        if [ "$SIZE" -lt "$2" ]; then
            echo -e "${YELLOW}⚠${NC} $1 (only $SIZE bytes, expected >$2)"
            ((WARNINGS++))
            return 1
        fi
    fi
    return 0
}

echo "1. Checking Core Application Files"
echo "-----------------------------------"
check_file "advanced.html"
check_file_size "advanced.html" 50000
check_file "agent_profiles.js"
check_file_size "agent_profiles.js" 7000
check_file "index.html"
check_file "autonomous.html"
check_file "four_layer.html"
check_file "iframe_wrapper.html"
echo ""

echo "2. Checking Documentation Files"
echo "--------------------------------"
check_file "README.md"
check_file_size "README.md" 5000
check_file "LICENSE"
check_file_size "LICENSE" 1000
check_file "CONTRIBUTING.md"
check_file_size "CONTRIBUTING.md" 7000
check_file "SECURITY.md"
check_file_size "SECURITY.md" 5000
check_file "CHANGELOG.md"
check_file_size "CHANGELOG.md" 5000
check_file "INSTALL.md"
check_file_size "INSTALL.md" 9000
echo ""

echo "3. Checking Project Configuration"
echo "----------------------------------"
check_file "package.json"
check_file ".gitignore"
echo ""

echo "4. Checking Test Infrastructure"
echo "--------------------------------"
check_dir "tests"
check_file "tests/puppeteer_test.js"
check_file "tests/integration_test.js"
check_file "tests/validation.html"
check_file "tests/manual_test.md"
check_dir "tests/screenshots"
check_file "tests/screenshots/.gitkeep"
echo ""

echo "5. Checking Design Assets"
echo "--------------------------"
check_dir "design"
if [ -f "design/design_tokens.json" ]; then
    check_file "design/design_tokens.json"
fi
echo ""

echo "6. Validating File Contents"
echo "----------------------------"

# Check if LICENSE has MIT text
if grep -q "MIT License" LICENSE 2>/dev/null; then
    echo -e "${GREEN}✓${NC} LICENSE contains MIT License"
else
    echo -e "${RED}✗${NC} LICENSE missing MIT License text"
    ((ERRORS++))
fi

# Check if README has installation instructions
if grep -q "Quick Start" README.md 2>/dev/null; then
    echo -e "${GREEN}✓${NC} README.md has Quick Start section"
else
    echo -e "${YELLOW}⚠${NC} README.md missing Quick Start section"
    ((WARNINGS++))
fi

# Check if package.json has correct name
if grep -q '"name": "watson-glaser-tis"' package.json 2>/dev/null; then
    echo -e "${GREEN}✓${NC} package.json has correct name"
else
    echo -e "${YELLOW}⚠${NC} package.json name mismatch"
    ((WARNINGS++))
fi

# Check if advanced.html has AdvancedTestIntelligenceSystem
if grep -q "AdvancedTestIntelligenceSystem" advanced.html 2>/dev/null; then
    echo -e "${GREEN}✓${NC} advanced.html has TIS implementation"
else
    echo -e "${RED}✗${NC} advanced.html missing TIS implementation"
    ((ERRORS++))
fi

echo ""

echo "7. Checking Git Status"
echo "----------------------"
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current)
    echo -e "${GREEN}✓${NC} Git repository detected"
    echo "  Current branch: $BRANCH"
    
    # Check if there are uncommitted changes
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "${GREEN}✓${NC} No uncommitted changes"
    else
        echo -e "${YELLOW}⚠${NC} There are uncommitted changes"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} Not a git repository"
    ((WARNINGS++))
fi

echo ""

echo "8. Deployment Readiness Checks"
echo "-------------------------------"

# Check if README has placeholder URLs
if grep -q "YOUR_USERNAME" README.md 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} README.md contains placeholder YOUR_USERNAME"
    echo "  → Update with actual GitHub username before deployment"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} No placeholder URLs in README.md"
fi

# Check if INSTALL.md has placeholder URLs
if grep -q "YOUR_USERNAME" INSTALL.md 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} INSTALL.md contains placeholder YOUR_USERNAME"
    echo "  → Update with actual GitHub username before deployment"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} No placeholder URLs in INSTALL.md"
fi

# Check if package.json has placeholder URLs
if grep -q "YOUR_USERNAME" package.json 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} package.json contains placeholder YOUR_USERNAME"
    echo "  → Update with actual GitHub username before deployment"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} No placeholder URLs in package.json"
fi

echo ""

# Summary
echo "=============================================="
echo "Verification Summary"
echo "=============================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED${NC}"
    echo ""
    echo "🚀 System is ready for deployment!"
    echo ""
    echo "Next steps:"
    echo "  1. Update placeholder URLs (YOUR_USERNAME → your GitHub username)"
    echo "  2. Test locally: npm start or open advanced.html"
    echo "  3. Run tests: npm test"
    echo "  4. Push to GitHub: git push origin watson-glaser-tis-standalone"
    echo "  5. Deploy to GitHub Pages, Netlify, or Vercel"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ PASSED WITH WARNINGS${NC}"
    echo ""
    echo "Warnings: $WARNINGS"
    echo ""
    echo "System is functional but has minor issues."
    echo "Review warnings above before deployment."
    exit 0
else
    echo -e "${RED}✗ VERIFICATION FAILED${NC}"
    echo ""
    echo "Errors: $ERRORS"
    echo "Warnings: $WARNINGS"
    echo ""
    echo "Please fix the errors above before deployment."
    exit 1
fi
