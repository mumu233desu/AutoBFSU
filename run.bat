@echo off
rem ====================================================================
rem AutoBFSU Quick Start Script (Windows)
rem ====================================================================
cd /d "%~dp0"

echo [AutoBFSU] Checking Virtual Environment...
if not exist ".venv" (
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [AutoBFSU] uv not found. Falling back to standard Python venv...
        where python >nul 2>nul
        if errorlevel 1 (
            echo.
            echo ==================================================
            echo  [ERROR] Python is not installed or not in PATH!
            echo ==================================================
            echo  Please download and install Python (>=3.11):
            echo  https://www.python.org/downloads/
            echo  *IMPORTANT*: Make sure to check "Add Python to PATH" during installation.
            echo ==================================================
            echo.
            pause
            exit /b 1
        )
        python -m venv .venv
        .venv\Scripts\python.exe -m pip install --upgrade pip
        .venv\Scripts\pip install -e .
    ) else (
        echo [AutoBFSU] uv detected! Initializing virtual environment with uv...
        uv venv
        uv pip install -e .
    )
)

rem Check command line arguments for bypass
if "%~1"=="--window" goto mode1
if "%~1"=="-w" goto mode1
if "%~1"=="--background" goto mode2
if "%~1"=="-b" goto mode2
if "%~1"=="--test" goto mode3
if "%~1"=="-t" goto mode3

echo.
echo ==================================================
echo  AutoBFSU Startup Menu
echo ==================================================
echo  1. Window Mode (Shows console logs, for testing)
echo  2. Background Mode (Runs silently via pythonw) [DEFAULT]
echo  3. UI Test Mode (Triggers a Mock notification)
echo ==================================================
echo.

echo Auto-selecting Background Mode (2) in 3 seconds...
choice /c 123 /t 3 /d 2 /m "Enter choice (1-3):"

if errorlevel 3 goto mode3
if errorlevel 2 goto mode2
if errorlevel 1 goto mode1

:mode1
echo [AutoBFSU] Starting in Window Mode...
.venv\Scripts\python.exe main.py --daemon
pause
exit

:mode2
echo [AutoBFSU] Starting in Background Mode...
start .venv\Scripts\pythonw.exe main.py --daemon
echo [AutoBFSU] Started in background!
echo [AutoBFSU] You can manage it via the blue system tray icon.
timeout /t 2 >nul
exit

:mode3
echo [AutoBFSU] Starting UI Test...
.venv\Scripts\python.exe main.py --test-ui
pause
exit
