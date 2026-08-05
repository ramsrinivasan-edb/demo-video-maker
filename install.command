#!/bin/bash
# Automatically navigate to the directory where this script is located
cd "$(dirname "$0")"

echo "=================================================="
echo "      Setting up Demo Video Maker                 "
echo "=================================================="
echo ""

# 1. Install Homebrew automatically if missing
if ! command -v brew &> /dev/null; then
    echo "--> Installing Homebrew package manager..."
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for current session (Apple Silicon & Intel Mac support)
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"
fi

# 2. Install required system dependencies
echo "--> Installing media utilities (ffmpeg, vhs, python3)..."
brew install vhs ffmpeg python3

# 3. Create the Python virtual environment
echo "--> Creating local Python environment..."
python3 -m venv .venv

# 4. Install Python libraries using explicit environment binary
echo "--> Installing AI voice model dependencies (this may take a few minutes)..."
.venv/bin/pip install --upgrade pip
if .venv/bin/pip install -r requirements.txt; then
    echo "--> Checking optional alignment model (Ollama)..."
    if command -v ollama >/dev/null; then
        ollama pull qwen2.5:3b || echo "    (couldn't pull qwen2.5:3b now — auto-sync falls back until available)"
    else
        echo "    (Ollama not found — auto-sync will fall back to proportional pacing."
        echo "     Optional: install from https://ollama.com, then run: ollama pull qwen2.5:3b)"
    fi
    echo ""
    echo "=================================================="
    echo " SUCCESS! Everything is installed and ready."
    echo " You can now close this window and double-click"
    echo " 'Start VideoMaker.command' to run the app!"
    echo "=================================================="
else
    echo ""
    echo "=================================================="
    echo " ❌ ERROR: Failed to install Python dependencies."
    echo " Please check your internet connection and try again."
    echo "=================================================="
fi

read -p "Press [Enter] to exit..." 