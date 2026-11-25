#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prompt 内容体检门禁：拦住「写对了但没用上」的装配层空模板。

根因依据：经验库 18.1-18.5 实测——《最后一盏灯》15 镜 CSV 六列用了通用模板，
详尽站位/几何从未流入出片底座；视频提示词.md 只是「存档」，不参与装配。
致命 bug：15 镜共 90 处 [Shot N] 全写成 [Shot 1]，等于告诉 H3「15 段都是第 1 镜
的开头」，镜次信息完全丢失；6/15 段作废、白耗 2 小时。

检查项（经验库 18.4 第 5 条「prompt 内容体检」门禁，四条断言）：
  1. [Shot N] 的 N 必须等于该行 shot_id 的镜号（六段式六列全部扫描）。
  2. subject_definitions 的 <Picture 2> 描述 > 80 字符，且不含孤立 on-screen speaker。
  3. detailed_description 含该镜具体动作，不是 "Fixed camera + 台词" 通用模板。
  4. 跨镜 detailed_description 不得完全相同（模板复制的硬特征）。
可选 --prompt-md：若视频提示词.md 的对应镜描述远丰富于 CSV，给「写对了没用上」提醒。

用法：
  python check_prompt_content.py shotlist.csv
  python check_prompt_content.py shotlist.csv --prompt-md 分镜/视频提示词.md
  python check_prompt_content.py shotlist.csv --allow-content      # 只统计不阻断

退出码：0 = PASS（可含提醒）；1 = 有内容 FAIL。
"""
import os
import re
import sys
import csv
import argparse

# 与 csv_to_timeline.py 的 PROMPT_SECTIONS 严格一致（官方 Ref2VA 六段式，顺序不可改）
PROMPT_SECTIONS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]

SHOT_TAG_RE = re.compile(r"\[Shot\s+(\d+)\]", re.I)
PIC2_RE = re.compile(r"<Picture\s*2>(.*?)(?=<Picture\s*\d>|<Subject\s*\d>|$)", re.I | re.S)
REUSE_RE = re.compile(
    r"same (?:identity|as|costume|outfit)|identical to|as (?:defined|above)|see above|above", re.I
)
EMPTY_SPEAKER_RE = re.compile(
    r"^(?:on-screen\s+speaker|speaker|person|subject|character)(?:\s+\w+)?$", re.I
)
# 通用空模板特征（经验库 18.1 ④：detailed_description 只剩 "Fixed camera + 台词 + 环境音"）
VAGUE_DESC_RE = re.compile(
    r"^\s*(?:fixed\s+camera|static\s+camera|locked\s+camera)\s*[+&、,，]\s*(?:台词|dialogue|speech)",
    re.I,
)
VAGUE_ONLY_RE = re.compile(
    r"^\s*(?:establishing\s+frame|scene\s+plate|shot\s+setup)\s+for\s+S?\d+\s*[.。；;]?\s*$", re.I
)
PLACEHOLDER_RE = re.compile(r"\b(?:TBD|TODO|N/?A|generic)\b", re.I)
# 具体动作动词（WARN 用：一个都没有说明疑似只有机位/台词）——覆盖实跑常见的英文动作句
ACTION_VERBS_RE = re.compile(
    r"\b(?:stands?|sits?|walks?|steps?|passes?|turns?|glances?|looks?|reaches?|hands?|"
    r"holds?|picks?|places?|puts?|moves?|leans?|faces?|nods?|shakes?|smiles?|frowns?|"
    r"speaks?|says?|answers?|whispers?|pauses?|stops?|follows?|swings?|crouches?|"
    r"rises?|opens?|closes?|touches?|grabs?|drops?|points?|watches?)\b",
    re.I,
)
SHOT_ID_NUM_RE = re.compile(r"(\d+)\s*$")


def shot_num(sid):
    """从 S004 / SHOT-EP001-004 / 004 提取镜号整数；提取不到返回 None。"""
    m = SHOT_ID_NUM_RE.search((sid or "").strip())
    return int(m.group(1)) if m else None


def pic2_desc(text):
    m = PIC2_RE.search(text or "")
    return (m.group(1) if m else "").strip(" \t\r\n：:；;，,。.")


def norm_text(s):
    return re.sub(r"[\s；;，,。.：:、\-—]", "", s or "").lower()


def load_md_shots(path):
    """读视频提示词.md，返回 {镜号整数: 该镜块文本}；只认 ## SHOT-xxx 标题。"""
    if not path or not os.path.isfile(path):
        return {}
    text = open(path, encoding="utf-8").read()
    chunks = re.split(r"(?m)^##\s+(SHOT-[^\s]+)", text)
    out = {}
    for i in range(1, len(chunks), 2):
        head, body = chunks[i], chunks[i + 1] if i + 1 < len(chunks) else ""
        n = shot_num(head)
        if n is not None:
            out[n] = body
    return out


def main():
    ap = argparse.ArgumentParser(description="prompt 内容体检门禁：按经验库 18.4 四条断言")
    ap.add_argument("csv", help="shotlist CSV（需含 PROMPT_SECTIONS 六列 + shot_id）")
    ap.add_argument("--prompt-md", help="可选：视频提示词.md，用于「写对了没用上」提醒")
    ap.add_argument("--min-pic2", type=int, default=80, help="<Picture 2> 描述最小字符数，默认 80")
    ap.add_argument("--min-desc", type=int, default=40, help="detailed_description 最小字符数，默认 40")
    ap.add_argument("--allow-content", action="store_true", help="只统计不阻断")
    args = ap.parse_args()

    if not os.path.isfile(args.csv):
        print("FAIL: 文件不存在:", args.csv)
        return 1
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("FAIL: CSV 无数据行")
        return 1

    errors, warnings = [], []
    md_shots = load_md_shots(args.prompt_md)
    seen_desc = {}   # 归一化 detailed_description -> 首个 shot_id

    print("%-10s %-9s %-8s %-8s %-8s %s" % (
        "SHOT", "SHOT#N", "PIC2", "DESC", "MD", "状态"))

    for r in rows:
        sid = (r.get("shot_id") or "?").strip()
        want = shot_num(sid)
        six = {k: (r.get(k) or "") for k in PROMPT_SECTIONS}
        err_before = len(errors)
        pic2_bad = pic2_warn = desc_bad = False

        # 1) [Shot N] 镜号匹配：六列全部扫描
        tags = []
        for k in PROMPT_SECTIONS:
            tags += [(k, int(n)) for n in SHOT_TAG_RE.findall(six[k])]
        bad_tags = [(k, n) for k, n in tags if want is not None and n != want]
        if want is None:
            errors.append("%s shot_id 无法提取镜号（期望 S004 形式）" % sid)
        for k, n in bad_tags:
            errors.append("%s [%s] 的 [Shot %d] 镜号错，应为 [Shot %d]——H3 会当成第 %d 镜开头"
                          % (sid, k, n, want, n))

        # 2) Picture2 身份描述：>80 字符 + 非孤立 speaker
        p2 = pic2_desc(six["subject_definitions"])
        if not p2:
            errors.append("%s subject_definitions 缺 <Picture 2> 身份板描述" % sid)
            pic2_bad = True
        elif EMPTY_SPEAKER_RE.match(p2):
            errors.append("%s <Picture 2> 只有孤立 %r，无身份/服装/发型锚"
                          % (sid, p2))
            pic2_bad = True
        elif len(p2) <= args.min_pic2 and not REUSE_RE.search(p2):
            errors.append("%s <Picture 2> 描述仅 %d 字符（≤%d），且非明确复用上文——须写全身份"
                          "（如 29yo East Asian man, navy suit, mid-length black hair...）"
                          % (sid, len(p2), args.min_pic2))
            pic2_bad = True
        elif len(p2) <= args.min_pic2:
            warnings.append("%s <Picture 2> 仅 %d 字符，靠复用上文 %r——若非同一人连续镜请补写"
                            % (sid, len(p2), p2[:50]))
            pic2_warn = True

        # 3) detailed_description 具体动作
        desc = six["detailed_description"].strip()
        if not desc:
            errors.append("%s detailed_description 为空" % sid)
            desc_bad = True
        elif len(desc) < args.min_desc:
            errors.append("%s detailed_description 仅 %d 字符（<%d），无具体动作"
                          % (sid, len(desc), args.min_desc))
            desc_bad = True
        elif VAGUE_DESC_RE.search(desc) or VAGUE_ONLY_RE.search(desc) or PLACEHOLDER_RE.search(desc):
            errors.append("%s detailed_description 是通用模板 %r——须逐镜写动作与朝向"
                          % (sid, desc[:60]))
            desc_bad = True
        elif not ACTION_VERBS_RE.search(desc):
            warnings.append("%s detailed_description 未检出动作动词，疑似只有机位/台词：%r"
                            % (sid, desc[:60]))

        # 4) 跨镜模板复制
        nd = norm_text(desc)
        if nd and nd in seen_desc:
            errors.append("%s detailed_description 与 %s 完全相同（模板复制，镜间无差异）"
                          % (sid, seen_desc[nd]))
            desc_bad = True
        elif nd:
            seen_desc[nd] = sid

        # 5) 提示词单一事实源：md 对应镜远丰富于 CSV
        md_flag = "-"
        if want in md_shots:
            md_len = len(norm_text(md_shots[want]))
            csv_len = len(nd)
            md_flag = "%d/%d" % (csv_len, md_len)
            if md_len > csv_len * 2 and csv_len < 120:
                warnings.append("%s 视频提示词.md 内容（%d 字）远丰富于 CSV（%d 字）——"
                                "疑似「写对了但没用上」，请核对 CSV 六列是否回填"
                                % (sid, md_len, csv_len))
        elif args.prompt_md:
            warnings.append("%s 在视频提示词.md 中找不到对应镜块（## SHOT-...）" % sid)

        ok = len(errors) == err_before
        print("%-10s %-9s %-8s %-8s %-8s %s" % (
            sid,
            "OK" if not bad_tags else "BAD(%d)" % len(bad_tags),
            "BAD" if pic2_bad else ("WARN" if pic2_warn else "OK"),
            "BAD" if desc_bad else "OK",
            md_flag,
            "OK" if ok else "CHECK",
        ))

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
        print("=== PASS：镜号/Picture2/动作描述/跨镜差异 全部合格 ===")

    if errors and args.allow_content:
        print("\n（--allow-content：仅统计，不阻断）")
        return 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
