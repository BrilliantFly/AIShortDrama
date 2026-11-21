# -*- coding: utf-8 -*-
"""
动作素材库切片脚本 —— 把参考武打片切成对齐 H3 约束的动作单元。

输出约束（喂给 H3 FunControlNetUnion 前就到位）：
  - 帧数对齐 17n+5 网格（24fps：5/22/39/56/73/90/107/124 帧）
  - 分辨率对齐 32 的倍数，长边不超 1344x768 框
  - 统一 24fps、去音轨（控制视频只承担动作）

用法：
  python make_action_clips.py --src <参考武打片.mp4> --cuts cuts.csv --out <输出目录>

cuts.csv 每行一个切片（首行为表头）：
  label,orient,start,end,fx
  拔刀突进,正面,0.0,3.2,
  格挡相击,侧面,8.5,11.8,mirror
  重劈,侧面,20.0,22.0,speed:0.5
  回刀,正面,25.0,26.5,reverse
  连招,侧面,12.0,16.0,mirror+speed:0.5

fx 可组合（+ 连接）：mirror = 镜像翻转；speed:x = x 倍速（0.5 慢放/2 快放）；reverse = 倒放。
"""
import argparse, csv, io, os, subprocess, sys

FF = r"D:/ComfyUI-aki-v3.2/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"

def snap_frames(sec, fps=24):
    """秒 → 最近的 17n+5 帧数（>=5）。"""
    raw = max(1, round(sec * fps))
    n = max(0, (raw - 5 + 8) // 17)   # 四舍五入到最近网格
    return n * 17 + 5

def build_filter(fx, fps, maxw, maxh):
    """fx 顺序：变速先于帧处理，镜像/倒放作用于帧序列。"""
    parts = [f"fps={fps}",
             f"scale={maxw}:{maxh}:force_original_aspect_ratio=decrease",
             f"crop=trunc(iw/32)*32:trunc(ih/32)*32"]
    speed = 1.0
    rev = mirror = False
    for tok in [t for t in (fx or "").split("+") if t.strip()]:
        tok = tok.strip()
        if tok == "mirror": mirror = True
        elif tok == "reverse": rev = True
        elif tok.startswith("speed:"): speed = float(tok.split(":")[1])
        else: sys.exit(f"未知 fx: {tok}")
    if speed != 1.0:
        parts.append(f"setpts=PTS/{speed}")
        parts.append(f"fps={fps}")          # 重采样回 24fps
    if rev: parts.append("reverse")
    if mirror: parts.append("hflip")
    return parts, speed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--cuts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--maxw", type=int, default=1344)
    ap.add_argument("--maxh", type=int, default=768)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows = list(csv.DictReader(io.open(a.cuts, encoding="utf-8-sig")))
    manifest = ["filename,source,label,orient,start_s,end_s,fx,frames,duration_s,size"]
    print(f"{'切片':<34}{'帧数':>5}  {'时长':>6}  分辨率")
    for i, r in enumerate(rows, 1):
        label, orient = r["label"].strip(), r["orient"].strip()
        s, e = float(r["start"]), float(r["end"])
        fx = r.get("fx", "").strip()
        _, speed = build_filter(fx, a.fps, a.maxw, a.maxh)
        frames = snap_frames((e - s) / speed, a.fps)
        fxtag = ("_" + fx.replace(":", "").replace("+", "-")) if fx else ""

        # 先探测最终分辨率（探测流跑一遍缩放链）
        probe = [FF, "-hide_banner", "-loglevel", "error", "-ss", str(s), "-to", str(e),
                 "-i", a.src, "-vf", ",".join(build_filter(fx, a.fps, a.maxw, a.maxh)[0]),
                 "-frames:v", "1", "-f", "null", "-"]
        subprocess.run(probe, check=True, capture_output=True)
        # 从 ffmpeg 选一遍最终宽高：用 filter 直接输出到 null 并解析不现实，改用 ffprobe 式计算
        # 简化：用 show_frames 太重，直接解析 crop 后结果由第二次 run 的 -s 无法得知；
        # 改为让编码输出后由 ffmpeg 自报。这里选择先跑一遍真实编码，再读产物头。
        name = f"ACT{i:03d}_{label}_{orient}_{s:g}-{e:g}s_{frames}f{fxtag}.mp4"
        dst = os.path.join(a.out, name)
        vf = ",".join(build_filter(fx, a.fps, a.maxw, a.maxh)[0])
        cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
               "-ss", str(s), "-to", str(e), "-i", a.src,
               "-vf", vf, "-frames:v", str(frames),
               "-an", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
               "-pix_fmt", "yuv420p", dst]
        subprocess.run(cmd, check=True)

        size = os.path.getsize(dst)
        # 读产物实际宽高与帧数
        p = subprocess.run([FF, "-hide_banner", "-i", dst], capture_output=True, text=True,
                           encoding="utf-8", errors="ignore")
        import re
        m = re.search(r"(\d{2,5})x(\d{2,5})", p.stderr)
        w, h = (m.group(1), m.group(2)) if m else ("?", "?")
        print(f"{name:<40}{frames:>4}f {frames/a.fps:>5.2f}s  {w}x{h}  {size//1024}KB")
        manifest.append(f"{name},{os.path.basename(a.src)},{label},{orient},{s},{e},{fx},{frames},{frames/a.fps:.2f},{w}x{h}")

    idx = os.path.join(a.out, "索引.csv")
    io.open(idx, "w", encoding="utf-8-sig").write("\n".join(manifest))
    print(f"\n完成 {len(rows)} 个切片 → {a.out}\n索引：{idx}")

if __name__ == "__main__":
    main()
