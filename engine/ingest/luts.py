"""LUTs for transcodes: library listing, auto-suggestion from camera gamma, a
default → camera → roll → clip cascade per output, and ASC CDL + .cube baking.

Assignment values (per output "edit" / "web", at any cascade level):
  None / "none"          no LUT (log stays log)
  "auto"                 pick from the library using the clip's gamma metadata
  "/path/to/show.cube"   that LUT
  {"lut": <one of the above>, "cdl": "/path/to/look.cdl"}   CDL then LUT, baked into one .cube
"""
import hashlib
import os
import re
import xml.etree.ElementTree as ET

from . import safefs

# gamma metadata (lowercase, punctuation stripped) -> filename keywords to look for
GAMMA_KEYWORDS = [
    (("slog3", "s-log3"), ("slog3", "s-log3", "slog-3")),
    (("slog2",), ("slog2", "s-log2")),
    (("logc4", "arrilogc4"), ("logc4",)),
    (("logc3", "logc", "arrilogc3"), ("logc3", "logc")),
    (("clog3",), ("clog3", "c-log3")),
    (("clog2",), ("clog2", "c-log2")),
    (("vlog",), ("vlog", "v-log")),
    (("log3g10", "redwidegamut", "ipp2"), ("log3g10", "ipp2", "rwg")),
    (("bmdfilm", "blackmagicdesignfilm"), ("bmdfilm", "bmd film", "blackmagic")),
    (("applelog",), ("applelog", "apple log")),
    (("hlg", "aribstdb67"), ("hlg",)),
]


def _flat(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def library(lib_dir):
    if not lib_dir or not os.path.isdir(lib_dir):
        return []
    out = []
    for d, _, files in os.walk(lib_dir):
        for n in sorted(files):
            if n.lower().endswith((".cube", ".cdl", ".cc", ".ccc")) and not n.startswith("._"):
                out.append(os.path.join(d, n))
    return sorted(out)


def suggest(gamma, lib_dir):
    """Best .cube in the library for this gamma, or None."""
    g = _flat(gamma)
    if not g:
        return None
    cubes = [p for p in library(lib_dir) if p.lower().endswith(".cube")]
    for keys, words in GAMMA_KEYWORDS:
        if any(k in g for k in keys):
            for p in cubes:
                name = _flat(os.path.basename(p))
                if any(_flat(w) in name for w in words):
                    return p
    return None


def assignment(luts, roll, clip, output):
    """Walk the cascade; the most specific level that mentions `output` wins."""
    luts = luts or {}
    levels = [
        (luts.get("clips") or {}).get(clip.get("name")),
        (luts.get("rolls") or {}).get(roll.get("roll")) or (luts.get("rolls") or {}).get(roll.get("id")),
        (luts.get("cams") or {}).get(roll.get("cam")),
        luts.get("default"),
    ]
    for lvl in levels:
        if isinstance(lvl, dict) and output in lvl:
            return lvl[output]
    return None


def resolve(luts, roll, clip, output, lib_dir, bake_dir, sources):
    """Return (lut_path_or_None, description) for one clip output."""
    a = assignment(luts, roll, clip, output)
    lut, cdl = (a.get("lut"), a.get("cdl")) if isinstance(a, dict) else (a, None)
    if lut in (None, "", "none"):
        lut = None
    elif lut == "auto":
        gamma = (clip.get("info") or {}).get("gamma")
        lut = suggest(gamma, lib_dir)
        if lut is None and not cdl:
            return None, f"auto: no LUT in library for gamma {gamma!r}" if gamma else "auto: no gamma metadata"
    if cdl:
        return bake(cdl, lut, bake_dir, sources), f"CDL {os.path.basename(cdl)}" + (f" + {os.path.basename(lut)}" if lut else "")
    return (lut, os.path.basename(lut)) if lut else (None, "none")


# ---------------------------------------------------------------- .cube I/O

def read_cube(path):
    size, dmin, dmax, table = None, [0.0] * 3, [1.0] * 3, []
    with safefs.open_source(path) as f:
        for raw in f.read().decode("utf-8", "replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key = line.split()[0].upper()
            if key == "LUT_3D_SIZE":
                size = int(line.split()[1])
            elif key == "DOMAIN_MIN":
                dmin = [float(x) for x in line.split()[1:4]]
            elif key == "DOMAIN_MAX":
                dmax = [float(x) for x in line.split()[1:4]]
            elif key in ("TITLE", "LUT_1D_SIZE", "LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE"):
                if key == "LUT_1D_SIZE":
                    raise ValueError("1D .cube LUTs are not supported for baking")
                continue
            else:
                try:
                    table.append(tuple(float(x) for x in line.split()[:3]))
                except ValueError:
                    continue
    if not size or len(table) != size ** 3:
        raise ValueError(f"{os.path.basename(path)}: not a valid 3D .cube ({len(table)} entries, size {size})")
    return {"size": size, "min": dmin, "max": dmax, "table": table}


def sample(cube, rgb):
    """Trilinear lookup. .cube order: red changes fastest."""
    n = cube["size"]
    t = cube["table"]
    idx = []
    for c, lo, hi in zip(rgb, cube["min"], cube["max"]):
        x = (min(max(c, lo), hi) - lo) / ((hi - lo) or 1) * (n - 1)
        i0 = min(int(x), n - 2) if n > 1 else 0
        idx.append((i0, x - i0))
    (r0, fr), (g0, fg), (b0, fb) = idx
    out = [0.0, 0.0, 0.0]
    for dr, wr in ((0, 1 - fr), (1, fr)):
        for dg, wg in ((0, 1 - fg), (1, fg)):
            for db, wb in ((0, 1 - fb), (1, fb)):
                w = wr * wg * wb
                if w:
                    v = t[(r0 + dr) + (g0 + dg) * n + (b0 + db) * n * n]
                    out[0] += v[0] * w
                    out[1] += v[1] * w
                    out[2] += v[2] * w
    return tuple(out)


def cube_text(size, table, title):
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in table]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- ASC CDL

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def read_cdl(path, cc_id=None):
    """First (or the given id) ColorCorrection in a .cdl / .cc / .ccc file."""
    with safefs.open_source(path) as f:
        root = ET.fromstring(f.read())
    nodes = [e for e in root.iter() if _local(e.tag) == "ColorCorrection"]
    if not nodes and _local(root.tag) == "ColorCorrection":
        nodes = [root]
    if cc_id:
        nodes = [n for n in nodes if n.get("id") == cc_id] or nodes
    if not nodes:
        raise ValueError(f"{os.path.basename(path)}: no ColorCorrection found")
    cdl = {"slope": [1.0] * 3, "offset": [0.0] * 3, "power": [1.0] * 3, "saturation": 1.0}
    for e in nodes[0].iter():
        tag = _local(e.tag)
        if tag in ("Slope", "Offset", "Power"):
            cdl[tag.lower()] = [float(x) for x in (e.text or "").split()[:3]]
        elif tag == "Saturation":
            cdl["saturation"] = float((e.text or "1").strip())
    return cdl


def apply_cdl(rgb, cdl):
    out = []
    for c, s, o, p in zip(rgb, cdl["slope"], cdl["offset"], cdl["power"]):
        v = min(max(c * s + o, 0.0), 1.0)
        out.append(v ** p)
    sat = cdl["saturation"]
    if sat != 1.0:
        luma = 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
        out = [min(max(luma + sat * (c - luma), 0.0), 1.0) for c in out]
    return tuple(out)


def bake(cdl_path, lut_path, bake_dir, sources, size=33):
    """CDL (then optional LUT) → one .cube in bake_dir. Cached by content hash."""
    with safefs.open_source(cdl_path) as f:
        key = hashlib.sha1(f.read())
    if lut_path:
        with safefs.open_source(lut_path) as f:
            key.update(f.read())
    out = os.path.join(bake_dir, f"baked_{key.hexdigest()[:16]}.cube")
    if os.path.exists(out):
        return out
    cdl = read_cdl(cdl_path)
    cube = read_cube(lut_path) if lut_path else None
    table = []
    for b in range(size):
        for g in range(size):
            for r in range(size):
                rgb = apply_cdl((r / (size - 1), g / (size - 1), b / (size - 1)), cdl)
                table.append(sample(cube, rgb) if cube else rgb)
    safefs.ensure_dir(bake_dir, sources)
    title = os.path.basename(cdl_path) + (f" + {os.path.basename(lut_path)}" if lut_path else "")
    try:
        safefs.write_new(out, cube_text(size, table, title), sources)
    except FileExistsError:
        pass  # another worker baked the same combination first
    return out
