#!/bin/bash
# Builds CooldownTracker into a macOS app AND packages it into a
# CooldownTracker.dmg you can share/install by dragging into Applications.
# Double-click this file in Finder to run it.
# (If macOS blocks it the first time: right-click -> Open -> Open.)
#
# Requirement: Python 3 must already be installed (python3 --version).
# Get it from python.org, or via Homebrew: brew install python

cd "$(dirname "$0")"

echo "[1/3] Installing required packages..."
python3 -m pip install -r requirements.txt pyinstaller
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Could not find python3/pip3, or the install failed."
    echo "Install Python 3 from python.org first, then run this again."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "[2/3] Building app..."
# NOTE: the installed package is named "PyInstaller" (capital letters).
# Python's "-m" import lookup is case-sensitive, so it must match exactly.
python3 -m PyInstaller --onefile --windowed --name CooldownTracker main.py
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: The build failed. See the message above for details."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "[3/3] Packaging dist/CooldownTracker.dmg ..."
rm -rf dist/dmg_staging
mkdir -p dist/dmg_staging
cp -R dist/CooldownTracker.app dist/dmg_staging/
ln -s /Applications dist/dmg_staging/Applications
rm -f dist/CooldownTracker.dmg
hdiutil create -volname "CooldownTracker" -srcfolder dist/dmg_staging -ov -format UDZO dist/CooldownTracker.dmg
DMG_STATUS=$?
rm -rf dist/dmg_staging
if [ $DMG_STATUS -ne 0 ]; then
    echo ""
    echo "ERROR: dmg packaging failed. dist/CooldownTracker.app was still built"
    echo "successfully, so you can run/share that directly instead."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "========================================="
echo "Done! dist/CooldownTracker.dmg is ready to share."
echo ""
echo "To install: open the dmg, then drag CooldownTracker into the"
echo "Applications shortcut shown inside it."
echo ""
echo "First launch: macOS will likely block it as an unidentified"
echo "developer app. Right-click (or Control-click) the app -> Open ->"
echo "Open, or allow it in System Settings > Privacy & Security."
echo "========================================="
read -n 1 -s -r -p "Press any key to close..."
