# SuperJoy Slating Workstation — AI Agent Architecture & Technical Reference

## 1. Purpose & Domain Scope
**SuperJoy Slating Workstation** is a macOS broadcast post-production automation application written in Python 3 (`tkinter` + `ctypes` Objective-C runtime bridge + zero-dependency stdlib `.xlsx` XML parser) that drives **Adobe After Effects** and **Adobe Media Encoder (AME)** via dynamically generated **ExtendScript (`.jsx`)**, `.epr` encoding presets, and `osascript` (AppleScript).

It organizes broadcast slating, transcoding, and finishing into **four focused workspace tabs** plus top-level **Output Folder**, **Build Output Mode**, and **Auto-Transcode** controls:

1. **Tab 1 — Batch Slate Builder (`self.tab_builder`, index `"1"`)**:
   - Auto-pulls `Ad-ID`, underscored `Title`, `TRT` (`60`, `30`, `15`, `06`), and aspect ratio (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`) from filenames in `MASTER VIDEOS`, or imports an `.xlsx`/`.tsv`/`.csv`/`.txt` spreadsheet via `prompt_and_merge_csv_into_batch()`, or accepts manual entry for standalone slates.
   - Supports interactive single-tap editing directly in the queue table (`self.tree`):
     - Column `#3` (`COMP / RES`): cycles `16x9 -> 1x1 -> 4x5 -> 9x16 -> 2x3`.
     - Column `#5` (`FLAME`): toggles per-slate Flame badge (`YES` / `NO`).
     - Column `#7` (`OUTPUT FOLDER`): opens a folder picker to set an **individual slate output folder override** (`row["output_dir"]`).
2. **Tab 2 — XLSX / CSV / TSV Import (`self.tab_file`, index `"0"`)**:
   - Parses native Excel `.xlsx` workbooks (`Slates From Spreadsheet_Template_001.xlsx` via `parse_xlsx_rows`) as well as `.tsv`, `.csv`, and `.txt` files (`parse_metadata_file`) with zero third-party Python dependencies.
   - Maps Column 1 (`COMP`: `16x9`, `4x5`, `9x16`, `1x1`, `2x3`) directly to the matching composition in `__templates` inside `sj_Slates From Spreadsheet_Template_006.aep`.
   - Ignores unpopulated Excel formula placeholder rows (where `NAME == "_"` and `Ad-ID` / `TITLE` are blank) and replaces `"YYYY_MM_DD"` template placeholders with `today_yyyy_mm_dd()`.
   - Can batch-rename raw master video files on disk (`rename_master_videos_from_metadata`) to match canonical `<Ad-ID>_<Title>.<ext>` filenames.
3. **Tab 3 — Marry Slates + Videos (`self.tab_marry`, index `"3"`)**:
   - Pairs already-rendered slates (`.mov`, `.mp4`, `.mxf`, `.png`, `.tif`, `.psd`, `.jpg`) from `self.marry_slates_dir` with existing Master Videos from `self.videos_dir` by `Ad-ID` and aspect ratio (`_scan_marry_pairs`).
   - Builds married broadcast compositions (`00:59:53:00` display start timecode) and clean unslated master compositions (`01:00:00:00`), queuing both into `SLATED/ProRes`, `SLATED/h264`, `UNSLATED/ProRes`, and `UNSLATED/h264`.
4. **Tab 4 — Un-Slate (Trim 7.0s) (`self.tab_unslate`, index `"2"`)**:
   - Performs a non-destructive `7.0s` head trim (`comp.displayStartTime = 3600.0`, `vidLayer.startTime = -7.0`) in After Effects and queues outputs in Adobe Media Encoder to `UNSLATED/ProRes` (`.mov` Apple ProRes 422 HQ) and `UNSLATED/h264` (`.mp4` H.264 25 Mbps).

---

## 2. Final Delivery Folder Structure & Dual Encoding Specs

All export pipelines (`process_batch`, `process_marry`, `process_unslate`) use `create_delivery_folders(base_out_dir, ...)` and `ensure_ame_presets(presets_dir)` to create the standardized broadcast folder hierarchy:

```text
<Output Folder>/
├── SLATED/
│   ├── ProRes/    # Apple ProRes 422 HQ (.mov), Match Source resolution & FPS
│   └── h264/      # H.264 (.mp4), Match Source resolution & FPS, 25 Mbps target/max bitrate
├── UNSLATED/
│   ├── ProRes/    # Apple ProRes 422 HQ (.mov), Match Source resolution & FPS
│   └── h264/      # H.264 (.mp4), Match Source resolution & FPS, 25 Mbps target/max bitrate
└── _AME_Presets/
    ├── SuperJoy_Apple_ProRes_422_HQ_MatchSource.epr
    └── SuperJoy_H264_MatchSource_25Mbps.epr
```

### Configurable Output Folder Hierarchy
1. **Individual Slate Override (`row["output_dir"]`)**: Set via Tab 1's `Set Output Folder` button (with row(s) selected) or by tapping the `OUTPUT FOLDER` cell (`#7`) in `self.tree`. Creates `SLATED/ProRes`, `SLATED/h264`, `UNSLATED/ProRes`, `UNSLATED/h264` inside that slate's custom folder.
2. **Global / Batch Output Folder (`self.output_dir`)**: Set in the top `MASTER ASSETS, OUTPUT DESTINATION & STUDIO CONFORM` card (or via `Set Output Folder` with no rows selected). Applies to batch standalone slates, full slated masters + H.264 transcodes, married slates, and un-slated exports.
3. **Automatic Fallback**: When `self.output_dir` is empty, defaults to `<Master Videos or Spreadsheet Folder>/SLATED_DELIVERY` (or `STANDALONE_SLATES` / `MARRIED_DELIVERY`).

---

## 3. Repository File Inventory

| File | Role |
| :--- | :--- |
| `SuperJoy_Slating_App.py` | Main single-file macOS GUI application, stdlib `.xlsx`/`.tsv`/`.csv` parser, video file renamer, `.epr` preset builder, `SLATED`/`UNSLATED` folder organizer, Objective-C `TKWindow` tap patch, and ExtendScript (`.jsx`) generator. |
| `sj_Slates From Spreadsheet_Template_006.aep` | Default Adobe After Effects 2026 broadcast slate template containing pre-built aspect compositions (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`) in `__templates` and `#Flame` pre-comps (`y`/`n`) in `_solids`. |
| `sj_Slates From Spreadsheet_Template_005.aep` | Legacy fallback After Effects template. |
| `Slates From Spreadsheet_Template_001.xlsx` | Standard producer/assistant-editor Excel workbook (`COMP, NAME, CLIENT, TITLE, Ad-ID, TRT, WORKSPACE_ARTIST, Day, NFA, Flame, Copyright`) imported natively by `parse_xlsx_rows()`. |
| `Start_SuperJoy_Slating_App.command` | Double-clickable macOS `zsh` launcher. |
| `readme.txt` | Assistant Editor operational guide. |
| `AGENT_ARCHITECTURE.md` | Technical reference document for AI coding agents and developers. |

---

## 4. Binary & Layer Structure of `sj_Slates From Spreadsheet_Template_006.aep`
When modifying `write_jsx()`, agents **MUST** preserve compatibility with the internal item and layer hierarchy of `sj_Slates From Spreadsheet_Template_006.aep`:

- `__templates` folder: `16x9` (`1920×1080`), `1x1` (`1080×1080`), `4x5` (`1080×1350`), `9x16` (`1080×1920`), `2x3` (`1080×1620`), each `23.976` fps, `121` frames (`5.0s + 1 frame`), `displayStartTime = 3593.0` (`00:59:53:00`).
- `_solids` folder: `y` (Flame badge visible) and `n` (Flame badge hidden).
- Dynamic right-column value layers (`1..10`): `^NFA`, `THE MARTIN AGENCY` (index 2, expression `name` disabled before `setValue`), `^Client`, `^Title`, `^Ad-ID`, `^TRT`, `^date`, `^WORKSPACE_ARTIST`, `STEREO` (index 9, expression `name` disabled before `setValue`), `^Copyright` (index 10, expression `text.sourceText` disabled before `setValue`).
- Static left-column label layers (`18..26`): `AGENCY`, `CLIENT`, `TITLE`, `ID`, `TRT`, `DATE`, `WORKSPACE`, `AUDIO`, `COPYRIGHT` (lack `^` prefix and are never modified by `resolveFieldValue()`).
