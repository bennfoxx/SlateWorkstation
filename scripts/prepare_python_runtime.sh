#!/bin/zsh
# Stages a trimmed, relocatable CPython (python-build-standalone, via uv) in vendor/python
# for embedding in the native app. Idempotent: does nothing if vendor/python matches.
# Usage: scripts/prepare_python_runtime.sh            (requires: uv)
set -e
cd "${0:A:h}/.."
PY_VERSION="${PY_VERSION:-3.12}"
DEST="vendor/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

command -v uv >/dev/null || { echo "error: uv not found (brew install uv)"; exit 1; }
uv python install --quiet "$PY_VERSION" >/dev/null
SRC_BIN=$(uv python find --managed-python "$PY_VERSION")
SRC=$(cd "$(dirname "$SRC_BIN")/.." && pwd -P)
STAMP="$SRC $(stat -f %m "$SRC/bin") $(md5 -q "${0:A}")"
if [[ -f "$DEST/.source" && "$(cat "$DEST/.source")" == "$STAMP" ]]; then
  echo "vendor/python up to date ($SRC)"; exit 0
fi

echo "Staging trimmed Python from $SRC"
rm -rf "$DEST"; mkdir -p "$DEST/bin"
PYVER=$(basename "$SRC"/lib/python3.*)
# The interpreter is statically linked (no libpython/Tcl dylibs needed).
cp "$SRC/bin/$PYVER" "$DEST/bin/$PYVER"
strip -x "$DEST/bin/$PYVER"   # local symbols only; re-signed when embedded
ln -s "$PYVER" "$DEST/bin/python3"
# Pure-Python stdlib minus what the engine never uses in a headless worker.
rsync -a --delete \
  --exclude 'site-packages/' --exclude 'idlelib/' --exclude 'tkinter/' --exclude 'turtledemo/' \
  --exclude 'turtle.py' --exclude 'ensurepip/' --exclude 'lib2to3/' --exclude 'pydoc_data/' \
  --exclude 'config-*/' --exclude 'test/' --exclude 'tests/' --exclude 'venv/' \
  --exclude 'lib-dynload/_tkinter.*' --exclude '__phello__/' --exclude '__pycache__/' \
  "$SRC/lib/$PYVER/" "$DEST/lib/$PYVER/"
mkdir -p "$DEST/lib/$PYVER/site-packages"
cp "$SRC/BUILD"* "$DEST/" 2>/dev/null || true
# Precompile only the stdlib modules the worker actually imports (the signed bundle is
# read-only at run time). Running the worker without -B writes exactly those .pyc files.
"$DEST/bin/python3" -I engine/slate_worker.py info >/dev/null
"$DEST/bin/python3" -I engine/slate_worker.py parse --file "engine/Slates From Spreadsheet_Template_001.xlsx" >/dev/null
"$DEST/bin/python3" -I -c "import email.utils, http.client, urllib.request, plistlib, uuid, hashlib" >/dev/null 2>&1 || true
rm -rf engine/__pycache__
echo "$STAMP" > "$DEST/.source"
du -sh "$DEST"
