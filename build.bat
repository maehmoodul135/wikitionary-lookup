@echo off
REM Builds WiktionaryLookup.exe using PyInstaller.
REM Run this by double-clicking it on Windows, in this same folder as main.py.

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install it from https://www.python.org/ and make sure to check "Add to PATH" during install.
    pause
    exit /b 1
)

if not exist venv (
    echo Creating a virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building WiktionaryLookup.exe ...
pyinstaller --noconsole --onefile --name WiktionaryLookup main.py

echo.
if exist dist\WiktionaryLookup.exe (
    echo Done. Your exe is at: dist\WiktionaryLookup.exe
) else (
    echo Something went wrong -- check the output above for errors.
)
pause
