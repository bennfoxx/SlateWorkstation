#!/usr/bin/env python3
"""
Re-render every comp in an After Effects project's slate folder as ProRes 422 HQ,
then transcode to visually lossless QuickTime H.264 (.mov, -crf 10, uncompressed PCM audio).

Usage: render_slates_h264.py PROJECT.aep OUTPUT_DIR [--folder "STANDALONE SLATES"]
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from engine.SuperJoy_Slating_App import execute_ae_script_file

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aep", help="After Effects project containing the slate comps")
    ap.add_argument("output_dir", help="where the H.264 .mov slates are written")
    ap.add_argument("--folder", default="STANDALONE SLATES", help="project folder holding the slate comps")
    a = ap.parse_args()
    aep_path = os.path.abspath(a.aep)
    dst_dir = os.path.abspath(a.output_dir)
    folder_name = a.folder
    tmp_hq_dir = "/tmp/slates_hq_staging"
    os.makedirs(tmp_hq_dir, exist_ok=True)

    # 1. Generate JSX to clear RQ, add every comp in the slate folder, apply ProRes 422 HQ, and render
    jsx = f"""
    try {{
        app.beginSuppressDialogs();
        var aep = new File({json.dumps(aep_path)});
        app.open(aep);
        
        while (app.project.renderQueue.numItems > 0) {{
            try {{ app.project.renderQueue.item(1).remove(); }} catch(e) {{ break; }}
        }}
        
        var slatesFolder = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it instanceof FolderItem && it.name === {json.dumps(folder_name)}) {{
                slatesFolder = it;
                break;
            }}
        }}
        
        if (!slatesFolder) {{
            throw new Error("Folder " + {json.dumps(folder_name)} + " not found in project.");
        }}
        
        var added = 0;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it instanceof CompItem && it.parentFolder === slatesFolder) {{
                var rq = app.project.renderQueue.items.add(it);
                var om = rq.outputModule(1);
                om.applyTemplate("Apple ProRes 422 HQ");
                try {{
                    om.setSettings({{"Output Audio": "On", "Output File Info": {{"Subfolder Path": ""}}}});
                }} catch (eAud) {{}}
                var outStem = it.name.replace(/_SLATE$/, "");
                om.file = new File({json.dumps(tmp_hq_dir)} + "/" + outStem + ".mov");
                added++;
            }}
        }}
        
        if (added > 0) {{
            app.project.renderQueue.render();
            app.project.save(aep);
        }}
        
        var statFile = new File("/tmp/slates_render_stat.txt");
        statFile.open("w");
        statFile.writeln("added=" + added);
        statFile.close();
        
    }} catch (e) {{
        var errFile = new File("/tmp/slates_render_stat.txt");
        errFile.open("w");
        errFile.writeln("error=" + e.toString());
        errFile.close();
    }} finally {{
        try {{ app.endSuppressDialogs(false); }} catch (eEnd) {{}}
    }}
    """
    
    jsx_path = "/tmp/render_all_slates_hq.jsx"
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    print(f"Submitting render job to After Effects (comps in '{folder_name}', ProRes 422 HQ)...")
    execute_ae_script_file(jsx_path, timeout=600)
    
    if os.path.exists("/tmp/slates_render_stat.txt"):
        with open("/tmp/slates_render_stat.txt") as sf:
            print("AE status:", sf.read().strip())

    # 2. Transcode each rendered ProRes HQ to visually lossless QuickTime H.264
    rendered_movs = sorted(glob.glob(os.path.join(tmp_hq_dir, "*.mov")))
    print(f"\nRendered {len(rendered_movs)} files in AE. Transcoding to QuickTime H.264 (-crf 10, uncompressed PCM audio)...")
    
    total_size = 0
    for i, mov in enumerate(rendered_movs, 1):
        base = os.path.basename(mov)
        target_path = os.path.join(dst_dir, base)
        tmp_out = target_path + ".h264_tmp.mov"
        
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", mov,
            "-c:v", "libx264",
            "-crf", "10",        # Visually lossless
            "-preset", "slow",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",      # Exact uncompressed PCM audio
            tmp_out
        ]
        res = subprocess.run(cmd)
        if res.returncode == 0 and os.path.isfile(tmp_out) and os.path.getsize(tmp_out) > 0:
            os.replace(tmp_out, target_path)
            sz = os.path.getsize(target_path) / (1024 * 1024)
            total_size += sz
            print(f"[{i:02d}/{len(rendered_movs)}] {base}: {sz:.2f} MB (QuickTime H.264, pristine)")
        else:
            if os.path.isfile(tmp_out):
                os.remove(tmp_out)
            print(f"[{i:02d}/{len(rendered_movs)}] FAILED: {base}", file=sys.stderr)

    if rendered_movs:
        print(f"\nAll done! Total size: {total_size:.1f} MB across {len(rendered_movs)} slates (~{total_size/len(rendered_movs):.2f} MB each).")
    
    # Cleanup temp HQ files
    shutil.rmtree(tmp_hq_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
