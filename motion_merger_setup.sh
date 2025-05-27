#!/bin/bash

# Motion Merger Setup Script
# Sets up the environment for merging legal motion versions

echo "🚀 Setting up Motion Merger Workflow..."

# Function to convert Windows paths to WSL paths
convert_path() {
    echo "$1" | sed 's|C:\\|/mnt/c/|g' | sed 's|\\|/|g'
}

# Check if we're in WSL
if [ -f /proc/version ] && grep -qi microsoft /proc/version; then
    echo "✅ Running in WSL environment"
else
    echo "❌ This script should be run in WSL"
    exit 1
fi

# Navigate to unified-redaction-hub
REDACTION_HUB="/home/lroc/unified-redaction-hub"
if [ -d "$REDACTION_HUB" ]; then
    echo "✅ Found unified-redaction-hub at $REDACTION_HUB"
    
    # Create symlink for easy access
    if [ ! -L ~/motion-merger ]; then
        ln -s "$REDACTION_HUB" ~/motion-merger
        echo "✅ Created symlink: ~/motion-merger"
    fi
    
    # Check if virtual environment exists
    if [ -d "$REDACTION_HUB/venv" ]; then
        echo "✅ Virtual environment exists"
        echo ""
        echo "📋 Quick Start Commands:"
        echo "   cd ~/motion-merger"
        echo "   source venv/bin/activate"
        echo "   python3 modern_elo_merger.py"
        echo ""
        echo "📁 For VS Code with WSL Remote:"
        echo "   code ~/motion-merger"
        echo ""
    else
        echo "⚠️  Virtual environment not found at $REDACTION_HUB/venv"
    fi
else
    echo "❌ unified-redaction-hub not found at expected location"
    echo "   Expected: $REDACTION_HUB"
fi

echo ""
echo "🎯 Motion File Access Examples:"
echo "   Windows: C:\Users\ramon\Documents\motion_v1.docx"
echo "   WSL:     /mnt/c/Users/ramon/Documents/motion_v1.docx"
echo ""
echo "💡 Tip: Place your motion files in a Windows folder for easy access"
echo "   Suggested: C:\\Users\\ramon\\Documents\\Motions\\"