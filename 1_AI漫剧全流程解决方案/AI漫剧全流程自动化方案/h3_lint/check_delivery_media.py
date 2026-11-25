#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成片交付门禁：段数、时长、分辨率、码率、尾段误交。

根因依据：经验库 1.2「产物成对，分段版优先」——导演台 SaveVideo 归档版只落最后一段
（时长≈末段、码率偏低、文件小），正片必须取 seg_*.mp4，归档整片不可单独交付。

用法（ffprobe 可选，缺失时只做段数与文件级检查）：
  python check_delivery_media.py out/seg_*.mp4
  python check_delivery_media.py out/seg_*.mp4 --archive out/整片.mp4 --expect 5
  python check_delivery_media.py out/seg_*.mp4 --width 1344 --height 768 --min-bitrate 1000

退出码：0 = PASS；1 = 段数/规格不符或整片疑似只含尾段。
"""
import os
import sys
import json
import shutil
import subprocess
import argparse


def probe(path, ffprobe=None):
    ff = ffprobe or shutil.which("ffprobe")
    if not ff:
        return None
    cmd = [ff, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate,bit_rate:format=duration,bit_rate",
           "-of", "json", path]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=30)
        d = json.loads(out.decode("utf-8", "replace"))
        st = (d.get("streams") or [{}])[0]
        fm = d.get("format") or {}
        bit = st.get("bit_rate") or fm.get("bit_rate") or 0
        return {
            "w": st.get("width"), "h": st.get("height"),
            "fps": st.get("r_frame_rate"),
            "kbps": round(int(bit) / 1000) if str(bit).isdigit() else 0,
            "dur": round(float(fm.get("duration", 0)), 2),
        }
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="成片交付门禁")
    ap.add_argument("segs", nargs="+", help="分段 mp4（支持通配符）")
    ap.add_argument("--archive", help="导演台归档整片 mp4（可选）")
    ap.add_argument("--expect", type=int, default=None, help="期望段数")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--min-bitrate", type=int, default=None, help="最低码率 kbps")
    ap.add_argument("--ffprobe", default=None, help="ffprobe 可执行文件路径（不在 PATH 时手填）")
    args = ap.parse_args()

    segs = [p for p in args.segs if os.path.isfile(p)]
    errors = []
    warnings = []
    print("分段数:", len(segs))
    if not segs:
        print("FAIL: 没有可读分段文件")
        return 1

    if args.expect is not None and len(segs) != args.expect:
        errors.append("分段数 %d != 期望 %d" % (len(segs), args.expect))

    infos = []
    for p in sorted(segs):
        info = probe(p, args.ffprobe)
        infos.append((p, info))
        if info is None:
            warnings.append("%s 无法探测（ffprobe 不可用或损坏），只做文件级检查" % os.path.basename(p))
        else:
            print("  %-40s %sx%s  %s  %dkbps  %.2fs" % (
                os.path.basename(p), info["w"], info["h"], info["fps"], info["kbps"], info["dur"]))
            if args.width and info["w"] != args.width:
                errors.append("%s 宽度 %s != %d" % (os.path.basename(p), info["w"], args.width))
            if args.height and info["h"] != args.height:
                errors.append("%s 高度 %s != %d" % (os.path.basename(p), info["h"], args.height))
            if args.min_bitrate and info["kbps"] and info["kbps"] < args.min_bitrate:
                errors.append("%s 码率 %d < %dkbps" % (os.path.basename(p), info["kbps"], args.min_bitrate))

    if args.archive and os.path.isfile(args.archive):
        ai = probe(args.archive, args.ffprobe)
        last = infos[-1][1] if infos else None
        if ai and last:
            print("归档整片: %.2fs %dkbps  末段: %.2fs %dkbps" % (
                ai["dur"], ai["kbps"], last["dur"], last["kbps"]))
            if len(segs) > 1 and abs(ai["dur"] - last["dur"]) < max(0.3, last["dur"] * 0.05):
                errors.append("归档整片时长≈末段（%.2f vs %.2f）——SaveVideo 只落尾段，正片必须取分段版" % (
                    ai["dur"], last["dur"]))
        else:
            warnings.append("归档整片无法探测，未做尾段误交检查")

    print()
    if errors:
        print("=== FAIL %d 项 ===" % len(errors))
        for e in errors:
            print("  -", e)
    if warnings:
        print("=== 提醒 %d 项 ===" % len(warnings))
        for w in warnings:
            print("  -", w)
    if not errors and not warnings:
        print("=== PASS：段数/规格/归档均符合交付契约 ===")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
