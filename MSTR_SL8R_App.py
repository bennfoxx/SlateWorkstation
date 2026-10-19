#!/usr/bin/env python3
"""
MSTR-SL8R  •  Broadcast Slating Workstation
Standalone branded launcher configured for Ben Fox Media palette and styling.
Directly imports the shared Workstation engine so all bugfixes and feature additions
apply to both SuperJoy Slating Workstation and MSTR-SL8R automatically.
"""
import os
import sys
import tkinter as tk

# Ensure the shared workstation module is resolvable
_APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from SuperJoy_Slating_App import SuperJoyWorkstation, set_theme

def main():
    root = tk.Tk()
    set_theme("mstr_sl8r")
    app = SuperJoyWorkstation(root, theme="mstr_sl8r")
    root.mainloop()

if __name__ == "__main__":
    main()
