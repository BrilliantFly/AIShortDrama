#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场景回合密度检查：把 `scene-beats.md` 的规则变成可执行检查。

检查的对象是章节里的「场次节拍表」，不是正文文笔。判据只有一条：
这一章能不能被拆成镜头——回合够不够、台词够不够、叙述有没有替台词把信息说完。

用法
  python check_scene_density.py 第01章.md
  python check_scene_density.py --all novels/书名/
  python check_scene_density.py 第01章.md --json

退出码：0 全通过（允许 WARN）／1 有 FAIL／2 用法或解析错误
"""
from __future__ import annotations

import argparse
import glob
import io
import os
import re
import sys

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("check_scene_density.py requires Python 3.9 or newer")

# 支点场 / 常规场 / 过场 的下限与上限
FLOOR = {
    "支点": {"rounds": 6, "lines": 10, "max_rounds": None, "max_lines": None},
    "常规": {"rounds": 3, "lines": 5, "max_rounds": None, "max_lines": None},
    "过场": {"rounds": 1, "lines": 1, "max_rounds": 2, "max_lines": 3},
}
CHARS_PER_SEC = 3.2          # 一格 6~12 字台词的保守估值
SEC_TOL = (1.6, 6.5)         # 每句台词允许的秒数区间
AVG_SHOT = 2.5               # 预估镜数 = 预估秒 ÷ 2.5
NARRATION_RATIO = 0.5        # 单场叙述段 ≤ 台词句数 × 0.5

HEADER_KEYS = ("回合", "台词句")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def to_int(v: str) -> int | None:
    m = re.search(r"-?\d+", v or "")
    return int(m.group()) if m else None


def to_float(v: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", v or "")
    return float(m.group()) if m else None


def find_tables(text: str) -> list[tuple[dict[str, int], list[list[str]]]]:
    """找出所有表头含「回合」「台词句」的 markdown 表格。"""
    lines = text.splitlines()
    out: list[tuple[dict[str, int], list[list[str]]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("|") and any(k in line for k in HEADER_KEYS):
            cols = cells(line)
            index = {name: n for n, name in enumerate(cols)}
            block: list[list[str]] = []
            j = i + 2  # 跳过表头与分隔行
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                block.append(cells(lines[j]))
                j += 1
            out.append((index, block))
            i = j
        else:
            i += 1
    return out


def norm_type(v: str) -> str | None:
    for key in FLOOR:
        if key in (v or ""):
            return key
    return None


def check_file(path: str) -> tuple[int, str, list[str], list[str]]:
    text = io.open(path, encoding="utf-8").read()
    tables = find_tables(text)
    if not tables:
        return 2, os.path.basename(path), [], ["没找到「场次节拍表」（表头需含「回合」「台词句」）"]

    fails: list[str] = []
    warns: list[str] = []
    total_lines = total_rounds = total_sec = total_shots = 0

    for index, rows in tables:
        col = lambda name: index.get(name)  # noqa: E731
        for row in rows:
            if len(row) < len(index):
                continue
            get = lambda name: row[col(name)] if col(name) is not None else ""  # noqa: E731
            scene = get("场") or "?"
            stype = norm_type(get("场型"))
            rounds = to_int(get("回合"))
            lines = to_int(get("台词句"))
            narr = to_int(get("叙述段"))
            sec = to_float(get("预估秒"))
            shots = to_int(get("预估镜"))

            if stype is None:
                warns.append(f"{scene}: 场型「{get('场型')}」不是 支点/常规/过场，跳过下限检查")
            if rounds is None or lines is None:
                fails.append(f"{scene}: 回合或台词句数读不出来（回合=「{get('回合')}」，台词句=「{get('台词句')}」）")
                continue

            total_rounds += rounds
            total_lines += lines

            if stype:
                fl = FLOOR[stype]
                if fl["max_rounds"] is None:
                    if rounds < fl["rounds"]:
                        fails.append(f"{scene}: {stype}场只有 {rounds} 个回合（下限 {fl['rounds']}）——"
                                     f"这场拆不出镜头，先补回合再补描写")
                    if lines < fl["lines"]:
                        fails.append(f"{scene}: {stype}场只有 {lines} 句台词（下限 {fl['lines']}）")
                else:
                    if rounds > fl["max_rounds"]:
                        warns.append(f"{scene}: 过场写了 {rounds} 个回合（上限 {fl['max_rounds']}），考虑并场")
                    if lines > fl["max_lines"]:
                        fails.append(f"{scene}: 过场写了 {lines} 句台词（上限 {fl['max_lines']}）——"
                                     f"过场只做搬运，承载新信息就应升为常规场")

            # 一回合至少一句台词：回合多于台词说明大部分交锋被概括掉了
            if lines < rounds:
                fails.append(f"{scene}: {rounds} 个回合只有 {lines} 句台词——"
                             f"有回合没有开口，多半写成了「聊了几句」这类概括")

            # 叙述不该替台词把信息说完
            if narr is not None and narr > lines * NARRATION_RATIO + 0.5:
                fails.append(f"{scene}: 叙述段 {narr} 段 vs 台词 {lines} 句（上限 {lines * NARRATION_RATIO:.0f} 段）——"
                             f"信息压在叙述上，改编只能出旁白")

            if sec is not None:
                total_sec += sec
                lo, hi = lines * SEC_TOL[0], lines * SEC_TOL[1]
                if sec < lo:
                    warns.append(f"{scene}: 预估 {sec:g} 秒对 {lines} 句台词偏短（参考 ≥{lo:.0f} 秒），"
                                 f"开口前的留白可能不够")
                elif sec > hi:
                    warns.append(f"{scene}: 预估 {sec:g} 秒对 {lines} 句台词偏长（参考 ≤{hi:.0f} 秒），"
                                 f"多出来的时长要由可见动作撑住，否则是空转")

            if shots is not None:
                total_shots += shots
                if shots < lines * 0.8:
                    fails.append(f"{scene}: 预估 {shots} 镜 < 台词 {lines} 句——一句一镜是下限，"
                                 f"这个镜数必然一镜吞多句")
                if sec is not None:
                    expect = sec / AVG_SHOT
                    if shots < expect * 0.6 or shots > expect * 1.8:
                        warns.append(f"{scene}: 预估 {shots} 镜与 {sec:g} 秒不匹配"
                                     f"（按 {AVG_SHOT} 秒/镜约 {expect:.0f} 镜）")

    summary = (f"{os.path.basename(path)}: 场 {sum(len(r) for _, r in tables)} / 回合 {total_rounds} / "
               f"台词 {total_lines} 句 / 预估 {total_sec or 0:.0f} 秒 / 预估 {total_shots or 0} 镜")
    return (1 if fails else 0), summary, fails, warns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="章节 md 文件，或配合 --all 传目录")
    ap.add_argument("--all", action="store_true", help="传入目录，检查其下所有 .md")
    ap.add_argument("--json", action="store_true", help="只输出 JSON，便于接流水线")
    a = ap.parse_args()

    if a.all:
        if not os.path.isdir(a.path):
            print(f"不是目录：{a.path}")
            return 2
        files = sorted(glob.glob(os.path.join(a.path, "**", "*.md"), recursive=True))
        files = [f for f in files if not os.path.basename(f).startswith("00-")
                 and not os.path.basename(f).startswith("01-")
                 and not os.path.basename(f).startswith("02-")]
    else:
        if not os.path.exists(a.path):
            print(f"找不到 {a.path}")
            return 2
        files = [a.path]

    if not files:
        print("没有可检查的章节文件")
        return 2

    rc = 0
    report = []
    for f in files:
        code, summary, fails, warns = check_file(f)
        rc = max(rc, code)
        report.append({"file": f, "rc": code, "summary": summary, "fails": fails, "warns": warns})
        if not a.json:
            print(summary)
            for line in fails:
                print("FAIL:", line)
            for line in warns[:10]:
                print("WARN:", line)
            if len(warns) > 10:
                print(f"WARN: …还有 {len(warns) - 10} 条")

    if a.json:
        import json
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif rc == 0:
        print("\nPASS — 场次回合与台词量够拆镜，叙述没有替台词把话说完")
    else:
        print("\nFAIL — 先回改回合与台词，再进剧本阶段")
    return rc


if __name__ == "__main__":
    sys.exit(main())
