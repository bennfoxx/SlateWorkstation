import os
import re
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


# Explicit bundle ID so osascript never hangs choosing between multiple AE versions.
AE_BUNDLE_ID = os.environ.get("SUPERJOY_AE_BUNDLE_ID", "com.adobe.AfterEffects")
VALID_EXTS = (".mov", ".mp4", ".mxf")
UNSLATE_SECONDS = 7.0  # 5s slate + 2s black

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
ASPECT_RESOLUTIONS = {
    "16x9": (1920, 1080),
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
}
STANDARD_TRTS = ("60", "30", "15", "06")


def today_yyyy_mm_dd():
    """Return the current date formatted as YYYY_MM_DD."""
    return datetime.now().strftime("%Y_%m_%d")


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
            # Only treat bare '6' as 06 if it wasn't just '06' already
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
def find_templates(folder):
    """Map aspect key ('16x9','1x1','4x5','9x16') -> PSD path, by filename (e.g. 'Slate_9x16.psd')."""
    found = {}
    if not folder or not os.path.isdir(folder):
        return found
    pat = re.compile(r"(?<![0-9])(16|1|4|9)\s*[x_:\-]\s*(9|1|5|16)(?![0-9])", re.IGNORECASE)
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(".psd") or f.startswith("."):
            continue
        m = pat.search(f)
        if m:
            key = f"{m.group(1)}x{m.group(2)}"
            if key in ASPECT_RESOLUTIONS:
                found.setdefault(key, os.path.join(folder, f))
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
        req_w = width * f.measure("0") + 24
        req_h = f.metrics("linespace") + 14
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=req_w, height=req_h, takefocus=0)

        self._border_id = round_rect(self, 1, 1, req_w - 1, req_h - 1, radius, fill=BORDER_SUBTLE, outline=BORDER_SUBTLE)
        self._fill_id = round_rect(self, 2, 2, req_w - 2, req_h - 2, max(0, radius - 1), fill=BG_DARKER, outline=BG_DARKER)

        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
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
        self.root.geometry("940x800")
        self.root.minsize(880, 740)
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
            padding=(8, 5),
        )
        self.style.map("Treeview.Heading", background=[("active", BG_GREY_HOVER)])

        # State variables
        self.tsv_path = tk.StringVar()
        self.template_dir = tk.StringVar()
        self.videos_dir = tk.StringVar()
        self.unslate_dir = tk.StringVar()
        self.fps_var = tk.StringVar(value=DEFAULT_FPS_LABEL)
        self.aspect_var = tk.StringVar(value=DEFAULT_ASPECT)
        self.active_tab_var = tk.StringVar(value="1")  # Open on Batch Slate Builder by default
        self.manual_batch_data = []
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
        header.pack(side="top", fill="x", padx=24, pady=(12, 6))

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
            text="Broadcast Slate Automation  •  Native Aspect Templates  •  1kHz 2-Pop @ 00:59:58:00",
            font=(FONT, 11),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))

        SJLogo(header, 46).pack(side="right", padx=(12, 0))

        # 2. Pinned Bottom Action Footer (packed BEFORE expandable workspace so it is NEVER clipped!)
        footer = tk.Frame(self.root, bg=BG_DARK)
        footer.pack(side="bottom", fill="x", padx=24, pady=(6, 12))

        self.btn_run = RoundedButton(
            footer,
            text="GENERATE .AEP & QUEUE IN AME",
            command=self.execute_workflow_thread,
            color=ACCENT_RED,
            font_spec=(FONT, 15, "bold"),
            padx=36,
            pady=12,
            radius=16,
        )
        self.btn_run.pack(anchor="center")

        # 3. Master Assets Card
        assets_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=13)
        assets_card.pack(side="top", fill="x", padx=24, pady=(0, 8))
        ab = assets_card.body
        ab.columnconfigure(1, weight=1)

        hdr_row = tk.Frame(ab, bg=BG_CARD)
        hdr_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        tk.Label(
            hdr_row,
            text="MASTER ASSETS & STUDIO CONFORM",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(side="left")
        self.asset_status_lbl = tk.Label(
            hdr_row,
            text="Select template & video folders",
            font=(FONT, 11),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.asset_status_lbl.pack(side="right")

        tk.Label(ab, text="SLATE TEMPLATES", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=3
        )
        RoundedEntry(ab, self.template_dir, 38).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)
        mkbtn(
            ab,
            text="Browse",
            command=lambda: self._browse_dir(self.template_dir, "Select PSD Slate Templates Folder"),
            padx=18,
            pady=6,
        ).grid(row=1, column=2, pady=3)

        tk.Label(ab, text="MASTER VIDEOS", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=3
        )
        RoundedEntry(ab, self.videos_dir, 38).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=3)
        mkbtn(
            ab,
            text="Browse",
            command=lambda: self._browse_dir(self.videos_dir, "Select Master Videos Folder"),
            padx=18,
            pady=6,
        ).grid(row=2, column=2, pady=3)

        # Fallback FPS & Aspect Pill Bar (No ttk.Combobox!)
        tk.Label(ab, text="STUDIO STANDARD", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=(5, 1)
        )
        std_row = tk.Frame(ab, bg=BG_CARD)
        std_row.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(5, 1))

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

        # 4. Segmented Mode Tab Bar (Replaces ttk.Notebook)
        tab_bar_frame = tk.Frame(self.root, bg=BG_DARK)
        tab_bar_frame.pack(side="top", fill="x", padx=24, pady=(2, 6))

        self.tab_pills = SegmentedPills(
            tab_bar_frame,
            [
                ("0", "Parse from File (TXT / CSV)"),
                ("1", "Batch Slate Builder"),
                ("2", "Un-Slate (Trim 7.0s)"),
            ],
            variable=self.active_tab_var,
            command=self.on_tab_changed,
            font_spec=(FONT, 12, "bold"),
            pad_x=22,
            pad_y=6,
            radius=10,
        )
        self.tab_pills.pack(side="left")

        # Compatibility shim so any external code checking self.notebook works seamlessly
        self.notebook = self

        # 5. Workspace Card (hosts the 3 mode pages)
        self.workspace_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=14)
        self.workspace_card.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 4))
        wb = self.workspace_card.body

        self.tab_file = tk.Frame(wb, bg=BG_CARD)
        self.tab_builder = tk.Frame(wb, bg=BG_CARD)
        self.tab_unslate = tk.Frame(wb, bg=BG_CARD)
        self._pages = [self.tab_file, self.tab_builder, self.tab_unslate]

        self._build_tab_file()
        self._build_tab_builder()
        self._build_tab_unslate()

        self._show_tab(int(self.active_tab_var.get()))

    def _build_tab_file(self):
        p = self.tab_file
        p.columnconfigure(0, weight=1)

        tk.Label(
            p,
            text="BATCH SLATE FROM METADATA SPREADSHEET",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            p,
            text="Load a tab-delimited (.tsv / .txt) or comma-delimited (.csv) slate sheet to automatically pair Ad-IDs with master videos.",
            font=(FONT, 12),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 16))

        f1 = tk.Frame(p, bg=BG_CARD)
        f1.pack(fill="x", pady=4)
        f1.columnconfigure(1, weight=1)
        tk.Label(f1, text="METADATA FILE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        RoundedEntry(f1, self.tsv_path, 44).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        mkbtn(
            f1,
            text="Browse File",
            command=lambda: self._browse_file(self.tsv_path),
            padx=20,
            pady=8,
        ).grid(row=0, column=2)

        self.file_preview_lbl = tk.Label(
            p,
            text="No metadata file selected.",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        )
        self.file_preview_lbl.pack(anchor="w", pady=(14, 16))

        info_card = RoundedCard(p, bg_fill=BG_DARKER, border_color=BORDER_SUBTLE, radius=12, pad=14)
        info_card.pack(fill="x", pady=(4, 0))
        ib = info_card.body
        tk.Label(
            ib,
            text="AUTOMATED BROADCAST PIPELINE",
            font=(FONT, 11, "bold"),
            bg=BG_DARKER,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(0, 6))
        steps = (
            "1. Strict word-boundary Ad-ID matching ('XQ12' pairs with 'XQ12_Master.mov', never 'XQ1234_Master.mov').\n"
            "2. Conforms each slated composition & output to the source video's native resolution and frame rate.\n"
            "3. Selects the matching native PSD slate template (16x9, 1x1, 4x5, or 9x16) with zero scaling.\n"
            "4. Inserts 5.0s slate (00:59:53:00), 2.0s black solid, and 1-frame 1kHz 2-pop at 5.0s (00:59:58:00)."
        )
        tk.Label(ib, text=steps, font=(FONT, 12), bg=BG_DARKER, fg=TEXT_MUTED, justify="left").pack(anchor="w")

    def _build_tab_builder(self):
        p = self.tab_builder

        # Section 1: Campaign Fields (User-entered shared fields + auto YYYY_MM_DD Date)
        sec1_hdr = tk.Frame(p, bg=BG_CARD)
        sec1_hdr.pack(fill="x", pady=(0, 3))
        tk.Label(
            sec1_hdr,
            text="CAMPAIGN METADATA (APPLIED TO BATCH)",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(side="left")
        tk.Label(
            sec1_hdr,
            text="Fill in Agency, Client, Workspace & Copyright — Date defaults to YYYY_MM_DD",
            font=(FONT, 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(side="right")

        form_frame = tk.Frame(p, bg=BG_CARD)
        form_frame.pack(fill="x", pady=(0, 4))
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
            RoundedEntry(form_frame, var, 22).grid(row=r, column=c + 1, sticky="ew", padx=(0, 12), pady=2)

        # Spot-Specific Auto-Parsed Fields (Ad-ID, Title, TRT + Flame Toggle)
        sec2_hdr = tk.Frame(p, bg=BG_CARD)
        sec2_hdr.pack(fill="x", pady=(4, 2))
        tk.Label(
            sec2_hdr,
            text="SPOT FILENAME PARSER (AUTO-PULLED FROM MASTER VIDEOS: AD-ID  •  TITLE_WITH_UNDERSCORES  •  TRT 60/30/15/06)",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        ).pack(side="left")

        spot_frame = tk.Frame(p, bg=BG_CARD)
        spot_frame.pack(fill="x", pady=(0, 4))
        spot_frame.columnconfigure(1, weight=2)
        spot_frame.columnconfigure(3, weight=4)
        spot_frame.columnconfigure(5, weight=1)

        tk.Label(spot_frame, text="AD-ID", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW).grid(
            row=0, column=0, sticky="w", padx=(2, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_id, 13).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)

        tk.Label(spot_frame, text="TITLE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_title, 26).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=2)

        tk.Label(spot_frame, text="TRT", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=4, sticky="w", padx=(0, 6), pady=2
        )
        RoundedEntry(spot_frame, self.f_trt, 6).grid(row=0, column=5, sticky="ew", padx=(0, 10), pady=2)

        RoundedToggle(spot_frame, "Flame Logo", self.f_flame, font_spec=(FONT, 11, "bold")).grid(
            row=0, column=6, sticky="e", padx=(2, 0), pady=2
        )

        # Action & Queue Toolbar
        bar = tk.Frame(p, bg=BG_CARD)
        bar.pack(fill="x", pady=(4, 4))
        mkbtn(
            bar,
            text="Auto-Pull Batch from Master Videos",
            bg=BG_BLUE,
            command=lambda: self.populate_batch_from_videos(notify_if_empty=True),
            padx=16,
            pady=6,
        ).pack(side="left")
        mkbtn(
            bar,
            text="+ Add / Update Spot",
            bg="#4CAF50",
            command=self.add_to_batch,
            padx=14,
            pady=6,
        ).pack(side="left", padx=(8, 0))
        mkbtn(bar, text="Remove Selected", bg=BG_GREY, command=self.remove_from_batch, padx=12, pady=6).pack(
            side="left", padx=(8, 0)
        )
        mkbtn(bar, text="Clear Batch", bg=BG_GREY, command=self.clear_batch, padx=12, pady=6).pack(
            side="left", padx=(8, 0)
        )
        self.batch_count_lbl = tk.Label(
            bar, text="0 slates in queue", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW
        )
        self.batch_count_lbl.pack(side="right", padx=4)

        # Queue Table
        tree_wrap = tk.Frame(p, bg=BORDER_SUBTLE, bd=0, highlightthickness=0)
        tree_wrap.pack(fill="both", expand=True, pady=(2, 0))
        columns = ("id", "title", "trt", "date", "client", "agency")
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=4)
        self.tree.heading("id", text="AD-ID")
        self.tree.heading("title", text="TITLE (SPACES → _)")
        self.tree.heading("trt", text="TRT")
        self.tree.heading("date", text="DATE")
        self.tree.heading("client", text="CLIENT")
        self.tree.heading("agency", text="AGENCY")
        self.tree.column("id", width=125, anchor="w")
        self.tree.column("title", width=330, anchor="w")
        self.tree.column("trt", width=60, anchor="center")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("client", width=120, anchor="w")
        self.tree.column("agency", width=120, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=1, pady=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<ButtonPress-1>", self._on_tree_tap, add="+")

    def _build_tab_unslate(self):
        p = self.tab_unslate

        tk.Label(
            p,
            text="BATCH UN-SLATE (QUICKTIME 7.0s HEAD TRIM)",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            p,
            text="Removes the 5.0s slate and 2.0s black/2-pop leader from slated masters and exports clean spots to an UNSLATED subfolder.",
            font=(FONT, 12),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 16))

        f2 = tk.Frame(p, bg=BG_CARD)
        f2.pack(fill="x", pady=4)
        f2.columnconfigure(1, weight=1)
        tk.Label(f2, text="SLATED VIDEOS", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        RoundedEntry(f2, self.unslate_dir, 44).grid(row=0, column=1, sticky="ew", padx=(0, 10))
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

        timeline_card = RoundedCard(p, bg_fill=BG_DARKER, border_color=BORDER_SUBTLE, radius=12, pad=14)
        timeline_card.pack(fill="x", pady=(4, 0))
        tb = timeline_card.body
        tk.Label(
            tb,
            text="TRIM SPECIFICATION",
            font=(FONT, 11, "bold"),
            bg=BG_DARKER,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            tb,
            text="• Trims exactly 7.0 seconds from the head of every .mov, .mp4, and .mxf file in the selected folder.\n"
                 "• Preserves the spot from 01:00:00:00 onward and writes trimmed files to <Folder>/UNSLATED/.\n"
                 "• Logs results and any skipped clips to Unslate_Log.txt.",
            font=(FONT, 12),
            bg=BG_DARKER,
            fg=TEXT_MUTED,
            justify="left",
        ).pack(anchor="w")

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

    def update_res_label(self):
        w, h = ASPECT_RESOLUTIONS.get(self.aspect_var.get(), (1920, 1080))
        self.res_label.config(text=f"{w}×{h}")

    def _on_videos_dir_changed(self):
        self.update_asset_badges()
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
            found_keys = ", ".join(k for k in ASPECT_RESOLUTIONS if k in tpls) or "none"
            parts.append(f"Templates: {len(tpls)}/4 ({found_keys})")
        if vdir:
            parts.append(f"Videos: {vcnt} found")
        self.asset_status_lbl.config(
            text="  •  ".join(parts) if parts else "Select template & video folders",
            fg=ACCENT_YELLOW if parts else TEXT_MUTED,
        )

    def update_file_preview(self):
        path = self.tsv_path.get().strip()
        if not path or not os.path.isfile(path):
            self.file_preview_lbl.config(text="No metadata file selected.", fg=TEXT_MUTED)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            rows = max(0, len(lines) - 1)
            self.file_preview_lbl.config(
                text=f"Loaded '{os.path.basename(path)}'  •  {rows} slate row(s) ready to pair",
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
            text=f"Found {cnt} video file(s) in '{os.path.basename(folder)}' ready for 7.0s head trim",
            fg=ACCENT_YELLOW,
        )

    def run_label(self):
        return "TRIM SLATES (UN-SLATE)" if int(self.active_tab_var.get()) == 2 else "GENERATE .AEP & QUEUE IN AME"

    # ------------------------------------------------------------------
    # Batch Slate Builder (Auto-Pull from Master Video Filenames + Manual Edit)
    # ------------------------------------------------------------------
    @staticmethod
    def _underscored(text):
        """Replace spaces with underscores '_'."""
        return re.sub(r"\s*_\s*|\s+", "_", text.strip()).strip("_") if text else ""

    def _current_campaign_fields(self):
        if not self.f_date.get().strip():
            self.f_date.set(today_yyyy_mm_dd())
        return {
            "agency": self.f_agency.get().strip(),
            "client": self.f_client.get().strip(),
            "date": self._underscored(self.f_date.get()) or today_yyyy_mm_dd(),
            "workspace": self.f_workspace.get().strip(),
            "audio": self.f_audio.get().strip() or "STEREO",
            "copyright": self.f_copyright.get().strip(),
            "flame": "y" if self.f_flame.get() else "n",
        }

    def populate_batch_from_videos(self, notify_if_empty=False):
        """Scan Master Videos folder and auto-populate Batch Slate Builder with
        Ad-ID, underscored Title, TRT (60/30/15/06), and today's YYYY_MM_DD date."""
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
        existing_by_id = {item["id"].lower(): item for item in self.manual_batch_data if item.get("id")}

        new_batch = []
        for vf in video_files:
            ad_id, title, trt = parse_video_filename(vf)
            prev = existing_by_id.get(ad_id.lower(), {})
            slate_data = {
                "agency": shared["agency"] or prev.get("agency", ""),
                "client": shared["client"] or prev.get("client", ""),
                "title": title,
                "id": ad_id,
                "trt": trt or prev.get("trt", ""),
                "date": shared["date"],
                "workspace": shared["workspace"] or prev.get("workspace", ""),
                "audio": shared["audio"],
                "copyright": shared["copyright"] or prev.get("copyright", ""),
                "flame": shared["flame"],
            }
            new_batch.append(slate_data)

        self.manual_batch_data = new_batch
        self._refresh_tree()

        # Pre-fill the spot preview fields with the first video's extracted metadata
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
            item["workspace"] = shared["workspace"]
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
            cid = self.tree.insert(
                "",
                "end",
                values=(
                    slate["id"],
                    slate["title"],
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
        if row_id:
            self.tree.selection_set(row_id)
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
            finally:
                self._loading_row = False

    def add_to_batch(self):
        raw_id = self.f_id.get().strip()
        raw_title = self._underscored(self.f_title.get())
        raw_trt = self.f_trt.get().strip()

        if not raw_id or not raw_title:
            self._alert("showwarning", "Missing Info", "Ad-ID and Title are required to build a slate.")
            return

        # Auto-detect TRT from title if the user left TRT blank
        if not raw_trt:
            _, _, detected_trt = parse_video_filename(f"{raw_id}_{raw_title}")
            raw_trt = detected_trt

        shared = self._current_campaign_fields()
        slate_data = {
            "agency": shared["agency"],
            "client": shared["client"],
            "title": raw_title,
            "id": raw_id,
            "trt": raw_trt,
            "date": shared["date"],
            "workspace": shared["workspace"],
            "audio": shared["audio"],
            "copyright": shared["copyright"],
            "flame": shared["flame"],
        }

        # If a matching Ad-ID is already in the batch (or selected), update it in place; otherwise append
        updated = False
        for i, existing in enumerate(self.manual_batch_data):
            if existing.get("id", "").lower() == raw_id.lower():
                self.manual_batch_data[i] = slate_data
                updated = True
                break
        if not updated:
            self.manual_batch_data.append(slate_data)

        self._refresh_tree()
        self.f_title.set("")
        self.f_id.set("")
        self.f_trt.set("")

    def remove_from_batch(self):
        selected = self.tree.selection()
        for item in selected:
            idx = self.tree.index(item)
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
    # Workflow Execution
    # ------------------------------------------------------------------
    def execute_workflow_thread(self):
        tab = int(self.active_tab_var.get())

        if tab == 2:
            folder = self.unslate_dir.get().strip()
            if not folder or not os.path.isdir(folder):
                self._alert("showerror", "Error", "Please select a folder of slated videos.")
                return
            self.btn_run.config(text="PROCESSING...", state="disabled")
            threading.Thread(target=self.process_unslate, args=(folder,), daemon=True).start()
            return

        template_dir = self.template_dir.get().strip()
        videos_dir = self.videos_dir.get().strip()

        fps = parse_fps(self.fps_var.get())
        if fps is None:
            self._alert("showerror", "Error", "Invalid frame rate. Pick a preset or enter a number between 1 and 120.")
            return
        width, height = ASPECT_RESOLUTIONS[self.aspect_var.get()]
        self.render_settings = {"fps": fps, "width": width, "height": height}

        if not template_dir or not videos_dir:
            self._alert("showerror", "Error", "Please select your Slate Template folder and Master Videos folder.")
            return

        batch_jobs_data = []
        if tab == 0:
            tsv = self.tsv_path.get().strip()
            if not tsv:
                self._alert("showerror", "Error", "Please select a metadata file.")
                return
            try:
                with open(tsv, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                delimiter = "\t" if "\t" in lines[0] else ","
                headers = [h.strip().lower() for h in lines[0].split(delimiter)]
                for r in range(1, len(lines)):
                    row = lines[r].split(delimiter)
                    data = {headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))}
                    batch_jobs_data.append(data)
            except Exception as e:
                self._alert("showerror", "Error", f"Failed to parse file:\n{str(e)}")
                return
        else:
            # Auto-pull from Master Videos if queue is empty when running from Batch Slate Builder
            if not self.manual_batch_data and os.path.isdir(videos_dir):
                self.populate_batch_from_videos(notify_if_empty=False)
            if not self.manual_batch_data:
                self._alert("showerror", "Error", "Your batch queue is empty and no master videos were found.")
                return
            self._sync_shared_fields_to_batch()
            batch_jobs_data = [dict(item) for item in self.manual_batch_data]

        self.btn_run.config(text="PROCESSING...", state="disabled")
        threading.Thread(
            target=self.process_batch, args=(batch_jobs_data, template_dir, videos_dir), daemon=True
        ).start()

    # ------------------------------------------------------------------
    # Un-Slate (QuickTime 7.0s Head Trim)
    # ------------------------------------------------------------------
    def process_unslate(self, folder):
        out_dir = os.path.join(folder, "UNSLATED")
        os.makedirs(out_dir, exist_ok=True)
        files = sorted(
            f for f in os.listdir(folder) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        )
        ok, failed = 0, []

        for fname in files:
            src = os.path.join(folder, fname)
            dst = os.path.join(out_dir, fname)
            if os.path.exists(dst):
                os.remove(dst)  # QuickTime save will not overwrite
            script = '''
            on run argv
                set srcFile to POSIX file (item 1 of argv)
                set dstFile to POSIX file (item 2 of argv)
                set trimStart to (item 3 of argv) as real
                tell application "QuickTime Player"
                    set theDoc to open srcFile
                    set theDur to duration of theDoc
                    if theDur <= trimStart then
                        close theDoc saving no
                        error "Video is shorter than the trim length."
                    end if
                    trim theDoc from trimStart to theDur
                    save theDoc in dstFile
                    close theDoc saving no
                end tell
            end run
            '''
            try:
                subprocess.run(
                    ["osascript", "-e", script, src, dst, str(UNSLATE_SECONDS)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                )
                ok += 1
            except subprocess.CalledProcessError as e:
                failed.append(f"{fname}: {e.stderr.strip()}")
            except Exception as e:
                failed.append(f"{fname}: {e}")

        log_lines = [f"Un-slated {ok}/{len(files)} files -> {out_dir}"] + failed
        try:
            with open(os.path.join(out_dir, "Unslate_Log.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except OSError:
            pass

        msg = "\n".join(log_lines[:15])
        if failed or not files:
            self.root.after(
                0,
                lambda: self._alert(
                    "showwarning", "Un-Slate Finished", msg if files else "No video files found."
                ),
            )
        else:
            self.root.after(0, lambda: self._alert("showinfo", "Un-Slate Complete", msg))
        self.root.after(0, self.reset_ui)

    # ------------------------------------------------------------------
    # Slate (After Effects + AME Queue)
    # ------------------------------------------------------------------
    def process_batch(self, batch_data, template_dir, videos_dir):
        templates = find_templates(template_dir)
        if not templates:
            self.root.after(
                0,
                lambda: self._alert(
                    "showerror",
                    "Error",
                    "No PSD templates named with 16x9, 1x1, 4x5 or 9x16 found in the template folder.",
                ),
            )
            self.root.after(0, self.reset_ui)
            return

        output_dir = os.path.join(videos_dir, "SLATED_DELIVERY")
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, "Slating_Results_Log.txt")
        aep_master_path = os.path.join(output_dir, "SuperJoy_Master_Slates.aep")
        beep_path = os.path.join(output_dir, "_2pop_1kHz_1frame.wav")
        log_entries = ["SUPERJOY AE/AME SLATING RESULTS LOG", "=" * 40, ""]

        ae_jobs = []
        success_count = 0
        error_count = 0

        for data in batch_data:
            ad_id = data.get("id", data.get("ad-id", ""))
            title = data.get("title", data.get("name", ""))
            flame_flag = data.get("flame", "").lower() in ("y", "yes", "true", "1")

            matched_video = None
            for vf in os.listdir(videos_dir):
                if vf.lower().endswith(VALID_EXTS) and ad_id_matches(ad_id, vf):
                    matched_video = os.path.join(videos_dir, vf)
                    break

            if not matched_video:
                log_entries.append(
                    f"[ERROR] ID: {ad_id} | Title: {title} | No strict filename match found in video folder."
                )
                error_count += 1
                continue

            final_output_file = os.path.join(output_dir, f"{ad_id}_Slated.mov")

            ae_jobs.append(
                {
                    "video_path": matched_video,
                    "final_output": final_output_file,
                    "flame": flame_flag,
                    "text_data": data,
                }
            )
            log_entries.append(f"[SUCCESS] Paired {ad_id} -> {os.path.basename(matched_video)}")
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

        # Target AE by bundle ID, not by name, so multiple installed versions can't hang osascript.
        applescript = '''
        on run argv
            set jsxPath to POSIX file (item 1 of argv)
            tell application id "%s"
                activate
                DoScriptFile jsxPath
            end tell
        end run
        ''' % AE_BUNDLE_ID

        try:
            subprocess.run(
                ["osascript", "-e", applescript, jsx_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            msg = (
                f"Successfully generated Master Project ({success_count} slates) and queued in AME!\n\n"
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

        app.newProject();
        app.beginUndoGroup("Batch Slate Generation");

        var skipped = [];
        var masterFolder = app.project.items.addFolder("Slated Comps");
        var beepItem = app.project.importFile(new ImportOptions(beepFile));
        beepItem.parentFolder = masterFolder;

        for (var i = 0; i < jobs.length; i++) {{
            var job = jobs[i];

            var ioVid = new ImportOptions(new File(job.video_path));
            var vidItem = app.project.importFile(ioVid);

            // Pick the slate template whose aspect matches the main video (no scaling applied).
            var tplKey = pickAspect(vidItem.width, vidItem.height);
            var tplPath = templates[tplKey];
            if (!tplPath) {{ skipped.push(vidItem.name + " (needs " + tplKey + " template)"); continue; }}

            var ioPSD = new ImportOptions(new File(tplPath));
            ioPSD.importAs = ImportAsType.COMP;
            var psdItem = app.project.importFile(ioPSD);
            var psdComp = null;
            if (psdItem instanceof CompItem) {{ psdComp = psdItem; }}

            if (psdComp) {{
                for (var l = 1; l <= psdComp.numLayers; l++) {{
                    var layer = psdComp.layer(l);
                    var lName = layer.name.toLowerCase();

                    if (lName.indexOf("flame") !== -1) {{
                        layer.enabled = job.flame;
                    }}

                    if (layer instanceof TextLayer) {{
                        var cleanName = lName.replace("^", "").toLowerCase();
                        if (job.text_data[cleanName] !== undefined) {{
                            var textProp = layer.property("Source Text");
                            var textDoc = textProp.value;
                            textDoc.text = job.text_data[cleanName];
                            textProp.setValue(textDoc);
                        }}
                    }}
                }}
            }}

            // Slate + final always conform to the main video's resolution and frame rate;
            // UI settings are only a fallback if the footage reports no usable values.
            var compW = vidItem.width > 0 ? vidItem.width : cfg.width;
            var compH = vidItem.height > 0 ? vidItem.height : cfg.height;
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : cfg.fps;
            var totalDuration = 7.0 + vidItem.duration;
            var masterComp = app.project.items.addComp(vidItem.name + "_SLATED", compW, compH, 1.0, totalDuration, compFps);
            masterComp.parentFolder = masterFolder;

            masterComp.displayStartTime = 3593.0; // 00:59:53:00

            var slateLayer = masterComp.layers.add(psdComp);  // template is native size; no scaling
            slateLayer.startTime = 0;
            slateLayer.outPoint = 5.0;

            var blackSolid = masterComp.layers.addSolid([0,0,0], "2s_Black", compW, compH, 1.0, 2.0);
            blackSolid.startTime = 5.0;

            // 2-pop: 1-frame 1kHz beep at 5.0s (comp timecode 00:59:58:00)
            var beepLayer = masterComp.layers.add(beepItem);
            beepLayer.startTime = 5.0;
            beepLayer.outPoint = 5.0 + masterComp.frameDuration;

            var vidLayer = masterComp.layers.add(vidItem);
            vidLayer.startTime = 7.0;
            vidLayer.property("Scale").setValue([100, 100]);

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
