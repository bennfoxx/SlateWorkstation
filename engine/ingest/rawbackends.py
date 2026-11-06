"""Clips ffmpeg can't decode (R3D, BRAW, ARRIRAW, Canon RAW): routing and backends.

Planned backends (not implemented yet, so these clips are reported as
"needs_raw_backend" instead of failing silently):
  * REDline (RED's free CLI): R3D -> ProRes / H.264 with IPP2 and a LUT
  * Adobe Media Encoder via the existing BridgeTalk path (addFileToBatch), in batches
"""
import os

from . import tools

RAW_EXT = {".r3d", ".braw", ".ari", ".arx", ".crm", ".nev"}


def ffmpeg_can_decode(clip):
    if clip.get("kind") == "red":
        return False
    ext = os.path.splitext(clip["paths"][0])[1].lower()
    return ext not in RAW_EXT


def available():
    return {"redline": tools.redline_path(), "ame": os.path.isdir("/Applications/Adobe Media Encoder 2026")}


def status_text():
    a = available()
    have = [k for k, v in a.items() if v]
    return ("RAW transcoding (REDline / Media Encoder) is not built yet; these clips are copied and "
            "listed in the report. Found: " + (", ".join(have) or "neither REDline nor Media Encoder") + ".")


def transcode(clip, output):
    return {"status": "needs_raw_backend", "error": f"{os.path.splitext(clip['paths'][0])[1].upper()[1:]} "
            "needs REDline or Media Encoder (coming in a later phase)"}
