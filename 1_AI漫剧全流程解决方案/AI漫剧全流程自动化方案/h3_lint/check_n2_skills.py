#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
N2 三 Skill 协议 —— 防忘门禁（硬检查）

目的：记忆层（MEMORY.md / 经验库 / 手册）是"软约束"，只能让 Agent 知道协议，
      防不了"忘了做导演运镜诊断"。本脚本把"是否执行了诊断"变成脚本可查的硬条件：
      分镜.md 的镜头数 vs 导演运镜诊断段数必须匹配，且必须有全场情绪曲线段。
      缺诊断 → exit 1，交不了 N3。

用法：
  python check_n2_skills.py 分镜/分镜.md
  python check_n2_skills.py 分镜/分镜.md --expect-shots 5
  python check_n2_skills.py 分镜/分镜.md --allow-no-diag   # 仅统计，不失败（迁移旧项目用）

退出码：0 = 门禁通过；1 = 缺诊断/缺曲线/数量不符。
"""
import os
import re
import sys
import argparse

SHOT_RE = re.compile(r"^##\s+SHOT-", re.M)
DIAG_RE = re.compile(r"【导演运镜诊断")
CURVE_RE = re.compile(r"^##\s+全场情绪曲线诊断", re.M)


def parse_shot_blocks(text):
    """返回 [(shot_id, block_text), ...]，按出现顺序。"""
    matches = list(re.finditer(r"^##\s+(SHOT-[^\s]+)[^\n]*$", text, re.M))
    blocks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1), text[m.start():end]))
    return blocks


def main():
    ap = argparse.ArgumentParser(description="N2 三 Skill 协议防忘门禁")
    ap.add_argument("storyboard", help="分镜.md 路径")
    ap.add_argument("--expect-shots", type=int, default=None, help="期望镜头数（可选，给则校验）")
    ap.add_argument("--allow-no-diag", action="store_true", help="只统计不失败（迁移旧项目）")
    args = ap.parse_args()

    if not os.path.isfile(args.storyboard):
        print("FAIL: 文件不存在:", args.storyboard)
        return 1

    text = open(args.storyboard, encoding="utf-8").read()
    blocks = parse_shot_blocks(text)
    n_shots = len(blocks)
    diag_total = len(DIAG_RE.findall(text))
    has_curve = bool(CURVE_RE.search(text))

    print("镜头数:", n_shots)
    print("诊断段数:", diag_total)
    print("全场情绪曲线段:", "有" if has_curve else "缺")
    print()

    errors = []

    # 逐镜检查：每镜块内必须有且仅有一个诊断段
    per_shot = []
    for shot_id, block in blocks:
        c = len(DIAG_RE.findall(block))
        per_shot.append((shot_id, c))
        if c == 0:
            errors.append("%s 缺导演运镜诊断段（导演运镜 Skill 未执行？）" % shot_id)
        elif c > 1:
            errors.append("%s 有 %d 个诊断段（应为 1）" % (shot_id, c))

    if per_shot:
        print("逐镜诊断:")
        for shot_id, c in per_shot:
            print("  %-22s %s" % (shot_id, "OK" if c == 1 else "缺(%d)" % c))
        print()

    if args.expect_shots is not None and n_shots != args.expect_shots:
        errors.append("镜头数 %d != 期望 %d" % (n_shots, args.expect_shots))

    if not has_curve:
        errors.append("缺【全场情绪曲线诊断】段——导演运镜只做了逐镜、没做全场走法判断")

    if diag_total != n_shots:
        errors.append("诊断段总数 %d != 镜头数 %d" % (diag_total, n_shots))

    if errors:
        print("=== 门禁 FAIL ===")
        for e in errors:
            print("  -", e)
        if args.allow_no_diag:
            print("（--allow-no-diag：仅统计，不阻断）")
            return 0
        print("\n→ 交 N3 前必须补齐：对缺诊断的镜头用『导演运镜与机位构图』Skill 逐镜诊断并回写")
        return 1

    print("=== 门禁 PASS：%d 镜全部有诊断 + 全场情绪曲线 ===" % n_shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
