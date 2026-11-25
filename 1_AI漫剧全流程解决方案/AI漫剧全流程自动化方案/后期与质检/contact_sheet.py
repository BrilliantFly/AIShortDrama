#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N8 逐镜巡检联系表（实跑 n8_sheet.py 参数化版）：每镜中点抽帧拼网格，人眼逐格看。

经验库 9.3：人数/座位/构图/场景一致性靠联系表逐格复核（ASR/F0/RMS 之外的图像门禁）。

用法（用 ComfyUI 的 python 跑，需 av/PIL）：
  python contact_sheet.py --videos <成片目录> --list N7-出片清单.csv --out _review.png
  python contact_sheet.py --videos <成片目录> --shots 001,002,003 --per-row 4
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

FONT = os.environ.get("CONTACT_FONT", "msyh.ttc")  # 跨机：默认字体名，或环境变量指定绝对路径


def mid_frame(path: Path) -> Image.Image:
    c = av.open(str(path))
    vs = [s for s in c.streams if s.type == "video"][0]
    want = max(1, int(vs.frames)) // 2
    img = None
    for i, f in enumerate(c.decode(video=0)):
        if i == want:
            img = f.to_image()
            break
    if img is None:
        c.close()
        c = av.open(str(path))
        for f in c.decode(video=0):
            img = f.to_image()
    c.close()
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="逐镜中点抽帧联系表")
    ap.add_argument("--videos", type=Path, required=True, help="成片目录")
    ap.add_argument("--list", type=Path, help="出片清单 CSV（按行取镜号）")
    ap.add_argument("--shots", default="", help="逗号分隔镜号后三位")
    ap.add_argument("--pattern", default="SHOT-{shot}-hd-1.mp4|SHOT-{shot}-hd.mp4",
                    help="源命名模板，| 分隔优先级")
    ap.add_argument("--out", type=Path, required=True, help="输出 PNG")
    ap.add_argument("--per-row", type=int, default=6)
    ap.add_argument("--thumb-w", type=int, default=360)
    a = ap.parse_args()

    if a.list:
        with a.list.open("r", encoding="utf-8-sig") as f:
            keys = []
            for r in csv.DictReader(f):
                v = r.get("shot") or r.get("shot_id") or ""
                d = "".join(c for c in v if c.isdigit())
                if d:
                    keys.append(d[-3:])
    else:
        keys = [s.strip().zfill(3) for s in a.shots.split(",") if s.strip()]

    items = []
    for k in keys:
        hit = None
        for pat in a.pattern.split("|"):
            p = a.videos / pat.format(shot=k)
            if p.exists() and p.stat().st_size > 100_000:
                hit = p
                break
        if hit is None:
            print(f"缺片 SHOT-{k}")
            continue
        items.append((k, hit))
    if not items:
        print("没有可巡检的成片")
        return

    tw = a.thumb_w
    th = int(tw * 9 / 16)
    pad, bar = 8, 26
    cols = a.per_row
    rows_n = (len(items) + cols - 1) // cols
    W = cols * (tw + pad) + pad
    H = rows_n * (th + bar + pad) + pad
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    try:
        f_big = ImageFont.truetype(FONT, 17)
    except Exception:
        f_big = ImageFont.load_default()
    for i, (k, p) in enumerate(items):
        cx, cy = i % cols, i // cols
        x = pad + cx * (tw + pad)
        y = pad + cy * (th + bar + pad)
        try:
            im = mid_frame(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        except Exception as e:
            print(f"抽帧失败 {k}: {e}")
            continue
        sheet.paste(im, (x, y))
        d.text((x + 2, y + th + 3), k, font=f_big, fill=(255, 220, 120))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out, quality=92)
    print(f"联系表 {a.out}  {len(items)} 镜  {W}x{H}")


if __name__ == "__main__":
    main()
