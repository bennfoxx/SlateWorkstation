#!/usr/bin/env python3
"""
Batch transcode standalone slates to Apple ProRes 422 Proxy (~12MB).
"""
import glob
import os
import subprocess
import sys

def transcode_folder(target_dir):
    files = sorted(glob.glob(os.path.join(target_dir, "*.mov")))
    if not files:
        print(f"No .mov files found in {target_dir}")
        return

    print(f"Found {len(files)} .mov files to convert to ProRes 422 Proxy in {target_dir}")
    total_before = sum(os.path.getsize(f) for f in files)
    
    for i, mov in enumerate(files, 1):
        orig_size = os.path.getsize(mov) / (1024 * 1024)
        base = os.path.basename(mov)
        tmp_mov = mov + ".proxy_tmp.mov"
        
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", mov,
            "-c:v", "prores_ks",
            "-profile:v", "0",  # 0 = Proxy, 1 = LT, 2 = Standard, 3 = HQ, 4 = 4444, 5 = 4444 XQ
            "-vendor", "apl0",
            "-bits_per_mb", "200",
            "-c:a", "copy",
            tmp_mov
        ]
        res = subprocess.run(cmd)
        if res.returncode == 0 and os.path.isfile(tmp_mov) and os.path.getsize(tmp_mov) > 0:
            new_size = os.path.getsize(tmp_mov) / (1024 * 1024)
            os.replace(tmp_mov, mov)
            print(f"[{i:02d}/{len(files)}] {base}: {orig_size:.1f} MB -> {new_size:.1f} MB (ProRes Proxy)")
        else:
            if os.path.isfile(tmp_mov):
                os.remove(tmp_mov)
            print(f"[{i:02d}/{len(files)}] FAILED: {base}", file=sys.stderr)

    total_after = sum(os.path.getsize(f) for f in files)
    print(f"\nDone! Total size: {total_before/(1024*1024):.1f} MB -> {total_after/(1024*1024):.1f} MB (Saved {(total_before-total_after)/(1024*1024):.1f} MB)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: transcode_slates_proxy.py FOLDER_OF_SLATE_MOVS")
    transcode_folder(sys.argv[1])
