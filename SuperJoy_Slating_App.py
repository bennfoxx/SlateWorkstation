import os
import re
import csv
import sys
import glob
import json
import math
import time
import wave
import shutil
import ctypes
import struct
import zipfile
import threading
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Theme & Branding Profiles
# ---------------------------------------------------------------------------
THEMES = {
    "superjoy": {
        "app_title": "SuperJoy Broadcast Slating Workstation",
        "header_title_bold": "SUPERJOY",
        "header_title_sub": "  SLATING WORKSTATION",
        "tagline": "Broadcast Slate Automation  •  ProRes 422 HQ + H.264 (25Mbps)  •  SLATED & UNSLATED Delivery",
        "project_prefix": "SuperJoy",
        "default_agency": "MARTIN*",
        "bg_dark": "#222538",         # Deep navy-slate background from the slate
        "bg_card": "#2A2E44",         # Elevated card surface
        "bg_darker": "#181B29",       # Recessed input / well surface
        "border_subtle": "#383D59",   # Soft card & input border
        "accent_red": "#E8453C",      # Signature SuperJoy coral-red
        "accent_red_hover": "#F45B52",
        "accent_yellow": "#F3E052",   # Signature SuperJoy ID/7 countdown yellow
        "text_light": "#FFFFFF",
        "text_muted": "#9BA3C2",
        "bg_green": "#2E9E44",
        "bg_green_hover": "#37B24D",
        "bg_blue": "#3B6EA8",
        "bg_grey": "#383E56",
        "bg_grey_hover": "#454C68",
        "bg_disabled": "#4A4F66",
        "font_family": "Avenir Next",
        "font_candidates": ("Avenir Next", "Helvetica Neue", "Helvetica"),
        "dmg_url_env": "SUPERJOY_UPDATE_DMG_URL",
        "dmg_url_default": "https://raw.githubusercontent.com/bennfoxx/SlateWorkstation/main/SuperJoy_Slating_Workstation_v1.0.0.dmg",
        "app_name": "SuperJoy Slating Workstation",
        "bundle_id": "com.superjoy.slatingworkstation",
        "logo_style": "superjoy",
    },
    "mstr_sl8r": {
        "app_title": "MSTR-SL8R  •  Broadcast Slating Workstation",
        "header_title_bold": "MSTR-SL8R",
        "header_title_sub": "  BROADCAST WORKSTATION",
        "tagline": "Broadcast Slate Automation  •  ProRes 422 HQ + H.264 (25Mbps)  •  SLATED & UNSLATED Delivery",
        "project_prefix": "MSTR_SL8R",
        "default_agency": "MARTIN*",
        "bg_dark": "#0A0A0C",         # Pitch dark studio background (benfoxmedia.com #000 / #0d0c0e)
        "bg_card": "#151418",         # Elevate dark card (#17151a)
        "bg_darker": "#000000",       # Recessed black input / well
        "border_subtle": "#2A272D",   # Ben Fox Media CSS --line token
        "accent_red": "#13F1D5",      # Ben Fox Media CSS --bf-aqua (signature vibrant cyan/aqua)
        "accent_red_hover": "#01D4FB", # Ben Fox Media CSS --bf-cyan
        "accent_yellow": "#E5C8FF",   # Ben Fox Media CSS --bf-lilac (accent highlights)
        "text_light": "#FFFFFF",      # Ben Fox Media CSS --fg
        "text_muted": "#A9A4AD",      # Ben Fox Media CSS --muted
        "bg_green": "#A8E8C5",        # Ben Fox Media CSS --bf-mint
        "bg_green_hover": "#B8F0D0",
        "bg_blue": "#01D4FB",         # Ben Fox Media CSS --bf-cyan
        "bg_grey": "#2A272D",         # Dark line grey
        "bg_grey_hover": "#3A363E",
        "bg_disabled": "#3A363E",
        "font_family": "Jost",
        "font_candidates": ("Jost", "Futura", "Century Gothic", "Archivo Narrow", "Helvetica Neue", "Helvetica"),
        "dmg_url_env": "MSTR_SL8R_UPDATE_DMG_URL",
        "dmg_url_default": "https://raw.githubusercontent.com/bennfoxx/SlateWorkstation/main/MSTR_SL8R_v1.0.0.dmg",
        "app_name": "MSTR-SL8R",
        "bundle_id": "com.benfoxmedia.mstrsl8r",
        "logo_style": "mstr_sl8r",
    },
}

# Active Brand Defaults
ACTIVE_THEME = "superjoy"
BG_DARK = THEMES["superjoy"]["bg_dark"]
BG_CARD = THEMES["superjoy"]["bg_card"]
BG_DARKER = THEMES["superjoy"]["bg_darker"]
BORDER_SUBTLE = THEMES["superjoy"]["border_subtle"]
ACCENT_RED = THEMES["superjoy"]["accent_red"]
ACCENT_RED_HOVER = THEMES["superjoy"]["accent_red_hover"]
ACCENT_YELLOW = THEMES["superjoy"]["accent_yellow"]
TEXT_LIGHT = THEMES["superjoy"]["text_light"]
TEXT_MUTED = THEMES["superjoy"]["text_muted"]
BG_GREEN = THEMES["superjoy"]["bg_green"]
BG_GREEN_HOVER = THEMES["superjoy"]["bg_green_hover"]
BG_BLUE = THEMES["superjoy"]["bg_blue"]
BG_GREY = THEMES["superjoy"]["bg_grey"]
BG_GREY_HOVER = THEMES["superjoy"]["bg_grey_hover"]
BG_DISABLED = THEMES["superjoy"]["bg_disabled"]

FONT = "Avenir Next"
FONT_CANDIDATES = THEMES["superjoy"]["font_candidates"]


def set_theme(theme_name="superjoy"):
    """Set the active branding theme globally before creating UI widgets."""
    global ACTIVE_THEME, BG_DARK, BG_CARD, BG_DARKER, BORDER_SUBTLE
    global ACCENT_RED, ACCENT_RED_HOVER, ACCENT_YELLOW, TEXT_LIGHT, TEXT_MUTED
    global BG_GREEN, BG_GREEN_HOVER, BG_BLUE, BG_GREY, BG_GREY_HOVER, BG_DISABLED
    global FONT, FONT_CANDIDATES
    key = theme_name.lower().replace("-", "_") if theme_name else "superjoy"
    cfg = THEMES.get(key, THEMES["superjoy"])
    ACTIVE_THEME = key if key in THEMES else "superjoy"
    BG_DARK = cfg["bg_dark"]
    BG_CARD = cfg["bg_card"]
    BG_DARKER = cfg["bg_darker"]
    BORDER_SUBTLE = cfg["border_subtle"]
    ACCENT_RED = cfg["accent_red"]
    ACCENT_RED_HOVER = cfg["accent_red_hover"]
    ACCENT_YELLOW = cfg["accent_yellow"]
    TEXT_LIGHT = cfg["text_light"]
    TEXT_MUTED = cfg["text_muted"]
    BG_GREEN = cfg["bg_green"]
    BG_GREEN_HOVER = cfg["bg_green_hover"]
    BG_BLUE = cfg["bg_blue"]
    BG_GREY = cfg["bg_grey"]
    BG_GREY_HOVER = cfg["bg_grey_hover"]
    BG_DISABLED = cfg["bg_disabled"]
    FONT = cfg["font_family"]
    FONT_CANDIDATES = cfg["font_candidates"]


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
DEFAULT_FPS = 24000 / 1001.0
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
ASPECT_KEYS = ("16x9", "1x1", "4x5", "9x16", "2x3")
ASPECT_RESOLUTIONS = {
    "16x9": (1920, 1080),
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
    "2x3": (1080, 1620),
}
STANDARD_TRTS = ("60", "30", "15", "06")


def format_resolution_label(aspect_key):
    """Return a human-readable resolution string such as '16x9 (1920×1080)'."""
    key = aspect_key if aspect_key in ASPECT_RESOLUTIONS else DEFAULT_ASPECT
    w, h = ASPECT_RESOLUTIONS[key]
    return f"{key} ({w}×{h})"


def detect_aspect_from_text(text):
    """Detect an explicit aspect token ('16x9', '1x1', '4x5', '9x16', '2x3') or pixel dimensions in a filename/title."""
    if not text:
        return None
    m = re.search(
        r"(?<![0-9])(16\s*[x_:\-]\s*9|1\s*[x_:\-]\s*1|4\s*[x_:\-]\s*5|9\s*[x_:\-]\s*16|2\s*[x_:\-]\s*3)(?![0-9])",
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
        "1080x1620": "2x3",
    }
    for dim_tok, asp in dim_map.items():
        if dim_tok in text.lower():
            return asp
    return None


def today_yyyy_mm_dd():
    """Return the current date formatted as YYYY_MM_DD."""
    return datetime.now().strftime("%Y_%m_%d")


# Default After Effects Slate Template (.aep) and Spreadsheet (.xlsx) bundled in the workstation folder
_APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))  # bundled resources when frozen
_TPL_006 = os.path.join(_APP_DIR, "sj_Slates From Spreadsheet_Template_006.aep")
_TPL_005 = os.path.join(_APP_DIR, "sj_Slates From Spreadsheet_Template_005.aep")
DEFAULT_TEMPLATE_AEP = _TPL_006 if os.path.exists(_TPL_006) else _TPL_005
DEFAULT_SPREADSHEET_XLSX = os.path.join(_APP_DIR, "Slates From Spreadsheet_Template_001.xlsx")
DEFAULT_README = os.path.join(_APP_DIR, "readme.txt")
DEFAULT_AGENCY = "MARTIN*"
METADATA_FILETYPES = [
    ("Spreadsheet & Metadata Files", "*.xlsx *.tsv *.csv *.txt"),
    ("Excel Workbook (.xlsx)", "*.xlsx"),
    ("Tab / Comma Delimited (.tsv, .csv, .txt)", "*.tsv *.csv *.txt"),
    ("All Files", "*.*"),
]


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
    """Normalize a dictionary from an XLSX/CSV/TSV/manual batch row so all template column aliases
    (e.g. 'COMP', 'NAME', 'CLIENT', 'TITLE', 'Ad-ID', 'TRT', 'WORKSPACE_ARTIST', 'Day', 'NFA', 'Flame', 'Copyright')
    map cleanly to canonical slate keys."""
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

    ad_id = pick("ad-id", "id", "ad_id", "adid", "spot_id", "isci")
    comp_name = pick("name", "comp_name")
    title = pick("title", "spot_title", "spot")
    if not title and comp_name:
        # If only NAME (e.g. '123400_Video 1') was provided, strip leading Ad-ID prefix to get the clean Title
        if ad_id and comp_name.lower().startswith(ad_id.lower()):
            title = comp_name[len(ad_id) :].lstrip("_- ") or comp_name
        else:
            title = comp_name
    if not comp_name and (ad_id or title):
        comp_name = f"{ad_id}_{title}".strip("_")

    client = pick("client", "brand", "advertiser")
    agency = pick("agency", "the martin agency", default=DEFAULT_AGENCY) or DEFAULT_AGENCY
    nfa = pick("nfa")
    trt = pick("trt", "duration", "length", "time")
    date_val = pick("day", "date", "air_date", "ship_date")
    if not date_val or date_val.upper() in ("YYYY_MM_DD", "YYYY-MM-DD", "MM_DD_YYYY", "MM/DD/YYYY"):
        date_val = today_yyyy_mm_dd()
    workspace = pick("workspace_artist", "workspace", "artist", "editor")
    audio = pick("audio", "mix", "sound", default="STEREO")
    copyright_val = pick("copyright", "legal")
    flame = pick("flame", "flame_logo", default="n")
    output_dir = pick("output_dir", "output_folder", "output")
    # First column ('COMP') designates the comp resolution which directs toward a specific template comp in the .aep
    raw_aspect = pick("comp", "aspect", "resolution", "format", "ratio")
    aspect = raw_aspect if raw_aspect in ASPECT_RESOLUTIONS else detect_aspect_from_text(raw_aspect)

    result = dict(cleaned)
    result.update(
        {
            "id": ad_id,
            "ad-id": ad_id,
            "title": title,
            "name": comp_name or title,
            "comp_name": comp_name or title,
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
            "output_dir": output_dir,
        }
    )
    if aspect:
        result["aspect"] = aspect
        result["comp"] = aspect
        result["resolution"] = format_resolution_label(aspect)
    return result


def _excel_col_to_index(cell_ref):
    """Convert an Excel cell reference like 'A1', 'D2', 'K15', 'AA3' into a 0-based column index."""
    m = re.match(r"^([A-Za-z]+)", cell_ref or "")
    if not m:
        return 0
    idx = 0
    for ch in m.group(1).upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(0, idx - 1)


def parse_xlsx_rows(path):
    """Zero-dependency native .xlsx workbook reader (using zipfile + xml.etree.ElementTree).
    Reads sharedStrings.xml and sheet1.xml, preserving exact column alignment even when empty cells are omitted."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path, "r") as z:
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(ns + "si"):
                shared_strings.append("".join(t.text or "" for t in si.iter(ns + "t")))

        sheet_files = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheet_files:
            return []
        sheet_root = ET.fromstring(z.read(sheet_files[0]))

        parsed_rows = []
        max_col = 0
        for row_el in sheet_root.iter(ns + "row"):
            row_map = {}
            next_col = 0
            for c_el in row_el.findall(ns + "c"):
                ref = c_el.attrib.get("r", "")
                col_idx = _excel_col_to_index(ref) if ref else next_col
                next_col = col_idx + 1
                max_col = max(max_col, col_idx + 1)

                cell_type = c_el.attrib.get("t", "")
                v_el = c_el.find(ns + "v")
                is_el = c_el.find(ns + "is")
                val = ""
                if cell_type == "s" and v_el is not None and v_el.text is not None:
                    s_idx = int(v_el.text)
                    val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                elif cell_type == "inlineStr" and is_el is not None:
                    val = "".join(t.text or "" for t in is_el.iter(ns + "t"))
                elif cell_type == "b" and v_el is not None and v_el.text is not None:
                    val = "y" if v_el.text.strip() in ("1", "true", "TRUE") else "n"
                elif v_el is not None and v_el.text is not None:
                    val = v_el.text.strip()
                    if re.match(r"^-?\d+\.0$", val):
                        val = val[:-2]
                row_map[col_idx] = val
            if row_map:
                parsed_rows.append(row_map)

        if not parsed_rows or max_col == 0:
            return []
        return [[r.get(i, "").strip() for i in range(max_col)] for r in parsed_rows]


def parse_metadata_file(path):
    """Parse an XLSX, CSV, TSV, or TXT metadata file (handling Excel workbooks, UTF-8 BOM,
    quoted commas, and skipping blank or placeholder '_' formula rows)."""
    if path.lower().endswith(".xlsx"):
        reader = parse_xlsx_rows(path)
    else:
        with open(path, "rb") as f:
            data = f.read()
        # Excel on Mac saves "Text (Tab delimited)" as Mac Roman, Windows as cp1252, others UTF-8/UTF-16
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = data.decode("utf-16")
        else:
            for enc in ("utf-8-sig", "mac_roman", "cp1252", "latin-1"):
                try:
                    text = data.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        text = text.replace("\xa0", " ")  # non-breaking spaces from Excel
        raw_lines = [line for line in text.splitlines(True) if line.strip()]
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


def create_delivery_folders(base_out_dir, include_slated=True, include_unslated=True, include_h264=True):
    """Create the canonical final delivery directory structure inside `base_out_dir`:
    - SLATED/ProRes  and SLATED/h264
    - UNSLATED/ProRes and UNSLATED/h264"""
    paths = {
        "base": base_out_dir,
        "slated_root": os.path.join(base_out_dir, "SLATED"),
        "slated_prores": os.path.join(base_out_dir, "SLATED", "ProRes"),
        "slated_h264": os.path.join(base_out_dir, "SLATED", "h264"),
        "unslated_root": os.path.join(base_out_dir, "UNSLATED"),
        "unslated_prores": os.path.join(base_out_dir, "UNSLATED", "ProRes"),
        "unslated_h264": os.path.join(base_out_dir, "UNSLATED", "h264"),
        "presets_dir": os.path.join(base_out_dir, "_AME_Presets"),
    }
    os.makedirs(base_out_dir, exist_ok=True)
    if include_slated:
        os.makedirs(paths["slated_prores"], exist_ok=True)
        if include_h264:
            os.makedirs(paths["slated_h264"], exist_ok=True)
    if include_unslated:
        os.makedirs(paths["unslated_prores"], exist_ok=True)
        if include_h264:
            os.makedirs(paths["unslated_h264"], exist_ok=True)
    os.makedirs(paths["presets_dir"], exist_ok=True)
    return paths


def ensure_ame_running(wait_seconds=75):
    """Launch Adobe Media Encoder (if needed) and give Dynamic Link time to come up,
    so After Effects' queueInAME doesn't fail with 'Failed to connect to Adobe Media Encoder'."""
    def running():
        r = subprocess.run(["pgrep", "-f", "[.]app/Contents/MacOS/Adobe Media Encoder [0-9]+$"], capture_output=True)
        return r.returncode == 0
    try:
        if running():
            return True
        apps = sorted(glob.glob("/Applications/Adobe Media Encoder */Adobe Media Encoder *.app"), reverse=True)
        if not apps:
            return False
        # Do NOT pass '-g' — launching AME with '-g' suppresses its main Queue window and Dynamic Link receiver
        subprocess.run(["open", apps[0]], check=False)
        for _ in range(wait_seconds):
            if running():
                time.sleep(15)  # let the Dynamic Link server finish starting
                return True
            time.sleep(1)
    except Exception:
        pass
    return False


def wrap_jsx_with_status(jsx_body, status_path):
    """Wrap a generated JSX so any error is caught and a status file is always written
    (osascript returns success even when After Effects throws, so Python reads this file)."""
    return (
        "var __SJ_STATUS = {ok: false, queued: false, rendered: false, rqItems: 0, error: \"\"};\n"
        "function __sjErrText(e) {\n"
        "  if (!e) return 'Unknown error';\n"
        "  try { if (typeof e === 'string') return e; } catch (e0) {}\n"
        "  try { if (e.message) return e.message + (e.line ? ' (line ' + e.line + ')' : ''); } catch (e1) {}\n"
        "  try { if (e.description) return e.description; } catch (e2) {}\n"
        "  try { if (e.toString) return e.toString(); } catch (e3) {}\n"
        "  return 'After Effects script error';\n"
        "}\n"
        "function __sjWriteStatus() {\n"
        "  try {\n"
        "    var f = new File(" + json.dumps(status_path) + "); f.encoding = 'UTF-8'; f.open('w');\n"
        "    var errClean = (__SJ_STATUS.error ? __sjErrText(__SJ_STATUS.error) : '').replace(/[\\r\\n]+/g, ' ');\n"
        "    f.write('ok=' + (__SJ_STATUS.ok ? 1 : 0) + '\\nqueued=' + (__SJ_STATUS.queued ? 1 : 0)"
        " + '\\nrendered=' + (__SJ_STATUS.rendered ? 1 : 0)"
        " + '\\nrq_items=' + __SJ_STATUS.rqItems + '\\nerror=' + errClean + '\\n');\n"
        "    f.close();\n"
        "  } catch (eW) {}\n"
        "}\n"
        "try {\n"
        "  var __sec = 'Pref_SCRIPTING_FILE_NETWORK_SECURITY';\n"
        "  if (app.preferences.getPrefAsLong('Main Pref Section', __sec, PREFType.PREF_Type_MACHINE_INDEPENDENT) !== 1) {\n"
        "    app.preferences.savePrefAsLong(1, 'Main Pref Section', __sec, PREFType.PREF_Type_MACHINE_INDEPENDENT);\n"
        "    app.preferences.saveToDisk();\n"
        "  }\n"
        "} catch (ePref) {}\n"
        "try { app.beginSuppressDialogs(); } catch (eSD) {}\n"
        "try {\n" + jsx_body + "\n"
        "  if (!__SJ_STATUS.error) { __SJ_STATUS.ok = true; }\n"
        "} catch (eMain) {\n"
        "  __SJ_STATUS.error = __sjErrText(eMain);\n"
        "  try { app.endUndoGroup(); } catch (eU) {}\n"
        "}\n"
        "try { app.endSuppressDialogs(false); } catch (eSE) {}\n"
        "__sjWriteStatus();\n"
    )


def clear_jsx_status(jsx_path):
    try:
        os.remove(jsx_path + ".status")
    except OSError:
        pass


def verify_jsx_status(jsx_path, expect_queue=True):
    """Raise RuntimeError unless the After Effects script reported success and queued/rendered items."""
    sp = jsx_path + ".status"
    if not os.path.isfile(sp):
        raise RuntimeError("After Effects did not finish the script (no status reported). Check for open dialogs in After Effects.")
    info = {}
    with open(sp, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                info[k] = v
    if info.get("ok") != "1" or info.get("error"):
        raise RuntimeError(info.get("error") or "After Effects script failed.")
    if expect_queue and (
        (info.get("queued") != "1" and info.get("rendered") != "1")
        or int(info.get("rq_items", "0") or 0) == 0
    ):
        raise RuntimeError("Nothing was rendered or queued in Adobe Media Encoder (render queue empty or AME unreachable).")
    return info


def execute_ae_script_file(jsx_path, timeout=3600):
    """Safely run a JSX script in Adobe After Effects using AppleScript DoScript with override.
    Passing the script code directly with 'with override' prevents:
    1. 'Attempt was made to run a second script while another script was already running' warning.
    2. File-not-found / path escaping issues with POSIX file objects."""
    ensure_ae_script_permissions()
    with open(jsx_path, "r", encoding="utf-8") as f:
        code = f.read()

    ae_target = resolve_ae_applescript_target()
    applescript = f'''
    on run argv
        set jsCode to item 1 of argv
        tell {ae_target}
            activate
            DoScript jsCode with override
        end tell
    end run
    '''
    return subprocess.run(
        ["osascript", "-e", applescript, code],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


AE_SCRIPT_PREF_KEY = "Pref_SCRIPTING_FILE_NETWORK_SECURITY"


def _ae_prefs_file():
    """Newest After Effects preferences file (e.g. ~/Library/Preferences/Adobe/After Effects/26.5/...Prefs.txt)."""
    base = os.path.expanduser("~/Library/Preferences/Adobe/After Effects")
    cands = glob.glob(os.path.join(base, "*", "Adobe After Effects * Prefs.txt"))

    def ver(pth):
        try:
            return tuple(int(x) for x in os.path.basename(os.path.dirname(pth)).split("."))
        except ValueError:
            return (0,)

    return max(cands, key=ver) if cands else ""


def ensure_ae_script_permissions():
    """The status report and file output need 'Allow Scripts to Write Files and Access Network'.
    If AE isn't running we enable it in its prefs file; if it is running we explain how to enable it."""
    pf = _ae_prefs_file()
    if not pf:
        return
    with open(pf, "rb") as f:
        data = f.read()
    on = ('"%s" = "1"' % AE_SCRIPT_PREF_KEY).encode()
    off = ('"%s" = "0"' % AE_SCRIPT_PREF_KEY).encode()
    if on in data or off not in data:
        return
    running = subprocess.run(
        ["pgrep", "-x", "After Effects"], capture_output=True
    ).returncode == 0
    if running:
        raise RuntimeError(
            "After Effects is blocking scripts from writing files.\n\n"
            "In After Effects choose Settings > Scripting & Expressions, tick "
            "'Allow Scripts to Write Files and Access Network', click OK, then quit and relaunch "
            "After Effects (or quit it and let this app relaunch it), and run again."
        )
    with open(pf, "wb") as f:
        f.write(data.replace(off, on))


def resolve_path_input(raw_path):
    """Resolve a user-supplied file or folder path, preserving trailing spaces if that exact path exists on disk."""
    if not raw_path:
        return ""
    expanded = os.path.expanduser(str(raw_path).strip("\r\n\t"))
    if os.path.exists(expanded):
        return expanded
    stripped = expanded.strip()
    if stripped and os.path.exists(stripped):
        return stripped
    return stripped or expanded


def create_flat_slate_folder(out_dir):
    """Standalone slates: a single flat output folder (.mov only, no ProRes/h264 subfolders)."""
    out_dir = resolve_path_input(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    return {
        "base": out_dir,
        "slated_prores": out_dir,
        "slated_h264": "",
        "unslated_prores": "",
        "unslated_h264": "",
        "presets_dir": os.path.join(out_dir, "_AME_Presets"),
    }


def ensure_ame_presets(presets_dir):
    """Ensure the two exact Adobe Media Encoder (.epr) preset files exist in `presets_dir`:
    1. ProRes Master (.mov): Apple ProRes 422 HQ, Match Source resolution & frame rate
    2. MP4 (.mp4): H.264, Match Source resolution & frame rate, 25 Mbps target bitrate
    Also resolves the bundled After Effects OutputModule seed project."""
    os.makedirs(presets_dir, exist_ok=True)
    prores_dst = os.path.join(presets_dir, "SuperJoy_Apple_ProRes_422_HQ_MatchSource.epr")
    h264_dst = os.path.join(presets_dir, "SuperJoy_H264_MatchSource_25Mbps.epr")

    bundled_presets_dir = os.path.join(_APP_DIR, "presets")
    bundled_prores = os.path.join(bundled_presets_dir, "SuperJoy_Apple_ProRes_422_HQ_MatchSource.epr")
    bundled_h264 = os.path.join(bundled_presets_dir, "SuperJoy_H264_MatchSource_25Mbps.epr")
    bundled_seed_aep = os.path.join(bundled_presets_dir, "SuperJoy_AE_OutputTemplates_Seed.aep")

    # 1. Resolve Apple ProRes 422 HQ (Match Source)
    if os.path.isfile(bundled_prores):
        shutil.copyfile(bundled_prores, prores_dst)
    else:
        prores_candidates = sorted(
            glob.glob(
                "/Applications/Adobe Media Encoder */Adobe Media Encoder *.app/Contents/MediaIO/systempresets/3F3F3F3F_4D6F6F56/Apple ProRes 422 HQ.epr"
            ),
            reverse=True,
        )
        if prores_candidates and os.path.isfile(prores_candidates[0]):
            shutil.copyfile(prores_candidates[0], prores_dst)

    # 2. Resolve H.264 Match Source 25 Mbps
    if os.path.isfile(bundled_h264):
        shutil.copyfile(bundled_h264, h264_dst)
    else:
        h264_candidates = sorted(
            glob.glob(
                "/Applications/Adobe Media Encoder */Adobe Media Encoder *.app/Contents/MediaIO/systempresets/4E49434B_48323634/00 - Match Source - High bitrate.epr"
            ),
            reverse=True,
        )
        if h264_candidates and os.path.isfile(h264_candidates[0]):
            with open(h264_candidates[0], "r", encoding="utf-8") as f:
                xml_text = f.read()
            xml_text = re.sub(
                r"<PresetName>.*?</PresetName>",
                "<PresetName>SuperJoy H.264 Match Source 25Mbps</PresetName>",
                xml_text,
                count=1,
            )
            xml_text = re.sub(
                r"(<ParamValue>)10\.(</ParamValue>\s*<ParamType>3</ParamType>[\s\S]{0,220}?<ParamIdentifier>ADBEVideoTargetBitrate</ParamIdentifier>)",
                r"\g<1>25.\g<2>",
                xml_text,
                count=1,
            )
            xml_text = re.sub(
                r"(<ParamValue>)12\.(</ParamValue>\s*<ParamType>3</ParamType>[\s\S]{0,220}?<ParamIdentifier>ADBEVideoMaxBitrate</ParamIdentifier>)",
                r"\g<1>25.\g<2>",
                xml_text,
                count=1,
            )
            with open(h264_dst, "w", encoding="utf-8") as f:
                f.write(xml_text)

    return {
        "prores_epr": prores_dst if os.path.isfile(prores_dst) else "",
        "h264_epr": h264_dst if os.path.isfile(h264_dst) else "",
        "ae_seed_aep": bundled_seed_aep if os.path.isfile(bundled_seed_aep) else "",
    }



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


class BrandLogo(tk.Canvas):
    """Branded emblem in the top right header.
    - SuperJoy: Coral-red rounded square with dark smiley face badge.
    - MSTR-SL8R: Deep noir badge with electric aqua border and 'M8' studio monogram."""

    def __init__(self, parent, size=46):
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_DARK
        super().__init__(parent, width=size, height=size, bg=parent_bg, highlightthickness=0, bd=0, takefocus=0)
        theme_cfg = THEMES.get(ACTIVE_THEME, THEMES["superjoy"])
        if theme_cfg.get("logo_style") == "mstr_sl8r":
            round_rect(self, 0, 0, size, size, size * 0.22, fill=BG_CARD, outline=ACCENT_RED)
            self.create_text(
                size / 2,
                size / 2,
                text="M8",
                font=(FONT, int(size * 0.44), "bold"),
                fill=ACCENT_RED,
            )
        else:
            round_rect(self, 0, 0, size, size, size * 0.20, fill=ACCENT_RED, outline=ACCENT_RED)
            c, rad, lw = size / 2, size * 0.31, max(2.5, size / 14)
            self.create_oval(c - rad, c - rad, c + rad, c + rad, outline=BG_DARK, width=lw)
            ey1, ey2, ex = c - rad * 0.38, c - rad * 0.05, rad * 0.28
            for dx in (-ex, ex):
                self.create_line(c + dx, ey1, c + dx, ey2, fill=BG_DARK, width=lw, capstyle="round")
            self.create_arc(c - rad * 0.48, c - rad * 0.32, c + rad * 0.48, c + rad * 0.52,
                            start=200, extent=140, style="arc", outline=BG_DARK, width=lw)


SJLogo = BrandLogo



class HelpCircleButton(tk.Canvas):
    """Circular '?' help button designed for macOS Tk single-tap response."""

    def __init__(self, parent, size=32, command=None, bg_fill=BG_GREY, fg=TEXT_LIGHT):
        parent_bg = parent.cget("bg") if "bg" in parent.keys() else BG_DARK
        super().__init__(parent, width=size, height=size, bg=parent_bg, highlightthickness=0, bd=0, takefocus=0)
        self._size = size
        self._cmd = command
        self._bg_fill = bg_fill
        self._fg = fg
        self._last_fire = 0.0
        self._hover = False
        self._circle = self.create_oval(1, 1, size - 1, size - 1, fill=bg_fill, outline=BORDER_SUBTLE, width=1.5)
        self._text = self.create_text(
            size / 2,
            size / 2,
            text="?",
            font=(FONT, int(size * 0.46), "bold"),
            fill=fg,
        )

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<Double-Button-1>", self._on_press)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e=None):
        self._hover = True
        self.itemconfigure(self._circle, fill=ACCENT_RED, outline=ACCENT_RED)
        self.itemconfigure(self._text, fill=TEXT_LIGHT)

    def _on_leave(self, _e=None):
        self._hover = False
        self.itemconfigure(self._circle, fill=self._bg_fill, outline=BORDER_SUBTLE)
        self.itemconfigure(self._text, fill=self._fg)

    def _on_press(self, _e=None):
        now = time.monotonic()
        if now - self._last_fire < 0.16:
            return "break"
        self._last_fire = now
        if self._cmd:
            self.after_idle(self._cmd)
        return "break"


class SlatePreviewViewer(tk.Toplevel):
    """Dependency-free static slate preview gallery (macOS native via sips & Tk PhotoImage).
    Lets users flip through the first frame (time = 0.0s) of every generated slate comp."""

    def __init__(self, parent, preview_items, initial_index=0):
        super().__init__(parent)
        self.preview_items = [p for p in (preview_items or []) if p and os.path.isfile(p.get("image_path", ""))]
        self.current_idx = max(0, min(initial_index, len(self.preview_items) - 1)) if self.preview_items else 0
        self._thumb_cache = {}
        self._photo_ref = None

        theme_cfg = THEMES.get(ACTIVE_THEME, THEMES["superjoy"])
        app_name = theme_cfg.get("app_name", "SuperJoy Slating Workstation")
        self.title(f"{app_name}  •  Slate Preview Gallery")
        self.geometry("900x720")
        self.minsize(740, 580)
        self.configure(bg=BG_DARK)
        self.transient(parent)

        self._build_ui()
        self._bind_keys()
        self._show_current()

    def _build_ui(self):
        # Header Info Card
        hdr = RoundedCard(self, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=12, pad=12)
        hdr.pack(fill="x", padx=18, pady=(14, 8))
        hb = hdr.body

        top_row = tk.Frame(hb, bg=BG_CARD)
        top_row.pack(fill="x")
        self.spot_counter_lbl = tk.Label(top_row, text="", font=(FONT, 14, "bold"), bg=BG_CARD, fg=ACCENT_RED)
        self.spot_counter_lbl.pack(side="left")
        self.aspect_lbl = tk.Label(top_row, text="", font=(FONT, 12, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.aspect_lbl.pack(side="right")

        self.title_lbl = tk.Label(hb, text="", font=(FONT, 13), bg=BG_CARD, fg=TEXT_LIGHT, anchor="w", justify="left")
        self.title_lbl.pack(fill="x", pady=(4, 0))
        bind_auto_wrap(self.title_lbl, hb)

        # Footer Navigation Bar - MUST be packed on bottom FIRST so it is permanently pinned on screen
        nav = tk.Frame(self, bg=BG_DARK)
        nav.pack(side="bottom", fill="x", padx=18, pady=(8, 14))

        self.btn_prev = RoundedButton(
            nav, text="◀ Previous", command=self.prev_slate, color=BG_GREY, padx=20, pady=8, radius=10
        )
        self.btn_prev.pack(side="left")

        self.btn_next = RoundedButton(
            nav, text="Next ▶", command=self.next_slate, color=ACCENT_RED, padx=24, pady=8, radius=10
        )
        self.btn_next.pack(side="left", padx=(10, 0))

        self.btn_folder = RoundedButton(
            nav, text="Open Folder", command=self._open_containing_folder, color=BG_BLUE, padx=16, pady=8, radius=10
        )
        self.btn_folder.pack(side="right")

        self.btn_close = RoundedButton(
            nav, text="Close", command=self.destroy, color=BG_DARKER, padx=18, pady=8, radius=10
        )
        self.btn_close.pack(side="right", padx=(0, 10))

        # Image Display Area - packed after nav to fill remaining space
        img_wrap = tk.Frame(self, bg=BG_DARKER, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        img_wrap.pack(side="top", fill="both", expand=True, padx=18, pady=6)
        self.img_label = tk.Label(img_wrap, bg=BG_DARKER)
        self.img_label.pack(fill="both", expand=True, padx=10, pady=10)
        self.img_label.bind("<Configure>", self._on_resize_viewport)

    def _bind_keys(self):
        self.bind("<Left>", lambda _e: self.prev_slate())
        self.bind("<Right>", lambda _e: self.next_slate())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<space>", lambda _e: self.next_slate())

    def _on_resize_viewport(self, event):
        # Debounce or redraw current image when window is noticeably resized
        if event.width > 100 and event.height > 100:
            self._show_current()

    def prev_slate(self):
        if not self.preview_items:
            return
        if self.current_idx > 0:
            self.current_idx -= 1
            self._show_current()

    def next_slate(self):
        if not self.preview_items:
            return
        if self.current_idx < len(self.preview_items) - 1:
            self.current_idx += 1
            self._show_current()

    def _show_current(self):
        if not self.preview_items:
            self.spot_counter_lbl.config(text="No slate previews available")
            self.title_lbl.config(text="")
            self.aspect_lbl.config(text="")
            self.img_label.config(image="", text="No preview snapshot found.", fg=TEXT_MUTED)
            return

        item = self.preview_items[self.current_idx]
        total = len(self.preview_items)
        ad_id = item.get("id", "UNKNOWN")
        aspect = item.get("aspect", "")
        title = item.get("title", "")
        img_path = item.get("image_path", "")

        self.spot_counter_lbl.config(text=f"Spot {self.current_idx + 1} of {total}:  {ad_id}")
        self.aspect_lbl.config(text=f"[{aspect}]" if aspect else "")
        self.title_lbl.config(text=f"Title: {title}" if title else f"File: {os.path.basename(img_path)}")

        # Update button states
        if self.current_idx == 0:
            self.btn_prev.config(state="disabled")
        else:
            self.btn_prev.config(state="normal")

        if self.current_idx == total - 1:
            self.btn_next.config(state="disabled")
        else:
            self.btn_next.config(state="normal")

        # Load & display image
        photo = self._get_scaled_photo(img_path)
        if photo:
            self._photo_ref = photo  # keep reference to prevent garbage collection
            self.img_label.config(image=photo, text="")
        else:
            self.img_label.config(image="", text=f"Could not load preview:\n{img_path}", fg=ACCENT_RED)

    def _get_scaled_photo(self, src_path):
        if not src_path or not os.path.isfile(src_path):
            return None

        # Determine target bounding box based on current window/viewport size
        vw = max(360, self.img_label.winfo_width() - 20) if self.img_label.winfo_width() > 100 else 760
        vh = max(240, self.img_label.winfo_height() - 20) if self.img_label.winfo_height() > 100 else 460

        cache_key = (src_path, vw // 20, vh // 20)  # bucket to avoid rescales on 1px jitter
        if cache_key in self._thumb_cache and os.path.isfile(self._thumb_cache[cache_key]):
            try:
                return tk.PhotoImage(file=self._thumb_cache[cache_key])
            except Exception:
                pass

        # Use macOS built-in /usr/bin/sips to probe source dimensions and downscale cleanly
        import tempfile
        out_thumb = tempfile.mktemp(prefix="sj_prev_", suffix=".png")
        try:
            # Query source width & height using sips
            dim_res = subprocess.run(
                ["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", src_path],
                capture_output=True,
                text=True,
            )
            src_w, src_h = 1920, 1080
            for line in dim_res.stdout.splitlines():
                if "pixelWidth:" in line:
                    src_w = int(line.split(":")[-1].strip())
                elif "pixelHeight:" in line:
                    src_h = int(line.split(":")[-1].strip())

            # Scale to fit strictly inside (vw, vh) bounding box
            scale = min(vw / max(1, src_w), vh / max(1, src_h))
            target_w = max(1, int(src_w * scale))
            target_h = max(1, int(src_h * scale))

            subprocess.run(
                ["/usr/bin/sips", "-z", str(target_h), str(target_w), src_path, "--out", out_thumb],
                check=True,
                capture_output=True,
                text=True,
            )
            photo = tk.PhotoImage(file=out_thumb)
            self._thumb_cache[cache_key] = out_thumb
            return photo
        except Exception:
            try:
                return tk.PhotoImage(file=src_path)
            except Exception:
                return None

    def _open_containing_folder(self):
        if not self.preview_items:
            return
        item = self.preview_items[self.current_idx]
        p = item.get("image_path", "")
        if p and os.path.exists(p):
            subprocess.Popen(["open", "-R", p])


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
    def __init__(self, root, theme=None):
        global FONT
        if theme:
            set_theme(theme)
        self.theme_name = ACTIVE_THEME
        self.theme_cfg = THEMES.get(self.theme_name, THEMES["superjoy"])

        self.root = root
        FONT = pick_font_family()
        for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(fname).configure(family=FONT)
            except Exception:
                pass

        self.root.title(self.theme_cfg.get("app_title", "SuperJoy Broadcast Slating Workstation"))
        self.root.geometry("1020x840")
        self.root.minsize(940, 770)
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
        self.tsv_path = tk.StringVar(
            value=DEFAULT_SPREADSHEET_XLSX if os.path.exists(DEFAULT_SPREADSHEET_XLSX) else ""
        )
        self.template_dir = tk.StringVar(
            value=DEFAULT_TEMPLATE_AEP if os.path.exists(DEFAULT_TEMPLATE_AEP) else ""
        )
        self.videos_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.unslate_dir = tk.StringVar()
        self.marry_slates_dir = tk.StringVar()
        self.marry_csv_path = tk.StringVar()
        self.output_mode_var = tk.StringVar(value="slates_only")  # 'slated_masters' or 'slates_only'
        self.auto_transcode_var = tk.BooleanVar(value=True)  # ProRes 422 HQ (.mov) + H.264 25Mbps (.mp4) + Unslated
        self.fps_var = tk.StringVar(value=DEFAULT_FPS_LABEL)
        self.aspect_var = tk.StringVar(value=DEFAULT_ASPECT)
        self.active_tab_var = tk.StringVar(value="1")  # Open on Batch Slate Builder by default
        self.manual_batch_data = []
        self.marry_pairs_data = []
        self.latest_previews = []
        self.preview_viewer_window = None
        self._loading_row = False

        # Shared campaign fields (filled in by user) + per-spot fields (pulled from master video filenames or spreadsheet)
        self.f_agency = tk.StringVar(value=DEFAULT_AGENCY)
        self.f_client = tk.StringVar()
        self.f_title = tk.StringVar()
        self.f_id = tk.StringVar()
        self.f_trt = tk.StringVar()
        self.f_date = tk.StringVar(value=today_yyyy_mm_dd())
        self.f_workspace = tk.StringVar()
        self.f_audio = tk.StringVar(value="STEREO")
        self.f_copyright = tk.StringVar()
        self.f_flame = tk.BooleanVar(value=False)
        self.f_nfa = tk.BooleanVar(value=False)

        self.create_widgets()

        # Live status & auto-sync traces
        self.template_dir.trace_add("write", lambda *_: self.update_asset_badges())
        self.videos_dir.trace_add("write", lambda *_: self._on_videos_dir_changed())
        self.output_dir.trace_add("write", lambda *_: self._on_output_dir_changed())
        self.tsv_path.trace_add("write", lambda *_: self.update_file_preview())
        self.unslate_dir.trace_add("write", lambda *_: self.update_unslate_preview())
        self.marry_slates_dir.trace_add("write", lambda *_: self.update_marry_preview())
        self.marry_csv_path.trace_add("write", lambda *_: self.update_marry_preview())
        self.output_mode_var.trace_add("write", lambda *_: self._on_output_mode_changed())
        self.auto_transcode_var.trace_add("write", lambda *_: self.update_asset_badges())
        self.auto_transcode_var.trace_add("write", lambda *_: self._on_output_mode_changed())
        self._on_output_mode_changed()
        self.update_asset_badges()
        if self.tsv_path.get().strip():
            self.update_file_preview()

        # Propagate shared campaign metadata edits to queued batch items in real time
        for shared_var in (
            self.f_agency,
            self.f_client,
            self.f_workspace,
            self.f_copyright,
            self.f_date,
            self.f_audio,
        ):
            shared_var.trace_add("write", lambda *_: self._sync_shared_fields_to_batch(sync_flame=False))
        self.f_flame.trace_add("write", lambda *_: self._sync_shared_fields_to_batch(sync_flame=True))
        self.f_nfa.trace_add("write", lambda *_: self._sync_shared_fields_to_batch(sync_nfa=True))

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

    def _browse_file(self, target_var, title="Select Spreadsheet / Metadata File (.xlsx, .tsv, .csv, .txt)"):
        def _open():
            reset_tk_mouse_state(self.root)
            cur = target_var.get().strip()
            init_dir = os.path.dirname(cur) if cur and os.path.exists(cur) else os.path.dirname(DEFAULT_SPREADSHEET_XLSX)
            chosen = filedialog.askopenfilename(
                parent=self.root,
                title=title,
                initialdir=init_dir,
                filetypes=METADATA_FILETYPES,
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
        header.pack(side="top", fill="x", padx=24, pady=(8, 3))

        title_col = tk.Frame(header, bg=BG_DARK)
        title_col.pack(side="left")
        title_row = tk.Frame(title_col, bg=BG_DARK)
        title_row.pack(anchor="w")
        tk.Label(
            title_row,
            text=self.theme_cfg.get("header_title_bold", "SUPERJOY"),
            font=(FONT, 22, "bold"),
            bg=BG_DARK,
            fg=ACCENT_RED,
        ).pack(side="left")
        tk.Label(
            title_row,
            text=self.theme_cfg.get("header_title_sub", "  SLATING WORKSTATION"),
            font=(FONT, 22, "bold"),
            bg=BG_DARK,
            fg=TEXT_LIGHT,
        ).pack(side="left")
        tk.Label(
            title_col,
            text=self.theme_cfg.get("tagline", "Broadcast Slate Automation  •  ProRes 422 HQ + H.264 (25Mbps)  •  SLATED & UNSLATED Delivery"),
            font=(FONT, 11),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))

        BrandLogo(header, 46).pack(side="right", padx=(12, 0))
        self.btn_update = mkbtn(
            header,
            text="↻ Update App",
            bg=BG_BLUE,
            command=self.prompt_self_update,
            padx=14,
            pady=6,
        )
        self.btn_update.pack(side="right", padx=(8, 4))
        self.btn_view_previews = mkbtn(
            header,
            text="👁 Slate Previews",
            bg=BG_GREY,
            command=self.open_preview_viewer,
            padx=14,
            pady=6,
        )
        self.btn_view_previews.pack(side="right", padx=(4, 4))

        # 2. Pinned Bottom Action Footer (packed BEFORE expandable workspace so it is NEVER clipped!)
        footer = tk.Frame(self.root, bg=BG_DARK)
        footer.pack(side="bottom", fill="x", padx=24, pady=(4, 8))

        self.btn_run = RoundedButton(
            footer,
            text="GENERATE .AEP & QUEUE IN AME",
            command=self.execute_workflow_thread,
            color=ACCENT_RED,
            font_spec=(FONT, 15, "bold"),
            padx=36,
            pady=10,
            radius=16,
        )
        self.btn_run.pack(anchor="center")

        self.btn_help = HelpCircleButton(
            footer,
            size=30,
            command=self.open_readme,
            bg_fill=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.btn_help.place(relx=1.0, rely=0.5, anchor="e")

        # 3. Master Assets Card
        assets_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=10)
        assets_card.pack(side="top", fill="x", padx=24, pady=(0, 5))
        ab = assets_card.body
        ab.columnconfigure(1, weight=1)

        hdr_row = tk.Frame(ab, bg=BG_CARD)
        hdr_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 3))
        tk.Label(
            hdr_row,
            text="MASTER ASSETS, OUTPUT DESTINATION & STUDIO CONFORM",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(side="left")
        self.asset_status_lbl = tk.Label(
            hdr_row,
            text="Select .aep template, master videos & output folder",
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
            pady=4,
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
            pady=4,
        ).grid(row=2, column=2, pady=2)

        tk.Label(ab, text="OUTPUT FOLDER", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW).grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(ab, self.output_dir, 38).grid(row=3, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            ab,
            text="Browse",
            command=lambda: self._browse_dir(
                self.output_dir,
                "Select Output Folder (Creates SLATED/ProRes, SLATED/h264, UNSLATED/ProRes, UNSLATED/h264)",
            ),
            padx=18,
            pady=4,
        ).grid(row=3, column=2, pady=2)

        # Fallback FPS & Aspect Pill Bar (No ttk.Combobox!)
        tk.Label(ab, text="STUDIO STANDARD", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=4, column=0, sticky="w", padx=(0, 10), pady=(3, 2)
        )
        std_row = tk.Frame(ab, bg=BG_CARD)
        std_row.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(3, 2))

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
            pad_x=9,
            pad_y=3,
            radius=8,
        )
        self.aspect_pills.pack(side="left")

        self.res_label = tk.Label(std_row, text="", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.res_label.pack(side="left", padx=(8, 0))
        self.aspect_var.trace_add("write", lambda *_: self.update_res_label())
        self.update_res_label()

        # Output Mode Row: Slated Masters (Slate + Video) vs Standalone Slates Only + Auto-Transcode Toggle
        tk.Label(ab, text="BUILD OUTPUT MODE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW).grid(
            row=5, column=0, sticky="w", padx=(0, 10), pady=(3, 1)
        )
        mode_row = tk.Frame(ab, bg=BG_CARD)
        mode_row.grid(row=5, column=1, columnspan=2, sticky="ew", pady=(3, 1))
        self.output_mode_pills = SegmentedPills(
            mode_row,
            [
                ("slated_masters", "Slated Masters (Slate + Video)"),
                ("slates_only", "Standalone Slates Only (No Video)"),
            ],
            variable=self.output_mode_var,
            font_spec=(FONT, 10, "bold"),
            pad_x=11,
            pad_y=3,
            radius=8,
        )
        self.output_mode_pills.pack(side="left")
        self.transcode_toggle = RoundedToggle(
            mode_row,
            "Auto-Transcode ProRes 422 HQ + H.264 (25Mbps)",
            self.auto_transcode_var,
            font_spec=(FONT, 10, "bold"),
        )
        self.transcode_toggle.pack(side="left", padx=(12, 0))
        # Hint gets its own row so it is never clipped at narrow window widths
        self.output_mode_hint = tk.Label(
            ab,
            text="SLATED & UNSLATED (ProRes + h264)",
            font=(FONT, 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
            anchor="w",
            justify="left",
        )
        self.output_mode_hint.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(0, 2))

        # 4. Segmented Mode Tab Bar (4 Focused Broadcast Modes)
        tab_bar_frame = tk.Frame(self.root, bg=BG_DARK)
        tab_bar_frame.pack(side="top", fill="x", padx=24, pady=(2, 4))

        self.tab_pills = SegmentedPills(
            tab_bar_frame,
            [
                ("1", "1. Batch Slate Builder"),
                ("0", "2. XLSX / CSV / TSV Import"),
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
        self.workspace_card = RoundedCard(self.root, bg_fill=BG_CARD, border_color=BORDER_SUBTLE, radius=16, pad=12)
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
            text="SPREADSHEET (.XLSX / .TSV / .CSV) IMPORT  •  COMP RESOLUTION ROUTING & VIDEO SYNC",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(2, 2))
        desc_lbl = tk.Label(
            p,
            text="Import 'Slates From Spreadsheet_Template_001.xlsx' directly (or .tsv/.csv/.txt). Column 1 (COMP: 16x9, 4x5, 9x16, 1x1, 2x3) routes each row to its exact template comp in the .aep.",
            font=(FONT, 11),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        desc_lbl.pack(anchor="w", pady=(0, 8))
        bind_auto_wrap(desc_lbl, p)

        f1 = tk.Frame(p, bg=BG_CARD)
        f1.pack(fill="x", pady=3)
        f1.columnconfigure(1, weight=1)
        tk.Label(f1, text="SPREADSHEET FILE", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        RoundedEntry(f1, self.tsv_path, 40).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        mkbtn(
            f1,
            text="Browse .XLSX / .TSV",
            command=lambda: self._browse_file(self.tsv_path),
            padx=16,
            pady=7,
        ).grid(row=0, column=2)

        self.file_preview_lbl = tk.Label(
            p,
            text="No metadata file selected.",
            font=(FONT, 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        )
        self.file_preview_lbl.pack(anchor="w", pady=(6, 8))
        bind_auto_wrap(self.file_preview_lbl, p)

        # Action toolbar for combining Spreadsheet with Master Videos & Queue
        csv_bar = tk.Frame(p, bg=BG_CARD)
        csv_bar.pack(fill="x", pady=(0, 8))
        mkbtn(
            csv_bar,
            text="New Spreadsheet Template",
            bg=ACCENT_RED,
            command=self.create_copy_of_template_spreadsheet,
            padx=14,
            pady=6,
        ).pack(side="left")
        mkbtn(
            csv_bar,
            text="Load Spreadsheet into Batch Slate Builder",
            bg=BG_BLUE,
            command=lambda: self.load_csv_into_batch_builder(switch_to_builder=True),
            padx=14,
            pady=6,
        ).pack(side="left", padx=(8, 0))
        mkbtn(
            csv_bar,
            text="Rename Master Video Files from Spreadsheet",
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
            text="NATIVE .XLSX SPREADSHEET & DELIVERY FOLDER STRUCTURE",
            font=(FONT, 11, "bold"),
            bg=BG_DARKER,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(0, 5))
        steps = (
            "• Direct .XLSX Import: Load your Excel spreadsheet directly — no need to export a tab-delimited .txt file first.\n"
            "• Automatic COMP Routing: The first column (COMP: 16x9, 4x5, 9x16, 1x1, 2x3) directs each slate to its matching comp in sj_Slates From Spreadsheet_Template_006.aep.\n"
            "• Delivery Folders: Exports organize automatically into SLATED/ProRes (.mov 422 HQ), SLATED/h264 (.mp4 25Mbps), UNSLATED/ProRes (.mov 422 HQ), and UNSLATED/h264 (.mp4 25Mbps)."
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
            text="Set Global Output Folder above OR Per-Slate Output Folder below",
            font=(FONT, 10),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        ).pack(side="right")

        form_frame = tk.Frame(p, bg=BG_CARD)
        form_frame.pack(fill="x", pady=(0, 2))
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
        sec2_hdr.pack(fill="x", pady=(2, 1))
        tk.Label(
            sec2_hdr,
            text="SPOT METADATA (AUTO-PULLED FROM VIDEOS / .XLSX  •  OR ENTER MANUALLY FOR STANDALONE SLATES)",
            font=(FONT, 10, "bold"),
            bg=BG_CARD,
            fg=ACCENT_YELLOW,
        ).pack(side="left")

        spot_frame = tk.Frame(p, bg=BG_CARD)
        spot_frame.pack(fill="x", pady=(0, 2))
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
            row=0, column=6, sticky="e", padx=(2, 6), pady=2
        )
        RoundedToggle(spot_frame, "NFA (Not For Air)", self.f_nfa, font_spec=(FONT, 11, "bold")).grid(
            row=0, column=7, sticky="e", padx=(2, 0), pady=2
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
                ("2x3", "2x3 (1080×1620)"),
                ("ALL", "ALL"),
            ],
            initial=[DEFAULT_ASPECT],
            font_spec=(FONT, 10, "bold"),
            pad_x=8,
            pad_y=3,
        )
        self.batch_res_pills.pack(side="left")
        mkbtn(
            res_row,
            text="Apply Res to Selected",
            bg=BG_BLUE,
            command=self.apply_res_to_selected,
            padx=11,
            pady=4,
        ).pack(side="right")

        # Action & Queue Toolbar
        bar = tk.Frame(p, bg=BG_CARD)
        bar.pack(fill="x", pady=(2, 3))
        mkbtn(
            bar,
            text="New Spreadsheet",
            bg=ACCENT_RED,
            command=self.create_copy_of_template_spreadsheet,
            padx=9,
            pady=5,
        ).pack(side="left")
        mkbtn(
            bar,
            text="Auto-Pull Videos",
            bg=BG_BLUE,
            command=lambda: self.populate_batch_from_videos(notify_if_empty=True),
            padx=9,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="Import .XLSX / CSV",
            bg=BG_BLUE,
            command=self.prompt_and_merge_csv_into_batch,
            padx=9,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="+ Add / Update",
            bg="#4CAF50",
            command=self.add_to_batch,
            padx=9,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="Set Output Folder",
            bg=BG_GREY,
            command=self.set_output_folder_for_selection,
            padx=9,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(
            bar,
            text="Cycle Res",
            bg=BG_GREY,
            command=self.cycle_selected_resolution,
            padx=8,
            pady=5,
        ).pack(side="left", padx=(5, 0))
        mkbtn(bar, text="Remove", bg=BG_GREY, command=self.remove_from_batch, padx=8, pady=5).pack(
            side="left", padx=(5, 0)
        )
        mkbtn(bar, text="Clear", bg=BG_GREY, command=self.clear_batch, padx=8, pady=5).pack(
            side="left", padx=(5, 0)
        )
        self.batch_count_lbl = tk.Label(
            bar, text="0 slates in queue", font=(FONT, 11, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW
        )
        self.batch_count_lbl.pack(side="right", padx=4)

        # Queue Table (tapping COMP/RES cycles resolution; tapping FLAME toggles y/n; tapping NFA toggles NFA; tapping OUTPUT FOLDER sets per-slate output dir)
        tree_wrap = tk.Frame(p, bg=BORDER_SUBTLE, bd=0, highlightthickness=0)
        tree_wrap.pack(fill="both", expand=True, pady=(2, 0))
        columns = ("id", "title", "res", "trt", "flame", "nfa", "client", "output")
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=4)
        self.tree.heading("id", text="AD-ID")
        self.tree.heading("title", text="TITLE")
        self.tree.heading("res", text="COMP / RES (TAP)")
        self.tree.heading("trt", text="TRT")
        self.tree.heading("flame", text="FLAME")
        self.tree.heading("nfa", text="NFA (TAP)")
        self.tree.heading("client", text="CLIENT")
        self.tree.heading("output", text="OUTPUT FOLDER (TAP)")
        self.tree.column("id", width=100, minwidth=75, anchor="w")
        self.tree.column("title", width=190, minwidth=120, anchor="w", stretch=True)
        self.tree.column("res", width=135, minwidth=110, anchor="center")
        self.tree.column("trt", width=50, minwidth=40, anchor="center")
        self.tree.column("flame", width=50, minwidth=40, anchor="center")
        self.tree.column("nfa", width=65, minwidth=50, anchor="center")
        self.tree.column("client", width=85, minwidth=70, anchor="w")
        self.tree.column("output", width=155, minwidth=110, anchor="w")
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
            text="Pairs already-rendered slates (.mov, .mp4, .mxf, .png, .tif, .psd, .jpg) with your Master Videos by Ad-ID (and aspect ratio), optionally applying canonical filenames from a Spreadsheet (.xlsx/.tsv/.csv), and exports to SLATED (ProRes + h264) & UNSLATED (ProRes + h264) in Adobe Media Encoder.",
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

        tk.Label(form, text="XLSX / CSV (OPTIONAL)", font=(FONT, 11, "bold"), bg=BG_CARD, fg=TEXT_MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=2
        )
        RoundedEntry(form, self.marry_csv_path, 36).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=2)
        mkbtn(
            form,
            text="Browse Sheet",
            command=lambda: self._browse_file(self.marry_csv_path, "Select Optional .XLSX/.CSV/.TSV for Accurate Naming"),
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
        self.marry_tree.heading("output", text="DELIVERY STEM (SLATED/ProRes & h264)")
        self.marry_tree.column("id", width=110, minwidth=85, anchor="w")
        self.marry_tree.column("slate", width=230, minwidth=150, anchor="w")
        self.marry_tree.column("video", width=230, minwidth=150, anchor="w")
        self.marry_tree.column("output", width=270, minwidth=170, anchor="w", stretch=True)
        self.marry_tree.pack(fill="both", expand=True, padx=1, pady=1)

    def _build_tab_unslate(self):
        p = self.tab_unslate
        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        pfx = theme_cfg.get("project_prefix", "SuperJoy")

        tk.Label(
            p,
            text="BATCH UN-SLATE (AE + MEDIA ENCODER 7.0s HEAD TRIM)",
            font=(FONT, 12, "bold"),
            bg=BG_CARD,
            fg=ACCENT_RED,
        ).pack(anchor="w", pady=(4, 2))
        unslate_desc = tk.Label(
            p,
            text=f"Builds non-destructive un-slated comps in After Effects (trimming the 5.0s slate + 2.0s black/2-pop leader), saves an editable {pfx}_Unslate_Project.aep for manual fixes, and queues ProRes 422 HQ (.mov) + H.264 25Mbps (.mp4) into UNSLATED/ProRes and UNSLATED/h264.",
            font=(FONT, 12),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        unslate_desc.pack(anchor="w", pady=(0, 14))
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
        self.unslate_preview_lbl.pack(anchor="w", pady=(12, 14))
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
            text=f"• Trims exactly 7.0 seconds from the head of every .mov, .mp4, and .mxf file (preserving picture/audio from 01:00:00:00 onward).\n"
                 f"• Saves {pfx}_Unslate_Project.aep so you can inspect timelines or make manual slip/trim adjustments.\n"
                 f"• Queues trimmed outputs in Adobe Media Encoder to UNSLATED/ProRes (Apple ProRes 422 HQ) and UNSLATED/h264 (H.264 25Mbps).",
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
        if hasattr(self, "transcode_toggle"):
            if slates_only:
                self.transcode_toggle.pack_forget()
            else:
                self.transcode_toggle.pack(side="left", padx=(12, 0))
        if hasattr(self, "output_mode_hint"):
            self.output_mode_hint.config(
                text=".mov only \u2192 single output folder (No Video)"
                if slates_only
                else (
                    "SLATED & UNSLATED (ProRes + h264)"
                    if self.auto_transcode_var.get()
                    else "SLATED (ProRes .mov only)"
                ),
                fg=ACCENT_YELLOW if slates_only else TEXT_MUTED,
            )
        if hasattr(self, "btn_run") and str(self.btn_run["state"]) == "normal":
            self.btn_run.config(text=self.run_label())
        self.update_asset_badges()

    def _on_output_dir_changed(self):
        self.update_asset_badges()
        if hasattr(self, "tree"):
            self._refresh_tree(preserve_selection=True)

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
        odir = self.output_dir.get().strip()
        tpls = find_templates(tdir)
        vcnt = 0
        if vdir and os.path.isdir(vdir):
            vcnt = sum(1 for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith("."))
        parts = []
        if tdir:
            if "_aep" in tpls:
                parts.append(f"Template: {os.path.basename(tpls['_aep'])}")
            else:
                found_keys = [k for k in ASPECT_RESOLUTIONS if k in tpls]
                found_str = ", ".join(found_keys) or "none"
                parts.append(f"Templates: {len(found_keys)}/5 ({found_str})")
        if self.output_mode_var.get() == "slates_only":
            parts.append("Mode: Standalone Slates")
        elif vdir:
            parts.append(f"Videos: {vcnt}")
        if odir:
            parts.append(f"Out: {os.path.basename(odir.rstrip(os.sep)) or odir}")
        self.asset_status_lbl.config(
            text="  •  ".join(parts) if parts else "Select .aep template, master videos & output folder",
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
            comp_summary = ", ".join(sorted({r.get("aspect", "16x9") for r in rows if r.get("aspect")}))
            comp_note = f"  •  Comps: {comp_summary}" if comp_summary else ""
            match_note = ""
            if vdir and os.path.isdir(vdir):
                all_vids = [f for f in os.listdir(vdir) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")]
                matched = sum(1 for r in rows if any(ad_id_matches(r.get("id", ""), vf) for vf in all_vids))
                match_note = f"  •  {matched}/{len(rows)} matched in Master Videos"
            self.file_preview_lbl.config(
                text=f"Loaded '{os.path.basename(path)}'  •  {len(rows)} slate row(s){comp_note}{match_note}",
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
            return "BUILD & RENDER STANDALONE SLATES (AE)"
        return "GENERATE .AEP & QUEUE IN AME"

    def open_readme(self):
        """Open the workstation documentation / README."""
        candidates = [
            DEFAULT_README,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "readme.txt"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
            os.path.join(_APP_DIR, "README.md"),
            os.path.join(os.path.dirname(sys.executable), "readme.txt"),
            os.path.join(os.path.dirname(sys.executable), "README.md"),
        ]
        target = None
        for c in candidates:
            if c and os.path.isfile(c):
                target = c
                break

        if target:
            try:
                subprocess.Popen(["open", target])
                return
            except Exception as e:
                self._alert("showwarning", "README", f"Could not launch viewer: {e}")
                return

        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        app_name = theme_cfg.get("app_name", "SuperJoy Slating Workstation")
        self._alert(
            "showinfo",
            app_name,
            f"{app_name} v1.0.0\n\n"
            "• Standalone Slates: Renders native resolution 5s slates directly in After Effects.\n"
            "• Slated Comps: 5s Slate + 2-Pop at 5:00 + 2s Black + Master Video.\n"
            "• Un-slated Comps: Clean master video exported starting at 01:00:00:00.\n"
            "• All slates use system-local typography."
        )

    def create_copy_of_template_spreadsheet(self):
        """Prompt user to save a new copy of the bundled spreadsheet template (.xlsx) and reveal/open it."""
        reset_tk_mouse_state(self.root)
        candidates = [
            DEFAULT_SPREADSHEET_XLSX,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "Slates From Spreadsheet_Template_001.xlsx"),
            os.path.join(_APP_DIR, "Slates From Spreadsheet_Template_001.xlsx"),
            os.path.join(os.path.dirname(sys.executable), "Slates From Spreadsheet_Template_001.xlsx"),
        ]
        src_template = None
        for c in candidates:
            if c and os.path.isfile(c):
                src_template = c
                break

        if not src_template:
            self._alert("showerror", "Template Not Found", "Could not locate the bundled 'Slates From Spreadsheet_Template_001.xlsx' template.")
            return

        init_dir = (
            resolve_path_input(self.tsv_path.get())
            or resolve_path_input(self.output_dir.get())
            or resolve_path_input(self.videos_dir.get())
            or os.path.expanduser("~/Documents")
        )
        if init_dir and os.path.isfile(init_dir):
            init_dir = os.path.dirname(init_dir)

        default_name = f"Slates From Spreadsheet_{today_yyyy_mm_dd()}.xlsx"
        save_dest = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save New Copy of Spreadsheet Template",
            initialdir=init_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook (*.xlsx)", "*.xlsx"), ("All Files", "*.*")],
        )
        wake_macos_window(self.root)
        if not save_dest:
            return

        try:
            shutil.copyfile(src_template, save_dest)
            self.tsv_path.set(save_dest)
            # Reveal the new copy in Finder and open it in Excel / Numbers
            try:
                subprocess.Popen(["open", "-R", save_dest])
                subprocess.Popen(["open", save_dest])
            except Exception:
                pass
            self._alert(
                "showinfo",
                "New Template Created",
                f"Created new spreadsheet template copy at:\n{save_dest}\n\n"
                "The file has been linked in your app and opened in your spreadsheet application."
            )
        except Exception as e:
            self._alert("showerror", "Save Error", f"Failed to save copy of spreadsheet template:\n{e}")

    def open_preview_viewer(self):
        """Open the static slate preview gallery viewer."""
        previews = [p for p in getattr(self, "latest_previews", []) if p and os.path.isfile(p.get("image_path", ""))]
        if not previews:
            # Check current output dir for any previously generated preview PNGs
            odir = resolve_path_input(self.output_dir.get())
            if odir and os.path.isdir(odir):
                pdir = os.path.join(odir, "_previews")
                if os.path.isdir(pdir):
                    pngs = sorted([f for f in os.listdir(pdir) if f.lower().endswith(".png") and not f.startswith(".")])
                    for png in pngs:
                        previews.append({
                            "id": png.replace("_preview.png", "").replace(".png", ""),
                            "aspect": "",
                            "title": png,
                            "image_path": os.path.join(pdir, png),
                        })
        if not previews:
            self._alert(
                "showinfo",
                "No Slate Previews",
                "No completed slate previews available yet.\n\n"
                "Run a batch in Standalone Slates or Slated Masters mode to automatically render preview snapshots.",
            )
            return

        if self.preview_viewer_window and self.preview_viewer_window.winfo_exists():
            self.preview_viewer_window.destroy()

        self.preview_viewer_window = SlatePreviewViewer(self.root, previews)
        self.preview_viewer_window.focus_set()

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
            "nfa": "NFA" if self.f_nfa.get() else "",
        }

    @staticmethod
    def _make_slate_entry(shared, ad_id, title, trt, aspect, prev=None):
        prev = prev or {}
        asp = aspect if aspect in ASPECT_RESOLUTIONS else DEFAULT_ASPECT
        ws = shared["workspace"] or prev.get("workspace", prev.get("workspace_artist", ""))
        dt = shared["date"] or prev.get("date", prev.get("day", today_yyyy_mm_dd()))
        prev_flame = str(prev.get("flame", "")).strip().lower()
        if prev_flame in ("y", "yes", "true", "1"):
            flame_val = "y"
        elif prev_flame in ("n", "no", "false", "0"):
            flame_val = "n"
        else:
            flame_val = shared["flame"]

        prev_nfa = str(prev.get("nfa", "")).strip()
        if prev_nfa:
            nfa_val = prev_nfa
        else:
            nfa_val = shared.get("nfa", "")
        return {
            "agency": shared["agency"] or prev.get("agency", "") or DEFAULT_AGENCY,
            "client": shared["client"] or prev.get("client", ""),
            "title": title,
            "name": prev.get("name") or title,
            "id": ad_id,
            "ad-id": ad_id,
            "trt": trt or prev.get("trt", ""),
            "aspect": asp,
            "comp": asp,
            "resolution": format_resolution_label(asp),
            "date": dt,
            "day": dt,
            "workspace": ws,
            "workspace_artist": ws,
            "audio": shared["audio"] or prev.get("audio", "STEREO"),
            "copyright": shared["copyright"] or prev.get("copyright", ""),
            "flame": flame_val,
            "nfa": nfa_val,
            "output_dir": prev.get("output_dir", ""),
        }

    def _format_output_cell(self, row):
        custom_out = (row.get("output_dir") or "").strip()
        if custom_out:
            base = os.path.basename(custom_out.rstrip(os.sep)) or custom_out
            return f"★ {base}"
        global_out = self.output_dir.get().strip()
        if global_out:
            base = os.path.basename(global_out.rstrip(os.sep)) or global_out
            return f"{base}/SLATED"
        return "Default (SLATED & UNSLATED)"

    def set_output_folder_for_selection(self, row_indices=None):
        """Set the output folder for selected individual slate(s), or for the entire batch if none selected."""
        if row_indices is None:
            selected = self.tree.selection()
            row_indices = [
                self.tree.index(s) for s in selected if 0 <= self.tree.index(s) < len(self.manual_batch_data)
            ]

        def _pick():
            reset_tk_mouse_state(self.root)
            if row_indices:
                title = (
                    f"Select Output Folder for Slate '{self.manual_batch_data[row_indices[0]].get('id', '')}'"
                    if len(row_indices) == 1
                    else f"Select Output Folder for {len(row_indices)} Selected Slates"
                )
            else:
                title = "Select Batch Output Folder (SLATED/ProRes, SLATED/h264, UNSLATED/ProRes, UNSLATED/h264)"
            chosen = filedialog.askdirectory(parent=self.root, title=title)
            wake_macos_window(self.root)
            if not chosen:
                return
            if row_indices:
                for idx in row_indices:
                    if 0 <= idx < len(self.manual_batch_data):
                        self.manual_batch_data[idx]["output_dir"] = chosen
                self._refresh_tree(preserve_selection=True)
            else:
                self.output_dir.set(chosen)
                for item in self.manual_batch_data:
                    item["output_dir"] = ""
                self._refresh_tree(preserve_selection=True)

        run_after_mouse_up(self.root, _pick)

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

    def _sync_shared_fields_to_batch(self, sync_flame=False, sync_nfa=False):
        """Keep Agency, Client, Workspace, Copyright, Date, Audio, and (when toggled) Flame/NFA synced
        across all queued batch items as the user types them in."""
        if self._loading_row or not self.manual_batch_data:
            return
        shared = self._current_campaign_fields()
        for item in self.manual_batch_data:
            if shared["agency"]:
                item["agency"] = shared["agency"]
            if shared["client"]:
                item["client"] = shared["client"]
            if shared["date"]:
                item["date"] = shared["date"]
                item["day"] = shared["date"]
            if shared["workspace"]:
                item["workspace"] = shared["workspace"]
                item["workspace_artist"] = shared["workspace"]
            if shared["audio"]:
                item["audio"] = shared["audio"]
            if shared["copyright"]:
                item["copyright"] = shared["copyright"]
            if sync_flame:
                item["flame"] = shared["flame"]
            if sync_nfa:
                item["nfa"] = shared["nfa"]
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
            slate["comp"] = asp
            slate["resolution"] = res_lbl
            flame_disp = "YES" if str(slate.get("flame", "n")).lower() in ("y", "yes", "true", "1") else "NO"
            nfa_val = str(slate.get("nfa", "")).strip()
            nfa_disp = "NFA" if (nfa_val and nfa_val.lower() not in ("0", "false", "no", "n")) else "AIR"
            out_disp = self._format_output_cell(slate)
            cid = self.tree.insert(
                "",
                "end",
                values=(
                    slate["id"],
                    slate["title"],
                    res_lbl,
                    slate["trt"],
                    flame_disp,
                    nfa_disp,
                    slate["client"],
                    out_disp,
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
        if 0 <= idx < len(self.manual_batch_data):
            # Single-tap on COMP/RES column (#3) cycles that individual slate's resolution
            if col_id == "#3":
                cur_asp = self.manual_batch_data[idx].get("aspect", DEFAULT_ASPECT)
                next_asp = (
                    ASPECT_KEYS[(ASPECT_KEYS.index(cur_asp) + 1) % len(ASPECT_KEYS)]
                    if cur_asp in ASPECT_KEYS
                    else DEFAULT_ASPECT
                )
                self.manual_batch_data[idx]["aspect"] = next_asp
                self.manual_batch_data[idx]["comp"] = next_asp
                self.manual_batch_data[idx]["resolution"] = format_resolution_label(next_asp)
                self._refresh_tree(preserve_selection=True)
            # Single-tap on FLAME column (#5) toggles Flame Logo y/n for that individual slate
            elif col_id == "#5":
                cur_fl = str(self.manual_batch_data[idx].get("flame", "n")).lower() in ("y", "yes", "true", "1")
                self.manual_batch_data[idx]["flame"] = "n" if cur_fl else "y"
                self._refresh_tree(preserve_selection=True)
            # Single-tap on NFA column (#6) toggles NFA / AIR for that individual slate
            elif col_id == "#6":
                cur_nfa = str(self.manual_batch_data[idx].get("nfa", "")).strip()
                is_nfa = bool(cur_nfa and cur_nfa.lower() not in ("0", "false", "no", "n"))
                self.manual_batch_data[idx]["nfa"] = "" if is_nfa else "NFA"
                self._refresh_tree(preserve_selection=True)
            # Single-tap on OUTPUT FOLDER column (#8) opens folder picker for that individual slate
            elif col_id == "#8":
                self.set_output_folder_for_selection([idx])
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
                self.f_flame.set(str(row.get("flame", "n")).lower() in ("y", "yes", "true", "1"))
                nfa_v = str(row.get("nfa", "")).strip()
                self.f_nfa.set(bool(nfa_v and nfa_v.lower() not in ("0", "false", "no", "n")))
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
        """Cycle the resolution (16x9 -> 1x1 -> 4x5 -> 9x16 -> 2x3) of the currently selected slate(s)."""
        selected = self.tree.selection()
        if not selected:
            self._alert("showinfo", "Select a Slate", "Tap a slate row in the queue table first (or tap its COMP/RES cell directly).")
            return
        new_aspects = []
        for s in selected:
            idx = self.tree.index(s)
            if 0 <= idx < len(self.manual_batch_data):
                cur_asp = self.manual_batch_data[idx].get("aspect", DEFAULT_ASPECT)
                next_asp = ASPECT_KEYS[(ASPECT_KEYS.index(cur_asp) + 1) % len(ASPECT_KEYS)] if cur_asp in ASPECT_KEYS else DEFAULT_ASPECT
                self.manual_batch_data[idx]["aspect"] = next_asp
                self.manual_batch_data[idx]["comp"] = next_asp
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
            new_asp = target_aspects[0]
            for idx in sel_indices:
                self.manual_batch_data[idx]["aspect"] = new_asp
                self.manual_batch_data[idx]["comp"] = new_asp
                self.manual_batch_data[idx]["resolution"] = format_resolution_label(new_asp)
            self._refresh_tree(preserve_selection=True)
        else:
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
        raw_title = sanitize_single_line(self.f_title.get())
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

        if len(selected_rows) == 1 and len(target_aspects) == 1:
            sel_idx = self.tree.index(selected_rows[0])
            if 0 <= sel_idx < len(self.manual_batch_data):
                existing = self.manual_batch_data[sel_idx]
                if existing.get("id", "").lower() == raw_id.lower():
                    updated_entry = self._make_slate_entry(
                        shared, raw_id, raw_title, raw_trt, target_aspects[0], existing
                    )
                    updated_entry["flame"] = "y" if self.f_flame.get() else "n"
                    updated_entry["nfa"] = "NFA" if self.f_nfa.get() else ""
                    self.manual_batch_data[sel_idx] = updated_entry
                    self._refresh_tree(preserve_selection=True)
                    return

        for asp in target_aspects:
            entry = self._make_slate_entry(shared, raw_id, raw_title, raw_trt, asp)
            entry["flame"] = "y" if self.f_flame.get() else "n"
            entry["nfa"] = "NFA" if self.f_nfa.get() else ""
            updated = False
            for i, existing in enumerate(self.manual_batch_data):
                if (
                    existing.get("id", "").lower() == raw_id.lower()
                    and existing.get("aspect", DEFAULT_ASPECT) == asp
                ):
                    entry["output_dir"] = existing.get("output_dir", "")
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
    # Spreadsheet (.XLSX / .CSV / .TSV) + Master Videos Combining & Renaming
    # ------------------------------------------------------------------
    def prompt_and_merge_csv_into_batch(self):
        """Let the user pick an .xlsx/.csv/.tsv/.txt file and load its rows into the Batch Builder queue."""
        def _pick():
            reset_tk_mouse_state(self.root)
            cur = self.tsv_path.get().strip()
            init_dir = os.path.dirname(cur) if cur and os.path.exists(cur) else os.path.dirname(DEFAULT_SPREADSHEET_XLSX)
            chosen = filedialog.askopenfilename(
                parent=self.root,
                title="Select Spreadsheet (.xlsx, .tsv, .csv, .txt) to Import into Batch Queue",
                initialdir=init_dir,
                filetypes=METADATA_FILETYPES,
            )
            wake_macos_window(self.root)
            if chosen:
                self.tsv_path.set(chosen)
                self.load_csv_into_batch_builder(csv_path=chosen, switch_to_builder=False)

        run_after_mouse_up(self.root, _pick)

    def load_csv_into_batch_builder(self, csv_path=None, switch_to_builder=True):
        """Combine rows from an .xlsx/.csv/.tsv/.txt metadata file with any Master Videos present in MASTER VIDEOS,
        populating the Batch Slate Builder queue with each row's COMP resolution and metadata."""
        path = (csv_path or self.tsv_path.get()).strip()
        if not path or not os.path.isfile(path):
            self._alert("showwarning", "Spreadsheet Required", "Please select an .xlsx, .tsv, .csv, or .txt metadata file first.")
            return 0

        try:
            csv_rows = parse_metadata_file(path)
        except Exception as e:
            self._alert("showerror", "Spreadsheet Parse Error", f"Failed to read metadata file:\n{e}")
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

        # Populate shared campaign fields from the first row that has them
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
            if first_row.get("nfa"):
                n_val = str(first_row["nfa"]).strip()
                self.f_nfa.set(bool(n_val and n_val.lower() not in ("0", "false", "no", "n")))
        finally:
            self._loading_row = False

        shared = self._current_campaign_fields()
        combined_batch = []

        for row in csv_rows:
            ad_id = row.get("id") or row.get("ad-id") or ""
            csv_title = row.get("title") or row.get("name") or ""
            csv_trt = row.get("trt") or ""
            row_aspect = (
                row.get("aspect")
                or detect_aspect_from_text(row.get("comp", ""))
                or detect_aspect_from_text(row.get("resolution", ""))
                or detect_aspect_from_text(csv_title)
            )

            matched_vids = [vf for vf in all_videos if ad_id and ad_id_matches(ad_id, vf)] if ad_id else []
            if matched_vids and not row_aspect:
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
        """Combine Master Videos with the loaded Spreadsheet/CSV metadata (or the Batch Slate Builder queue)
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
                self._alert("showerror", "Parse Error", f"Could not read metadata file:\n{e}")
                return 0
        elif self.manual_batch_data:
            rows = [normalize_slate_row(item) for item in self.manual_batch_data]

        if not rows:
            self._alert(
                "showwarning",
                "Metadata Required",
                "Please select an .xlsx / .csv / .tsv metadata file (or populate the Batch Slate Builder queue) first.",
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
                f"Renamed {renamed_count} master video file(s) to match canonical spreadsheet metadata:\n\n{preview}",
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
        used_slate_video_keys = set()

        for sf in slate_files:
            s_stem = re.sub(r"(?i)[_\-\s]*slate[ds]?$", "", os.path.splitext(sf)[0]).strip("_- ")
            s_id, s_title, _ = parse_video_filename(s_stem)
            s_aspect = detect_aspect_from_text(sf)
            if not s_id:
                continue

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
            if pair_key in used_slate_video_keys:
                continue
            used_slate_video_keys.add(pair_key)

            v_id, v_title, _ = parse_video_filename(matched_vf)
            eff_aspect = s_aspect or detect_aspect_from_text(matched_vf)
            csv_row = csv_by_id.get(s_id.lower()) or csv_by_id.get(v_id.lower())

            if csv_row:
                out_stem = build_canonical_delivery_stem(
                    csv_row, target_aspect=eff_aspect, include_aspect=bool(eff_aspect), suffix="Slated"
                )
                clean_stem = build_canonical_delivery_stem(
                    csv_row, target_aspect=eff_aspect, include_aspect=bool(eff_aspect), suffix=""
                )
            else:
                base_stem = os.path.splitext(matched_vf)[0]
                clean_stem = re.sub(r"(?i)[_\-\s]*slated$", "", base_stem).strip("_- ")
                out_stem = f"{clean_stem}_Slated"

            out_name = f"{out_stem}.mov"
            pairs.append(
                {
                    "id": s_id,
                    "slate_name": sf,
                    "slate_path": os.path.join(sdir, sf),
                    "video_name": matched_vf,
                    "video_path": os.path.join(vdir, matched_vf),
                    "output_name": out_name,
                    "slated_stem": out_stem,
                    "clean_stem": clean_stem,
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
        custom_out = resolve_path_input(self.output_dir.get())
        output_dir = custom_out if custom_out else os.path.join(videos_dir, "MARRIED_DELIVERY")
        auto_transcode = bool(self.auto_transcode_var.get())
        folders = create_delivery_folders(output_dir, include_slated=True, include_unslated=auto_transcode)
        presets = ensure_ame_presets(folders["presets_dir"])

        settings = dict(settings or {})
        settings["prores_epr"] = presets.get("prores_epr", "")
        settings["h264_epr"] = presets.get("h264_epr", "")
        settings["ae_seed_aep"] = presets.get("ae_seed_aep", "")
        settings["auto_transcode"] = auto_transcode

        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        pfx = theme_cfg.get("project_prefix", "SuperJoy")
        hdr_brand = theme_cfg.get("header_title_bold", "SUPERJOY")
        aep_marry_path = os.path.join(output_dir, f"{pfx}_Married_Slates.aep")
        beep_path = os.path.join(output_dir, "_2pop_1kHz_1frame.wav")
        jsx_path = os.path.join(output_dir, "_temp_ae_marry.jsx")
        log_path = os.path.join(output_dir, "Marry_Results_Log.txt")

        create_beep_wav(beep_path)

        marry_jobs = []
        log_lines = [
            f"{hdr_brand} AE/AME MARRY EXISTING SLATES + VIDEOS LOG",
            "=" * 56,
            f"Slates Folder:   {slates_dir}",
            f"Videos Folder:   {videos_dir}",
            f"Output Root:     {output_dir}",
            f"Slated ProRes:   {folders['slated_prores']}",
            f"Slated H.264:    {folders['slated_h264']}",
            f"Unslated ProRes: {folders['unslated_prores']}",
            f"Unslated H.264:  {folders['unslated_h264']}",
            "",
        ]
        for p in pairs:
            slated_stem = p.get("slated_stem") or os.path.splitext(p["output_name"])[0]
            clean_stem = p.get("clean_stem") or re.sub(r"(?i)[_\-\s]*slated$", "", slated_stem).strip("_- ")
            slated_prores_out = os.path.join(folders["slated_prores"], f"{slated_stem}.mov")
            slated_h264_out = os.path.join(folders["slated_h264"], f"{slated_stem}.mp4") if auto_transcode else ""
            unslated_prores_out = os.path.join(folders["unslated_prores"], f"{clean_stem}.mov") if auto_transcode else ""
            unslated_h264_out = os.path.join(folders["unslated_h264"], f"{clean_stem}.mp4") if auto_transcode else ""

            marry_jobs.append(
                {
                    "id": p["id"],
                    "slate_path": p["slate_path"],
                    "video_path": p["video_path"],
                    "final_output": slated_prores_out,
                    "slated_prores_output": slated_prores_out,
                    "slated_h264_output": slated_h264_out,
                    "unslated_prores_output": unslated_prores_out,
                    "unslated_h264_output": unslated_h264_out,
                    "comp_name": slated_stem,
                    "unslated_comp_name": f"{clean_stem}_UNSLATED",
                }
            )
            log_lines.append(
                f"[MARRIED] {p['slate_name']} + {p['video_name']} -> SLATED/ProRes/{slated_stem}.mov & SLATED/h264/{slated_stem}.mp4"
            )

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except OSError:
            pass

        self.write_marry_jsx(jsx_path, marry_jobs, aep_marry_path, beep_path, settings)

        ensure_ame_running()
        clear_jsx_status(jsx_path)

        try:
            execute_ae_script_file(jsx_path)
            verify_jsx_status(jsx_path)
            msg = (
                f"Married {len(marry_jobs)} existing slate(s) + master video(s) and queued in AME!\n\n"
                f"Folders Created:\n"
                f"• {folders['slated_prores']}\n"
                f"• {folders['slated_h264']}\n"
                f"• {folders['unslated_prores']}\n"
                f"• {folders['unslated_h264']}\n\n"
                f"Editable Project:\n{aep_marry_path}"
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

        function ensureSuperJoyOutputTemplates(seedAepPath) {{
            try {{
                if (!seedAepPath) return;
                var seedFile = new File(seedAepPath);
                if (!seedFile.exists) return;
                if (app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                app.newProject();
                var tc = app.project.items.addComp("_tpl_check", 1920, 1080, 1.0, 1.0, 24.0);
                var trq = app.project.renderQueue.items.add(tc);
                var tpls = trq.outputModule(1).templates;
                var hasProRes = false, hasH264 = false;
                for (var t = 0; t < tpls.length; t++) {{
                    if (String(tpls[t]) === "Apple ProRes 422 HQ") hasProRes = true;
                    if (String(tpls[t]) === "SuperJoy H.264 25 Mbps") hasH264 = true;
                }}
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                if (!hasProRes || !hasH264) {{
                    app.open(seedFile);
                    if (!hasProRes && app.project.renderQueue.numItems >= 1) {{
                        try {{ app.project.renderQueue.item(1).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS1) {{}}
                        app.project.renderQueue.item(1).outputModule(1).saveAsTemplate("Apple ProRes 422 HQ");
                    }}
                    if (!hasH264 && app.project.renderQueue.numItems >= 2) {{
                        try {{ app.project.renderQueue.item(2).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS2) {{}}
                        app.project.renderQueue.item(2).outputModule(1).saveAsTemplate("SuperJoy H.264 25 Mbps");
                    }}
                    app.preferences.saveToDisk();
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                }}
            }} catch (eSeed) {{}}
        }}

        function applyOutputTemplateSafe(outMod, preferredNames) {{
            try {{
                var tpls = outMod.templates;
                for (var p = 0; p < preferredNames.length; p++) {{
                    var want = preferredNames[p].toLowerCase();
                    for (var t = 0; t < tpls.length; t++) {{
                        if (String(tpls[t]).toLowerCase() === want) {{
                            outMod.applyTemplate(tpls[t]);
                            return true;
                        }}
                    }}
                }}
            }} catch (eTpl) {{}}
            return false;
        }}

        function queueProResAndH264(comp, proresPath, h264Path) {{
            if (proresPath) {{
                var rqPro = app.project.renderQueue.items.add(comp);
                var omPro = rqPro.outputModule(1);
                applyOutputTemplateSafe(omPro, ["Apple ProRes 422 HQ", "High Quality", "Lossless"]);
                try {{
                    omPro.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudP) {{}}
                omPro.file = new File(proresPath);
            }}
            if (h264Path) {{
                var rqMp4 = app.project.renderQueue.items.add(comp);
                var omMp4 = rqMp4.outputModule(1);
                applyOutputTemplateSafe(omMp4, [
                    "SuperJoy H.264 25 Mbps",
                    "H.264 - Match Render Settings - 25 Mbps",
                    "H.264 - Match Render Settings - 40 Mbps",
                    "H.264 - Match Render Settings - 15 Mbps"
                ]);
                try {{
                    omMp4.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudM) {{}}
                omMp4.file = new File(h264Path);
            }}
        }}

        function setCompStartTimecode(c, tcString) {{
            try {{
                var t = currentFormatToTime(tcString, c.frameRate);
                c.displayStartTime = t + (c.frameDuration * 0.5);
            }} catch (eTc) {{
                c.displayStartTime = (tcString === "00:59:53:00") ? 3593.0 : 3600.0;
            }}
        }}

        try {{
            if (app.project) {{
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            }}
        }} catch (eClose) {{}}

        ensureSuperJoyOutputTemplates(cfg.ae_seed_aep || "");

        app.newProject();
        app.beginUndoGroup("Batch Marry Existing Slates + Videos");

        var masterFolder = app.project.items.addFolder("Married Slated Comps");
        var unslatedFolder = app.project.items.addFolder("Unslated Master Comps");
        var assetsFolder = app.project.items.addFolder("Imported Slates & Masters");
        assetsFolder.parentFolder = masterFolder;

        var beepItem = null;
        if (beepFile.exists) {{
            beepItem = app.project.importFile(new ImportOptions(beepFile));
            beepItem.parentFolder = assetsFolder;
        }}

        function hasTwoPopLeader(item, fps) {{
            if (!item) return false;
            try {{
                var dispSec = item.displayStartTime;
                var tcStr = timeToCurrentFormat(dispSec, fps).replace(/;/g, ":");
                if (tcStr.indexOf("00:59:58:") === 0) return true;
                if (Math.abs(dispSec - 3598.0) < 0.2) return true;
                var tcTarget = currentFormatToTime("00:59:58:00", fps);
                if (Math.abs(dispSec - tcTarget) < 0.1) return true;
            }} catch (eTcCheck) {{}}
            return false;
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
            var nominalFps = Math.round(compFps);
            var videoHas2Pop = hasTwoPopLeader(vidItem, compFps);

            var slateFrames = Math.round(5.0 * nominalFps);
            var slateDuration = slateFrames / compFps;
            var headDuration = 0;
            var totalDuration = 0;

            if (videoHas2Pop) {{
                // Video already starts at 00:59:58:00 (has 2-pop + 2s black leader with picture at 01:00:00:00).
                // Prepend only the 5.0s slate so master comp starts at 00:59:53:00 and picture lands at 01:00:00:00.
                headDuration = slateDuration;
                totalDuration = headDuration + vidItem.duration;
            }} else {{
                // Video starts at 01:00:00:00 (clean master with no 2-pop leader).
                // Add standard 7.0s leader: 5.0s slate + 2-pop + 2.0s black.
                var headFrames = Math.round(7.0 * nominalFps);
                headDuration = headFrames / compFps;
                totalDuration = headDuration + vidItem.duration;
            }}

            var masterComp = app.project.items.addComp(job.comp_name, compW, compH, 1.0, totalDuration, compFps);
            masterComp.parentFolder = masterFolder;
            setCompStartTimecode(masterComp, "00:59:53:00");

            if (!videoHas2Pop) {{
                var blackDuration = headDuration - slateDuration;
                var blackSolid = masterComp.layers.addSolid([0,0,0], "2s_Black", compW, compH, 1.0, blackDuration);
                blackSolid.startTime = slateDuration;
                blackSolid.outPoint = headDuration;
            }}

            var slateLayer = masterComp.layers.add(slateItem);
            slateLayer.startTime = 0.0;
            if (videoHas2Pop) {{
                slateLayer.outPoint = slateDuration;
            }} else if (slateItem.duration && slateItem.duration >= slateDuration + masterComp.frameDuration) {{
                slateLayer.outPoint = Math.min(headDuration, slateItem.duration);
            }} else {{
                slateLayer.outPoint = slateDuration;
                if (beepItem) {{
                    var beepLayer = masterComp.layers.add(beepItem);
                    beepLayer.startTime = slateDuration;
                    beepLayer.outPoint = slateDuration + masterComp.frameDuration;
                }}
            }}

            if (slateItem.width > 0 && slateItem.height > 0 && (slateItem.width !== compW || slateItem.height !== compH)) {{
                var sx = (compW / slateItem.width) * 100.0;
                var sy = (compH / slateItem.height) * 100.0;
                var sUniform = Math.min(sx, sy);
                slateLayer.property("Scale").setValue([sUniform, sUniform]);
            }}

            var vidLayer = masterComp.layers.add(vidItem);
            vidLayer.startTime = headDuration;
            vidLayer.property("Scale").setValue([100, 100]);

            queueProResAndH264(
                masterComp,
                job.slated_prores_output || job.final_output,
                job.slated_h264_output || ""
            );

            if (job.unslated_prores_output || job.unslated_h264_output) {{
                var cleanCompName = job.unslated_comp_name || (job.comp_name + "_UNSLATED");
                var cleanComp = null;
                var cleanVidLayer = null;
                if (videoHas2Pop) {{
                    // Video has a 2-pop leader (starts at 00:59:58:00). Trim the first 2.0s so picture begins at 01:00:00:00.
                    var twoSecFrames = Math.round(2.0 * nominalFps);
                    var twoSecDur = twoSecFrames / compFps;
                    var cleanDuration = Math.max(masterComp.frameDuration, vidItem.duration - twoSecDur);
                    cleanComp = app.project.items.addComp(cleanCompName, compW, compH, 1.0, cleanDuration, compFps);
                    cleanComp.parentFolder = unslatedFolder;
                    setCompStartTimecode(cleanComp, "01:00:00:00");
                    cleanVidLayer = cleanComp.layers.add(vidItem);
                    cleanVidLayer.startTime = -twoSecDur;
                    cleanVidLayer.inPoint = 0.0;
                    cleanVidLayer.outPoint = cleanDuration;
                }} else {{
                    // Clean video without leader starts directly at 01:00:00:00.
                    cleanComp = app.project.items.addComp(cleanCompName, compW, compH, 1.0, vidItem.duration, compFps);
                    cleanComp.parentFolder = unslatedFolder;
                    setCompStartTimecode(cleanComp, "01:00:00:00");
                    cleanVidLayer = cleanComp.layers.add(vidItem);
                    cleanVidLayer.startTime = 0.0;
                }}
                cleanVidLayer.property("Scale").setValue([100, 100]);
                queueProResAndH264(cleanComp, job.unslated_prores_output || "", job.unslated_h264_output || "");
            }}
        }}

        app.endUndoGroup();

        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        var queued = false, lastErr = "";
        __SJ_STATUS.rqItems = app.project.renderQueue.numItems;
        for (var qa = 0; qa < 4 && !queued; qa++) {{
            try {{
                app.project.renderQueue.queueInAME(false);
                queued = true;
                __SJ_STATUS.queued = true;
            }} catch (eQ) {{
                lastErr = __sjErrText(eQ);
                $.sleep(5000);
            }}
        }}
        if (!queued) {{
            __SJ_STATUS.error = "Could not queue in Adobe Media Encoder: " + lastErr;
        }}
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrap_jsx_with_status(jsx_code, path + ".status"))

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
            folder = resolve_path_input(self.unslate_dir.get())
            if not folder or not os.path.isdir(folder):
                self._alert("showerror", "Error", "Please select a folder of slated videos.")
                return
            self.btn_run.config(text="PROCESSING...", state="disabled")
            threading.Thread(
                target=self.process_unslate, args=(folder, self.render_settings), daemon=True
            ).start()
            return

        if tab == 3:
            sdir = resolve_path_input(self.marry_slates_dir.get())
            vdir = resolve_path_input(self.videos_dir.get())
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

        template_dir = resolve_path_input(self.template_dir.get())
        videos_dir = resolve_path_input(self.videos_dir.get())
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
            tsv = resolve_path_input(self.tsv_path.get())
            if not tsv:
                self._alert("showerror", "Error", "Please select a spreadsheet / metadata file.")
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
            if not self.manual_batch_data and videos_dir and os.path.isdir(videos_dir):
                self.populate_batch_from_videos(notify_if_empty=False)
            if not self.manual_batch_data:
                self._alert(
                    "showerror",
                    "Empty Queue",
                    "Your batch queue is empty. Add spots manually, import an .xlsx/.csv/.tsv, or select a Master Videos folder.",
                )
                return
            self._sync_shared_fields_to_batch(sync_flame=False)
            batch_jobs_data = [normalize_slate_row(item) for item in self.manual_batch_data]

        self.btn_run.config(text="PROCESSING...", state="disabled")
        threading.Thread(
            target=self.process_batch,
            args=(batch_jobs_data, template_dir, videos_dir, slates_only),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Un-Slate (After Effects + Adobe Media Encoder 7.0s Head Trim -> UNSLATED/ProRes & UNSLATED/h264)
    # ------------------------------------------------------------------
    def process_unslate(self, folder, settings=None):
        settings = dict(settings or getattr(self, "render_settings", {"fps": DEFAULT_FPS, "width": 1920, "height": 1080}))
        custom_out = resolve_path_input(self.output_dir.get())
        base_out = custom_out if custom_out else folder
        auto_transcode = bool(self.auto_transcode_var.get())

        folders = create_delivery_folders(base_out, include_slated=False, include_unslated=True)
        presets = ensure_ame_presets(folders["presets_dir"])
        settings["prores_epr"] = presets.get("prores_epr", "")
        settings["h264_epr"] = presets.get("h264_epr", "")
        settings["ae_seed_aep"] = presets.get("ae_seed_aep", "")
        settings["auto_transcode"] = auto_transcode

        out_dir = folders["unslated_root"]
        files = sorted(
            f for f in os.listdir(folder) if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        )
        if not files:
            self.root.after(0, lambda: self._alert("showwarning", "No Videos Found", "No video files found in the selected folder."))
            self.root.after(0, self.reset_ui)
            return

        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        pfx = theme_cfg.get("project_prefix", "SuperJoy")
        hdr_brand = theme_cfg.get("header_title_bold", "SUPERJOY")
        aep_unslate_path = os.path.join(out_dir, f"{pfx}_Unslate_Project.aep")
        jsx_path = os.path.join(out_dir, "_temp_ae_unslate.jsx")
        log_path = os.path.join(out_dir, "Unslate_Log.txt")

        unslate_jobs = []
        log_lines = [
            f"{hdr_brand} AE/AME UN-SLATE (7.0s HEAD TRIM) LOG",
            "=" * 52,
            f"Source Folder:   {folder}",
            f"Unslated ProRes: {folders['unslated_prores']}",
            f"Unslated H.264:  {folders['unslated_h264']}",
            f"Editable AEP:    {aep_unslate_path}",
            f"Head Trim:       {UNSLATE_SECONDS:.1f}s (5.0s Slate + 2.0s Black/2-Pop)",
            "",
        ]

        for fname in files:
            src = os.path.join(folder, fname)
            stem, _ = os.path.splitext(fname)
            clean_stem = re.sub(r"(?i)[_\-\s]*slated$", "", stem).strip("_- ") or f"{stem}_Unslated"
            prores_dst = os.path.join(folders["unslated_prores"], f"{clean_stem}.mov")
            h264_dst = os.path.join(folders["unslated_h264"], f"{clean_stem}.mp4") if auto_transcode else ""
            unslate_jobs.append(
                {
                    "video_path": src,
                    "final_output": prores_dst,
                    "prores_output": prores_dst,
                    "h264_output": h264_dst,
                    "comp_name": f"{clean_stem}_UNSLATED",
                }
            )
            log_lines.append(
                f"[QUEUED] {fname} -> UNSLATED/ProRes/{clean_stem}.mov"
                + (f" & UNSLATED/h264/{clean_stem}.mp4" if h264_dst else "")
                + f" (trim first {UNSLATE_SECONDS:.1f}s)"
            )

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
        except OSError:
            pass

        self.write_unslate_jsx(jsx_path, unslate_jobs, aep_unslate_path, settings)

        ensure_ame_running()
        clear_jsx_status(jsx_path)

        try:
            execute_ae_script_file(jsx_path)
            verify_jsx_status(jsx_path)
            msg = (
                f"Queued {len(unslate_jobs)} un-slated spot(s) in Adobe Media Encoder!\n\n"
                f"Output Folders:\n"
                f"• {folders['unslated_prores']}\n"
                f"• {folders['unslated_h264']}\n\n"
                f"Editable Project (for manual checks/fixes):\n{aep_unslate_path}"
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

        function ensureSuperJoyOutputTemplates(seedAepPath) {{
            try {{
                if (!seedAepPath) return;
                var seedFile = new File(seedAepPath);
                if (!seedFile.exists) return;
                if (app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                app.newProject();
                var tc = app.project.items.addComp("_tpl_check", 1920, 1080, 1.0, 1.0, 24.0);
                var trq = app.project.renderQueue.items.add(tc);
                var tpls = trq.outputModule(1).templates;
                var hasProRes = false, hasH264 = false;
                for (var t = 0; t < tpls.length; t++) {{
                    if (String(tpls[t]) === "Apple ProRes 422 HQ") hasProRes = true;
                    if (String(tpls[t]) === "SuperJoy H.264 25 Mbps") hasH264 = true;
                }}
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                if (!hasProRes || !hasH264) {{
                    app.open(seedFile);
                    if (!hasProRes && app.project.renderQueue.numItems >= 1) {{
                        try {{ app.project.renderQueue.item(1).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS1) {{}}
                        app.project.renderQueue.item(1).outputModule(1).saveAsTemplate("Apple ProRes 422 HQ");
                    }}
                    if (!hasH264 && app.project.renderQueue.numItems >= 2) {{
                        try {{ app.project.renderQueue.item(2).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS2) {{}}
                        app.project.renderQueue.item(2).outputModule(1).saveAsTemplate("SuperJoy H.264 25 Mbps");
                    }}
                    app.preferences.saveToDisk();
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                }}
            }} catch (eSeed) {{}}
        }}

        function applyOutputTemplateSafe(outMod, preferredNames) {{
            try {{
                var tpls = outMod.templates;
                for (var p = 0; p < preferredNames.length; p++) {{
                    var want = preferredNames[p].toLowerCase();
                    for (var t = 0; t < tpls.length; t++) {{
                        if (String(tpls[t]).toLowerCase() === want) {{
                            outMod.applyTemplate(tpls[t]);
                            return true;
                        }}
                    }}
                }}
            }} catch (eTpl) {{}}
            return false;
        }}

        function setCompStartTimecode(c, tcString) {{
            try {{
                var t = currentFormatToTime(tcString, c.frameRate);
                c.displayStartTime = t + (c.frameDuration * 0.5);
            }} catch (eTc) {{
                c.displayStartTime = 3600.0;
            }}
        }}

        try {{
            if (app.project) {{
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            }}
        }} catch (eClose) {{}}

        ensureSuperJoyOutputTemplates(cfg.ae_seed_aep || "");

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

            var compW = vidItem.width > 0 ? vidItem.width : cfg.width;
            var compH = vidItem.height > 0 ? vidItem.height : cfg.height;
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : cfg.fps;
            var nominalFps = Math.round(compFps);
            var headFrames = Math.round(trimSeconds * nominalFps);
            var headDuration = headFrames / compFps;

            if (vidItem.duration <= headDuration) {{
                skipped.push(vidItem.name + " (duration " + vidItem.duration.toFixed(2) + "s <= " + headDuration.toFixed(3) + "s head trim)");
                continue;
            }}

            var cleanDuration = vidItem.duration - headDuration;

            var comp = app.project.items.addComp(job.comp_name, compW, compH, 1.0, cleanDuration, compFps);
            comp.parentFolder = rootFolder;
            setCompStartTimecode(comp, "01:00:00:00");

            var vidLayer = comp.layers.add(vidItem);
            vidLayer.startTime = -headDuration;
            vidLayer.inPoint = 0.0;
            vidLayer.outPoint = cleanDuration;
            vidLayer.property("Scale").setValue([100, 100]);

            var proresTarget = job.prores_output || job.final_output;
            if (proresTarget) {{
                var rqItem = app.project.renderQueue.items.add(comp);
                var outMod = rqItem.outputModule(1);
                applyOutputTemplateSafe(outMod, ["Apple ProRes 422 HQ", "High Quality", "Lossless"]);
                try {{
                    outMod.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudP) {{}}
                outMod.file = new File(proresTarget);
            }}
            if (job.h264_output) {{
                var rqMp4 = app.project.renderQueue.items.add(comp);
                var outMp4 = rqMp4.outputModule(1);
                applyOutputTemplateSafe(outMp4, [
                    "SuperJoy H.264 25 Mbps",
                    "H.264 - Match Render Settings - 25 Mbps",
                    "H.264 - Match Render Settings - 40 Mbps",
                    "H.264 - Match Render Settings - 15 Mbps"
                ]);
                try {{
                    outMp4.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudM) {{}}
                outMp4.file = new File(job.h264_output);
            }}
        }}

        app.endUndoGroup();

        if (skipped.length) {{
            alert("Skipped during Un-Slate:\\n" + skipped.join("\\n"));
        }}

        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        var queued = false, lastErr = "";
        __SJ_STATUS.rqItems = app.project.renderQueue.numItems;
        for (var qa = 0; qa < 4 && !queued; qa++) {{
            try {{
                app.project.renderQueue.queueInAME(false);
                queued = true;
                __SJ_STATUS.queued = true;
            }} catch (eQ) {{
                lastErr = __sjErrText(eQ);
                $.sleep(5000);
            }}
        }}
        if (!queued) {{
            __SJ_STATUS.error = "Could not queue in Adobe Media Encoder: " + lastErr;
        }}
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrap_jsx_with_status(jsx_code, path + ".status"))

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

        # Determine default parent folder when global Output Folder is not explicitly set
        tsv_resolved = resolve_path_input(self.tsv_path.get())
        if videos_dir and os.path.isdir(videos_dir):
            base_out_parent = videos_dir
        elif tsv_resolved and os.path.isfile(tsv_resolved):
            base_out_parent = os.path.dirname(tsv_resolved)
        elif os.path.isfile(template_dir):
            base_out_parent = os.path.dirname(template_dir)
        else:
            base_out_parent = template_dir

        custom_global_out = resolve_path_input(self.output_dir.get())
        if custom_global_out:
            base_slates_root = custom_global_out
        else:
            subfolder_name = "STANDALONE_SLATES" if slates_only else "SLATED_DELIVERY"
            base_slates_root = os.path.join(base_out_parent, subfolder_name)

        now = datetime.now()
        date_folder = now.strftime("%Y_%m_%d")
        time_folder = now.strftime("%H%M_Slates")
        output_dir = os.path.join(base_slates_root, date_folder, time_folder)

        # Detect workspace name from manual entry fields or batch data rows
        workspace_token = ""
        manual_ws = (self.f_workspace.get() or "").strip()
        if manual_ws:
            workspace_token = sanitize_filename_token(manual_ws)
        if not workspace_token:
            for d in batch_data:
                norm_d = normalize_slate_row(d)
                ws = norm_d.get("workspace") or norm_d.get("workspace_artist") or ""
                if ws and str(ws).strip():
                    workspace_token = sanitize_filename_token(str(ws).strip())
                    break

        auto_transcode = bool(self.auto_transcode_var.get())
        if slates_only:
            auto_transcode = False  # standalone slates are .mov only
            folders = create_flat_slate_folder(output_dir)
        else:
            folders = create_delivery_folders(
                output_dir,
                include_slated=True,
                include_unslated=auto_transcode,
            )
        presets = ensure_ame_presets(folders["presets_dir"])

        render_cfg = dict(getattr(self, "render_settings", {"fps": DEFAULT_FPS, "width": 1920, "height": 1080}))
        render_cfg["prores_epr"] = presets.get("prores_epr", "")
        render_cfg["h264_epr"] = presets.get("h264_epr", "")
        render_cfg["ae_seed_aep"] = presets.get("ae_seed_aep", "")
        render_cfg["auto_transcode"] = auto_transcode
        render_cfg["slates_only"] = bool(slates_only)

        log_path = os.path.join(output_dir, "Slating_Results_Log.txt")
        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        pfx = theme_cfg.get("project_prefix", "SuperJoy")
        hdr_brand = theme_cfg.get("header_title_bold", "SUPERJOY")
        default_proj = f"{pfx}_Standalone_Slates.aep" if slates_only else f"{pfx}_Master_Slates.aep"
        proj_filename = f"{workspace_token}_SLATES.aep" if workspace_token else default_proj
        aep_master_path = os.path.join(output_dir, proj_filename)
        beep_path = os.path.join(output_dir, "_2pop_1kHz_1frame.wav")
        log_entries = [
            f"{hdr_brand} AE/AME {'STANDALONE SLATES' if slates_only else 'SLATING + H.264 TRANSCODE'} RESULTS LOG",
            "=" * 64,
            f"Template AEP:    {templates.get('_aep', template_dir)}",
            f"Output Root:     {output_dir}",
            f"Slated ProRes:   {folders['slated_prores']}",
        ]
        if not slates_only:
            log_entries.append(f"Slated H.264:    {folders['slated_h264']}")
        if not slates_only and auto_transcode:
            log_entries.extend(
                [
                    f"Unslated ProRes: {folders['unslated_prores']}",
                    f"Unslated H.264:  {folders['unslated_h264']}",
                ]
            )
        log_entries.append("")

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

        previews_dir = os.path.join(output_dir, "_previews")
        os.makedirs(previews_dir, exist_ok=True)

        for raw_data in batch_data:
            data = normalize_slate_row(raw_data)
            ad_id = data.get("id", data.get("ad-id", ""))
            title = data.get("title", data.get("name", ""))
            flame_flag = data.get("flame", "").lower() in ("y", "yes", "true", "1")
            explicit_aspect = (
                data.get("aspect")
                or detect_aspect_from_text(data.get("comp", ""))
                or detect_aspect_from_text(data.get("resolution", ""))
            )
            target_aspect = explicit_aspect if explicit_aspect in ASPECT_RESOLUTIONS else None
            multi_aspect = id_counts.get(ad_id.lower(), 0) > 1

            # Support per-slate Output Folder override in addition to batch/global Output Folder
            row_out_override = resolve_path_input(data.get("output_dir") or "")
            if row_out_override:
                row_dest = os.path.join(row_out_override, date_folder, time_folder)
                if slates_only:
                    row_folders = create_flat_slate_folder(row_dest)
                else:
                    row_folders = create_delivery_folders(
                        row_dest,
                        include_slated=True,
                        include_unslated=auto_transcode,
                    )
            else:
                row_folders = folders

            if slates_only:
                asp = target_aspect or self.aspect_var.get() or DEFAULT_ASPECT
                tw, th = ASPECT_RESOLUTIONS.get(asp, (1920, 1080))
                out_stem = build_canonical_delivery_stem(
                    data, target_aspect=asp, include_aspect=multi_aspect, suffix="Slate"
                )
                slated_prores_file = os.path.join(row_folders["slated_prores"], f"{out_stem}.mov")
                slated_h264_file = ""
                preview_png_file = os.path.join(previews_dir, f"{out_stem}_preview.png")
                job_entry = {
                    "video_path": "",
                    "slate_only": True,
                    "final_output": slated_prores_file,
                    "slated_prores_output": slated_prores_file,
                    "slated_h264_output": slated_h264_file,
                    "unslated_prores_output": "",
                    "unslated_h264_output": "",
                    "preview_png": preview_png_file,
                    "flame": flame_flag,
                    "text_data": data,
                    "aspect": asp,
                    "width": tw,
                    "height": th,
                }
                ae_jobs.append(job_entry)
                log_entries.append(
                    f"[SUCCESS] Standalone Slate {ad_id} [{format_resolution_label(asp)}] -> {out_stem}.mov"
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
                    f"[ERROR] ID: {ad_id} | Title: {title} | No matching master video found in video folder."
                )
                error_count += 1
                continue

            out_stem = build_canonical_delivery_stem(
                data, target_aspect=target_aspect, include_aspect=multi_aspect, suffix="Slated"
            )
            clean_stem = build_canonical_delivery_stem(
                data, target_aspect=target_aspect, include_aspect=multi_aspect, suffix=""
            )
            slated_prores_file = os.path.join(row_folders["slated_prores"], f"{out_stem}.mov")
            slated_h264_file = (
                os.path.join(row_folders["slated_h264"], f"{out_stem}.mp4") if auto_transcode else ""
            )
            unslated_prores_file = (
                os.path.join(row_folders["unslated_prores"], f"{clean_stem}.mov") if auto_transcode else ""
            )
            unslated_h264_file = (
                os.path.join(row_folders["unslated_h264"], f"{clean_stem}.mp4") if auto_transcode else ""
            )
            preview_png_file = os.path.join(previews_dir, f"{out_stem}_preview.png")

            job_entry = {
                "video_path": matched_video,
                "slate_only": False,
                "final_output": slated_prores_file,
                "slated_prores_output": slated_prores_file,
                "slated_h264_output": slated_h264_file,
                "unslated_prores_output": unslated_prores_file,
                "unslated_h264_output": unslated_h264_file,
                "preview_png": preview_png_file,
                "clean_stem": clean_stem,
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
                f"[SUCCESS] Paired {ad_id}{res_note} -> {os.path.basename(matched_video)} => "
                f"SLATED/ProRes/{out_stem}.mov, SLATED/h264/{out_stem}.mp4, "
                f"UNSLATED/ProRes/{clean_stem}.mov, UNSLATED/h264/{clean_stem}.mp4"
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
        self.write_jsx(jsx_path, ae_jobs, aep_master_path, beep_path, render_cfg, templates)

        if not slates_only:
            ensure_ame_running()
        clear_jsx_status(jsx_path)

        try:
            execute_ae_script_file(jsx_path)
            status_info = verify_jsx_status(jsx_path)

            # Generate static first-frame preview PNGs for in-app preview viewer using macOS native Quick Look
            created_previews = []
            for j in ae_jobs:
                ppath = j.get("preview_png")
                mov_file = j.get("slated_prores_output") or j.get("final_output")
                if ppath and mov_file and os.path.isfile(mov_file) and not os.path.isfile(ppath):
                    try:
                        # Extract first frame thumbnail via macOS built-in /usr/bin/qlmanage
                        subprocess.run(
                            ["/usr/bin/qlmanage", "-t", "-s", "1080", "-o", previews_dir, mov_file],
                            capture_output=True,
                            timeout=30,
                        )
                        ql_out = os.path.join(previews_dir, os.path.basename(mov_file) + ".png")
                        if os.path.isfile(ql_out):
                            os.replace(ql_out, ppath)
                    except Exception:
                        pass

                if ppath and os.path.isfile(ppath):
                    created_previews.append({
                        "id": j.get("text_data", {}).get("id") or j.get("text_data", {}).get("ad-id", ""),
                        "aspect": j.get("aspect", ""),
                        "title": j.get("text_data", {}).get("title") or j.get("text_data", {}).get("name", ""),
                        "image_path": ppath,
                    })
            if created_previews:
                self.latest_previews = created_previews
                self.root.after(200, self.open_preview_viewer)

            mode_desc = "Standalone Slates Project" if slates_only else "Master Slated + Unslated Project"
            folder_summary = (
                f"• {folders['slated_prores']}"
                if slates_only
                else f"• {folders['slated_prores']}\n• {folders['slated_h264']}\n• {folders['unslated_prores']}\n• {folders['unslated_h264']}"
            )
            action_desc = (
                "rendered ProRes 422 HQ .mov files"
                if status_info.get("rendered") == "1"
                else "queued in AME"
            )
            msg = (
                f"Successfully generated {mode_desc} ({success_count} spot(s)) and {action_desc}!\n\n"
                f"Delivery Folders:\n{folder_summary}\n\n"
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

    # ------------------------------------------------------------------
    # One-Click GitHub DMG Self-Updater
    # ------------------------------------------------------------------
    def prompt_self_update(self):
        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        dmg_env = theme_cfg.get("dmg_url_env", "SUPERJOY_UPDATE_DMG_URL")
        dmg_def = theme_cfg.get("dmg_url_default", "https://raw.githubusercontent.com/bennfoxx/SlateWorkstation/main/SuperJoy_Slating_Workstation_v1.0.0.dmg")
        app_name = theme_cfg.get("app_name", "SuperJoy Slating Workstation")
        dmg_url = os.environ.get(dmg_env, dmg_def)
        ans = messagebox.askyesno(
            f"Update {app_name}",
            f"Download the latest {app_name} build from GitHub and update your local app now?\n\n"
            f"• Source: github.com/bennfoxx/SlateWorkstation\n"
            f"• Installs to: /Applications/{app_name}.app\n"
            "• Automatically clears macOS Gatekeeper quarantine and relaunches the app.",
        )
        reset_tk_mouse_state(self.root)
        if not ans:
            return
        if hasattr(self, "btn_update"):
            self.btn_update.config(text="Updating...", state="disabled")
        self.asset_status_lbl.config(text="Downloading latest DMG from GitHub...", fg=ACCENT_YELLOW)
        threading.Thread(target=self._run_self_update_worker, args=(dmg_url,), daemon=True).start()

    def _run_self_update_worker(self, dmg_url):
        import tempfile

        theme_cfg = getattr(self, "theme_cfg", THEMES.get(ACTIVE_THEME, THEMES["superjoy"]))
        app_name = theme_cfg.get("app_name", "SuperJoy Slating Workstation")
        tmp_dir = tempfile.mkdtemp(prefix="update_")
        dmg_path = os.path.join(tmp_dir, "App_Update.dmg")
        mount_point = os.path.join(tmp_dir, "mnt")
        os.makedirs(mount_point, exist_ok=True)
        cache_bust_url = f"{dmg_url}?t={int(time.time())}"

        try:
            # 1. Download latest DMG from GitHub
            subprocess.run(
                ["curl", "-fL", "--retry", "2", "--connect-timeout", "15", "-o", dmg_path, cache_bust_url],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )

            self.root.after(
                0, lambda: self.asset_status_lbl.config(text="Mounting update image...", fg=ACCENT_YELLOW)
            )

            # 2. Attach DMG to temporary mount point
            subprocess.run(
                ["hdiutil", "attach", dmg_path, "-mountpoint", mount_point, "-nobrowse", "-quiet"],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            src_app = os.path.join(mount_point, f"{app_name}.app")
            if not os.path.isdir(src_app):
                candidates = glob.glob(os.path.join(mount_point, "*.app"))
                if candidates:
                    src_app = candidates[0]
                else:
                    raise RuntimeError("No .app bundle found inside the downloaded DMG.")

            # 3. Determine target .app path(s) to update
            exe_path = os.path.abspath(sys.executable)
            current_app = None
            if ".app/Contents/" in exe_path:
                current_app = exe_path.split(".app/Contents/")[0] + ".app"

            apps_target = f"/Applications/{app_name}.app"
            if current_app and not current_app.startswith("/Volumes/") and os.access(os.path.dirname(current_app), os.W_OK):
                primary_target = current_app
            else:
                primary_target = apps_target

            # Also pull latest git repo files if running from a git checkout
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.isdir(os.path.join(repo_dir, ".git")):
                try:
                    subprocess.run(
                        ["git", "-C", repo_dir, "pull", "--ff-only", "origin", "main"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception:
                    pass

            # 4. Spawn detached installer script that swaps the .app bundle, strips quarantine, unmounts DMG, and relaunches
            updater_sh = os.path.join(tmp_dir, "apply_update.sh")
            pid = os.getpid()
            sh_content = f"""#!/bin/bash
sleep 1
kill -9 {pid} 2>/dev/null || true
for i in $(seq 1 20); do
    if ! kill -0 {pid} 2>/dev/null; then break; fi
    sleep 0.2
done

rm -rf "{primary_target}"
ditto "{src_app}" "{primary_target}"
xattr -cr "{primary_target}" 2>/dev/null || true

if [ "{primary_target}" != "{apps_target}" ] && [ -w "/Applications" ]; then
    rm -rf "{apps_target}"
    ditto "{src_app}" "{apps_target}"
    xattr -cr "{apps_target}" 2>/dev/null || true
fi

hdiutil detach "{mount_point}" -force >/dev/null 2>&1 || true
rm -rf "{tmp_dir}" >/dev/null 2>&1 || true

open "{primary_target}"
"""
            with open(updater_sh, "w", encoding="utf-8") as f:
                f.write(sh_content)
            os.chmod(updater_sh, 0o755)

            def _finish_and_relaunch():
                if hasattr(self, "btn_update"):
                    self.btn_update.config(text="↻ Update App", state="normal")
                self._alert(
                    "showinfo",
                    "Update Ready — Relaunching",
                    f"Latest version downloaded from GitHub!\n\n"
                    f"SuperJoy Slating Workstation will now install to:\n{primary_target}\n\nand relaunch automatically.",
                )
                subprocess.Popen(
                    ["/bin/bash", updater_sh],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.root.after(150, self.root.destroy)

            self.root.after(0, _finish_and_relaunch)

        except Exception as e:
            try:
                subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True, timeout=15)
            except Exception:
                pass

            def _on_err(err_msg=str(e)):
                if hasattr(self, "btn_update"):
                    self.btn_update.config(text="↻ Update App", state="normal")
                self.asset_status_lbl.config(text="Update failed.", fg=ACCENT_RED)
                self._alert("showerror", "Update Failed", f"Could not update from GitHub:\n{err_msg}")

            self.root.after(0, _on_err)

    def write_jsx(self, path, jobs, aep_path, beep_path, settings, templates):
        # Work from a private copy of the .aep so the original template is never opened/locked in AE
        templates = dict(templates or {})
        src_aep = templates.get("_aep")
        if src_aep and os.path.isfile(src_aep):
            import tempfile
            work_dir = tempfile.mkdtemp(prefix="sj_tpl_")
            work_aep = os.path.join(work_dir, os.path.basename(src_aep))
            shutil.copyfile(src_aep, work_aep)
            os.chmod(work_aep, 0o644)
            for k, v in list(templates.items()):
                if v == src_aep:
                    templates[k] = work_aep
        jobs_json = json.dumps(jobs)
        settings_json = json.dumps(settings)
        templates_json = json.dumps(templates)
        jsx_code = f"""
        var jobs = {jobs_json};
        var cfg = {settings_json};
        var templates = {templates_json};
        var beepFile = new File({json.dumps(beep_path)});

        function ensureSuperJoyOutputTemplates(seedAepPath) {{
            try {{
                if (!seedAepPath) return;
                var seedFile = new File(seedAepPath);
                if (!seedFile.exists) return;
                if (app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                app.newProject();
                var tc = app.project.items.addComp("_tpl_check", 1920, 1080, 1.0, 1.0, 24.0);
                var trq = app.project.renderQueue.items.add(tc);
                var tpls = trq.outputModule(1).templates;
                var hasProRes = false, hasH264 = false;
                for (var t = 0; t < tpls.length; t++) {{
                    if (String(tpls[t]) === "Apple ProRes 422 HQ") hasProRes = true;
                    if (String(tpls[t]) === "SuperJoy H.264 25 Mbps") hasH264 = true;
                }}
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                if (!hasProRes || !hasH264) {{
                    app.open(seedFile);
                    if (!hasProRes && app.project.renderQueue.numItems >= 1) {{
                        try {{ app.project.renderQueue.item(1).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS1) {{}}
                        app.project.renderQueue.item(1).outputModule(1).saveAsTemplate("Apple ProRes 422 HQ");
                    }}
                    if (!hasH264 && app.project.renderQueue.numItems >= 2) {{
                        try {{ app.project.renderQueue.item(2).outputModule(1).setSettings({{"Output File Info": {{"Subfolder Path": ""}}}}); }} catch (eS2) {{}}
                        app.project.renderQueue.item(2).outputModule(1).saveAsTemplate("SuperJoy H.264 25 Mbps");
                    }}
                    app.preferences.saveToDisk();
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                }}
            }} catch (eSeed) {{}}
        }}

        // Map a video size to the nearest standard aspect key.
        function pickAspect(w, h) {{
            var r = w / h;
            var keys = {{"16x9": 16/9, "1x1": 1.0, "4x5": 0.8, "9x16": 9/16, "2x3": 2/3}};
            var best = null, bestDiff = 1e9;
            for (var k in keys) {{
                var d = Math.abs(r - keys[k]);
                if (d < bestDiff) {{ bestDiff = d; best = k; }}
            }}
            return best;
        }}

        function applyOutputTemplateSafe(outMod, preferredNames) {{
            try {{
                var tpls = outMod.templates;
                for (var p = 0; p < preferredNames.length; p++) {{
                    var want = preferredNames[p].toLowerCase();
                    for (var t = 0; t < tpls.length; t++) {{
                        if (String(tpls[t]).toLowerCase() === want) {{
                            outMod.applyTemplate(tpls[t]);
                            return true;
                        }}
                    }}
                }}
            }} catch (eTpl) {{}}
            return false;
        }}

        function queueProResAndH264(comp, proresPath, h264Path) {{
            if (proresPath) {{
                var rqPro = app.project.renderQueue.items.add(comp);
                var omPro = rqPro.outputModule(1);
                applyOutputTemplateSafe(omPro, ["Apple ProRes 422 HQ", "High Quality", "Lossless"]);
                try {{
                    omPro.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudP) {{}}
                omPro.file = new File(proresPath);
            }}
            if (h264Path) {{
                var rqMp4 = app.project.renderQueue.items.add(comp);
                var omMp4 = rqMp4.outputModule(1);
                applyOutputTemplateSafe(omMp4, [
                    "SuperJoy H.264 25 Mbps",
                    "H.264 - Match Render Settings - 25 Mbps",
                    "H.264 - Match Render Settings - 40 Mbps",
                    "H.264 - Match Render Settings - 15 Mbps"
                ]);
                try {{
                    omMp4.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAudM) {{}}
                omMp4.file = new File(h264Path);
            }}
        }}

        function hasTwoPopLeader(item, fps) {{
            if (!item) return false;
            try {{
                var dispSec = item.displayStartTime;
                var tcStr = timeToCurrentFormat(dispSec, fps).replace(/;/g, ":");
                if (tcStr.indexOf("00:59:58:") === 0) return true;
                if (Math.abs(dispSec - 3598.0) < 0.2) return true;
                var tcTarget = currentFormatToTime("00:59:58:00", fps);
                if (Math.abs(dispSec - tcTarget) < 0.1) return true;
            }} catch (eTcCheck) {{}}
            return false;
        }}

        function setCompStartTimecode(c, tcString) {{
            try {{
                var t = currentFormatToTime(tcString, c.frameRate);
                c.displayStartTime = t + (c.frameDuration * 0.5);
            }} catch (eTc) {{
                c.displayStartTime = (tcString === "00:59:53:00") ? 3593.0 : 3600.0;
            }}
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

            // Match the Agency & Audio value layers in sj_Slates From Spreadsheet_Template_006.aep
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

        function mapFontToAvenirNext(oldFont, oldStyle) {{
            var f = String(oldFont || "").toLowerCase();
            var s = String(oldStyle || "").toLowerCase();
            var isItalic = (f.indexOf("it") !== -1) || (s.indexOf("it") !== -1) || (s.indexOf("oblique") !== -1);
            if (f.indexOf("blk") !== -1 || f.indexOf("xbd") !== -1 || f.indexOf("hvy") !== -1 || s.indexOf("blk") !== -1 || s.indexOf("xbd") !== -1 || s.indexOf("heavy") !== -1 || s.indexOf("black") !== -1) {{
                return isItalic ? "AvenirNext-HeavyItalic" : "AvenirNext-Heavy";
            }}
            if (f.indexOf("dmbd") !== -1 || f.indexOf("demi") !== -1 || f.indexOf("sbd") !== -1 || s.indexOf("dmbd") !== -1 || s.indexOf("demi") !== -1 || s.indexOf("semi") !== -1) {{
                return isItalic ? "AvenirNext-DemiBoldItalic" : "AvenirNext-DemiBold";
            }}
            if (f.indexOf("bd") !== -1 || f.indexOf("bold") !== -1 || s.indexOf("bold") !== -1 || s === "bd") {{
                return isItalic ? "AvenirNext-BoldItalic" : "AvenirNext-Bold";
            }}
            if (f.indexOf("med") !== -1 || f.indexOf("md") !== -1 || s.indexOf("med") !== -1) {{
                return isItalic ? "AvenirNext-MediumItalic" : "AvenirNext-Medium";
            }}
            if (f.indexOf("thin") !== -1 || f.indexOf("ul") !== -1 || f.indexOf("lt") !== -1 || s.indexOf("light") !== -1 || s.indexOf("thin") !== -1) {{
                return isItalic ? "AvenirNext-UltraLightItalic" : "AvenirNext-UltraLight";
            }}
            return isItalic ? "AvenirNext-Italic" : "AvenirNext-Regular";
        }}

        function ensureAvenirNextFont(layer) {{
            try {{
                var sp = layer.property("Source Text");
                if (!sp) return;
                var td = sp.value;
                var fontStr = String(td.font || "").toLowerCase();
                var famStr = String(td.fontFamily || "").toLowerCase();
                if (fontStr.indexOf("ttfors") !== -1 || famStr.indexOf("tt fors") !== -1 || famStr.indexOf("ttfors") !== -1) {{
                    td.font = mapFontToAvenirNext(td.font, td.fontStyle);
                    sp.setValue(td);
                }}
            }} catch (eFont) {{}}
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
                    ensureAvenirNextFont(layer);
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

        ensureSuperJoyOutputTemplates(cfg.ae_seed_aep || "");

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

        // Purge any stale or existing RenderQueue items from the template or previous session
        while (app.project.renderQueue.numItems > 0) {{
            try {{
                app.project.renderQueue.item(1).remove();
            }} catch (eRqClean) {{
                break;
            }}
        }}

        app.beginUndoGroup("Batch Slate Generation");

        var skipped = [];
        var isStandaloneOnly = (cfg.slates_only === true);
        var masterFolder = isStandaloneOnly ? null : app.project.items.addFolder("Slated Comps");
        var unslatedFolder = isStandaloneOnly ? null : app.project.items.addFolder("Unslated Comps");
        var slatesFolder = app.project.items.addFolder(isStandaloneOnly ? "STANDALONE SLATES" : "Generated Slate Precomps");
        if (masterFolder) {{
            slatesFolder.parentFolder = masterFolder;
        }}

        var beepItem = null;
        if (!usingAepTemplate && beepFile.exists) {{
            beepItem = app.project.importFile(new ImportOptions(beepFile));
            if (masterFolder) {{
                beepItem.parentFolder = masterFolder;
            }}
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

            // Standalone Slate Only mode: queue the populated slateComp to ProRes (.mov)
            if (isSlateOnly) {{
                if (slateComp) {{
                    queueProResAndH264(
                        slateComp,
                        job.slated_prores_output || job.final_output,
                        job.slated_h264_output || ""
                    );
                }}
                continue;
            }}

            // Slated Master mode (Slate + 2-Pop + 2s Black + Master Video):
            // Rule: Deliverables are rendered from specific native resolutions and never letterboxed or cropped.
            var compW = (vidItem.width > 0) ? vidItem.width : (job.width ? job.width : cfg.width);
            var compH = (vidItem.height > 0) ? vidItem.height : (job.height ? job.height : cfg.height);
            var compFps = vidItem.frameRate > 0 ? vidItem.frameRate : cfg.fps;
            var nominalFps = Math.round(compFps);
            var videoHas2Pop = hasTwoPopLeader(vidItem, compFps);

            var slateFrames = Math.round(5.0 * nominalFps);
            var slateDuration = slateFrames / compFps;
            var headDuration = 0;
            var totalDuration = 0;

            if (videoHas2Pop) {{
                // Video already starts at 00:59:58:00 (has 2-pop + 2s black leader with picture at 01:00:00:00).
                // Prepend only the 5.0s slate so master comp starts at 00:59:53:00 and picture lands at 01:00:00:00.
                headDuration = slateDuration;
                totalDuration = headDuration + vidItem.duration;
            }} else {{
                // Video starts at 01:00:00:00 (clean master with no 2-pop leader).
                // Add standard 7.0s leader: 5.0s slate + 2-pop + 2.0s black.
                var headFrames = Math.round(7.0 * nominalFps);
                headDuration = headFrames / compFps;
                totalDuration = headDuration + vidItem.duration;
            }}

            var compName = job.aspect ? (slateId + "_" + job.aspect + "_SLATED") : (slateId + "_SLATED");
            var masterComp = app.project.items.addComp(compName, compW, compH, 1.0, totalDuration, compFps);
            masterComp.parentFolder = masterFolder;
            setCompStartTimecode(masterComp, "00:59:53:00");

            if (!videoHas2Pop) {{
                var blackDuration = headDuration - slateDuration;
                var blackSolid = masterComp.layers.addSolid([0,0,0], "2s_Black", compW, compH, 1.0, blackDuration);
                blackSolid.startTime = slateDuration;
                blackSolid.outPoint = headDuration;
            }}

            var slateLayer = masterComp.layers.add(slateComp);
            slateLayer.startTime = 0;
            if (videoHas2Pop) {{
                slateLayer.outPoint = slateDuration;
            }} else if (usingAepTemplate) {{
                slateLayer.outPoint = slateDuration + masterComp.frameDuration;
            }} else {{
                slateLayer.outPoint = slateDuration;
                if (beepItem) {{
                    var beepLayer = masterComp.layers.add(beepItem);
                    beepLayer.startTime = slateDuration;
                    beepLayer.outPoint = slateDuration + masterComp.frameDuration;
                }}
            }}

            if (slateComp.width !== compW || slateComp.height !== compH) {{
                var sx = (compW / slateComp.width) * 100.0;
                var sy = (compH / slateComp.height) * 100.0;
                var sUniform = Math.min(sx, sy);
                slateLayer.property("Scale").setValue([sUniform, sUniform]);
            }}

            // Master Video is ALWAYS rendered native 100% scale without letterbox or crop
            var vidLayer = masterComp.layers.add(vidItem);
            vidLayer.startTime = headDuration;
            vidLayer.property("Scale").setValue([100, 100]);

            // Queue Slated Master to SLATED/ProRes (.mov 422 HQ) and SLATED/h264 (.mp4 25Mbps)
            queueProResAndH264(
                masterComp,
                job.slated_prores_output || job.final_output,
                job.slated_h264_output || ""
            );

            // Auto-transcode clean Master Video to UNSLATED/ProRes (.mov 422 HQ) and UNSLATED/h264 (.mp4 25Mbps)
            if (job.unslated_prores_output || job.unslated_h264_output) {{
                var cleanW = vidItem.width > 0 ? vidItem.width : compW;
                var cleanH = vidItem.height > 0 ? vidItem.height : compH;
                var cleanCompName = job.clean_stem ? (job.clean_stem + "_UNSLATED") : (slateId + "_UNSLATED");
                var cleanComp = null;
                var cleanLayer = null;
                if (videoHas2Pop) {{
                    // Video has a 2-pop leader (starts at 00:59:58:00). Trim the first 2.0s so picture begins at 01:00:00:00.
                    var twoSecFrames = Math.round(2.0 * nominalFps);
                    var twoSecDur = twoSecFrames / compFps;
                    var cleanDuration = Math.max(masterComp.frameDuration, vidItem.duration - twoSecDur);
                    cleanComp = app.project.items.addComp(cleanCompName, cleanW, cleanH, 1.0, cleanDuration, compFps);
                    cleanComp.parentFolder = unslatedFolder;
                    setCompStartTimecode(cleanComp, "01:00:00:00");
                    cleanLayer = cleanComp.layers.add(vidItem);
                    cleanLayer.startTime = -twoSecDur;
                    cleanLayer.inPoint = 0.0;
                    cleanLayer.outPoint = cleanDuration;
                }} else {{
                    // Clean video without leader starts directly at 01:00:00:00.
                    cleanComp = app.project.items.addComp(cleanCompName, cleanW, cleanH, 1.0, vidItem.duration, compFps);
                    cleanComp.parentFolder = unslatedFolder;
                    setCompStartTimecode(cleanComp, "01:00:00:00");
                    cleanLayer = cleanComp.layers.add(vidItem);
                    cleanLayer.startTime = 0.0;
                }}
                cleanLayer.property("Scale").setValue([100, 100]);
                queueProResAndH264(
                    unslatedComp,
                    job.unslated_prores_output || "",
                    job.unslated_h264_output || ""
                );
            }}
        }}

        app.endUndoGroup();

        if (skipped.length) {{ alert("Skipped (no matching slate template):\\n" + skipped.join("\\n")); }}
        var aepFile = new File({json.dumps(aep_path)});
        app.project.save(aepFile);
        __SJ_STATUS.rqItems = app.project.renderQueue.numItems;

        if (cfg.slates_only) {{
            try {{
                app.project.renderQueue.render();
                app.project.save(aepFile);
                __SJ_STATUS.rendered = true;
                __SJ_STATUS.queued = true;
            }} catch (eRen) {{
                __SJ_STATUS.error = "After Effects render failed: " + __sjErrText(eRen);
            }}
        }} else {{
            var queued = false, lastErr = "";
            for (var qa = 0; qa < 4 && !queued; qa++) {{
                try {{
                    app.project.renderQueue.queueInAME(false);
                    queued = true;
                    __SJ_STATUS.queued = true;
                }} catch (eQ) {{
                    lastErr = __sjErrText(eQ);
                    $.sleep(5000);
                }}
            }}
            if (!queued) {{
                __SJ_STATUS.error = "Could not queue in Adobe Media Encoder: " + lastErr;
            }}
        }}
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrap_jsx_with_status(jsx_code, path + ".status"))


if __name__ == "__main__":
    theme_arg = os.environ.get("SLATE_WORKSTATION_THEME", "superjoy")
    for arg in sys.argv[1:]:
        if arg.startswith("--theme="):
            theme_arg = arg.split("=", 1)[1]
        elif arg in ("--mstr-sl8r", "--mstr_sl8r", "-mstr"):
            theme_arg = "mstr_sl8r"
        elif arg in ("--superjoy", "-sj"):
            theme_arg = "superjoy"

    root = tk.Tk()
    app = SuperJoyWorkstation(root, theme=theme_arg)
    root.mainloop()

