================================================================================
SUPERJOY SLATING WORKSTATION — ASSISTANT EDITOR USER GUIDE
================================================================================

OVERVIEW
--------
SuperJoy Slating Workstation is a macOS broadcast delivery tool that automates
four core workflows using Adobe After Effects + Adobe Media Encoder (AME):

  1. BATCH SLATE BUILDER:
     Auto-pulls Ad-ID, Title, TRT (`60`, `30`, `15`, `06`), and resolution from
     your Master Videos (or lets you enter spots manually / merge a CSV) and
     builds either Slated Masters (Slate + Video) OR Standalone Slates Only
     (no video attached).
  2. CSV / TSV + VIDEO NAMING:
     Imports producer/traffic spreadsheets (`.csv`, `.tsv`, `.txt`), pairs them
     with Master Videos to enforce accurate canonical delivery filenames
     (`<Ad-ID>_<Title>_Slated.mov`), and can even rename raw master video files
     on disk to match the spreadsheet's exact Ad-ID and Title.
  3. MARRY SLATES + VIDEOS:
     Takes a folder of already-rendered slates (`.mov`, `.mp4`, `.mxf`, `.png`,
     `.tif`, `.psd`, `.jpg`) and a folder of existing Master Videos, pairs them
     automatically by Ad-ID (and aspect ratio), and marries them onto a
     broadcast timeline (`00:59:53:00` start) queued in Adobe Media Encoder.
  4. UN-SLATE (TRIM 7.0s):
     Non-destructively trims the `7.0s` leader (`5.0s` slate + `2.0s` black/2-pop)
     from slated videos via After Effects + Media Encoder while saving an
     editable `.aep` project for retroactive QC checks and manual slip/trim fixes.

Broadcast Slate Timeline Standard:
  • 00:59:53:00 – 00:59:58:00 (5.0s) : Populated SuperJoy Broadcast Slate
  • 00:59:58:00 (1 frame)            : 1kHz 2-Pop Audio Tone + Smiley Flash
  • 00:59:58:00 – 01:00:00:00 (2.0s) : 2 Seconds of Black
  • 01:00:00:00 onward               : Master Picture & Audio Start


--------------------------------------------------------------------------------
1. HOW TO LAUNCH THE APP
--------------------------------------------------------------------------------
Double-click:
  Start_SuperJoy_Slating_App.command
(Located in `/Users/benfox/Documents/Development/SuperJoy_SlateWorkstation/`)

Or run from Terminal:
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 SuperJoy_Slating_App.py


--------------------------------------------------------------------------------
2. TOP PANEL: MASTER ASSETS, STUDIO STANDARD & BUILD OUTPUT MODE
--------------------------------------------------------------------------------
• SLATE TEMPLATE (.AEP):
  Automatically pre-loaded on launch with:
    `sj_Slates From Spreadsheet_Template_005.aep`
  This single After Effects template project contains all native aspect ratio
  slate compositions (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`), countdown layers,
  1kHz 2-pop audio, and the `#Flame` toggle badge.

• MASTER VIDEOS:
  Tap "Browse" to select your folder of clean master video files (`.mov`,
  `.mp4`, `.mxf`). (Optional when building Standalone Slates Only!)

• BUILD OUTPUT MODE (Slated Masters vs. Standalone Slates Only):
  Located right inside the top Master Assets card:
  • `Slated Masters (Slate + Video)`:
    Builds full slated broadcast masters (`5.0s` slate + `2-pop` + `2.0s` black
    + master video at `01:00:00:00`) and outputs to `SLATED_DELIVERY/`.
  • `Standalone Slates Only (No Video Attached)`:
    Builds ONLY the populated `5.0s` slates (with countdown + 1-frame 2-pop)
    from either Tab 1 (Batch Slate Builder) or Tab 2 (CSV / TSV) and queues
    them in Adobe Media Encoder outputting to `STANDALONE_SLATES/` (`SuperJoy_Standalone_Slates.aep`).
    No master video files are required in this mode!


--------------------------------------------------------------------------------
3. TAB 1: BATCH SLATE BUILDER
--------------------------------------------------------------------------------
• Auto-Pull from Master Video Filenames:
  Selecting a `MASTER VIDEOS` folder (or tapping `Auto-Pull Videos`) scans every
  video filename and extracts:
    - `AD-ID` (leading alphanumeric code)
    - `TITLE` (spot title with spaces converted to underscores `_`)
    - `TRT` (standard broadcast times `60`, `30`, `15`, `06`)
    - `RESOLUTION` (`16x9`, `1x1`, `4x5`, `9x16`)
    - `DATE` (today's date in `YYYY_MM_DD` format)
• Combine with a CSV/TXT Sheet (`Merge CSV/TXT` button):
  Have both master videos AND a CSV/TXT sheet? Tap `Merge CSV/TXT` in the
  Batch Slate Builder toolbar to combine the spreadsheet's exact official
  Titles, TRTs, Agency, Client, Workspace, and Copyright with your master videos'
  detected aspect ratios.
• Multi-Resolution & Retroactive Resolution Fixes:
  - Single-tap the `RESOLUTION` column (3rd column) on any row in the table to
    cycle `16x9 -> 1x1 -> 4x5 -> 9x16` for that specific slate.
  - Or select multiple `SLATE RES` pills (e.g. `16x9` + `9x16`, or `ALL 4`) and
    tap `Apply Res to Selected` to retroactively switch or expand selected spots
    into multiple resolutions at once.


--------------------------------------------------------------------------------
4. TAB 2: CSV / TSV + VIDEO NAMING (ACCURATE FILENAME SYNC)
--------------------------------------------------------------------------------
Use this tab when working from a `.csv`, `.tsv`, or `.txt` metadata sheet:

  1. Tap `Browse File` to select your spreadsheet.
     The status line immediately shows how many rows loaded and how many match
     clips in your `MASTER VIDEOS` folder.
  2. Accurate Delivery Filenames:
     Every slated output is automatically named using the canonical Ad-ID and
     underscored Title from your metadata (`<Ad-ID>_<Canonical_Title>_Slated.mov`),
     even if the source video file had a rough working name like `PJ595169000H_v3_final.mov`.
  3. Rename Master Video Files on Disk (`Rename Master Video Files from CSV Metadata`):
     Want your raw master video files in the `MASTER VIDEOS` folder renamed to
     match the exact `Ad-ID` and `Title` from the CSV? Tap the green
     `Rename Master Video Files from CSV Metadata` button to batch-rename your
     source master videos on disk (`<Ad-ID>_<Canonical_Title>.mov`).
  4. Send to Batch Builder (`Load CSV + Pair Videos into Batch Builder`):
     Tap the blue button to load all CSV rows + matched video resolutions into
     Tab 1's interactive table for visual inspection or per-slate tweaks.


--------------------------------------------------------------------------------
5. TAB 3: MARRY SLATES + VIDEOS (EXISTING SLATES + EXISTING MASTER VIDEOS)
--------------------------------------------------------------------------------
Use this tab when you ALREADY have rendered slates (standalone `.mov`/`.mp4`
slate clips or `.png`/`.tif`/`.psd`/`.jpg` slate stills) and existing Master
Videos, and simply want to marry them together:

  1. Switch to `3. Marry Slates + Videos`.
  2. Ensure your `MASTER VIDEOS` folder is selected in the top panel.
  3. Tap `Browse Slates` and select your folder of existing slates.
  4. (Optional) Select a `CSV / TXT` file if you want the married output files
     named using the spreadsheet's canonical `<Ad-ID>_<Title>_Slated.mov` titles.
  5. Review the automatic `AD-ID ↔ SLATE ↔ VIDEO ↔ MARRIED DELIVERY FILENAME`
     preview table.
  6. Tap `MARRY SLATES + VIDEOS & QUEUE IN AME`.
     After Effects builds a `00:59:53:00` broadcast composition for each pair
     (`0..5s` existing slate + 1-frame 1kHz 2-pop at `00:59:58:00` + `2s` black +
     master video at `01:00:00:00`), saves `MARRIED_DELIVERY/SuperJoy_Married_Slates.aep`,
     and queues all married spots in Adobe Media Encoder!


--------------------------------------------------------------------------------
6. TAB 4: UN-SLATE (AE + MEDIA ENCODER 7.0s HEAD TRIM)
--------------------------------------------------------------------------------
Use this tab to remove the `7.0s` slate + black/2-pop leader from slated videos
using After Effects and Adobe Media Encoder:

  1. Switch to `4. Un-Slate (Trim 7.0s)`.
  2. Tap `Browse Folder` and choose your folder of slated videos.
  3. Tap `UN-SLATE & QUEUE IN AME`.
  4. After Effects creates a non-destructive trimmed composition (`startTime = -7.0s`,
     display start timecode `01:00:00:00`) for each video, saves an editable
     project at `<Slated Videos Folder>/UNSLATED/SuperJoy_Unslate_Project.aep`
     for retroactive checks or manual slip/trim adjustments, and queues all
     clean spots in Adobe Media Encoder.
================================================================================
