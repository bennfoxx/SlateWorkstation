#!/bin/zsh
# Notarizes the Developer ID–signed MSTR-SL8R build so it opens on any Mac without
# Gatekeeper warnings, installs the stapled app, and makes a notarized, stapled DMG to share.
#
# Usage: scripts/notarize_mstr.sh        (run after scripts/install_native_mstr.sh has built the app)
#
# One-time setup (stores your Apple notary credentials in the login keychain):
#   xcrun notarytool store-credentials "MSTR-SL8R-notary" \
#     --apple-id ben.fox202@gmail.com --team-id 43LRM27435
#   (it asks for an app-specific password from account.apple.com > Sign-In and Security)
set -e
setopt pipefail
cd "${0:A:h}/.."
APP="MSTR-SL8R"
PROFILE="${NOTARY_PROFILE:-MSTR-SL8R-notary}"
BUILT="build/xcode-release/Build/Products/Release/$APP.app"
DEST="/Applications/$APP.app"
OUTDIR="build/release"
WORK="build/notarize"

[[ -d "$BUILT" ]] || { echo "No build at $BUILT. Run scripts/install_native_mstr.sh first."; exit 1; }
xcrun notarytool history --keychain-profile "$PROFILE" >/dev/null 2>&1 || {
  echo "No notary credentials saved as \"$PROFILE\". Run the one-time setup at the top of this script."; exit 1; }

# Must be Developer ID + Hardened Runtime + secure timestamp, or Apple rejects it.
codesign --verify --deep --strict "$BUILT"
SIGNATURE=$(codesign -dvv "$BUILT" 2>&1)   # captured first: grep -q on a pipe trips pipefail
[[ "$SIGNATURE" == *"Authority=Developer ID Application"* ]] || {
  echo "$BUILT is not signed with Developer ID Application. Rebuild with scripts/install_native_mstr.sh."
  echo "$SIGNATURE" | grep -E "^Authority=|^TeamIdentifier="; exit 1; }
VERSION=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$BUILT/Contents/Info.plist")

notarize() {   # notarize <file>: submit, wait, and show Apple's log if it isn't accepted
  local file="$1" json="$WORK/$(basename "$1").json"
  echo "Submitting $(basename "$file") to Apple (usually 1-5 minutes)…"
  xcrun notarytool submit "$file" --keychain-profile "$PROFILE" --wait --output-format json > "$json" || true
  local sid=$(plutil -extract id raw -o - "$json" 2>/dev/null || true)
  local result=$(plutil -extract status raw -o - "$json" 2>/dev/null || true)
  echo "  status: ${result:-unknown} (id ${sid:-none})"
  if [[ "$result" != "Accepted" ]]; then
    cat "$json"
    [[ -n "$sid" ]] && xcrun notarytool log "$sid" --keychain-profile "$PROFILE"
    exit 1
  fi
}

rm -rf "$WORK"; mkdir -p "$WORK" "$OUTDIR"

# 1. Notarize the app and staple the ticket to it (lets it open even when the Mac is offline).
ditto -c -k --keepParent "$BUILT" "$WORK/$APP.zip"
notarize "$WORK/$APP.zip"
xcrun stapler staple "$BUILT"
xcrun stapler validate "$BUILT"

# 2. Install the stapled app.
pkill -f "^$DEST/Contents/MacOS/" 2>/dev/null || true
existing_id=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$DEST/Contents/Info.plist" 2>/dev/null || true)
if [[ -d "$DEST" && "$existing_id" == "com.benfoxmedia.mstrsl8r" ]]; then
  mv "$DEST" "/Applications/$APP (Tk Legacy).app"     # never delete the old PyInstaller app
fi
rm -rf "$DEST"
ditto "$BUILT" "$DEST"

# 3. DMG for other Macs: stapled app + Applications shortcut, signed, notarized, stapled.
STAGE="$WORK/dmg"; mkdir -p "$STAGE"
ditto "$BUILT" "$STAGE/$APP.app"
ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/FIRST_LAUNCH.txt" <<'TXT'
1. Drag MSTR-SL8R into Applications and open it.
2. The first time it drives After Effects / Media Encoder, macOS asks to allow it. Click OK.
   (If you clicked Don't Allow: System Settings > Privacy & Security > Automation.)
TXT
cp engine/readme.txt "$STAGE/README.txt" 2>/dev/null || true
DMG="$OUTDIR/${APP}_v$VERSION.dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "$APP $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
codesign --force --sign "Developer ID Application" --timestamp "$DMG"
notarize "$DMG"
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"

# 4. Gatekeeper's verdict, as a Mac that downloaded these would see it.
echo "Gatekeeper:"
spctl -a -vv -t exec "$DEST" 2>&1 | sed 's/^/  /'
spctl -a -vv -t open --context context:primary-signature "$DMG" 2>&1 | sed 's/^/  /'
cp -f "$DMG" "$PWD/"
rm -rf "$WORK"
echo "Done. Installed $DEST; share $PWD/$(basename "$DMG") (also in build/release)"
