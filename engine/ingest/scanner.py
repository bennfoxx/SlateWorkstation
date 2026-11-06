"""Read-only scanner: finds camera cards / rolls under one or more source folders and
proposes Date / Cam / Roll for each. It never writes anything.

Recognised structures (Sony and RED first, per the production's camera mix):
  sony_xavc   <card>/PRIVATE/M4ROOT/CLIP/C0001.MP4 (+ C0001M01.XML, THMBNL/C0001T01.JPG)
  sony_xdcam  <card>/XDROOT/Clip/*.MXF (+ *M01.XML)
  red         <mag>.RDM/<clip>.RDC/<clip>_001.R3D … (segments grouped into one clip)
  generic     any other folder holding MOV / MP4 / MXF / MTS / R3D files (one folder = one roll)
"""
import datetime as dt
import os
import re
from concurrent.futures import ThreadPoolExecutor

from . import safefs, sony, tools

MEDIA_EXT = {".mov", ".mp4", ".mxf", ".mts", ".m4v", ".r3d", ".braw", ".avi"}
REPORT_EXT = {".csv", ".tsv", ".xlsx", ".pdf", ".mhl", ".html", ".txt"}
REPORT_HINT = re.compile(r"report|camera|cam.?log|log.?sheet|mhl|silverstack|shotput|offload", re.I)

# A001_C001_1106AB  (RED: cam letter, reel, clip, MMDD, 2-char id)
RED_NAME = re.compile(r"^([A-Z])(\d{3})_C(\d{3})_(\d{2})(\d{2})[A-Z0-9]{2}", re.I)
# A001C003_261106_R1AB  (ARRI / Venice style: YYMMDD)
REEL_NAME = re.compile(r"^([A-Z])(\d{3})C(\d{3})_(\d{2})(\d{2})(\d{2})", re.I)
CAM_FOLDER = re.compile(r"^(?:([A-Z])[ _-]?cam(?:era)?|cam(?:era)?[ _-]?([A-Z]))$", re.I)
ROLL_FOLDER = re.compile(r"^([A-Z])(\d{3})$", re.I)
CLIP_NUM = re.compile(r"C(\d{3,4})", re.I)


def _is_junk(name):
    return name in safefs.JUNK_NAMES or name.startswith("._")


def _scandir(path):
    try:
        with os.scandir(path) as it:
            return sorted(it, key=lambda e: e.name)
    except OSError:
        return []


def _child(path, *names):
    """Case-insensitive child lookup (exFAT cards are mixed case)."""
    cur = path
    for n in names:
        match = next((e.path for e in _scandir(cur) if e.name.lower() == n.lower()
                      and e.is_dir(follow_symlinks=False)), None)
        if not match:
            return None
        cur = match
    return cur


def _stat(path):
    try:
        return os.stat(path, follow_symlinks=False)
    except OSError:
        return None


# ---------------------------------------------------------------- clip builders

def _clip(name, paths, kind):
    st = [_stat(p) for p in paths]
    return {"name": name, "paths": paths, "kind": kind,
            "bytes": sum(s.st_size for s in st if s),
            "mtime": min((s.st_mtime for s in st if s), default=None),
            "meta": {}, "thumbnail_source": None, "report": {}}


def _sony_clips(clip_dir, thumb_dir, kind):
    clips = []
    entries = _scandir(clip_dir)
    xml_by_stem = {}
    for e in entries:
        low = e.name.lower()
        if low.endswith(".xml") and low[:-4].upper().endswith("M01"):
            xml_by_stem[e.name[:-7].lower()] = e.path
    thumbs = {}
    if thumb_dir:
        for e in _scandir(thumb_dir):
            if e.name.lower().endswith(".jpg"):
                thumbs[re.sub(r"t01$", "", os.path.splitext(e.name)[0], flags=re.I).lower()] = e.path
    for e in entries:
        stem, ext = os.path.splitext(e.name)
        if ext.lower() not in MEDIA_EXT or _is_junk(e.name) or not e.is_file(follow_symlinks=False):
            continue
        c = _clip(stem, [e.path], kind)
        xml = xml_by_stem.get(stem.lower())
        if xml:
            c["sidecar"] = xml
            c["meta"]["sony"] = sony.parse_xml(xml)
        c["thumbnail_source"] = thumbs.get(stem.lower())
        clips.append(c)
    return clips


def _red_clip(rdc_dir):
    segs = sorted(e.path for e in _scandir(rdc_dir)
                  if e.name.lower().endswith(".r3d") and not _is_junk(e.name))
    if not segs:
        return None
    name = os.path.splitext(os.path.basename(rdc_dir))[0]
    return _clip(name, segs, "red")


# ---------------------------------------------------------------- discovery

def discover(sources, on_progress=None):
    """Walk sources (no symlinks followed) and return (raw_rolls, found_reports)."""
    rolls, reports = [], []
    seen_dirs = 0
    for src in sources:
        stack = [safefs.real(src)]
        while stack:
            d = stack.pop()
            seen_dirs += 1
            if on_progress and seen_dirs % 200 == 0:
                on_progress(seen_dirs)
            entries = _scandir(d)
            names = {e.name.lower(): e for e in entries}
            skip = set()

            # Sony XAVC (M4ROOT)
            m4 = _child(d, "PRIVATE", "M4ROOT")
            if m4 and _child(m4, "CLIP"):
                clips = _sony_clips(_child(m4, "CLIP"), _child(m4, "THMBNL"), "sony_xavc")
                if clips:
                    rolls.append({"kind": "sony_xavc", "root": d, "clips": clips})
                skip.add("private")
            # Sony XDCAM / FX9 / Venice (XDROOT)
            xd = _child(d, "XDROOT")
            if xd and _child(xd, "Clip"):
                clips = _sony_clips(_child(xd, "Clip"), _child(xd, "Thmbnl"), "sony_xdcam")
                if clips:
                    rolls.append({"kind": "sony_xdcam", "root": d, "clips": clips})
                skip.add("xdroot")

            loose_media, loose_rdc = [], []
            for e in entries:
                low = e.name.lower()
                if _is_junk(e.name) or low in skip:
                    continue
                if e.is_dir(follow_symlinks=False):
                    if low.endswith(".rdm"):
                        clips = [c for c in (_red_clip(x.path) for x in _scandir(e.path)
                                             if x.name.lower().endswith(".rdc")) if c]
                        if clips:
                            rolls.append({"kind": "red", "root": e.path, "clips": clips})
                    elif low.endswith(".rdc"):
                        loose_rdc.append(e.path)
                    elif low == "ascmhl":
                        reports.append({"path": e.path, "type": "mhl", "dir": d})
                    else:
                        stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    ext = os.path.splitext(low)[1]
                    if ext in MEDIA_EXT:
                        loose_media.append(e)
                    elif ext in REPORT_EXT and (ext == ".mhl" or REPORT_HINT.search(e.name)):
                        reports.append({"path": e.path, "type": ext.lstrip("."), "dir": d})

            if loose_rdc:
                clips = [c for c in map(_red_clip, loose_rdc) if c]
                if clips:
                    rolls.append({"kind": "red", "root": d, "clips": clips})
            if loose_media:
                # Group loose R3D segments (A001_C001_1106AB_001.R3D, _002 …) into one clip.
                groups = {}
                for e in loose_media:
                    stem, ext = os.path.splitext(e.name)
                    key = re.sub(r"_\d{3}$", "", stem) if ext.lower() == ".r3d" else stem
                    groups.setdefault((key, ext.lower()), []).append(e.path)
                clips = [_clip(k, sorted(p), "red" if ext == ".r3d" else "generic")
                         for (k, ext), p in sorted(groups.items())]
                rolls.append({"kind": "generic", "root": d, "clips": clips})
    return rolls, reports


# ---------------------------------------------------------------- metadata

def _parse_dt(value):
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        t = dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    if t.tzinfo is not None:
        t = t.astimezone().replace(tzinfo=None)  # shoot-local = this machine's zone
    return t


def _clip_datetime(c):
    sony_meta = c["meta"].get("sony", {})
    t = _parse_dt(sony_meta.get("created"))
    if t:
        return t, "sony_xml"
    t = _parse_dt((c["meta"].get("probe") or {}).get("creation_time"))
    if t and t.year > 1990:
        return t, "embedded"
    mtime = dt.datetime.fromtimestamp(c["mtime"]) if c["mtime"] else None
    m = RED_NAME.match(c["name"])
    if m:
        year = mtime.year if mtime else dt.date.today().year
        try:
            t = dt.datetime(year, int(m.group(4)), int(m.group(5)))
            if mtime and t > mtime + dt.timedelta(days=1):
                t = t.replace(year=year - 1)
            return t, "clip_name"
        except ValueError:
            pass
    m = REEL_NAME.match(c["name"])
    if m:
        try:
            return dt.datetime(2000 + int(m.group(4)), int(m.group(5)), int(m.group(6))), "clip_name"
        except ValueError:
            pass
    if mtime:
        return mtime, "file_modified"
    return None, None


def _summarise_clip(c):
    s = c["meta"].get("sony", {})
    p = c["meta"].get("probe", {})
    tc = s.get("tc_start") or p.get("timecode")
    fps = p.get("fps")
    if fps is None and s.get("capture_fps"):
        try:
            fps = float(re.sub(r"[^\d.]", "", s["capture_fps"]))
        except ValueError:
            pass
    c["info"] = {
        "codec": p.get("codec") or s.get("video_codec") or ("REDCODE RAW" if c["kind"] == "red" else None),
        "width": p.get("width") or _int(s.get("width")),
        "height": p.get("height") or _int(s.get("height")),
        "fps": fps,
        "duration": p.get("duration"),
        "timecode": tc,
        "audio_channels": p.get("audio_channels") or _int(s.get("audio_channels")),
        "camera_model": s.get("model"),
        "camera_serial": s.get("serial"),
        "gamma": s.get("gamma") or p.get("color_transfer"),
        "gamut": s.get("gamut"),
        "probe_error": p.get("probe_error"),
    }


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _probe_all(rolls, workers, on_progress):
    jobs = [c for r in rolls for c in r["clips"] if c["kind"] != "red"]
    if not jobs:
        return
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for c, res in zip(jobs, ex.map(lambda c: tools.probe(c["paths"][0]), jobs)):
            c["meta"]["probe"] = res
            done += 1
            if on_progress and (done % 10 == 0 or done == len(jobs)):
                on_progress(done, len(jobs))


# ---------------------------------------------------------------- organise

def _path_hints(root, sources):
    """Cam letter / roll name from folder names like 'A Cam/A003'."""
    cam = roll = None
    base = next((safefs.real(s) for s in sources if safefs.is_within(root, s)), None)
    # Relative to the source's parent, so a source folder itself named "A001" still counts.
    rel = os.path.relpath(root, os.path.dirname(base)) if base else root
    for part in rel.split(os.sep):
        m = CAM_FOLDER.match(part)
        if m:
            cam = (m.group(1) or m.group(2)).upper()
        part_stem = os.path.splitext(part)[0]
        m = ROLL_FOLDER.match(part_stem) or ROLL_FOLDER.match(part_stem.split("_")[0])
        if m:
            roll = part_stem.split("_")[0].upper()
            cam = cam or m.group(1).upper()
    return cam, roll


def organise(raw_rolls, sources, day_start_hour=0):
    rolls = []
    for r in raw_rolls:
        for c in r["clips"]:
            _summarise_clip(c)
            t, src = _clip_datetime(c)
            c["datetime"] = t.isoformat(timespec="seconds") if t else None
            c["date_source"] = src
        first = next((c for c in r["clips"] if c["datetime"]), None)
        when = dt.datetime.fromisoformat(first["datetime"]) if first else None
        shoot_day = (when - dt.timedelta(hours=day_start_hour)).date() if when else None

        name_cam = name_roll = None
        for c in r["clips"]:
            m = RED_NAME.match(c["name"]) or REEL_NAME.match(c["name"])
            if m:
                name_cam, name_roll = m.group(1).upper(), f"{m.group(1).upper()}{m.group(2)}"
                break
        hint_cam, hint_roll = _path_hints(r["root"], sources)
        models = sorted({c["info"]["camera_model"] for c in r["clips"] if c["info"]["camera_model"]})
        serials = sorted({c["info"]["camera_serial"] for c in r["clips"] if c["info"]["camera_serial"]})
        rolls.append({
            "id": f"r{len(rolls) + 1}",
            "kind": r["kind"], "root": r["root"],
            "date": shoot_day.isoformat() if shoot_day else None,
            "date_source": first["date_source"] if first else None,
            "cam": name_cam or hint_cam, "roll": name_roll or hint_roll,
            "cam_source": "clip_name" if name_cam else ("folder" if hint_cam else None),
            "camera_model": ", ".join(models) or None,
            "camera_serial": ", ".join(serials) or None,
            "_identity": serials[0] if serials else (models[0] if models else None),
            "_sort": when or dt.datetime.max,
            "clips": r["clips"],
        })

    # Cameras without a letter: give each camera identity the next free letter.
    used = {r["cam"] for r in rolls if r["cam"]}
    by_identity = {r["_identity"]: r["cam"] for r in rolls if r["cam"] and r["_identity"]}
    letters = (chr(c) for c in range(ord("A"), ord("Z") + 1))
    for r in sorted(rolls, key=lambda r: (r["_sort"], r["root"])):
        if r["cam"]:
            continue
        key = r["_identity"] or f"unknown:{r['root']}"
        if key not in by_identity:
            by_identity[key] = next(l for l in letters if l not in used)
            used.add(by_identity[key])
        r["cam"] = by_identity[key]
        r["cam_source"] = "auto"

    # Rolls without a name: next number per cam, in shooting order.
    top = {}
    for r in rolls:
        if r["roll"]:
            top[r["cam"]] = max(top.get(r["cam"], 0), int(r["roll"][1:]))
    for r in sorted(rolls, key=lambda r: (r["_sort"], r["root"])):
        if not r["roll"]:
            top[r["cam"]] = top.get(r["cam"], 0) + 1
            r["roll"] = f"{r['cam']}{top[r['cam']]:03d}"
            r["roll_source"] = "auto"
        else:
            r.setdefault("roll_source", "clip_name" if r["cam_source"] == "clip_name" else "folder")

    for r in rolls:
        r.pop("_identity"), r.pop("_sort")
        r["clip_count"] = len(r["clips"])
        r["bytes"] = sum(c["bytes"] for c in r["clips"])
        r["duration"] = round(sum(c["info"]["duration"] or 0 for c in r["clips"]), 3)
        r["codecs"] = sorted({c["info"]["codec"] for c in r["clips"] if c["info"]["codec"]})
        r["gammas"] = sorted({c["info"]["gamma"] for c in r["clips"] if c["info"]["gamma"]})
        fmt = next((c["info"] for c in r["clips"] if c["info"]["width"]), None)
        r["format"] = f"{fmt['width']}x{fmt['height']} @ {fmt['fps']}" if fmt else None
        r["clips"].sort(key=lambda c: (c["datetime"] or "", c["name"]))
    rolls.sort(key=lambda r: (r["date"] or "9999", r["cam"], r["roll"]))
    return rolls


def attach_reports(rolls, reports):
    """Point each found report/MHL at the deepest roll whose root it sits in or above."""
    for r in rolls:
        r["found_reports"] = []
    loose = []
    for rep in reports:
        owners = [r for r in rolls if safefs.is_within(r["root"], rep["dir"])
                  or safefs.is_within(rep["dir"], r["root"])]
        if len(owners) == 1:
            owners[0]["found_reports"].append(rep["path"])
        else:
            loose.append(rep["path"])
    return loose


def scan(sources, probe=True, probe_workers=3, day_start_hour=0, on_progress=None):
    raw, reports = discover(sources, on_progress=(lambda n: on_progress("walk", n, None)) if on_progress else None)
    if probe:
        _probe_all(raw, probe_workers, (lambda d, t: on_progress("probe", d, t)) if on_progress else None)
    rolls = organise(raw, sources, day_start_hour=day_start_hour)
    loose = attach_reports(rolls, reports)
    return {"rolls": rolls, "reports_unassigned": loose}
