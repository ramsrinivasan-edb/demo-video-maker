@echo off
cd /d "%~dp0"

echo ==================================================
echo       Launching Demo Video Maker UI...
echo ==================================================
echo.

:: 1. Check if virtual environment exists
if not exist ".venv" (
    echo ❌ Error: Virtual environment not found!
    echo Please double-click 'Install.bat' first to set up the app.
    echo.
    pause
    exit /b 1
)

:: 2. Activate environment and run UI
call .venv\Scripts\activate.bat
python demovideomaker.py

echo.
echo ==================================================
echo  App closed. You can now close this window.
echo ==================================================
pause