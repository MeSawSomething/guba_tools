@echo off
REM Builds CooltimeTracker into a single exe file.
REM Put this file in the same folder as main.py and double-click it.
REM Requirement: Python must already be installed on Windows and the
REM "python" command must work (check with "python --version" in cmd).

cd /d "%~dp0"

echo [1/3] Installing required packages...
python -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 (
    echo.
    echo ERROR: Could not find Python or pip.
    echo Please install Python from python.org first, then run this again.
    pause
    exit /b 1
)

echo.
echo [2/3] Checking for a custom icon (.png file in this folder)...
python make_icon.py

echo.
echo [3/3] Building exe...
REM NOTE: the installed package is named "PyInstaller" (capital letters).
REM Windows Python's "-m" import lookup is case-sensitive, so "-m pyinstaller"
REM (lowercase) fails with "No module named pyinstaller" even though the
REM package is installed. Using the correct case fixes it.
set ICON_ARG=
if exist icon.ico set ICON_ARG=--icon icon.ico
python -m PyInstaller --onefile --noconsole --name CooltimeTracker %ICON_ARG% main.py
if errorlevel 1 (
    echo.
    echo ERROR: The build failed. See the message above for details.
    pause
    exit /b 1
)

echo.
echo =========================================
echo Done! Run dist\CooltimeTracker.exe
echo =========================================
pause
