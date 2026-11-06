"""Phase 2–4 tests: verified offload, MHL, transcodes, LUTs, watchdog, resume and conflicts.
Run:  vendor/python/bin/python3 -m unittest tests/test_pipeline.py -v   (needs ffmpeg)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ingest import luts, mhl, offload, pipeline, safefs, scanner, tools, transcode  # noqa: E402
from test_ingest import build_fixture, snapshot, worker  # noqa: E402

HAVE_FFMPEG = bool(tools.ffmpeg_path() and tools.ffprobe_path())


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def probe_streams(path):
    out = subprocess.run([tools.ffprobe_path(), "-v", "error", "-show_streams", "-show_format",
                          "-of", "json", path], capture_output=True, text=True).stdout
    return json.loads(out)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe required")
class OffloadTranscodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ingest_pipe_")
        cls.src = os.path.join(cls.tmp, "DRIVE")
        build_fixture(cls.src)
        cls.before = snapshot(cls.src)
        cls.scan = scanner.scan([cls.src])
        cls.project = os.path.join(cls.tmp, "PROJECT")
        cls.backup = os.path.join(cls.tmp, "BACKUP")
        cls.job = {"sources": [cls.src], "rolls": cls.scan["rolls"], "mode": "offload_transcode",
                   "destinations": [cls.project, cls.backup], "outputs": ["edit", "web"]}
        cls.res = pipeline.Runner(cls.job).run()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def roll(self, kind):
        return next(r for r in self.scan["rolls"] if r["kind"] == kind)

    def test_offload_ok_and_counts(self):
        self.assertTrue(self.res["ok"], self.res)
        self.assertEqual(self.res["copy"]["copied"], 11)
        self.assertEqual(self.res["transcode"]["made"], 8)  # 4 decodable clips x EDIT + WEB
        self.assertEqual(self.res["transcode"]["needs_raw_backend"], 4)  # 2 R3D clips x 2

    def test_card_structure_preserved_and_identical(self):
        r = self.roll("sony_xavc")
        for dest in (self.project, self.backup):
            ocf = offload.roll_dir(dest, r)
            for src, rel in offload.roll_files(r):
                self.assertEqual(sha(src), sha(os.path.join(ocf, rel)), rel)
            self.assertTrue(os.path.exists(os.path.join(ocf, "PRIVATE", "M4ROOT", "CLIP", "C0001M01.XML")))
        red = self.roll("red")
        self.assertTrue(os.path.isdir(os.path.join(offload.roll_dir(self.project, red), "A001_1106AB.RDM",
                                                   "A001_C001_1106AB.RDC")))

    def test_no_partials_left(self):
        for d, _, files in os.walk(self.tmp):
            for n in files:
                self.assertNotIn(safefs.PARTIAL, n, os.path.join(d, n))

    def test_mhl_written_and_verifies(self):
        for dest in (self.project, self.backup):
            ocf = offload.roll_dir(dest, self.roll("sony_xavc"))
            mhls = [n for n in os.listdir(os.path.join(ocf, "ascmhl")) if n.endswith(".mhl")]
            self.assertEqual(len(mhls), 1)
            res = mhl.verify(os.path.join(ocf, "ascmhl", mhls[0]))
            self.assertTrue(res["ok"], res)
            self.assertEqual(res["verified"], 5)
            self.assertTrue(os.path.exists(os.path.join(ocf, "ascmhl", "ascmhl_chain.xml")))

    def test_edit_output_spec(self):
        r = self.roll("sony_xavc")
        p = os.path.join(offload.roll_dir(self.project, r, os.path.join("TRANSCODES", "EDIT")), "C0001.mov")
        info = probe_streams(p)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["codec_name"], v.get("profile"), v["width"], v["height"]), ("prores", "Proxy", 1920, 1080))
        a = next(s for s in info["streams"] if s["codec_type"] == "audio")
        self.assertEqual(a["codec_name"], "pcm_s24le")
        tcs = [s.get("tags", {}).get("timecode") for s in info["streams"]]
        self.assertIn("12:30:15:00", tcs)  # Sony start TC carried over for relinking

    def test_web_output_spec(self):
        r = self.roll("generic")
        p = os.path.join(offload.roll_dir(self.project, r, os.path.join("TRANSCODES", "WEB")), "interview.mp4")
        info = probe_streams(p)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["codec_name"], v["width"], v["height"]), ("h264", 1920, 1080))
        self.assertLessEqual(int(v["bit_rate"]), 5_500_000)
        a = next(s for s in info["streams"] if s["codec_type"] == "audio")
        self.assertEqual((a["codec_name"], a["channels"]), ("aac", 2))

    def test_transcodes_only_in_primary(self):
        self.assertFalse(os.path.exists(os.path.join(self.backup, "TRANSCODES")))

    def test_reports_and_journal(self):
        self.assertTrue(os.path.exists(self.res["report"]))
        self.assertTrue(os.path.exists(self.res["report"].replace(".json", ".csv")))
        self.assertTrue(os.path.exists(os.path.join(self.project, ".ingest", "journal.sqlite")))

    def test_source_untouched(self):
        self.assertEqual(snapshot(self.src), self.before)

    def test_rerun_is_idempotent_and_never_overwrites(self):
        res = pipeline.Runner(self.job).run()
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["copy"]["copied"], 0)
        self.assertEqual(res["copy"]["verified_existing"], 11)
        self.assertEqual(res["transcode"]["made"], 0)
        self.assertEqual(res["transcode"]["exists"], 8)

    def test_conflict_is_flagged_and_left_alone(self):
        tmp = tempfile.mkdtemp(prefix="ingest_conflict_", dir=self.tmp)
        r = self.roll("generic")
        job = dict(self.job, rolls=[r], destinations=[tmp], outputs=["edit"])
        target = os.path.join(offload.roll_dir(tmp, r), "interview.mov")
        os.makedirs(os.path.dirname(target))
        with open(target, "wb") as f:  # a different file with the same name (reused roll number)
            f.write(b"someone else's clip")
        res = pipeline.Runner(job).run()
        self.assertFalse(res["ok"])
        self.assertEqual(res["copy"]["conflict"], 1)
        with open(target, "rb") as f:
            self.assertEqual(f.read(), b"someone else's clip")
        self.assertEqual(res["transcode"]["skipped"], 1)  # not transcoded from an unverified original

    def test_stale_partial_from_crash_is_replaced(self):
        tmp = tempfile.mkdtemp(prefix="ingest_partial_", dir=self.tmp)
        r = self.roll("generic")
        final = os.path.join(offload.roll_dir(tmp, r), "interview.mov")
        os.makedirs(os.path.dirname(final))
        with open(safefs.partial_path(final), "wb") as f:
            f.write(b"half a file")
        res = pipeline.Runner(dict(self.job, rolls=[r], destinations=[tmp], mode="offload")).run()
        self.assertTrue(res["ok"], res)
        self.assertEqual(sha(final), sha(r["clips"][0]["paths"][0]))
        self.assertFalse(os.path.exists(safefs.partial_path(final)))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe required")
class PreflightAndModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ingest_plan_")
        cls.src = os.path.join(cls.tmp, "DRIVE")
        build_fixture(cls.src)
        cls.scan = scanner.scan([cls.src])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def job(self, **kw):
        j = {"sources": [self.src], "rolls": self.scan["rolls"], "mode": "offload_transcode",
             "destinations": [os.path.join(self.tmp, "P")], "outputs": ["edit"]}
        j.update(kw)
        return j

    def test_refuses_destination_inside_source(self):
        p = pipeline.plan(self.job(destinations=[os.path.join(self.src, "RED", "out")]))
        self.assertFalse(p["ok"])
        self.assertTrue(any("inside the source" in e for e in p["errors"]))
        res = pipeline.Runner(self.job(destinations=[os.path.join(self.src, "RED", "out")])).run()
        self.assertFalse(res["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.src, "RED", "out")))

    def test_refuses_duplicate_roll_names(self):
        rolls = [dict(r) for r in self.scan["rolls"]]
        rolls[1]["cam"], rolls[1]["roll"], rolls[1]["date"] = rolls[0]["cam"], rolls[0]["roll"], rolls[0]["date"]
        p = pipeline.plan(self.job(rolls=rolls))
        self.assertTrue(any("Rename one" in e for e in p["errors"]))

    def test_refuses_not_enough_space(self):
        orig = safefs.free_bytes
        safefs.free_bytes = lambda path: 1024
        try:
            p = pipeline.plan(self.job())
        finally:
            safefs.free_bytes = orig
        self.assertTrue(any("Not enough space" in e for e in p["errors"]))

    def test_plan_is_read_only(self):
        dest = os.path.join(self.tmp, "never_created")
        pipeline.plan(self.job(destinations=[dest]))
        self.assertFalse(os.path.exists(dest))

    @unittest.skipUnless(shutil.which("hdiutil"), "macOS hdiutil required")
    def test_transcode_only_from_read_only_card(self):
        img, mnt = os.path.join(self.tmp, "card.dmg"), os.path.join(self.tmp, "mnt")
        os.makedirs(mnt)
        subprocess.run(["hdiutil", "create", "-quiet", "-srcfolder", self.src, "-format", "UDRO", img], check=True)
        subprocess.run(["hdiutil", "attach", "-quiet", "-readonly", "-nobrowse", "-mountpoint", mnt, img], check=True)
        try:
            scan = scanner.scan([mnt])
            dest = os.path.join(self.tmp, "TC_ONLY")
            res = pipeline.Runner({"sources": [mnt], "rolls": scan["rolls"], "mode": "transcode",
                                   "destinations": [dest], "outputs": ["web"]}).run()
            self.assertTrue(res["ok"], res)
            self.assertEqual(res["transcode"]["made"], 4)
            self.assertFalse(os.path.exists(os.path.join(dest, "OCF")))
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", mnt], check=False)

    def test_worker_plan_and_run_commands(self):
        r = next(r for r in self.scan["rolls"] if r["kind"] == "generic")
        job = json.dumps(self.job(rolls=[r], destinations=[os.path.join(self.tmp, "W")], outputs=["web"]))
        res, _ = worker("plan", "--job", "-", stdin=job)
        self.assertTrue(res["plan"]["ok"], res)
        res, lines = worker("run", "--job", "-", stdin=job)
        self.assertTrue(res["ok"], res)
        self.assertTrue(any(l["event"] == "progress" and l["stage"] == "transcode" for l in lines))


class LutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ingest_lut_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w") as f:
            f.write(text)
        return p

    def test_cascade_order(self):
        cfg = {"default": {"edit": "auto", "web": "/d.cube"}, "cams": {"A": {"web": "/cam.cube"}},
               "rolls": {"A001": {"edit": None}}, "clips": {"C1": {"web": "/clip.cube"}}}
        roll, clip = {"cam": "A", "roll": "A001"}, {"name": "C1"}
        self.assertIsNone(luts.assignment(cfg, roll, clip, "edit"))  # roll says none
        self.assertEqual(luts.assignment(cfg, roll, clip, "web"), "/clip.cube")
        self.assertEqual(luts.assignment(cfg, roll, {"name": "C2"}, "web"), "/cam.cube")
        self.assertEqual(luts.assignment(cfg, {"cam": "B", "roll": "B001"}, clip, "edit"), "auto")

    def test_suggest_from_gamma(self):
        lib = os.path.join(self.tmp, "lib")
        os.makedirs(lib)
        for n in ("Show_SLog3_to_709.cube", "ARRI_LogC4_709.cube", "notes.txt"):
            open(os.path.join(lib, n), "w").close()
        self.assertTrue(luts.suggest("s-log3-cine", lib).endswith("Show_SLog3_to_709.cube"))
        self.assertTrue(luts.suggest("LogC4", lib).endswith("ARRI_LogC4_709.cube"))
        self.assertIsNone(luts.suggest("rec709", lib))

    def test_cdl_bake_math(self):
        cdl = self.write("look.cdl", """<ColorDecisionList xmlns="urn:ASC:CDL:v1.01"><ColorDecision>
          <ColorCorrection id="sc12"><SOPNode><Slope>0.5 1 1</Slope><Offset>0 0.1 0</Offset><Power>1 1 2</Power></SOPNode>
          <SatNode><Saturation>1</Saturation></SatNode></ColorCorrection></ColorDecision></ColorDecisionList>""")
        out = luts.bake(cdl, None, os.path.join(self.tmp, "baked"), [], size=5)
        cube = luts.read_cube(out)
        r, g, b = luts.sample(cube, (1.0, 0.5, 0.5))
        self.assertAlmostEqual(r, 0.5, places=4)
        self.assertAlmostEqual(g, 0.6, places=4)
        self.assertAlmostEqual(b, 0.25, places=4)
        self.assertEqual(luts.bake(cdl, None, os.path.join(self.tmp, "baked"), [], size=5), out)  # cached

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
    def test_lut_is_applied_in_transcode(self):
        # a 2-point LUT that maps every colour to pure red
        red = self.write("all_red.cube", "LUT_3D_SIZE 2\n" + "1 0 0\n" * 8)
        src = os.path.join(self.tmp, "grey.mov")
        subprocess.run([tools.ffmpeg_path(), "-v", "error", "-f", "lavfi", "-i", "color=gray:size=320x180:rate=24:duration=1",
                        "-c:v", "prores_ks", src], check=True)
        out = os.path.join(self.tmp, "out", "grey.mp4")
        res = transcode.transcode_clip(src, out, "web", {"duration": 1.0}, "T001", [], lut=red)
        self.assertEqual(res["status"], "made", res)
        px = subprocess.run([tools.ffmpeg_path(), "-v", "error", "-i", out, "-frames:v", "1", "-vf", "scale=1:1",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        self.assertGreater(px[0], 200)
        self.assertLess(max(px[1], px[2]), 60)


class WatchdogTests(unittest.TestCase):
    def test_stalled_process_is_killed(self):
        ok, reason, _ = transcode.run_watched([sys.executable, "-c", "import time; time.sleep(60)"],
                                              duration=10, stall_timeout=2, low_priority=False)
        self.assertFalse(ok)
        self.assertIn("stalled", reason)

    def test_stop_event_kills(self):
        stop = threading.Event()
        threading.Timer(1.0, stop.set).start()
        ok, reason, _ = transcode.run_watched([sys.executable, "-c", "import time; time.sleep(60)"],
                                              stall_timeout=30, stop=stop, low_priority=False)
        self.assertEqual((ok, reason), (False, "stopped"))


class SafeFsTests(unittest.TestCase):
    def test_finalize_never_overwrites(self):
        tmp = tempfile.mkdtemp(prefix="ingest_fs_")
        try:
            final = os.path.join(tmp, "a.mov")
            with open(final, "wb") as f:
                f.write(b"keep me")
            part, fh = safefs.open_partial(final, [])
            fh.write(b"new")
            fh.close()
            with self.assertRaises(FileExistsError):
                safefs.finalize(part, final, [])
            with open(final, "rb") as f:
                self.assertEqual(f.read(), b"keep me")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_discard_refuses_non_partial(self):
        with self.assertRaises(safefs.UnsafeDestination):
            safefs.discard_partial("/tmp/clip.mov", [])
        with self.assertRaises(safefs.UnsafeDestination):
            safefs.discard_partial("/Volumes/CARD/clip" + safefs.PARTIAL + ".mov", ["/Volumes/CARD"])


if __name__ == "__main__":
    unittest.main()
