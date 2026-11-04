#!/bin/zsh
# Builds the native SwiftUI MSTR-SL8R (Release, signed with team 43LRM27435)
# and installs it to /Applications/MSTR-SL8R.app.
# Usage: ./install_native_mstr.sh            (requires: Xcode, xcodegen, python3 on this Mac)
#        LEGACY_ACTION=keep|trash ./install_native_mstr.sh
#   If the installed MSTR-SL8R.app is the old PyInstaller/Tk build, it is renamed to
#   "MSTR-SL8R (Tk Legacy).app" (default, LEGACY_ACTION=keep) or moved to the Trash.
set -e
cd "${0:A:h}"
APP="MSTR-SL8R"
DEST="/Applications/$APP.app"
OUT="build/xcode-release"

xcodegen generate --quiet
xcodebuild -project SlateWorkstation.xcodeproj -scheme "$APP" -configuration Release \
  -derivedDataPath "$OUT" -allowProvisioningUpdates build | grep -E "error|BUILD" || true
BUILT="$OUT/Build/Products/Release/$APP.app"
[[ -d "$BUILT" ]] || { echo "Build failed: $BUILT missing"; exit 1; }
codesign --verify --deep --strict "$BUILT"

if [[ -d "$DEST" ]]; then
  existing_id=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$DEST/Contents/Info.plist" 2>/dev/null || true)
  if [[ "$existing_id" == "com.benfoxmedia.mstrsl8r" ]]; then
    if [[ "${LEGACY_ACTION:-keep}" == "trash" ]]; then
      pkill -f "^$DEST/Contents/MacOS/" 2>/dev/null || true
      trashed="$HOME/.Trash/$APP (Tk Legacy) $(date +%Y%m%d-%H%M%S).app"
      mv "$DEST" "$trashed"
      echo "Moved legacy Tk app to $trashed"
    else
      mv "$DEST" "/Applications/$APP (Tk Legacy).app"
      echo "Renamed legacy Tk app to /Applications/$APP (Tk Legacy).app"
    fi
  else
    rm -rf "$DEST"   # previous native install
  fi
fi

# Quit only the installed copy (never a build running from Xcode / DerivedData)
pkill -f "^$DEST/Contents/MacOS/" 2>/dev/null || true
ditto "$BUILT" "$DEST"
codesign --verify --deep --strict "$DEST"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST"
echo "Installed $DEST ($(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$DEST/Contents/Info.plist"))"
