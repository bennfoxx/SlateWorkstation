import os
import re
import csv
import sys
import glob
import json
import math
import time
import wave
import ctypes
import struct
import threading
import subprocess
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Color Palette (Inspired directly by the SuperJoy Broadcast Slate)
# ---------------------------------------------------------------------------
BG_DARK = "#222538"         # Deep navy-slate background from the slate
BG_CARD = "#2A2E44"         # Elevated card surface
BG_DARKER = "#181B29"       # Recessed input / well surface
BORDER_SUBTLE = "#383D59"   # Soft card & input border
ACCENT_RED = "#E8453C"      # Signature SuperJoy coral-red
ACCENT_RED_HOVER = "#F45B52"
ACCENT_YELLOW = "#F3E052"   # Signature SuperJoy ID/7 countdown yellow
TEXT_LIGHT = "#FFFFFF"
TEXT_MUTED = "#9BA3C2"
BG_GREEN = "#2E9E44"
BG_GREEN_HOVER = "#37B24D"
BG_BLUE = "#3B6EA8"
BG_GREY = "#383E56"
BG_GREY_HOVER = "#454C68"
BG_DISABLED = "#4A4F66"

# Preferred UI font (matches the slate). Falls back cleanly if TT Fors isn't installed.
FONT = "Helvetica"
FONT_CANDIDATES = (
    "TT Fors",
    "TT Fors Trial",
    "TT Fors Variable",
    "TT Fors Medium",
    "Avenir Next",
    "Helvetica Neue",
    "Helvetica",
)


def pick_font_family():
    available = {f.lower(): f for f in tkfont.families()}
    for name in FONT_CANDIDATES:
        if name.lower() in available:
            return available[name.lower()]
    return "Helvetica"


# Explicit bundle ID / app discovery so osascript never fails with (-1728) or hangs choosing between AE versions.
# Note: Adobe After Effects 2024/2025/2026+ uses CFBundleIdentifier "com.adobe.AfterEffects.application".
AE_BUNDLE_ID = os.environ.get("SUPERJOY_AE_BUNDLE_ID", "com.adobe.AfterEffects.application")
VALID_EXTS = (".mov", ".mp4", ".mxf")
SLATE_ASSET_EXTS = (".mov", ".mp4", ".mxf", ".png", ".tif", ".tiff", ".psd", ".jpg", ".jpeg")
UNSLATE_SECONDS = 7.0  # 5s slate + 2s black


def resolve_ae_applescript_target():
    """Return an AppleScript application target clause (e.g. 'application id \"com.adobe.AfterEffects.application\"'
    or 'application \"/Applications/Adobe After Effects 2026/Adobe After Effects 2026.app\"') that is guaranteed
    to resolve on this Mac."""
    env_id = os.environ.get("SUPERJOY_AE_BUNDLE_ID", "").strip()
    if env_id:
        if env_id.endswith(".app") and os.path.exists(env_id):
            return f'application "{env_id}"'
        return f'application id "{env_id}"'

    # Prefer the newest installed Adobe After Effects .app bundle on disk so multiple installed versions
    # (e.g. AE 2025 + AE 2026) never conflict.
    app_candidates = sorted(
        glob.glob("/Applications/Adobe After Effects */Adobe After Effects *.app"),
        reverse=True,
    )
    for app_path in app_candidates:
        if "Render Engine" not in app_path and os.path.isdir(app_path):
            return f'application "{app_path}"'

    return f'application id "{AE_BUNDLE_ID}"'


# Studio standard: 23.976 fps (exactly 24000/1001), 1080p base.
DEFAULT_FPS_LABEL = "23.976"
FPS_PRESETS = {
    "23.976": 24000 / 1001.0,
    "24": 24.0,
    "25": 25.0,
    "29.97": 30000 / 1001.0,
    "30": 30.0,
    "50": 50.0,
    "59.94": 60000 / 1001.0,
    "60": 60.0,
}
DEFAULT_ASPECT = "16x9"
ASPECT_KEYS = ("16x9", "1x1", "4x5", "9x16")
ASPECT_RESOLUTIONS = {
    "16x9": (1920, 1080),
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
}
STANDARD_TRTS = ("60", "30", "15", "06")


def format_resolution_label(aspect_key):
    """Return a human-readable resolution string such as '16x9 (1920×1080)'."""
    key = aspect_key if aspect_key in ASPECT_RESOLUTIONS else DEFAULT_ASPECT
    w, h = ASPECT_RESOLUTIONS[key]
    return f"{key} ({w}×{h})"


def detect_aspect_from_text(text):
    """Detect an explicit aspect token ('16x9', '1x1', '4x5', '9x16') or pixel dimensions in a filename/title."""
    if not text:
        return None
    m = re.search(
        r"(?<![0-9])(16\s*[x_:\-]\s*9|1\s*[x_:\-]\s*1|4\s*[x_:\-]\s*5|9\s*[x_:\-]\s*16)(?![0-9])",
        text,
        re.IGNORECASE,
    )
    if m:
        parts = re.split(r"[x_:\-\s]+", m.group(1).lower())
        candidate = f"{parts[0]}x{parts[1]}"
        if candidate in ASPECT_RESOLUTIONS:
            return candidate
    dim_map = {
        "1920x1080": "16x9",
        "3840x2160": "16x9",
        "1080x1080": "1x1",
        "1280x1280": "1x1",
        "1080x1350": "4x5",
        "1280x1600": "4x5",
        "1080x1920": "9x16",
        "2160x3840": "9x16",
    }
    for dim_tok, asp in dim_map.items():
        if dim_tok in text.lower():
            return asp
    return None


def today_yyyy_mm_dd():
    """Return the current date formatted as YYYY_MM_DD."""
    return datetime.now().strftime("%Y_%m_%d")


# Default After Effects Slate Template (.aep) bundled in the workstation folder
DEFAULT_TEMPLATE_AEP = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "sj_Slates From Spreadsheet_Template_005.aep",
)


def sanitize_single_line(value):
    """Collapse any embedded newlines/tabs into single spaces so slate text fields never force line breaks."""
    if value is None:
        return ""
    return re.sub(r"[\r\n\t]+", " ", str(value)).strip()


def sanitize_filename_token(value):
    """Format a metadata string into a filesystem-safe broadcast filename token with underscores."""
    if not value:
        return ""
    cleaned = sanitize_single_line(value)
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", cleaned)
    cleaned = re.sub(r"\s*_\s*|\s+", "_", cleaned).strip("_.")
    return cleaned


def build_canonical_delivery_stem(data, target_aspect=None, include_aspect=False, suffix="Slated"):
    """Construct an accurate broadcast delivery filename stem from normalized slate metadata
    (Ad-ID + underscored Title + optional aspect token + suffix) so outputs have guaranteed accurate filenames."""
    ad_id = sanitize_filename_token(data.get("id") or data.get("ad-id") or "SPOT")
    title = sanitize_filename_token(data.get("title") or data.get("name") or "")
    # Avoid duplicating Ad-ID if the title already begins with the Ad-ID
    if title and title.lower().startswith(ad_id.lower()):
        stem = title
    elif title:
        stem = f"{ad_id}_{title}"
    else:
        stem = ad_id

    if include_aspect and target_aspect and target_aspect.lower() not in stem.lower():
        stem = f"{stem}_{target_aspect}"

    if suffix:
        stem = f"{stem}_{suffix}"
    return stem


def normalize_slate_row(raw_row):
    """Normalize a dictionary from a CSV/TSV/manual batch row so all template column aliases
    (e.g. 'Ad-ID', 'NFA', 'WORKSPACE_ARTIST', 'Day', 'COMP') map to canonical slate keys."""
    cleaned = {}
    for k, v in (raw_row or {}).items():
        if k is None:
            continue
        norm_k = re.sub(r"^[\^#]+", "", str(k).strip()).lower()
        cleaned[norm_k] = sanitize_single_line(v)

    def pick(*keys, default=""):
        for k in keys:
            val = cleaned.get(k, "")
            if val and val != "_":
                return val
        return default

    ad_id = pick("id", "ad-id", "ad_id", "adid", "spot_id", "isci")
    title = pick("title", "spot_title", "spot", "name")
    client = pick("client", "brand", "advertiser")
    agency = pick("agency", "the martin agency")
    nfa = pick("nfa")
    trt = pick("trt", "duration", "length", "time")
    date_val = pick("date", "day", "air_date", "ship_date")
    workspace = pick("workspace", "workspace_artist", "artist", "editor")
    audio = pick("audio", "mix", "sound", default="STEREO")
    copyright_val = pick("copyright", "legal")
    flame = pick("flame", "flame_logo", default="n")
    raw_aspect = pick("aspect", "comp", "resolution", "format", "ratio")
    aspect = raw_aspect if raw_aspect in ASPECT_RESOLUTIONS else detect_aspect_from_text(raw_aspect)

    result = dict(cleaned)
    result.update(
        {
            "id": ad_id,
            "ad-id": ad_id,
            "title": title,
            "name": title,
            "client": client,
            "agency": agency,
            "nfa": nfa,
            "trt": trt,
            "duration": trt,
            "date": date_val,
            "day": date_val,
            "workspace": workspace,
            "workspace_artist": workspace,
            "audio": audio,
            "copyright": copyright_val,
            "flame": flame,
        }
    )
    if aspect:
        result["aspect"] = aspect
        result["resolution"] = format_resolution_label(aspect)
    return result


def parse_metadata_file(path):
    """Parse a CSV, TSV, or TXT metadata file using csv.reader (handling UTF-8 BOM, quoted commas,
    and skipping blank or placeholder '_' rows)."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        raw_lines = [line for line in f if line.strip()]
    if not raw_lines:
        return []
    delimiter = "\t" if "\t" in raw_lines[0] else ","
    reader = list(csv.reader(raw_lines, delimiter=delimiter))
    if len(reader) < 2:
        return []
    headers = [h.strip().lower() for h in reader[0]]
    rows = []
    for row in reader[1:]:
        if not row or all(not c.strip() or c.strip() == "_" for c in row):
            continue
        raw_dict = {headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers)) if headers[i]}
        norm = normalize_slate_row(raw_dict)
        if norm.get("id") or norm.get("title"):
            rows.append(norm)
    return rows


def parse_video_filename(filename):
    """Extract (ad_id, title_with_underscores, trt) from a master video filename.

    Rules:
    - Ad-ID is the leading series of letters and numbers up front.
    - Title is the remainder of the filename stem after the Ad-ID, with spaces replaced by '_'.
    - TRT is detected from the title (standard broadcast times: 60, 30, 15, 06), formatted as ':15', etc.
    """
    stem = os.path.splitext(os.path.basename(filename))[0].strip()
    # Strip leading/trailing whitespace and split off the leading alphanumeric Ad-ID
    m = re.match(r"^([A-Za-z0-9]+)(?:[\s_\-]+(.*))?$", stem)
    if m:
        ad_id = m.group(1)
        raw_title = (m.group(2) or "").strip()
    else:
        ad_id = stem
        raw_title = stem

    # Replace spaces with underscores (collapse any space runs around underscores cleanly)
    if raw_title:
        title = re.sub(r"\s*_\s*|\s+", "_", raw_title).strip("_")
    else:
        title = re.sub(r"\s*_\s*|\s+", "_", stem).strip("_")

    # Search for standard broadcast TRT tokens (60, 30, 15, 06) in the title.
    # Scan from the end of the title backward so trailing tokens (e.g. '..._16x9_15') win.
    # Ignore tokens immediately adjacent to 'x' (aspect ratios like 16x9).
    trt = ""
    trt_matches = list(
        re.finditer(r"(?<![A-Za-z0-9xX]):?(60|30|15|06|0?6)(?:s|sec)?(?![A-Za-z0-9xX])", title, re.IGNORECASE)
    )
    for match in reversed(trt_matches):
        token = match.group(1)
        if token == "6":
            token = "06"
        if token in STANDARD_TRTS:
            trt = f":{token}"
            break

    return ad_id, title, trt



# ---------------------------------------------------------------------------
# macOS Tk 8.6.12 Tap-to-Click & Pointer State Fix
# ---------------------------------------------------------------------------
def _init_tk_c_bridge():
    """Bind to libtk8.6 C symbols used for button state checks and capture cleanup."""
    if sys.platform != "darwin":
        return None
    try:
        lib = ctypes.CDLL(None)
        lib.TkpSetCapture.argtypes = [ctypes.c_void_p]
        lib.TkMacOSXButtonKeyState.argtypes = []
        lib.TkMacOSXButtonKeyState.restype = ctypes.c_uint32
        lib.TkGenerateButtonEvent.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_ulong, ctypes.c_uint]
        lib.TkGenerateButtonEvent.restype = ctypes.c_int
        lib.TkMacOSXDrawable.argtypes = [ctypes.c_ulong]
        lib.TkMacOSXDrawable.restype = ctypes.c_void_p
        return lib
    except Exception:
        return None


_TK_LIB = None
_OBJC_PATCHED = False


def patch_macos_tk_tap_bug(root=None):
    """Fix the macOS Sonoma/Sequoia/Tahoe + Tk 8.6.12 bug in -[TKApplication tkProcessMouseEvent:]:
    When AppKit fires NSEventTypeMouseEntered (type 8) for any tracking area inside the window,
    Tk 8.6.12 calls [TKWindow setMouseInResizeArea:YES]. While mouseInResizeArea is YES,
    tkProcessMouseEvent: (at offset 0xc3a9c) drops 100% of NSEventTypeLeftMouseDown (type 1)
    events and only responds to NSEventTypeLeftMouseDragged (type 6, a deep press/drag).
    Replacing -[TKWindow mouseInResizeArea] with -[TKContentView wantsDefaultClipping] (return 0)
    and -[TKWindow setMouseInResizeArea:] with -[TKContentView keyDown:] (no-op) ensures every
    light trackpad tap (LeftMouseDown + LeftMouseUp) registers immediately."""
    global _TK_LIB, _OBJC_PATCHED
    if sys.platform != "darwin":
        return
    if _TK_LIB is None:
        _TK_LIB = _init_tk_c_bridge()
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.class_getInstanceMethod.restype = ctypes.c_void_p
        objc.method_getImplementation.argtypes = [ctypes.c_void_p]
        objc.method_getImplementation.restype = ctypes.c_void_p
        objc.method_setImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.method_setImplementation.restype = ctypes.c_void_p

        if not _OBJC_PATCHED:
            tk_win_cls = objc.objc_getClass(b"TKWindow")
            tk_view_cls = objc.objc_getClass(b"TKContentView")
            if tk_win_cls and tk_view_cls:
                imp_ret_zero = objc.method_getImplementation(
                    objc.class_getInstanceMethod(tk_view_cls, objc.sel_registerName(b"wantsDefaultClipping"))
                )
                imp_noop = objc.method_getImplementation(
                    objc.class_getInstanceMethod(tk_view_cls, objc.sel_registerName(b"keyDown:"))
                )
                m_get = objc.class_getInstanceMethod(tk_win_cls, objc.sel_registerName(b"mouseInResizeArea"))
                m_set = objc.class_getInstanceMethod(tk_win_cls, objc.sel_registerName(b"setMouseInResizeArea:"))
                if m_get and imp_ret_zero:
                    objc.method_setImplementation(m_get, imp_ret_zero)
                if m_set and imp_noop:
                    objc.method_setImplementation(m_set, imp_noop)
                _OBJC_PATCHED = True

        # Ensure NSApp is active in front so tkProcessMouseEvent: (0xc3a5c) never ignores the first tap
        ns_app_cls = objc.objc_getClass(b"NSApplication")
        if ns_app_cls:
            msg_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_bool = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(("objc_msgSend", objc))
            ns_app = msg_ptr(ns_app_cls, objc.sel_registerName(b"sharedApplication"))
            if ns_app:
                msg_bool(ns_app, objc.sel_registerName(b"activateIgnoringOtherApps:"), True)
    except Exception:
        pass


def is_mouse_button_down():
    """Return True if any hardware mouse/trackpad button is currently pressed."""
    global _TK_LIB
    if _TK_LIB is None:
        _TK_LIB = _init_tk_c_bridge()
    try:
        if _TK_LIB is not None:
            return (_TK_LIB.TkMacOSXButtonKeyState() & 0x1F00) != 0
    except Exception:
        pass
    return False


def run_after_mouse_up(root, callback, _attempt=0):
    """Wait until the user's tap/click release (LeftMouseUp) has been processed by Cocoa & Tk
    before opening a native modal dialog (NSOpenPanel / NSAlert), preventing validPresses/buttonWinPtr
    from getting stuck."""
    if root is None:
        callback()
        return
    if is_mouse_button_down() and _attempt < 40:
        root.after(15, lambda: run_after_mouse_up(root, callback, _attempt + 1))
    else:
        root.after(15, callback)


def reset_tk_mouse_state(root):
    """Clear any stuck capture or grab state after a native modal dialog closes."""
    global _TK_LIB
    if root is None:
        return
    if _TK_LIB is None:
        _TK_LIB = _init_tk_c_bridge()
    try:
        if _TK_LIB is not None:
            _TK_LIB.TkpSetCapture(None)
            _TK_LIB.TkGenerateButtonEvent(
                int(root.winfo_pointerx()), int(root.winfo_pointery()), root.winfo_id(), 0
            )
        cur_grab = root.grab_current()
        if cur_grab is not None:
            cur_grab.grab_release()
    except Exception:
        pass


def wake_macos_window(root):
    """Ensure the macOS window is active, focused, and has TKWindow tap bug patched."""
    try:
        patch_macos_tk_tap_bug(root)
        root.lift()
        root.focus_force()
        reset_tk_mouse_state(root)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Domain Helpers
# ---------------------------------------------------------------------------
def find_templates(path):
    """Resolve an After Effects .aep slate template file (e.g. 'sj_Slates From Spreadsheet_Template_005.aep')
    or a folder containing .aep / .psd templates into an aspect map ('16x9','1x1','4x5','9x16')."""
    found = {}
    if not path:
        return found
    path = os.path.expanduser(path.strip())

    # 1. Direct .aep template file (contains 16x9, 1x1, 4x5, 9x16 comps in __templates)
    if os.path.isfile(path) and path.lower().endswith(".aep"):
        for k in ASPECT_RESOLUTIONS:
            found[k] = path
        found["_aep"] = path
        return found

    if not os.path.isdir(path):
        return found

    # 2. Folder containing an .aep template file
    aep_files = [
        os.path.join(path, f)
        for f in sorted(os.listdir(path))
        if f.lower().endswith(".aep") and not f.startswith(".") and "master_slates" not in f.lower()
    ]
    if aep_files:
        aep_path = aep_files[0]
        for k in ASPECT_RESOLUTIONS:
            found[k] = aep_path
        found["_aep"] = aep_path
        return found

    # 3. Legacy fallback: folder containing per-aspect .psd templates
    pat = re.compile(r"(?<![0-9])(16|1|4|9)\s*[x_:\-]\s*(9|1|5|16)(?![0-9])", re.IGNORECASE)
    for f in sorted(os.listdir(path)):
        if not f.lower().endswith(".psd") or f.startswith("."):
            continue
        m = pat.search(f)
        if m:
            key = f"{m.group(1)}x{m.group(2)}"
            if key in ASPECT_RESOLUTIONS:
                found.setdefault(key, os.path.join(path, f))
    return found



def parse_fps(text):
    """Return fps float from a preset label or custom numeric entry; None if invalid."""
    text = text.strip()
    if text in FPS_PRESETS:
        return FPS_PRESETS[text]
    try:
        v = float(text)
    except ValueError:
        return None
    return v if 1.0 <= v <= 120.0 else None


def ad_id_matches(ad_id, filename):
    """Strict word-boundary match: 'XQ12' must not match 'XQ1234_Master.mov'.
    Underscores count as separators (unlike regex \\b), so 'XQ12_Master' matches."""
    if not ad_id:
        return False
    pattern = r"(?<![A-Za-z0-9])" + re.escape(ad_id) + r"(?![A-Za-z0-9])"
    return re.search(pattern, filename, re.IGNORECASE) is not None


def create_beep_wav(path, fps=10.0, freq=1000.0, rate=48000, amp=0.5):
    """Write a 1-frame, 1kHz mono 16-bit sine WAV."""
    n = max(1, int(round(rate / fps)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(n)
        )
        w.writeframes(frames)


# ---------------------------------------------------------------------------
# Smooth Custom Canvas UI Components (In-Place Item Updates, Instant Single-Tap)
# ---------------------------------------------------------------------------
def round_rect_coords(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    return cv.create_polygon(round_rect_coords(x1, y1, x2, y2, r), smooth=True, **kw)


class RoundedCard(tk.Canvas):
    """Smooth rounded container card with subtle 1px border (updates coords in place)."""
    def __init__(self, parent, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=16):
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_DARK
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, takefocus=0)
        self._bg_fill = bg_fill
        self._border_color = border_color
        self._radius = radius
        self._pad = pad
        self._border_id = round_rect(self, 0, 0, 10, 10, radius, fill=border_color, outline=border_color)
        self._fill_id = round_rect(self, 1, 1, 9, 9, max(0, radius - 1), fill=bg_fill, outline=bg_fill)
        self.body = tk.Frame(self, bg=bg_fill, bd=0, highlightthickness=0)
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, _e=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.coords(self._border_id, *round_rect_coords(0, 0, w, h, self._radius))
        self.coords(self._fill_id, *round_rect_coords(1, 1, w - 1, h - 1, max(0, self._radius - 1)))


class RoundedButton(tk.Canvas):
    """Instant single-tap rounded button for macOS Tk 8.6.12.
    - Fires immediately on <ButtonPress-1> (single light tap) anywhere in the button bounds.
    - Updates colors/coords in place without ever deleting canvas items."""

    def __init__(self, parent, text="", command=None, color=ACCENT_RED, font_spec=None,
                 padx=20, pady=9, radius=12):
        self._font = tkfont.Font(font=font_spec or (FONT, 13, "bold"))
        self._text = text
        self._cmd = command
        self._color = color
        self._radius = radius
        self._padx = padx
        self._pady = pady
        self._state = "normal"
        self._hover = False
        self._down = False
        self._last_fire = 0.0

        w = self._font.measure(text) + 2 * padx
        h = self._font.metrics("linespace") + 2 * pady
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_DARK
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=w, height=h, takefocus=0)
        self._size = (w, h)
        self._shape = round_rect(self, 1, 1, w - 1, h - 1, radius, fill=color, outline=color)
        self._label = self.create_text(w / 2, h / 2, text=text, font=self._font, fill=TEXT_LIGHT)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<Double-Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._recolor()

    def _on_enter(self, _e=None):
        self._hover = True
        self._recolor()

    def _on_leave(self, _e=None):
        self._hover = False
        self._down = False
        self._recolor()

    def _on_press(self, _e=None):
        if self._state == "disabled":
            return "break"
        self._down = True
        self._recolor()
        self._try_fire()
        return "break"

    def _on_release(self, e=None):
        was_down = self._down
        self._down = False
        self._recolor()
        if self._state == "disabled":
            return "break"
        if e is not None and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self._try_fire()
        elif was_down:
            self._try_fire()
        return "break"

    def _try_fire(self):
        now = time.monotonic()
        if now - self._last_fire < 0.16:
            return
        self._last_fire = now
        self.after(110, self._clear_down)
        if self._cmd:
            self.after_idle(self._cmd)

    def invoke(self):
        if self._state != "disabled" and self._cmd:
            return self._cmd()

    def _clear_down(self):
        if self._down:
            self._down = False
            self._recolor()

    def _recolor(self):
        if self._state == "disabled":
            fill, fg = BG_DISABLED, "#C5C9DC"
        elif self._down:
            fill, fg = BG_DARKER, TEXT_LIGHT
        elif self._hover:
            fill, fg = self._lighten(self._color), TEXT_LIGHT
        else:
            fill, fg = self._color, TEXT_LIGHT
        self.itemconfigure(self._shape, fill=fill, outline=fill)
        self.itemconfigure(self._label, fill=fg, text=self._text)

    def _resize(self):
        w = self._font.measure(self._text) + 2 * self._padx
        h = self._font.metrics("linespace") + 2 * self._pady
        if (w, h) != self._size:
            self._size = (w, h)
            super().configure(width=w, height=h)
            self.coords(self._shape, *round_rect_coords(1, 1, w - 1, h - 1, self._radius))
            self.coords(self._label, w / 2, h / 2)

    @staticmethod
    def _lighten(hexc):
        c = [min(255, int(hexc[i:i + 2], 16) + 24) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(c)

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self._text = kw.pop("text")
        if "state" in kw:
            self._state = kw.pop("state")
        if "command" in kw:
            self._cmd = kw.pop("command")
        kw.pop("bg", None)
        kw.pop("fg", None)
        if kw:
            super().configure(cnf, **kw)
        self._resize()
        self._recolor()

    config = configure

    def cget(self, key):
        if key == "state":
            return self._state
        if key == "text":
            return self._text
        return super().cget(key)

    __getitem__ = cget


class RoundedEntry(tk.Canvas):
    """Smooth rounded text input field. Single-tapping anywhere inside the rounded box
    or text area immediately focuses the Entry widget."""

    def __init__(self, parent, textvariable, width=20, radius=10):
        f = tkfont.Font(font=(FONT, 13))
        self._radius = radius
        self._focus = False
        req_w = max(72, width * f.measure("0") + 24)
        req_h = f.metrics("linespace") + 14
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=req_w, height=req_h, takefocus=0)

        self._border_id = round_rect(self, 1, 1, req_w - 1, req_h - 1, radius, fill=BORDER_SUBTLE, outline=BORDER_SUBTLE)
        self._fill_id = round_rect(self, 2, 2, req_w - 2, req_h - 2, max(0, radius - 1), fill=BG_DARKER, outline=BG_DARKER)

        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            width=max(2, int(width * 0.7)),
            bg=BG_DARKER,
            fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT,
            selectbackground=ACCENT_RED,
            selectforeground=TEXT_LIGHT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=f,
        )
        self.entry.place(x=12, rely=0.5, anchor="w", relwidth=1.0, width=-24)

        self.bind("<Configure>", self._on_configure)
        self.bind("<ButtonPress-1>", self._focus_entry)
        self.entry.bind("<ButtonPress-1>", self._on_entry_tap, add="+")
        self.entry.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.entry.bind("<FocusOut>", lambda _e: self._set_focus(False))

    def _on_entry_tap(self, _e=None):
        self.entry.focus_force()

    def _focus_entry(self, _e=None):
        self.entry.focus_force()
        self.entry.icursor("end")
        return "break"

    def _set_focus(self, focused):
        self._focus = focused
        col = ACCENT_RED if focused else BORDER_SUBTLE
        self.itemconfigure(self._border_id, fill=col, outline=col)

    def _on_configure(self, _e=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        col = ACCENT_RED if self._focus else BORDER_SUBTLE
        self.coords(self._border_id, *round_rect_coords(1, 1, w - 1, h - 1, self._radius))
        self.coords(self._fill_id, *round_rect_coords(2, 2, w - 2, h - 2, max(0, self._radius - 1)))
        self.itemconfigure(self._border_id, fill=col, outline=col)



class SegmentedPills(tk.Canvas):
    """Single-tap segmented pill bar (replaces ttk.Combobox and ttk.Notebook tabs).
    Creates all canvas items once and updates colors in place so hover/motion events
    never delete canvas items mid-tap."""

    def __init__(self, parent, options, variable=None, command=None, font_spec=None,
                 pad_x=14, pad_y=6, radius=10, bg_well=BG_DARKER, active_color=ACCENT_RED):
        self._choices = list(options)
        self._items = [opt if isinstance(opt, tuple) else (opt, str(opt)) for opt in self._choices]
        self._var = variable or tk.StringVar(value=self._items[0][0] if self._items else "")
        self._cmd = command
        self._font = tkfont.Font(font=font_spec or (FONT, 12, "bold"))
        self._pad_x = pad_x
        self._pad_y = pad_y
        self._radius = radius
        self._bg_well = bg_well
        self._active_color = active_color
        self._hover_idx = None
        self._last_fire = 0.0
        self._rects = []
        self._pill_ids = []

        item_widths = [self._font.measure(lbl) + 2 * pad_x for _, lbl in self._items]
        total_w = sum(item_widths) + 8 + max(0, len(self._items) - 1) * 4
        total_h = self._font.metrics("linespace") + 2 * pad_y + 8
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=total_w, height=total_h, takefocus=0)

        self._item_widths = item_widths
        self._total_w = total_w
        self._total_h = total_h
        self._build_items()
        self._recolor()

        self.bind("<ButtonPress-1>", self._on_click)
        self.bind("<Double-Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self._var.trace_add("write", lambda *_: self._recolor())

    def _build_items(self):
        self._well_id = round_rect(
            self, 0, 0, self._total_w, self._total_h, self._radius + 2, fill=self._bg_well, outline=BORDER_SUBTLE
        )
        x = 4
        for (val, lbl), iw in zip(self._items, self._item_widths):
            x1, y1, x2, y2 = x, 4, x + iw, self._total_h - 4
            self._rects.append((x1, y1, x2, y2, val))
            bg_id = round_rect(self, x1, y1, x2, y2, self._radius, fill=self._bg_well, outline=self._bg_well)
            txt_id = self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=lbl, font=self._font, fill=TEXT_MUTED)
            self._pill_ids.append((bg_id, txt_id, val))
            x = x2 + 4

    def _recolor(self):
        cur_val = self._var.get()
        for idx, (bg_id, txt_id, val) in enumerate(self._pill_ids):
            if val == cur_val:
                fill, fg = self._active_color, TEXT_LIGHT
            elif idx == self._hover_idx:
                fill, fg = BG_GREY, TEXT_LIGHT
            else:
                fill, fg = self._bg_well, TEXT_MUTED
            self.itemconfigure(bg_id, fill=fill, outline=fill)
            self.itemconfigure(txt_id, fill=fg)

    def _hit_index(self, x, y):
        if not (0 <= y <= self._total_h):
            return None
        for idx, (x1, _y1, x2, _y2, _val) in enumerate(self._rects):
            if x1 - 3 <= x <= x2 + 3:
                return idx
        return None

    def _on_motion(self, e):
        idx = self._hit_index(e.x, e.y)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self._recolor()

    def _on_leave(self, _e):
        if self._hover_idx is not None:
            self._hover_idx = None
            self._recolor()

    def _on_click(self, e):
        idx = self._hit_index(e.x, e.y)
        if idx is None:
            return "break"
        self._select_index(idx)
        return "break"

    def _on_release(self, e):
        idx = self._hit_index(e.x, e.y)
        if idx is not None and self._rects[idx][4] != self._var.get():
            self._select_index(idx)
        return "break"

    def _select_index(self, idx):
        now = time.monotonic()
        val = self._rects[idx][4]
        if val != self._var.get() or (now - self._last_fire > 0.16):
            self._last_fire = now
            self._var.set(val)
            self._recolor()
            if self._cmd:
                self.after_idle(lambda v=val: self._cmd(v))


class MultiSelectPills(tk.Canvas):
    """Single-tap multi-select resolution pill bar for Batch Slate Builder.
    Allows selecting one or multiple resolutions (16x9, 1x1, 4x5, 9x16, or ALL 4)
    and updates canvas items in place without deleting items on hover/tap."""

    def __init__(self, parent, options, initial=None, command=None, font_spec=None,
                 pad_x=11, pad_y=5, radius=9, bg_well=BG_DARKER, active_color=ACCENT_RED):
        self._choices = [opt if isinstance(opt, tuple) else (opt, str(opt)) for opt in options]
        self._all_keys = [k for k, _ in self._choices if k != "ALL"]
        self._selected = set(initial if initial else [self._all_keys[0]])
        self._cmd = command
        self._font = tkfont.Font(font=font_spec or (FONT, 11, "bold"))
        self._pad_x = pad_x
        self._pad_y = pad_y
        self._radius = radius
        self._bg_well = bg_well
        self._active_color = active_color
        self._hover_idx = None
        self._last_fire = 0.0
        self._rects = []
        self._pill_ids = []

        item_widths = [self._font.measure(f"✓ {lbl}") + 2 * pad_x for _, lbl in self._choices]
        total_w = sum(item_widths) + 8 + max(0, len(self._choices) - 1) * 4
        total_h = self._font.metrics("linespace") + 2 * pad_y + 8
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=total_w, height=total_h, takefocus=0)

        self._item_widths = item_widths
        self._total_w = total_w
        self._total_h = total_h
        self._build_items()
        self._recolor()

        self.bind("<ButtonPress-1>", self._on_click)
        self.bind("<Double-Button-1>", self._on_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

    def _build_items(self):
        self._well_id = round_rect(
            self, 0, 0, self._total_w, self._total_h, self._radius + 2, fill=self._bg_well, outline=BORDER_SUBTLE
        )
        x = 4
        for (val, lbl), iw in zip(self._choices, self._item_widths):
            x1, y1, x2, y2 = x, 4, x + iw, self._total_h - 4
            self._rects.append((x1, y1, x2, y2, val, lbl))
            bg_id = round_rect(self, x1, y1, x2, y2, self._radius, fill=self._bg_well, outline=self._bg_well)
            txt_id = self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=lbl, font=self._font, fill=TEXT_MUTED)
            self._pill_ids.append((bg_id, txt_id, val, lbl))
            x = x2 + 4

    def get_selected(self):
        """Return selected resolution keys in canonical ASPECT_KEYS order."""
        ordered = [k for k in self._all_keys if k in self._selected]
        return ordered if ordered else [self._all_keys[0]]

    def set_selected(self, keys):
        valid = [k for k in keys if k in self._all_keys]
        self._selected = set(valid if valid else [self._all_keys[0]])
        self._recolor()

    def _recolor(self):
        all_on = len(self._selected) == len(self._all_keys)
        for idx, (bg_id, txt_id, val, lbl) in enumerate(self._pill_ids):
            is_on = all_on if val == "ALL" else (val in self._selected)
            if is_on:
                fill = BG_BLUE if val == "ALL" else self._active_color
                fg = TEXT_LIGHT
                disp_txt = f"✓ {lbl}"
            elif idx == self._hover_idx:
                fill = BG_GREY
                fg = TEXT_LIGHT
                disp_txt = lbl
            else:
                fill = self._bg_well
                fg = ACCENT_YELLOW if val == "ALL" else TEXT_MUTED
                disp_txt = lbl
            self.itemconfigure(bg_id, fill=fill, outline=fill)
            self.itemconfigure(txt_id, fill=fg, text=disp_txt)

    def _hit_index(self, x, y):
        if not (0 <= y <= self._total_h):
            return None
        for idx, (x1, _y1, x2, _y2, _val, _lbl) in enumerate(self._rects):
            if x1 - 3 <= x <= x2 + 3:
                return idx
        return None

    def _on_motion(self, e):
        idx = self._hit_index(e.x, e.y)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self._recolor()

    def _on_leave(self, _e):
        if self._hover_idx is not None:
            self._hover_idx = None
            self._recolor()

    def _on_click(self, e):
        idx = self._hit_index(e.x, e.y)
        if idx is None:
            return "break"
        now = time.monotonic()
        if now - self._last_fire < 0.14:
            return "break"
        self._last_fire = now
        val = self._rects[idx][4]
        if val == "ALL":
            if len(self._selected) == len(self._all_keys):
                self._selected = {self._all_keys[0]}
            else:
                self._selected = set(self._all_keys)
        else:
            if val in self._selected:
                if len(self._selected) > 1:
                    self._selected.remove(val)
            else:
                self._selected.add(val)
        self._recolor()
        if self._cmd:
            sel = self.get_selected()
            self.after_idle(lambda s=sel, v=val: self._cmd(s, v))
        return "break"


class RoundedToggle(tk.Canvas):
    """Single-tap pill toggle switch for boolean options (updates items in place)."""

    def __init__(self, parent, text, variable, font_spec=None):
        self._var = variable
        self._text = text
        self._font = tkfont.Font(font=font_spec or (FONT, 13, "bold"))
        self._last_fire = 0.0
        track_w, track_h = 44, 24
        w = track_w + 10 + self._font.measure(text) + 8
        h = max(track_h + 4, self._font.metrics("linespace") + 6)
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=w, height=h, takefocus=0)
        self._track_w, self._track_h, self._h = track_w, track_h, h

        y1 = (self._h - self._track_h) / 2
        y2 = y1 + self._track_h
        self._y1 = y1
        self._track_id = round_rect(self, 2, y1, 2 + self._track_w, y2, self._track_h / 2, fill=BG_DARKER, outline=BORDER_SUBTLE)
        knob_d = self._track_h - 6
        self._knob_id = self.create_oval(5, y1 + 3, 5 + knob_d, y1 + 3 + knob_d, fill=TEXT_LIGHT, outline=TEXT_LIGHT)
        self._label_id = self.create_text(
            self._track_w + 12, self._h / 2, text=self._text, anchor="w", font=self._font, fill=TEXT_MUTED
        )
        self._recolor()

        self.bind("<ButtonPress-1>", self._toggle)
        self.bind("<Double-Button-1>", self._toggle)
        self._var.trace_add("write", lambda *_: self._recolor())

    def _toggle(self, _e=None):
        now = time.monotonic()
        if now - self._last_fire < 0.14:
            return "break"
        self._last_fire = now
        self._var.set(not self._var.get())
        self._recolor()
        return "break"

    def _recolor(self):
        on = bool(self._var.get())
        fill = ACCENT_RED if on else BG_DARKER
        outline = ACCENT_RED if on else BORDER_SUBTLE
        self.itemconfigure(self._track_id, fill=fill, outline=outline)
        knob_d = self._track_h - 6
        kx = (2 + self._track_w - 3 - knob_d) if on else 5
        self.coords(self._knob_id, kx, self._y1 + 3, kx + knob_d, self._y1 + 3 + knob_d)
        self.itemconfigure(self._label_id, fill=TEXT_LIGHT if on else TEXT_MUTED)


class SJLogo(tk.Canvas):
    """Red rounded square with dark outlined smiley (matches the bottom-right slate badge)."""

    def __init__(self, parent, size=46):
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_DARK
        super().__init__(parent, width=size, height=size, bg=parent_bg, highlightthickness=0, bd=0, takefocus=0)
        round_rect(self, 0, 0, size, size, size * 0.20, fill=ACCENT_RED, outline=ACCENT_RED)
        c, rad, lw = size / 2, size * 0.31, max(2.5, size / 14)
        self.create_oval(c - rad, c - rad, c + rad, c + rad, outline=BG_DARK, width=lw)
        ey1, ey2, ex = c - rad * 0.38, c - rad * 0.05, rad * 0.28
        for dx in (-ex, ex):
            self.create_line(c + dx, ey1, c + dx, ey2, fill=BG_DARK, width=lw, capstyle="round")
        self.create_arc(c - rad * 0.48, c - rad * 0.32, c + rad * 0.48, c + rad * 0.52,
                        start=200, extent=140, style="arc", outline=BG_DARK, width=lw)


def mkbtn(parent, text="", command=None, bg=None, padx=18, pady=8, **_ignored):
    color = {
        "#4CAF50": BG_GREEN,
        BG_GREEN: BG_GREEN,
        BG_BLUE: BG_BLUE,
        BG_DARKER: BG_GREY,
        BG_GREY: BG_GREY,
    }.get(bg, ACCENT_RED)
    return RoundedButton(parent, text=text, command=command, color=color, padx=padx, pady=pady)


def bind_auto_wrap(label, container=None, min_wrap=320, pad=24):
    """Automatically wrap multi-line or dynamic status labels to their container width
    so text never overflows or clips off the right edge of a card."""
    host = container or label.master
    label.configure(wraplength=820, justify="left")

    def _on_cfg(e):
        if e.width > 60:
            label.configure(wraplength=max(min_wrap, e.width - pad))

    host.bind("<Configure>", _on_cfg, add="+")
    return label


# ---------------------------------------------------------------------------
# Main Workstation Application
# ---------------------------------------------------------------------------
class SuperJoyWorkstation:
    def __init__(self, root):
        global FONT
        self.root = root
        FONT = pick_font_family()
        for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(fname).configure(family=FONT)
            except Exception:
                pass

        self.root.title("SuperJoy Broadcast Slating Workstation")
        self.root.geometry("980x810")
        self.root.minsize(920, 750)
        self.root.configure(bg=BG_DARK)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=BG_DARK, foreground=TEXT_LIGHT, font=(FONT, 13))
        self.style.configure(
            "Treeview",
            background=BG_DARKER,
            foreground=TEXT_LIGHT,
            fieldbackground=BG_DARKER,
            borderwidth=0,
            relief="flat",
            rowheight=28,
            font=(FONT, 11),
        )
        self.style.map("Treeview", background=[("selected", ACCENT_RED)], foreground=[("selected", TEXT_LIGHT)])
        self.style.configure(
            "Treeview.Heading",
            background=BG_GREY,
            foreground=TEXT_LIGHT,
            borderwidth=0,
            relief="flat",
            font=(FONT, 10, "bold"),
            padding=(6, 5),
        )
        self.style.map("Treeview.Heading", background=[("active", BG_GREY_HOVER)])

        # State variables
        self.tsv_path = tk.StringVar()
        self.template_dir = tk.StringVar(
            value=DEFAULT_TEMPLATE_AEP if os.path.exists(DEFAULT_TEMPLATE_AEP) else ""
        )
        self.videos_dir = tk.StringVar()
        self.unslate_dir = tk.StringVar()
        self.marry_slates_dir = tk.StringVar()
        self.marry_csv_path = tk.StringVar()
        self.output_mode_var = tk.StringVar(value="slated_masters")  # 'slated_masters' or 'slates_only'
        self.fps_var = tk.StringVar(value=DEFAULT_FPS_LABEL)
        self.aspect_var = tk.StringVar(value=DEFAULT_ASPECT)
        self.active_tab_var = tk.StringVar(value="1")  # Open on Batch Slate Builder by default
        self.manual_batch_data = []
        self.marry_pairs_data = []
        self._loading_row = False

        # Shared campaign fields (filled in by user) + per-spot fields (pulled from master video filenames)
        self.f_agency = tk.StringVar()
        self.f_client = tk.StringVar()
        self.f_title = tk.StringVar()
        self.f_id = tk.StringVar()
        self.f_trt = tk.StringVar()
        self.f_date = tk.StringVar(value=today_yyyy_mm_dd())
        self.f_workspace = tk.StringVar()
        self.f_audio = tk.StringVar(value="STEREO")
        self.f_copyright = tk.StringVar()
        self.f_flame = tk.BooleanVar(value=False)

        self.create_widgets()

        # Live status & auto-sync traces
        self.template_dir.trace_add("write", lambda *_: self.update_asset_badges())
        self.videos_dir.trace_add("write", lambda *_: self._on_videos_dir_changed())
        self.tsv_path.trace_add("write", lambda *_: self.update_file_preview())
        self.unslate_dir.trace_add("write", lambda *_: self.update_unslate_preview())
        self.marry_slates_dir.trace_add("write", lambda *_: self.update_marry_preview())
        self.marry_csv_path.trace_add("write", lambda *_: self.update_marry_preview())
        self.output_mode_var.trace_add("write", lambda *_: self._on_output_mode_changed())
        self.update_asset_badges()

        # Propagate shared campaign metadata edits to queued batch items in real time
        for shared_var in (
            self.f_agency,
            self.f_client,
            self.f_workspace,
            self.f_copyright,
            self.f_date,
            self.f_audio,
            self.f_flame,
        ):
            shared_var.trace_add("write", lambda *_: self._sync_shared_fields_to_batch())

        # Apply the macOS Tk 8.6.12 TKWindow.mouseInResizeArea tap fix immediately and on map
        patch_macos_tk_tap_bug(self.root)
        self.root.after(40, lambda: wake_macos_window(self.root))

    # ------------------------------------------------------------------
    # Modal Dialog Wrapper (waits for LeftMouseUp before opening NSOpenPanel/NSAlert)
    # ------------------------------------------------------------------
    def _browse_dir(self, target_var, title="Select Folder"):
        def _open():
            reset_tk_mouse_state(self.root)
            chosen = filedialog.askdirectory(parent=self.root, title=title)
            wake_macos_window(self.root)
            if chosen:
                target_var.set(chosen)

        run_after_mouse_up(self.root, _open)

    def _browse_template(self, target_var, title="Select After Effects Slate Template (.aep)"):
        def _open():
            reset_tk_mouse_state(self.root)
            cur = target_var.get().strip()
            init_dir = os.path.dirname(cur) if cur and os.path.exists(cur) else os.path.dirname(DEFAULT_TEMPLATE_AEP)
            chosen = filedialog.askopenfilename(
                parent=self.root,
                title=title,
                initialdir=init_dir,
                filetypes=[("After Effects Template", "*.aep"), ("All Files", "*.*")],
            )
            wake_macos_window(self.root)
            if chosen:
                target_var.set(chosen)

        run_after_mouse_up(self.root, _open)

    def _browse_file(self, target_var, title="Select Metadata File"):
        def _open():
            reset_tk_mouse_state(self.root)
            chosen = filedialog.askopenfilename(
                parent=self.root,
                title=title,
                filetypes=[("Metadata Files", "*.tsv *.csv *.txt"), ("All Files", "*.*")],
            )
            wake_macos_window(self.root)
            if chosen:
                target_var.set(chosen)

        run_after_mouse_up(self.root, _open)

    def _alert(self, kind, title, message):
        def _open():
            reset_tk_mouse_state(self.root)
            fn = getattr(messagebox, kind, messagebox.showinfo)
            fn(title, message, parent=self.root)
            wake_macos_window(self.root)

        run_after_mouse_up(self.root, _open)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def create_widgets(self):
        # 1. Header Bar
        header = tk.Frame(self.root, bg=BG_DARK)
        header.pack(side="top", fill="x", padx=24, pady=(10, 4))

        title_col = tk.Frame(header, bg=BG_DARK)
        title_col.pack(side="left")
        title_row = tk.Frame(title_col, bg=BG_DARK)
        title_row.pack(anchor="w")
        tk.Label(
            title_row,
            text="SUPERJOY",
            font=(FONT, 22, "bold"),
            bg=BG_DARK,
            fg=ACCENT_RED,
        ).pack(side="left")
        tk.Label(
            title_row,
            text="  SLATING WORKSTATION",
            font=(FONT, 22, "bold"),
            bg=BG_DARK,
            fg=TEXT_LIGHT,
        ).pack(side="left")
        tk.Label(
            title_col,
            text="Broadcast Slate Automation  •  Slates + Videos / Standalone Slates / Marry Slates / Un-Slate",
            font=(FONT, 11),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))

        SJLogo(header, 46).pack(side="right", padx=(12, 0))

        # 2. Pinned Bottom Action Footer (packed BEFORE expandable workspace so it is NEVER clipped!)
        footer = tk.Frame(self.root, bg=BG_DARK)
        footer.pack(side="bottom", fill="x", padx=24, pady=(5, 10))

        self.btn_run = RoundedButton(
            footer,
            text="GENERATE .AEP & QUEUE IN AME",
            command=self.execute_workflow_thread,
            color=ACCENT_RED,
            font_spec=(FONT, 15, "bold"),
            padx=36,
            pady=11,
            radius=16,
        )
        self.btn_run.pack(anchor="center")

        # 3. Master Assets Card
        assets_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=11)
        assets_card.pack(side="top", fill="x", padx=24, pady=(0, 6))
        ab = assets_card.body
        ab.columnconfigure(1, weight=1)

        hdr_row = tk.Frame(ab, bg=BG_CARD)
        hdr_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        tk.Label(
            hdr_row,
            text="MASTER ASSETS & STUDIO CONFORM",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(side="left")
        self.asset_status_lbl = tk.Label(
            hdr_row,
            text="Select .aep template & master videos folder",
            font=(FONT, 11),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.asset_status_lbl.pack(side="right")

        tk.Label(ab, text="SLATE TEMPLATE (.AEP)", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(ab, self.template_dir, 38).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            ab,
            text="Browse",
            command=lambda: self._browse_template(self.template_dir, "Select After Effects Slate Template (.aep)"),
            padx=18,
            pady=5,
        ).grid(row=1, column=2, pady=2)

        tk.Label(ab, text="MASTER VIDEOS", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(ab, self.videos_dir, 38).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            ab,
            text="Browse",
            command=lambda: self._browse_dir(self.videos_dir, "Select Master Videos Folder"),
            padx=18,
            pady=5,
        ).grid(row=2, column=2, pady=2)

        # Fallback FPS & Aspect Pill Bar (No ttk.Combobox!)
        tk.Label(ab, text="STUDIO STANDARD", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=(4, 2)
        )
        std_row = tk.Frame(ab, bg=BG_CARD)
        std_row.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(4, 2))

        fps_choices = [(k, k) for k in ("23.976", "24", "25", "29.97", "30", "59.94", "60")]
        self.fps_pills = SegmentedPills(
            std_row,
            fps_choices,
            variable=self.fps_var,
            font_spec=(FONT, 11, "bold"),
            pad_x=9,
            pad_y=3,
            radius=8,
        )
        self.fps_pills.pack(side="left")

        tk.Label(std_row, text="FPS", font=(FONT, 10, "bold"), bg=BG_CARD, fg=TEXT_MUTED).pack(
            side="left", padx=(5, 14)
        )

        aspect_choices = [(k, k) for k in ASPECT_RESOLUTIONS]
        self.aspect_pills = SegmentedPills(
            std_row,
            aspect_choices,
            variable=self.aspect_var,
            font_spec=(FONT, 11, "bold"),
            pad_x=10,
            pad_y=3,
            radius=8,
        )
        self.aspect_pills.pack(side="left")

        self.res_label = tk.Label(std_row, text="", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.res_label.pack(side="left", padx=(8, 0))
        self.aspect_var.trace_add("write", lambda *_: self.update_res_label())
        self.update_res_label()

        # Output Mode Row: Slated Masters (Slate + Video) vs Standalone Slates Only (No Video Required)
        tk.Label(ab, text="BUILD OUTPUT MODE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW).grid(
            row=4, column=0, sticky="w", padx=(0, 10), pady=(4, 1)
        )
        mode_row = tk.Frame(ab, bg=BG_CARD)
        mode_row.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(4, 1))
        self.output_mode_pills = SegmentedPills(
            mode_row,
            [
                ("slated_masters", "Slated Masters (Slate + Video)"),
                ("slates_only", "Standalone Slates Only (No Video Attached)"),
            ],
            variable=self.output_mode_var,
            font_spec=(FONT, 10, "bold"),
            pad_x=12,
            pad_y=3,
            radius=8,
        )
        self.output_mode_pills.pack(side="left")
        self.output_mode_hint = tk.Label(
            mode_row,
            text="Pairs each slate with its master video",
            font=(FONT, 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.output_mode_hint.pack(side="left", padx=(10, 0))

        # 4. Segmented Mode Tab Bar (4 Focused Broadcast Modes)
        tab_bar_frame = tk.Frame(self.root, bg=BG_DARK)
        tab_bar_frame.pack(side="top", fill="x", padx=24, pady=(2, 5))

        self.tab_pills = SegmentedPills(
            tab_bar_frame,
            [
                ("1", "1. Batch Slate Builder"),
                ("0", "2. CSV / TSV + Video Naming"),
                ("3", "3. Marry Slates + Videos"),
                ("2", "4. Un-Slate (Trim 7.0s)"),
            ],
            variable=self.active_tab_var,
            command=self.on_tab_changed,
            font_spec=(FONT, 11, "bold"),
            pad_x=16,
            pad_y=5,
            radius=10,
        )
        self.tab_pills.pack(side="left")

        # Compatibility shim so any external code checking self.notebook works seamlessly
        self.notebook = self

        # 5. Workspace Card (hosts the 4 mode pages; indices 0, 1, 2, 3 preserved)
        self.workspace_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=13)
        self.workspace_card.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 4))
        wb = self.workspace_card.body

        self.tab_file = tk.Frame(wb, bg=BG_CARD)
        self.tab_builder = tk.Frame(wb, bg=BG_CARD)
        self.tab_unslate = tk.Frame(wb, bg=BG_CARD)
        self.tab_marry = tk.Frame(wb, bg=BG_CARD)
        self._pages = [self.tab_file, self.tab_builder, self.tab_unslate, self.tab_marry]

        self._build_tab_file()
        self._build_tab_builder()
        self._build_tab_unslate()
        self._build_tab_marry()

        self._show_tab(int(self.active_tab_var.get()))

    def _build_tab_file(self):
        p = self.tab_file
        p.columnconfigure(0, weight=1)

        tk.Label(
            p,
            text="CSV / TSV METADATA IMPORT  •  ACCURATE VIDEO FILENAME SYNC",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(2, 2))
        desc_lbl = tk.Label(
            p,
            text="Load a .csv, .tsv, or .txt metadata sheet to build slates (with or without master videos), send rows to the Batch Slate Builder for editing, or combine with Master Videos to enforce accurate canonical filenames.",
            font=(FONT, 11),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        desc_lbl.pack(anchor="w", pady=(0, 10))
        bind_auto_wrap(desc_lbl, p)

        f1 = tk.Frame(p, bg=BG_CARD)
        f1.pack(fill="x", pady=3)
        f1.columnconfigure(1, weight=1)
        tk.Label(f1, text="METADATA FILE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        RoundedEntry(f1, self.tsv_path, 40).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        mkbtn(
            f1,
            text="Browse File",
            command=lambda: self._browse_file(self.tsv_path),
            padx=18,
            pady=7,
        ).grid(row=0, column=2)

        self.file_preview_lbl = tk.Label(
            p,
            text="No metadata file selected.",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        )
        self.file_preview_lbl.pack(anchor="w", pady=(8, 8))
        bind_auto_wrap(self.file_preview_lbl, p)

        # Action toolbar for combining CSV/TSV with Master Videos & Queue
        csv_bar = tk.Frame(p, bg=BG_CARD)
        csv_bar.pack(fill="x", pady=(0, 10))
        mkbtn(
            csv_bar,
            text="Load CSV + Pair Videos into Batch Builder",
            bg=BG_BLUE,
            command=lambda: self.load_csv_into_batch_builder(switch_to_builder=True),
            padx=14,
            pady=6,
        ).pack(side="left")
        mkbtn(
            csv_bar,
            text="Rename Master Video Files from CSV Metadata",
            bg="#4CAF50",
            command=self.rename_master_videos_from_metadata,
            padx=14,
            pady=6,
        ).pack(side="left", padx=(8, 0))

        info_card = RoundedCard(p, bg_fill=BG_DARKER, border_color=BORDER_SUBTLE, radius=12, pad=12)
        info_card.pack(fill="x", pady=(2, 0))
        ib = info_card.body
        tk.Label(
            ib,
            text="HOW CSV / TSV + MASTER VIDEO COMBINING WORKS",
            font=(FONT, 11, "bold"),
            bg=BG_DARKER,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(0, 5))
        steps = (
            "• Accurate Output Naming: Slated deliveries are automatically named <Ad-ID>_<Canonical_CSV_Title>_Slated.mov using your spreadsheet's exact Ad-ID and Title.\n"
            "• Source File Renaming: Tap 'Rename Master Video Files from CSV Metadata' to rename raw master videos on disk (e.g. 'PJ595169000H_v3_final.mov' → 'PJ595169000H_PapaJohns_Pairings_16x9_15.mov').\n"
            "• Standalone Slates Only: Switch 'BUILD OUTPUT MODE' above to 'Standalone Slates Only' to build 5.0s slates from your CSV without needing any master videos!"
        )
        steps_lbl = tk.Label(ib, text=steps, font=(FONT, 11), bg=BG_DARKER, fg=TEXT_MUTED, justify="left")
        steps_lbl.pack(anchor="w")
        bind_auto_wrap(steps_lbl, ib)

    def _build_tab_builder(self):
        p = self.tab_builder

        # Section 1: Campaign Fields (User-entered shared fields + auto YYYY_MM_DD Date)
        sec1_hdr = tk.Frame(p, bg=BG_CARD)
        sec1_hdr.pack(fill="x", pady=(0, 2))
        tk.Label(
            sec1_hdr,
            text="CAMPAIGN METADATA (APPLIED TO BATCH)",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(side="left")
        tk.Label(
            sec1_hdr,
            text="Works with Master Videos OR Standalone (Slates Only)",
            font=(FONT, 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(side="right")

        form_frame = tk.Frame(p, bg=BG_CARD)
        form_frame.pack(fill="x", pady=(0, 3))
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        campaign_fields = [
            ("AGENCY", self.f_agency, 0, 0, TEXT_LIGHT),
            ("CLIENT", self.f_client, 0, 2, TEXT_LIGHT),
            ("WORKSPACE", self.f_workspace, 1, 0, TEXT_LIGHT),
            ("COPYRIGHT", self.f_copyright, 1, 2, TEXT_LIGHT),
            ("DATE", self.f_date, 2, 0, ACCENT_YELLOW),
            ("AUDIO", self.f_audio, 2, 2, TEXT_MUTED),
        ]

        for label, var, r, c, lbl_color in campaign_fields:
            tk.Label(form_frame, text=label, font=(FONT, 11, "bold"), bg=BG_CARD, fg=lbl_color).grid(
                row=r, column=c, sticky="w", padx=(2, 8), pady=2
            )
            RoundedEntry(form_frame, var, 20).grid(row=r, column=c + 1, sticky="ew", padx=(0, 12), pady=2)

        # Spot-Specific Auto-Parsed Fields (Ad-ID, Title, TRT + Flame Toggle)
        sec2_hdr = tk.Frame(p, bg=BG_CARD)
        sec2_hdr.pack(fill="x", pady=(3, 2))
        tk.Label(
            sec2_hdr,
            text="SPOT METADATA (AUTO-PULLED FROM VIDEOS OR CSV  •  OR ENTER MANUALLY FOR STANDALONE SLATES)",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        ).pack(side="left")

        spot_frame = tk.Frame(p, bg=BG_CARD)
        spot_frame.pack(fill="x", pady=(0, 3))
        spot_frame.columnconfigure(1, weight=2)
        spot_frame.columnconfigure(3, weight=4)
        spot_frame.columnconfigure(5, weight=1)

        tk.Label(spot_frame, text="AD-ID", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW).grid(
            row=0, column=0, sticky="w", padx=(2, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_id, 12).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)

        tk.Label(spot_frame, text="TITLE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_title, 22).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=2)

        tk.Label(spot_frame, text="TRT", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=4, sticky="w", padx=(0, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_trt, 6).grid(row=0, column=5, sticky="ew", padx=(0, 10), pady=2)

        RoundedToggle(spot_frame, "Flame Logo", self.f_flame, font_spec=(FONT, 11, "bold")).grid(
            row=0, column=6, sticky="e", padx=(2, 0), pady=2
        )

        # Multi-Resolution Selector & Retroactive Resolution Override Row
        res_row = tk.Frame(p, bg=BG_CARD)
        res_row.pack(fill="x", pady=(2, 2))
        tk.Label(
            res_row,
            text="SLATE RES",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        ).pack(side="left", padx=(2, 8))
        self.batch_res_pills = MultiSelectPills(
            res_row,
            options=[
                ("16x9", "16x9 (1920×1080)"),
                ("1x1", "1x1 (1080×1080)"),
                ("4x5", "4x5 (1080×1350)"),
                ("9x16", "9x16 (1080×1920)"),
                ("ALL", "ALL 4"),
            ],
            initial=[DEFAULT_ASPECT],
            font_spec=(FONT, 10, "bold"),
            pad_x=9,
            pad_y=4,
        )
        self.batch_res_pills.pack(side="left")
        mkbtn(
            res_row,
            text="Apply Res to Selected",
            bg=BG_BLUE,
            command=self.apply_res_to_selected,
            padx=12,
            pady=4,
        ).pack(side="right")

        # Action & Queue Toolbar
        bar = tk.Frame(p, bg=BG_CARD)
        bar.pack(fill="x", pady=(2, 3))
        mkbtn(
            bar,
            text="Auto-Pull Videos",
            bg=BG_BLUE,
            command=lambda: self.populate_batch_from_videos(notify_if_empty=True),
            padx=10,
            pady=5,
        ).pack(side="left")
        mkbtn(
            bar,
            text="Merge CSV/TXT",
            bg=BG_BLUE,
            command=self.prompt_and_merge_csv_into_batch,
            padx=10,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="+ Add / Update",
            bg="#4CAF50",
            command=self.add_to_batch,
            padx=10,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="Cycle Res",
            bg=BG_GREY,
            command=self.cycle_selected_resolution,
            padx=9,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(bar, text="Remove", bg=BG_GREY, command=self.remove_from_batch, padx=9, pady=5).pack(
            side="left", padx=(5, 0)
        )
        mkbtn(bar, text="Clear", bg=BG_GREY, command=self.clear_batch, padx=9, pady=5).pack(
            side="left", padx=(5, 0)
        )
        self.batch_count_lbl = tk.Label(
            bar, text="0 slates in queue", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW
        )
        self.batch_count_lbl.pack(side="right", padx=4)

        # Queue Table (includes RESOLUTION column; tapping RESOLUTION cell cycles 16x9 -> 1x1 -> 4x5 -> 9x16)
        tree_wrap = tk.Frame(p, bg=BORDER_SUBTLE, bd=0, highlightthickness=0)
        tree_wrap.pack(fill="both", expand=True, pady=(2, 0))
        columns = ("id", "title", "res", "trt", "date", "client", "agency")
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=4)
        self.tree.heading("id", text="AD-ID")
        self.tree.heading("title", text="TITLE (SPACES → _)")
        self.tree.heading("res", text="RESOLUTION (TAP TO CHANGE)")
        self.tree.heading("trt", text="TRT")
        self.tree.heading("date", text="DATE")
        self.tree.heading("client", text="CLIENT")
        self.tree.heading("agency", text="AGENCY")
        self.tree.column("id", width=110, minwidth=85, anchor="w")
        self.tree.column("title", width=225, minwidth=150, anchor="w", stretch=True)
        self.tree.column("res", width=155, minwidth=130, anchor="center")
        self.tree.column("trt", width=55, minwidth=45, anchor="center")
        self.tree.column("date", width=95, minwidth=80, anchor="center")
        self.tree.column("client", width=95, minwidth=75, anchor="w")
        self.tree.column("agency", width=95, minwidth=75, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=1, pady=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<ButtonPress-1>", self._on_tree_tap, add="+")

    def _build_tab_marry(self):
        p = self.tab_marry
        p.columnconfigure(0, weight=1)

        tk.Label(
            p,
            text="MARRY EXISTING SLATES + EXISTING MASTER VIDEOS",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(2, 2))
        marry_desc = tk.Label(
            p,
            text="Pairs already-rendered slates (.mov, .mp4, .mxf, .png, .tif, .psd, .jpg) with your Master Videos by Ad-ID (and aspect ratio), optionally applying accurate delivery filenames from a CSV/TSV sheet, and queues the married masters in Adobe Media Encoder.",
            font=(FONT, 11),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        marry_desc.pack(anchor="w", pady=(0, 8))
        bind_auto_wrap(marry_desc, p)

        form = tk.Frame(p, bg=BG_CARD)
        form.pack(fill="x", pady=2)
        form.columnconfigure(1, weight=1)

        tk.Label(form, text="EXISTING SLATES", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(form, self.marry_slates_dir, 36).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            form,
            text="Browse Slates",
            command=lambda: self._browse_dir(self.marry_slates_dir, "Select Existing Slates Folder"),
            padx=14,
            pady=5,
        ).grid(row=0, column=2, pady=2)

        tk.Label(form, text="CSV / TXT (OPTIONAL)", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(form, self.marry_csv_path, 36).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            form,
            text="Browse CSV",
            command=lambda: self._browse_file(self.marry_csv_path, "Select Optional CSV/TSV for Accurate Naming"),
            padx=14,
            pady=5,
        ).grid(row=1, column=2, pady=2)

        mbar = tk.Frame(p, bg=BG_CARD)
        mbar.pack(fill="x", pady=(4, 4))
        mkbtn(
            mbar,
            text="Scan & Preview Slate ↔ Video Pairs",
            bg=BG_BLUE,
            command=self.update_marry_preview,
            padx=12,
            pady=5,
        ).pack(side="left")
        self.marry_status_lbl = tk.Label(
            mbar,
            text="Select Existing Slates folder and Master Videos folder (above) to preview pairs.",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        )
        self.marry_status_lbl.pack(side="left", padx=(12, 0))

        mtree_wrap = tk.Frame(p, bg=BORDER_SUBTLE, bd=0, highlightthickness=0)
        mtree_wrap.pack(fill="both", expand=True, pady=(2, 0))
        mcols = ("id", "slate", "video", "output")
        self.marry_tree = ttk.Treeview(mtree_wrap, columns=mcols, show="headings", height=4)
        self.marry_tree.heading("id", text="AD-ID")
        self.marry_tree.heading("slate", text="EXISTING SLATE FILE")
        self.marry_tree.heading("video", text="MASTER VIDEO FILE")
        self.marry_tree.heading("output", text="MARRIED DELIVERY FILENAME")
        self.marry_tree.column("id", width=110, minwidth=85, anchor="w")
        self.marry_tree.column("slate", width=230, minwidth=150, anchor="w")
        self.marry_tree.column("video", width=230, minwidth=150, anchor="w")
        self.marry_tree.column("output", width=270, minwidth=170, anchor="w", stretch=True)
        self.marry_tree.pack(fill="both", expand=True, padx=1, pady=1)

    def _build_tab_unslate(self):
        p = self.tab_unslate

        tk.Label(
            p,
            text="BATCH UN-SLATE (AE + MEDIA ENCODER 7.0s HEAD TRIM)",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(4, 2))
        unslate_desc = tk.Label(
            p,
            text="Builds non-destructive un-slated comps in After Effects (trimming the 5.0s slate + 2.0s black/2-pop leader), saves an editable SuperJoy_Unslate_Project.aep for manual fixes, and queues all clean spots in Adobe Media Encoder.",
            font=(FONT, 12),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        unslate_desc.pack(anchor="w", pady=(0, 16))
        bind_auto_wrap(unslate_desc, p)

        f2 = tk.Frame(p, bg=BG_CARD)
        f2.pack(fill="x", pady=4)
        f2.columnconfigure(1, weight=1)
        tk.Label(f2, text="SLATED VIDEOS", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        RoundedEntry(f2, self.unslate_dir, 40).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        mkbtn(
            f2,
            text="Browse Folder",
            command=lambda: self._browse_dir(self.unslate_dir, "Select Folder of Slated Videos"),
            padx=20,
            pady=8,
        ).grid(row=0, column=2)

        self.unslate_preview_lbl = tk.Label(
            p,
            text="No slated videos folder selected.",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        )
        self.unslate_preview_lbl.pack(anchor="w", pady=(14, 16))
        bind_auto_wrap(self.unslate_preview_lbl, p)

        timeline_card = RoundedCard(p, bg_fill=BG_DARKER, border_color=BORDER_SUBTLE, radius=12, pad=14)
        timeline_card.pack(fill="x", pady=(4, 0))
        tb = timeline_card.body
        tk.Label(
            tb,
            text="MEDIA ENCODER UN-SLATE WORKFLOW",
            font=(FONT, 11, "bold"),
            bg=BG_DARKER,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(0, 6))
        trim_spec_lbl = tk.Label(
            tb,
            text="• Trims exactly 7.0 seconds from the head of every .mov, .mp4, and .mxf file (preserving picture/audio from 01:00:00:00 onward).\n"
                 "• Saves <Folder>/UNSLATED/SuperJoy_Unslate_Project.aep so you can inspect timelines or make manual slip/trim adjustments.\n"
                 "• Queues all trimmed comps in Adobe Media Encoder outputting to <Folder>/UNSLATED/ and logs to Unslate_Log.txt.",
            font=(FONT, 12),
            bg=BG_DARKER,
            fg=TEXT_MUTED,
            justify="left",
        )
        trim_spec_lbl.pack(anchor="w")
        bind_auto_wrap(trim_spec_lbl, tb)

    # ------------------------------------------------------------------
    # Tab & Live Status Helpers
    # ------------------------------------------------------------------
    def select(self, tab_id=None):
        """Compatibility method matching ttk.Notebook.select()."""
        if tab_id is None:
            return self.active_tab_var.get()
        idx = int(tab_id) if str(tab_id).isdigit() else 0
        self.active_tab_var.set(str(idx))
        self._show_tab(idx)
        return str(idx)

    def index(self, tab_id):
        """Compatibility method matching ttk.Notebook.index()."""
        if isinstance(tab_id, int):
            return tab_id
        if str(tab_id).isdigit():
            return int(tab_id)
        if tab_id in self._pages:
            return self._pages.index(tab_id)
        return int(self.active_tab_var.get())

    def _show_tab(self, idx):
        for i, page in enumerate(self._pages):
            if i == idx:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        if str(self.btn_run["state"]) == "normal":
            self.btn_run.config(text=self.run_label())
        self.root.update_idletasks()

    def on_tab_changed(self, val=None):
        idx = int(val) if val is not None and str(val).isdigit() else int(self.active_tab_var.get())
        self._show_tab(idx)

    def _on_output_mode_changed(self):
        slates_only = self.output_mode_var.get() == "slates_only"
        if hasattr(self, "output_mode_hint"):
            self.output_mode_hint.config(
                text="Builds 5.0s slates (+ 2-pop) with NO master videos required"
                if slates_only
                else "Pairs each slate with its master video",
                fg=ACCENT_YELLOW if slates_only else TEXT_MUTED,
            )
        if str(self.btn_run["state"]) == "normal":
            self.btn_run.config(text=self.run_label())
        self.update_asset_badges()

    def update_res_label(self):
        w, h = ASPECT_RESOLUTIONS.get(self.aspect_var.get(), (1920, 1080))
        self.res_label.config(text=f"{w}×{h}")

    def _on_videos_dir_changed(self):
        self.update_asset_badges()
        self.update_marry_preview()
        vdir = self.videos_dir.get().strip()
        if vdir and os.path.isdir(vdir):
            self.populate_batch_from_videos(notify_if_empty=False)

    def update_asset_badges(self):
        tdir = self.template_dir.get().strip()
        vdir = self.videos_dir.get().strip()
        tpls = find_templates(tdir)
        vcnt = 0
        if vdir and os.path.isdir(vdir):
            vcnt = sum(1 for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith("."))
        parts = []
        if tdir:
            if "_aep" in tpls:
                parts.append(f"Template: {os.path.basename(tpls['_aep'])} (16x9, 1x1, 4x5, 9x16)")
            else:
                found_keys = [k for k in ASPECT_RESOLUTIONS if k in tpls]
                found_str = ", ".join(found_keys) or "none"
                parts.append(f"Templates: {len(found_keys)}/4 ({found_str})")
        if self.output_mode_var.get() == "slates_only":
            parts.append("Mode: Standalone Slates Only")
        elif vdir:
            parts.append(f"Videos: {vcnt} found")
        self.asset_status_lbl.config(
            text="  •  ".join(parts) if parts else "Select .aep template & master videos folder",
            fg=ACCENT_YELLOW if parts else TEXT_MUTED,
        )

    def update_file_preview(self):
        path = self.tsv_path.get().strip()
        if not path or not os.path.isfile(path):
            self.file_preview_lbl.config(text="No metadata file selected.", fg=TEXT_MUTED)
            return
        try:
            rows = parse_metadata_file(path)
            vdir = self.videos_dir.get().strip()
            match_note = ""
            if vdir and os.path.isdir(vdir):
                all_vids = [f for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")]
                matched = sum(1 for r in rows if any(ad_id_matches(r.get("id", ""), vf) for vf in all_vids))
                match_note = f"  •  {matched}/{len(rows)} matched in Master Videos"
            self.file_preview_lbl.config(
                text=f"Loaded '{os.path.basename(path)}'  •  {len(rows)} slate row(s){match_note}",
                fg=ACCENT_YELLOW,
            )
        except Exception as e:
            self.file_preview_lbl.config(text=f"Could not read file: {e}", fg=ACCENT_RED)

    def update_unslate_preview(self):
        folder = self.unslate_dir.get().strip()
        if not folder or not os.path.isdir(folder):
            self.unslate_preview_lbl.config(text="No slated videos folder selected.", fg=TEXT_MUTED)
            return
        cnt = sum(1 for f in os.listdir(folder) if f.lower().endswith(VALID_EXTS) and not f.startswith("."))
        self.unslate_preview_lbl.config(
            text=f"Found {cnt} video file(s) in '{os.path.basename(folder)}' ready to un-slate & queue in AME",
            fg=ACCENT_YELLOW,
        )

    def run_label(self):
        tab = int(self.active_tab_var.get())
        if tab == 2:
            return "UN-SLATE & QUEUE IN AME"
        if tab == 3:
            return "MARRY SLATES + VIDEOS & QUEUE IN AME"
        if self.output_mode_var.get() == "slates_only":
            return "BUILD STANDALONE SLATES & QUEUE IN AME"
        return "GENERATE .AEP & QUEUE IN AME"

    # ------------------------------------------------------------------
    # Batch Slate Builder (Auto-Pull, Multi-Resolution & Retroactive Edit)
    # ------------------------------------------------------------------
    @staticmethod
    def _underscored(text):
        """Replace spaces with underscores '_'."""
        return re.sub(r"\s*_\s*|\s+", "_", text.strip()).strip("_") if text else ""

    def _current_campaign_fields(self):
        if not self.f_date.get().strip():
            self.f_date.set(today_yyyy_mm_dd())
        return {
            "agency": sanitize_single_line(self.f_agency.get()),
            "client": sanitize_single_line(self.f_client.get()),
            "date": self._underscored(self.f_date.get()) or today_yyyy_mm_dd(),
            "workspace": sanitize_single_line(self.f_workspace.get()),
            "audio": sanitize_single_line(self.f_audio.get()) or "STEREO",
            "copyright": sanitize_single_line(self.f_copyright.get()),
            "flame": "y" if self.f_flame.get() else "n",
        }

    @staticmethod
    def _make_slate_entry(shared, ad_id, title, trt, aspect, prev=None):
        prev = prev or {}
        asp = aspect if aspect in ASPECT_RESOLUTIONS else DEFAULT_ASPECT
        ws = shared["workspace"] or prev.get("workspace", prev.get("workspace_artist", ""))
        dt = shared["date"]
        return {
            "agency": shared["agency"] or prev.get("agency", ""),
            "client": shared["client"] or prev.get("client", ""),
            "title": title,
            "name": title,
            "id": ad_id,
            "ad-id": ad_id,
            "trt": trt or prev.get("trt", ""),
            "aspect": asp,
            "resolution": format_resolution_label(asp),
            "date": dt,
            "day": dt,
            "workspace": ws,
            "workspace_artist": ws,
            "audio": shared["audio"],
            "copyright": shared["copyright"] or prev.get("copyright", ""),
            "flame": shared["flame"],
            "nfa": prev.get("nfa", ""),
        }

    def populate_batch_from_videos(self, notify_if_empty=False):
        """Scan Master Videos folder and auto-populate Batch Slate Builder with
        Ad-ID, underscored Title, TRT (60/30/15/06), resolution(s), and today's YYYY_MM_DD date."""
        vdir = self.videos_dir.get().strip()
        if not vdir or not os.path.isdir(vdir):
            if notify_if_empty:
                self._alert("showwarning", "Master Videos Required", "Please select your Master Videos folder first.")
            return 0

        video_files = sorted(
            f for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        )
        if not video_files:
            if notify_if_empty:
                self._alert("showwarning", "No Videos Found", "No .mov, .mp4, or .mxf files found in Master Videos folder.")
            return 0

        if not self.f_date.get().strip():
            self.f_date.set(today_yyyy_mm_dd())

        shared = self._current_campaign_fields()
        existing_by_key = {
            (item.get("id", "").lower(), item.get("aspect", DEFAULT_ASPECT)): item
            for item in self.manual_batch_data
            if item.get("id")
        }
        existing_by_id = {item["id"].lower(): item for item in self.manual_batch_data if item.get("id")}
        pill_aspects = self.batch_res_pills.get_selected()

        new_batch = []
        for vf in video_files:
            ad_id, title, trt = parse_video_filename(vf)
            file_aspect = detect_aspect_from_text(vf)
            # If user selected multiple resolutions in the pill bar, generate all selected resolutions;
            # otherwise use the filename's detected aspect ratio (or the active resolution pill).
            if len(pill_aspects) > 1:
                target_aspects = pill_aspects
            else:
                target_aspects = [file_aspect or pill_aspects[0] or self.aspect_var.get()]

            for asp in target_aspects:
                prev = existing_by_key.get((ad_id.lower(), asp)) or existing_by_id.get(ad_id.lower(), {})
                new_batch.append(self._make_slate_entry(shared, ad_id, title, trt, asp, prev))

        self.manual_batch_data = new_batch
        self._refresh_tree()

        if new_batch:
            self._loading_row = True
            try:
                first = new_batch[0]
                self.f_id.set(first["id"])
                self.f_title.set(first["title"])
                self.f_trt.set(first["trt"])
            finally:
                self._loading_row = False

        return len(new_batch)

    def _sync_shared_fields_to_batch(self):
        """Keep Agency, Client, Workspace, Copyright, Date, Audio, and Flame synced
        across all queued batch items as the user types them in."""
        if self._loading_row or not self.manual_batch_data:
            return
        shared = self._current_campaign_fields()
        for item in self.manual_batch_data:
            item["agency"] = shared["agency"]
            item["client"] = shared["client"]
            item["date"] = shared["date"]
            item["day"] = shared["date"]
            item["workspace"] = shared["workspace"]
            item["workspace_artist"] = shared["workspace"]
            item["audio"] = shared["audio"]
            item["copyright"] = shared["copyright"]
            item["flame"] = shared["flame"]
        self._refresh_tree(preserve_selection=True)

    def _refresh_tree(self, preserve_selection=False):
        sel_indices = [self.tree.index(s) for s in self.tree.selection()] if preserve_selection else []
        for item in self.tree.get_children():
            self.tree.delete(item)
        children = []
        for slate in self.manual_batch_data:
            asp = slate.get("aspect", DEFAULT_ASPECT)
            res_lbl = format_resolution_label(asp)
            slate["aspect"] = asp
            slate["resolution"] = res_lbl
            cid = self.tree.insert(
                "",
                "end",
                values=(
                    slate["id"],
                    slate["title"],
                    res_lbl,
                    slate["trt"],
                    slate["date"],
                    slate["client"],
                    slate["agency"],
                ),
            )
            children.append(cid)
        for idx in sel_indices:
            if 0 <= idx < len(children):
                self.tree.selection_add(children[idx])
        self._update_batch_count()

    def _on_tree_tap(self, e):
        row_id = self.tree.identify_row(e.y)
        col_id = self.tree.identify_column(e.x)
        if not row_id:
            return
        idx = self.tree.index(row_id)
        self.tree.selection_set(row_id)
        # Single-tap on the RESOLUTION column (#3) immediately cycles that individual slate's resolution!
        if col_id == "#3" and 0 <= idx < len(self.manual_batch_data):
            cur_asp = self.manual_batch_data[idx].get("aspect", DEFAULT_ASPECT)
            next_asp = ASPECT_KEYS[(ASPECT_KEYS.index(cur_asp) + 1) % len(ASPECT_KEYS)] if cur_asp in ASPECT_KEYS else DEFAULT_ASPECT
            self.manual_batch_data[idx]["aspect"] = next_asp
            self.manual_batch_data[idx]["resolution"] = format_resolution_label(next_asp)
            self._refresh_tree(preserve_selection=True)
        self._on_tree_select()

    def _on_tree_select(self, _e=None):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        if 0 <= idx < len(self.manual_batch_data):
            row = self.manual_batch_data[idx]
            self._loading_row = True
            try:
                self.f_id.set(row.get("id", ""))
                self.f_title.set(row.get("title", ""))
                self.f_trt.set(row.get("trt", ""))
                # Show all resolutions currently queued for this selected row(s)
                sel_aspects = [
                    self.manual_batch_data[self.tree.index(s)].get("aspect", DEFAULT_ASPECT)
                    for s in selected
                    if 0 <= self.tree.index(s) < len(self.manual_batch_data)
                ]
                if sel_aspects:
                    self.batch_res_pills.set_selected(sel_aspects)
            finally:
                self._loading_row = False

    def cycle_selected_resolution(self):
        """Cycle the resolution (16x9 -> 1x1 -> 4x5 -> 9x16) of the currently selected slate(s)."""
        selected = self.tree.selection()
        if not selected:
            self._alert("showinfo", "Select a Slate", "Tap a slate row in the queue table first (or tap its RESOLUTION cell directly).")
            return
        new_aspects = []
        for s in selected:
            idx = self.tree.index(s)
            if 0 <= idx < len(self.manual_batch_data):
                cur_asp = self.manual_batch_data[idx].get("aspect", DEFAULT_ASPECT)
                next_asp = ASPECT_KEYS[(ASPECT_KEYS.index(cur_asp) + 1) % len(ASPECT_KEYS)] if cur_asp in ASPECT_KEYS else DEFAULT_ASPECT
                self.manual_batch_data[idx]["aspect"] = next_asp
                self.manual_batch_data[idx]["resolution"] = format_resolution_label(next_asp)
                new_aspects.append(next_asp)
        if new_aspects:
            self.batch_res_pills.set_selected(new_aspects)
        self._refresh_tree(preserve_selection=True)

    def apply_res_to_selected(self):
        """Retroactively change the resolution of selected slate(s), or expand selected spot(s)
        into multiple resolutions at once based on the active SLATE RES pills."""
        selected = self.tree.selection()
        target_aspects = self.batch_res_pills.get_selected()
        if not selected:
            self._alert(
                "showinfo",
                "Select a Slate",
                "Select one or more slates in the queue to change or expand their resolution(s).",
            )
            return

        sel_indices = sorted(self.tree.index(s) for s in selected if 0 <= self.tree.index(s) < len(self.manual_batch_data))
        if not sel_indices:
            return

        if len(target_aspects) == 1:
            # Retroactively switch each selected slate to the chosen single resolution
            new_asp = target_aspects[0]
            for idx in sel_indices:
                self.manual_batch_data[idx]["aspect"] = new_asp
                self.manual_batch_data[idx]["resolution"] = format_resolution_label(new_asp)
            self._refresh_tree(preserve_selection=True)
        else:
            # Expand each selected spot to have a slate for every selected resolution
            shared = self._current_campaign_fields()
            updated_list = []
            sel_set = set(sel_indices)
            for idx, item in enumerate(self.manual_batch_data):
                if idx in sel_set:
                    for asp in target_aspects:
                        updated_list.append(
                            self._make_slate_entry(
                                shared,
                                item.get("id", ""),
                                item.get("title", ""),
                                item.get("trt", ""),
                                asp,
                                item,
                            )
                        )
                else:
                    updated_list.append(item)
            self.manual_batch_data = updated_list
            self._refresh_tree()

    def add_to_batch(self):
        """Add or retroactively update a spot for one or multiple selected resolutions."""
        raw_id = sanitize_single_line(self.f_id.get())
        raw_title = self._underscored(self.f_title.get())
        raw_trt = sanitize_single_line(self.f_trt.get())

        if not raw_id or not raw_title:
            self._alert("showwarning", "Missing Info", "Ad-ID and Title are required to build a slate.")
            return

        if not raw_trt:
            _, _, detected_trt = parse_video_filename(f"{raw_id}_{raw_title}")
            raw_trt = detected_trt

        shared = self._current_campaign_fields()
        target_aspects = self.batch_res_pills.get_selected()
        selected_rows = self.tree.selection()

        # If a single row is selected in the table and 1 resolution is chosen, update that exact row in place
        # (allowing retroactive resolution fixes like 16x9 -> 4x5 or Ad-ID/Title edits on that row).
        if len(selected_rows) == 1 and len(target_aspects) == 1:
            sel_idx = self.tree.index(selected_rows[0])
            if 0 <= sel_idx < len(self.manual_batch_data):
                existing = self.manual_batch_data[sel_idx]
                if existing.get("id", "").lower() == raw_id.lower():
                    self.manual_batch_data[sel_idx] = self._make_slate_entry(
                        shared, raw_id, raw_title, raw_trt, target_aspects[0], existing
                    )
                    self._refresh_tree(preserve_selection=True)
                    return

        # Otherwise, add or update a slate entry for every selected resolution
        for asp in target_aspects:
            entry = self._make_slate_entry(shared, raw_id, raw_title, raw_trt, asp)
            updated = False
            for i, existing in enumerate(self.manual_batch_data):
                if (
                    existing.get("id", "").lower() == raw_id.lower()
                    and existing.get("aspect", DEFAULT_ASPECT) == asp
                ):
                    self.manual_batch_data[i] = entry
                    updated = True
                    break
            if not updated:
                self.manual_batch_data.append(entry)

        self._refresh_tree()
        self.f_title.set("")
        self.f_id.set("")
        self.f_trt.set("")

    def remove_from_batch(self):
        selected = self.tree.selection()
        for item in reversed(selected):
            idx = self.tree.index(item)
            if 0 <= idx < len(self.manual_batch_data):
                del self.manual_batch_data[idx]
            self.tree.delete(item)
        self._update_batch_count()

    def clear_batch(self):
        self.manual_batch_data.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._update_batch_count()

    def _update_batch_count(self):
        n = len(self.manual_batch_data)
        self.batch_count_lbl.config(text=f"{n} slate{'s' if n != 1 else ''} in queue")

    # ------------------------------------------------------------------
    # CSV / TSV + Master Videos Combining & Accurate Filename Renaming
    # ------------------------------------------------------------------
    def prompt_and_merge_csv_into_batch(self):
        """Let the user pick a CSV/TSV/TXT file (or use the currently selected one) and merge its
        canonical Titles, TRT, Client, Agency, Workspace, Copyright, and Flame flags into the Batch Builder queue."""
        cur = self.tsv_path.get().strip()
        if cur and os.path.isfile(cur):
            self.load_csv_into_batch_builder(csv_path=cur, switch_to_builder=False)
            return

        def _pick():
            reset_tk_mouse_state(self.root)
            chosen = filedialog.askopenfilename(
                parent=self.root,
                title="Select CSV / TSV / TXT Metadata File to Merge with Master Videos",
                filetypes=[("Metadata Files", "*.tsv *.csv *.txt"), ("All Files", "*.*")],
            )
            wake_macos_window(self.root)
            if chosen:
                self.tsv_path.set(chosen)
                self.load_csv_into_batch_builder(csv_path=chosen, switch_to_builder=False)

        run_after_mouse_up(self.root, _pick)

    def load_csv_into_batch_builder(self, csv_path=None, switch_to_builder=True):
        """Combine rows from a CSV/TSV/TXT metadata file with any Master Videos present in MASTER VIDEOS,
        populating the Batch Slate Builder queue with accurate canonical titles and detected video resolutions."""
        path = (csv_path or self.tsv_path.get()).strip()
        if not path or not os.path.isfile(path):
            self._alert("showwarning", "Metadata File Required", "Please select a .csv, .tsv, or .txt metadata file first.")
            return 0

        try:
            csv_rows = parse_metadata_file(path)
        except Exception as e:
            self._alert("showerror", "CSV Parse Error", f"Failed to read metadata file:\n{e}")
            return 0

        if not csv_rows:
            self._alert("showwarning", "Empty File", "No valid slate rows found in the selected metadata file.")
            return 0

        vdir = self.videos_dir.get().strip()
        all_videos = []
        if vdir and os.path.isdir(vdir):
            all_videos = sorted(
                vf for vf in os.listdir(vdir) if vf.lower().endswith(VALID_EXTS) and not vf.startswith(".")
            )

        # Populate shared campaign fields from the first CSV row that has them
        first_row = csv_rows[0]
        self._loading_row = True
        try:
            if first_row.get("agency"):
                self.f_agency.set(first_row["agency"])
            if first_row.get("client"):
                self.f_client.set(first_row["client"])
            if first_row.get("workspace"):
                self.f_workspace.set(first_row["workspace"])
            if first_row.get("copyright"):
                self.f_copyright.set(first_row["copyright"])
            if first_row.get("date"):
                self.f_date.set(self._underscored(first_row["date"]))
            if first_row.get("audio"):
                self.f_audio.set(first_row["audio"])
            if first_row.get("flame"):
                self.f_flame.set(first_row["flame"].lower() in ("y", "yes", "true", "1"))
        finally:
            self._loading_row = False

        shared = self._current_campaign_fields()
        combined_batch = []

        for row in csv_rows:
            ad_id = row.get("id") or row.get("ad-id") or ""
            csv_title = self._underscored(row.get("title") or row.get("name") or "")
            csv_trt = row.get("trt") or ""
            row_aspect = row.get("aspect") or detect_aspect_from_text(row.get("resolution", "")) or detect_aspect_from_text(csv_title)

            # Match against Master Videos if present to detect video aspect(s) or fill missing title/TRT
            matched_vids = [vf for vf in all_videos if ad_id and ad_id_matches(ad_id, vf)] if ad_id else []
            if matched_vids and not row_aspect:
                # Create an entry for each distinct aspect variant found in Master Videos for this Ad-ID
                seen_aspects = []
                for vf in matched_vids:
                    v_id, v_title, v_trt = parse_video_filename(vf)
                    vasp = detect_aspect_from_text(vf) or DEFAULT_ASPECT
                    if vasp not in seen_aspects:
                        seen_aspects.append(vasp)
                        entry = self._make_slate_entry(
                            shared,
                            ad_id or v_id,
                            csv_title or v_title,
                            csv_trt or v_trt,
                            vasp,
                            row,
                        )
                        combined_batch.append(entry)
            else:
                asp = row_aspect or DEFAULT_ASPECT
                if matched_vids and (not csv_title or not csv_trt):
                    _, v_title, v_trt = parse_video_filename(matched_vids[0])
                    csv_title = csv_title or v_title
                    csv_trt = csv_trt or v_trt
                entry = self._make_slate_entry(shared, ad_id, csv_title, csv_trt, asp, row)
                combined_batch.append(entry)

        self.manual_batch_data = combined_batch
        self._refresh_tree()
        if switch_to_builder:
            self.select(1)
        return len(combined_batch)

    def rename_master_videos_from_metadata(self):
        """Combine Master Videos with the loaded CSV/TSV metadata (or the Batch Slate Builder queue)
        to rename master video files on disk to their accurate canonical `<Ad-ID>_<Title>.<ext>` filenames."""
        vdir = self.videos_dir.get().strip()
        if not vdir or not os.path.isdir(vdir):
            self._alert("showwarning", "Master Videos Required", "Please select your Master Videos folder first.")
            return 0

        rows = []
        tsv = self.tsv_path.get().strip()
        if tsv and os.path.isfile(tsv):
            try:
                rows = parse_metadata_file(tsv)
            except Exception as e:
                self._alert("showerror", "CSV Parse Error", f"Could not read metadata file:\n{e}")
                return 0
        elif self.manual_batch_data:
            rows = [normalize_slate_row(item) for item in self.manual_batch_data]

        if not rows:
            self._alert(
                "showwarning",
                "Metadata Required",
                "Please select a CSV / TSV metadata file (or populate the Batch Slate Builder queue) first.",
            )
            return 0

        all_videos = sorted(
            vf for vf in os.listdir(vdir) if vf.lower().endswith(VALID_EXTS) and not vf.startswith(".")
        )
        if not all_videos:
            self._alert("showwarning", "No Videos Found", "No .mov, .mp4, or .mxf files found in Master Videos folder.")
            return 0

        id_counts = {}
        for r in rows:
            aid = (r.get("id") or r.get("ad-id") or "").lower()
            if aid:
                id_counts[aid] = id_counts.get(aid, 0) + 1

        renamed_log = []
        renamed_count = 0

        for r in rows:
            ad_id = r.get("id") or r.get("ad-id") or ""
            if not ad_id:
                continue
            target_aspect = r.get("aspect") or detect_aspect_from_text(r.get("resolution", ""))
            candidates = [vf for vf in all_videos if ad_id_matches(ad_id, vf)]
            if not candidates:
                continue

            chosen_vf = None
            if target_aspect:
                for vf in candidates:
                    if detect_aspect_from_text(vf) == target_aspect:
                        chosen_vf = vf
                        break
            if not chosen_vf:
                chosen_vf = candidates[0]

            _, ext = os.path.splitext(chosen_vf)
            multi_aspect = id_counts.get(ad_id.lower(), 0) > 1 or len(candidates) > 1
            file_aspect = target_aspect or detect_aspect_from_text(chosen_vf)
            new_stem = build_canonical_delivery_stem(
                r, target_aspect=file_aspect, include_aspect=multi_aspect, suffix=""
            )
            new_fname = f"{new_stem}{ext}"
            if new_fname == chosen_vf:
                continue

            src_path = os.path.join(vdir, chosen_vf)
            dst_path = os.path.join(vdir, new_fname)
            if os.path.exists(dst_path):
                continue

            try:
                os.rename(src_path, dst_path)
                all_videos = [new_fname if vf == chosen_vf else vf for vf in all_videos]
                renamed_log.append(f"{chosen_vf}  →  {new_fname}")
                renamed_count += 1
            except OSError as e:
                renamed_log.append(f"[ERROR] {chosen_vf}: {e}")

        self.update_file_preview()
        if renamed_count > 0:
            preview = "\n".join(renamed_log[:12])
            self._alert(
                "showinfo",
                "Master Videos Renamed",
                f"Renamed {renamed_count} master video file(s) to match canonical CSV metadata:\n\n{preview}",
            )
        else:
            self._alert(
                "showinfo",
                "No Renames Needed",
                "All matched master video files already have accurate canonical filenames (or no Ad-ID matches needed renaming).",
            )
        return renamed_count

    # ------------------------------------------------------------------
    # Marry Existing Slates + Existing Master Videos (Tab 3)
    # ------------------------------------------------------------------
    def _scan_marry_pairs(self):
        """Scan `self.marry_slates_dir` and `self.videos_dir` (plus optional `self.marry_csv_path` or `self.tsv_path`)
        and pair each existing slate file with its matching master video by Ad-ID (and aspect ratio)."""
        sdir = self.marry_slates_dir.get().strip()
        vdir = self.videos_dir.get().strip()
        if not sdir or not os.path.isdir(sdir) or not vdir or not os.path.isdir(vdir):
            return []

        slate_files = sorted(
            f for f in os.listdir(sdir) if f.lower().endswith(SLATE_ASSET_EXTS) and not f.startswith(".")
        )
        video_files = sorted(
            f for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        )
        if not slate_files or not video_files:
            return []

        # Optional CSV/TSV lookup by Ad-ID for canonical output naming
        csv_by_id = {}
        csv_path = self.marry_csv_path.get().strip() or self.tsv_path.get().strip()
        if csv_path and os.path.isfile(csv_path):
            try:
                for r in parse_metadata_file(csv_path):
                    aid = (r.get("id") or r.get("ad-id") or "").lower()
                    if aid:
                        csv_by_id[aid] = r
            except Exception:
                pass

        pairs = []
        used_slate_Video_keys = set()

        for sf in slate_files:
            s_stem = re.sub(r"(?i)[_\-\s]*slate[ds]?$", "", os.path.splitext(sf)[0]).strip("_- ")
            s_id, s_title, _ = parse_video_filename(s_stem)
            s_aspect = detect_aspect_from_text(sf)
            if not s_id:
                continue

            # Find master videos matching this slate's Ad-ID
            candidates = [vf for vf in video_files if ad_id_matches(s_id, vf)]
            if not candidates:
                continue

            matched_vf = None
            if s_aspect:
                for vf in candidates:
                    if detect_aspect_from_text(vf) == s_aspect:
                        matched_vf = vf
                        break
            if not matched_vf:
                matched_vf = candidates[0]

            pair_key = (sf, matched_vf)
            if pair_key in used_slate_Video_keys:
                continue
            used_slate_Video_keys.add(pair_key)

            v_id, v_title, _ = parse_video_filename(matched_vf)
            eff_aspect = s_aspect or detect_aspect_from_text(matched_vf)
            csv_row = csv_by_id.get(s_id.lower()) or csv_by_id.get(v_id.lower())

            if csv_row:
                out_stem = build_canonical_delivery_stem(
                    csv_row, target_aspect=eff_aspect, include_aspect=bool(eff_aspect), suffix="Slated"
                )
            else:
                base_stem = os.path.splitext(matched_vf)[0]
                clean_base = re.sub(r"(?i)[_\-\s]*slated$", "", base_stem).strip("_- ")
                out_stem = f"{clean_base}_Slated"

            out_name = f"{out_stem}.mov"
            pairs.append(
                {
                    "id": s_id,
                    "slate_name": sf,
                    "slate_path": os.path.join(sdir, sf),
                    "video_name": matched_vf,
                    "video_path": os.path.join(vdir, matched_vf),
                    "output_name": out_name,
                    "aspect": eff_aspect or DEFAULT_ASPECT,
                }
            )

        return pairs

    def update_marry_preview(self):
        if not hasattr(self, "marry_tree"):
            return
        for item in self.marry_tree.get_children():
            self.marry_tree.delete(item)

        sdir = self.marry_slates_dir.get().strip()
        vdir = self.videos_dir.get().strip()
        if not sdir or not os.path.isdir(sdir) or not vdir or not os.path.isdir(vdir):
            self.marry_pairs_data = []
            self.marry_status_lbl.config(
                text="Select Existing Slates folder and Master Videos folder (above) to preview pairs.",
                fg=TEXT_MUTED,
            )
            return

        pairs = self._scan_marry_pairs()
        self.marry_pairs_data = pairs
        for p in pairs:
            self.marry_tree.insert(
                "",
                "end",
                values=(p["id"], p["slate_name"], p["video_name"], p["output_name"]),
            )
        self.marry_status_lbl.config(
            text=f"Matched {len(pairs)} Slate ↔ Master Video pair(s) ready to marry in AE + AME",
            fg=ACCENT_YELLOW if pairs else ACCENT_RED,
        )

    def process_marry(self, pairs, slates_dir, videos_dir, settings):
        output_dir = os.path.join(videos_dir, "MARRIED_DELIVERY")
        os.makedirs(output_dir, exist_ok=True)
        aep_marry_path = os.path.join(output_dir, "SuperJoy_Married_Slates.aep")
        beep_path = os.path.join(output_dir, "_2pop_1kHz_1frame.wav")
        jsx_path = os.path.join(output_dir, "_temp_ae_marry.jsx")
        log_path = os.path.join(output_dir, "Marry_Results_Log.txt")

        create_beep_wav(beep_path)

        marry_jobs = []
        log_lines = [
            "SUPERJOY AE/AME MARRY EXISTING SLATES + VIDEOS LOG",
            "=" * 52,
            f"Slates Folder: {slates_dir}",
            f"Videos Folder: {videos_dir}",
            f"Output Folder: {output_dir}",
            "",
        ]
        for p in pairs:
            final_out = os.path.join(output_dir, p["output_name"])
            marry_jobs.append(
                {
                    "id": p["id"],
                    "slate_path": p["slate_path"],
                    "video_path": p["video_path"],
                    "final_output": final_out,
                    "comp_name": os.path.splitext(p["output_name"])[0],
                }
            )
            log_lines.append(f"[MARRIED] {p['slate_name']} + {p['video_name']} -> {p['output_name']}")

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except OSError:
            pass

        self.write_marry_jsx(jsx_path, marry_jobs, aep_marry_path, beep_path, settings)

        ae_target = resolve_ae_applescript_target()
        applescript = f'''
        on run argv
            set jsxPath to POSIX file (item 1 of argv)
            tell {ae_target}
                activate
                DoScriptFile jsxPath
            end tell
        end run
        '''

        try:
            subprocess.run(
                ["osascript", "-e", applescript, jsx_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            msg = (
                f"Married {len(marry_jobs)} existing slate(s) + master video(s) and queued in AME!\n\n"
                f"Editable Project:\n{aep_marry_path}\n\n"
                f"Output Folder:\n{output_dir}"
            )
            self.root.after(0, lambda: self._alert("showinfo", "Marry Complete", msg))
        except subprocess.CalledProcessError as e:
            err = (e.stderr or str(e)).strip()
            self.root.after(
                0,
                lambda: self._alert("showerror", "AE/AME Error", f"Failed to execute Marry script:\n{err}"),
            )
        except Exception as e:
            self.root.after(
                0,
                lambda: self._alert("showerror", "AE/AME Error", f"Failed to execute Marry script:\n{str(e)}"),
            )
        finally:
            self.root.after(0, self.reset_ui)

    def write_marry_jsx(self, path, marry_jobs, aep_path, beep_path, settings):
        jobs_json = json.dumps(marry_jobs)
        settings_json = json.dumps(settings)
        jsx_code = f"""
        var jobs = {jobs_json};
        var cfg = {settings_json};
        var beepFile = new File({json.dumps(beep_path)});

        try {{
            if (app.project) {{
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            }}
        }} catch (eClose) {{}}

        app.newProject();
        app.beginUndoGroup("Batch Marry Existing Slates + Videos");

        var masterFolder = app.project.items.addFolder("Married Slated Comps");
        var assetsFolder = app.project.items.addFolder("Imported Slates & Masters");
        assetsFolder.parentFolder = masterFolder;

        var beepItem = null;
        if (beepFile.exists) {{
            beepItem = app.project.importFile(new ImportOptions(beepFile));
            beepItem.parentFolder = assetsFolder;
        }}

        for (var i = 0; i < jobs.length; i++) {{
            var job = jobs[i];
            var slateFile = new File(job.slate_path);
            var vidFile = new File(job.video_path);
            if (!slateFile.exists || !vidFile.exists) continue;

            var slateItem = app.project.importFile(new ImportOptions(slateFile));
            slateItem.parentFolder = assetsFolder;
            var vidItem = app.project.importFile(new ImportOptions(vidFile));
            vidItem.parentFolder = assetsFolder;

            var compW = vidItem.width > 0 ? vidItem.width : (slateItem.width > 0 ? slateItem.width : cfg.width);
            var compH = vidItem.height > 0 ? vidItem.height : (slateItem.height > 0 ? slateItem.height : cfg.height);
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : (slateItem.frameRate > 0 ? slateItem.frameRate : cfg.fps);
            var totalDuration = 7.0 + vidItem.duration;

            var masterComp = app.project.items.addComp(job.comp_name, compW, compH, 1.0, totalDuration, compFps);
            masterComp.parentFolder = masterFolder;
            masterComp.displayStartTime = 3593.0; // 00:59:53:00

            var blackSolid = masterComp.layers.addSolid([0,0,0], "2s_Black", compW, compH, 1.0, 2.0);
            blackSolid.startTime = 5.0;

            var slateLayer = masterComp.layers.add(slateItem);
            slateLayer.startTime = 0.0;
            // If the pre-rendered slate clip is >= 5.04s (already includes 2-pop at 5.0s) or >= 7.0s (includes black + 2-pop),
            // preserve its native 2-pop; otherwise trim still/5s clip at 5.0s and insert the 1-frame 1kHz 2-pop at 5.0s.
            if (slateItem.duration && slateItem.duration >= 5.0 + masterComp.frameDuration) {{
                slateLayer.outPoint = Math.min(7.0, slateItem.duration);
            }} else {{
                slateLayer.outPoint = 5.0;
                if (beepItem) {{
                    var beepLayer = masterComp.layers.add(beepItem);
                    beepLayer.startTime = 5.0;
                    beepLayer.outPoint = 5.0 + masterComp.frameDuration;
                }}
            }}

            if (slateItem.width > 0 && slateItem.height > 0 && (slateItem.width !== compW || slateItem.height !== compH)) {{
                var sx = (compW / slateItem.width) * 100.0;
                var sy = (compH / slateItem.height) * 100.0;
                var sUniform = Math.min(sx, sy);
                slateLayer.property("Scale").setValue([sUniform, sUniform]);
            }}

            var vidLayer = masterComp.layers.add(vidItem);
            vidLayer.startTime = 7.0;
            vidLayer.property("Scale").setValue([100, 100]);

            var rqItem = app.project.renderQueue.items.add(masterComp);
            var outMod = rqItem.outputModule(1);
            outMod.file = new File(job.final_output);
        }}

        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        app.project.renderQueue.queueInAME(false);
        app.endUndoGroup();
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsx_code)

    # ------------------------------------------------------------------
    # Workflow Execution
    # ------------------------------------------------------------------
    def execute_workflow_thread(self):
        tab = int(self.active_tab_var.get())

        fps = parse_fps(self.fps_var.get())
        if fps is None:
            self._alert("showerror", "Error", "Invalid frame rate. Pick a preset or enter a number between 1 and 120.")
            return
        width, height = ASPECT_RESOLUTIONS[self.aspect_var.get()]
        self.render_settings = {"fps": fps, "width": width, "height": height}

        if tab == 2:
            folder = self.unslate_dir.get().strip()
            if not folder or not os.path.isdir(folder):
                self._alert("showerror", "Error", "Please select a folder of slated videos.")
                return
            self.btn_run.config(text="PROCESSING...", state="disabled")
            threading.Thread(
                target=self.process_unslate, args=(folder, self.render_settings), daemon=True
            ).start()
            return

        if tab == 3:
            sdir = self.marry_slates_dir.get().strip()
            vdir = self.videos_dir.get().strip()
            if not sdir or not os.path.isdir(sdir):
                self._alert("showerror", "Error", "Please select your Existing Slates folder.")
                return
            if not vdir or not os.path.isdir(vdir):
                self._alert("showerror", "Error", "Please select your Master Videos folder in the top panel.")
                return
            pairs = self._scan_marry_pairs()
            if not pairs:
                self._alert("showwarning", "No Pairs Found", "No matching Ad-ID pairs found between Existing Slates and Master Videos.")
                return
            self.btn_run.config(text="PROCESSING...", state="disabled")
            threading.Thread(
                target=self.process_marry, args=(pairs, sdir, vdir, self.render_settings), daemon=True
            ).start()
            return

        template_dir = self.template_dir.get().strip()
        videos_dir = self.videos_dir.get().strip()
        slates_only = self.output_mode_var.get() == "slates_only"

        if not template_dir:
            self._alert("showerror", "Error", "Please select your Slate Template (.aep).")
            return
        if not slates_only and (not videos_dir or not os.path.isdir(videos_dir)):
            self._alert(
                "showerror",
                "Master Videos Required",
                "Please select your Master Videos folder, or switch BUILD OUTPUT MODE to 'Standalone Slates Only'.",
            )
            return

        batch_jobs_data = []
        if tab == 0:
            tsv = self.tsv_path.get().strip()
            if not tsv:
                self._alert("showerror", "Error", "Please select a metadata file.")
                return
            try:
                batch_jobs_data = parse_metadata_file(tsv)
            except Exception as e:
                self._alert("showerror", "Error", f"Failed to parse file:\n{str(e)}")
                return
            if not batch_jobs_data:
                self._alert("showerror", "Error", "Metadata file contains no valid slate rows.")
                return
        else:
            # Auto-pull from Master Videos if queue is empty when running from Batch Slate Builder
            if not self.manual_batch_data and videos_dir and os.path.isdir(videos_dir):
                self.populate_batch_from_videos(notify_if_empty=False)
            if not self.manual_batch_data:
                self._alert(
                    "showerror",
                    "Empty Queue",
                    "Your batch queue is empty. Add spots manually, load a CSV/TSV, or select a Master Videos folder.",
                )
                return
            self._sync_shared_fields_to_batch()
            batch_jobs_data = [normalize_slate_row(item) for item in self.manual_batch_data]

        self.btn_run.config(text="PROCESSING...", state="disabled")
        threading.Thread(
            target=self.process_batch,
            args=(batch_jobs_data, template_dir, videos_dir, slates_only),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Un-Slate (After Effects + Adobe Media Encoder 7.0s Head Trim)
    # ------------------------------------------------------------------
    def process_unslate(self, folder, settings=None):
        settings = settings or getattr(self, "render_settings", {"fps": DEFAULT_FPS, "width": 1920, "height": 1080})
        out_dir = os.path.join(folder, "UNSLATED")
        os.makedirs(out_dir, exist_ok=True)
        files = sorted(
            f for f in os.listdir(folder) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        )
        if not files:
            self.root.after(0, lambda: self._alert("showwarning", "No Videos Found", "No video files found in the selected folder."))
            self.root.after(0, self.reset_ui)
            return

        aep_unslate_path = os.path.join(out_dir, "SuperJoy_Unslate_Project.aep")
        jsx_path = os.path.join(out_dir, "_temp_ae_unslate.jsx")
        log_path = os.path.join(out_dir, "Unslate_Log.txt")

        unslate_jobs = []
        log_lines = [
            "SUPERJOY AE/AME UN-SLATE (7.0s HEAD TRIM) LOG",
            "=" * 48,
            f"Source Folder: {folder}",
            f"Output Folder: {out_dir}",
            f"Editable AEP:  {aep_unslate_path}",
            f"Head Trim:     {UNSLATE_SECONDS:.1f}s (5.0s Slate + 2.0s Black/2-Pop)",
            "",
        ]

        for fname in files:
            src = os.path.join(folder, fname)
            stem, ext = os.path.splitext(fname)
            clean_stem = re.sub(r"(?i)[_\-\s]*slated$", "", stem).strip("_- ") or f"{stem}_Unslated"
            dst_name = f"{clean_stem}{ext}" if clean_stem != stem else fname
            dst = os.path.join(out_dir, dst_name)
            unslate_jobs.append(
                {
                    "video_path": src,
                    "final_output": dst,
                    "comp_name": f"{clean_stem}_UNSLATED",
                }
            )
            log_lines.append(f"[QUEUED] {fname} -> {dst_name} (trim first {UNSLATE_SECONDS:.1f}s)")

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except OSError:
            pass

        self.write_unslate_jsx(jsx_path, unslate_jobs, aep_unslate_path, settings)

        ae_target = resolve_ae_applescript_target()
        applescript = f'''
        on run argv
            set jsxPath to POSIX file (item 1 of argv)
            tell {ae_target}
                activate
                DoScriptFile jsxPath
            end tell
        end run
        '''

        try:
            subprocess.run(
                ["osascript", "-e", applescript, jsx_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            msg = (
                f"Queued {len(unslate_jobs)} un-slated spot(s) in Adobe Media Encoder!\n\n"
                f"Editable Project (for manual checks/fixes):\n{aep_unslate_path}\n\n"
                f"Output Folder:\n{out_dir}"
            )
            self.root.after(0, lambda: self._alert("showinfo", "Un-Slate Queued in AME", msg))
        except subprocess.CalledProcessError as e:
            err = (e.stderr or str(e)).strip()
            self.root.after(
                0,
                lambda: self._alert("showerror", "AE/AME Error", f"Failed to execute Un-Slate script:\n{err}"),
            )
        except Exception as e:
            self.root.after(
                0,
                lambda: self._alert("showerror", "AE/AME Error", f"Failed to execute Un-Slate script:\n{str(e)}"),
            )
        finally:
            self.root.after(0, self.reset_ui)

    def write_unslate_jsx(self, path, unslate_jobs, aep_path, settings):
        jobs_json = json.dumps(unslate_jobs)
        settings_json = json.dumps(settings)
        trim_sec = float(UNSLATE_SECONDS)
        jsx_code = f"""
        var jobs = {jobs_json};
        var cfg = {settings_json};
        var trimSeconds = {trim_sec};

        try {{
            if (app.project) {{
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            }}
        }} catch (eClose) {{}}

        app.newProject();
        app.beginUndoGroup("Batch Un-Slate (7.0s Head Trim)");

        var skipped = [];
        var rootFolder = app.project.items.addFolder("Unslated Comps");
        var sourceFolder = app.project.items.addFolder("Slated Source Footage");
        sourceFolder.parentFolder = rootFolder;

        for (var i = 0; i < jobs.length; i++) {{
            var job = jobs[i];
            var srcFile = new File(job.video_path);
            if (!srcFile.exists) {{
                skipped.push(job.video_path + " (file not found)");
                continue;
            }}

            var ioVid = new ImportOptions(srcFile);
            var vidItem = app.project.importFile(ioVid);
            vidItem.parentFolder = sourceFolder;

            if (vidItem.duration <= trimSeconds) {{
                skipped.push(vidItem.name + " (duration " + vidItem.duration.toFixed(2) + "s <= " + trimSeconds + "s trim)");
                continue;
            }}

            var compW = vidItem.width > 0 ? vidItem.width : cfg.width;
            var compH = vidItem.height > 0 ? vidItem.height : cfg.height;
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : cfg.fps;
            var cleanDuration = vidItem.duration - trimSeconds;

            var comp = app.project.items.addComp(job.comp_name, compW, compH, 1.0, cleanDuration, compFps);
            comp.parentFolder = rootFolder;
            comp.displayStartTime = 3600.0; // 01:00:00:00 picture start

            var vidLayer = comp.layers.add(vidItem);
            // Shift layer start to -7.0s so frame at 7.0s of slated source lands at 0.0s (01:00:00:00) of comp.
            // Full footage remains non-destructively intact in timeline for retroactive slip/trim adjustments!
            vidLayer.startTime = -trimSeconds;
            vidLayer.inPoint = 0.0;
            vidLayer.outPoint = cleanDuration;
            vidLayer.property("Scale").setValue([100, 100]);

            var rqItem = app.project.renderQueue.items.add(comp);
            var outMod = rqItem.outputModule(1);
            outMod.file = new File(job.final_output);
        }}

        if (skipped.length) {{
            alert("Skipped during Un-Slate:\\n" + skipped.join("\\n"));
        }}

        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        app.project.renderQueue.queueInAME(false);
        app.endUndoGroup();
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsx_code)

    # ------------------------------------------------------------------
    # Slate (After Effects + AME Queue — Supports Slated Masters & Standalone Slates Only)
    # ------------------------------------------------------------------
    def process_batch(self, batch_data, template_dir, videos_dir, slates_only=False):
        templates = find_templates(template_dir)
        if not templates:
            self.root.after(
                0,
                lambda: self._alert(
                    "showerror",
                    "Error",
                    "No valid .aep Slate Template (or PSD templates) found at the selected template path.",
                ),
            )
            self.root.after(0, self.reset_ui)
            return

        # Determine base output directory even when building Standalone Slates Only without a Master Videos folder
        if videos_dir and os.path.isdir(videos_dir):
            base_out_parent = videos_dir
        elif self.tsv_path.get().strip() and os.path.isfile(self.tsv_path.get().strip()):
            base_out_parent = os.path.dirname(self.tsv_path.get().strip())
        elif os.path.isfile(template_dir):
            base_out_parent = os.path.dirname(template_dir)
        else:
            base_out_parent = template_dir

        subfolder_name = "STANDALONE_SLATES" if slates_only else "SLATED_DELIVERY"
        output_dir = os.path.join(base_out_parent, subfolder_name)
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, "Slating_Results_Log.txt")
        aep_master_path = os.path.join(
            output_dir, "SuperJoy_Standalone_Slates.aep" if slates_only else "SuperJoy_Master_Slates.aep"
        )
        beep_path = os.path.join(output_dir, "_2pop_1kHz_1frame.wav")
        log_entries = [
            f"SUPERJOY AE/AME {'STANDALONE SLATES' if slates_only else 'SLATING'} RESULTS LOG",
            "=" * 48,
            "",
        ]

        ae_jobs = []
        success_count = 0
        error_count = 0

        # Count occurrences per Ad-ID so multi-resolution exports get distinct filenames
        id_counts = {}
        for d in batch_data:
            aid = d.get("id", d.get("ad-id", "")).lower()
            id_counts[aid] = id_counts.get(aid, 0) + 1

        all_videos = []
        if not slates_only and videos_dir and os.path.isdir(videos_dir):
            all_videos = sorted(
                vf for vf in os.listdir(videos_dir) if vf.lower().endswith(VALID_EXTS) and not vf.startswith(".")
            )

        for raw_data in batch_data:
            data = normalize_slate_row(raw_data)
            ad_id = data.get("id", data.get("ad-id", ""))
            title = data.get("title", data.get("name", ""))
            flame_flag = data.get("flame", "").lower() in ("y", "yes", "true", "1")
            explicit_aspect = data.get("aspect") or detect_aspect_from_text(data.get("resolution", ""))
            target_aspect = explicit_aspect if explicit_aspect in ASPECT_RESOLUTIONS else None
            multi_aspect = id_counts.get(ad_id.lower(), 0) > 1

            if slates_only:
                asp = target_aspect or self.aspect_var.get() or DEFAULT_ASPECT
                tw, th = ASPECT_RESOLUTIONS.get(asp, (1920, 1080))
                out_stem = build_canonical_delivery_stem(
                    data, target_aspect=asp, include_aspect=multi_aspect, suffix="Slate"
                )
                final_output_file = os.path.join(output_dir, f"{out_stem}.mov")
                job_entry = {
                    "video_path": "",
                    "slate_only": True,
                    "final_output": final_output_file,
                    "flame": flame_flag,
                    "text_data": data,
                    "aspect": asp,
                    "width": tw,
                    "height": th,
                }
                ae_jobs.append(job_entry)
                log_entries.append(
                    f"[SUCCESS] Standalone Slate {ad_id} [{format_resolution_label(asp)}] -> {os.path.basename(final_output_file)}"
                )
                success_count += 1
                continue

            # Prefer a master video that matches both Ad-ID and the target aspect token, falling back to Ad-ID match
            candidates = [vf for vf in all_videos if ad_id_matches(ad_id, vf)]
            matched_video = None
            if candidates:
                if target_aspect:
                    for vf in candidates:
                        if detect_aspect_from_text(vf) == target_aspect:
                            matched_video = os.path.join(videos_dir, vf)
                            break
                if not matched_video:
                    matched_video = os.path.join(videos_dir, candidates[0])

            if not matched_video:
                log_entries.append(
                    f"[ERROR] ID: {ad_id} | Title: {title} | No strict filename match found in video folder."
                )
                error_count += 1
                continue

            out_stem = build_canonical_delivery_stem(
                data, target_aspect=target_aspect, include_aspect=multi_aspect, suffix="Slated"
            )
            final_output_file = os.path.join(output_dir, f"{out_stem}.mov")

            job_entry = {
                "video_path": matched_video,
                "slate_only": False,
                "final_output": final_output_file,
                "flame": flame_flag,
                "text_data": data,
            }
            if target_aspect:
                tw, th = ASPECT_RESOLUTIONS[target_aspect]
                job_entry["aspect"] = target_aspect
                job_entry["width"] = tw
                job_entry["height"] = th

            ae_jobs.append(job_entry)
            res_note = f" [{format_resolution_label(target_aspect)}]" if target_aspect else ""
            log_entries.append(
                f"[SUCCESS] Paired {ad_id}{res_note} -> {os.path.basename(matched_video)} => {os.path.basename(final_output_file)}"
            )
            success_count += 1

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log_entries))

        if not ae_jobs:
            self.root.after(
                0,
                lambda: self._alert(
                    "showwarning", "Warning", "No valid matches found to process. Check the results log."
                ),
            )
            self.root.after(0, self.reset_ui)
            return

        create_beep_wav(beep_path)  # long enough for any rate; JSX trims it to 1 frame
        jsx_path = os.path.join(output_dir, "_temp_ae_build.jsx")
        self.write_jsx(jsx_path, ae_jobs, aep_master_path, beep_path, self.render_settings, templates)

        # Target installed After Effects app bundle dynamically (supports AE 2024/2025/2026)
        ae_target = resolve_ae_applescript_target()
        applescript = f'''
        on run argv
            set jsxPath to POSIX file (item 1 of argv)
            tell {ae_target}
                activate
                DoScriptFile jsxPath
            end tell
        end run
        '''

        try:
            subprocess.run(
                ["osascript", "-e", applescript, jsx_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            mode_desc = "Standalone Slates Project" if slates_only else "Master Slated Project"
            msg = (
                f"Successfully generated {mode_desc} ({success_count} slate(s)) and queued in AME!\n\n"
                f"Review log at:\n{log_path}"
            )
            self.root.after(0, lambda: self._alert("showinfo", "Complete", msg))
        except subprocess.CalledProcessError as e:
            err = (e.stderr or str(e)).strip()
            self.root.after(
                0,
                lambda: self._alert("showerror", "AE Error", f"Failed to execute After Effects script:\n{err}"),
            )
        except Exception as e:
            self.root.after(
                0,
                lambda: self._alert(
                    "showerror", "AE Error", f"Failed to execute After Effects script:\n{str(e)}"
                ),
            )
        finally:
            self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_run.config(text=self.run_label(), state="normal")
        reset_tk_mouse_state(self.root)

    def write_jsx(self, path, jobs, aep_path, beep_path, settings, templates):
        jobs_json = json.dumps(jobs)
        settings_json = json.dumps(settings)
        templates_json = json.dumps(templates)
        jsx_code = f"""
        var jobs = {jobs_json};
        var cfg = {settings_json};
        var templates = {templates_json};
        var beepFile = new File({json.dumps(beep_path)});

        // Map a video size to the nearest standard aspect key.
        function pickAspect(w, h) {{
            var r = w / h;
            var keys = {{"16x9": 16/9, "1x1": 1.0, "4x5": 0.8, "9x16": 9/16}};
            var best = null, bestDiff = 1e9;
            for (var k in keys) {{
                var d = Math.abs(r - keys[k]);
                if (d < bestDiff) {{ bestDiff = d; best = k; }}
            }}
            return best;
        }}

        // Flatten any accidental CR/LF/tabs to a single line so slate text never wraps onto a second row.
        function cleanLine(val) {{
            if (val === undefined || val === null) return "";
            return String(val).replace(/[\\r\\n\\t]+/g, " ").replace(/\\s{{2,}}/g, " ").replace(/^\\s+|\\s+$/g, "");
        }}

        // Resolve which dynamic field a TextLayer represents without ever touching the static left-column labels!
        function resolveFieldValue(layer, td) {{
            var rawName = String(layer.name);
            var trimmed = rawName.replace(/^\\s+|\\s+$/g, "");
            var lower = trimmed.toLowerCase();

            // Never overwrite static left-column label layers (which lack a '^' prefix)
            var staticLabels = {{
                "agency": true, "client": true, "title": true, "id": true, "trt": true,
                "date": true, "workspace": true, "audio": true, "copyright": true
            }};
            if (trimmed.charAt(0) !== "^" && staticLabels[lower]) {{
                return null;
            }}

            if (trimmed.charAt(0) === "^") {{
                var key = lower.substring(1).replace(/^\\s+|\\s+$/g, "");
                if (key === "nfa") {{
                    return cleanLine(td["nfa"] || "");
                }}
                if (key === "agency") {{
                    return cleanLine(td["agency"]);
                }}
                if (key === "client") {{
                    return cleanLine(td["client"]);
                }}
                if (key === "title" || key === "name") {{
                    return cleanLine(td["title"] || td["name"]);
                }}
                if (key === "ad-id" || key === "ad_id" || key === "adid" || key === "id") {{
                    return cleanLine(td["id"] || td["ad-id"]);
                }}
                if (key === "trt") {{
                    return cleanLine(td["trt"]);
                }}
                if (key === "date" || key === "day") {{
                    return cleanLine(td["date"] || td["day"]);
                }}
                if (key === "workspace_artist" || key === "workspace") {{
                    return cleanLine(td["workspace"] || td["workspace_artist"]);
                }}
                if (key === "audio") {{
                    return cleanLine(td["audio"] || "STEREO");
                }}
                if (key === "copyright") {{
                    return cleanLine(td["copyright"]);
                }}
                if (td[key] !== undefined) {{
                    return cleanLine(td[key]);
                }}
            }}

            // Match the Agency & Audio value layers in sj_Slates From Spreadsheet_Template_005.aep
            if (lower.indexOf("martin agency") !== -1 || layer.index === 2) {{
                return cleanLine(td["agency"]);
            }}
            if (lower === "stereo" || layer.index === 9) {{
                return cleanLine(td["audio"] || "STEREO");
            }}
            return null;
        }}

        // Set a TextLayer to a single line and auto-fit its font size so long titles/IDs never wrap or overflow the red grid.
        function applySingleLineText(layer, newText, maxWidthPx) {{
            var textProp = layer.property("Source Text");
            if (!textProp) return;
            try {{
                if (textProp.canSetExpression && textProp.expressionEnabled) {{
                    textProp.expressionEnabled = false;
                }}
            }} catch (eExpr) {{}}

            var textDoc = textProp.value;
            var baseFontSize = textDoc.fontSize || 27;

            try {{
                if (textDoc.boxText) {{
                    textDoc.boxTextSize = [4000, 300];
                }}
            }} catch (eBox) {{}}

            textDoc.text = newText;
            textProp.setValue(textDoc);

            if (newText && newText.length > 0 && maxWidthPx > 0) {{
                try {{
                    var rect = layer.sourceRectAtTime(2.0, false);
                    if (rect && rect.width > maxWidthPx) {{
                        var ratio = maxWidthPx / rect.width;
                        var newSize = Math.max(12, Math.floor(baseFontSize * ratio * 0.98));
                        textDoc = textProp.value;
                        textDoc.fontSize = newSize;
                        try {{
                            textDoc.baselineShift = -Math.round((baseFontSize - newSize) * 0.35);
                        }} catch (eBase) {{}}
                        textProp.setValue(textDoc);
                    }}
                }} catch (eFit) {{}}
            }}
        }}

        // Populate all dynamic text and Flame layers inside a slate composition.
        function populateSlateComp(slateComp, job, solidComps) {{
            var td = job.text_data || {{}};
            var maxLineW = (slateComp.width >= 1920) ? 630 : 620;

            for (var l = 1; l <= slateComp.numLayers; l++) {{
                var layer = slateComp.layer(l);
                var lName = String(layer.name).toLowerCase();

                if (lName.indexOf("flame") !== -1) {{
                    layer.enabled = job.flame ? true : false;
                    var replacement = job.flame ? solidComps["y"] : solidComps["n"];
                    if (replacement && layer.replaceSource) {{
                        try {{
                            layer.replaceSource(replacement, false);
                            layer.enabled = true;
                        }} catch (eRep) {{}}
                    }}
                    continue;
                }}

                if (layer instanceof TextLayer) {{
                    var val = resolveFieldValue(layer, td);
                    if (val !== null) {{
                        applySingleLineText(layer, val, maxLineW);
                    }}
                }}
            }}
        }}

        try {{
            if (app.project) {{
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            }}
        }} catch (eClose) {{}}

        var templateComps = {{}};
        var solidComps = {{"y": null, "n": null}};
        var usingAepTemplate = (templates["_aep"] !== undefined && templates["_aep"] !== "");

        if (usingAepTemplate) {{
            var tplAepFile = new File(templates["_aep"]);
            app.open(tplAepFile);
            for (var it = 1; it <= app.project.numItems; it++) {{
                var item = app.project.item(it);
                if (item instanceof CompItem) {{
                    if (item.name === "16x9" || item.name === "1x1" || item.name === "4x5" || item.name === "9x16" || item.name === "2x3") {{
                        templateComps[item.name] = item;
                    }} else if (item.name.toLowerCase() === "y") {{
                        solidComps["y"] = item;
                    }} else if (item.name.toLowerCase() === "n") {{
                        solidComps["n"] = item;
                    }}
                }}
            }}
        }} else {{
            app.newProject();
        }}

        app.beginUndoGroup("Batch Slate Generation");

        var skipped = [];
        var masterFolder = app.project.items.addFolder("Slated Comps");
        var slatesFolder = app.project.items.addFolder("Generated Slate Precomps");
        slatesFolder.parentFolder = masterFolder;

        var beepItem = null;
        if (!usingAepTemplate && beepFile.exists) {{
            beepItem = app.project.importFile(new ImportOptions(beepFile));
            beepItem.parentFolder = masterFolder;
        }}

        for (var i = 0; i < jobs.length; i++) {{
            var job = jobs[i];
            var isSlateOnly = (job.slate_only === true || !job.video_path);
            var vidItem = null;
            var vidAspect = job.aspect ? job.aspect : "16x9";

            if (!isSlateOnly) {{
                var ioVid = new ImportOptions(new File(job.video_path));
                vidItem = app.project.importFile(ioVid);
                vidItem.parentFolder = masterFolder;
                vidAspect = pickAspect(vidItem.width, vidItem.height);
            }}

            var tplKey = job.aspect ? job.aspect : vidAspect;
            var slateComp = null;
            var slateId = (job.text_data && (job.text_data["id"] || job.text_data["ad-id"])) ? (job.text_data["id"] || job.text_data["ad-id"]) : ("Slate_" + (i + 1));

            if (usingAepTemplate) {{
                var baseTplComp = templateComps[tplKey];
                if (!baseTplComp) {{
                    skipped.push(slateId + " (missing " + tplKey + " comp in .aep template)");
                    continue;
                }}
                slateComp = baseTplComp.duplicate();
                slateComp.name = slateId + "_" + tplKey + "_SLATE";
                slateComp.parentFolder = slatesFolder;
            }} else {{
                var tplPath = templates[tplKey];
                if (!tplPath) {{
                    skipped.push(slateId + " (needs " + tplKey + " template)");
                    continue;
                }}
                var ioPSD = new ImportOptions(new File(tplPath));
                ioPSD.importAs = ImportAsType.COMP;
                var psdItem = app.project.importFile(ioPSD);
                if (psdItem instanceof CompItem) {{
                    slateComp = psdItem;
                    slateComp.parentFolder = slatesFolder;
                }}
            }}

            if (slateComp) {{
                populateSlateComp(slateComp, job, solidComps);
            }}

            // Standalone Slate Only mode: queue the populated slateComp directly in AME without attaching a master video!
            if (isSlateOnly) {{
                if (slateComp) {{
                    var rqSlate = app.project.renderQueue.items.add(slateComp);
                    var outSlate = rqSlate.outputModule(1);
                    outSlate.file = new File(job.final_output);
                }}
                continue;
            }}

            // Slated Master mode (Slate + 2-Pop + 2s Black + Master Video):
            var compW = (job.aspect && job.aspect !== vidAspect && job.width) ? job.width : (vidItem.width > 0 ? vidItem.width : cfg.width);
            var compH = (job.aspect && job.aspect !== vidAspect && job.height) ? job.height : (vidItem.height > 0 ? vidItem.height : cfg.height);
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : cfg.fps;
            var totalDuration = 7.0 + vidItem.duration;
            var compName = job.aspect ? (slateId + "_" + job.aspect + "_SLATED") : (slateId + "_SLATED");
            var masterComp = app.project.items.addComp(compName, compW, compH, 1.0, totalDuration, compFps);
            masterComp.parentFolder = masterFolder;

            masterComp.displayStartTime = 3593.0; // 00:59:53:00

            var blackSolid = masterComp.layers.addSolid([0,0,0], "2s_Black", compW, compH, 1.0, 2.0);
            blackSolid.startTime = 5.0;

            var slateLayer = masterComp.layers.add(slateComp);
            slateLayer.startTime = 0;
            if (usingAepTemplate) {{
                slateLayer.outPoint = 5.0 + masterComp.frameDuration;
            }} else {{
                slateLayer.outPoint = 5.0;
                if (beepItem) {{
                    var beepLayer = masterComp.layers.add(beepItem);
                    beepLayer.startTime = 5.0;
                    beepLayer.outPoint = 5.0 + masterComp.frameDuration;
                }}
            }}

            if (slateComp.width !== compW || slateComp.height !== compH) {{
                var sx = (compW / slateComp.width) * 100.0;
                var sy = (compH / slateComp.height) * 100.0;
                var sUniform = Math.min(sx, sy);
                slateLayer.property("Scale").setValue([sUniform, sUniform]);
            }}

            var vidLayer = masterComp.layers.add(vidItem);
            vidLayer.startTime = 7.0;
            if (vidItem.width > 0 && vidItem.height > 0 && (vidItem.width !== compW || vidItem.height !== compH)) {{
                var vsx = (compW / vidItem.width) * 100.0;
                var vsy = (compH / vidItem.height) * 100.0;
                var vs = Math.min(vsx, vsy);
                vidLayer.property("Scale").setValue([vs, vs]);
            }} else {{
                vidLayer.property("Scale").setValue([100, 100]);
            }}

            var rqItem = app.project.renderQueue.items.add(masterComp);
            var outMod = rqItem.outputModule(1);
            outMod.file = new File(job.final_output);
        }}

        if (skipped.length) {{ alert("Skipped (no matching slate template):\\n" + skipped.join("\\n")); }}
        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        app.project.renderQueue.queueInAME(true);
        app.endUndoGroup();
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsx_code)


if __name__ == "__main__":
    root = tk.Tk()
    app = SuperJoyWorkstation(root)
    root.mainloop()
