#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N9 后期音轨精修（实跑 n9_audio_tighten.py 参数化版）：压缩对白镜句间静默。

原理（经验库 4.7）：H3 静默期画面为静止对视、无口型动作 → 剪短静默不穿帮。
只压 >=MIN_GAP 的句间静默到 --gap，入画/句内短停顿/结尾留白不碰；音视频用相同
trim 区间保证同步。相对阈值 max*0.15 + 下限 0.012（抗底噪差异）。

用法（用 ComfyUI 的 python 跑，需 numpy/imageio_ffmpeg）：
  python audio_tighten.py --videos <成片目录> --out <输出目录> --all --gap 0.55
  python audio_tighten.py --videos <成片目录> --out <输出目录> --shot 008 --dry
  python audio_tighten.py --videos <成片目录> --out <输出目录> --shots 003,004,008
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()

# 检测参数（实跑定版）
SR = 16000
HOP = 200
THR_RATIO = 0.15
THR_FLOOR = 0.012
MIN_VOX = 4
MIN_GAP = 0.75


def vox_segments(path: Path) -> tuple[list[tuple[float, float]], float]:
    tp = os.path.join(tempfile.gettempdir(), "h3_audio_tighten_vox.wav")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(path), "-vn",
                    "-ac", "1", "-ar", str(SR), "-f", "wav", tp], check=True)
    with wave.open(tp, "rb") as w:
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768
    dur = len(data) / SR
    rms = np.array([np.sqrt(np.mean(data[i:i + HOP] ** 2))
                    for i in range(0, len(data) - HOP, HOP)])
    thr = max(rms.max() * THR_RATIO, THR_FLOOR)
    active = rms > thr
    segs: list[tuple[float, float]] = []
    st = None
    for i, a in enumerate(active):
        if a and st is None:
            st = i
        if not a and st is not None:
            if i - st >= MIN_VOX:
                segs.append((st * HOP / SR, i * HOP / SR))
            st = None
    if st is not None:
        segs.append((st * HOP / SR, len(active) * HOP / SR))
    merged: list[tuple[float, float]] = []
    for a, b in segs:
        if merged and a - merged[-1][1] < 0.12:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged, dur


def cut_plan(segs: list[tuple[float, float]], dur: float, keep_gap: float) -> list[tuple[float, float]]:
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for idx, (a, b) in enumerate(segs):
        if idx == 0:
            keep.append((0.0, b))
            cursor = b
            continue
        gap = a - cursor
        if gap >= MIN_GAP:
            keep.append((cursor + keep_gap, b))
        else:
            keep[-1] = (keep[-1][0], b)
        cursor = b
    if keep:
        keep[-1] = (keep[-1][0], dur)
    return keep


def tighten(src: Path, keep: list[tuple[float, float]], dest: Path, dry: bool) -> None:
    cuts = [keep[i][0] - keep[i - 1][1] for i in range(1, len(keep))]
    print(f"  删除 {len(cuts)} 段静默共 {sum(cuts):.2f}s；保留 {len(keep)} 段")
    if dry:
        print("  [dry] 未出片")
        return
    fc = []
    vin, ain = [], []
    for i, (a, b) in enumerate(keep):
        fc.append(f"[0:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS[a{i}]")
        vin.append(f"[v{i}]")
        ain.append(f"[a{i}]")
    fc.append("".join(vin) + f"concat=n={len(keep)}:v=1:a=0[vout]")
    fc.append("".join(ain) + f"concat=n={len(keep)}:v=0:a=1[aout]")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FF, "-y", "-loglevel", "error", "-i", str(src),
           "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "32000", "-movflags", "+faststart", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("  ffmpeg 失败:", (r.stderr or "")[-1200:])
        return
    print(f"  ✓ {dest.name}  {dest.stat().st_size/1024/1024:.1f}MB")


def main() -> None:
    ap = argparse.ArgumentParser(description="后期音轨精修：压缩对白镜句间静默")
    ap.add_argument("--videos", type=Path, required=True, help="成片源目录")
    ap.add_argument("--out", type=Path, required=True, help="精修版输出目录")
    ap.add_argument("--shots", default="", help="逗号分隔镜号（如 003,004）；与 --all 二选一")
    ap.add_argument("--all", action="store_true", help="处理 --talk-shots 列出的全部对白镜")
    ap.add_argument("--talk-shots", default="", help="--all 时的对白镜列表，逗号分隔")
    ap.add_argument("--pattern", default="SHOT-{shot}-hd-1.mp4",
                    help="源文件命名模板，{shot} 占位（默认 SHOT-{shot}-hd-1.mp4）")
    ap.add_argument("--name", default="SHOT-{shot}-hd-音轨精修.mp4", help="输出命名模板")
    ap.add_argument("--gap", type=float, default=0.55, help="句间静默压缩目标秒（默认 0.55）")
    ap.add_argument("--dry", action="store_true", help="只报告裁剪点，不出片")
    a = ap.parse_args()

    if a.all:
        shots = [s.strip() for s in a.talk_shots.split(",") if s.strip()]
        if not shots:
            print("[ERROR] --all 需配 --talk-shots 给出对白镜列表")
            raise SystemExit(2)
    else:
        shots = [s.strip() for s in a.shots.split(",") if s.strip()] or ["008"]

    for shot in shots:
        src = a.videos / a.pattern.format(shot=shot)
        if not src.exists():
            print(f"缺 {src}")
            continue
        print(f"\n=== {src.name} ===")
        segs, dur = vox_segments(src)
        print(f"  dur={dur:.2f}s  发声段 {len(segs)} 个")
        for s, e in segs:
            print(f"    {s:.2f}~{e:.2f} ({e-s:.2f}s)")
        keep = cut_plan(segs, dur, a.gap)
        tighten(src, keep, a.out / a.name.format(shot=shot), a.dry)


if __name__ == "__main__":
    main()
