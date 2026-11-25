#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运镜落地体检：检查「分镜导演运镜诊断」是否真的落进「视频提示词」。

背景：三 Skill 协议里导演运镜只回写分镜.md 诊断段，tudou H3 lint 只校验提示词契约。
两者正交（A/B lint 视图字节相同），所以「诊断做了没」有门禁，但「诊断有没有落进提示词」
此前无人检查。本脚本补这一层：逐镜比对诊断的运镜意图与英文 detailed_description 的镜头句。

附带两项同层检查（都是实测返工根因）：
  1. 景别冲突：分镜/提示词写胸上、腰部以上、chest-up、waist-up，与「全身入镜露脚踩地」硬约束打架。
  2. 道具尺度：shallow-focus + 小道具 + 缺 natural size 锚，4step r2v 下会被放大成巨物。

用法：
  python check_camera_landing.py 分镜/分镜.md 分镜/视频提示词.md
  python check_camera_landing.py 分镜/分镜.md 分镜/视频提示词.md --allow-conflict   # 只统计不阻断

退出码：0 = 无冲突（可有提醒）；1 = 有运镜/景别冲突。
"""
import os
import re
import sys
import argparse

SHOT_HEAD = re.compile(r"^##\s+(SHOT-[^\s]+)", re.M)
MOTION_HEAD = re.compile(r"^##\s+(MOTION-[^\s]+)", re.M)
DIAG_START = "【导演运镜诊断"

# 诊断层：想要镜头运动
WANT_PUSH = re.compile(r"缓推|极缓推|缓慢推|推轨|slow push|gentle push|dolly", re.I)
# 诊断层：明确不要运镜（不含「非运镜」「是动作非运镜」这类否定辨析）
WANT_FIXED = re.compile(r"彻底固定|固定中景|不要运镜|机位锁死|代替运镜|相机固定", re.I)
# 提示词层：镜头句
PROMPT_NO_PUSH = re.compile(r"no push|does not move|camera (?:stays |remains )?locked|camera fixed", re.I)
PROMPT_PUSH = re.compile(r"slow push|gentle push|very slow push|dolly (?:in|forward)|push in", re.I)

# 景别冲突（与「全身入镜、露脚/鞋/地面」硬约束相反）
HALF_BODY = re.compile(
    r"胸上|腰部以上|半身|chest-up|waist-up|upper[- ]body (?:shot|framing)|half-body", re.I
)
# 道具尺度风险
SCALE_RISK = re.compile(r"shallow[- ]focus", re.I)
SCALE_GUARD = re.compile(r"natural size|small keychain|at chest level|not enlarged|hand[- ]sized", re.I)


def blocks_from(text, head_re):
    matches = list(head_re.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[m.start():end]))
    return out


def shot_key(shot_id):
    """SHOT-EP001-001 -> EP001-001；用于和 MOTION 对齐。"""
    return shot_id.split("SHOT-", 1)[-1].strip()


def diagnosis_of(shot_block):
    idx = shot_block.find(DIAG_START)
    if idx < 0:
        return ""
    # 诊断段到下一个二级标题为止（末镜后面可能还有「全场情绪曲线」「审片清单」）
    rest = shot_block[idx:]
    m = re.search(r"^##\s+", rest, re.M)
    return rest[:m.start()] if m else rest


def detailed_of(motion_block):
    m = re.search(r"^>\s*detailed_description:\s*(.+)$", motion_block, re.M)
    return m.group(1) if m else ""


def motion_shot_id(motion_block):
    m = re.search(r"^-\s*分镜[：:]\s*(SHOT-[^\s]+)", motion_block, re.M)
    if m:
        return m.group(1)
    m = re.search(r"(SHOT-[A-Za-z0-9-]+)", motion_block)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser(description="运镜落地体检（诊断 vs 提示词）")
    ap.add_argument("storyboard", help="分镜.md")
    ap.add_argument("prompts", help="视频提示词.md")
    ap.add_argument("--allow-conflict", action="store_true", help="只统计不阻断")
    args = ap.parse_args()

    for p in (args.storyboard, args.prompts):
        if not os.path.isfile(p):
            print("FAIL: 文件不存在:", p)
            return 1

    sb = open(args.storyboard, encoding="utf-8").read()
    pb = open(args.prompts, encoding="utf-8").read()

    shots = dict((shot_key(sid), text) for sid, text in blocks_from(sb, SHOT_HEAD))
    motions = blocks_from(pb, MOTION_HEAD)

    errors = []
    warnings = []
    rows = []

    for mid, block in motions:
        sid = motion_shot_id(block)
        key = shot_key(sid) if sid else ""
        diag = diagnosis_of(shots.get(key, ""))
        dd = detailed_of(block)
        cam = "n/a"

        if not diag:
            errors.append("%s 分镜缺诊断段，无法比对" % mid)
        else:
            want_push = bool(WANT_PUSH.search(diag))
            want_fixed = bool(WANT_FIXED.search(diag))
            if want_push and want_fixed:
                warnings.append("%s 诊断同时出现「推」与「固定」表述，需人工消歧" % mid)
            prompt_no = bool(PROMPT_NO_PUSH.search(dd))
            prompt_push = bool(PROMPT_PUSH.search(dd))

            if want_push and not want_fixed:
                cam = "诊断=缓推"
                if prompt_no and not prompt_push:
                    errors.append("%s 运镜冲突：诊断要求缓推，提示词写 no push / locked / does not move" % mid)
                elif not prompt_push:
                    errors.append("%s 运镜未落地：诊断要求缓推，提示词没有 slow push / dolly 镜头句" % mid)
            elif want_fixed:
                cam = "诊断=固定"
                if prompt_push:
                    errors.append("%s 运镜冲突：诊断要求固定，提示词却出现推轨镜头句" % mid)
                elif not prompt_no:
                    warnings.append("%s 诊断要求固定，提示词未明写 no push / locked" % mid)
            else:
                cam = "诊断=未定"
                warnings.append("%s 诊断没给出明确运镜意图（推或固定）" % mid)

        # 景别：提示词侧
        framed = HALF_BODY.findall(dd)
        if framed:
            errors.append("%s 景别冲突：提示词写 %s，与全身露脚踩地硬约束相反" % (mid, "/".join(sorted(set(framed)))))
        # 景别：分镜侧
        if key and key in shots:
            sb_framed = HALF_BODY.findall(shots[key])
            if sb_framed:
                errors.append("%s 景别冲突：分镜出场设定写 %s（起始帧已是全身）" % (mid, "/".join(sorted(set(sb_framed)))))

        # 道具尺度
        if SCALE_RISK.search(dd) and re.search(r"keychain|道具|prop", dd, re.I) and not SCALE_GUARD.search(dd):
            warnings.append("%s 道具尺度风险：shallow-focus 写小道具但缺 natural size 锚（4step 会放大）" % mid)

        rows.append((mid, sid or "-", cam, "OK" if not any(mid in e for e in errors + warnings) else "见下"))

    print("分镜镜数: %d   提示词镜数: %d" % (len(shots), len(motions)))
    print()
    print("%-24s %-18s %-14s %s" % ("MOTION", "SHOT", "诊断运镜意图", "状态"))
    for r in rows:
        print("%-24s %-18s %-14s %s" % r)
    print()

    if errors:
        print("=== 冲突 %d 项 ===" % len(errors))
        for e in errors:
            print("  -", e)
    if warnings:
        print("=== 提醒 %d 项 ===" % len(warnings))
        for w in warnings:
            print("  -", w)
    if not errors and not warnings:
        print("=== 无冲突：诊断已落地为提示词镜头句 ===")

    if errors and not args.allow_conflict:
        print("\n→ 交 N10 前须回写视频提示词：缓推镜补 slow push 镜头句；半身表述改 full-body / head to shoes。")
        return 1
    if errors:
        print("\n（--allow-conflict：仅统计，不阻断）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
