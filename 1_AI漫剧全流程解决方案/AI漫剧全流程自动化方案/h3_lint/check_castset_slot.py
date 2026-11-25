#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CAST+SET / 四槽顺序 / 景别 / 镜号门禁。

根因依据：经验库 18 章（CSV 装配掏空身份几何、90 处 [Shot N] 全为 1）、
13.3 与出图审片（起始帧缺 CAST+SET 导致校服/白天/半身）、30.7（四槽契约）。

用法：
  python check_castset_slot.py 分镜/视频提示词.md
  python check_castset_slot.py 分镜/视频提示词.md --expect-shots 5 --shot-index-mode group

镜型分档（2026-11-25）：
  DUO 交流镜仍判全身露脚；SOLO / OTS 反应镜豁免半身检查（允许 85mm 特写等，运镜 SKILL「五」节镜型分档）。
  镜型来源优先级：提示词块内 `镜型：SOLO/OTS/DUO` > --solo-shots 显式指定 > --storyboard 分镜.md 解析 > 默认按 DUO 全身判。

退出码：0 = PASS；1 = 缺 CAST/SET、槽位乱、DUO 镜半身景别、镜号不符。
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
SHOTTYPE_RE = re.compile(r"镜型[：:]\s*(SOLO|OTS|DUO)", re.I)


def parse_storyboard_types(path):
    """从分镜.md 解析每镜镜型：## SHOT- 块内 `镜型：SOLO/OTS/DUO`，按出现顺序映射到段号。"""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^##\s+SHOT-", text, flags=re.M)[1:]
    for i, part in enumerate(parts, 1):
        m = SHOTTYPE_RE.search(part)
        if m:
            out[i] = m.group(1).upper()
    return out


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
    ap.add_argument("--storyboard", help="分镜.md 路径：解析块内 `镜型：SOLO/OTS/DUO` 按镜号映射")
    ap.add_argument("--solo-shots", help="显式指定豁免镜段号，逗号分隔如 2,4（优先级最高）")
    args = ap.parse_args()

    if not os.path.isfile(args.prompts):
        print("FAIL: 文件不存在:", args.prompts)
        return 1
    text = open(args.prompts, encoding="utf-8").read()
    blocks = split_blocks(text)
    errors = []
    warnings = []

    sb_types = parse_storyboard_types(getattr(args, "storyboard", None))
    explicit = set()
    if getattr(args, "solo_shots", None):
        explicit = {int(x) for x in re.findall(r"\d+", args.solo_shots)}

    print("提示词镜数:", len(blocks))
    if sb_types:
        print("分镜镜型:", {k: v for k, v in sorted(sb_types.items())})
    print("%-28s %-8s %-8s %-8s %-8s %s" % ("MOTION", "镜型", "槽位", "CAST", "SET", "景别"))

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

        # 镜型解析：--solo-shots > 块内标注 > 分镜.md > 默认 DUO（保守，判全身）
        m_st = SHOTTYPE_RE.search(block)
        if idx in explicit:
            shot_type = "SOLO"
        elif m_st:
            shot_type = m_st.group(1).upper()
        elif sb_types.get(idx):
            shot_type = sb_types[idx]
        else:
            shot_type = ""
        exempt = shot_type in ("SOLO", "OTS")

        half = HALF_BODY.search(dd) or HALF_BODY.search(block)
        if not has_cast:
            errors.append("%s 缺 CAST：subject_definitions 未写年龄+服装，4step/25step 都会漂身份" % short)
        if not has_set:
            errors.append("%s 缺 SET：subject_definitions 未写场景+光向，r2v 会自由生成空间" % short)
        if half and exempt:
            warnings.append("%s 镜型=%s 含半身词 %s —— 按镜型分档豁免（SOLO/OTS 允许特写）" % (short, shot_type, half.group(0)))
        elif half:
            errors.append("%s 半身景别 %s 与全身露脚硬约束冲突（DUO 镜不豁免；若为 SOLO 反应镜请标镜型或用 --solo-shots）" % (short, half.group(0)))
        if not shot_type:
            warnings.append("%s 未标镜型（SOLO/OTS/DUO），按 DUO 全身保守判；SOLO 反应镜请在提示词块或分镜.md 标 `镜型`" % short)

        shot_ns = [int(n) for n in SHOT_N_RE.findall(dd)]
        if args.shot_index_mode == "group" and shot_ns and any(n != idx for n in shot_ns):
            errors.append("%s [Shot N] 镜号错：出现 %s，段号应为 %d" % (short, sorted(set(shot_ns)), idx))
        elif args.shot_index_mode == "single" and shot_ns and any(n != 1 for n in shot_ns):
            warnings.append("%s [Shot N] 非 1（%s），若本段属整组 timeline 请加 --shot-index-mode group" % (short, sorted(set(shot_ns))))

        print("%-28s %-8s %-8s %-8s %-8s %s" % (
            short,
            shot_type or "未标",
            "OK" if orders == [1, 2, 3, 4] else "FAIL",
            "OK" if has_cast else "缺",
            "OK" if has_set else "缺",
            "FAIL" if (half and not exempt) else ("豁免" if half else "OK"),
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
        print("=== PASS：CAST+SET 齐、四槽顺序对、DUO 全身/SOLO 豁免、镜号一致 ===")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
