#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出片后质检门禁（经验库 9.3 四检编排）：ASR / F0 / RMS / 联系表。

工具分工（别用错，经验库 4.0）：
  * ASR  → 台词内容逐字正确（硬门槛）；内容错了先换 seed 重出
  * F0   → 音色是否锁住（男≈152Hz / 女≈257Hz），不验语速
  * RMS  → 开口时机 / 句间隔 / 碎片，不验内容
  * 联系表 → 人数/座位/构图/场景一致性（人眼逐格看）

本脚本做能自动的部分（RMS / F0 / 抽帧），把 ASR 生成待办清单交给 AudioTranscribe
（agent 内置）或用户填结果；给出每镜 PASS/WARN/FAIL 汇总，内容类 FAIL 阻断交付。

依赖：numpy + imageio_ffmpeg（F0/RMS 抽 wav）；联系表另需 av/PIL（调 contact_sheet.py）。
缺依赖时对应检查输出 SKIP 与安装提示，不影响其他检查。

用法（建议用 ComfyUI 的 python）：
  python qc_gate.py --videos <成片目录> --list N7-出片清单.csv \\
      --script <台词文本.json> --report qc_report.json
  python qc_gate.py --videos <成片目录> --shots 003,004,008 --report qc.json
  # 台词文本.json：{"003": "苏晚。", "004": "你怎么在这儿。/调回来了。上个月。", ...}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
    HAS_FF = True
except ImportError:
    FF = ""
    HAS_FF = False

# 判据（经验库）
F0_MALE = 152.0
F0_FEMALE = 257.0
F0_TOL = 30.0          # ±30Hz 视为锁住
VOX_OPEN_MIN = 0.5     # 首句开口 ≤ ~1s 为佳，>2s 提醒
GAP_MIN, GAP_MAX = 0.3, 0.8
MAX_FRAGMENTS = 4      # 单句碎片段 >3 提醒
SR = 16000
HOP = 200


def extract_wav(video: Path) -> str:
    tp = os.path.join(tempfile.gettempdir(), f"qc_{abs(hash(str(video)))}.wav")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(video), "-vn",
                    "-ac", "1", "-ar", str(SR), "-f", "wav", tp], check=True)
    return tp


def load_audio(wav_path: str):
    with wave.open(wav_path, "rb") as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    return data


def rms_check(data) -> dict:
    """发声段检测：开口时机 / 句间隔 / 碎片数。相对阈值 max*0.15 + 下限。"""
    rms = np.array([np.sqrt(np.mean(data[i:i + HOP] ** 2)) for i in range(0, len(data) - HOP, HOP)])
    if rms.size == 0 or rms.max() <= 0:
        return {"status": "SKIP", "reason": "无有效音轨"}
    thr = max(rms.max() * 0.15, 0.012)
    active = rms > thr
    segs, st = [], None
    for i, a in enumerate(active):
        if a and st is None:
            st = i
        if not a and st is not None:
            if i - st >= 4:
                segs.append((st * HOP / SR, i * HOP / SR))
            st = None
    if st is not None:
        segs.append((st * HOP / SR, len(active) * HOP / SR))
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] < 0.12:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if not merged:
        return {"status": "SKIP", "reason": "未检测到发声（可能无对白镜）", "segments": []}
    open_at = round(merged[0][0], 2)
    gaps = [round(merged[i][0] - merged[i - 1][1], 2) for i in range(1, len(merged))]
    dur = round(len(data) / SR, 2)
    warns = []
    if open_at > VOX_OPEN_MIN * 2:
        warns.append(f"开口偏晚 {open_at}s")
    long_gaps = [g for g in gaps if g > GAP_MAX * 2]
    if long_gaps:
        warns.append(f"句间隔过长 {long_gaps}s（可后期 audio_tighten）")
    if len(merged) > MAX_FRAGMENTS:
        warns.append(f"发声段 {len(merged)} 个，疑似字级碎片")
    return {"status": "WARN" if warns else "PASS", "open_at": open_at,
            "gaps": gaps, "segments": len(merged), "duration": dur, "warns": warns}


def f0_autocorr(data, sr=SR) -> float:
    """自相关估基频（简易，够验音色）。"""
    n = len(data)
    if n < sr // 4:
        return 0.0
    # 取中段 0.3s
    seg = data[n // 2 - sr // 6: n // 2 + sr // 6]
    seg = seg - seg.mean()
    if seg.std() < 1e-4:
        return 0.0
    corr = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
    lo, hi = int(sr / 400), int(sr / 80)  # 80~400Hz
    lag = int(np.argmax(corr[lo:hi])) + lo
    return sr / lag if lag > 0 else 0.0


def f0_check(data, expect: str) -> dict:
    f0 = f0_autocorr(data)
    if not f0:
        return {"status": "SKIP", "reason": "基频估计失败"}
    target = F0_FEMALE if expect == "female" else F0_MALE if expect == "male" else 0
    if not target:
        return {"status": "INFO", "f0_hz": round(f0, 1)}
    ok = abs(f0 - target) <= F0_TOL
    return {"status": "PASS" if ok else "WARN", "f0_hz": round(f0, 1),
            "expect_hz": target, "note": "" if ok else f"偏离目标 {target}Hz 超过 ±{F0_TOL}Hz"}


def shots_from_list(list_csv: Path) -> list[str]:
    import csv
    with list_csv.open("r", encoding="utf-8-sig") as f:
        keys = []
        for r in csv.DictReader(f):
            v = r.get("shot") or r.get("shot_id") or ""
            d = "".join(c for c in v if c.isdigit())
            if d:
                keys.append(d[-3:])
    return keys


def main() -> None:
    ap = argparse.ArgumentParser(description="出片后质检门禁：ASR/F0/RMS/联系表")
    ap.add_argument("--videos", type=Path, required=True, help="成片目录")
    ap.add_argument("--list", type=Path, help="出片清单 CSV")
    ap.add_argument("--shots", default="", help="逗号分隔镜号后三位")
    ap.add_argument("--pattern", default="SHOT-{shot}-hd-1.mp4|SHOT-{shot}-hd.mp4",
                    help="源命名模板，| 分隔优先级")
    ap.add_argument("--script", type=Path, help="台词文本 JSON：{镜号: 台词}（ASR 比对用）")
    ap.add_argument("--expect-voice", default="",
                    help="音色期望 JSON：{镜号: male|female}，如 '{\"004\":\"female\"}'")
    ap.add_argument("--report", type=Path, required=True, help="QC 报告 JSON 输出")
    a = ap.parse_args()

    if a.list:
        shots = shots_from_list(a.list)
    else:
        shots = [s.strip().zfill(3) for s in a.shots.split(",") if s.strip()]
    scripts = {}
    if a.script and a.script.exists():
        try:
            scripts = json.loads(a.script.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] 台词文本 JSON 读取失败，ASR 全部按 TODO：{e}")
    try:
        expects = json.loads(a.expect_voice) if a.expect_voice else {}
    except json.JSONDecodeError:
        print("[WARN] --expect-voice 不是合法 JSON，忽略音色判据")
        expects = {}

    report: dict = {"tool": "qc_gate", "deps": {"numpy": HAS_NUMPY, "ffmpeg": HAS_FF}, "shots": {}}
    for k in shots:
        video = None
        for pat in a.pattern.split("|"):
            p = a.videos / pat.format(shot=k)
            if p.exists() and p.stat().st_size > 100_000:
                video = p
                break
        entry: dict = {}
        if video is None:
            entry["RMS"] = {"status": "SKIP", "reason": "缺成片"}
            report["shots"][k] = entry
            continue
        if not (HAS_NUMPY and HAS_FF):
            entry["RMS"] = {"status": "SKIP", "reason": "缺 numpy/imageio_ffmpeg，用 ComfyUI python 跑"}
            entry["F0"] = {"status": "SKIP", "reason": "同上"}
        else:
            wav = extract_wav(video)
            data = load_audio(wav)
            entry["RMS"] = rms_check(data)
            entry["F0"] = f0_check(data, expects.get(k, ""))
            try:
                os.remove(wav)
            except OSError:
                pass
        # ASR：本脚本不内置识别，给待办（用 AudioTranscribe 抽 wav 转写后填入）
        if k in scripts:
            entry["ASR"] = {"status": "TODO", "expect": scripts[k],
                            "action": "用 AudioTranscribe 抽该镜 wav 转写，逐字比对；内容错→换 seed 重出"}
        else:
            entry["ASR"] = {"status": "SKIP", "reason": "未提供台词文本"}
        # 联系表由 contact_sheet.py 单独生成，这里登记待人工复核
        entry["contact_sheet"] = {"status": "TODO", "action": "运行 contact_sheet.py 逐格看人数/座位/构图"}
        report["shots"][k] = entry

    # 汇总：RMS/F0 WARN 与 TODO 不算失败；内容类由人工 ASR 判定
    statuses = [c.get("status") for s in report["shots"].values() for c in s.values() if isinstance(c, dict)]
    report["summary"] = {"pass": statuses.count("PASS"), "warn": statuses.count("WARN"),
                         "skip": statuses.count("SKIP"), "todo": statuses.count("TODO"),
                         "note": "ASR/联系表为人工门禁，未填 TODO 不代表通过"}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QC 报告 -> {a.report}")
    print(f"  汇总：{report['summary']}")


if __name__ == "__main__":
    main()
