@echo off
title AutoBFSU Nuitka Standalone Compiler
echo ====================================================
echo      AutoBFSU Nuitka Standalone Builder (Windows)
echo ====================================================
echo.

cd /d "%~dp0"

:: 1. Detect and activate virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\
    echo Please make sure you have created the .venv first!
    pause
    exit /b 1
)

echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 2. Clean previous builds
echo [2/5] Cleaning up old build artifacts...
if exist "dist\main.dist" (
    echo Removing existing 'main.dist' folder to ensure clean packaging...
    rd /s /q "dist\main.dist"
)
if exist "dist\AutoBFSU-windows-x64.zip" (
    del /q "dist\AutoBFSU-windows-x64.zip"
)

:: 3. Double check Nuitka and dependencies
echo [3/5] Checking Nuitka installation...
python -c "import nuitka" >nul 2>&1
if %errorlevel% neq 0 (
    echo Nuitka is not installed. Installing Nuitka via uv...
    uv pip install nuitka
)

:: 4. Run Nuitka standalone compiler
echo [4/5] Running Nuitka Compilation. Please wait...
echo (This may take several minutes as it translates Python to C++ and compiles to native machine code)
echo.

uv run nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --enable-plugin=tk-inter ^
    --include-package-data=customtkinter ^
    --include-data-files=auto_bfsu/auth/des.js=auto_bfsu/auth/des.js ^
    --output-filename=AutoBFSU.exe ^
    --output-dir=dist ^
    --jobs=%NUMBER_OF_PROCESSORS% ^
    --python-flag=no_docstrings ^
    --lto=yes ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=IPython ^
    --nofollow-import-to=tkinter.test ^
    --nofollow-import-to=PIL.ImageQt ^
    --nofollow-import-to=PIL._avif ^
    --nofollow-import-to=PIL._webp ^
    --nofollow-import-to=PIL._imagingcms ^
    --nofollow-import-to=PIL._imagingmath ^
    --noinclude-custom-mode=unittest:error ^
    --noinclude-custom-mode=tkinter.test:error ^
    --noinclude-custom-mode=PIL.ImageQt:error ^
    --noinclude-custom-mode=IPython:error ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Nuitka compilation failed!
    pause
    exit /b %errorlevel%
)

:: 5. Package to ZIP for easy release
echo.
echo [5/5] Packaging distribution into AutoBFSU-windows-x64.zip...
powershell -Command "Compress-Archive -Path dist\main.dist\* -DestinationPath dist\AutoBFSU-windows-x64.zip -Force"

echo.
echo ====================================================
echo   [SUCCESS] AutoBFSU compiled and packaged successfully!
echo.
echo   1. Standalone Folder: dist\main.dist\
echo   2. Ready-to-Release ZIP: dist\AutoBFSU-windows-x64.zip
echo ====================================================
echo.
pause
