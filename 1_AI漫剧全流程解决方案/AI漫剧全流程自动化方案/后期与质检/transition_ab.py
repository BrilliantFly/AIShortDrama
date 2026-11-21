#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N10 转场方案 A/B/J-cut 对比样片（实跑 n10_transition_ab.py 参数化版，独立不改动成片）。

同一个接缝做三种衔接，依次播放 + 左上角标签：
  A 0.35s 视音叠化 / B 0.60s 慢叠化 / C J-cut 声音提前 lead 秒进入。
素材：音轨精修版片段（audio_tighten.py 输出）。

用法（用 ComfyUI 的 python 跑，需 av/imageio_ffmpeg）：
  python transition_ab.py --fixed-dir <精修目录> --a 007 --b 008 --out 对比.mp4
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import av
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def src(fixed_dir: Path, k: str) -> Path:
    hits = list(fixed_dir.glob(f"*{k}*音轨精修*.mp4"))
    if not hits:
        raise SystemExit(f"缺精修片段：{fixed_dir} 下找 *{k}*音轨精修*.mp4")
    return hits[0]


def dur(path: Path) -> float:
    c = av.open(str(path))
    st = c.streams.video[0]
    n = st.frames or 0
    rate = float(st.average_rate or 24)
    c.close()
    return n / rate if n else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description="转场方案 A/B/J-cut 对比")
    ap.add_argument("--fixed-dir", type=Path, required=True, help="音轨精修版片段目录")
    ap.add_argument("--a", default="007", help="前镜镜号")
    ap.add_argument("--b", default="008", help="后镜镜号")
    ap.add_argument("--lead", type=float, default=0.35, help="J-cut 声音提前秒")
    ap.add_argument("--va", type=float, default=1.30, help="前镜取尾部时长")
    ap.add_argument("--vb", type=float, default=1.90, help="后镜取头部时长")
    ap.add_argument("--out", type=Path, required=True, help="输出对比 mp4")
    a = ap.parse_args()

    pa, pb = src(a.fixed_dir, a.a), src(a.fixed_dir, a.b)
    da = dur(pa)
    ss = da - a.va
    total = a.va + a.vb
    print(f"接缝 {a.a}→{a.b}  前镜 {da:.2f}s 取 {ss:.2f}~{da:.2f} / 后镜取 0~{a.vb:.2f}")

    variants = [("A  0.35s fade", 0.35, 0.35, 0.0),
                ("B  0.60s slow", 0.60, 0.60, 0.0),
                (f"C  J-cut +{a.lead:.2f}s", 0.20, 0.35 + a.lead, a.lead)]
    fc: list[str] = []
    vlabels, alabels = [], []
    for i, (lbl, vover, aover, lead) in enumerate(variants, 1):
        fc.append(f"[0:v:0]trim=start={ss:.3f}:duration={a.va:.3f},setpts=PTS-STARTPTS,fps=24,scale=672:384,format=yuv420p[va{i}]")
        fc.append(f"[1:v:0]trim=start=0:duration={a.vb:.3f},setpts=PTS-STARTPTS,fps=24,scale=672:384,format=yuv420p[vb{i}]")
        voff = a.va - vover
        fc.append(f"[va{i}][vb{i}]xfade=transition=fade:duration={vover:.3f}:offset={voff:.3f}[vx{i}]")
        fc.append(f"[vx{i}]tpad=stop_mode=clone:stop_duration={vover:.3f}[vxf{i}]")
        safe = lbl.replace(" ", "\\ ").replace(":", "\\:")
        fc.append(f"[vxf{i}]drawtext=text='{safe}':x=16:y=14:fontsize=21:fontcolor=yellow:box=1:boxcolor=black@0.65:boxborderw=6[lv{i}]")
        vlabels.append(f"lv{i}")
        fc.append(f"[0:a:0]atrim=start={ss:.3f}:duration={a.va:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=32000:channel_layouts=stereo[aa{i}]")
        fc.append(f"[1:a:0]atrim=start=0:duration={a.vb:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=32000:channel_layouts=stereo[ab{i}]")
        fc.append(f"[aa{i}][ab{i}]acrossfade=d={aover:.3f}:c1=tri:c2=tri[ax{i}]")
        fc.append(f"[ax{i}]apad=pad_dur={aover+0.2:.3f},atrim=0:{total:.3f}[lax{i}]")
        alabels.append(f"lax{i}")
    fc.append("".join(f"[{v}]" for v in vlabels) + f"concat=n=3:v=1:a=0[V]")
    fc.append("".join(f"[{l}]" for l in alabels) + f"concat=n=3:v=0:a=1[A]")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(pa), "-i", str(pb),
           "-filter_complex", ";".join(fc), "-map", "[V]", "-map", "[A]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "32000", "-movflags", "+faststart",
           "-shortest", str(a.out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ffmpeg 失败:\n", (r.stderr or "")[-2500:])
        return
    print(f"✓ {a.out}  {a.out.stat().st_size/1024/1024:.1f} MB  约 {total*3:.1f}s")


if __name__ == "__main__":
    main()
