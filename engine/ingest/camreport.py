"""Camera reports: import existing ones (CSV / TSV / XLSX) onto scanned clips, and
generate new per-roll reports (HTML + CSV, with thumbnails) when none exist."""
import csv
import datetime as dt
import html
import io
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

from . import safefs, tools

# canonical field -> header spellings seen on AC sheets, Silverstack and ShotPut exports
FIELDS = {
    "roll": ["roll", "reel", "card", "mag", "magazine", "reel name", "tape", "roll #"],
    "clip": ["clip", "clip name", "file", "file name", "filename", "name", "clip #", "clip id"],
    "scene": ["scene", "sc", "scene #"],
    "take": ["take", "tk", "take #"],
    "shot": ["shot", "slate", "setup"],
    "lens": ["lens", "focal length", "focal", "mm", "lens (mm)"],
    "stop": ["stop", "t-stop", "tstop", "t stop", "iris", "aperture", "f-stop"],
    "iso": ["iso", "ei", "asa", "exposure index"],
    "shutter": ["shutter", "shutter angle", "shutter speed"],
    "wb": ["wb", "white balance", "kelvin", "color temp"],
    "filter": ["filter", "filters", "nd"],
    "circled": ["circled", "circle", "good", "print", "select"],
    "notes": ["notes", "note", "comments", "comment", "description", "remarks"],
}
_HEADER_MAP = {alias: key for key, aliases in FIELDS.items() for alias in aliases}


def _norm_header(h):
    return re.sub(r"\s+", " ", str(h or "").strip().lower().replace("_", " "))


def _norm_name(s):
    s = os.path.splitext(os.path.basename(str(s or "").strip()))[0]
    s = re.sub(r"_\d{3}$", "", s)  # R3D segment suffix
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------- reading files

def _read_xlsx(path):
    with safefs.open_source(path) as f, zipfile.ZipFile(io.BytesIO(f.read())) as z:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheet = next((n for n in sorted(z.namelist()) if n.startswith("xl/worksheets/sheet")), None)
        if not sheet:
            return []
        rows = []
        for row in ET.fromstring(z.read(sheet)).iter(f"{{{ns['m']}}}row"):
            vals = {}
            for c in row.findall("m:c", ns):
                col = re.match(r"[A-Z]+", c.get("r", "A")).group(0)
                idx = 0
                for ch in col:
                    idx = idx * 26 + (ord(ch) - 64)
                v = c.find("m:v", ns)
                text = v.text if v is not None else "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
                if c.get("t") == "s" and text not in (None, ""):
                    text = shared[int(text)]
                vals[idx - 1] = text or ""
            if vals:
                rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
        return rows


def _read_table(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        return _read_xlsx(path)
    with safefs.open_source(path) as f:
        text = f.read().decode("utf-8-sig", "replace")
    delim = "\t" if ext == ".tsv" or text.count("\t") > text.count(",") else ","
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def read_report(path):
    """Return a list of dicts keyed by canonical field names (+ 'extra' for the rest)."""
    table = [r for r in _read_table(path) if any(str(c).strip() for c in r)]
    # Header = first row (within the first 15) that maps to a clip/roll column.
    for hi, row in enumerate(table[:15]):
        keys = [_HEADER_MAP.get(_norm_header(h)) for h in row]
        if "clip" in keys or ("roll" in keys and "take" in keys):
            break
    else:
        raise ValueError("No Clip / File Name (or Roll + Take) column found in the first 15 rows.")
    headers = table[hi]
    out = []
    for row in table[hi + 1:]:
        rec, extra = {}, {}
        for h, key, val in zip(headers, keys, row):
            val = str(val).strip()
            if not val:
                continue
            if key and key not in rec:
                rec[key] = val
            elif str(h).strip():
                extra[str(h).strip()] = val
        if rec:
            rec["extra"] = extra
            out.append(rec)
    return out


# ---------------------------------------------------------------- import / merge

def merge_report(rolls, path):
    records = read_report(path)
    by_name = {}
    for r in rolls:
        for c in r["clips"]:
            by_name.setdefault(_norm_name(c["name"]), []).append((r, c))
    matched, unmatched = 0, []
    for rec in records:
        hits = by_name.get(_norm_name(rec.get("clip"))) if rec.get("clip") else None
        if not hits and rec.get("roll"):
            # Fallback: roll + clip number (e.g. roll A001, clip "3" or "C003").
            want_roll = rec["roll"].strip().upper()
            num = re.search(r"(\d+)\s*$", rec.get("clip", ""))
            if num:
                n = int(num.group(1))
                hits = [(r, c) for r in rolls if r["roll"].upper() == want_roll
                        for c in r["clips"] if _clip_number(c["name"]) == n]
        if hits and len(hits) == 1:
            r, c = hits[0]
            c["report"] = {k: v for k, v in rec.items() if k not in ("clip", "roll")}
            c["report"]["source"] = os.path.basename(path)
            if path not in r.setdefault("imported_reports", []):
                r["imported_reports"].append(path)
            matched += 1
        else:
            unmatched.append(rec.get("clip") or f"{rec.get('roll', '?')} / {rec.get('take', '?')}")
    return {"rows": len(records), "matched": matched, "unmatched": unmatched[:50],
            "unmatched_count": len(unmatched)}


def _clip_number(name):
    m = re.search(r"C(\d{3,4})", name, re.I)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- generation

def _fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1000


def _fmt_dur(sec):
    if not sec:
        return ""
    sec = int(round(sec))
    return f"{sec // 3600:d}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def _thumb(clip, out_path, sources, ffmpeg):
    """Returns (relative-ready path or None, note)."""
    safefs.assert_outside_sources(out_path, sources)
    if clip.get("thumbnail_source"):  # Sony card thumbnail: just copy the bytes
        with safefs.open_source(clip["thumbnail_source"]) as f:
            safefs.write_new(out_path, f.read(), sources)
        return out_path, "card thumbnail"
    if clip["kind"] == "red":
        return None, "R3D: thumbnail needs REDline or AME (not run in this phase)"
    if not ffmpeg:
        return None, "ffmpeg not found"
    dur = clip["info"].get("duration") or 0
    seek = max(0.0, min(dur * 0.1, dur - 0.5)) if dur else 0
    try:
        p = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-n", "-ss", f"{seek:.2f}",
                            "-i", clip["paths"][0], "-frames:v", "1",
                            "-vf", "scale=320:-2", "-q:v", "4", out_path],
                           capture_output=True, timeout=45, check=False)
    except subprocess.TimeoutExpired:
        return None, "thumbnail timed out"
    if p.returncode == 0 and os.path.exists(out_path):
        return out_path, "ffmpeg"
    return None, (p.stderr.decode("utf-8", "replace").strip().splitlines() or ["ffmpeg failed"])[-1][:200]


CSV_COLUMNS = ["Date", "Cam", "Roll", "Clip", "Timecode In", "Duration", "FPS", "Resolution",
               "Codec", "Camera", "Serial", "Gamma", "Audio Ch", "Size", "Scene", "Take",
               "Lens", "Stop", "ISO", "Circled", "Notes", "Source Path"]


def _row(r, c):
    i, rep = c["info"], c.get("report", {})
    return [r["date"] or "", r["cam"], r["roll"], c["name"], i["timecode"] or "",
            _fmt_dur(i["duration"]), i["fps"] or "",
            f"{i['width']}x{i['height']}" if i["width"] else "", i["codec"] or "",
            i["camera_model"] or "", i["camera_serial"] or "", i["gamma"] or "",
            i["audio_channels"] or "", _fmt_bytes(c["bytes"]), rep.get("scene", ""), rep.get("take", ""),
            rep.get("lens", ""), rep.get("stop", ""), rep.get("iso", ""), rep.get("circled", ""),
            rep.get("notes", ""), c["paths"][0]]


def generate(rolls, out_dir, sources, thumbnails=True, workers=2, on_progress=None):
    """Write one folder per roll: <out>/<date>/<cam>/<roll>_camera_report/{report.html, report.csv, thumbs/}."""
    safefs.assert_outside_sources(out_dir, sources)
    ffmpeg = tools.ffmpeg_path() if thumbnails else None
    written = []
    total = sum(len(r["clips"]) for r in rolls)
    done = 0
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    for r in rolls:
        base = os.path.join(out_dir, r["date"] or "undated", f"{r['cam']}-Cam")
        safefs.ensure_dir(base, sources)
        folder = safefs.make_new_dir(os.path.join(base, f"{r['roll']}_camera_report"), sources)
        thumbs_dir = safefs.ensure_dir(os.path.join(folder, "thumbs"), sources) if thumbnails else None

        notes = {}
        if thumbnails:
            def job(c):
                safe = re.sub(r"[^A-Za-z0-9._-]", "_", c["name"])
                return c["name"], _thumb(c, os.path.join(thumbs_dir, safe + ".jpg"), sources, ffmpeg)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                for name, res in ex.map(job, r["clips"]):
                    notes[name] = res
                    done += 1
                    if on_progress:
                        on_progress(done, total)

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(CSV_COLUMNS)
        for c in r["clips"]:
            w.writerow(_row(r, c))
        safefs.write_new(os.path.join(folder, f"{r['roll']}_camera_report.csv"), buf.getvalue(), sources)
        html_path = os.path.join(folder, f"{r['roll']}_camera_report.html")
        safefs.write_new(html_path, _html(r, notes, stamp), sources)
        written.append({"roll": r["roll"], "folder": folder, "html": html_path})
    return written


def _html(r, notes, stamp):
    e = html.escape
    rows = []
    for c in r["clips"]:
        i, rep = c["info"], c.get("report", {})
        tpath, tnote = notes.get(c["name"], (None, ""))
        img = (f'<img src="thumbs/{e(os.path.basename(tpath))}" alt="">' if tpath
               else f'<div class="nothumb">{e(tnote or "no thumbnail")}</div>')
        slate = " · ".join(x for x in (f"Sc {rep['scene']}" if rep.get("scene") else "",
                                       f"Tk {rep['take']}" if rep.get("take") else "",
                                       "◯ circled" if rep.get("circled") else "") if x)
        lens = " · ".join(x for x in (rep.get("lens", ""), rep.get("stop", ""),
                                      f"ISO {rep['iso']}" if rep.get("iso") else "") if x)
        rows.append(f"""<tr><td class="t">{img}</td>
<td><b>{e(c['name'])}</b><div class="m">{e(slate)}</div><div class="m">{e(rep.get('notes', ''))}</div></td>
<td>{e(i['timecode'] or '')}<div class="m">{_fmt_dur(i['duration'])}</div></td>
<td>{e(f"{i['width']}x{i['height']}" if i['width'] else '')}<div class="m">{e(str(i['fps'] or ''))} fps</div></td>
<td>{e(i['codec'] or '')}<div class="m">{e(i['gamma'] or '')}</div></td>
<td>{e(lens)}</td><td class="r">{_fmt_bytes(c['bytes'])}</td></tr>""")
    meta = [("Date", r["date"] or "—"), ("Camera", f"{r['cam']} Cam · {r['camera_model'] or 'unknown model'}"),
            ("Serial", r["camera_serial"] or "—"), ("Format", r["format"] or "—"),
            ("Clips", str(r["clip_count"])), ("Total", f"{_fmt_bytes(r['bytes'])} · {_fmt_dur(r['duration'])}"),
            ("Source", r["root"])]
    meta_html = "".join(f"<div><span>{e(k)}</span>{e(v)}</div>" for k, v in meta)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{e(r['roll'])} Camera Report</title>
<style>
body{{font:13px -apple-system,Helvetica,sans-serif;margin:28px;color:#111;background:#fff}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#666;margin-bottom:16px}}
.meta{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px 18px;margin-bottom:18px}}
.meta span{{display:block;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:.06em}}
.meta div{{overflow-wrap:anywhere}}
table{{border-collapse:collapse;width:100%}} th{{text-align:left;font-size:10px;text-transform:uppercase;color:#888;border-bottom:1px solid #ccc;padding:6px}}
td{{border-bottom:1px solid #eee;padding:6px;vertical-align:top}} .r{{text-align:right;white-space:nowrap}}
.t img{{width:160px;display:block;border-radius:3px}} .nothumb{{width:160px;height:90px;background:#f1f1f1;color:#888;font-size:10px;display:flex;align-items:center;justify-content:center;text-align:center;padding:4px;box-sizing:border-box}}
.m{{color:#666;font-size:11px;margin-top:2px}} tr{{page-break-inside:avoid}}
</style></head><body>
<h1>{e(r['roll'])} — Camera Report</h1>
<div class="sub">Generated {e(stamp)} by MSTR-SL8R Ingest · source media opened read-only</div>
<div class="meta">{meta_html}</div>
<table><thead><tr><th>Thumb</th><th>Clip</th><th>TC In / Dur</th><th>Res / FPS</th><th>Codec / Gamma</th><th>Lens</th><th class="r">Size</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""
