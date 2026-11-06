#!/bin/zsh
# Xcode build phase for MSTR-SL8R Ingest: copies vendor/ffmpeg (from scripts/build_ffmpeg.sh)
# into Contents/Helpers and signs it with Hardened Runtime. If it hasn't been built, the app
# still builds and the engine falls back to a system ffmpeg (Homebrew) for development.
set -e
cd "$SRCROOT"
SRC="vendor/ffmpeg"
DST="$TARGET_BUILD_DIR/$CONTENTS_FOLDER_PATH/Helpers"
if [[ ! -x "$SRC/bin/ffmpeg" || ! -x "$SRC/bin/ffprobe" ]]; then
  echo "warning: vendor/ffmpeg not built (scripts/build_ffmpeg.sh); the app will use a system ffmpeg if one is installed"
  exit 0
fi
mkdir -p "$DST"
cp "$SRC/bin/ffmpeg" "$SRC/bin/ffprobe" "$DST/"
mkdir -p "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/ffmpeg-license"
cp "$SRC/LICENSE.txt" "$SRC/SOURCE" "$SRC/BUILDCONF" "$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/ffmpeg-license/" 2>/dev/null || true
IDENTITY="${EXPANDED_CODE_SIGN_IDENTITY:--}"
TIMESTAMP="--timestamp"; [[ "$IDENTITY" == "-" ]] && TIMESTAMP="--timestamp=none"
for f in "$DST/ffmpeg" "$DST/ffprobe"; do
  codesign --force --options runtime "$TIMESTAMP" --sign "$IDENTITY" "$f"
done
echo "Embedded $(cat "$SRC/VERSION" 2>/dev/null) into $DST"
