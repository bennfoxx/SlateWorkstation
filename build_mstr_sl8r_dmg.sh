#!/bin/zsh
# Builds MSTR-SL8R.app (PyInstaller) and wraps it in a DMG.
# Usage: ./build_mstr_sl8r_dmg.sh        (requires: pip3 install pyinstaller)
set -e
cd "${0:A:h}"
VERSION="1.0.0"
APP="MSTR-SL8R"
rm -rf build dist_mstr dist_dmg_mstr

python3 -m PyInstaller --noconfirm --windowed --name "$APP" --distpath dist_mstr \
  --icon assets/MSTR_SL8R.icns --target-architecture arm64 --osx-bundle-identifier com.benfoxmedia.mstrsl8r \
  --add-data "presets:presets" \
  --add-data "sj_Slates From Spreadsheet_Template_006.aep:." \
  --add-data "sj_Slates From Spreadsheet_Template_005.aep:." \
  --add-data "Slates From Spreadsheet_Template_001.xlsx:." \
  --add-data "readme.txt:." \
  MSTR_SL8R_App.py

# Version in Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "dist_mstr/$APP.app/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "dist_mstr/$APP.app/Contents/Info.plist"
codesign --force --deep --sign - "dist_mstr/$APP.app"

# DMG staging: app + Applications shortcut + readme
mkdir dist_dmg_mstr
cp -R "dist_mstr/$APP.app" dist_dmg_mstr/
cat > dist_dmg_mstr/FIRST_LAUNCH.txt <<'TXT'
1. Drag the app into Applications.
2. If macOS says it can't be verified, run this once in Terminal:
   xattr -dr com.apple.quarantine "/Applications/MSTR-SL8R.app"
   (or right-click the app > Open > Open)
3. Allow it to control After Effects when prompted.
TXT
cp readme.txt dist_dmg_mstr/README.txt 2>/dev/null || true
ln -s /Applications dist_dmg_mstr/Applications
hdiutil create -volname "$APP $VERSION" -srcfolder dist_dmg_mstr -ov -format UDZO "MSTR_SL8R_v$VERSION.dmg"
rm -rf dist_dmg_mstr
echo "Built MSTR_SL8R_v$VERSION.dmg"
