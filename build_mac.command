#!/bin/bash
# Builds CooltimeTracker into a macOS app AND packages it into a
# CooltimeTracker.dmg you can share/install by dragging into Applications.
# Double-click this file in Finder to run it.
# (If macOS blocks it the first time: right-click -> Open -> Open.)
#
# Requirement: Python 3 must already be installed (python3 --version).
# Get it from python.org, or via Homebrew: brew install python

cd "$(dirname "$0")"

echo "[1/4] Installing required packages..."
python3 -m pip install -r requirements.txt pyinstaller pillow
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Could not find python3/pip3, or the install failed."
    echo "Install Python 3 from python.org first, then run this again."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "[2/4] Checking for a custom icon (.png file in this folder)..."
python3 make_icon.py

echo ""
echo "[3/4] Building app..."
# NOTE: the installed package is named "PyInstaller" (capital letters).
# Python's "-m" import lookup is case-sensitive, so it must match exactly.
ICON_ARG=()
if [ -f icon.icns ]; then
    ICON_ARG=(--icon=icon.icns)
fi
python3 -m PyInstaller --onefile --windowed --name CooltimeTracker "${ICON_ARG[@]}" main.py
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: The build failed. See the message above for details."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "[4/4] Packaging dist/CooltimeTracker.dmg ..."
rm -rf dist/dmg_staging
mkdir -p dist/dmg_staging
cp -R dist/CooltimeTracker.app dist/dmg_staging/
ln -s /Applications dist/dmg_staging/Applications
rm -f dist/CooltimeTracker.dmg
hdiutil create -volname "CooltimeTracker" -srcfolder dist/dmg_staging -ov -format UDZO dist/CooltimeTracker.dmg
DMG_STATUS=$?
rm -rf dist/dmg_staging
if [ $DMG_STATUS -ne 0 ]; then
    echo ""
    echo "ERROR: dmg packaging failed. dist/CooltimeTracker.app was still built"
    echo "successfully, so you can run/share that directly instead."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo ""
echo "========================================="
echo "Done! dist/CooltimeTracker.dmg is ready to share."
echo ""
echo "To install: open the dmg, then drag CooltimeTracker into the"
echo "Applications shortcut shown inside it."
echo ""
echo "First launch: macOS will likely block it as an unidentified"
echo "developer app. Right-click (or Control-click) the app -> Open ->"
echo "Open, or allow it in System Settings > Privacy & Security."
echo "========================================="
read -n 1 -s -r -p "Press any key to close..."
