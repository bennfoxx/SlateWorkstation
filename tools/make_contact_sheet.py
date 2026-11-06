#!/usr/bin/env python3
"""Repo shortcut for engine/make_contact_sheet.py (the copy the app bundles); same arguments."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
from make_contact_sheet import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
