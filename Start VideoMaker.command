#!/bin/bash
# Automatically navigate to the directory where this script is located
cd "$(dirname "$0")"

echo "=================================================="
echo "      Launching Demo Video Maker UI...            "
echo "=================================================="
echo ""

# 1. Check if the virtual environment exists first
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "Please double-click 'Install.command' first to set up the app."
    echo ""
    read -p "Press [Enter] to exit..."
    exit 1
fi

# 2. Activate environment and launch the UI
source .venv/bin/activate
python3 demovideomaker.py

# 3. Keep terminal open after closing UI to display any logs/errors
echo ""
echo "=================================================="
echo " App closed. You can now close this terminal window."
echo "=================================================="
read -p "Press [Enter] to exit..."