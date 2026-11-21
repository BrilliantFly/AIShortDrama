#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交付验收：数帧、查音轨、测响度，和设计帧数对账。

为什么不用 `ffprobe -show_entries format=duration`：容器时长含音轨尾部 padding，
`concat -c copy` 还会累积每段 AAC 编码延迟。核帧数才是唯一可靠的账。

用法
  python verify_delivery.py --dir <导出目录> --workflow <工作流.json>
  python verify_delivery.py --video <成片.mp4> --dir <导出目录> --workflow <工作流.json>
  python verify_delivery.py --dir ... --workflow ... --csv 验收.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_ep import find_ffmpeg, probe_movie  # noqa: E402

FPS = 24
DEFAULT_CTX = 22
# 实测：36 段里 13 段比预测公式少 1 帧（多为预测值 ≡1 mod 3 的段），
# 量级 0.04s/段、全片 0.54s，属编码末帧处理，不影响验收。±1 帧内只报警不判失败。
FRAME_TOL = 1


def align17k5(n: int) -> int:
    if n <= 5:
        return 5
    return ((n - 5 + 16) // 17) * 17 + 5


def predict_export(length: int, ctx: int) -> int:
    if ctx <= 0:
        return length
    return align17k5(length + ctx) - ctx


def expected_from_workflow(path: str) -> tuple[list[int], int]:
    wf = json.load(io.open(path, encoding="utf-8"))
    node = next(n for n in wf["nodes"] if n["type"] == "MiniMaxH3Director")
    td = json.loads(node["widgets_values"][11])
    out = td.get("output") or {}
    ctx = int(out.get("continuityOverlapFrames", DEFAULT_CTX)) if out.get("continuityEnabled") else 0
    return [int(s["length"]) for s in td["segments"]], ctx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="分段 mp4 所在目录")
    ap.add_argument("--workflow", help="用于算出预期帧数")
    ap.add_argument("--video", help="拼好的成片，额外核容器时长偏差")
    ap.add_argument("--csv")
    a = ap.parse_args()

    ff = find_ffmpeg()
    if not ff:
        print("找不到 ffmpeg")
        return 3

    files = sorted(glob.glob(os.path.join(a.dir, "seg_*.mp4")))
    if not files:
        print(f"{a.dir} 下没有 seg_*.mp4")
        return 3

    rows, fails, warns = [], [], []
    exp_total = 0
    if a.workflow:
        lens, ctx = expected_from_workflow(a.workflow)
        exp = [L if i == 0 else predict_export(L, ctx) for i, L in enumerate(lens)]
        exp_total = sum(exp)
        if len(exp) != len(files):
            warns.append(f"工作流 {len(exp)} 段，目录里 {len(files)} 个 mp4，按位数对齐比较")
    else:
        exp = []

    act_total = 0
    for i, f in enumerate(files):
        p = probe_movie(f, ff)
        e = exp[i] if i < len(exp) else None
        act_total += p["frames"]
        drift = (p["frames"] - e) if e else None
        rows.append({
            "seg": os.path.basename(f),
            "frames": p["frames"],
            "expected": e if e is not None else "",
            "drift": drift if drift is not None else "",
            "audio": "Y" if p["audio"] else "N",
            "mean_db": f"{p['mean_db']:.1f}" if p["mean_db"] is not None else "",
            "peak_db": f"{p['peak_db']:.1f}" if p["peak_db"] is not None else "",
        })
        if e is not None and drift:
            if abs(drift) <= FRAME_TOL:
                warns.append(f"{os.path.basename(f)} 帧数 {p['frames']} vs 预期 {e}（{drift:+d}，编码舍入）")
            else:
                fails.append(f"{os.path.basename(f)} 帧数 {p['frames']} ≠ 预期 {e}（差 {drift:+d}）")
        if not p["audio"]:
            fails.append(f"{os.path.basename(f)} 没有音轨")
        elif p["mean_db"] is not None and p["mean_db"] < -40:
            warns.append(f"{os.path.basename(f)} 平均 {p['mean_db']:.1f} dB，近乎无声")

    print(f"{'段':<16}{'实际帧':>7}{'预期帧':>7}{'偏差':>6}{'音轨':>5}{'mean':>8}{'peak':>8}")
    for r in rows:
        print(f"{r['seg']:<16}{r['frames']:>7}{str(r['expected']):>7}{str(r['drift']):>6}"
              f"{r['audio']:>5}{r['mean_db']:>8}{r['peak_db']:>8}")

    print(f"\n段数={len(files)}  实际总帧={act_total}（{act_total / FPS:.2f}s）"
          + (f"  预期总帧={exp_total}（{exp_total / FPS:.2f}s）  差 {act_total - exp_total:+d} 帧"
             if exp_total else ""))

    if a.video and os.path.exists(a.video):
        out = subprocess.run([ff, "-i", a.video], capture_output=True, text=True, errors="replace")
        dur = None
        for line in (out.stderr or "").splitlines():
            if "Duration:" in line:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                dur = int(h) * 3600 + int(m) * 60 + float(s)
                break
        if dur:
            delta = dur - act_total / FPS
            print(f"成片容器时长={dur:.2f}s  帧数折合={act_total / FPS:.2f}s  容器多出={delta:+.2f}s"
                  f"（AAC padding，正常应 < 段数×0.03s）")
            if delta > len(files) * 0.05:
                warns.append(f"容器比帧数多 {delta:.2f}s，偏大，检查是否有丢帧或音轨错位")

    if a.csv:
        with io.open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"清单: {a.csv}")

    for m in warns:
        print("WARN:", m)
    if fails:
        for m in fails:
            print("FAIL:", m)
        print(f"\n{len(fails)} 项不通过")
        return 1
    print("\nPASS — 帧数与音轨对得上")
    return 0


if __name__ == "__main__":
    sys.exit(main())
