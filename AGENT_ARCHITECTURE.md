# SuperJoy Slating Workstation — AI Agent Architecture & Technical Reference

## 1. Purpose & Domain Scope
**SuperJoy Slating Workstation** is a macOS broadcast post-production automation application written in Python 3 (`tkinter` + `ctypes` Objective-C runtime bridge) that drives **Adobe After Effects** and **Adobe Media Encoder (AME)** via dynamically generated **ExtendScript (`.jsx`)** and `osascript` (AppleScript).

It automates two core broadcast finishing workflows:
1. **Batch Broadcast Slating (`process_batch` / `write_jsx`)**:
   - Pairs commercial spot metadata (either auto-parsed from master video filenames in the **Batch Slate Builder** or imported from `.tsv`/`.csv` spreadsheets) with master video files (`.mov`, `.mp4`, `.mxf`).
   - Opens the native After Effects Slate Template project (`sj_Slates From Spreadsheet_Template_005.aep`), duplicates the matching aspect ratio composition (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`), populates all dynamic text layers on a single auto-fitted line, toggles the `#Flame` finishing badge, builds slated master compositions (`00:59:53:00` display start timecode), saves `SuperJoy_Master_Slates.aep`, and queues all comps in **Adobe Media Encoder**.
2. **Batch Un-Slating (`process_unslate` / `write_unslate_jsx`)**:
   - Performs a non-destructive `7.0s` head trim (removing the `5.0s` slate + `2.0s` black/2-pop leader so picture starts at `01:00:00:00`) using **After Effects + Adobe Media Encoder**.
   - Creates a clean composition per video (`comp.displayStartTime = 3600.0`, `vidLayer.startTime = -7.0`), saves an editable project (`<Folder>/UNSLATED/SuperJoy_Unslate_Project.aep`) for retroactive QC and manual slip/trim adjustments, and sends all trimmed comps to **Adobe Media Encoder** (`app.project.renderQueue.queueInAME(false)`).

---

## 2. Repository File Inventory

| File | Role |
| :--- | :--- |
| `SuperJoy_Slating_App.py` | Main single-file macOS GUI application, filename parser, CSV/TSV normalizer, Objective-C `TKWindow` tap patch, and ExtendScript (`.jsx`) generator. |
| `sj_Slates From Spreadsheet_Template_005.aep` | Native Adobe After Effects broadcast slate template containing pre-built aspect compositions (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`), countdown layers, 1-frame 2-pop smiley & tone, and `#Flame` pre-comps (`y`/`n`). |
| `Start_SuperJoy_Slating_App.command` | Double-clickable macOS `zsh` launcher that resolves its own directory (`${0:A:h}`) and selects a Python 3 interpreter with `tkinter` support. |
| `readme.txt` | Assistant Editor operational guide covering setup, Batch Slate Builder, TSV/CSV import, multi-resolution workflows, and AME Un-Slating. |
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
   - **CRITICAL INVARIANT**: `resolveFieldValue()` in `write_jsx()` explicitly returns `null` for any layer lacking a `^` prefix whose lowercase name matches one of these 9 static labels. Never strip `^` unconditionally before checking for static labels, or you will overwrite the narrow left-column labels (`240px` wide) with long values and cause severe text wrapping/overlap.

---

## 4. Text Wrapping & Overflow Prevention Architecture

### 4.1 In After Effects Slate Comps (`applySingleLineText` in `write_jsx`)
- **Single-Line Sanitization**: Both Python (`sanitize_single_line`) and ExtendScript (`cleanLine`) strip all `\r`, `\n`, and `\t` characters so no value can ever break onto a second line and collide with the slate row beneath it.
- **Box-Text Widening**: If a `TextLayer` uses paragraph/box text (`textDoc.boxText == true`), `textDoc.boxTextSize` is widened to `[4000, 300]` before setting `textDoc.text` so After Effects never soft-wraps unbroken strings with underscores (`_`).
- **Auto-Fit Font Scaling (`sourceRectAtTime`)**:
  - In `sj_Slates From Spreadsheet_Template_005.aep`, the right-hand value column starts at `x = 480` on `16x9` (right grid boundary at `x = 1120`, available width `630px`) and `x = 375` on `1x1`/`4x5`/`9x16` (right grid boundary at `x = 1015`, available width `620px`).
  - After setting `textDoc.text`, `applySingleLineText()` measures the rendered single-line width via `layer.sourceRectAtTime(2.0, false).width`.
  - If `rect.width > maxWidthPx`, it proportionally scales `textDoc.fontSize` down (`Math.max(12, Math.floor(baseFontSize * (maxWidthPx / rect.width) * 0.98))`) and applies a compensating `textDoc.baselineShift` (`-Math.round((baseFontSize - newSize) * 0.35)`) so the scaled text remains vertically centered with its left-column label.

### 4.2 In the macOS Tkinter GUI (`bind_auto_wrap` & `RoundedEntry`)
- Dynamic `tk.Label` descriptions use `bind_auto_wrap(label, container, pad=28)` which listens to `<Configure>` on the parent container and updates `label.configure(wraplength=...)` dynamically as the window resizes.
- `RoundedEntry` sets `width=4` on the internal `tk.Entry` widget and positions it via `Canvas.create_window(..., width=w - 24)` on `<Configure>`, preventing `tk.Entry`'s character-width request from forcing parent grid columns wider than the window (`980×810`, `minsize(920, 750)`).

---

## 5. Key Subsystems & Internal Mechanisms

### 5.1 macOS Tk 8.6.12 Single-Tap Fix (`patch_macos_tk_tap_bug`)
Bundled Python 3.11 on macOS ships with Tcl/Tk `8.6.12`, whose `-[TKWindow mouseInResizeArea:]` implementation in `libtk8.6.dylib` returns `YES` across the bottom ~30% of the window. That causes `-[TKApplication _checkResize:]` to swallow `NSLeftMouseDown` events before Tk widgets ever see them.
- `patch_macos_tk_tap_bug()` uses `ctypes` and `libobjc.A.dylib` (`class_replaceMethod`) to swizzle `TKWindow.mouseInResizeArea:` to always return `0` (`NO`).
- Every custom widget (`RoundedButton`, `SegmentedPills`, `MultiSelectPills`, `CheckPill`, `RoundedEntry`) binds directly to `<ButtonPress-1>` for immediate single-tap activation.
- Modal native dialogs (`filedialog`, `messagebox`) are wrapped in `run_after_mouse_up()` + `reset_tk_mouse_state()` + `wake_macos_window()` so AppKit's modal loop never leaves Tk's button-state mask stuck.

### 5.2 Dynamic After Effects App Target Resolution (`resolve_ae_applescript_target`)
Adobe changed the macOS bundle identifier in newer releases (`com.adobe.AfterEffects.application` in AE 2025/2026 vs. `com.adobe.AfterEffects` in older versions). Calling `tell application id "com.adobe.AfterEffects"` on AE 2026 fails with AppleEvent error `-1728`.
- `resolve_ae_applescript_target()` scans `/Applications/Adobe After Effects */Adobe After Effects *.app` (newest year first), inspects `Contents/Info.plist`, and returns `application "/Applications/Adobe After Effects 2026/Adobe After Effects 2026.app"` (or falls back to `application id "com.adobe.AfterEffects"`).

### 5.3 Master Video Filename Parser (`parse_video_filename` & `detect_aspect_from_text`)
When scanning a Master Videos folder:
- `parse_video_filename(filename)` extracts:
  - `ad_id`: Leading token (`^[A-Za-z0-9-]+` containing at least one digit, or short leading prefix).
  - `trt`: Broadcast durations (`60`, `30`, `15`, `06`, `:30`, `30s`, `15sec`, etc.), prioritizing standard broadcast times (`60`, `30`, `15`, `06`).
  - `title`: Remaining body with spaces normalized to underscores (`_`).
- `detect_aspect_from_text(text)` detects `16x9`, `1x1`, `4x5`, `9x16`, or pixel dimensions (`1920x1080`, `1080x1080`, `1080x1350`, `1080x1920`).

### 5.4 Multi-Resolution & Retroactive Resolution Editing
- Each entry in `self.manual_batch_data` stores `"aspect"` (`"16x9"`, `"1x1"`, `"4x5"`, `"9x16"`) and `"resolution"` (`"16x9 (1920×1080)"`, etc.).
- Tapping column `#3` (`RESOLUTION`) in `self.tree` (`_on_tree_tap`) immediately cycles that individual row's aspect ratio.
- `self.batch_res_pills` (`MultiSelectPills`) allows selecting multiple aspect ratios simultaneously; `apply_res_to_selected()` either updates selected rows to a single aspect ratio or expands each selected spot into multiple slate rows (one per selected aspect ratio).
- When multiple slates share the same `Ad-ID` in `process_batch()`, output filenames automatically include the aspect suffix (`<Ad-ID>_<aspect>_Slated.mov`) so exports never overwrite each other in AME.

---

## 6. Extension Guidelines for Future AI Agents
1. **Adding New Aspect Ratios (e.g., `2x3`)**:
   - `sj_Slates From Spreadsheet_Template_005.aep` already contains a `2x3` (`1080×1620`) comp inside `__templates`, and `write_jsx()` already indexes `item.name === "2x3"` into `templateComps["2x3"]`. To expose `2x3` in the UI, add `"2x3": (1080, 1620)` to `ASPECT_RESOLUTIONS` in `SuperJoy_Slating_App.py`.
2. **Adding Custom Adobe Media Encoder Presets (`.epr`)**:
   - Currently, `app.project.renderQueue.queueInAME(...)` queues items using AME's default/last-used format preset so the assistant editor can verify or switch presets before starting the queue (`queueInAME(false)` in Un-Slate, `queueInAME(true)` in Slate).
   - If a studio `.epr` preset file is introduced in the future, apply it on `rqItem.outputModule(1).applyTemplate(...)` prior to calling `queueInAME()`.
3. **Modifying Text Layer Mapping**:
   - Always test against `sj_Slates From Spreadsheet_Template_005.aep` and verify that layers `18..26` (static left-column labels) are untouched and that layers `2` (`THE MARTIN AGENCY`), `9` (`STEREO`), and `10` (`^Copyright`) have `textProp.expressionEnabled = false` set before updating `Source Text`.
