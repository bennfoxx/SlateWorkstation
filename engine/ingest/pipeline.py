"""Ingest job: preflight plan, then copy → verify → MHL → transcode → reports.

JOB (JSON):
  sources        scan sources (never written to)
  rolls          rolls from `scan`, with the user's Cam / Roll edits
  mode           "transcode" (originals stay put) | "offload" | "offload_transcode"
  destinations   [project_root, optional_backup_root, ...]; transcodes + reports go to the first
  outputs        ["edit", "web"]   (see transcode.PRESETS)
  luts           cascade, see luts.py;  lut_library: folder of .cube/.cdl
  burn_in        bool (needs an ffmpeg with drawtext)
  copy_workers   default 1 (one stream per source device is fastest and safest)
  transcode_workers default 2;  low_priority default true
  hash           "xxh64" | "md5" | "sha1" (default: xxh64 when available, else md5)
  camera_reports bool: also write camera reports into REPORTS/

Stages run with bounded pools: a roll's transcodes start as soon as that roll is verified,
while the next roll copies. Results are journaled to <project>/.ingest/journal.sqlite.
"""
import csv
import datetime as dt
import io
import json
import os
import socket
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from . import camreport, hashing, luts, mhl, offload, rawbackends, safefs, tools, transcode

MODES = ("transcode", "offload", "offload_transcode")


def _norm(job):
    j = dict(job)
    j["mode"] = j.get("mode") or "offload_transcode"
    if j["mode"] not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    j["sources"] = [safefs.real(s) for s in j.get("sources") or []]
    j["destinations"] = [safefs.real(d) for d in j.get("destinations") or [] if d]
    j["outputs"] = [o for o in (j.get("outputs") or []) if o in transcode.PRESETS]
    if j["mode"] == "offload":
        j["outputs"] = []
    j["hash"] = j.get("hash") or hashing.DEFAULT
    j["copy_workers"] = max(1, int(j.get("copy_workers") or 1))
    j["transcode_workers"] = max(1, int(j.get("transcode_workers") or 2))
    j["low_priority"] = j.get("low_priority", True)
    return j


def _offloading(j):
    return j["mode"] in ("offload", "offload_transcode")


# ---------------------------------------------------------------- plan

def plan(job):
    """Read-only preflight. Returns {"ok", "errors", "warnings", "rolls": [...], totals}."""
    j = _norm(job)
    errors, warnings = [], []
    if not j["sources"]:
        errors.append("No sources in the job.")
    if not j["destinations"]:
        errors.append("Choose a project folder (destination).")
    if not j.get("rolls"):
        errors.append("No rolls to process.")
    if j["mode"] != "offload" and not j["outputs"]:
        errors.append("Choose at least one transcode output (EDIT or WEB).")
    for d in j["destinations"]:
        for s in j["sources"]:
            if safefs.is_within(d, s):
                errors.append(f"Destination {d} is inside the source {s}.")
            if safefs.is_within(s, d):
                errors.append(f"Source {s} is inside the destination {d}; pick a separate project folder.")
    if len(set(j["destinations"])) != len(j["destinations"]):
        errors.append("The same destination is listed twice.")
    if j["hash"] not in hashing.AVAILABLE:
        errors.append(f"Hash {j['hash']} is not available here (have {', '.join(hashing.AVAILABLE)}).")

    caps = transcode.capabilities() if j["outputs"] else {}
    if j["outputs"] and not caps.get("ffmpeg"):
        errors.append("ffmpeg not found; transcodes are not possible.")
    for o in j["outputs"]:
        if caps.get("ffmpeg") and not transcode.encoder_chain(o, caps):
            errors.append(f"ffmpeg has no encoder for {o.upper()}.")
    if j.get("burn_in") and caps.get("ffmpeg") and "drawtext" not in caps.get("filters", []):
        warnings.append("This ffmpeg has no drawtext filter; burn-ins will be skipped.")

    all_roots = [r["root"] for r in j.get("rolls") or []]
    rolls_out, need = [], {d: 0 for d in j["destinations"]}
    seen_dirs = {}
    files_total = bytes_total = 0
    raw_clips = 0
    for r in j.get("rolls") or []:
        key = (r.get("date"), r.get("cam"), r.get("roll"))
        if key in seen_dirs:
            errors.append(f"Two rolls would both become {r.get('cam')}-Cam/{r.get('roll')} on {r.get('date')}: "
                          f"{seen_dirs[key]} and {r['root']}. Rename one.")
        seen_dirs[key] = r["root"]
        entry = {"id": r.get("id"), "roll": r.get("roll"), "cam": r.get("cam"), "date": r.get("date"),
                 "clips": len(r.get("clips") or [])}
        if _offloading(j):
            files = offload.roll_files(r, all_roots)
            size = sum(os.path.getsize(p) for p, _ in files if os.path.exists(p))
            entry.update(files=len(files), bytes=size)
            files_total += len(files)
            bytes_total += size
            lower = {}
            for _, rel in files:
                lower.setdefault(rel.lower(), []).append(rel)
            dupes = [v for v in lower.values() if len(v) > 1]
            for d in j["destinations"]:
                ocf = offload.roll_dir(d, r)
                present = [rel for _, rel in files if os.path.lexists(os.path.join(ocf, rel))]
                need[d] += sum(os.path.getsize(p) for p, rel in files
                               if not os.path.lexists(os.path.join(ocf, rel)) and os.path.exists(p))
                if present:
                    entry.setdefault("already_at", {})[d] = len(present)
                ft = safefs.fs_type(d)
                if ft == "msdos" and any(os.path.getsize(p) >= 4 * 1024 ** 3 for p, _ in files):
                    errors.append(f"{d} is FAT32 and roll {r.get('roll')} has files over 4 GB.")
                if dupes and ft in ("msdos", "exfat", "smbfs"):
                    warnings.append(f"Roll {r.get('roll')}: names that differ only in case may collide on {ft}.")
        if j["outputs"]:
            n_raw = sum(1 for c in r.get("clips") or [] if not rawbackends.ffmpeg_can_decode(c))
            raw_clips += n_raw
            entry["raw_clips"] = n_raw
            lut_desc = {}
            for o in j["outputs"]:
                descs = set()
                for c in r.get("clips") or []:
                    a = luts.assignment(j.get("luts"), r, c, o)
                    if isinstance(a, dict):
                        a = f"CDL+{a.get('lut') or 'none'}"
                    if a == "auto":
                        s = luts.suggest((c.get("info") or {}).get("gamma"), j.get("lut_library"))
                        a = f"auto → {os.path.basename(s) if s else 'none found'}"
                    descs.add(os.path.basename(a) if isinstance(a, str) and os.sep in a else (a or "none"))
                lut_desc[o] = sorted(descs)
            entry["luts"] = lut_desc
        rolls_out.append(entry)

    if _offloading(j):
        for d, n in need.items():
            free = safefs.free_bytes(d)
            if n * 1.02 + 2 * 1024 ** 3 > free:
                errors.append(f"Not enough space on {d}: need {n / 1e9:.1f} GB (+ margin), have {free / 1e9:.1f} GB.")
    for d in j["destinations"]:
        probe_dir = d
        while not os.path.exists(probe_dir):
            probe_dir = os.path.dirname(probe_dir) or "/"
        if not os.access(probe_dir, os.W_OK):
            errors.append(f"Can't write to {d}.")
    if raw_clips:
        warnings.append(f"{raw_clips} RAW clip(s) (e.g. R3D) can't be transcoded by ffmpeg; "
                        f"{rawbackends.status_text()}")
    if j["mode"] == "transcode":
        warnings.append("Transcode-only: transcodes are made straight from the source media, "
                        "which is only read.")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "mode": j["mode"],
            "outputs": j["outputs"], "hash": j["hash"], "rolls": rolls_out,
            "files": files_total, "bytes": bytes_total, "raw_clips": raw_clips,
            "ffmpeg": caps.get("version") if caps else None}


# ---------------------------------------------------------------- journal

class Journal:
    def __init__(self, project_root, sources):
        d = safefs.ensure_dir(os.path.join(project_root, ".ingest"), sources)
        self.path = os.path.join(d, "journal.sqlite")
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            job TEXT, ts TEXT, roll TEXT, stage TEXT, item TEXT, status TEXT, detail TEXT, hash TEXT)""")
        self.db.commit()

    def add(self, job, roll, stage, item, status, detail=None, hsh=None):
        with self.lock:
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
                            (job, dt.datetime.now().isoformat(timespec="seconds"), roll, stage, item,
                             status, detail, hsh))
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()


# ---------------------------------------------------------------- run

class Runner:
    def __init__(self, job, emit=None, stop=None):
        self.j = _norm(job)
        self.emit = emit or (lambda *a, **k: None)
        self.stop = stop or threading.Event()
        self.active = set()  # running ffmpeg processes, for Stop
        self.lock = threading.Lock()
        self.counts = {"copy_done": 0, "copy_total": 0, "tc_done": 0, "tc_total": 0}
        self.files, self.transcodes, self.rolls_summary = [], [], []
        self.job_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    def log(self, msg):
        self.emit("log", message=msg)

    def progress(self, stage):
        c = self.counts
        if stage == "copy":
            self.emit("progress", stage="copy", done=c["copy_done"], total=c["copy_total"])
        else:
            self.emit("progress", stage="transcode", done=c["tc_done"], total=c["tc_total"])

    def stop_now(self):
        self.stop.set()
        for p in list(self.active):
            try:
                p.terminate()
            except OSError:
                pass

    def run(self):
        pre = plan(self.j)
        if not pre["ok"]:
            return {"ok": False, "error": "Preflight failed:\n" + "\n".join(pre["errors"]), "plan": pre}
        j = self.j
        project = j["destinations"][0]
        sources = j["sources"]
        safefs.ensure_dir(project, sources)
        journal = Journal(project, sources)
        bake_dir = os.path.join(project, ".ingest", "luts")
        all_roots = [r["root"] for r in j["rolls"]]
        offloading = _offloading(j)
        self.log(f"Job {self.job_id}: mode {j['mode']}, {len(j['rolls'])} roll(s), outputs "
                 f"{', '.join(o.upper() for o in j['outputs']) or 'none'}, hash {j['hash']}")
        for w in pre["warnings"]:
            self.log("⚠︎ " + w)

        roll_files = {r["id"]: offload.roll_files(r, all_roots) for r in j["rolls"]} if offloading else {}
        self.counts["copy_total"] = sum(len(v) for v in roll_files.values())
        self.counts["tc_total"] = sum(len(r.get("clips") or []) for r in j["rolls"]) * len(j["outputs"])

        tc_pool = ThreadPoolExecutor(max_workers=j["transcode_workers"]) if j["outputs"] else None
        tc_futures = []
        try:
            for r in j["rolls"]:
                if self.stop.is_set():
                    break
                summary = {"roll": r.get("roll"), "cam": r.get("cam"), "date": r.get("date"), "root": r["root"]}
                ok_paths = None
                if offloading:
                    ok_paths, summary["offload"] = self._offload_roll(r, roll_files[r["id"]], journal, sources)
                self.rolls_summary.append(summary)
                if tc_pool and not self.stop.is_set():
                    transcode_sources = sources + ([os.path.join(d, "OCF") for d in j["destinations"]]
                                                   if offloading else [])
                    for c in r.get("clips") or []:
                        src = c["paths"][0]
                        if offloading:
                            src = ok_paths.get(src)
                            if not src:  # this clip's original didn't verify: don't transcode it
                                for o in j["outputs"]:
                                    self._tc_result(r, c, o, {"status": "skipped",
                                                              "error": "original not verified"}, journal)
                                continue
                        for o in j["outputs"]:
                            tc_futures.append(tc_pool.submit(self._transcode_one, r, c, o, src, project,
                                                             transcode_sources, bake_dir, journal))
            for f in tc_futures:
                f.result()
        finally:
            if tc_pool:
                tc_pool.shutdown(wait=True, cancel_futures=True)

        reports = None
        if j.get("camera_reports") and not self.stop.is_set():
            try:
                reports = camreport.generate(j["rolls"], os.path.join(project, "REPORTS", "camera_reports"),
                                             sources + [os.path.join(project, "OCF")],
                                             on_progress=lambda d, t: self.emit("progress", stage="thumbs", done=d, total=t))
            except Exception as e:  # reports must never fail the ingest
                self.log(f"⚠︎ camera reports failed: {e}")
        summary = self._write_report(project, sources)
        journal.close()
        summary["camera_reports"] = reports
        summary["stopped"] = self.stop.is_set()
        return summary

    # -- offload
    def _offload_roll(self, r, files, journal, sources):
        j = self.j
        dest_dirs = [offload.roll_dir(d, r) for d in j["destinations"]]
        for d in dest_dirs:
            safefs.ensure_dir(d, sources)
        self.log(f"Copying {r.get('cam')}-Cam / {r.get('roll')}: {len(files)} file(s) → "
                 f"{len(dest_dirs)} destination(s)")
        results = []

        def one(item):
            src, rel = item
            res = offload.copy_file(src, rel, dest_dirs, j["hash"], sources, self.stop)
            with self.lock:
                self.counts["copy_done"] += 1
                self.files.append(res)
            journal.add(self.job_id, r.get("roll"), "copy", rel, res["status"], res.get("error"), res.get("hash"))
            if res["status"] not in ("copied", "verified_existing"):
                self.log(f"✗ {r.get('roll')}/{rel}: {res['status']} — {res.get('error')}")
            self.progress("copy")
            return res

        with ThreadPoolExecutor(max_workers=j["copy_workers"]) as ex:
            results = list(ex.map(one, files))

        good = [x for x in results if x["status"] in ("copied", "verified_existing")]
        mhls = []
        if good and not self.stop.is_set():
            entries = [{"rel": x["rel"], "size": x["size"], "mtime": x["mtime"], "algo": x["algo"], "hash": x["hash"]}
                       for x in good]
            for d in dest_dirs:
                try:
                    mhls.append(mhl.write_v2(d, entries, sources, roll_name=r.get("roll")))
                except Exception as e:
                    self.log(f"⚠︎ MHL for {d} failed: {e}")
        ok_paths = {}
        primary = dest_dirs[0]
        for x in good:
            ok_paths[x["src"]] = os.path.join(primary, x["rel"])
        status = {k: sum(1 for x in results if x["status"] == k) for k in
                  ("copied", "verified_existing", "conflict", "failed", "stopped")}
        status["all_verified"] = len(good) == len(results)
        status["mhl"] = mhls
        status["bytes"] = sum(x["size"] for x in good)
        self.log(f"{'✓' if status['all_verified'] else '✗'} {r.get('roll')}: {status['copied']} copied, "
                 f"{status['verified_existing']} already verified, {status['conflict']} conflict(s), "
                 f"{status['failed']} failed")
        return ok_paths, status

    # -- transcode
    def _transcode_one(self, r, c, output, src, project, sources, bake_dir, journal):
        if self.stop.is_set():
            return self._tc_result(r, c, output, {"status": "stopped"}, journal)
        if not rawbackends.ffmpeg_can_decode(c):
            res = rawbackends.transcode(c, output)
            return self._tc_result(r, c, output, res, journal)
        preset = transcode.PRESETS[output]
        out_dir = offload.roll_dir(project, r, kind=os.path.join("TRANSCODES", preset["folder"]))
        final = os.path.join(out_dir, offload.safe_name(c["name"], "clip") + preset["ext"])
        try:
            lut, lut_desc = luts.resolve(self.j.get("luts"), r, c, output, self.j.get("lut_library"),
                                         bake_dir, sources)
        except Exception as e:
            return self._tc_result(r, c, output, {"status": "failed", "path": final,
                                                  "error": f"LUT problem: {e}"}, journal)
        res = transcode.transcode_clip(src, final, output, c.get("info") or {}, r.get("roll"), sources,
                                       lut=lut, burn_in=self.j.get("burn_in"), stop=self.stop,
                                       active=self.active, low_priority=self.j["low_priority"])
        res["lut"] = lut_desc
        return self._tc_result(r, c, output, res, journal)

    def _tc_result(self, r, c, output, res, journal):
        res = dict(res, roll=r.get("roll"), clip=c["name"], output=output)
        with self.lock:
            self.counts["tc_done"] += 1
            self.transcodes.append(res)
        journal.add(self.job_id, r.get("roll"), f"transcode:{output}", c["name"], res["status"],
                    res.get("error") or res.get("lut"))
        if res["status"] in ("failed", "needs_raw_backend"):
            self.log(f"✗ {output.upper()} {c['name']}: {res.get('error')}")
        self.progress("transcode")
        return res

    # -- report
    def _write_report(self, project, sources):
        tc = {k: sum(1 for x in self.transcodes if x["status"] == k)
              for k in ("made", "exists", "failed", "skipped", "stopped", "needs_raw_backend")}
        cp = {k: sum(1 for x in self.files if x["status"] == k)
              for k in ("copied", "verified_existing", "conflict", "failed", "stopped")}
        summary = {"ok": True, "job": self.job_id, "mode": self.j["mode"], "host": socket.gethostname(),
                   "finished": dt.datetime.now().isoformat(timespec="seconds"),
                   "destinations": self.j["destinations"], "hash": self.j["hash"],
                   "copy": cp, "transcode": tc, "rolls": self.rolls_summary,
                   "problems": [x for x in self.files if x["status"] not in ("copied", "verified_existing")][:200]
                   + [x for x in self.transcodes if x["status"] in ("failed", "needs_raw_backend")][:200]}
        rep_dir = safefs.ensure_dir(os.path.join(project, "REPORTS", "ingest"), sources)
        base = os.path.join(rep_dir, f"ingest_{self.job_id}")
        safefs.write_new(base + ".json", json.dumps(dict(summary, files=self.files, transcodes=self.transcodes),
                                                    indent=1, default=str), sources)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Kind", "Roll", "Item", "Status", "Detail", "Hash / LUT", "Path"])
        for x in self.files:
            w.writerow(["copy", "", x["rel"], x["status"], x.get("error") or "", x.get("hash") or "", x["src"]])
        for x in self.transcodes:
            w.writerow([f"transcode:{x['output']}", x["roll"], x["clip"], x["status"], x.get("error") or "",
                        x.get("lut") or "", x.get("path") or ""])
        safefs.write_new(base + ".csv", buf.getvalue(), sources)
        summary["report"] = base + ".json"
        summary["ok"] = not cp["conflict"] and not cp["failed"] and not tc["failed"]
        return summary
