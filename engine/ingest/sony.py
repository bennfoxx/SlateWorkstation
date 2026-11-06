"""Sony NonRealTimeMeta sidecar XML (C0001M01.XML) reader."""
import xml.etree.ElementTree as ET

from . import safefs


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _bcd(byte, mask):
    v = byte & mask
    return (v >> 4) * 10 + (v & 0x0F)


def ltc_to_tc(value):
    """Sony LTC value is 4 BCD bytes FFSSMMHH (hex string) with flag bits."""
    try:
        b = bytes.fromhex(value)
    except (ValueError, TypeError):
        return None
    if len(b) != 4:
        return None
    ff, ss, mm, hh = _bcd(b[0], 0x3F), _bcd(b[1], 0x7F), _bcd(b[2], 0x7F), _bcd(b[3], 0x3F)
    sep = ";" if b[0] & 0x40 else ":"
    return f"{hh:02d}:{mm:02d}:{ss:02d}{sep}{ff:02d}"


def parse_xml(path):
    try:
        with safefs.open_source(path) as f:
            root = ET.fromstring(f.read(2_000_000))
    except (OSError, ET.ParseError):
        return {}
    r = {}
    for el in root.iter():
        tag, a = _local(el.tag), el.attrib
        if tag == "CreationDate":
            r["created"] = a.get("value")
        elif tag == "Duration" and "value" in a:
            r["duration_frames"] = a.get("value")
        elif tag == "LtcChangeTable":
            r["tc_fps"] = a.get("tcFps")
        elif tag == "LtcChange" and a.get("frameCount") == "0" and "tc_start" not in r:
            r["tc_start"] = ltc_to_tc(a.get("value"))
        elif tag == "VideoFrame":
            r["video_codec"] = a.get("videoCodec")
            r["capture_fps"] = a.get("captureFps")
            r["format_fps"] = a.get("formatFps")
        elif tag == "VideoLayout":
            r["width"] = a.get("pixel")
            r["height"] = a.get("numOfVerticalLine")
        elif tag == "AudioFormat":
            r["audio_channels"] = a.get("numOfChannel")
        elif tag == "Device":
            r["manufacturer"] = a.get("manufacturer")
            r["model"] = a.get("modelName")
            r["serial"] = a.get("serialNo")
        elif tag == "Item":
            name = a.get("name")
            if name == "CaptureGammaEquation":
                r["gamma"] = a.get("value")
            elif name == "CaptureColorPrimaries":
                r["gamut"] = a.get("value")
    return r
