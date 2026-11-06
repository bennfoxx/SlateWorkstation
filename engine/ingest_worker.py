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
  tools                                          -> resolved ffprobe / ffmpeg / REDline paths + capabilities
  plan          --job FILE|-                     -> preflight (read-only): space, conflicts, LUTs, errors
  run           --job FILE|-                     -> copy / verify / MHL / transcode / report (see pipeline.py)
  verify-mhl    --mhl FILE [--root DIR]          -> re-hash files listed in an MHL v1/v2 (read-only)
  luts          --library DIR [--gamma G ...]    -> LUTs in a library + suggestions per gamma
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

import signal  # noqa: E402
import threading  # noqa: E402

from ingest import camreport, hashing, luts, mhl, pipeline, safefs, scanner, tools, transcode  # noqa: E402


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


def _load_job(arg):
    return json.load(sys.stdin if arg == "-" else open(arg, "r", encoding="utf-8"))


def cmd_plan(a):
    res = pipeline.plan(_load_job(a.job))
    emit("result", ok=True, plan=res)


def cmd_run(a):
    stop = threading.Event()
    runner = pipeline.Runner(_load_job(a.job), emit=emit, stop=stop)

    def on_term(signum, frame):  # Stop button: finish nothing new, kill ffmpeg, keep partials discarded
        log("Stopping…")
        runner.stop_now()

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    res = runner.run()
    emit("result", **{"ok": res.pop("ok", False), **res})


def cmd_verify_mhl(a):
    res = mhl.verify(a.mhl, a.root, on_progress=lambda d, t: progress("verify", d, t))
    log(f"{os.path.basename(a.mhl)}: {res['verified']}/{res['files']} verified, "
        f"{len(res['mismatched'])} mismatched, {len(res['missing'])} missing")
    emit("result", ok=True, verify=res)


def cmd_luts(a):
    lib = luts.library(a.library)
    emit("result", ok=True, library=lib,
         suggestions={g: luts.suggest(g, a.library) for g in (a.gamma or [])})


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
    p = sub.add_parser("plan"); p.add_argument("--job", required=True)
    p = sub.add_parser("run"); p.add_argument("--job", required=True)
    p = sub.add_parser("verify-mhl"); p.add_argument("--mhl", required=True); p.add_argument("--root")
    p = sub.add_parser("luts"); p.add_argument("--library", required=True); p.add_argument("--gamma", action="append")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "scan":
            cmd_scan(a)
        elif a.cmd == "import-report":
            cmd_import(a)
        elif a.cmd == "camera-report":
            cmd_camera_report(a)
        elif a.cmd == "plan":
            cmd_plan(a)
        elif a.cmd == "run":
            cmd_run(a)
        elif a.cmd == "verify-mhl":
            cmd_verify_mhl(a)
        elif a.cmd == "luts":
            cmd_luts(a)
        else:
            caps = transcode.capabilities()
            emit("result", ok=True, tools=tools.tool_info(), hashes=hashing.AVAILABLE, hash_default=hashing.DEFAULT,
                 encoders=[e for e in caps.get("encoders", []) if e in
                           ("prores_videotoolbox", "prores_ks", "h264_videotoolbox", "libx264")],
                 filters=[f for f in caps.get("filters", []) if f in ("lut3d", "drawtext")],
                 ffmpeg_version=caps.get("version"))
        return 0
    except Exception as e:
        emit("result", ok=False, error=f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
