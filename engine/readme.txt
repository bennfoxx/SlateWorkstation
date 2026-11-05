================================================================================
SUPERJOY SLATING WORKSTATION — ASSISTANT EDITOR USER GUIDE
================================================================================

OVERVIEW
--------
SuperJoy Slating Workstation is a macOS broadcast delivery tool that automates
four core workflows using Adobe After Effects + Adobe Media Encoder (AME):

  1. BATCH SLATE BUILDER:
     Auto-pulls Ad-ID, Title, TRT (`60`, `30`, `15`, `06`), and resolution from
     your Master Videos (or lets you import an `.xlsx` / `.tsv` / `.csv` sheet
     or enter spots manually) and builds either Slated Masters (Slate + Video)
     OR Standalone Slates Only (no video attached).
  2. XLSX / CSV / TSV IMPORT & VIDEO SYNC:
     Imports `Slates From Spreadsheet_Template_001.xlsx` directly (no need to
     export to a tab-delimited `.txt` file first!), routes each row by its
     first column (`COMP`: `16x9`, `4x5`, `9x16`, `1x1`, `2x3`) to the matching
     template comp inside `sj_Slates From Spreadsheet_Template_006.aep`, and can
     also rename raw master video files on disk to match the spreadsheet.
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
1. FINAL DELIVERY FOLDER STRUCTURE & ENCODING SPECS
--------------------------------------------------------------------------------
Whenever you export Slated Masters, Standalone Slates, Married Slates, or
Un-Slated spots, the workstation automatically organizes final files into:

  <Output Folder>/
  ├── SLATED/
  │   ├── ProRes/    -> Apple ProRes 422 HQ (.mov), Match Source resolution
  │   └── h264/      -> H.264 (.mp4), Match Source resolution, 25 Mbps
  └── UNSLATED/
      ├── ProRes/    -> Apple ProRes 422 HQ (.mov), Match Source resolution
      └── h264/      -> H.264 (.mp4), Match Source resolution, 25 Mbps

• In Full Build + Export (`Slated Masters` mode with `Auto-Transcode ProRes 422 HQ + H.264 (25Mbps)` enabled):
  - Queues each Slated Master into `SLATED/ProRes/<Stem>_Slated.mov` and `SLATED/h264/<Stem>_Slated.mp4`.
  - Also auto-transcodes each clean Master Video into `UNSLATED/ProRes/<CleanStem>.mov` and `UNSLATED/h264/<CleanStem>.mp4` in Adobe Media Encoder!


--------------------------------------------------------------------------------
2. SETTING THE OUTPUT FOLDER (INDIVIDUAL SLATES, BATCH SLATES, OR FULL EXPORT)
--------------------------------------------------------------------------------
You can customize the output destination at three levels:

  1. Global / Complete Batch Output Folder (`OUTPUT FOLDER` in Top Panel):
     - In the top `MASTER ASSETS, OUTPUT DESTINATION & STUDIO CONFORM` card, use
       the `OUTPUT FOLDER` field ("Browse") to set the destination folder for
       complete slated masters + H.264 transcodes or batch standalone slates.
     - If left blank, it defaults automatically to `<Master Videos Folder>/SLATED_DELIVERY`
       (or `STANDALONE_SLATES` when building slates without videos).
  2. Batch Slates Output Folder (`Set Output Folder` button in Tab 1):
     - With no rows selected in Tab 1's queue table, click `Set Output Folder` to
       choose the output folder for the entire batch of slates.
  3. Individual Slate Output Folder Override (Per-Slate in Tab 1):
     - Select one or more individual slates in Tab 1's queue table and click
       `Set Output Folder` — OR simply single-tap the `OUTPUT FOLDER (TAP)` cell
       (7th column) on any row in the table — to route that individual slate to
       its own custom output folder (indicated with a `★` badge in the table).


--------------------------------------------------------------------------------
3. TOP PANEL: MASTER ASSETS, STUDIO STANDARD & BUILD OUTPUT MODE
--------------------------------------------------------------------------------
• SLATE TEMPLATE (.AEP):
  Automatically pre-loaded on launch with:
    `sj_Slates From Spreadsheet_Template_006.aep`
  (Updated for the latest version of Adobe After Effects, containing `__templates`
  comps for `16x9`, `1x1`, `4x5`, `9x16`, and `2x3` plus `_solids` `y`/`n` for Flame.)

• MASTER VIDEOS:
  Tap "Browse" to select your folder of clean master video files (`.mov`,
  `.mp4`, `.mxf`). (Optional when building Standalone Slates Only!)

• BUILD OUTPUT MODE & AUTO-TRANSCODE TOGGLE:
  • `Slated Masters (Slate + Video)`:
    Builds full slated broadcast masters (`5.0s` slate + `2-pop` + `2.0s` black
    + master video at `01:00:00:00`) AND clean unslated master comps.
  • `Standalone Slates Only (No Video)`:
    Builds ONLY the populated `5.0s` slates (with countdown + 1-frame 2-pop)
    and queues them to `SLATED/ProRes` and `SLATED/h264`.
  • `Auto-Transcode ProRes 422 HQ + H.264 (25Mbps)`:
    Enabled by default so every build automatically queues both Apple ProRes 422 HQ
    (`.mov`, source resolution) and H.264 (`.mp4`, source resolution, 25 Mbps)
    along with clean Unslated Master transcodes.


--------------------------------------------------------------------------------
4. TAB 1: BATCH SLATE BUILDER
--------------------------------------------------------------------------------
• Import `.XLSX` / `.CSV` / `.TSV` (`Import .XLSX / CSV` button):
  Loads `Slates From Spreadsheet_Template_001.xlsx` (or any `.tsv`/`.csv`/`.txt`
  file) directly into the interactive queue table, preserving each row's `COMP`
  resolution (`16x9`, `4x5`, `9x16`, `1x1`, `2x3`) and per-row `Flame` (`YES`/`NO`).
• Interactive Single-Tap Queue Columns:
  - Tap Column 3 (`COMP / RES (TAP)`) to cycle `16x9 -> 1x1 -> 4x5 -> 9x16 -> 2x3`.
  - Tap Column 5 (`FLAME`) to toggle the Flame badge (`YES` / `NO`) for that slate.
  - Tap Column 7 (`OUTPUT FOLDER (TAP)`) to set a custom output folder for that
    individual slate.


--------------------------------------------------------------------------------
5. TAB 2: XLSX / CSV / TSV IMPORT & VIDEO NAMING
--------------------------------------------------------------------------------
• Native `.xlsx` Support:
  Pre-loaded by default with `Slates From Spreadsheet_Template_001.xlsx` when
  present in the workstation folder. You no longer need to export your Excel
  sheet to a tab-delimited `.txt` file first!
• First Column (`COMP`) Routing:
  The first column (`COMP`: `16x9`, `4x5`, `9x16`, `1x1`, `2x3`) automatically
  directs each row to its corresponding template composition inside
  `sj_Slates From Spreadsheet_Template_006.aep`.
• `Rename Master Video Files from Spreadsheet`:
  Renames raw master video files in your `MASTER VIDEOS` folder on disk to match
  the exact canonical `<Ad-ID>_<Title>.<ext>` from the spreadsheet.
================================================================================
