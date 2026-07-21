@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==================================================
echo       Setting up Demo Video Maker (Windows)
echo ==================================================
echo.

:: 1. Check/Install dependencies via Winget
echo --> Checking system dependencies (Python, FFmpeg)...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo --> Installing Python via Winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
)

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo --> Installing FFmpeg via Winget...
    winget install -e --id GCP.FFmpeg --accept-package-agreements --accept-source-agreements
)

:: 2. Create Python virtual environment
echo --> Creating local Python virtual environment...
if not exist ".venv" (
    python -m venv .venv
)

:: 3. Install Python requirements
echo --> Installing AI voice model dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ==================================================
    echo  SUCCESS! Everything is installed and ready.
    echo  You can now double-click 'Start VideoMaker.bat'!
    echo ==================================================
) else (
    echo.
    echo ==================================================
    echo  ❌ ERROR: Failed to install Python dependencies.
    echo ==================================================
)

pause