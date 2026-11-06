"""Verified copy of camera originals (OCF) into <dest>/OCF/<date>/<cam>-Cam/<roll>/.

Per file: read the source once (uncached), hashing as it streams into an exclusive
in-progress file on every destination; fsync; re-read each destination from disk
(uncached) and compare; only then publish it under its final name (no-overwrite).
An existing final file is never replaced: same hash = already done, different = conflict.
"""
import os
import re

from . import hashing, safefs

CHUNK = 8 * 1024 * 1024


def safe_name(s, fallback="X"):
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", (s or "").strip())
    return s.strip("._") or fallback


def roll_dir(dest_root, roll, kind="OCF"):
    return os.path.join(dest_root, kind, safe_name(roll.get("date"), "undated"),
                        f"{safe_name(roll.get('cam'), 'X')}-Cam", safe_name(roll.get("roll"), "ROLL"))


def hash_file(path, algo, stop=None):
    h = hashing.new(algo)
    with safefs.open_source_nocache(path) as f:
        while True:
            if stop is not None and stop.is_set():
                raise InterruptedError("stopped")
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _walk(top, skip_dirs):
    for d, dirs, files in os.walk(top, followlinks=False):
        dirs[:] = sorted(x for x in dirs if x not in safefs.JUNK_NAMES and not x.startswith("._")
                         and safefs.real(os.path.join(d, x)) not in skip_dirs)
        for n in sorted(files):
            p = os.path.join(d, n)
            if n in safefs.JUNK_NAMES or n.startswith("._") or os.path.islink(p):
                continue
            yield p


def roll_files(roll, other_roots=()):
    """[(source_path, relative_destination_path)] for everything that belongs to a roll,
    keeping the card structure. Other rolls nested under this root are left out."""
    root = safefs.real(roll["root"])
    skip = {safefs.real(r) for r in other_roots if safefs.real(r) != root}
    kind = roll.get("kind")
    out = []
    if kind == "red" and root.lower().endswith(".rdm"):
        base = os.path.basename(root)
        out = [(p, os.path.join(base, os.path.relpath(p, root))) for p in _walk(root, skip)]
    elif kind == "red":  # loose .RDC folders sitting in a plain folder
        for rdc in sorted({os.path.dirname(c["paths"][0]) for c in roll["clips"]}):
            base = os.path.basename(rdc)
            out += [(p, os.path.join(base, os.path.relpath(p, rdc))) for p in _walk(rdc, skip)]
    elif kind in ("sony_xavc", "sony_xdcam"):
        out = [(p, os.path.relpath(p, root)) for p in _walk(root, skip)]
    else:  # generic: files directly in the folder (sub-folders are their own rolls)
        try:
            names = sorted(os.listdir(root))
        except OSError:
            names = []
        for n in names:
            p = os.path.join(root, n)
            if (n in safefs.JUNK_NAMES or n.startswith("._") or os.path.islink(p)
                    or not os.path.isfile(p)):
                continue
            out.append((p, n))
    return out


def copy_file(src, rel, dest_roll_dirs, algo, sources, stop=None, retries=1):
    """Copy one file to every destination roll folder. Returns a result dict."""
    st = os.stat(src)
    res = {"src": src, "rel": rel, "size": st.st_size, "mtime": st.st_mtime, "algo": algo,
           "hash": None, "dests": {}, "status": None, "error": None}
    finals = {d: os.path.join(d, rel) for d in dest_roll_dirs}
    todo = [d for d, f in finals.items() if not os.path.lexists(f)]
    existing = [d for d in finals if d not in todo]

    attempt = 0
    while todo:
        attempt += 1
        handles = []
        try:
            for d in todo:
                part = safefs.partial_path(finals[d])
                if os.path.lexists(part):  # stale from an interrupted run
                    safefs.discard_partial(part, sources)
                handles.append((d,) + safefs.open_partial(finals[d], sources))
            h = hashing.new(algo)
            copied = 0
            with safefs.open_source_nocache(src) as f:
                while True:
                    if stop is not None and stop.is_set():
                        raise InterruptedError("stopped")
                    b = f.read(CHUNK)
                    if not b:
                        break
                    h.update(b)
                    for _, _, out in handles:
                        out.write(b)
                    copied += len(b)
            for _, _, out in handles:
                os.fsync(out.fileno())
                out.close()
            res["hash"] = h.hexdigest()
            if copied != st.st_size:
                raise IOError(f"source size changed during copy ({copied} of {st.st_size} bytes)")
        except BaseException as e:
            for _, part, out in handles:
                try:
                    out.close()
                finally:
                    safefs.discard_partial(part, sources)
            if isinstance(e, InterruptedError):
                res.update(status="stopped", error="stopped")
                return res
            if attempt > retries:
                res.update(status="failed", error=f"copy failed: {e}")
                for d in todo:
                    res["dests"][d] = "failed"
                return res
            continue

        retry = []
        for d, part, _ in handles:
            got = hash_file(part, algo, stop)
            if got == res["hash"]:
                safefs.finalize(part, finals[d], sources)
                safefs.set_times(finals[d], st.st_atime, st.st_mtime, sources)
                res["dests"][d] = "copied"
            else:
                safefs.discard_partial(part, sources)
                retry.append(d)
        todo = retry if attempt <= retries else []
        for d in retry:
            if attempt > retries:
                res["dests"][d] = "verify_failed"

    for d in existing:
        if res["hash"] is None:
            res["hash"] = hash_file(src, algo, stop)
        same = os.path.getsize(finals[d]) == st.st_size and hash_file(finals[d], algo, stop) == res["hash"]
        res["dests"][d] = "verified_existing" if same else "conflict"

    states = set(res["dests"].values())
    if "conflict" in states:
        res["status"] = "conflict"
        res["error"] = "a different file already exists at the destination; it was left untouched"
    elif states & {"failed", "verify_failed"}:
        res["status"] = "failed"
        res["error"] = res["error"] or "read-back verification failed"
    elif states == {"verified_existing"}:
        res["status"] = "verified_existing"
    else:
        res["status"] = "copied"
    return res
