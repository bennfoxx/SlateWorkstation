"""Media hash lists.

write_v2(): writes an ASC MHL v2 history into <roll>/ascmhl/ (NNNN_<name>_<date>.mhl plus
ascmhl_chain.xml), following the ASC MHL v2.0 schema layout. Not yet validated with the
official `ascmhl verify` tool: do that before relying on it for delivery.

read(): parses MHL v1.x (ShotPut / older Silverstack) and ASC MHL v2 (Silverstack 8+,
ascmhl) into [{"path", "size", "hashes": {algo: hex}}] so existing offloads can be
verified (Silverstack interop).
"""
import datetime as dt
import os
import socket
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

from . import hashing, safefs

TOOL = "MSTR-SL8R Ingest"
TOOL_VERSION = "0.2"
HASH_TAGS = ("xxh64", "xxh3", "xxh128", "md5", "sha1", "c4")


def _now():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def write_v2(roll_dir, entries, sources, process="transfer", roll_name=None):
    """entries: [{"rel": path relative to roll_dir, "size", "mtime", "algo", "hash"}].
    Returns the .mhl path. Never overwrites: each call appends a new generation."""
    mhl_dir = safefs.ensure_dir(os.path.join(roll_dir, "ascmhl"), sources)
    existing = sorted(n for n in os.listdir(mhl_dir) if n.endswith(".mhl"))
    seq = len(existing) + 1
    name = roll_name or os.path.basename(roll_dir.rstrip(os.sep))
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    mhl_name = f"{seq:04d}_{name}_{stamp}.mhl"
    now = _now()
    hashes = []
    for e in sorted(entries, key=lambda e: e["rel"]):
        hashes.append(
            f'    <hash>\n      <path size="{int(e["size"])}" lastmodificationdate="{_iso(e["mtime"])}">'
            f'{escape(e["rel"].replace(os.sep, "/"))}</path>\n'
            f'      <{e["algo"]} action="original" hashdate="{now}">{e["hash"]}</{e["algo"]}>\n    </hash>')
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<hashlist version="2.0" xmlns="urn:ASC:MHL:v2.0">
  <creatorinfo>
    <creationdate>{now}</creationdate>
    <hostname>{escape(socket.gethostname())}</hostname>
    <tool version={quoteattr(TOOL_VERSION)}>{TOOL}</tool>
  </creatorinfo>
  <processinfo>
    <process>{process}</process>
    <ignore>
      <pattern>.DS_Store</pattern>
      <pattern>ascmhl</pattern>
      <pattern>ascmhl/</pattern>
    </ignore>
  </processinfo>
  <hashes>
{chr(10).join(hashes)}
  </hashes>
</hashlist>
"""
    data = xml.encode("utf-8")
    path = safefs.write_new(os.path.join(mhl_dir, mhl_name), data, sources)
    _write_chain(mhl_dir, existing + [mhl_name], sources)
    return path


def _write_chain(mhl_dir, names, sources):
    """The chain file is rewritten per generation, so write it as a new versioned file
    then publish it (the old chain is kept as ascmhl_chain.NNNN.xml)."""
    items = []
    for i, n in enumerate(names, 1):
        with safefs.open_source(os.path.join(mhl_dir, n)) as f:
            c4 = hashing.c4_id(f.read())
        items.append(f'  <hashlist sequencenr="{i}">\n    <path>{escape(n)}</path>\n    <c4>{c4}</c4>\n  </hashlist>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<ascmhldirectory xmlns="urn:ASC:MHL:DIRECTORY:v2.0">\n'
           + "\n".join(items) + "\n</ascmhldirectory>\n")
    final = os.path.join(mhl_dir, "ascmhl_chain.xml")
    partial, f = safefs.open_partial(final, sources)
    with f:
        f.write(xml.encode("utf-8"))
        os.fsync(f.fileno())
    if os.path.exists(final):
        # keep history: the previous chain stays, renamed by link to a numbered copy
        safefs.finalize_versioned(final, os.path.join(mhl_dir, f"ascmhl_chain.{len(names) - 1:04d}.xml"), sources)
    safefs.finalize(partial, final, sources)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def read(path):
    """Parse an MHL v1 or v2 file. Paths are relative to the MHL's root folder
    (v2: the folder that contains ascmhl/; v1: the folder holding the .mhl)."""
    with safefs.open_source(path) as f:
        root = ET.fromstring(f.read())
    out = []
    for h in root.iter():
        if _local(h.tag) != "hash":
            continue
        rec = {"path": None, "size": None, "hashes": {}}
        for child in h:
            tag = _local(child.tag)
            if tag in ("path", "file"):
                rec["path"] = (child.text or "").strip()
                if child.get("size"):
                    rec["size"] = int(child.get("size"))
            elif tag == "size":
                rec["size"] = int((child.text or "0").strip())
            elif tag in HASH_TAGS:
                rec["hashes"][tag] = (child.text or "").strip().lower()
        if rec["path"]:
            out.append(rec)
    return out


def mhl_root(path):
    d = os.path.dirname(os.path.abspath(path))
    return os.path.dirname(d) if os.path.basename(d) == "ascmhl" else d


def verify(path, root=None, on_progress=None):
    """Re-hash files listed in an MHL. Returns a summary; reads files only."""
    from .offload import hash_file
    root = root or mhl_root(path)
    records = read(path)
    ok, bad, missing, unsupported = [], [], [], []
    for i, rec in enumerate(records, 1):
        full = os.path.join(root, rec["path"])
        algo = next((a for a in rec["hashes"] if a in hashing.AVAILABLE), None)
        if not os.path.isfile(full):
            missing.append(rec["path"])
        elif algo is None:
            unsupported.append(f"{rec['path']} ({', '.join(rec['hashes'])})")
        else:
            if hash_file(full, algo) == rec["hashes"][algo]:
                ok.append(rec["path"])
            else:
                bad.append(rec["path"])
        if on_progress:
            on_progress(i, len(records))
    return {"mhl": path, "root": root, "files": len(records), "verified": len(ok),
            "mismatched": bad, "missing": missing, "unsupported": unsupported,
            "ok": not bad and not missing and not unsupported}
