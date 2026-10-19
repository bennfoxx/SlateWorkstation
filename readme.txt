================================================================================
SUPERJOY SLATING WORKSTATION — ASSISTANT EDITOR USER GUIDE
================================================================================

OVERVIEW
--------
SuperJoy Slating Workstation is a macOS broadcast delivery tool that automates:
  1. Building slated broadcast masters in Adobe After Effects + queueing them
     in Adobe Media Encoder (AME) using the native SuperJoy .aep Slate Template.
  2. Batch "Un-Slating" (trimming the 7.0-second slate + black/2-pop leader)
     via After Effects + Adobe Media Encoder while saving an editable .aep
     project for retroactive QC checks and manual slip/trim fixes.

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
2. TOP PANEL: MASTER ASSETS & STUDIO CONFORM
--------------------------------------------------------------------------------
• SLATE TEMPLATE (.AEP):
  By default, the app automatically loads:
    `sj_Slates From Spreadsheet_Template_005.aep`
  This single After Effects template project contains all native aspect ratio
  slate compositions (`16x9`, `1x1`, `4x5`, `9x16`, `2x3`), countdown layers,
  1kHz 2-pop audio, and the `#Flame` toggle badge. You do NOT need to point the
  app to a PSD folder—just keep the `.aep` template selected (or tap "Browse"
  if you ever want to pick a different `.aep` template).

• MASTER VIDEOS:
  Tap "Browse" and select the folder containing your clean/unslated master video
  files (`.mov`, `.mp4`, or `.mxf`).
  As soon as you select a Master Videos folder, the Batch Slate Builder tab
  automatically scans the filenames and populates the slate queue!

• STUDIO STANDARD (Fallback FPS & Default Aspect):
  Each slated master comp automatically conforms to the frame rate and dimensions
  of your master video file. These pills (`23.976`, `24`, `25`, `29.97`, `30`,
  `59.94`, `60` and `16x9`, `1x1`, `4x5`, `9x16`) act as your studio defaults
  when a clip's metadata does not specify an aspect ratio.


--------------------------------------------------------------------------------
3. TAB 1: BATCH SLATE BUILDER (MOST COMMON WORKFLOW)
--------------------------------------------------------------------------------
Use this tab when you have a folder of master video files and want to build
slates quickly without creating a spreadsheet first.

STEP A — Auto-Pull from Master Video Filenames:
  When you select your "MASTER VIDEOS" folder (or tap "Auto-Pull from Master
  Videos"), the app reads every video filename and extracts:
    • AD-ID       : Leading alphanumeric code at the start of the filename
                    (e.g., `PJ595169000H` or `DEMO001H`)
    • TITLE       : Spot title following the Ad-ID, formatted with underscores `_`
    • TRT         : Broadcast duration (`:60`, `:30`, `:15`, `:06`, etc.)
    • RESOLUTION  : Detected from aspect tokens in the filename (`16x9`, `1x1`,
                    `4x5`, `9x16`) or set from your active SLATE RES pills
    • DATE        : Auto-populated to today's date in `YYYY_MM_DD` format

STEP B — Fill in Shared Campaign Metadata:
  Fill in the shared campaign fields once at the top of the card:
    • AGENCY      : e.g., `THE MARTIN AGENCY`
    • CLIENT      : e.g., `PAPA JOHNS`
    • WORKSPACE   : e.g., `BEN_FOX` (artist / edit bay / project workspace)
    • COPYRIGHT   : e.g., `2026 PAPA JOHNS INTERNATIONAL`
    • AUDIO       : Defaults to `STEREO` (change to `5.1`, `MONO`, etc. if needed)
    • FLAME       : Tap "Include Flame Logo" if the spot was finished in Flame
  As you type into these shared fields, every slate in your queue updates live!

STEP C — Multi-Resolution Slates & Retroactive Resolution Fixes:
  Need to generate multiple aspect ratios at once, or fix a slate that was
  mistakenly set to `16x9` instead of `4x5`? You have three easy ways:
    1. SINGLE-TAP IN THE TABLE:
       Tap directly on the `RESOLUTION` cell (3rd column) of any row in the
       queue table to cycle that individual slate through:
         `16x9 (1920×1080)` -> `1x1 (1080×1080)` -> `4x5 (1080×1350)` -> `9x16 (1080×1920)`
    2. MULTI-SELECT "SLATE RES" PILLS:
       Tap multiple resolution pills (for example, both `16x9` and `9x16`) and:
         • Tap `+ Add / Update Spot` (or `Auto-Pull from Master Videos`) to
           create slates for all selected resolutions at once.
         • Or select existing row(s) in the table and tap `Apply Res to Selected`
           to retroactively switch or expand those spots into the selected
           resolutions.
    3. CYCLE SELECTED RES BUTTON:
       Select one or more rows in the table and tap `Cycle Selected Res`.

STEP D — Generate .AEP & Queue in AME:
  Tap the red `GENERATE .AEP & QUEUE IN AME` button at the bottom of the window.
  The app will:
    • Open the `.aep` slate template in After Effects
    • Duplicate the matching `16x9`, `1x1`, `4x5`, or `9x16` slate composition
      for each spot and populate all text fields on a single line (automatically
      scaling down long titles/IDs so text never wraps or overflows the red grid)
    • Assemble each slated master composition (`5.0s` slate + 1-frame `1kHz`
      2-pop at `00:59:58:00` + `2.0s` black + master video at `01:00:00:00`)
    • Save `<Master Videos Folder>/SLATED_DELIVERY/SuperJoy_Master_Slates.aep`
    • Send all slated master comps to the Adobe Media Encoder queue ready to
      render to `<Master Videos Folder>/SLATED_DELIVERY/`


--------------------------------------------------------------------------------
4. TAB 2: FILE IMPORT (.TSV / .CSV)
--------------------------------------------------------------------------------
Use this tab when a producer or traffic manager has provided a TSV or CSV
spreadsheet (such as the "Slates From Spreadsheet" template).

  1. Make sure `SLATE TEMPLATE (.AEP)` and `MASTER VIDEOS` are selected at the top.
  2. Tap `Browse File` and choose your `.tsv`, `.csv`, or `.txt` file.
  3. Supported column headers (case-insensitive, with or without `^` prefix):
       `Agency`, `Client`, `Title` (or `Name`), `Ad-ID` (or `ID`), `TRT`,
       `Date` (or `Day`), `Workspace_Artist` (or `Workspace`), `Audio`,
       `Copyright`, `#Flame` (or `Flame`: `y`/`n`), `Aspect` (or `Resolution`), `NFA`
  4. Tap `GENERATE .AEP & QUEUE IN AME`.


--------------------------------------------------------------------------------
5. TAB 3: UN-SLATE VIDEOS (AE + MEDIA ENCODER 7.0s HEAD TRIM)
--------------------------------------------------------------------------------
Use this tab when you have slated master videos and need clean, un-slated spots
starting at picture start (`01:00:00:00`, removing the `5.0s` slate + `2.0s`
black/2-pop leader) using After Effects and Adobe Media Encoder.

  1. Switch to `3. Un-Slate Videos`.
  2. Tap `Browse Folder` and select the folder containing your slated videos.
  3. Tap `UN-SLATE & QUEUE IN AME`.
  4. What happens under the hood:
     • After Effects imports every slated video and creates a matching clean
       composition (`<SpotName>_UNSLATED`) with display start timecode set to
       `01:00:00:00` and duration reduced by `7.0 seconds`.
     • Inside each composition, the slated video layer's `startTime` is shifted
       to `-7.0 seconds` (non-destructively).
     • After Effects saves the project to:
         `<Slated Videos Folder>/UNSLATED/SuperJoy_Unslate_Project.aep`
     • All trimmed compositions are sent to **Adobe Media Encoder** targeting:
         `<Slated Videos Folder>/UNSLATED/<CleanSpotName>.mov`

  HOW TO DO RETROACTIVE CHECKS OR MANUAL FIXES WHEN UN-SLATING:
     Because the un-slate workflow builds an After Effects project and queues
     it in Media Encoder (rather than destructively overwriting files):
     • Before hitting the green "Start Queue" play button in Media Encoder, you
       can choose your preferred output preset (e.g., Apple ProRes 422 HQ, H.264)
       or scrub the preview in AME to verify that picture starts cleanly at
       frame 0.
     • If a spot had a non-standard leader (e.g., 6.5s or 8.0s instead of 7.0s),
       simply open `<Folder>/UNSLATED/SuperJoy_Unslate_Project.aep` in After
       Effects, slip the video layer in that spot's composition, save the `.aep`,
       and re-queue in Media Encoder!


--------------------------------------------------------------------------------
6. TROUBLESHOOTING & TIPS FOR ASSISTANT EDITORS
--------------------------------------------------------------------------------
• "No strict filename match found in video folder":
  Make sure each video filename in your Master Videos folder contains the exact
  `Ad-ID` listed in your queue or spreadsheet. The matcher checks token
  boundaries so `ABC123` will match `ABC123_Brand_Spot_30.mov` without
  accidentally matching `ABC1234_OtherSpot.mov`.

• Long Titles or Ad-IDs:
  You never need to manually abbreviate long titles to prevent line wrapping.
  The workstation strips accidental linebreaks and automatically scales down the
  font size of any field that exceeds the width of the right-hand slate column
  (`630px`), keeping every field on a single crisp line inside the red grid.

• Checking Logs:
  • Slating logs are saved to: `<Master Videos>/SLATED_DELIVERY/Slating_Results_Log.txt`
  • Un-Slating logs are saved to: `<Slated Videos>/UNSLATED/Unslate_Log.txt`
================================================================================
