#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N14 转场拼接（实跑 n8_concat_xfade.py 参数化版）：xfade 叠化 + acrossfade 音频交叉。

经验库 2.5：实跑最终选「每镜独立出片 → ffmpeg xfade 叠化」，不要试图让 ComfyUI
跑转场。av 精确读帧算 offset；音轨精修版优先（--audio-fix，配 audio_tighten.py）。

用法（用 ComfyUI 的 python 跑，需 av/imageio_ffmpeg）：
  python concat_xfade.py --videos <成片目录> --shots 001,002,003 --out X.mp4
  python concat_xfade.py --videos <成片目录> --list N7-出片清单.csv --transition 0.35
  python concat_xfade.py --videos <成片目录> --list N7-出片清单.csv --audio-fix \\
      --fixed-dir <音轨精修目录> --out 全片.mp4
"""
from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path

import av
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def pick(shot: str, videos: Path, pattern: str, fixed_dir: Path | None) -> Path | None:
    # 音轨精修版优先
    if fixed_dir:
        for p in sorted(fixed_dir.glob(f"*{shot}*音轨精修*.mp4")):
            if p.exists() and p.stat().st_size > 100_000:
                return p
    for pat in pattern.split("|"):
        p = videos / pat.format(shot=shot)
        if p.exists() and p.stat().st_size > 100_000:
            return p
    hits = sorted(videos.glob(f"*{shot}*.mp4"))
    return hits[0] if hits else None


def duration_of(path: Path, fps: int) -> float:
    c = av.open(str(path))
    st = c.streams.video[0]
    n = st.frames or 0
    rate = float(st.average_rate or fps)
    c.close()
    if n:
        return n / rate
    return path.stat().st_size / 1000


def build_filter(files: list[Path], durs: list[float], fps: int, t: float) -> tuple[str, str, str, float]:
    n = len(files)
    fc: list[str] = []
    for i in range(n):
        fc.append(f"[{i}:v:0]setpts=PTS-STARTPTS,fps={fps},format=yuv420p[v{i}]")
        fc.append(f"[{i}:a:0]aformat=sample_rates=32000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
    acc = durs[0]
    vprev = "v0"
    for i in range(1, n):
        off = acc - t
        vout = f"vx{i}"
        fc.append(f"[{vprev}][v{i}]xfade=transition=fade:duration={t:.4f}:offset={off:.4f}[{vout}]")
        vprev = vout
        acc += durs[i] - t
    acc = durs[0]
    aprev = "a0"
    for i in range(1, n):
        aout = f"ax{i}"
        fc.append(f"[{aprev}][a{i}]acrossfade=d={t:.4f}:c1=tri:c2=tri[{aout}]")
        aprev = aout
        acc += durs[i] - t
    return ";".join(fc), vprev, aprev, acc


def shots_from_list(list_csv: Path) -> list[str]:
    with list_csv.open("r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    keys = []
    for r in rows:
        v = r.get("shot") or r.get("shot_id") or ""
        digits = "".join(c for c in v if c.isdigit())
        if digits:
            keys.append(digits[-3:])
    return keys


def main() -> None:
    ap = argparse.ArgumentParser(description="xfade 叠化拼接整片")
    ap.add_argument("--videos", type=Path, required=True, help="成片源目录")
    ap.add_argument("--shots", default="", help="逗号分隔镜号后三位；与 --list 二选一")
    ap.add_argument("--list", type=Path, help="出片清单 CSV（按行顺序取镜号）")
    ap.add_argument("--pattern", default="SHOT-{shot}-hd-1.mp4|SHOT-{shot}-hd.mp4|SHOT-{shot}-hd-2.mp4",
                    help="源命名模板，| 分隔优先级，{shot} 占位")
    ap.add_argument("--audio-fix", action="store_true", help="优先用音轨精修版")
    ap.add_argument("--fixed-dir", type=Path, help="音轨精修版目录（--audio-fix 时用）")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--transition", type=float, default=0.35, help="叠化秒数")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--out", type=Path, required=True, help="输出 mp4")
    a = ap.parse_args()

    if a.list:
        keys = shots_from_list(a.list)
    else:
        keys = [s.strip().zfill(3) for s in a.shots.split(",") if s.strip()]
    if not keys:
        print("没有镜号，退出")
        return
    files, missing = [], []
    for k in keys:
        p = pick(k, a.videos, a.pattern, a.fixed_dir if a.audio_fix else None)
        (files if p else missing).append(p if p else k)
    if missing:
        print(f"缺 {len(missing)} 镜，未拼接：{missing}")
        return
    durs = [duration_of(p, a.fps) for p in files]
    if len(files) == 1:
        fc, vlast, alast, total = "", "0:v", "0:a", durs[0]
    else:
        fc, vlast, alast, total = build_filter(files, durs, a.fps, a.transition)
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for p in files:
        cmd += ["-i", str(p)]
    if fc:
        cmd += ["-filter_complex", fc]
    cmd += ["-map", f"[{vlast}]" if len(files) > 1 else vlast,
            "-map", f"[{alast}]" if len(files) > 1 else alast,
            "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "32000",
            "-movflags", "+faststart", str(a.out)]
    print(f"xfade 拼接 {len(files)} 镜 · 转场 {a.transition}s · 预计 {total:.1f}s"
          f"（硬切 {sum(durs):.1f}s，缩短 {sum(durs)-total:.1f}s）")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ffmpeg 失败：\n", (r.stderr or "")[-2000:])
        return
    print(f"✓ {a.out}  {a.out.stat().st_size/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
