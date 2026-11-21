# -*- coding: utf-8 -*-
"""
动作切点自动检测 —— 把「人工记时间码」降级为「人工删行+命名」。

做法（纯本地 ffmpeg + numpy，无 AI 模型）：
  1. scdet 滤镜检测镜头切换点（打斗剪辑点）
  2. 8fps 灰度抽样算帧差，得到运动强度曲线（动作密度）
  3. 切点 = 镜头切换点 ∪ 过长段落在低运动谷底处再切
  4. 每段对齐 17n+5 帧网格（H3 控制视频硬约束），输出候选 CSV

它能判定：镜头切点、动作密度高低、段落合理长度。
它不能判定：动作叫什么、朝向哪边、这一招好不好看 —— 这三样仍需人工。

用法：
  python detect_action_cuts.py --src <参考武打片.mp4>
  python detect_action_cuts.py --src x.mp4 --out candidates.csv --thresh 12 --min-len 1.0 --max-len 6.0

产出：
  candidates.csv   直接喂 make_action_clips.py 的 --cuts（label 已预填 候选NN，orient 留空待填）
  candidates.md    逐段运动强度报告，用于判断哪几段值得留
"""
import argparse, csv, io, os, re, subprocess, sys

import numpy as np

FF = r"D:/ComfyUI-aki-v3.2/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
GRID_STEP, GRID_BASE = 17, 5          # H3 帧数网格：17n+5


def probe_duration(src):
    p = subprocess.run([FF, "-hide_banner", "-i", src], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    if not m:
        sys.exit(f"读不到时长：{src}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def scene_times(src, thresh):
    """scdet 检测镜头切换，返回 [(time_s, score), ...]。"""
    cmd = [FF, "-hide_banner", "-nostats", "-i", src, "-an",
           "-vf", f"scdet=threshold={thresh},metadata=mode=print", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = (p.stdout or "") + (p.stderr or "")
    hits, t, score = [], None, None
    for line in out.splitlines():
        m = re.search(r"lavfi\.scd\.time=([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"lavfi\.scd\.score=([\d.]+)", line)
        if m:
            score = float(m.group(1))
            if t is not None:
                hits.append((t, score))
            t = score = None
    return hits


def motion_curve(src, sfps=8, w=96, h=54):
    """低分辨率灰度抽样，返回 (时间数组, 帧差数组 0~1)。"""
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-i", src, "-an",
           "-vf", f"fps={sfps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    fsize = w * h
    buf, frames = b"", []
    while True:
        chunk = p.stdout.read(fsize * 32)
        if not chunk:
            break
        buf += chunk
        while len(buf) >= fsize:
            frames.append(np.frombuffer(buf[:fsize], dtype=np.uint8))
            buf = buf[fsize:]
    p.wait()
    if len(frames) < 2:
        sys.exit("抽样帧数不足，检查源视频")
    arr = np.stack(frames).astype(np.float32)
    diff = np.abs(np.diff(arr, axis=0)).mean(axis=1) / 255.0
    t = np.arange(len(diff)) / sfps
    return t, diff


def snap_frames(sec, fps, min_frames=22):
    """秒 → 最近网格帧数（17n+5，且不小于 min_frames）。"""
    raw = max(sec * fps, min_frames)
    n = int(round((raw - GRID_BASE) / GRID_STEP))
    return max(GRID_BASE, n * GRID_STEP + GRID_BASE)


def build_segments(cuts, dur, mtime, mdiff, min_len, max_len):
    """按镜头切点分段，合并过短段、拆分过长段。"""
    bounds = sorted({0.0, dur, *[c for c in cuts if 0.3 < c < dur - 0.3]})
    segs = [[bounds[i], bounds[i + 1]] for i in range(len(bounds) - 1)]

    def motion(a, b):
        m = (mtime >= a) & (mtime <= b)
        return float(mdiff[m].mean()) if m.any() else 0.0

    # 合并过短段：并入运动更强的一侧
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, (a, b) in enumerate(segs):
            if b - a >= min_len:
                continue
            left = motion(*segs[i - 1]) if i > 0 else -1
            right = motion(*segs[i + 1]) if i < len(segs) - 1 else -1
            if left < 0 and right < 0:
                break
            j = i - 1 if left >= right else i + 1
            lo, hi = min(i, j), max(i, j)
            segs[lo:hi + 1] = [[segs[lo][0], segs[hi][1]]]
            changed = True
            break

    # 拆分过长段：递归在中间区间找运动谷底切，直到全部 ≤ max_len
    out = []
    for a, b in segs:
        out.extend(_split_long(a, b, mtime, mdiff, min_len, max_len))
    return out


def _split_long(a, b, mtime, mdiff, min_len, max_len):
    """递归二分：段长超过 max_len 就在运动谷底切一刀，两半各自继续判断。"""
    if b - a <= max_len:
        return [[a, b]]
    guard = min(min_len, (b - a) / 3)
    lo, hi = a + guard, b - guard
    idx = np.where((mtime >= lo) & (mtime <= hi))[0]
    if len(idx) < 3:
        return [[a, b]]
    k = idx[int(np.argmin(mdiff[idx]))]
    cut = float(mtime[k])
    if cut - a < min_len or b - cut < min_len:
        return [[a, b]]
    return _split_long(a, cut, mtime, mdiff, min_len, max_len) + \
           _split_long(cut, b, mtime, mdiff, min_len, max_len)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="", help="候选 CSV 路径，默认与源片同目录 candidates.csv")
    ap.add_argument("--thresh", type=float, default=12.0, help="镜头切换灵敏度（scdet 0~100，越小越敏感）")
    ap.add_argument("--min-len", type=float, default=1.0, help="最短动作段（秒）")
    ap.add_argument("--max-len", type=float, default=6.0, help="最长动作段（秒），超了在运动谷底再切")
    ap.add_argument("--min-frames", type=int, default=22, help="最短板数（17n+5 网格内）")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()

    dur = probe_duration(a.src)
    print(f"源片 {os.path.basename(a.src)}  时长 {dur:.2f}s")
    hits = scene_times(a.src, a.thresh)
    cuts = [t for t, _ in hits]
    print(f"镜头切点 {len(cuts)} 个：{', '.join(f'{t:.2f}' for t in cuts) or '（无）'}")

    mtime, mdiff = motion_curve(a.src)
    segs = build_segments(cuts, dur, mtime, mdiff, a.min_len, a.max_len)

    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.src)), "candidates.csv")
    rows, report = [], []
    cursor = 0.0                      # 顺序吸附，保证相邻段不重叠
    for i, (s, e) in enumerate(segs, 1):
        s = max(s, cursor)
        if dur - s < a.min_frames / a.fps:
            break                     # 剩余不足最短板数，丢弃
        frames = snap_frames(e - s, a.fps, a.min_frames)
        s = round(s, 2)
        e = round(min(s + frames / a.fps, dur), 2)
        cursor = e
        m = (mtime >= s) & (mtime <= e)
        peak = float(mdiff[m].max()) if m.any() else 0.0
        mean = float(mdiff[m].mean()) if m.any() else 0.0
        level = "高" if mean > 0.045 else ("中" if mean > 0.02 else "低")
        rows.append([f"候选{i:02d}", "", f"{s:.2f}", f"{e:.2f}", ""])
        report.append((i, s, e, frames, mean, peak, level))

    with io.open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "orient", "start", "end", "fx"])
        w.writerows(rows)

    md = os.path.splitext(out)[0] + ".md"
    lines = [f"# 动作切点候选 · {os.path.basename(a.src)}", "",
             f"- 时长 {dur:.2f}s ｜ 镜头切点 {len(cuts)} 个 ｜ 候选 {len(rows)} 段",
             f"- 参数：scdet {a.thresh} / 段长 {a.min_len}~{a.max_len}s / 最短 {a.min_frames} 帧",
             "",
             "| # | 起(s) | 止(s) | 帧数 | 平均运动 | 峰值 | 动作密度 |",
             "|---|---|---|---|---|---|---|"]
    for i, s, e, fr, mean, peak, level in report:
        lines.append(f"| {i:02d} | {s:.2f} | {e:.2f} | {fr} | {mean:.3f} | {peak:.3f} | {level} |")
    lines += ["", "## 接下来",
              "1. 删掉不要的行，给留下的行填 label（动作名）和 orient（正面/侧面/背面）",
              "2. 需要变形就填 fx：mirror / speed:0.5 / reverse，可 + 组合",
              "3. 跑切片：`python make_action_clips.py --src <源片> --cuts <本csv> --out <通用库>`"]
    io.open(md, "w", encoding="utf-8").write("\n".join(lines))

    print(f"\n候选 {len(rows)} 段 → {out}\n报告 → {md}")
    print(f"{'#':<4}{'起':>7}{'止':>8}{'帧数':>5}{'运动':>7}  密度")
    for i, s, e, fr, mean, peak, level in report:
        print(f"{i:<4}{s:>7.2f}{e:>8.2f}{fr:>5}{mean:>7.3f}  {level}")


if __name__ == "__main__":
    main()
