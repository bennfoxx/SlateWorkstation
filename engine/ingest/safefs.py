"""The only place the ingest engine writes to disk.

Rules:
  * Writes only create NEW files (O_CREAT | O_EXCL); nothing is ever overwritten.
  * Every destination is checked to be outside every source root first.
  * There is deliberately no delete / move / rename helper in this module.
"""
import os

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
