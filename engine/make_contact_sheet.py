#!/usr/bin/env python3
"""Generates a high-res slate contact sheet / thumbnail sheet (PNG and PDF)
arranging all preview slates evenly in a grid with metadata headers and labels.

Usage:
  make_contact_sheet.py PREVIEWS_DIR [TEMPLATE.xlsx] [OUTPUT_BASE]
                        [--client C] [--agency A] [--workspace W] [--campaign NAME] [--date D]
Client / workspace default to the first slate row in the template; nothing is
hard-coded to a particular job.
"""

import argparse
import datetime
import os
import re
import sys
import glob
import openpyxl
from PIL import Image, ImageDraw, ImageFont


def parse_order_from_template(template_path):
    if not os.path.exists(template_path):
        return []
    wb = openpyxl.load_workbook(template_path)
    ws = wb.active
    items = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        aspect = str(row[0] or "")
        name = str(row[1] or "")
        client = str(row[2] or "")
        title = str(row[3] or "")
        ad_id = str(row[4] or "")
        trt = str(row[5] or "")
        workspace = str(row[6] or "")
        if name or ad_id or title:
            items.append({
                "aspect": aspect,
                "name": name,
                "client": client,
                "title": title,
                "ad_id": ad_id,
                "trt": trt,
                "workspace": workspace
            })
    return items


def sanitize_filename_token(value):
    if not value:
        return ""
    cleaned = re.sub(r"[\r\n\t]+", " ", str(value)).strip()
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", cleaned)
    cleaned = re.sub(r"\s*_\s*|\s+", "_", cleaned).strip("_.")
    return cleaned


def find_preview_for_item(item, previews_dir):
    ad_id = item["ad_id"]
    aspect = item["aspect"]
    trt_raw = item["trt"].replace(":", "")
    title = item["title"]

    # Try matching filename
    files = glob.glob(os.path.join(previews_dir, "*.png"))
    
    # 1. Exact match by ad_id and aspect
    candidates = []
    for f in files:
        base = os.path.basename(f)
        if ad_id == "NFA":
            if base.startswith("NFA_") and aspect in base and (f"_{trt_raw}_" in base or base.endswith(f"_{trt_raw}.png") or f"_{item['trt']}_" in base):
                # match title token
                t_token = sanitize_filename_token(title)[:15]
                if t_token in base:
                    return f
                candidates.append(f)
        else:
            if base.startswith(ad_id) and aspect in base:
                return f
            elif base.startswith(ad_id):
                candidates.append(f)
                
    if candidates:
        return candidates[0]
    return None


def _join(parts, sep="   •   "):
    return sep.join(p for p in parts if p)


def generate_contact_sheet(previews_dir, template_path, output_base, client="", agency="",
                           workspace="", campaign="", date=""):
    template_items = parse_order_from_template(template_path) if template_path else []
    first = template_items[0] if template_items else {}
    client = client or first.get("client", "")
    workspace = workspace or first.get("workspace", "")
    date = date or datetime.date.today().strftime("%Y_%m_%d")
    
    # Match items with preview image paths
    slate_entries = []
    used_files = set()
    for item in template_items:
        p_path = find_preview_for_item(item, previews_dir)
        if p_path and p_path not in used_files:
            used_files.add(p_path)
            slate_entries.append((item, p_path))
            
    # Include any remaining previews not matched
    all_files = sorted(glob.glob(os.path.join(previews_dir, "*.png")))
    for f in all_files:
        if f not in used_files:
            base = os.path.basename(f)
            slate_entries.append(({
                "ad_id": base.split("_")[0],
                "aspect": "16x9" if "16x9" in base else "9x16" if "9x16" in base else "4x5" if "4x5" in base else "1x1",
                "title": base.replace("_preview.png", ""),
                "trt": "",
                "client": client,
                "workspace": workspace
            }, f))

    num_items = len(slate_entries)
    if num_items == 0:
        print("No preview images found to build contact sheet.")
        return None

    # Layout geometry
    cols = 6
    rows = (num_items + cols - 1) // cols
    
    col_w = 640
    row_h = 560
    header_h = 320
    footer_h = 100
    margin_x = 60
    margin_y = 40
    
    total_w = margin_x * 2 + cols * col_w
    total_h = header_h + rows * row_h + footer_h
    
    # Create canvas
    canvas = Image.new("RGB", (total_w, total_h), "#0B0C10")
    draw = ImageDraw.Draw(canvas)
    
    # Fonts
    def get_font(size, bold=False):
        font_path = "/System/Library/Fonts/HelveticaNeue.ttc"
        try:
            return ImageFont.truetype(font_path, size, index=1 if bold else 0)
        except Exception:
            try:
                return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
            except Exception:
                return ImageFont.load_default()

    font_title = get_font(44, bold=True)
    font_sub = get_font(22, bold=False)
    font_meta = get_font(18, bold=False)
    font_card_head = get_font(20, bold=True)
    font_card_sub = get_font(14, bold=False)
    font_tag = get_font(15, bold=True)

    # Draw Header
    draw.rectangle([(margin_x, margin_y), (total_w - margin_x, header_h - 20)], fill="#141721")
    draw.rectangle([(margin_x, margin_y), (total_w - margin_x, header_h - 20)], outline="#262A3B", width=2)
    
    # Accent top banner bar (Signature SuperJoy Coral + MSTR Cyan gradient / bar)
    draw.rectangle([(margin_x, margin_y), (total_w - margin_x, margin_y + 8)], fill="#13F1D5")
    
    heading = " — ".join(x.upper() for x in (client, campaign) if x) or "BROADCAST SLATES"
    draw.text((margin_x + 36, margin_y + 36), heading, fill="#FFFFFF", font=font_title)
    draw.text((margin_x + 38, margin_y + 96), f"BROADCAST SLATE CONTACT SHEET  •  {num_items} DELIVERABLES", fill="#13F1D5", font=font_sub)
    
    meta_line = _join([f"CLIENT: {client}" if client else "", f"AGENCY: {agency}" if agency else "",
                       f"WORKSPACE: {workspace}" if workspace else "", f"DATE: {date}"])
    draw.text((margin_x + 38, margin_y + 146), meta_line, fill="#9BA3C2", font=font_meta)
    
    aspects = sorted({e[0].get("aspect", "") for e in slate_entries if e[0].get("aspect")})
    cuts = sorted({e[0].get("trt", "") for e in slate_entries if e[0].get("trt")}, reverse=True)
    stats_line = _join(["ASPECTS: " + ", ".join(a.replace("x", ":") for a in aspects) if aspects else "",
                        "CUTS: " + ", ".join(cuts) if cuts else ""])
    draw.text((margin_x + 38, margin_y + 184), stats_line, fill="#727B9E", font=font_meta)

    # Draw Cards
    thumb_box_w = col_w - 28
    thumb_box_h = 360

    for idx, (item, img_path) in enumerate(slate_entries):
        c = idx % cols
        r = idx // cols
        
        cell_x = margin_x + c * col_w
        cell_y = header_h + r * row_h
        
        # Card Background
        card_rect = [cell_x + 6, cell_y + 6, cell_x + col_w - 6, cell_y + row_h - 10]
        draw.rectangle(card_rect, fill="#13151F", outline="#222534", width=2)
        
        # Image area
        img_rect_x = cell_x + 14
        img_rect_y = cell_y + 14
        draw.rectangle([img_rect_x, img_rect_y, img_rect_x + thumb_box_w, img_rect_y + thumb_box_h], fill="#0A0B10")
        
        try:
            with Image.open(img_path) as im:
                im_ratio = im.width / im.height
                box_ratio = thumb_box_w / thumb_box_h
                
                if im_ratio > box_ratio:
                    new_w = thumb_box_w
                    new_h = int(thumb_box_w / im_ratio)
                else:
                    new_h = thumb_box_h
                    new_w = int(thumb_box_h * im_ratio)
                    
                im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                pos_x = img_rect_x + (thumb_box_w - new_w) // 2
                pos_y = img_rect_y + (thumb_box_h - new_h) // 2
                canvas.paste(im_resized, (pos_x, pos_y))
        except Exception as e:
            draw.text((img_rect_x + 20, img_rect_y + 40), f"Error loading image:\n{e}", fill="#E8453C", font=font_card_sub)
            
        # Draw frame border around thumbnail
        draw.rectangle([img_rect_x, img_rect_y, img_rect_x + thumb_box_w, img_rect_y + thumb_box_h], outline="#2B3045", width=1)
        
        # Labels below image
        text_y = cell_y + thumb_box_h + 24
        
        # Line 1: Ad-ID (Aqua) + Aspect Pill (Yellow/White) + TRT
        ad_id_str = item["ad_id"]
        aspect_str = item["aspect"]
        trt_str = item["trt"]
        
        draw.text((cell_x + 16, text_y), ad_id_str, fill="#13F1D5", font=font_card_head)
        
        # Measure Ad-ID width to position aspect tag
        bbox = font_card_head.getbbox(ad_id_str)
        tag_x = cell_x + 16 + (bbox[2] - bbox[0]) + 14
        
        aspect_pill = f"{aspect_str}  {trt_str}".strip()
        draw.text((tag_x, text_y + 2), aspect_pill, fill="#F3E052", font=font_tag)
        
        # Line 2: Deliverable Name / Title
        title_str = item["title"]
        if len(title_str) > 52:
            title_str = title_str[:50] + "…"
        draw.text((cell_x + 16, text_y + 30), title_str, fill="#9BA3C2", font=font_card_sub)
        
        # Line 3: Index indicator
        draw.text((cell_x + col_w - 56, text_y + 2), f"#{idx+1:02d}", fill="#454C68", font=font_card_sub)

    # Draw Footer
    footer_y = total_h - footer_h + 30
    draw.text((margin_x + 10, footer_y), "MSTR-SL8R & SuperJoy Slating Workstation  •  Automated Delivery Verification", fill="#5A6282", font=font_meta)
    footer_right = _join([f"Generated: {datetime.date.today().isoformat()}", "Confidential"], "  •  ")
    fb = font_meta.getbbox(footer_right)
    draw.text((total_w - margin_x - (fb[2] - fb[0]) - 10, footer_y), footer_right, fill="#5A6282", font=font_meta)

    # Save PNG
    png_path = output_base + ".png"
    canvas.save(png_path, "PNG", optimize=True)
    print(f"Generated High-Res PNG: {png_path} ({total_w}x{total_h}px)")

    # Save PDF
    pdf_path = output_base + ".pdf"
    # Convert RGB canvas to PDF
    canvas.save(pdf_path, "PDF", resolution=150.0)
    print(f"Generated High-Res PDF: {pdf_path}")
    
    return png_path, pdf_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a PNG + PDF contact sheet from slate preview PNGs.")
    ap.add_argument("previews_dir")
    ap.add_argument("template", nargs="?", default="", help="slate sheet (.xlsx) for order and metadata")
    ap.add_argument("output_base", nargs="?", default="", help="output path without extension")
    ap.add_argument("--client", default="")
    ap.add_argument("--agency", default="")
    ap.add_argument("--workspace", default="")
    ap.add_argument("--campaign", default="")
    ap.add_argument("--date", default="")
    a = ap.parse_args(argv)
    output_base = a.output_base or os.path.join(os.path.dirname(os.path.abspath(a.previews_dir)), "Slates_Contact_Sheet")
    result = generate_contact_sheet(a.previews_dir, a.template, output_base, client=a.client, agency=a.agency,
                                    workspace=a.workspace, campaign=a.campaign, date=a.date)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
