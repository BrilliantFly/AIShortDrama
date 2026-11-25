#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CAST+SET / 四槽顺序 / 景别 / 镜号门禁。

根因依据：经验库 18 章（CSV 装配掏空身份几何、90 处 [Shot N] 全为 1）、
13.3 与出图审片（起始帧缺 CAST+SET 导致校服/白天/半身）、30.7（四槽契约）。

用法：
  python check_castset_slot.py 分镜/视频提示词.md
  python check_castset_slot.py 分镜/视频提示词.md --expect-shots 5 --shot-index-mode group

退出码：0 = PASS；1 = 缺 CAST/SET、槽位乱、半身景别、镜号不符。
"""
import os
import re
import sys
import argparse

MOTION_HEAD = re.compile(r"^##\s+MOTION-[^\s]+.*$", re.M)
ORDER_RE = re.compile(r"顺序[：:]\s*(\d+)")
SHOT_N_RE = re.compile(r"\[Shot\s*(\d+)\]")

CAST_RE = re.compile(r"\d{2}[- ](?:year|yo)|years? old|aged\s*\d|岁", re.I)
CLOTHES_RE = re.compile(
    r"blazer|shirt|cardigan|dress|suit|coat|polo|sweater|trouser|skirt|jacket|"
    r"sneaker|boot|西装|衬衫|开衫|长裙|大衣|校服|毛衣|裤|鞋", re.I
)
SET_RE = re.compile(
    r"corridor|office|room|hall|door|window|wall|floor|stair| terrazzo|"
    r"走廊|办公室|门|窗|墙|地面|楼梯", re.I
)
LIGHT_RE = re.compile(r"warm|cool|lamp|light|glow|暖|冷|灯|光|逆光|轮廓光", re.I)
HALF_BODY = re.compile(r"胸上|腰部以上|半身|chest-up|waist-up|upper[- ]body (?:shot|framing)|half-body", re.I)


def split_blocks(text):
    ms = list(MOTION_HEAD.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append((m.group(0).strip(), text[m.start():end]))
    return out


def line_after(block, prefix):
    m = re.search(r"^-\s*" + re.escape(prefix) + r"[^\n]*$", block, re.M)
    return m.group(0) if m else ""


def section(block, key):
    m = re.search(r"^>\s*" + re.escape(key) + r":\s*(.*(?:\n>\s.*)*)", block, re.M)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser(description="CAST+SET / 四槽 / 景别 / 镜号门禁")
    ap.add_argument("prompts", help="视频提示词.md")
    ap.add_argument("--expect-shots", type=int, default=None)
    ap.add_argument("--shot-index-mode", choices=["single", "group"], default="single",
                    help="single: 每段独立文件 [Shot 1] 合法；group: 整组 timeline，N 必须等于段号")
    args = ap.parse_args()

    if not os.path.isfile(args.prompts):
        print("FAIL: 文件不存在:", args.prompts)
        return 1
    text = open(args.prompts, encoding="utf-8").read()
    blocks = split_blocks(text)
    errors = []
    warnings = []

    print("提示词镜数:", len(blocks))
    print("%-28s %-10s %-10s %-10s %s" % ("MOTION", "槽位", "CAST", "SET", "景别"))

    for idx, (title, block) in enumerate(blocks, 1):
        short = title.replace("## ", "")[:28]
        ref_line = line_after(block, "输入参考图")
        orders = sorted(int(x) for x in ORDER_RE.findall(ref_line))
        if orders != [1, 2, 3, 4]:
            errors.append("%s 四槽顺序异常：%s（应为 1,2,3,4，不增不减）" % (short, orders))

        subj = section(block, "subject_definitions")
        dd = section(block, "detailed_description")
        has_cast = bool(CAST_RE.search(subj) and CLOTHES_RE.search(subj))
        has_set = bool(SET_RE.search(subj) and LIGHT_RE.search(subj))
        half = HALF_BODY.search(dd) or HALF_BODY.search(block)
        if not has_cast:
            errors.append("%s 缺 CAST：subject_definitions 未写年龄+服装，4step/25step 都会漂身份" % short)
        if not has_set:
            errors.append("%s 缺 SET：subject_definitions 未写场景+光向，r2v 会自由生成空间" % short)
        if half:
            errors.append("%s 半身景别 %s 与全身露脚硬约束冲突" % (short, half.group(0)))

        shot_ns = [int(n) for n in SHOT_N_RE.findall(dd)]
        if args.shot_index_mode == "group" and shot_ns and any(n != idx for n in shot_ns):
            errors.append("%s [Shot N] 镜号错：出现 %s，段号应为 %d" % (short, sorted(set(shot_ns)), idx))
        elif args.shot_index_mode == "single" and shot_ns and any(n != 1 for n in shot_ns):
            warnings.append("%s [Shot N] 非 1（%s），若本段属整组 timeline 请加 --shot-index-mode group" % (short, sorted(set(shot_ns))))

        print("%-28s %-10s %-10s %-10s %s" % (
            short,
            "OK" if orders == [1, 2, 3, 4] else "FAIL",
            "OK" if has_cast else "缺",
            "OK" if has_set else "缺",
            "FAIL" if half else "OK",
        ))

    if args.expect_shots is not None and len(blocks) != args.expect_shots:
        errors.append("镜数 %d != 期望 %d" % (len(blocks), args.expect_shots))

    print()
    if errors:
        print("=== FAIL %d 项 ===" % len(errors))
        for e in errors:
            print("  -", e)
    if warnings:
        print("=== 提醒 %d 项 ===" % len(warnings))
        for w in warnings:
            print("  -", w)
    if not errors and not warnings:
        print("=== PASS：CAST+SET 齐、四槽顺序对、全身景别、镜号一致 ===")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
