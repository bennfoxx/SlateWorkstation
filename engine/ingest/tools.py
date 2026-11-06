"""Locate external tools (bundled first) and run ffprobe with a hard timeout."""
import json
import os
import shutil
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
# In the app bundle the engine lives in Contents/Resources/ingest; helpers go in Contents/Helpers.
_BUNDLE_HELPERS = os.path.normpath(os.path.join(_HERE, "..", "..", "Helpers"))
_FALLBACK_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]


def find_tool(name, env_var=None):
    if env_var and os.environ.get(env_var):
        p = os.environ[env_var]
        return p if os.access(p, os.X_OK) else None
    bundled = os.path.join(_BUNDLE_HELPERS, name)
    if os.access(bundled, os.X_OK):
        return bundled
    for d in _FALLBACK_DIRS:
        p = os.path.join(d, name)
        if os.access(p, os.X_OK):
            return p
    return shutil.which(name)


def ffprobe_path():
    return find_tool("ffprobe", "SLATE_FFPROBE")


def ffmpeg_path():
    return find_tool("ffmpeg", "SLATE_FFMPEG")


def redline_path():
    return find_tool("REDline", "SLATE_REDLINE")


def tool_info():
    return {"ffprobe": ffprobe_path(), "ffmpeg": ffmpeg_path(), "redline": redline_path()}


def probe(path, timeout=20):
    """ffprobe one file. Returns a flat dict, or {"probe_error": "..."}; never raises."""
    exe = ffprobe_path()
    if not exe:
        return {"probe_error": "ffprobe not found"}
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"probe_error": f"ffprobe timed out after {timeout}s"}
    except OSError as e:
        return {"probe_error": str(e)}
    if out.returncode != 0:
        return {"probe_error": (out.stderr.decode("utf-8", "replace").strip() or "ffprobe failed")[:300]}
    try:
        data = json.loads(out.stdout or b"{}")
    except ValueError:
        return {"probe_error": "unreadable ffprobe output"}
    return _flatten(data)


def _fps(rate):
    try:
        n, d = rate.split("/")
        n, d = float(n), float(d)
        return round(n / d, 3) if d else None
    except (ValueError, AttributeError):
        return None


def _flatten(data):
    fmt = data.get("format", {}) or {}
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    r = {"duration": None, "codec": None, "profile": None, "width": None, "height": None,
         "fps": None, "timecode": tags.get("timecode"), "audio_channels": 0,
         "creation_time": tags.get("creation_time"), "color_transfer": None,
         "pix_fmt": None, "bit_rate": None, "format": fmt.get("format_name")}
    try:
        r["duration"] = round(float(fmt.get("duration")), 3)
    except (TypeError, ValueError):
        pass
    try:
        r["bit_rate"] = int(fmt.get("bit_rate"))
    except (TypeError, ValueError):
        pass
    for s in data.get("streams", []) or []:
        st = {k.lower(): v for k, v in (s.get("tags") or {}).items()}
        kind = s.get("codec_type")
        if kind == "video" and r["codec"] is None and s.get("disposition", {}).get("attached_pic") != 1:
            r.update(codec=s.get("codec_name"), profile=s.get("profile"), width=s.get("width"),
                     height=s.get("height"), fps=_fps(s.get("avg_frame_rate")) or _fps(s.get("r_frame_rate")),
                     color_transfer=s.get("color_transfer"), pix_fmt=s.get("pix_fmt"))
            r["timecode"] = r["timecode"] or st.get("timecode")
        elif kind == "audio":
            r["audio_channels"] += int(s.get("channels") or 0)
        elif kind == "data" and not r["timecode"]:
            r["timecode"] = st.get("timecode")
    return r
