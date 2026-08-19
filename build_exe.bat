@echo off
REM Builds CooldownTracker into a single exe file.
REM Put this file in the same folder as main.py and double-click it.
REM Requirement: Python must already be installed on Windows and the
REM "python" command must work (check with "python --version" in cmd).

cd /d "%~dp0"

echo [1/2] Installing required packages...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: Could not find Python or pip.
    echo Please install Python from python.org first, then run this again.
    pause
    exit /b 1
)

echo.
echo [2/2] Building exe...
REM NOTE: the installed package is named "PyInstaller" (capital letters).
REM Windows Python's "-m" import lookup is case-sensitive, so "-m pyinstaller"
REM (lowercase) fails with "No module named pyinstaller" even though the
REM package is installed. Using the correct case fixes it.
python -m PyInstaller --onefile --noconsole --name CooldownTracker main.py
if errorlevel 1 (
    echo.
    echo ERROR: The build failed. See the message above for details.
    pause
    exit /b 1
)

echo.
echo =========================================
echo Done! Run dist\CooldownTracker.exe
echo =========================================
pause
