"""Checksums for verified copies and MHL files.

xxh64 (the DIT standard) is used when the `xxhash` module is available in the
embedded Python; otherwise md5, which every MHL reader (Silverstack, ShotPut,
ascmhl) also accepts. All hashers share one tiny interface: update(bytes) / hexdigest().
"""
import hashlib

try:  # optional C extension; bundle it into vendor/python to get xxh64
    import xxhash  # type: ignore
except ImportError:  # pragma: no cover - depends on the runtime
    xxhash = None

AVAILABLE = ["md5", "sha1"] + (["xxh64", "xxh3", "xxh128"] if xxhash else [])
DEFAULT = "xxh64" if xxhash else "md5"


def new(algo=DEFAULT):
    if algo == "md5":
        return hashlib.md5()
    if algo == "sha1":
        return hashlib.sha1()
    if xxhash and algo == "xxh64":
        return xxhash.xxh64()
    if xxhash and algo == "xxh3":
        return xxhash.xxh3_64()
    if xxhash and algo == "xxh128":
        return xxhash.xxh3_128()
    raise ValueError(f"hash algorithm {algo!r} not available (have: {', '.join(AVAILABLE)})")


# --- C4 ID (used by ASC MHL v2 to fingerprint each .mhl file in the chain) ---
_C4_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def c4_id(data):
    n = int.from_bytes(hashlib.sha512(data).digest(), "big")
    out = []
    while n:
        n, r = divmod(n, 58)
        out.append(_C4_ALPHABET[r])
    body = "".join(reversed(out)).rjust(88, "1")
    return "c4" + body
