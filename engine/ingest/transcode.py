"""ffmpeg transcodes for editing and web, with a watchdog so one bad clip can't hang a job.

EDIT: ProRes 422 Proxy, 1920x1080 (fit + pad, never stretched), all audio as 24-bit PCM, .mov
WEB:  H.264, 4 Mbps target / 5 Mbps max, 1920x1080, AAC stereo, .mp4 (+faststart)
Both keep the OCF clip name, start timecode and reel name so they relink to the originals.
Hardware VideoToolbox encoders are used when present, with software fallbacks.
"""
import os
import subprocess
import threading
import time

from . import safefs, tools

PRESETS = {
    "edit": {"label": "ProRes 422 Proxy · 1920×1080", "folder": "EDIT", "ext": ".mov"},
    "web": {"label": "H.264 · 4–5 Mbps · 1920×1080", "folder": "WEB", "ext": ".mp4"},
}
FIT_1080 = ("scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
FONT_CANDIDATES = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
                   "/Library/Fonts/Arial.ttf"]

_caps_cache = {}


def capabilities(ffmpeg=None):
    ffmpeg = ffmpeg or tools.ffmpeg_path()
    if not ffmpeg:
        return {"ffmpeg": None, "encoders": [], "filters": []}
    if ffmpeg in _caps_cache:
        return _caps_cache[ffmpeg]

    def names(flag):
        try:
            out = subprocess.run([ffmpeg, "-hide_banner", flag], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        found = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and 2 <= len(parts[0]) <= 6 and set(parts[0]) <= set("VASDFXBTCN.|"):
                found.append(parts[1])
        return found

    caps = {"ffmpeg": ffmpeg, "encoders": names("-encoders"), "filters": names("-filters")}
    try:
        caps["version"] = subprocess.run([ffmpeg, "-hide_banner", "-version"], capture_output=True,
                                         text=True, timeout=10).stdout.splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        caps["version"] = None
    _caps_cache[ffmpeg] = caps
    return caps


def _esc_filter_path(p):
    # inside a single-quoted filter option: escape backslash and single quote
    return p.replace("\\", "\\\\").replace("'", "'\\''")


def _esc_text(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def encoder_chain(preset, caps):
    enc = caps.get("encoders", [])
    if preset == "edit":
        chain = [e for e in ("prores_videotoolbox", "prores_ks") if e in enc]
    else:
        chain = [e for e in ("h264_videotoolbox", "libx264") if e in enc]
    return chain


def build_command(ffmpeg, src, out_path, preset, encoder, info, roll_name, lut=None,
                  burn_in=False, caps=None):
    caps = caps or {}
    vf = []
    if lut:
        vf.append(f"lut3d=file='{_esc_filter_path(lut)}':interp=tetrahedral")
    vf.append(FIT_1080)
    if burn_in and "drawtext" in caps.get("filters", []):
        font = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
        if font:
            name = _esc_text(os.path.splitext(os.path.basename(src))[0])
            base = (f"fontfile='{_esc_filter_path(font)}':fontsize=30:fontcolor=white:"
                    f"box=1:boxcolor=black@0.55:boxborderw=8")
            vf.append(f"drawtext={base}:text='{name}':x=24:y=h-th-24")
            tc, fps = info.get("timecode"), info.get("fps")
            if tc and fps:
                vf.append(f"drawtext={base}:timecode='{_esc_text(tc)}':rate={fps}:x=w-tw-24:y=h-th-24")
    if encoder == "prores_ks":
        vf.append("format=yuv422p10le")
    if preset == "web":
        vf.append("format=yuv420p")

    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-nostats", "-progress", "pipe:1",
           "-i", src, "-map", "0:v:0"]
    cmd += ["-map", "0:a?"] if preset == "edit" else ["-map", "0:a:0?"]
    cmd += ["-vf", ",".join(vf)]
    if preset == "edit":
        if encoder == "prores_videotoolbox":
            cmd += ["-c:v", "prores_videotoolbox", "-profile:v", "proxy"]
        else:
            cmd += ["-c:v", "prores_ks", "-profile:v", "0", "-vendor", "apl0"]
        cmd += ["-c:a", "pcm_s24le"]
    else:
        if encoder == "h264_videotoolbox":
            cmd += ["-c:v", "h264_videotoolbox", "-profile:v", "high"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "medium", "-profile:v", "high"]
        cmd += ["-b:v", "4M", "-maxrate", "5M", "-bufsize", "10M",
                "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000", "-movflags", "+faststart"]
    if lut:
        cmd += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    if info.get("timecode"):
        cmd += ["-timecode", info["timecode"]]
    if roll_name:
        cmd += ["-metadata", f"reel_name={roll_name}", "-metadata:s:v:0", f"reel_name={roll_name}"]
    cmd += ["-metadata", "comment=Transcoded by MSTR-SL8R Ingest", "-n", out_path]
    return cmd


def run_watched(cmd, duration=None, stall_timeout=90, rss_cap_mb=6144, stop=None,
                on_progress=None, active=None, low_priority=True):
    """Run ffmpeg (or anything emitting -progress lines). Kill it if it stalls, blows past
    a memory cap, runs absurdly long, or the job is stopped. Returns (ok, reason, stderr_tail)."""
    if low_priority and os.path.exists("/usr/bin/nice"):
        cmd = ["/usr/bin/nice", "-n", "10"] + cmd
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
    if active is not None:
        active.add(p)
    state = {"last": time.monotonic(), "out_us": 0, "end": False}
    err_tail = []

    def read_out():
        for raw in p.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    v = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if v > state["out_us"]:
                    state["out_us"], state["last"] = v, time.monotonic()
                    if on_progress and duration:
                        on_progress(min(1.0, v / 1e6 / duration))
            elif line == "progress=end":
                state["end"] = True
                state["last"] = time.monotonic()

    def read_err():
        for raw in p.stderr:
            err_tail.append(raw.decode("utf-8", "replace").rstrip())
            del err_tail[:-20]

    threads = [threading.Thread(target=read_out, daemon=True), threading.Thread(target=read_err, daemon=True)]
    for t in threads:
        t.start()
    started = time.monotonic()
    wall_cap = max(900.0, (duration or 0) * 20)
    reason = None
    last_rss_check = 0.0
    try:
        while p.poll() is None:
            time.sleep(0.5)
            now = time.monotonic()
            if stop is not None and stop.is_set():
                reason = "stopped"
            elif now - state["last"] > stall_timeout:
                reason = f"stalled (no progress for {stall_timeout}s)"
            elif now - started > wall_cap:
                reason = f"took longer than {int(wall_cap)}s"
            elif now - last_rss_check > 5:
                last_rss_check = now
                rss = _rss_mb(p.pid)
                if rss and rss > rss_cap_mb:
                    reason = f"memory over {rss_cap_mb} MB"
            if reason:
                _kill(p)
                break
        p.wait()
        for t in threads:
            t.join(timeout=5)
    finally:
        if active is not None:
            active.discard(p)
        for stream in (p.stdout, p.stderr):
            try:
                stream.close()
            except OSError:
                pass
    if reason:
        return False, reason, err_tail
    if p.returncode != 0:
        return False, f"exit code {p.returncode}", err_tail
    return True, None, err_tail


def _rss_mb(pid):
    try:
        out = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip() or 0) / 1024
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _kill(p):
    try:
        p.terminate()
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
    except OSError:
        pass


def check_output(path, expect_duration=None):
    """ffprobe the finished file: video present, 1920x1080, duration sane."""
    info = tools.probe(path, timeout=30)
    if info.get("probe_error"):
        return False, info["probe_error"]
    if (info.get("width"), info.get("height")) != (1920, 1080):
        return False, f"unexpected size {info.get('width')}x{info.get('height')}"
    if expect_duration and info.get("duration") and abs(info["duration"] - expect_duration) > max(1.0, expect_duration * 0.02):
        return False, f"duration {info['duration']}s vs source {expect_duration}s"
    return True, None


def transcode_clip(src, final_path, preset, info, roll_name, sources, lut=None, burn_in=False,
                   stop=None, active=None, low_priority=True, stall_timeout=90, on_progress=None):
    """Make one output. Never overwrites: an existing final file counts as done."""
    if os.path.lexists(final_path):
        return {"status": "exists", "path": final_path}
    caps = capabilities()
    if not caps["ffmpeg"]:
        return {"status": "failed", "path": final_path, "error": "ffmpeg not found"}
    chain = encoder_chain(preset, caps)
    if not chain:
        return {"status": "failed", "path": final_path, "error": f"no encoder for {preset}"}
    safefs.ensure_dir(os.path.dirname(final_path), sources)
    part = safefs.partial_path(final_path)
    errors = []
    for encoder in chain:
        if os.path.lexists(part):
            safefs.discard_partial(part, sources)
        safefs.assert_outside_sources(part, sources)
        cmd = build_command(caps["ffmpeg"], src, part, preset, encoder, info, roll_name, lut, burn_in, caps)
        ok, reason, tail = run_watched(cmd, info.get("duration"), stall_timeout=stall_timeout, stop=stop,
                                       on_progress=on_progress, active=active, low_priority=low_priority)
        if ok:
            good, why = check_output(part, info.get("duration"))
            if good:
                safefs.finalize(part, final_path, sources)
                return {"status": "made", "path": final_path, "encoder": encoder}
            reason = f"output check failed: {why}"
        if os.path.lexists(part):
            safefs.discard_partial(part, sources)
        errors.append(f"{encoder}: {reason}" + (f" — {tail[-1]}" if tail else ""))
        if reason == "stopped":
            return {"status": "stopped", "path": final_path}
    return {"status": "failed", "path": final_path, "error": "; ".join(errors)[:600]}
