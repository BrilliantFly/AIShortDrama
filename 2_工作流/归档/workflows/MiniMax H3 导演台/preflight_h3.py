#!/usr/bin/env python
"""MiniMax H3 导演台 提交前检查（preflight）。

用法:
    python preflight_h3.py "路径/工作流.json"
    python preflight_h3.py "路径/工作流.json" --input-dir "D:/ComfyUI-aki-v3.2/ComfyUI/input"
    python preflight_h3.py "路径/工作流.json" --audio-detail     # 额外测参考音频响度（慢）

检查项：
  1. 每段 length 落在 17k 网格上；连续性开启时若取 17k+5 会逐段 +12 帧 → FAIL 并给出预测成片帧数
  2. Σ length == totalFrames == 节点 total_frames
  3. 每段「」出现次数 ≤ 1，且不含 <d> 方言
  4. global.prompt 为空
  5. refAudios 无 index 字段、每段 ≤ 1 条
  6. refs/refAudios 指向的文件真实存在
  7. 输出 exportMode 必须为 segments（总帧 > 约 960 时 all 会撞内存墙）
  8. 参考音频采样率一致 / 时长 5~8 秒内 / 峰值不削波
  9. 输出盘剩余空间 ≥ 2 GB
 10. 生成模式是否会让 refAudios 失效：fl2v / i2v / t2v 下 audioMode 被静默降级为 generate，
     段 mp4 音轨必为空 → FAIL（已改用唇形后处理补音轨时加 --accept-silent-segments 降为 WARN）
 11. 段内 taskType 与顶层 task_type 是否不一致（顶层只是界面默认值，实际按段内执行）

任一 FAIL 即退出码 1。
"""
import argparse, glob, io, json, os, re, shutil, subprocess, sys

FPS = 24.0
DEFAULT_CTX = 22          # continuityOverlapFrames 默认值
MAX_FRAMES_FOR_ALL = 960  # exportMode=all 的安全总帧上限（约 40 秒）


def align17k5(n: int) -> int:
    """向上对齐到 MiniMax H3 的 17k+5 帧网格。"""
    n = max(5, int(n))
    while n % 17 != 5:
        n += 1
    return n


def predict_export(length: int, ctx: int) -> int:
    """连续链下的实际导出帧数：align17k5(length + ctx) - ctx。"""
    if ctx <= 0:
        return int(length)
    return max(1, align17k5(int(length) + ctx) - ctx)


def find_key(obj, key, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            find_key(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            find_key(v, key, out)
    return out


_TASK_RE = re.compile(r"^\s*([a-z0-9_]+)")


def task_key(val) -> str:
    """任务名有时是 `r2v — 参考主体生视频(Reference to Video)` 这种带描述的长串，
    只取开头的任务键，避免拿整串去比。"""
    m = _TASK_RE.match(str(val or "").lower())
    return m.group(1) if m else ""


def find_ffmpeg() -> str | None:
    env = os.environ.get("H3_FFMPEG")
    if env and os.path.isfile(env):
        return env
    hit = glob.glob(
        r"D:/ComfyUI-aki-v3.2/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-*.exe"
    )
    if hit:
        return hit[0]
    return shutil.which("ffmpeg")


def probe_audio(path: str, ffmpeg: str) -> dict | None:
    """从 ffmpeg -i 的 stderr 里读采样率 / 声道 / 时长。"""
    try:
        p = subprocess.run([ffmpeg, "-i", path], capture_output=True)
    except OSError:
        return None
    txt = (p.stderr or b"").decode("utf-8", "ignore")
    m_sr = re.search(r"(\d+) Hz, ([a-z0-9 ]+)", txt)
    m_du = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", txt)
    if not m_sr or not m_du:
        return None
    h, mi, se = int(m_du.group(1)), int(m_du.group(2)), float(m_du.group(3))
    return {
        "sr": int(m_sr.group(1)),
        "layout": m_sr.group(2).strip(),
        "dur": h * 3600 + mi * 60 + se,
    }


def probe_loudness(path: str, ffmpeg: str) -> tuple[float, float] | None:
    try:
        p = subprocess.run(
            [ffmpeg, "-i", path, "-af", "volumedetect", "-f", "null", os.devnull],
            capture_output=True,
        )
    except OSError:
        return None
    txt = (p.stderr or b"").decode("utf-8", "ignore")
    m_mean = re.search(r"mean_volume: (-?\d+\.?\d*) dB", txt)
    m_max = re.search(r"max_volume: (-?\d+\.?\d*) dB", txt)
    if not m_mean:
        return None
    return float(m_mean.group(1)), float(m_max.group(1)) if m_max else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--input-dir", default=r"D:/ComfyUI-aki-v3.2/ComfyUI/input")
    ap.add_argument("--audio-detail", action="store_true", help="测参考音频响度（较慢）")
    ap.add_argument("--min-free-gb", type=float, default=2.0)
    ap.add_argument(
        "--accept-silent-segments",
        action="store_true",
        help="已知段音轨为空、改走唇形后处理时，把「模式不产音轨」从 FAIL 降为 WARN",
    )
    a = ap.parse_args()

    wf = json.load(io.open(a.workflow, encoding="utf-8"))
    node = next((n for n in wf["nodes"] if n["type"] == "MiniMaxH3Director"), None)
    if node is None:
        print("FAIL: 工作流里没有 MiniMaxH3Director 节点")
        return 1

    w = node["widgets_values"]
    td = json.loads(w[11]) if isinstance(w[11], str) else w[11]
    segs = td["segments"]
    out_cfg = td.get("output") or {}
    continuity = bool(out_cfg.get("continuityEnabled", False))
    ctx = int(out_cfg.get("continuityOverlapFrames", DEFAULT_CTX)) if continuity else 0

    errs, warns = [], []

    # 1 / 2 帧长网格与总帧：用真公式预测实际成片帧数
    total_design = 0
    total_actual = 0
    bad_grid = []
    for i, s in enumerate(segs):
        L = int(s["length"])
        total_design += L
        # 首段无前文语境
        exp = L if i == 0 else predict_export(L, ctx)
        total_actual += exp
        if L % 17 != (5 - ctx) % 17:
            bad_grid.append((i + 1, L, exp, exp - L))
    if bad_grid:
        drift = total_actual - total_design
        sample = "、".join(f"段{n}({L}→{e})" for n, L, e, _ in bad_grid[:6])
        errs.append(
            f"{len(bad_grid)} 段 length 与 ctx={ctx} 不匹配，每段会多出固定帧：{sample}"
            f"{' 等' if len(bad_grid) > 6 else ''}；"
            f"预测成片 {total_actual} 帧（设计 {total_design} 帧，多 {drift} 帧 = {drift / FPS:.2f}s）。"
            f"取 length 为 17 的倍数即可零漂移"
        )

    if total_design != int(td.get("totalFrames", -1)):
        errs.append(f"timeline.totalFrames={td.get('totalFrames')} ≠ Σlength={total_design}")
    if total_design != int(w[10]):
        errs.append(f"节点 total_frames={w[10]} ≠ Σlength={total_design}")

    # 3 台词体量
    for i, s in enumerate(segs):
        p = s.get("prompt") or ""
        if p.count("「") > 1:
            errs.append(f"段{i+1} 「」出现 {p.count('「')} 次（一镜一句）")
        if "<d>" in p:
            errs.append(f"段{i+1} 用了 <d> 方言（导演台不解析）")

    # 4 全局提示词
    if td.get("global", {}).get("prompt", ""):
        errs.append("global.prompt 非空（批量会被拼进每段，冲淡段内台词）")

    # 5 音频槽位
    # 生成模式决定 refAudios 有没有用：source 只在 r2v/v2v/rv2v 生效，
    # fl2v/i2v/t2v 会被静默降级成 generate，段 mp4 音轨为空（实测峰值 0.000）。
    SILENT_TASKS = {"fl2v", "i2v", "t2v", "first_last_frame", "first_frame", "text"}
    top_task = task_key(w[0] if w else "")
    seg_tasks = {task_key(s.get("taskType") or s.get("task_type")) for s in segs}
    seg_tasks.discard("")
    if top_task and seg_tasks and seg_tasks != {top_task}:
        warns.append(
            f"顶层 task_type={top_task}，段内为 {'/'.join(sorted(seg_tasks))}；"
            f"实际按段内执行，顶层只是界面默认值（别被界面误导）"
        )

    silent_hits: list[tuple[int, str]] = []
    for i, s in enumerate(segs):
        ra = s.get("refAudios") or []
        eff_task = task_key(s.get("taskType") or s.get("task_type")) or top_task
        if len(ra) > 1:
            warns.append(
                f"段{i+1} 挂了 {len(ra)} 条参考音频；执行端实测挂两条时只取一条、"
                f"或两条都不取并退回念提示词描述——一镜一音色最稳，双挂需单独验证"
            )
        for r in ra:
            if "index" in r:
                errs.append(f"段{i+1} refAudios 带 index（0-based 槽位，写了会落空）")
        if ra and eff_task in SILENT_TASKS:
            silent_hits.append((i + 1, eff_task))

    # 10 生成模式让 refAudios 失效（本次最容易白跑的一坑）
    if silent_hits:
        segs_txt = "、".join(str(n) for n, _ in silent_hits[:8]) + (" 等" if len(silent_hits) > 8 else "")
        modes = "/".join(sorted({t for _, t in silent_hits}))
        msg = (
            f"{len(silent_hits)} 段（段{segs_txt}）在 {modes} 模式下挂了 refAudios："
            f"该模式会把 audioMode 静默降级为 generate，refAudios 只当音色条件、不逐字驱动口型，"
            f"这些段的 mp4 音轨必为空（实测峰值 0.000）"
        )
        if a.accept_silent_segments:
            warns.append(msg + "（已声明走唇形后处理）")
        else:
            errs.append(
                msg + "。要音轨改用 r2v/v2v；确实要首尾帧接续就先接受无声，"
                "再按 lip-sync-fallback 做音频驱动唇形后处理，并加 --accept-silent-segments"
            )

    # 6 文件存在
    files = []
    find_key(segs, "imageFile", files)
    find_key(segs, "audioFile", files)
    audio_files = find_key(segs, "audioFile", [])
    miss = []
    for f in files:
        if not f:
            continue
        cand = [os.path.join(a.input_dir, f)]
        if not os.path.splitext(f)[1]:
            cand += glob.glob(os.path.join(a.input_dir, f + ".*"))
        if not any(os.path.exists(c) for c in cand):
            miss.append(f)
    for f in miss:
        errs.append(f"素材缺失: {f}")

    # 7 导出模式
    if out_cfg.get("exportMode") != "segments":
        msg = f"exportMode={out_cfg.get('exportMode')}，建议 segments（每段解码即释放像素）"
        if total_actual > MAX_FRAMES_FOR_ALL:
            errs.append(msg + f"；本片 {total_actual} 帧，合并导出必撞内存墙")
        else:
            warns.append(msg + "；本片帧数尚小，暂不会崩")

    # 8 参考音频技术参数
    uniq_audio = sorted({f for f in audio_files if f})
    if uniq_audio:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            warns.append("找不到 ffmpeg，跳过参考音频参数检查（可设 H3_FFMPEG 环境变量）")
        else:
            srs, seen = {}, []
            for f in uniq_audio:
                path = os.path.join(a.input_dir, f)
                if not os.path.exists(path):
                    continue
                info = probe_audio(path, ffmpeg)
                if not info:
                    warns.append(f"音频无法探测: {f}")
                    continue
                srs.setdefault(info["sr"], []).append(f)
                seen.append((f, info))
                if f.lower().endswith(".wav") and info["dur"] < 4.0:
                    warns.append(f"{f} 仅 {info['dur']:.2f}s，音色克隆偏短（建议 5~8s）")
                if a.audio_detail:
                    ld = probe_loudness(path, ffmpeg)
                    if ld:
                        mean, peak = ld
                        if mean < -26:
                            warns.append(f"{f} 平均响度 {mean:.1f} dB 偏低（建议 ≈ -18 dB）")
                        if peak > -1.0:
                            errs.append(f"{f} 峰值 {peak:.1f} dB 已削波（应 ≤ -3 dBFS）")
            if len(srs) > 1:
                detail = "；".join(f"{sr}Hz: {len(v)}条" for sr, v in sorted(srs.items()))
                errs.append(f"参考音频采样率不统一（{detail}），音色克隆频响基准会漂 —— 先跑 normalize_ref_audio.py")

    # 9 磁盘余量
    try:
        free_gb = shutil.disk_usage(a.input_dir).free / 1e9
        if free_gb < a.min_free_gb:
            errs.append(f"输出盘剩余 {free_gb:.1f} GB < {a.min_free_gb} GB")
    except OSError:
        pass

    print(f"工作流: {os.path.basename(a.workflow)}")
    print(
        f"段数={len(segs)}  设计={total_design}帧/{total_design / FPS:.2f}s  "
        f"实际={total_actual}帧/{total_actual / FPS:.2f}s  ctx={ctx}  素材={len([f for f in files if f])}"
    )
    for m in warns:
        print("WARN:", m)
    if errs:
        for e in errs:
            print("FAIL:", e)
        print(f"\n共 {len(errs)} 项不通过，禁止提交")
        return 1
    print("\nPASS — 可以提交")
    return 0


if __name__ == "__main__":
    sys.exit(main())
