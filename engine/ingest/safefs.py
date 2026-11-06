"""The only place the ingest engine writes to disk.

Rules:
  * Writes only create NEW files (O_CREAT | O_EXCL); nothing is ever overwritten.
  * Every destination is checked to be outside every source root first.
  * There is no general delete / move / rename helper. The only exceptions act on
    this engine's own in-progress files (suffix PARTIAL) inside a destination, never on
    a source path, and are asserted as such.
"""
import os
import re
import subprocess

PARTIAL = ".ingest-partial"
F_NOCACHE = 48  # macOS fcntl: bypass the unified buffer cache (verify the disk, not RAM)

JUNK_NAMES = {".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems",
              ".DocumentRevisions-V100", "$RECYCLE.BIN", "System Volume Information",
              ".DS_Store", ".ingest"}


class UnsafeDestination(Exception):
    pass


def real(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def is_within(child, parent):
    child, parent = real(child), real(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def assert_outside_sources(dest, sources):
    for s in sources:
        if is_within(dest, s):
            raise UnsafeDestination(f"Refusing to write inside the source media: {dest} is inside {s}")


def open_source(path):
    """Open source media read-only (never anything else)."""
    return open(path, "rb")


def make_new_dir(path, sources):
    """Create `path`, or `path_v2`, `path_v3`… if it exists. Returns the created path."""
    assert_outside_sources(path, sources)
    candidate, n = path, 1
    while True:
        try:
            os.makedirs(candidate, exist_ok=False)
            return candidate
        except FileExistsError:
            n += 1
            candidate = f"{path}_v{n}"


def ensure_dir(path, sources):
    assert_outside_sources(path, sources)
    os.makedirs(path, exist_ok=True)
    return path


def write_new(path, data, sources):
    """Write bytes/str to a file that must not already exist."""
    assert_outside_sources(path, sources)
    if isinstance(data, str):
        data = data.encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return path


# ---------------------------------------------------------------- verified-copy helpers

def _nocache(fd):
    try:
        import fcntl
        fcntl.fcntl(fd, F_NOCACHE, 1)
    except (ImportError, OSError):
        pass


def open_source_nocache(path):
    """Read-only, uncached open (for copying and for read-back verification)."""
    fd = os.open(path, os.O_RDONLY)
    _nocache(fd)
    return os.fdopen(fd, "rb", buffering=0)


def partial_path(final_path):
    d, name = os.path.split(final_path)
    stem, ext = os.path.splitext(name)
    # keep the real extension last so tools (ffmpeg) still infer the container
    return os.path.join(d, f"{stem}{PARTIAL}{ext}")


def open_partial(final_path, sources):
    """Create the in-progress file for `final_path` (exclusively). Returns (path, file)."""
    p = partial_path(final_path)
    assert_outside_sources(p, sources)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    _nocache(fd)
    return p, os.fdopen(fd, "wb", buffering=0)


def _assert_own_partial(path, sources):
    assert_outside_sources(path, sources)
    if PARTIAL not in os.path.basename(path):
        raise UnsafeDestination(f"Not an ingest in-progress file: {path}")


def discard_partial(path, sources):
    """Remove one of OUR in-progress files (stale from a crash, or failed verification)."""
    _assert_own_partial(path, sources)
    if os.path.lexists(path):
        os.unlink(path)  # sanctioned: our own in-progress name only


def finalize(partial, final_path, sources):
    """Publish a verified partial under its final name WITHOUT ever overwriting:
    hard-link (fails if the final name exists), then drop the partial name."""
    _assert_own_partial(partial, sources)
    assert_outside_sources(final_path, sources)
    if os.path.lexists(final_path):
        raise FileExistsError(final_path)
    try:
        os.link(partial, final_path)  # sanctioned: atomic, fails if the name exists
        os.unlink(partial)  # sanctioned: our own in-progress name only
        return final_path
    except FileExistsError:
        raise
    except OSError:
        pass  # exFAT / SMB / NFS may not support hard links
    if _rename_excl(partial, final_path):
        return final_path
    if os.path.lexists(final_path):
        raise FileExistsError(final_path)
    os.rename(partial, final_path)  # sanctioned: last resort, checked just above
    return final_path


def _rename_excl(src, dst):
    """macOS rename with RENAME_EXCL: refuses to replace an existing name."""
    try:
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        rc = libc.renamex_np(os.fsencode(src), os.fsencode(dst), 0x00000004)  # sanctioned
    except (OSError, AttributeError):
        return False
    if rc == 0:
        return True
    if ctypes.get_errno() == 17:  # EEXIST
        raise FileExistsError(dst)
    return False


def set_times(path, atime, mtime, sources):
    assert_outside_sources(path, sources)
    os.utime(path, (atime, mtime), follow_symlinks=False)


def free_bytes(path):
    p = path
    while not os.path.exists(p):
        p = os.path.dirname(p) or "/"
    st = os.statvfs(p)
    return st.f_bavail * st.f_frsize


def fs_type(path):
    """Filesystem type of the volume holding `path` (apfs, hfs, exfat, msdos, smbfs, nfs…)."""
    p = real(path)
    while not os.path.exists(p):
        p = os.path.dirname(p) or "/"
    try:
        out = subprocess.run(["/sbin/mount"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    best, kind = "", None
    for line in out.splitlines():
        m = re.match(r"^.+? on (.+?) \((\w+)", line)
        if m and is_within(p, m.group(1)) and len(m.group(1)) > len(best):
            best, kind = m.group(1), m.group(2)
    return kind


def finalize_versioned(final_path, archive_path, sources):
    """Only for the ASC MHL chain file, which is regenerated per generation: keep the
    previous version under a numbered name (hard link, never overwriting), then free
    the canonical name for the new one. Refuses anything else."""
    assert_outside_sources(final_path, sources)
    if os.path.basename(final_path) != "ascmhl_chain.xml" or \
            os.path.basename(os.path.dirname(final_path)) != "ascmhl":
        raise UnsafeDestination(f"finalize_versioned only handles ascmhl_chain.xml: {final_path}")
    os.link(final_path, archive_path)  # sanctioned
    os.unlink(final_path)  # sanctioned: MHL chain file only, previous version kept above
