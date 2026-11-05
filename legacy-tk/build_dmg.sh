#!/bin/zsh
# Builds SuperJoy Slating Workstation.app (PyInstaller) and wraps it in a DMG.
# Usage: legacy-tk/build_dmg.sh        (requires: pip3 install pyinstaller)
set -e
cd "${0:A:h}/.."
VERSION="1.0.0"
APP="SuperJoy Slating Workstation"
rm -rf build legacy-tk/dist dist_dmg

python3 -m PyInstaller --noconfirm --windowed --name "$APP" --distpath legacy-tk/dist \
  --icon assets/SJ.icns --target-architecture arm64 --osx-bundle-identifier com.superjoy.slatingworkstation \
  --add-data "engine/presets:presets" \
  --add-data "engine/sj_Slates From Spreadsheet_Template_006.aep:." \
  --add-data "engine/sj_Slates From Spreadsheet_Template_005.aep:." \
  --add-data "engine/Slates From Spreadsheet_Template_001.xlsx:." \
  --add-data "engine/readme.txt:." \
  engine/SuperJoy_Slating_App.py

# Version in Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "legacy-tk/dist/$APP.app/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "legacy-tk/dist/$APP.app/Contents/Info.plist"
codesign --force --deep --sign - "legacy-tk/dist/$APP.app"

# DMG staging: app + Applications shortcut + readme
mkdir dist_dmg
cp -R "legacy-tk/dist/$APP.app" dist_dmg/
cat > dist_dmg/FIRST_LAUNCH.txt <<'TXT'
1. Drag the app into Applications.
2. If macOS says it can't be verified, run this once in Terminal:
   xattr -dr com.apple.quarantine "/Applications/SuperJoy Slating Workstation.app"
   (or right-click the app > Open > Open)
3. Allow it to control After Effects when prompted.
TXT
cp engine/readme.txt dist_dmg/README.txt 2>/dev/null || true
ln -s /Applications dist_dmg/Applications
hdiutil create -volname "$APP $VERSION" -srcfolder dist_dmg -ov -format UDZO "legacy-tk/SuperJoy_Slating_Workstation_v$VERSION.dmg"
rm -rf dist_dmg
echo "Built SuperJoy_Slating_Workstation_v$VERSION.dmg"
