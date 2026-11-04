#!/usr/bin/env python3
"""
Headless worker for the SlateWorkstation engine.

The native SwiftUI app (and anything else) drives the battle-tested After Effects /
Adobe Media Encoder pipeline in SuperJoy_Slating_App.py through this CLI, without
creating a Tk window. The workflow methods (process_batch / process_marry /
process_unslate) and the JSX generators are reused as-is: they are called with a
HeadlessHost standing in for the Tk window, so the Tk app and this worker always
produce identical JSX.

Protocol: every line written to stdout is one JSON object with an "event" key:
  {"event": "log",     "message": "..."}
  {"event": "alert",   "level": "info|warning|error", "title": "...", "message": "..."}
  {"event": "previews","items": [{"id","aspect","title","image_path"}, ...]}
  {"event": "result",  "ok": true|false, ...command-specific fields}
The final line is always a "result" event. Exit code 0 = ok, 1 = failed, 2 = bad usage.

Commands:
  parse        --file PATH                      -> rows (normalized slate rows)
  scan-videos  --videos DIR [--aspects A,B] [--shared JSON] -> rows built from master video file names
  scan-marry   --slates DIR --videos DIR [--csv PATH] -> pairs
  run          --job JOB.json | --job -         -> runs one workflow (see JOB keys below)
  info                                          -> constants (themes, aspects, fps presets, defaults)

JOB keys (run):
  mode: "batch" | "marry" | "unslate"     theme: "superjoy" | "mstr_sl8r"
  fps: number (default 23.976)             aspect: "16x9" | "1x1" | "4x5" | "9x16" | "2x3"
  output_dir, auto_transcode (bool, default true), dry_run (bool)
  batch:   template (.aep path, default bundled), videos_dir, slates_only (bool),
           workspace, rows (list of slate dicts) OR spreadsheet (path)
  marry:   slates_dir, videos_dir, csv (optional)
  unslate: unslate_dir
dry_run writes the generated JSX next to the outputs (as *.dryrun.jsx) instead of
running After Effects / launching Media Encoder.
"""
import argparse
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import SuperJoy_Slating_App as engine  # noqa: E402  (import has no UI side effects)

_W = engine.SuperJoyWorkstation  # unbound workflow methods are reused with HeadlessHost


def emit(event, **fields):
    fields["event"] = event
    sys.stdout.write(json.dumps(fields, default=str) + "\n")
    sys.stdout.flush()


class _Var:
    """Minimal stand-in for tk.StringVar / BooleanVar."""

    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, value):
        self._v = value


class _Root:
    """Runs Tk `after` callbacks immediately (the worker has no event loop)."""

    def after(self, _delay, fn=None, *args):
        if fn is not None:
            fn(*args)


_ALERT_LEVELS = {"showinfo": "info", "showwarning": "warning", "showerror": "error"}


class HeadlessHost:
    """Provides exactly the attributes the workflow methods read from the Tk window.
    Any attribute not provided here raises a clear error, so a future change to the
    Tk workflow methods that needs new UI state fails loudly instead of silently."""

    def __init__(self, job):
        theme = str(job.get("theme") or "superjoy").lower().replace("-", "_")
        if theme not in engine.THEMES:
            theme = "superjoy"
        engine.set_theme(theme)
        self.theme_name = theme
        self.theme_cfg = engine.THEMES[theme]
        self.root = _Root()
        self.output_dir = _Var(job.get("output_dir") or "")
        self.auto_transcode_var = _Var(bool(job.get("auto_transcode", True)))
        self.tsv_path = _Var(job.get("spreadsheet") or job.get("csv") or "")
        self.marry_csv_path = _Var(job.get("csv") or "")
        self.f_workspace = _Var(job.get("workspace") or "")
        self.aspect_var = _Var(job.get("aspect") or engine.DEFAULT_ASPECT)
        self.videos_dir = _Var(job.get("videos_dir") or "")
        self.marry_slates_dir = _Var(job.get("slates_dir") or "")
        self.latest_previews = []
        self.alerts = []
        fps = job.get("fps")
        fps = engine.parse_fps(str(fps)) if fps not in (None, "") else engine.DEFAULT_FPS
        if fps is None:
            raise ValueError("Invalid frame rate. Use a number between 1 and 120.")
        w, h = engine.ASPECT_RESOLUTIONS.get(self.aspect_var.get(), (1920, 1080))
        self.render_settings = {"fps": fps, "width": w, "height": h}

    # --- UI hooks used by the workflow methods ---
    def _alert(self, kind, title, message):
        level = _ALERT_LEVELS.get(kind, "info")
        self.alerts.append({"level": level, "title": title, "message": message})
        emit("alert", level=level, title=title, message=message)

    def reset_ui(self):
        pass

    def open_preview_viewer(self):
        emit("previews", items=self.latest_previews)

    # --- pure generators (no UI state) ---
    write_jsx = _W.write_jsx
    write_marry_jsx = _W.write_marry_jsx
    write_unslate_jsx = _W.write_unslate_jsx
    _scan_marry_pairs = _W._scan_marry_pairs

    def __getattr__(self, name):
        raise AttributeError(
            f"HeadlessHost has no '{name}': the Tk workflow now needs UI state the worker "
            f"does not provide. Add it to HeadlessHost in slate_worker.py."
        )


def _install_dry_run():
    """Replace the Adobe-facing calls with ones that keep the generated JSX on disk."""
    written = []

    def fake_execute(jsx_path, timeout=3600):
        dst = os.path.splitext(jsx_path)[0] + ".dryrun.jsx"
        shutil.copyfile(jsx_path, dst)
        written.append(dst)
        emit("log", message=f"[dry-run] JSX written to {dst}")

    engine.execute_ae_script_file = fake_execute
    engine.ensure_ame_running = lambda *a, **k: True
    engine.verify_jsx_status = lambda *a, **k: {"ok": "1", "dry_run": "1"}
    return written


def _require_dir(path, label):
    p = engine.resolve_path_input(path or "")
    if not p or not os.path.isdir(p):
        raise ValueError(f"{label} folder not found: {path!r}")
    return p


def cmd_run(job):
    mode = job.get("mode")
    dry = bool(job.get("dry_run"))
    written = _install_dry_run() if dry else []
    host = HeadlessHost(job)

    if mode == "unslate":
        folder = _require_dir(job.get("unslate_dir"), "Un-slate")
        _W.process_unslate(host, folder, host.render_settings)
    elif mode == "marry":
        sdir = _require_dir(job.get("slates_dir"), "Existing Slates")
        vdir = _require_dir(job.get("videos_dir"), "Master Videos")
        host.marry_slates_dir.set(sdir)
        host.videos_dir.set(vdir)
        pairs = host._scan_marry_pairs()
        if not pairs:
            raise ValueError("No matching Ad-ID pairs found between Existing Slates and Master Videos.")
        _W.process_marry(host, pairs, sdir, vdir, host.render_settings)
    elif mode == "batch":
        template = engine.resolve_path_input(job.get("template") or "") or engine.DEFAULT_TEMPLATE_AEP
        slates_only = bool(job.get("slates_only"))
        videos_dir = engine.resolve_path_input(job.get("videos_dir") or "")
        if not slates_only and (not videos_dir or not os.path.isdir(videos_dir)):
            raise ValueError("Master Videos folder is required unless slates_only is true.")
        if slates_only and not job.get("output_dir") and not job.get("spreadsheet"):
            # The Tk app would fall back to the template's folder, which here is inside the app bundle.
            raise ValueError("Choose an Output Folder for standalone slates.")
        if job.get("rows"):
            rows = [engine.normalize_slate_row(r) for r in job["rows"]]
        elif job.get("spreadsheet"):
            rows = engine.parse_metadata_file(engine.resolve_path_input(job["spreadsheet"]))
        else:
            raise ValueError("Batch job needs 'rows' or 'spreadsheet'.")
        if not rows:
            raise ValueError("No valid slate rows to process.")
        _W.process_batch(host, rows, template, videos_dir, slates_only)
    else:
        raise ValueError(f"Unknown mode {mode!r} (expected batch, marry or unslate).")

    # Every successful workflow ends with exactly one "info" alert; errors/"nothing to do" warnings do not.
    ok = any(a["level"] == "info" for a in host.alerts) and not any(a["level"] == "error" for a in host.alerts)
    return {"ok": ok, "mode": mode, "dry_run": dry, "jsx": written, "alerts": host.alerts,
            "previews": host.latest_previews}


def cmd_scan_videos(videos_dir, aspects, shared_json):
    """Mirror of SuperJoyWorkstation.populate_batch_from_videos without the Tk tree."""
    vdir = _require_dir(videos_dir, "Master Videos")
    given = json.loads(shared_json) if shared_json else {}
    sl = engine.sanitize_single_line
    shared = {
        "agency": sl(given.get("agency", "")),
        "client": sl(given.get("client", "")),
        "date": _W._underscored(given.get("date", "")) or engine.today_yyyy_mm_dd(),
        "workspace": sl(given.get("workspace", "")),
        "audio": sl(given.get("audio", "")) or "STEREO",
        "copyright": sl(given.get("copyright", "")),
        "flame": "y" if given.get("flame") else "n",
        "nfa": "NFA" if given.get("nfa") else "",
    }
    pill_aspects = [a for a in (aspects or "").split(",") if a in engine.ASPECT_RESOLUTIONS] or [engine.DEFAULT_ASPECT]
    rows = []
    for vf in sorted(os.listdir(vdir)):
        if not vf.lower().endswith(engine.VALID_EXTS) or vf.startswith("."):
            continue
        ad_id, title, trt = engine.parse_video_filename(vf)
        targets = pill_aspects if len(pill_aspects) > 1 else [engine.detect_aspect_from_text(vf) or pill_aspects[0]]
        for asp in targets:
            rows.append(_W._make_slate_entry(shared, ad_id, title, trt, asp))
    return {"ok": True, "rows": rows}


def cmd_info():
    return {
        "ok": True,
        "themes": {k: {kk: vv for kk, vv in v.items() if isinstance(vv, str)} for k, v in engine.THEMES.items()},
        "aspects": {k: list(v) for k, v in engine.ASPECT_RESOLUTIONS.items()},
        "aspect_keys": list(engine.ASPECT_KEYS),
        "fps_presets": engine.FPS_PRESETS,
        "default_fps_label": engine.DEFAULT_FPS_LABEL,
        "default_template": engine.DEFAULT_TEMPLATE_AEP,
        "default_spreadsheet": engine.DEFAULT_SPREADSHEET_XLSX,
        "standard_trts": list(engine.STANDARD_TRTS),
        "engine_dir": engine._APP_DIR,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Headless SlateWorkstation worker (JSON-lines on stdout).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse"); p.add_argument("--file", required=True)
    p = sub.add_parser("scan-videos"); p.add_argument("--videos", required=True)
    p.add_argument("--aspects", default="", help="comma list, e.g. 16x9,9x16")
    p.add_argument("--shared", default="", help="JSON campaign fields: agency, client, date, workspace, audio, copyright, flame, nfa")
    p = sub.add_parser("scan-marry")
    p.add_argument("--slates", required=True); p.add_argument("--videos", required=True); p.add_argument("--csv", default="")
    p = sub.add_parser("run"); p.add_argument("--job", required=True, help="path to job JSON, or - for stdin")
    sub.add_parser("info")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "parse":
            res = {"ok": True, "rows": engine.parse_metadata_file(engine.resolve_path_input(args.file))}
        elif args.cmd == "scan-videos":
            res = cmd_scan_videos(args.videos, args.aspects, args.shared)
        elif args.cmd == "scan-marry":
            host = HeadlessHost({"slates_dir": args.slates, "videos_dir": args.videos, "csv": args.csv})
            res = {"ok": True, "pairs": host._scan_marry_pairs()}
        elif args.cmd == "run":
            raw = sys.stdin.read() if args.job == "-" else open(args.job, encoding="utf-8").read()
            res = cmd_run(json.loads(raw))
        else:
            res = cmd_info()
    except Exception as e:  # report every failure through the protocol
        emit("result", ok=False, error=f"{type(e).__name__}: {e}")
        return 1
    emit("result", **res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
