#!/usr/bin/env python3
"""
Headless worker for the media ingest engine (engine/ingest). Same JSON-lines protocol
as slate_worker.py: one JSON object per stdout line, final line is a "result" event.
  {"event": "log", "message": "..."}
  {"event": "progress", "stage": "walk|probe|thumbs", "done": n, "total": m|null}
  {"event": "result", "ok": true|false, ...}

Commands (all read-only with respect to the source media):
  scan          --source DIR [--source DIR ...] [--report FILE ...] [--no-probe]
                [--day-start-hour N] [--probe-workers N]
                -> rolls (Date / Cam / Roll proposals with clips); camera reports found on
                   the media (CSV/TSV/XLSX) are imported automatically
  import-report --scan FILE|- --report FILE      -> rolls with report fields merged onto clips
  camera-report --scan FILE|- --out DIR [--no-thumbs] -> written report folders
  tools                                          -> resolved ffprobe / ffmpeg / REDline paths
--scan takes the JSON produced by `scan` ({"sources": [...], "rolls": [...]}), possibly
with Cam / Roll edited by the user.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import camreport, safefs, scanner, tools  # noqa: E402


def emit(event, **fields):
    sys.stdout.write(json.dumps({"event": event, **fields}, default=str) + "\n")
    sys.stdout.flush()


def log(msg):
    emit("log", message=msg)


def progress(stage, done, total):
    emit("progress", stage=stage, done=done, total=total)


def _load_scan(arg):
    data = json.load(sys.stdin if arg == "-" else open(arg, "r", encoding="utf-8"))
    if not data.get("sources") or not isinstance(data.get("rolls"), list):
        raise ValueError("scan JSON needs 'sources' and 'rolls'")
    return data


def cmd_scan(a):
    sources = []
    for s in a.source:
        if not os.path.isdir(s):
            raise ValueError(f"Source folder not found: {s}")
        sources.append(safefs.real(s))
    log(f"Scanning {len(sources)} source(s) read-only…")
    res = scanner.scan(sources, probe=not a.no_probe, probe_workers=a.probe_workers,
                       day_start_hour=a.day_start_hour, on_progress=progress)
    rolls = res["rolls"]
    imports = []
    auto = [p for r in rolls for p in r["found_reports"]
            if os.path.splitext(p)[1].lower() in (".csv", ".tsv", ".xlsx")]
    for path in list(dict.fromkeys(auto + list(a.report or []))):
        try:
            imports.append({"path": path, **camreport.merge_report(rolls, path)})
        except Exception as e:  # a bad report must never fail the scan
            imports.append({"path": path, "error": str(e)})
    clips = sum(r["clip_count"] for r in rolls)
    log(f"Found {len(rolls)} roll(s), {clips} clip(s).")
    emit("result", ok=True, sources=sources, rolls=rolls, imports=imports,
         reports_unassigned=res["reports_unassigned"], tools=tools.tool_info())


def cmd_import(a):
    data = _load_scan(a.scan)
    summary = camreport.merge_report(data["rolls"], a.report)
    log(f"{os.path.basename(a.report)}: matched {summary['matched']} of {summary['rows']} row(s).")
    emit("result", ok=True, sources=data["sources"], rolls=data["rolls"], import_summary=summary)


def cmd_camera_report(a):
    data = _load_scan(a.scan)
    out = safefs.real(a.out)
    written = camreport.generate(data["rolls"], out, data["sources"], thumbnails=not a.no_thumbs,
                                 on_progress=lambda d, t: progress("thumbs", d, t))
    log(f"Wrote {len(written)} camera report(s) to {out}")
    emit("result", ok=True, written=written)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--report", action="append")
    p.add_argument("--no-probe", action="store_true")
    p.add_argument("--probe-workers", type=int, default=3)
    p.add_argument("--day-start-hour", type=int, default=0)
    p = sub.add_parser("import-report")
    p.add_argument("--scan", required=True)
    p.add_argument("--report", required=True)
    p = sub.add_parser("camera-report")
    p.add_argument("--scan", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--no-thumbs", action="store_true")
    sub.add_parser("tools")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "scan":
            cmd_scan(a)
        elif a.cmd == "import-report":
            cmd_import(a)
        elif a.cmd == "camera-report":
            cmd_camera_report(a)
        else:
            emit("result", ok=True, tools=tools.tool_info())
        return 0
    except Exception as e:
        emit("result", ok=False, error=f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
