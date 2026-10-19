# SuperJoy Slating Workstation — AI Agent Architecture & Technical Reference

## 1. Purpose & Domain Scope
**SuperJoy Slating Workstation** is a macOS broadcast post-production automation application written in Python 3 (`tkinter` + `ctypes` Objective-C runtime bridge) that drives **Adobe After Effects** and **Adobe Media Encoder (AME)** via dynamically generated **ExtendScript (`.jsx`)** and `osascript` (AppleScript).

It organizes broadcast slating and finishing into **four focused workspace tabs** plus a top-level **Build Output Mode** selector:

1. **Tab 1 — Batch Slate Builder (`self.tab_builder`, index `"1"`)**:
   - Auto-pulls `Ad-ID`, underscored `Title`, `TRT` (`60`, `30`, `15`, `06`), and aspect ratio (`16x9`, `1x1`, `4x5`, `9x16`) from filenames in `MASTER VIDEOS`, or merges a CSV/TSV spreadsheet via `prompt_and_merge_csv_into_batch()`, or accepts manual entry for standalone slates.
   - Supports multi-resolution slate generation and single-tap retroactive resolution editing in the queue table.
2. **Tab 2 — CSV / TSV + Video Naming (`self.tab_file`, index `"0"`)**:
   - Parses `.csv`, `.tsv`, or `.txt` metadata sheets (`parse_metadata_file`).
   - Combines CSV metadata with Master Videos (`load_csv_into_batch_builder`) to enforce accurate canonical delivery filenames (`build_canonical_delivery_stem` -> `<Ad-ID>_<Title>_Slated.mov`).
   - Can batch-rename raw master video files on disk (`rename_master_videos_from_metadata`) so source files match the exact canonical `<Ad-ID>_<Title>.<ext>` from the spreadsheet.
3. **Tab 3 — Marry Slates + Videos (`self.tab_marry`, index `"3"`)**:
   - Pairs already-rendered slates (`.mov`, `.mp4`, `.mxf`, `.png`, `.tif`, `.psd`, `.jpg`) from `self.marry_slates_dir` with existing Master Videos from `self.videos_dir` by `Ad-ID` and aspect ratio (`_scan_marry_pairs`).
   - Optionally applies canonical delivery filenames from a CSV/TSV file (`self.marry_csv_path`).
   - Builds married broadcast compositions (`00:59:53:00` display start timecode, `0..5s` existing slate + 1-frame 1kHz 2-pop at `5.0s` + `2.0s` black + master video at `7.0s`), saves `MARRIED_DELIVERY/SuperJoy_Married_Slates.aep`, and queues all comps in **Adobe Media Encoder** (`process_marry` / `write_marry_jsx`).
4. **Tab 4 — Un-Slate (Trim 7.0s) (`self.tab_unslate`, index `"2"`)**:
   - Performs a non-destructive `7.0s` head trim (removing the `5.0s` slate + `2.0s` black/2-pop leader so picture starts at `01:00:00:00`) using **After Effects + Adobe Media Encoder**.
   - Creates a clean composition per video (`comp.displayStartTime = 3600.0`, `vidLayer.startTime = -7.0`), saves an editable project (`<Folder>/UNSLATED/SuperJoy_Unslate_Project.aep`) for retroactive QC and manual slip/trim adjustments, and sends all trimmed comps to **Adobe Media Encoder** (`process_unslate` / `write_unslate_jsx`).

### Top-Level Build Output Mode (`self.output_mode_var`)
- **`"slated_masters"` (`Slated Masters (Slate + Video)`)**: Pairs each generated slate with its matching master video and queues the full slated master comp (`7.0s + video.duration`) in AME (`SLATED_DELIVERY/SuperJoy_Master_Slates.aep`).
- **`"slates_only"` (`Standalone Slates Only (No Video Attached)`)**: Builds and populates only the `5.0s` slate compositions (including countdown and 1-frame 2-pop) from `sj_Slates From Spreadsheet_Template_005.aep` and queues them directly in AME (`STANDALONE_SLATES/SuperJoy_Standalone_Slates.aep`) without requiring any master videos.

---

## 2. Repository File Inventory

| File | Role |
| :--- | :--- |
| `SuperJoy_Slating_App.py` | Main single-file macOS GUI application, filename parser, CSV/TSV normalizer, video file renamer, slate/video marriage engine, Objective-C `TKWindow` tap patch, and ExtendScript (`.jsx`) generator. |
| `sj_Slates From Spreadsheet_Template_005.aep` | Native Adobe After Effects broadcast slate template containing pre-built aspect compositions (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`), countdown layers, 1-frame 2-pop smiley & tone, and `#Flame` pre-comps (`y`/`n`). |
| `Start_SuperJoy_Slating_App.command` | Double-clickable macOS `zsh` launcher that resolves its own directory (`${0:A:h}`) and selects a Python 3 interpreter with `tkinter` support. |
| `readme.txt` | Assistant Editor operational guide covering all 4 tabs, Standalone Slates Only mode, CSV+Video filename syncing, Marrying existing slates, and AME Un-Slating. |
| `AGENT_ARCHITECTURE.md` | This technical reference document for AI coding agents and developers. |

---

## 3. Binary & Layer Structure of `sj_Slates From Spreadsheet_Template_005.aep`
When modifying `write_jsx()`, agents **MUST** preserve compatibility with the exact internal item and layer hierarchy of `sj_Slates From Spreadsheet_Template_005.aep`:

### 3.1 Project Folder & Composition Hierarchy
- `__templates` folder:
  - `16x9` (`1920×1080`, `23.976` fps, `121` frames = `5.0s + 1 frame`, `displayStartTime = 3593.0` / `00:59:53:00`)
  - `1x1` (`1080×1080`, `23.976` fps, `121` frames)
  - `4x5` (`1080×1350`, `23.976` fps, `121` frames)
  - `9x16` (`1080×1920`, `23.976` fps, `121` frames)
  - `2x3` (`1080×1620`, `23.976` fps, `121` frames)
- `_solids` folder:
  - `y` (`1920×1080` pre-comp displaying the Autodesk Flame badge)
  - `n` (`1920×1080` blank pre-comp used when Flame is off)

### 3.2 Layer Stack Inside Each Template Composition (`16x9`, `1x1`, `4x5`, `9x16`)
Each aspect composition in `__templates` has 42 layers organized into four functional groups:

1. **Dynamic Right-Column Value Text Layers (Layers 1–10)**:
   | Layer Index | Layer Name in `.aep` | Field Semantic | Special Notes / Gotchas |
   | :--- | :--- | :--- | :--- |
   | `1` | `^NFA` | Optional NFA callout (`td["nfa"]`) | **DO NOT** map `agency` to `^NFA`! Defaults to `""` unless `nfa` is explicitly set. |
   | `2` | `THE MARTIN AGENCY` | **AGENCY** value (`td["agency"]`) | Layer name does NOT start with `^`, and `Source Text` has expression `name` enabled! Must disable expression (`textProp.expressionEnabled = false`) before calling `setValue()`. |
   | `3` | `^Client` | **CLIENT** value (`td["client"]`) | Standard `^` prefix. |
   | `4` | `^Title` | **TITLE** value (`td["title"]`) | Standard `^` prefix. |
   | `5` | `^Ad-ID` | **ID** value (`td["id"]`) | Standard `^` prefix. |
   | `6` | `^TRT` | **TRT** value (`td["trt"]`) | Standard `^` prefix. |
   | `7` | `^date` | **DATE** value (`td["date"]`) | Standard `^` prefix. |
   | `8` | `^WORKSPACE_ARTIST` | **WORKSPACE** value (`td["workspace"]`) | Standard `^` prefix. |
   | `9` | `STEREO` | **AUDIO** value (`td["audio"]`) | Layer name does NOT start with `^`, and `Source Text` has expression `name` enabled! Must disable expression before `setValue()`. |
   | `10` | `^Copyright` | **COPYRIGHT** value (`td["copyright"]`) | Has expression `text.sourceText` enabled on `Source Text`! Must disable expression before `setValue()`. |

2. **Flame Toggle Layer (Layer 11)**:
   - Named `#Flame` (pre-comp reference).
   - Controlled in `populateSlateComp()` by setting `layer.enabled = job.flame` and calling `layer.replaceSource(solidComps[job.flame ? "y" : "n"], false)`.

3. **Countdown & 2-Pop Audio/Visual Layers (Layers 12–17, 41–42)**:
   - Layer 12: `2-pop smiley` (`inPoint = 5.0s`, duration `1 frame` at `00:59:58:00`).
   - Layers 13–17: Countdown numerals `3`, `4 `, `5 `, `6`, `7`.
   - Layers 41–42: `Tone` / `Tone 2` (1-frame 1kHz 2-pop audio at `5.0s`).
   - **Critical Timing Rule**: Because the native `.aep` template comp has its 1-frame 2-pop at `5.0s..5.0s + 1 frame`, when `slateComp` is placed into `masterComp`, `slateLayer.outPoint` **must** be set to `5.0 + masterComp.frameDuration` (not `5.0`), so the 1-frame `2-pop smiley` and `Tone` at `00:59:58:00` are preserved!

4. **Static Left-Column Label Text Layers (Layers 18–26)**:
   - Named `AGENCY`, `CLIENT`, `TITLE`, `ID`, `TRT`, `DATE`, `WORKSPACE`, `AUDIO`, `COPYRIGHT` (no `^` prefix).
   - **CRITICAL INVARIANT**: `resolveFieldValue()` in `write_jsx()` explicitly returns `null` for any layer lacking a `^` prefix whose lowercase name matches one of these 9 static labels.

---

## 4. Text Wrapping & Overflow Prevention Architecture

### 4.1 In After Effects Slate Comps (`applySingleLineText` in `write_jsx`)
- **Single-Line Sanitization**: Both Python (`sanitize_single_line`) and ExtendScript (`cleanLine`) strip all `\r`, `\n`, and `\t` characters so no value can ever break onto a second line and collide with the slate row beneath it.
- **Box-Text Widening**: If a `TextLayer` uses paragraph/box text (`textDoc.boxText == true`), `textDoc.boxTextSize` is widened to `[4000, 300]` before setting `textDoc.text` so After Effects never soft-wraps unbroken strings with underscores (`_`).
- **Auto-Fit Font Scaling (`sourceRectAtTime`)**:
  - After setting `textDoc.text`, `applySingleLineText()` measures the rendered single-line width via `layer.sourceRectAtTime(2.0, false).width`.
  - If `rect.width > maxWidthPx` (`630px` on `16x9`, `620px` on `1x1`/`4x5`/`9x16`), it proportionally scales `textDoc.fontSize` down and applies a compensating `textDoc.baselineShift` (`-Math.round((baseFontSize - newSize) * 0.35)`) so the scaled text remains vertically centered with its left-column label.

### 4.2 In the macOS Tkinter GUI (`bind_auto_wrap` & `RoundedEntry`)
- Dynamic `tk.Label` descriptions use `bind_auto_wrap(label, container, pad=28)` which listens to `<Configure>` on the parent container and updates `label.configure(wraplength=...)` dynamically as the window resizes.
- `RoundedEntry` sets `width=4` on the internal `tk.Entry` widget and positions it via `Canvas.create_window(..., width=w - 24)` on `<Configure>`, preventing `tk.Entry`'s character-width request from forcing parent grid columns wider than the window.

---

## 5. Key Subsystems & Internal Mechanisms

1. **macOS Tk 8.6.12 Single-Tap Fix (`patch_macos_tk_tap_bug`)**:
   - Uses `ctypes` and `libobjc.A.dylib` (`method_setImplementation`) to swizzle `TKWindow.mouseInResizeArea` to return `0` (`NO`), fixing the macOS Sonoma/Sequoia/Tahoe + Tk 8.6.12 bug where light trackpad taps are dropped.
2. **Dynamic After Effects App Target Resolution (`resolve_ae_applescript_target`)**:
   - Scans `/Applications/Adobe After Effects */Adobe After Effects *.app` (newest year first) and returns an explicit `application "/Applications/..."` clause so `osascript` never fails with `-1728` on AE 2025/2026 (`com.adobe.AfterEffects.application`).
3. **Canonical Delivery Filename Builder (`build_canonical_delivery_stem`)**:
   - Combines `Ad-ID` + underscored `Title` + optional aspect suffix (`16x9`, `4x5`, etc.) + mode suffix (`Slated` or `Slate`), ensuring accurate delivery filenames when combining CSV metadata with master videos or renaming master video files on disk (`rename_master_videos_from_metadata`).
