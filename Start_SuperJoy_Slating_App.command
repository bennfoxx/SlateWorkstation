#!/bin/zsh
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR" || exit 1

for PY_BIN in \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    "$(command -v python3)"; do
    if [[ -n "$PY_BIN" && -x "$PY_BIN" ]] && "$PY_BIN" -c "import tkinter" >/dev/null 2>&1; then
        exec "$PY_BIN" "$SCRIPT_DIR/SuperJoy_Slating_App.py"
    fi
done

echo "Error: No Python 3 installation with Tkinter found."
exit 1
