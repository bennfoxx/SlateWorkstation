"""Tests for engine/ingest. Run:  vendor/python/bin/python3 -m unittest tests/test_ingest.py -v

Builds fake Sony (M4ROOT + XDROOT), RED (RDM/RDC) and loose-folder cards with real tiny
clips (needs ffmpeg), then checks detection, metadata, report import/generation, and
that the source media is never modified, including when mounted from a read-only disk image.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
WORKER = os.path.join(ENGINE, "ingest_worker.py")
sys.path.insert(0, ENGINE)

from ingest import tools  # noqa: E402

FFMPEG = tools.ffmpeg_path()

SONY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<NonRealTimeMeta xmlns="urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.00" lastUpdate="2026-11-06T09:00:00-08:00">
<Duration value="48"/>
<LtcChangeTable tcFps="24" halfStep="false"><LtcChange frameCount="0" value="{ltc}" status="increment"/></LtcChangeTable>
<CreationDate value="{created}"/>
<VideoFormat><VideoFrame videoCodec="AVC_1920_1080_HP@L41" captureFps="23.98p" formatFps="23.98p"/>
<VideoLayout pixel="1920" numOfVerticalLine="1080" aspectRatio="16:9"/></VideoFormat>
<AudioFormat numOfChannel="2"/>
<Device manufacturer="Sony" modelName="ILME-FX6V" serialNo="{serial}"/>
<AcquisitionRecord><Group name="CameraUnitMetadataSet">
<Item name="CaptureGammaEquation" value="s-log3-cine"/><Item name="CaptureColorPrimaries" value="s-gamut3-cine"/>
</Group></AcquisitionRecord></NonRealTimeMeta>"""


def make_clip(path, fmt_args, tc="01:00:00:00"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=1000:duration=2:sample_rate=48000", "-timecode", tc,
                    *fmt_args, path], check=True)


def build_fixture(root):
    # Sony FX6 card in "A Cam" folder, 2 clips, with card thumbnail for the first
    card = os.path.join(root, "A Cam", "CARD1")
    clip_dir = os.path.join(card, "PRIVATE", "M4ROOT", "CLIP")
    for i, (ltc, created) in enumerate([("00153012", "2026-11-06T09:15:00-08:00"),
                                        ("00203012", "2026-11-06T09:20:00-08:00")], 1):
        make_clip(os.path.join(clip_dir, f"C000{i}.MP4"), ["-c:v", "libx264", "-c:a", "aac"])
        with open(os.path.join(clip_dir, f"C000{i}M01.XML"), "w") as f:
            f.write(SONY_XML.format(ltc=ltc, created=created, serial="5001234"))
    os.makedirs(os.path.join(card, "PRIVATE", "M4ROOT", "THMBNL"))
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=red:size=160x90", "-frames:v", "1",
                    os.path.join(card, "PRIVATE", "M4ROOT", "THMBNL", "C0001T01.JPG")], check=True)
    # Sony FX9 XDCAM card, different serial -> should become another cam letter
    xd = os.path.join(root, "Card_FX9", "XDROOT", "Clip")
    make_clip(os.path.join(xd, "Clip0001.MXF"),
              ["-c:v", "mpeg2video", "-pix_fmt", "yuv422p", "-b:v", "5M", "-c:a", "pcm_s16le", "-f", "mxf"])
    with open(os.path.join(xd, "Clip0001M01.XML"), "w") as f:
        f.write(SONY_XML.format(ltc="00000010", created="2026-11-06T11:00:00-08:00", serial="7009999"))
    # RED mag: two clips, first is spanned across two segments; plus an AC camera report
    rdm = os.path.join(root, "RED", "A001_1106AB.RDM")
    for clip, segs in (("A001_C001_1106AB", 2), ("A001_C002_1106AB", 1)):
        rdc = os.path.join(rdm, clip + ".RDC")
        os.makedirs(rdc)
        for s in range(1, segs + 1):
            with open(os.path.join(rdc, f"{clip}_{s:03d}.R3D"), "wb") as f:
                f.write(b"RED2" + os.urandom(4096))
    with open(os.path.join(root, "RED", "A001_camera_report.csv"), "w") as f:
        f.write("Roll,Clip,Scene,Take,Lens,Notes\nA001,A001_C001_1106AB,12A,3,50mm,great take\nA001,2,12A,4,50mm,\n")
    # Loose folder of MOVs under B Cam (with macOS junk that must be ignored)
    loose = os.path.join(root, "Shoot", "B_Cam", "B003")
    make_clip(os.path.join(loose, "interview.mov"), ["-c:v", "prores_ks", "-profile:v", "0", "-c:a", "pcm_s16le"],
              tc="10:00:00:00")
    with open(os.path.join(loose, "._interview.mov"), "wb") as f:
        f.write(b"junk")


def snapshot(root):
    out = {}
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n)
            st = os.lstat(p)
            h = ""
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns, st.st_mode, h)
    return out


def worker(*args, stdin=None):
    p = subprocess.run([sys.executable, "-I", "-B", WORKER, *args], input=stdin,
                       capture_output=True, text=True, timeout=300)
    lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    result = lines[-1]
    assert result["event"] == "result", p.stdout + p.stderr
    return result, lines


@unittest.skipUnless(FFMPEG and tools.ffprobe_path(), "ffmpeg/ffprobe required")
class IngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ingest_test_")
        cls.src = os.path.join(cls.tmp, "DRIVE")
        build_fixture(cls.src)
        cls.before = snapshot(cls.src)
        cls.res, cls.lines = worker("scan", "--source", cls.src)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def roll(self, kind):
        return [r for r in self.res["rolls"] if r["kind"] == kind]

    def test_detects_all_cards(self):
        self.assertTrue(self.res["ok"], self.res)
        kinds = sorted(r["kind"] for r in self.res["rolls"])
        self.assertEqual(kinds, ["generic", "red", "sony_xavc", "sony_xdcam"])

    def test_sony_xavc_metadata(self):
        (r,) = self.roll("sony_xavc")
        # A Cam folder hint; A001 is taken by the RED mag, so the auto roll continues at A002
        self.assertEqual((r["date"], r["cam"], r["roll"]), ("2026-11-06", "A", "A002"))
        self.assertEqual(r["clip_count"], 2)
        c = r["clips"][0]
        self.assertEqual(c["info"]["timecode"], "12:30:15:00")
        self.assertEqual(c["info"]["gamma"], "s-log3-cine")
        self.assertEqual(c["info"]["camera_model"], "ILME-FX6V")
        self.assertTrue(c["thumbnail_source"].endswith("C0001T01.JPG"))

    def test_second_sony_body_gets_next_letter(self):
        (r,) = self.roll("sony_xdcam")
        self.assertNotEqual(r["cam"], "A")
        self.assertEqual(r["roll"], f"{r['cam']}001")
        self.assertEqual(r["camera_serial"], "7009999")

    def test_red_segments_grouped_and_named(self):
        (r,) = self.roll("red")
        self.assertEqual((r["cam"], r["roll"]), ("A", "A001"))
        names = [c["name"] for c in r["clips"]]
        self.assertEqual(names, ["A001_C001_1106AB", "A001_C002_1106AB"])
        self.assertEqual(len(r["clips"][0]["paths"]), 2)
        self.assertTrue(r["date"].endswith("-11-06"))

    def test_red_report_auto_imported(self):
        (r,) = self.roll("red")
        c1, c2 = r["clips"]
        self.assertEqual(c1["report"].get("scene"), "12A")
        self.assertEqual(c1["report"].get("notes"), "great take")
        self.assertEqual(c2["report"].get("take"), "4")  # matched by roll + clip number
        imp = self.res["imports"][0]
        self.assertEqual((imp["matched"], imp["rows"]), (2, 2))

    def test_loose_folder_hints_and_junk(self):
        (r,) = self.roll("generic")
        self.assertEqual((r["cam"], r["roll"]), ("B", "B003"))
        self.assertEqual([c["name"] for c in r["clips"]], ["interview"])
        self.assertEqual(r["clips"][0]["info"]["timecode"], "10:00:00:00")
        self.assertEqual(r["clips"][0]["info"]["codec"], "prores")

    def test_progress_events(self):
        self.assertTrue(any(l["event"] == "progress" and l["stage"] == "probe" for l in self.lines))

    def test_camera_report_and_source_untouched(self):
        out = os.path.join(self.tmp, "REPORTS")
        scan = json.dumps({"sources": self.res["sources"], "rolls": self.res["rolls"]})
        res, _ = worker("camera-report", "--scan", "-", "--out", out, stdin=scan)
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(res["written"]), 4)
        sony = next(w for w in res["written"] if w["roll"] == "A002")
        with open(sony["html"]) as f:
            html_text = f.read()
        self.assertIn("12:30:15:00", html_text)
        self.assertTrue(os.path.exists(os.path.join(sony["folder"], "thumbs", "C0002.jpg")))  # ffmpeg grab
        # running again never overwrites: a _v2 folder appears instead
        res2, _ = worker("camera-report", "--scan", "-", "--out", out, stdin=scan)
        self.assertTrue(all(re.search(r"_v2$", w["folder"]) for w in res2["written"]))
        self.assertEqual(snapshot(self.src), self.before)

    def test_refuses_report_inside_source(self):
        scan = json.dumps({"sources": self.res["sources"], "rolls": self.res["rolls"]})
        res, _ = worker("camera-report", "--scan", "-", "--out", os.path.join(self.src, "RED", "reports"), stdin=scan)
        self.assertFalse(res["ok"])
        self.assertIn("Refusing to write inside the source", res["error"])
        self.assertFalse(os.path.exists(os.path.join(self.src, "RED", "reports")))

    @unittest.skipUnless(shutil.which("hdiutil"), "macOS hdiutil required")
    def test_read_only_disk_image(self):
        img = os.path.join(self.tmp, "card.dmg")
        mnt = os.path.join(self.tmp, "mnt")
        os.makedirs(mnt)
        subprocess.run(["hdiutil", "create", "-quiet", "-srcfolder", self.src, "-format", "UDRO", img], check=True)
        subprocess.run(["hdiutil", "attach", "-quiet", "-readonly", "-nobrowse", "-mountpoint", mnt, img], check=True)
        try:
            res, _ = worker("scan", "--source", mnt)
            self.assertTrue(res["ok"], res)
            self.assertEqual(len(res["rolls"]), 4)
            scan = json.dumps({"sources": res["sources"], "rolls": res["rolls"]})
            out = os.path.join(self.tmp, "REPORTS_RO")
            rep, _ = worker("camera-report", "--scan", "-", "--out", out, stdin=scan)
            self.assertTrue(rep["ok"], rep)
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", mnt], check=False)


class StaticSafetyTests(unittest.TestCase):
    FORBIDDEN = re.compile(r"\b(os\.(remove|unlink|rmdir|removedirs|rename|replace|truncate)|"
                           r"shutil\.(rmtree|move|copy\w*)|send2trash|\.unlink\(|\.rename\(|"
                           r"\.replace\(\s*['\"]?/|open\([^)]*['\"][wa+])")

    def test_no_destructive_calls_in_ingest(self):
        files = [os.path.join(ENGINE, "ingest", n) for n in os.listdir(os.path.join(ENGINE, "ingest"))
                 if n.endswith(".py")] + [WORKER]
        offenders = []
        for path in files:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                code = line.split("#")[0]
                if os.path.basename(path) == "safefs.py":
                    code = code.replace('os.fdopen(fd, "wb")', "")  # the one sanctioned O_EXCL writer
                if self.FORBIDDEN.search(code):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], "Destructive or write-mode calls outside safefs:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
