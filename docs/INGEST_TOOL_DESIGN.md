# Ingest & Transcode Tool — design proposal

**Status:** Proposal (2026-11-06). Nothing here is implemented yet.
**App:** **MSTR-SL8R Ingest**, a separate companion app to MSTR-SL8R (decided 2026-11-06,
so each app can be dialled in on its own before any merge). Bundle id
`com.benfoxmedia.mstrsl8r.ingest`; its UI lives in `IngestApp/`. It shares `Shared/` (theme,
Python worker, log console) and the embedded Python with the slate apps, and bundles only
`engine/ingest/` + `engine/ingest_worker.py`, none of the slate engine.

## 1. What it is (and isn't)

You point it at a drive, a card, or a network share. It finds every camera card or roll
inside, however deeply it's nested, and then does one of two things:

| Mode | Originals (OCF) | Transcodes |
|---|---|---|
| **Transcode only** | Left where they are, opened read-only | Written to the new project's `TRANSCODES/` |
| **Offload + transcode** | Copied with checksums to `OCF/` (to 1 or 2 destinations), verified, MHL written | Made **from the verified copy**, not from the card |

**Relationship to Silverstack.** Pomfort Silverstack is the industry default, and this
tool should not try to replace it on a big set with a dedicated DIT. The gap it fills is
work in our own pipeline: one tool, one click that goes from "drive plugged in" to
"organised project + edit proxies + web review files + Premiere bin". It uses the same
Adobe integration and presets the slate workstation already ships. So we copy
Silverstack's safety model (xxHash, ASC MHL, verified copies, reports) and **interoperate
with it**: when a drive arrives already offloaded by Silverstack, we read its MHL, verify
against it, and only transcode.

## 2. Folder convention

```
<Project>/
  OCF/                                ← camera originals, card structure preserved
    2026-11-06/
      A-Cam/
        A001/                         ← one roll = one card, copied byte-for-byte
          <original card tree: PRIVATE/M4ROOT/..., CLIPS001/..., A001C003_....mxf, *.RDM/...>
          A001.mhl                    ← ASC MHL v2 manifest (xxh64)
  TRANSCODES/
    EDIT/2026-11-06/A-Cam/A001/A001C003_261106_R1AB.mov   ← same basename as OCF clip
    WEB/2026-11-06/A-Cam/A001/A001C003_261106_R1AB.mp4
  REPORTS/2026-11-06/A001_offload.pdf|csv, ingest.log
  .ingest/journal.sqlite              ← job state (resume after crash)
```

- **Never flatten OCF.** Premiere, Resolve and the camera SDKs need the card structure and
  sidecars (XML, RMD, CIF, BIM).
- Transcodes keep the **OCF basename, timecode and reel name**, so relinking from proxy to
  original works in Premiere and Resolve.
- **Date** comes from clip metadata, in this order: ffprobe `creation_time` → camera
  naming → file birth time. The user can override it. A shoot day that runs past midnight
  needs a "day starts at 05:00" setting.
- **Cam / Roll** come from camera naming where it exists (ARRI/RED/Sony Venice `A001C003…`).
  Otherwise the scanner proposes `A001`, `A002`… per card, and the user confirms or edits
  them in the scan preview before anything runs.

## 3. Discovery (the scanner)

It walks the tree lazily (generator → SQLite rows, so memory stays bounded) and
recognises cards by signature, not by file extension alone:

| Signature | Camera |
|---|---|
| `PRIVATE/M4ROOT`, `XDROOT`, `SONY` | Sony XAVC / Venice / FX |
| `CONTENTS/CLIPS001`, `.CRM` | Canon Cinema RAW Light / XF-AVC |
| `*.RDM/*.RDC/*.R3D` | RED |
| `.braw` + sidecar | Blackmagic |
| ARRI `A001C001_*.mxf` / `.ari` | ARRI |
| `DCIM/100GOPRO`, `DCIM/100MEDIA` (DJI) | Action / drone (chaptered clips grouped) |
| `PRIVATE/AVCHD`, `PANA_GRP` | AVCHD / Panasonic (spanned clips grouped) |
| loose `.mov/.mp4/.mxf` | Generic: one folder = one roll |

It skips `.Spotlight-V100`, `.Trashes`, `._*` AppleDouble files, `.fseventsd`, and our own
`OCF/`/`TRANSCODES/` (so pointing it at a parent folder twice can't recurse into itself).
Each clip is `ffprobe`d once (codec, resolution, fps, TC, duration, audio layout, colour
tags, log profile), with a hard per-file timeout so one corrupt file can't hang the scan.

## 4. "Absolutely cannot delete footage": the safety design

These are enforced in code and by tests, not by convention:

1. **There is no delete, move or rename code path for sources.** All file I/O goes
   through one `safefs` module. Sources are opened `O_RDONLY` only. The module has no
   `remove()`/`unlink()`/`rename()` that accepts a source path. A CI test greps the engine
   and fails if any other module calls `os.remove`, `shutil.rmtree`, `shutil.move`,
   `os.rename` or `unlink`.
2. **Test against read-only media.** The test suite builds fake card trees inside a
   read-only DMG (`hdiutil create … -format UDRO`). Any write to a source anywhere in the
   pipeline fails loudly.
3. **Never overwrite.** Writes go to `name.partial` → fsync → re-hash → atomic rename. If
   the destination already exists with a matching hash, the clip is skipped as already
   done. If the hash differs, the clip is **halted and flagged** (a different clip with the
   same name is a real-world risk with reused roll numbers). It is never overwritten.
4. **Verified copy.** xxh64 is computed while reading the source. The destination is then
   **re-read from disk with `F_NOCACHE`** (so we verify the disk, not the RAM cache) and
   compared. A roll is marked "Offloaded ✓" only after every file verifies and the MHL is
   written. Optionally two destinations at once, like Silverstack.
5. **Pre-flight refusal.** The run stops before it starts if: the destination is inside
   the source (or the reverse), source == destination, there isn't enough free space for the
   whole plan + 5 %, the destination is exFAT/FAT and the plan has case-only name collisions
   or files over 4 GB on FAT, or a path would exceed limits.
6. **The tool never erases, formats or ejects cards.** "Safe to format" is a report the
   human reads; formatting stays a human action in Finder or in the camera.
7. **Transcodes only write under `TRANSCODES/`.** The output path is computed and then
   asserted to sit under that root before any encoder is launched.
8. **Journal + resume.** Every clip/stage state lives in SQLite. After a crash, unplugged
   drive or dropped SMB mount, re-running picks up where it stopped and re-verifies any
   partial copies.

## 5. Not choking on thousands of clips

The failure mode with AME and naïve scripts is enqueueing everything at once. Instead:

- **Pipeline with bounded stages and backpressure:** `scan → copy → verify → transcode(EDIT)
  → transcode(WEB) → report`. Each stage has a fixed-size worker pool and pulls the next
  clip from SQLite only when a slot is free. Nothing holds 3,000 clips in RAM or in a queue.
- **Per-device copy concurrency:** 1 stream per spinning disk or card reader, 2–4 for NVMe,
  1–2 for SMB (configurable). Large aligned buffers (8–16 MB).
- **Transcode concurrency** defaults to 2 ffmpeg processes on this M5 Max (each one
  multi-threaded; VideoToolbox has a limited number of hardware sessions). It runs at
  background QoS (`taskpolicy -b` / `nice`), so the machine stays usable for editing.
- **Watchdog per job:** read ffmpeg's `-progress pipe:1`. If there's no progress for N
  seconds or RSS goes over a cap → kill, retry once, then quarantine the clip and carry on.
  One bad clip never stalls a roll.
- **AME in batches:** when the AME backend is used, submit ≤ 20 items, wait for them to
  finish (the existing `.ame_status` verification pattern), then submit the next batch.

## 6. Encoder backends: hybrid routing

The engine routes each clip based on what ffprobe found:

| Clip codec | Backend |
|---|---|
| ProRes / ProRes RAW / H.264 / HEVC / XAVC / XF-AVC / DNx / MXF OP1a | **ffmpeg** (bundled) |
| R3D, BRAW, ARRIRAW, Canon RAW | **AME** (via our existing BridgeTalk path; Adobe has the SDKs) or the vendor CLI (REDline, ART CLI) if installed |
| Anything undecodable | Copy + verify only, flagged "needs transcode" in the report |

**Verified locally (Homebrew ffmpeg 9.0.2 on this Mac):** `prores_raw` decoder,
`prores_videotoolbox`, `h264_videotoolbox`, `hevc_videotoolbox`, `prores_ks`, `dnxhd`. It has
no BRAW or R3D decoder, which confirms that RAW needs the AME/vendor route.

Default outputs (presets, editable):
- **EDIT:** ProRes 422 Proxy or LT (VideoToolbox, falling back to `prores_ks`), or DNxHR LB.
  Original resolution or half. All audio channels kept, TC and reel name carried over.
- **WEB:** H.264 1080p ~10 Mbps (`h264_videotoolbox`), optional burn-in of clip
  name / TC / LUT name (`drawtext`), 2-ch AAC.

## 7. LUTs

LUTs are first-class. Each output gets its own colour setting:

- **Per output:** e.g. EDIT = show LUT, WEB = show LUT + burn-ins. Or EDIT = log (no LUT)
  for a grade-later workflow.
- **Assignment cascade:** project default → per camera → per roll → per clip. Shown and
  editable in the scan preview table.
- **Auto-suggest from metadata:** the scanner reads the log profile (ARRI LogC3/LogC4,
  Sony S-Log3/S-Gamut3.Cine, Canon C-Log2/3, Panasonic V-Log, BMD Film, Apple Log) and
  pre-selects the matching LUT from the project's `LUTs/` library. The user confirms it.
- **ffmpeg:** `lut3d=file=…cube:interp=tetrahedral`, with explicit input range/matrix
  handling and output tagged bt709, so the result doesn't shift in QuickTime/Premiere.
- **CDL + LUT:** ASC CDL (`.cdl/.ccc/.cc`, e.g. from Livegrade or Silverstack) gets baked
  into a combined 33³ `.cube` in Python before encoding, so per-scene looks need one filter.
- **AME route:** a generated .epr per LUT using the Lumetri "apply LUT" effect *(unverified:
  needs a test that AME honours a LUT set in a preset across 2026 builds)*.
- **Traceability:** the report records each transcode's LUT filename + xxh64, so you can
  reproduce exactly what was baked in.

## 8. Adobe integration (building on what exists)

- **Premiere Pro 2026:** optional final step. Create or open a project, then build bins
  `Date/Cam/Roll`, import OCF and **attach EDIT transcodes as proxies**
  (`ProjectItem.attachProxy`) so editors can toggle proxy ↔ original. The plumbing is the same
  osascript → ExtendScript pattern as AE today *(Premiere's scripting surface is moving to
  UXP; check what 2026 supports before building)*.
- **AME:** the RAW backend, reusing `__sjQueueViaAMEBridgeTalk` but with
  `addFileToBatch` (files, not AE comps) and the batching described above.
- **Slates:** the clip metadata table (scene/take from the camera or entered) could feed the
  existing slate spreadsheet pipeline later.

## 9. Architecture

Same shape as the slate workflows:

- `engine/ingest/` (Python, the canonical engine): `scanner.py`, `safefs.py`, `hashing.py`,
  `mhl.py`, `pipeline.py`, `ffmpeg_backend.py`, `ame_backend.py`, `luts.py`, `report.py`.
- `engine/ingest_worker.py`: a JSON-lines CLI like `slate_worker.py` (`scan`, `plan`, `run`,
  `resume`, `verify-mhl`), with `progress` events per stage so the SwiftUI app shows live
  queue depths.
- SwiftUI **MSTR-SL8R Ingest app** (`IngestApp/`): Source picker (volume, folder or `smb://` share) → Project root →
  Mode → Presets/LUTs → **Scan preview** (Date / Cam / Roll / clips / size / codecs /
  LUT / backend; editable) → Start → per-stage progress → reports.
- **Hashing speed:** stdlib has no xxh64, so bundle the `xxhash` wheel into
  `vendor/python` (it's a C extension and needs signing with the rest). Fall back to
  `hashlib.md5` (also MHL-valid) if it's missing.

## 10. Bundling ffmpeg safely

- **Build it ourselves** (`scripts/build_ffmpeg.sh`): pinned release tarball with a SHA256
  check, `--enable-videotoolbox --enable-audiotoolbox --enable-libfreetype` (needed for
  burn-ins), **no `--enable-gpl` and no `--enable-nonfree`** → an LGPL build. Everything we
  need (VideoToolbox, ProRes, DNx, native AAC, lut3d, drawtext) is available without x264.
  Don't ship third-party static downloads: they're usually GPL and of unknown provenance.
- Ship `ffmpeg` + `ffprobe` as separate executables in `Contents/Helpers/`. Sign them with
  Developer ID + hardened runtime in the existing `install_native_mstr.sh` /
  `notarize_mstr.sh` flow, the same way the embedded Python is handled. We invoke them as
  subprocesses (no linking).
- **LGPL obligations:** an About → Licenses screen, the ffmpeg version + configure line,
  and a pointer to the matching source tarball.
- The resolver prefers the bundled binary and never `PATH`/Homebrew in release builds, so
  behaviour is reproducible.

## 11. Phases

1. **Scanner + scan preview** (read-only, zero risk): proves Date/Cam/Roll detection on
   real drives.
2. **safefs copy + verify + MHL**, with the read-only-DMG test suite. Offload-only mode.
3. **ffmpeg backend** (EDIT/WEB presets, watchdog, concurrency) + bundled LGPL ffmpeg.
4. **LUTs** (cascade, auto-suggest, CDL bake).
5. **AME RAW backend + Premiere bin/proxy attach.**
6. **Silverstack MHL interop, dual destinations, PDF reports.**

## Decisions (2026-11-06, from the user)

- **Priority formats:** Sony (MP4 XAVC on `PRIVATE/M4ROOT`, MXF on `XDROOT`) and RED (R3D),
  plus loose MOV/MP4/MXF. Sony and RED signatures come first.
- **EDIT preset:** ProRes 422 Proxy, 1920×1080 (fit and pad to 16:9, never stretched).
- **WEB preset:** H.264, 3–5 Mbps (target 4 Mbps, max 5), 1920×1080, AAC stereo.
- **R3D note:** ffmpeg can't decode R3D. R3D transcodes and thumbnails need RED's free
  `REDline` CLI (detected if installed) or the AME route.

## Camera reports

- **Generate** (when none exists): per roll, an HTML report (prints cleanly to PDF) + CSV.
  It lists clip name, TC in, duration, fps, resolution, codec, camera/serial, gamma and
  size, plus a thumbnail per clip (ffmpeg frame grab at about 10 % of the duration, 320 px
  JPEG). R3D gets a placeholder unless REDline is installed. Reports are written only
  outside the source, and never overwrite: an existing name gets a `_v2` suffix.
- **Import** (when they exist): CSV / TSV / XLSX from a camera assistant, Silverstack or
  ShotPut. Headers are matched loosely (Roll/Reel/Card/Mag, Clip/File/Name, Scene, Take,
  Lens, Stop/T-Stop, ISO/EI, Shutter, WB, Filter, Notes/Comments, Circled/Good). Rows merge
  onto clips by clip name, falling back to roll + clip number. The scanner also flags report
  files and MHLs it finds on the card itself.

## Premiere: organised copy of an existing project (new phase)

Point the app at a `.prproj`. It reads the media paths (a `.prproj` is gzipped XML), then
builds a **new** organised tree (Date/Cam/Roll for camera media; `AUDIO/`, `GFX/`, `MUSIC/`
etc. by type) using the safe verified copy. Next it saves a **copy** of the project and
relinks that copy to the new paths through Premiere scripting (open copy → `changeMediaPath`
per item → save). It never edits the XML in place or touches the original project.
Premiere's own Project Manager can collect files but can't reorganise them; that's the gap
this fills.

Revised phases: 1 scanner + preview + camera reports (**in progress**) → 2 verified offload →
3 ffmpeg transcodes (EDIT/WEB above) + bundled ffmpeg → 4 LUTs → 5 Premiere bins/proxies +
AME/REDline for R3D → 6 Premiere organised-copy → 7 Silverstack interop / dual destinations.

## Status & roadmap (updated 2026-11-06)

Legend: ✅ built + tested on fixtures · 🟡 code in place, needs real media / a decision · ⬜ not started.
Real Sony / RED cards and a network share are still needed to validate everything marked ✅.

| # | Area | Status | Where | What's left |
|---|---|---|---|---|
| 1 | Scanner (Sony M4ROOT/XDROOT, RED RDM/RDC, loose folders), Date/Cam/Roll proposals | ✅ | `ingest/scanner.py`, `sony.py` | Tune against real cards (Venice X-OCN, FX3 vs FX6 XML, RED naming variants) |
| 1 | Camera report import (CSV/TSV/XLSX) + generation (HTML/CSV + thumbnails) | ✅ | `ingest/camreport.py` | Real AC / Silverstack exports to tune header matching; PDF export |
| 2 | Verified offload: uncached read, hash-while-copy, fsync, uncached read-back, no-overwrite publish, conflicts flagged, stale partials replaced, dual destination | ✅ | `ingest/offload.py`, `safefs.py` | Throughput tuning on real drives / SMB; per-device parallelism |
| 2 | ASC MHL v2 writer + chain; MHL v1/v2 reader + verify | 🟡 | `ingest/mhl.py` | Validate output with the official `ascmhl verify`; xxh64 needs the `xxhash` module in the embedded Python (md5 until then) |
| 2 | Preflight plan: space, dest-inside-source, duplicate roll names, FAT32 4 GB, case collisions, writability | ✅ | `ingest/pipeline.py` `plan()` | — |
| 2 | Journal (SQLite) + JSON/CSV ingest report | ✅ | `pipeline.py` | Resume UI ("finish last job") |
| 3 | Transcodes: EDIT ProRes 422 Proxy 1080p, WEB H.264 4/5 Mbps 1080p, TC + reel name kept, VideoToolbox with software fallback, output check | ✅ | `ingest/transcode.py` | Check relink in Premiere with real footage; audio channel layouts from real cards |
| 3 | Watchdog (stall / memory / wall-time / Stop), bounded pools, low priority, overlap copy→transcode | ✅ | `transcode.py`, `pipeline.py` | Load test with 1,000+ real clips |
| 3 | Modes: transcode only / copy only / copy + transcode | ✅ | `pipeline.py`, `IngestApp/` | — |
| 3 | Bundled LGPL ffmpeg | 🟡 | `scripts/build_ffmpeg.sh`, `embed_ffmpeg.sh` | Download + verify source, pin SHA-256, build (needs your OK to download); static freetype for burn-ins |
| 4 | LUTs: default → cam → roll → clip cascade per output, auto from gamma, CDL + LUT bake, LUT recorded in report | ✅ | `ingest/luts.py` | Your show LUTs; per-clip overrides in the UI (engine supports it) |
| 5 | R3D transcodes / thumbnails / metadata (REDline or AME) | ⬜ | `ingest/rawbackends.py` (stub; R3D reported as "needs_raw_backend") | Install REDline or pick AME; R3D samples |
| 5 | Premiere: bins by Date/Cam/Roll, attach EDIT as proxies | ⬜ | — | Confirm Premiere 2026 scripting surface (ExtendScript vs UXP) |
| 6 | Premiere project → organised copy + relink | ⬜ | — | A sample .prproj |
| 7 | Silverstack interop: verify a Silverstack offload against its MHL, then transcode only | 🟡 | `mhl.verify` + `verify-mhl` command | UI entry point; real Silverstack MHL samples |
| — | Release: Ingest app in install/notarize scripts, own icon | ⬜ | — | — |

## Open questions

- Which network workspace (SMB NAS, LucidLink, Suite, NEXIS)? Each has different
  caching/locking behaviour to test against.
