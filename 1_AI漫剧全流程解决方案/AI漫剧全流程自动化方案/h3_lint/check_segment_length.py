#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拆段门禁：检查每段帧长是否越过「长段必漂」安全线，超长须拆段。

根因依据：经验库 28.18/28.19 实测——单段 ≤124 帧身份稳、≥209 帧必漂，
安全线 ≤144 帧（约 6 秒）；超长按 5+17n 拆两段，B 段首帧从 A 段成片
按时间点抽取（人物仍在 + 构图已推进），接缝无跳变，长段漂移可 100% 消除。
另据 28.14：fl2v 尾帧锚定只在 t≈6s 内有效，长段后半段出画也靠拆段治。

检查项：
  1. 段长 > 144 帧 → FAIL（须拆段），并给出建议拆法与 B 段抽帧时间点。
  2. 帧网格必须是 17n 或 5+17n；拆出的子段同样要对齐网格。
  3. duration_sec 与 length_frames / fps 一致（误差 > 0.1s → FAIL）。
  4. 同一 continuity_group 内段长差异过大提示（拼接观感）。

用法：
  python check_segment_length.py shotlist.csv
  python check_segment_length.py shotlist.csv --fps 24 --max-frames 144
  python check_segment_length.py shotlist.csv --allow-long     # 只统计不阻断

退出码：0 = PASS（或有提醒）；1 = 有超长段/网格错/duration 不符。
"""
import os
import sys
import csv
import argparse

GRID_BASE = 17
SAFE_MAX = 144          # 经验库 28.18：124 稳、209 必漂，取 144（约 6s）为安全线
DANGER = 209            # 必漂线，单独标红


def grid_ok(n):
    return n % GRID_BASE == 0 or (n - 5) % GRID_BASE == 0


def nearest_grid(n):
    """返回 <=n 的最大合法网格帧数，及对应的 5+17k 备选。"""
    a = (n // GRID_BASE) * GRID_BASE
    b = 5 + ((n - 5) // GRID_BASE) * GRID_BASE
    return max(a, b if b <= n else 0)


def split_plan(n):
    """给超长段的拆段建议：两段各对齐网格，B 段抽帧时间点按 fps 折算。"""
    half = nearest_grid(n // 2)
    rest = nearest_grid(n - half)
    return half, rest


def main():
    ap = argparse.ArgumentParser(description="拆段门禁：帧长安全线 144 帧")
    ap.add_argument("csv", help="shotlist CSV（需含 length_frames / duration_sec 列）")
    ap.add_argument("--fps", type=float, default=24.0, help="帧率，默认 24（H3 导演台）")
    ap.add_argument("--max-frames", type=int, default=SAFE_MAX, help="单段安全上限帧数，默认 144")
    ap.add_argument("--allow-long", action="store_true", help="只统计不阻断")
    args = ap.parse_args()

    if not os.path.isfile(args.csv):
        print("FAIL: 文件不存在:", args.csv)
        return 1

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("FAIL: CSV 无数据行")
        return 1

    errors = []
    warnings = []
    print("%-10s %-12s %-10s %-10s %-10s %s" % (
        "SHOT", "GROUP", "FRAMES", "SEC", "GRID", "状态"))

    groups = {}
    for r in rows:
        sid = r.get("shot_id", "?").strip()
        grp = r.get("continuity_group", "").strip() or "-"
        try:
            frames = int(float(r.get("length_frames", "0")))
        except (ValueError, TypeError):
            errors.append("%s length_frames 非数字：%r" % (sid, r.get("length_frames")))
            continue
        try:
            dur = float(r.get("duration_sec", "0"))
        except (ValueError, TypeError):
            dur = 0.0

        ok_grid = grid_ok(frames)
        over = frames > args.max_frames
        dur_expected = frames / args.fps
        dur_bad = dur > 0 and abs(dur - dur_expected) > 0.1

        status = "OK"
        if over or not ok_grid or dur_bad:
            status = "FAIL"

        print("%-10s %-12s %-10d %-10.3f %-10s %s" % (
            sid, grp, frames, dur, "OK" if ok_grid else "BAD", status))

        if over:
            a, b = split_plan(frames)
            sec_a = a / args.fps
            tag = "危险(必漂)" if frames >= DANGER else "超安全线"
            errors.append(
                "%s 段长 %d 帧(%.2fs) %s，上限 %d 帧——须拆两段：A=%d 帧 / B=%d 帧；"
                "B 段首帧从 A 段成片 t≈%.1fs 抽（人物仍在 + 构图已推进），勿与 A 同构图"
                % (sid, frames, dur_expected, tag, args.max_frames, a, b, sec_a))
        if not ok_grid:
            errors.append("%s 帧数 %d 不在 17n / 5+17n 网格（建议最近合法值 %d）"
                          % (sid, frames, nearest_grid(frames)))
        if dur_bad:
            errors.append("%s duration_sec=%.3f 与 %d/%g=%.3f 不符" % (
                sid, dur, frames, args.fps, dur_expected))

        groups.setdefault(grp, []).append((sid, frames))

    print()
    for grp, items in groups.items():
        if len(items) > 1:
            fs = [f for _, f in items]
            if max(fs) - min(fs) > 40:
                warnings.append("组 %s 段长差异 %d 帧（%s），拼接观感可能跳变，建议核对"
                                % (grp, max(fs) - min(fs),
                                   ", ".join("%s:%d" % (s, f) for s, f in items)))

    if errors:
        print("=== FAIL %d 项 ===" % len(errors))
        for e in errors:
            print("  -", e)
    if warnings:
        print("=== 提醒 %d 项 ===" % len(warnings))
        for w in warnings:
            print("  -", w)
    if not errors and not warnings:
        print("=== PASS：所有段长 ≤%d 帧、网格合法、duration 一致 ===" % args.max_frames)

    if errors and args.allow_long:
        print("\n（--allow-long：仅统计，不阻断）")
        return 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
