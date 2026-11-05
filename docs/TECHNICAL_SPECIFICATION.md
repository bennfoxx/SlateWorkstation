# SuperJoy Slating Workstation — Technical Architecture & Implementation Specification

**Application:** SuperJoy Slating Workstation (macOS Desktop Application)  
**Version:** v1.0.0  
**Repository:** [github.com/bennfoxx/SlateWorkstation](https://github.com/bennfoxx/SlateWorkstation)  
**Target Environment:** macOS (Apple Silicon arm64 native), Adobe After Effects (2024, 2025, 2026), Adobe Media Encoder (2024, 2025, 2026)  
**Primary Language & Runtime:** Python 3.11 + Tkinter + macOS Cocoa scripting bridge (packaged via PyInstaller)  
**Scripting Target:** Adobe ExtendScript (JSX) running inside After Effects  

---

## 1. Executive Summary & Design Principles

The **SuperJoy Slating Workstation** is a standalone, single-window macOS application designed to automate professional broadcast and social delivery workflows:
1. Generating populated **Standalone 5s Slates** (`.mov` ProRes 422 HQ).
2. Generating **Master Slated Comps** (5s Slate + 1-frame 2-Pop sync tone at 5:00 + 2s Black Pad + Native Master Video).
3. **Un-slating** delivery files (frame-accurate removal of the 7-second head slate + pad, setting timecode picture start cleanly to `01:00:00:00`).
4. **Marrying** pre-rendered slates with master videos and queuing to Adobe Media Encoder (AME).
5. Reviewing rendered deliverables via an **In-App Static Preview Viewer** without external video players.

### Core Architectural Constraint: 100% Dependency-Free
The application requires **zero external runtime dependencies** (no `ffmpeg`, no Homebrew, no third-party Python packages like `pandas`, `openpyxl`, or `Pillow`). Everything is accomplished via Python standard library modules, native macOS system utilities (`/usr/bin/qlmanage`, `osascript`), and embedded Adobe presets and template assets.

---

## 2. Bundled Assets & App Packaging Architecture

All templates, presets, runtime dependencies, and documentation are packaged directly inside the app bundle (`dist/SuperJoy Slating Workstation.app/Contents/Resources/`).

```
SuperJoy Slating Workstation.app/
└── Contents/
    ├── MacOS/
    │   └── SuperJoy Slating Workstation (Universal arm64 binary)
    ├── Frameworks/
    │   ├── Python.framework (Python 3.11.3)
    │   ├── libtcl8.6.dylib & libtk8.6.dylib
    │   └── libssl / libcrypto
    └── Resources/
        ├── sj_Slates From Spreadsheet_Template_006.aep (Multi-aspect AE Slate Template)
        ├── sj_Slates From Spreadsheet_Template_005.aep (Fallback AE Slate Template)
        ├── Slates From Spreadsheet_Template_001.xlsx (Master spreadsheet template)
        ├── SJ.icns (High-res macOS application icon)
        ├── readme.txt (Workstation documentation)
        └── presets/
            ├── SuperJoy_AE_OutputTemplates_Seed.aep (Render Queue OutputModule seed)
            ├── SuperJoy_Apple_ProRes_422_HQ_MatchSource.epr (AME ProRes Match Source preset)
            └── SuperJoy_H264_MatchSource_25Mbps.epr (AME H.264 25 Mbps Match Source preset)
```

At runtime, `_APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))` resolves these resources automatically whether running from raw source or inside the compiled app bundle.

---

## 3. Key Workflow Engines & ExtendScript Generators

### 3.1. Native Metadata Parser (`parse_metadata_file`)
- **Excel (.xlsx) Parsing**: A pure standard-library reader using `zipfile` and `xml.etree.ElementTree`. It parses `xl/sharedStrings.xml` and `xl/worksheets/sheet1.xml`, reconstructing cell coordinates (`A1`, `B1`, etc.) so that empty columns and optional fields remain perfectly aligned.
- **TSV / CSV / TXT Parsing**: Handles UTF-8 with BOM (`\xef\xbb\xbf`), UTF-16 LE/BE, Mac Roman, and CP1252 encodings, transparently stripping Excel placeholder rows (`_`, empty formulas).
- **Column 1 COMP Routing**: Automatically identifies the aspect ratio from the first column (`16x9`, `4x5`, `9x16`, `1x1`, `2x3`) or video pixel dimensions.

### 3.2. Frame-Accurate Timecode & Duration Engine (`setCompStartTimecode`)
To guarantee that broadcast and streaming timecode standards are strictly maintained across mixed frame rates ($23.976$, $24$, $25$, $29.97$, $30$, $50$, $59.94$, $60$ fps):
1. **Dynamic Frame Calculations**:
   Wall-clock floats are never used for frame alignment. ExtendScript dynamically calculates:
   ```javascript
   var nominalFps = Math.round(compFps);
   var slateFrames = Math.round(5.0 * nominalFps);   // e.g. 120 frames at 23.976/24fps
   var headFrames  = Math.round(7.0 * nominalFps);   // e.g. 168 frames at 23.976/24fps
   var slateDuration = slateFrames / compFps;        // 5.005005s at 23.976fps
   var headDuration  = headFrames / compFps;         // 7.007007s at 23.976fps
   var blackDuration = (headFrames - slateFrames) / compFps;
   ```
2. **Display Start Timecode**:
   In After Effects, `comp.displayStartTime` is stored in seconds. Hardcoding `3600.0s` at $23.976$ fps yields $86,313.6$ frames, which displays as `00:59:56:09` (87 frames early).  
   The workstation uses `setCompStartTimecode`:
   ```javascript
   function setCompStartTimecode(c, tcString) {
       try {
           var t = currentFormatToTime(tcString, c.frameRate);
           c.displayStartTime = t + (c.frameDuration * 0.5); // half-frame offset prevents float rounding
       } catch (eTc) {
           c.displayStartTime = (tcString === "00:59:53:00") ? 3593.0 : 3600.0;
       }
   }
   ```
   - **Slated Comps**: Set to `"00:59:53:00"`.
   - **Unslated / Clean Comps**: Set to `"01:00:00:00"`.

### 3.3. Un-Slating Engine (7.0s Head Trim)
- Imports slated source footage into a clean composition.
- Sets composition `displayStartTime` to `01:00:00:00`.
- Offsets the layer by `-headDuration` (`-168 frames` at 23.976 fps) and trims `inPoint = 0.0`.
- **Result:** Frame 0 is guaranteed to be the first picture frame of the spot (no black pad frame or audio pop residue).

### 3.4. Pure Python 2-Pop Audio Synthesizer (`create_beep_wav`)
Uses Python’s `wave`, `struct`, and `math` modules to synthesize an exact uncompressed 16-bit 48 kHz mono 1 kHz sine wave audio file (`_2pop_1kHz_1frame.wav`) at $-20\text{ dBFS}$. In ExtendScript, the layer duration is trimmed to `masterComp.frameDuration` positioned exactly at `slateDuration` ($5:00$), providing a frame-accurate sync flash.

### 3.5. Native Quick Look Static Preview Extraction (`qlmanage`)
Generates high-resolution static thumbnails of the first frame of rendered ProRes `.mov` files without requiring `ffmpeg`:
```bash
/usr/bin/qlmanage -t -s 1080 -o "<output_dir>/_previews" "<output_file>.mov"
```
The resulting PNG is displayed in the built-in modal preview viewer, which supports aspect ratio-aware letterboxing, cycling between queue items, keyboard shortcuts (`Left`, `Right`, `Esc`), and file size/resolution overlays.

---

## 4. File Organization & Project Naming Conventions

### 4.1. Workspace-Named After Effects Projects
- Master AE project files dynamically adopt the workspace/artist name extracted from the spreadsheet or manual entry:
  `<Workspace>_SLATES.aep` (sanitized via `re.sub(r'[^A-Za-z0-9_.-]+', '_')`).
- If no workspace token is provided, it falls back cleanly to `SuperJoy_Standalone_Slates.aep` or `SuperJoy_Master_Slates.aep`.

### 4.2. Timestamped Run Directory Structure
All deliverables, log files, presets, and project files land in a dated run folder:
```
<Output Root>/
└── YYYY_MM_DD/
    └── HHMM_Slates/
        ├── <Workspace>_SLATES.aep
        ├── Slating_Results_Log.txt
        ├── _2pop_1kHz_1frame.wav
        ├── _temp_ae_build.jsx
        ├── _previews/
        │   ├── <SpotID>_16x9_Slate_preview.png
        │   └── <SpotID>_9x16_Slate_preview.png
        ├── _AME_Presets/
        │   ├── SuperJoy_Apple_ProRes_422_HQ_MatchSource.epr
        │   └── SuperJoy_H264_MatchSource_25Mbps.epr
        │
        │── [Standalone Slates Mode]
        │   └── <SpotID>_<Aspect>_Slate.mov
        │
        └── [Master Slated Mode]
            ├── SLATED/
            │   ├── ProRes/ (<SpotID>_<Aspect>_Slated.mov)
            │   └── h264/   (<SpotID>_<Aspect>_Slated.mp4)
            └── UNSLATED/
                ├── ProRes/ (<SpotID>_<Aspect>.mov)
                └── h264/   (<SpotID>_<Aspect>.mp4)
```

---

## 5. UI & Interaction Layer

- **Framework**: Python `tkinter` styled with custom card containers (`RoundedCard`), anti-aliased canvas pills (`MultiSelectPills`), and toggle switches (`ToggleSwitch`).
- **Spreadsheet Template Generation**:
  - A dedicated **`New Spreadsheet Template`** button in the Spreadsheet tab and **`New Spreadsheet`** button in the Batch Slate Builder tab let users duplicate the bundled `.xlsx` template to any local folder, automatically linking and opening it in Excel/Numbers.
- **Workflow Modes**:
  1. `Standalone Slates Only` (default): Renders 5-second slates directly in After Effects.
  2. `Marry Slates + Videos`: Pairs pre-rendered slates with clean video files.
  3. `Un-Slate Delivery Videos`: Trims the 7s head off finished spots to produce clean master deliverables.
- **Auto-Transcode Toggle**: Visible only when master video marrying/slating modes are active, controlling whether H.264 MP4 copies are encoded alongside ProRes 422 HQ masters.
- **One-Click In-App Updater**: Embedded updater (`prompt_self_update`) that pulls the latest verified DMG release from GitHub, clears quarantine attributes via `xattr -cr`, and restarts the app.

---

## 6. Build & Deployment Pipeline

- **Build Script**: `./build_dmg.sh`
- **Steps Executed**:
  1. Compiles with `pyinstaller --windowed --target-architecture arm64 --icon assets/SJ.icns`.
  2. Embeds `.aep` templates, `.xlsx` spreadsheet, `.epr` presets, and `readme.txt` into `Contents/Resources`.
  3. Sets `CFBundleShortVersionString` in `Info.plist`.
  4. Ad-hoc signs the application bundle (`codesign --force --deep --sign -`).
  5. Packages a drag-and-drop DMG (`hdiutil create -format UDZO`) with an `/Applications` symlink and `FIRST_LAUNCH.txt` instructions.
