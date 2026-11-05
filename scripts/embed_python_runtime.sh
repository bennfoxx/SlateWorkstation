#!/bin/zsh
# Xcode "Embed Python Runtime" build phase: copies vendor/python into
# Contents/Resources/python and signs its Mach-O files (Hardened Runtime) with the
# target's identity, before Xcode signs the app itself.
set -e
cd "$SRCROOT"
scripts/prepare_python_runtime.sh
DST="$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/python"
rm -rf "$DST"
ditto "vendor/python" "$DST"
rm -f "$DST/.source"

IDENTITY="${EXPANDED_CODE_SIGN_IDENTITY:--}"
# Developer ID / notarization needs a secure timestamp on every nested binary; ad-hoc can't have one.
TIMESTAMP="--timestamp"; [[ "$IDENTITY" == "-" ]] && TIMESTAMP="--timestamp=none"
find "$DST" -type f \( -perm -u+x -o -name '*.so' -o -name '*.dylib' \) | while read -r f; do
  if file -b "$f" | grep -q 'Mach-O'; then
    codesign --force --options runtime "$TIMESTAMP" --sign "$IDENTITY" "$f"
  fi
done
echo "Embedded Python: $(du -sh "$DST" | cut -f1) at $DST"
