#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分镜 → H3 NG 故事板转换器：把《分镜.md》的站位与景别翻成 NGStoryboard 的
`h3-storyboard` 文档（panel + 图层坐标），可在 ComfyUI 的 H3 Storyboard 节点里
直接粘贴 / 用 `--workflow` 注入模板。

为什么要这个脚本：drama 的「场景站位」是散文，产线上要靠人照着文字去拖图层；
NGStoryboard 的图层是数字（x / y / scale）。文字到数字这一步以前是手工的，
于是「站位不对」在产线上无法机械核对。本脚本让站位块直接变成坐标。

用法
  python storyboard_to_ng.py 分镜.md --out 故事板.json
  python storyboard_to_ng.py 分镜.md --out 故事板.json \\
      --bg "旧书店门廊（雨夜）=porch.jpg" \\
      --figure "林知夏=linzhixia-cut.webp" --figure "陈屿=chenyu-cut.webp"
  python storyboard_to_ng.py 分镜.md --out 故事板.json \\
      --workflow H3-NG导演台-06-故事板-双角色.json --out-workflow 我的故事板.json

映射规则见 references/ng-storyboard-export.md。脚本只做「分镜里已经写明的事」，
推不出来的会进报告，不静默编造。

退出码：0 成功（可能有提示）／1 没解析到镜头块／2 路径或格式错误
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("storyboard_to_ng.py requires Python 3.9 or newer")

# ---------------------------------------------------------------- 解析分镜

SHOT_RE = re.compile(r"^##\s+(SHOT-[0-9A-Za-z\-]+)\s*[·:：]?\s*(.*)$", re.M)
SCENE_RE = re.compile(r"^##\s*场景站位\s*[·:：]\s*([A-Za-z]{1,4}\d+(?:-SC\d+)?)\s*[·:：]?\s*(.*)$", re.M)
FIELD_RE = re.compile(r"^-\s+(?:\*\*)?(.+?)(?:\*\*)?\s*[：:]\s*(.*)$", re.M)
PERSON_RE = re.compile(r"人物「([^」]{1,30})」")
PLACE_RE = re.compile(r"地点「([^」]{1,40})」")

# 景别 → (标签, scale, head_y)。scale / head_y 由 06 模板实测标定：
# 全景 0.17 / y 0.64、中景 0.42 / y 0.70、中近景 0.60 / y 0.80 三档完全吻合，
# 其余档位按同一公式 y = head_y + scale/2 外推。
SIZE_TABLE: Dict[str, Tuple[float, float, List[str]]] = {
    "大景": (0.12, 0.60, ["大景", "大全景", "远景", "establishing shot", "extreme wide", "aerial", "wide establishing"]),
    "全景": (0.17, 0.555, ["全景", "wide shot", "wide frame", "full shot", "long shot", "wide of"]),
    "中全景": (0.30, 0.50, ["中全景", "medium wide", "medium full", "cowboy shot"]),
    "中景": (0.42, 0.49, ["中景", "medium shot", "medium two-shot", "two-shot", "medium of"]),
    "中近景": (0.60, 0.50, ["中近景", "medium close", "mcu"]),
    "近景": (0.80, 0.45, ["近景", "close-up", "close up", "closeup", "close on"]),
    "特写": (0.0, 0.0, ["特写", "大特写", "extreme close", "macro", "insert shot"]),
}
# 判读顺序：先具体后笼统，否则 "medium close-up" 会被 "medium" 抢走
SIZE_ORDER = ["特写", "中近景", "近景", "中全景", "大景", "全景", "中景"]

# 左右线索分强弱：写明「frame / side / third / half」的强线索先归人，
# 只有「at lower left」这类弱线索在无人认领时才用，避免把杂物位置读成人物站位。
SIDE_PATTERNS: List[Tuple[str, bool]] = [
    (r"(?:on|at|in)\s+(?:the\s+)?(?:frame'?s?\s+)?(?P<side>left|right)\s+(?:side|half|third|edge)", True),
    (r"(?P<side>left|right)\s+(?:upper|lower|top|bottom)?\s*(?:third|half|side|edge)\s+of\s+(?:the\s+)?frame", True),
    (r"画(?:面)?(?P<side>左|右)", True),
    (r"(?P<side>left|right)\s+foreground", True),
    (r"(?P<side>cent(?:er|re))(?:\s+(?:of\s+(?:the\s+)?)?frame)?", True),
    (r"画(?:面)?中央(?P<side>center)", True),
    (r"(?:on|at|in|to|toward)\s+(?:the\s+)?(?:upper|lower|top|bottom)?\s*(?P<side>left|right)\b", False),
    (r"\b(?:upper|lower|top|bottom)\s+(?P<side>left|right)\b", False),
]
# 垂直高度线索：只在这类词就近指向某人时才抬 y（高度层行本身不自动套用，避免全场平移）
LIFT_RE = re.compile(
    r"\b(airborne|mid-?air|leaps?|leaping|jumps?|jumping|above|pillar top|rooftop|rafters?)\b"
    r"|腾空|跃起|跳起|空中|柱顶|屋顶|上层|半空", re.I)
# 特写镜里判断「拍的是人还是物」：正文出现人物/身体部位词才算人物特写
PERSON_CUE_RE = re.compile(
    r"\b(face|faces|eyes|eye|profile|hands?|fingers?|lips|mouth|chin|jaw|brow|hair|"
    r"she|he|her|his|woman|man|girl|boy|figure|shoulders?)\b|她|他|脸|眼|唇|手|下颌|发", re.I)
SCENE_SIDE_RE = re.compile(r"([^，。；、,;]{1,12}?)在画面(左|右)")
# 来源字段的场次 ID：取开头「字母+数字」段（SC01 / EP001-SC01），后跟「」引文不影响解析
SCENE_KEY_RE = re.compile(r"^([A-Za-z]{1,4}\d+(?:-SC\d+)?(?:-SC\d+)*)")
# OTS 前景肩：中文「越过X的肩 / 越过X左肩 / X的肩背 / X的西装肩背」，英文 "the shoulder of X" / "X's back"
OTS_FG_RE = re.compile(
    r"越过([\u4e00-\u9fa5]{2,8}?)(?:的)?(?:左|右)?肩"
    r"|([\u4e00-\u9fa5]{2,8})的(?:西装|黑色|黑西装)?(?:肩|肩背|肩线|背影|后背|背)"
    r"|(?:the\s+)?(?:shoulder|shoulders|back|torso)\s+of\s+(?:the\s+)?([A-Za-z][A-Za-z]{2,20})"
    r"|(?:\b)([A-Za-z][A-Za-z]{2,20})'s\s+(?:shoulder|back)", re.I)
# 视觉依据兜底：正文是英文没点名时，「人物「X」（…仅虚化肩背…）」就是前景肩
OTS_FG_VISUAL_RE = re.compile(r"人物「([\u4e00-\u9fa5]{2,8})」[（(][^）]*虚化[^）]*肩背")


def read_text(path: str) -> str:
    return io.open(path, encoding="utf-8").read()


def fields_of(block: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in FIELD_RE.finditer(block):
        key = m.group(1).strip()
        if key and key not in out:
            out[key] = m.group(2).strip()
    return out


def pick(f: Dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in f and f[k]:
            return f[k]
    return ""


def split_shots(text: str) -> List[Tuple[str, str, str]]:
    marks = list(SHOT_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.end():end]))
    return out


def scene_blocks(text: str) -> Dict[str, Dict[str, str]]:
    marks = list(SCENE_RE.finditer(text))
    out: Dict[str, Dict[str, str]] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[m.group(1)] = fields_of(text[m.end():end])
    return out


def keyframe_body(block: str) -> str:
    """取「冻结关键帧」后的正文，去代码围栏与引用号，压成一行。"""
    m = re.search(r"^###\s*冻结关键帧.*?$", block, re.M)
    body = block[m.end():] if m else block.split("\n###", 1)[1] if "\n###" in block else ""
    body = re.sub(r"^\s*```[a-zA-Z]*\s*$", "", body, flags=re.M)
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line == ">":
            continue
        line = re.sub(r"^>\s?", "", line)
        lines.append(line)
    return " ".join(lines).strip()


def parse_seconds(raw: str) -> float:
    m = re.search(r"([\d.]+)\s*(?:s|秒)?", raw or "")
    return float(m.group(1)) if m else 0.0


# ---------------------------------------------------------------- 视觉设定

def parse_cast(visual_text: str) -> Dict[str, List[str]]:
    """人物名 → 画面代称列表（creator-documents.md：多个写法用「、」分隔）。"""
    out: Dict[str, List[str]] = {}
    for m in re.finditer(r"^#{2,4}\s*人物\s*[·:：]\s*(.+?)\s*$", visual_text, re.M):
        name = m.group(1).strip()
        nxt = visual_text.find("\n## ", m.end())
        chunk = visual_text[m.end(): nxt if nxt > 0 else len(visual_text)]
        alias = pick(fields_of(chunk), "画面代称", "英文名")
        if not alias or alias.strip() == "无":
            out[name] = []
            continue
        out[name] = [a.strip() for a in re.split(r"[、,，/]", alias) if a.strip()]
    return out


def parse_aspect(visual_text: str) -> str:
    m = re.search(r"(竖屏|横屏|方形)?\s*(21:9|16:9|9:16|4:3|3:4|1:1)", visual_text or "")
    return m.group(2) if m else "16:9"


# ---------------------------------------------------------------- 推理

def infer_size(size_field: str, body: str) -> Tuple[str, float, float, str]:
    """返回 (标签, scale, head_y, 依据)。特写返回 scale=0（不摆全身图层）。"""
    for idx, text in enumerate([size_field.lower(), body.lower()]):
        if not text:
            continue
        for label in SIZE_ORDER:
            for w in SIZE_TABLE[label][2]:
                pat = re.escape(w) if not w.isascii() else r"(?<![a-z])" + re.escape(w) + r"(?![a-z])"
                if re.search(pat, text):
                    # "medium" 单独命中时排除 medium close / medium wide 这类更具体的写法
                    if label == "中景" and re.search(r"medium\s+(close|wide|full)", text) \
                            and not re.search(r"medium (shot|two-shot)", text):
                        continue
                    return label, SIZE_TABLE[label][0], SIZE_TABLE[label][1], \
                        "景别/机位" if idx == 0 else "关键帧正文"
    return "", 0.0, 0.0, ""


def name_pattern(lit: str) -> "re.Pattern[str]":
    """人名匹配：中文整体匹配；拉丁代称允许词间空格（DongfangBubai ↔ Dongfang Bubai）。"""
    if re.search(r"[\u4e00-\u9fff]", lit):
        return re.compile(re.escape(lit))
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+", lit) or [lit]
    body = r"\s*".join(re.escape(x) for x in parts)
    return re.compile(r"(?<![A-Za-z])" + body + r"(?![A-Za-z])", re.I)


def side_tokens(text: str) -> List[Tuple[int, int, str, bool]]:
    """返回 [(start, end, side, strong)]；side 为 left/right。"""
    out: List[Tuple[int, int, str, bool]] = []
    if not text:
        return out
    for pat, strong in SIDE_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            raw = m.group("side").lower()
            side = {"left": "left", "左": "left", "right": "right", "右": "right"}.get(raw, "center")
            out.append((m.start(), m.end(), side, strong))
    return out


def sides_in_text(text: str, people: List[Tuple[str, List[str]]]) -> Dict[str, str]:
    """把「画面左/右/中」的线索归到离它最近的那个人身上。

    逐人找左右会把别人的方位读成自己的（「他走向站在画右的她」），所以先收集所有人名
    出现位置，再按「离谁最近就归谁」分配；距离相近时强线索优先。
    """
    tokens = side_tokens(text)
    if not tokens:
        return {}
    mentions: List[Tuple[int, int, str]] = []
    for cn, aliases in people:
        for lit in [cn] + aliases:
            if not lit:
                continue
            for m in name_pattern(lit).finditer(text):
                mentions.append((m.start(), m.end(), cn))
    if not mentions:
        return {}
    best_by_person: Dict[str, Tuple[float, bool, str]] = {}
    for start, end, side, strong in tokens:
        # 英文习惯是「先说人再说位置」（his shoulder fills the left foreground），
        # 所以同一小句里先出现的那个人优先；前面没人时才看后面提到的人。
        before = [x for x in mentions if x[1] <= start and start - x[1] <= 80]
        after = [x for x in mentions if x[0] >= end and x[0] - end <= 80]
        if before:
            who = max(before, key=lambda x: x[1])
            gap = start - who[1]
        elif after:
            who = min(after, key=lambda x: x[0])
            gap = who[0] - end
        else:
            continue
        cur = best_by_person.get(who[2])
        score = (gap, 0 if strong else 1)
        if cur is None or score < (cur[0], 0 if cur[1] else 1):
            best_by_person[who[2]] = (gap, strong, side)
    return {k: v[2] for k, v in best_by_person.items()}


def parse_scene_sides(blocking: Dict[str, str]) -> Dict[str, str]:
    line = pick(blocking, "屏幕方向", "朝向")
    out: Dict[str, str] = {}
    for m in SCENE_SIDE_RE.finditer(line or ""):
        seg, side = m.group(1).strip(" 　的"), m.group(2)
        out[seg] = "left" if side == "左" else "right"
    return out


def parse_layer_override(raw: str) -> Dict[str, Dict[str, float]]:
    """`- 图层：陈屿 x=0.30 scale=0.60 y=0.80 flip=true opacity=0.9` 逐镜硬指定。"""
    out: Dict[str, Dict[str, float]] = {}
    for m in re.finditer(r"([^\s=，,;；]+?)\s*((?:\s+\w+=[^\s，,;；]+)+)", raw or ""):
        name = m.group(1)
        vals: Dict[str, float] = {}
        for kv in re.finditer(r"(\w+)=([^\s，,;；]+)", m.group(2)):
            k, v = kv.group(1), kv.group(2)
            try:
                vals[k] = float(v) if k != "flip" else (1.0 if v.lower() in ("true", "1", "yes") else 0.0)
            except ValueError:
                continue
        if vals:
            out[name] = vals
    return out


# ---------------------------------------------------------------- 组装

def src_of(path: str) -> Dict[str, str]:
    path = (path or "").strip()
    if not path:
        return {"filename": "", "subfolder": "", "type": "input"}
    path = path.replace("\\", "/").lstrip("/")
    if "/" in path:
        sub, name = path.rsplit("/", 1)
        return {"filename": name, "subfolder": sub, "type": "input"}
    return {"filename": path, "subfolder": "", "type": "input"}


def filter_shots(shots: List[Tuple[str, str, str]],
                 scene_sel: List[str], shot_sel: List[str],
                 notes: List[str]) -> List[Tuple[str, str, str]]:
    """按 --scene / --shots 过滤镜头；两个都给时取交集。"""
    if not scene_sel and not shot_sel:
        return shots
    out = []
    for sid, title, block in shots:
        f = fields_of(block)
        src = pick(f, "来源", "场次")
        hit_scene = (not scene_sel) or any(
            re.search(r"(?<![0-9A-Za-z])" + re.escape(s), src, re.I) for s in scene_sel)
        # 镜号匹配：完整 SHOT-xxx 精确；纯数字对镜号尾段；001-005 为闭区间
        hit_shot = not shot_sel
        if shot_sel:
            tail = sid.rsplit("-", 1)[-1]
            for tok in shot_sel:
                m = re.fullmatch(r"(\d{2,4})-(\d{2,4})", tok)
                if m and tail.isdigit() and int(m.group(1)) <= int(tail) <= int(m.group(2)):
                    hit_shot = True
                elif tok.upper() == sid.upper() or tok == tail:
                    hit_shot = True
        if hit_scene and hit_shot:
            out.append((sid, title, block))
    if not out:
        raise SystemExit(f"--scene/--shots 过滤后没有命中任何镜（scene={scene_sel}, shots={shot_sel}）；"
                         f"请核对分镜「来源」的场次 ID 与镜号")
    notes.append(f"按场次/镜号筛选：{len(shots)} 镜中取 {len(out)} 镜")
    return out


def build(text: str, visual_text: str, opts: argparse.Namespace) -> Tuple[dict, List[str], List[str], List[dict]]:
    shots = split_shots(text)
    pre_notes: List[str] = []
    shots = filter_shots(shots, getattr(opts, "scene_sel", []) or [],
                         getattr(opts, "shot_sel", []) or [], pre_notes)
    scenes = scene_blocks(text)
    cast = parse_cast(visual_text) if visual_text else {}
    for cn, alias in parse_kv(getattr(opts, "cast", []) or []).items():
        cast.setdefault(cn, [])
        if alias and alias not in cast[cn]:
            cast[cn] = [alias] + cast[cn]
    aspect = opts.aspect or parse_aspect(visual_text)

    notes: List[str] = []
    notes.extend(pre_notes)
    panels: List[dict] = []
    meta: List[dict] = []
    layer_uid = 0
    library: List[dict] = []
    lib_ids: Dict[str, str] = {}

    def lib_entry(name: str, kind: str, filename: str) -> None:
        if not filename or name in lib_ids:
            return
        lid = f"a{len(lib_ids) + 1}"
        lib_ids[name] = lid
        library.append({"id": lid, "name": name, "kind": kind, "src": src_of(filename)})

    total = 0.0
    for idx, (sid, title, block) in enumerate(shots):
        f = fields_of(block)
        body = keyframe_body(block)
        scene_id = pick(f, "来源", "场次") or ""
        m_key = SCENE_KEY_RE.match(scene_id)
        scene_key = m_key.group(1) if m_key else scene_id
        blocking = scenes.get(scene_key) or scenes.get(scene_id, {})
        scene_sides = parse_scene_sides(blocking)

        secs = parse_seconds(pick(f, "时长", "镜长"))
        if not secs:
            frames = parse_seconds(pick(f, "export_frames", "帧数"))
            secs = round(frames / opts.fps, 2) if frames else 0.0
            if secs:
                notes.append(f"{sid} 缺 `时长`，按 export_frames÷{opts.fps} 折算 {secs}s")
        if not secs:
            secs = 5.0
            notes.append(f"{sid} 既缺 `时长` 也缺 `export_frames`，暂按 5s（面板时长会写错，请补）")
        total += secs

        size_field = pick(f, "景别/机位", "景别", "机位", "镜头")
        size_label, scale, head_y, size_src = infer_size(size_field, body)
        if not size_label:
            size_label, scale, head_y, size_src = ("中景", 0.42, 0.49, "默认")
            notes.append(f"{sid} 认不出景别（`景别/机位` 与正文都没有 wide/medium/close 级词），按中景摆放")

        # 人物：优先「视觉依据」里点名的人，缺则从站位块人物行找本镜具名者
        names = []
        # 画外的人不摆图层：视觉依据里「画外：人物「X」」是声音/视线对象，不在画面内
        visual = re.sub(r"画外[：:][^;；]*[;；]?", "", pick(f, "视觉依据"))
        for m in PERSON_RE.finditer(visual):
            n = m.group(1).strip()
            if n not in names:
                names.append(n)
        if not names and pick(f, "起点", "终点"):
            for cn in cast:
                if cn in pick(f, "起点", "终点"):
                    names.append(cn)
        # SOLO 镜只摆一个人：视觉依据常把对手也列进来，照单全收会摆出两人同框
        if (pick(f, "镜型") or "").upper() == "SOLO" and len(names) > 1:
            mentioned = [cn for cn in names
                         if cn in body or any(a and name_pattern(a).search(body)
                                              for a in cast.get(cn, []))]
            if len(mentioned) == 1:
                names = mentioned
            elif not mentioned:
                names = names[:1]
                notes.append(f"{sid} 镜型=SOLO 但正文没点名，只摆视觉依据里的第一个人（{names[0]}）")
            else:
                notes.append(f"{sid} 镜型=SOLO 但正文点名了 {len(mentioned)} 人——镜型可能误标，请核对")

        override = parse_layer_override(pick(f, "图层"))

        # OTS 前景肩：正文点名「越过X的肩 / X的肩背 / the shoulder of X」时，
        # X 是前景肩背——放大贴边并置顶层，让拼贴接近成片的过肩构图。
        ots_fg = ""
        if (pick(f, "镜型") or "").upper() == "OTS" and len(names) >= 2:
            fg_text = " ".join([size_field, pick(f, "起点"), pick(f, "终点"), pick(f, "唯一动作"), body])
            for m in OTS_FG_RE.finditer(fg_text):
                found = next(g for g in m.groups() if g)
                for cn in names:
                    lits = [cn] + cast.get(cn, [])
                    if any(lit and (lit.lower() == found.lower() or lit in found or found in lit)
                           for lit in lits):
                        ots_fg = cn
                        break
                if ots_fg:
                    break
            if not ots_fg:
                m_vis = OTS_FG_VISUAL_RE.search(pick(f, "视觉依据"))
                if m_vis and m_vis.group(1) in names:
                    ots_fg = m_vis.group(1)

        layers: List[dict] = []
        bg_file = opts.bg_default
        place = place_name = ""
        for m in PLACE_RE.finditer(pick(f, "视觉依据")):
            place_name = m.group(1).strip()
            break
        if place_name and place_name in opts.bg_map:
            place, bg_file = place_name, opts.bg_map[place_name]
        elif place_name:
            place = place_name
        bg_name = place or "Background"
        if not bg_file:
            bg_file = "h3-example-hall.jpg"
        lib_entry(bg_name, "background", bg_file)
        layer_uid += 1
        layers.append({
            "id": f"l{layer_uid}", "kind": "image", "name": bg_name,
            "x": 0.5, "y": 0.5, "rotation": 0, "flip": False, "opacity": 1,
            "hidden": False, "src": src_of(bg_file), "scale": 1, "redrawn": False,
        })

        placed = []
        people = [(cn, cast.get(cn, [])) for cn in names]
        shot_sides: Dict[str, str] = {}
        for field_text in [size_field, pick(f, "起点"), pick(f, "终点"), pick(f, "唯一动作"), body]:
            for cn, side in sides_in_text(field_text, people).items():
                shot_sides.setdefault(cn, side)
        shot_lift: Dict[str, str] = {}
        for field_text in [size_field, body]:
            if not field_text:
                continue
            for m in LIFT_RE.finditer(field_text):
                mid = (m.start() + m.end()) / 2
                best = None
                for cn2, aliases2 in people:
                    for lit in [cn2] + aliases2:
                        if not lit:
                            continue
                        for mm in name_pattern(lit).finditer(field_text):
                            d = min(abs(mid - mm.start()), abs(mid - mm.end()))
                            if best is None or d < best[0]:
                                best = (d, cn2)
                if best and best[0] <= 40:
                    shot_lift.setdefault(best[1], m.group(0))
        for cn, side in scene_sides.items():
            for real in names:
                if real == cn or cn in real or real in cn:
                    shot_sides.setdefault(real, side)

        for n, cn in enumerate(names):
            aliases = cast.get(cn, [])
            tag = aliases[0] if aliases else cn
            ov = override.get(tag) or override.get(cn) or {}
            is_fg = cn == ots_fg and "scale" not in ov and "x" not in ov
            if size_label == "特写" and "scale" not in ov:
                if PERSON_CUE_RE.search(body):
                    # 人物特写：全身抠图缩不出脸，先按近景构图占位
                    s, hy = 0.80, 0.45
                    notes.append(f"{sid} 景别=特写，{cn} 先按近景（scale 0.80）摆放——"
                                 f"面部特写请在面板里换图或手动调整，别指望全身抠图缩出脸")
                else:
                    # 物证/细节特写（针尖、绣绷、水珠）：画面里本来就没有人
                    notes.append(f"{sid} 景别=特写且正文没有人（物证/细节镜），{cn} 不摆人物图层")
                    continue
            else:
                s = float(ov.get("scale", scale)) if scale or "scale" in ov else 0.42
                hy = head_y if head_y else 0.49
            if is_fg:
                # 前景肩背：放大贴边、位置下移到肩背高度；上一轮教训——图层按添加
                # 顺序叠加，前景必须在最后添加（循环后挪到列表末尾）
                s = round(min(1.15, max(s, 0.42) * 1.9), 3)
                y = 0.62
                side = shot_sides.get(cn)
                x = {"left": 0.10, "right": 0.90}.get(side, 0.12)
                xsrc = "OTS 前景肩贴边"
                notes.append(f"{sid} OTS 前景肩：{cn} 自动放大贴边（scale→{s}、x→{x}、置顶层）；"
                             f"要手调就写 `- 图层：{tag} scale=… x=…` 覆盖")
            y = float(ov.get("y", (hy + s / 2) if not is_fg else y))
            if "y" not in ov and not is_fg and shot_lift.get(cn):
                y = round(max(0.05, y - 0.15), 3)
                notes.append(f"{sid} {cn} 读作离地/高处（{shot_lift[cn]}），y 抬 0.15 → {y:.2f}；"
                             f"高度层只能这样近似，精确高度用 `- 图层：{tag} y=0.45`")
            if is_fg:
                pass  # x 已在上方按前景肩贴边定死，跳过常规推定
            elif "x" in ov:
                x, xsrc = float(ov["x"]), "图层行指定"
            elif shot_sides.get(cn):
                x = {"left": 0.30, "right": 0.70}.get(shot_sides[cn], 0.5)
                xsrc = f"文本线索（{shot_sides[cn]}）"
            elif len(names) == 1:
                x, xsrc = 0.5, "单人镜居中"
            else:
                step = 0.40 / max(1, len(names) - 1)
                x = round(0.5 + (n - (len(names) - 1) / 2) * step, 3)
                xsrc = "推定（无左右线索）"
                notes.append(f"{sid} 读不出 {cn} 在画面哪侧，x 先按 {x:.2f} 推定——"
                             f"请在分镜里补「画面左/右」或加 `- 图层：{tag} x=0.30` 行")
            flip = bool(ov.get("flip", 0))
            opacity = float(ov.get("opacity", 1))
            layer_uid += 1
            layers.append({
                "id": f"l{layer_uid}", "kind": "image", "name": tag,
                "x": round(x, 3), "y": round(y, 3), "rotation": 0, "flip": flip,
                "opacity": opacity, "hidden": False,
                "src": src_of(opts.fig_map.get(tag) or opts.fig_map.get(cn)
                              or opts.fig_placeholder.get(tag) or opts.fig_placeholder.get(cn) or ""),
                "scale": round(s, 3), "redrawn": False,
            })
            if not (opts.fig_map.get(tag) or opts.fig_map.get(cn)):
                notes.append(f"{sid} {tag} 用占位人物图 `{layers[-1]['src']['filename']}`，请用 `--figure \"{cn}=你的抠图.webp\"` 换成真图")
            placed.append((tag, x))
            lib_entry(tag, "figure", layers[-1]["src"]["filename"])

        # 前景肩置顶层：图层按列表顺序叠加，最后添加的画在最上面
        if ots_fg:
            fg_tag = (cast.get(ots_fg) or [ots_fg])[0]
            fg_layer = next((l for l in layers[1:] if l["name"] == fg_tag), None)
            if fg_layer is not None and layers.index(fg_layer) != len(layers) - 1:
                layers.remove(fg_layer)
                layers.append(fg_layer)

        panel = {
            "id": f"p{idx + 1}",
            "seconds": secs,
            "title": (title or sid)[:24],
            "caption": (pick(f, "目的") or pick(f, "唯一动作") or body)[:160],
            "shot": shot_text(body, names, cast, placed),
            "first_frame": False,
            "last_frame": False,
            "layers": layers,
        }
        panels.append(panel)
        meta.append({
            "id": panel["id"], "sid": sid, "seconds": secs,
            "sound": pick(f, "声音", "音效"), "voice": pick(f, "音色"),
            "shot": panel["shot"], "caption": panel["caption"],
        })

    doc = {
        "format": "h3-storyboard", "schema_version": 1,
        "id": opts.storyboard_id or "sb-converted",
        "title": opts.title or "", "subtitle": opts.subtitle or "",
        "aspect": aspect, "idea": opts.idea or "",
        "panels": panels, "library": library,
    }
    if opts.max_panels and len(panels) > opts.max_panels:
        notes.append(
            f"共 {len(panels)} 镜，超过 NGStoryboard 上限 {opts.max_panels} 个面板——"
            f"已只写入前 {opts.max_panels} 个；其余请按场次拆成第二张故事板")
        panels = panels[:opts.max_panels]
        doc["panels"] = panels
    notes.insert(0, f"共 {len(shots)} 镜，总时长 {total:.2f}s，画幅 {aspect}")
    return doc, notes, [p["title"] for p in panels], meta[:len(panels)]


def shot_text(body: str, names: List[str], cast: Dict[str, List[str]],
              placed: List[Tuple[str, float]]) -> str:
    """把正文里的人名换成 @代称；正文没点名时补一句入画声明。

    H3 的 <Subject N> 只认提示词里写到的名字（NG 文档：@Name 指代卡名，
    分镜稿正文常写「a twenty-six-year-old man」，不点名就没法绑定），
    所以名字缺失时补 `In frame: @A at frame left.` 这类前置声明。
    """
    text = body
    pairs: List[Tuple[str, str]] = []
    for cn in names:
        aliases = cast.get(cn) or []
        tag = aliases[0] if aliases else cn
        for lit in [cn] + aliases:
            if lit:
                pairs.append((lit, tag))
    pairs.sort(key=lambda p: -len(p[0]))
    for lit, tag in pairs:
        text = name_pattern(lit).sub(f"@{tag}", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    missing = []
    for tag, x in placed:
        if "@" + tag in text:
            continue
        where = "at frame left" if x < 0.45 else ("at frame right" if x > 0.55 else "at frame centre")
        missing.append(f"@{tag} {where}")
    if missing:
        text = "In frame: " + ", ".join(missing) + ". " + text
    return text


# ---------------------------------------------------------------- 注入模板

NEG_PROMPT_02 = ("text, subtitles, watermark, logo, split screen, deformed hands, "
                 "extra fingers, blurry face, lowres")


def find_timeline_widget(node: dict) -> Tuple[Optional[int], Optional[dict]]:
    """在节点的 widgets_values 里找装着 segments 时间线的那个 JSON 字符串。

    不同模板的索引不同（通用02 在 10、EP001 产物在 11），按内容找才稳。"""
    for i, v in enumerate(node.get("widgets_values", [])):
        if isinstance(v, str) and v.lstrip().startswith("{"):
            try:
                d = json.loads(v)
            except Exception:
                continue
            if isinstance(d, dict) and "segments" in d:
                return i, d
    return None, None


def snap_frames(seconds: float, fps: int) -> Tuple[int, int]:
    """把秒数折成 02 线合法段长：17 的整数倍，夹在 [102, 204]。返回 (原帧, 合法帧)。"""
    raw = int(round(seconds * fps))
    legal = int(round(raw / 17.0)) * 17
    legal = max(102, min(204, legal))
    return raw, legal


def build_segments_02(doc: dict, meta: List[dict], fps: int) -> Tuple[List[dict], float, List[str]]:
    """panels → MiniMaxH3Director 的 segments（r2v 草稿）。

    refs 顺序按 FAQ Q13 的槽位优先级：说话人物在前、场景板收尾；段长对齐 17 网格并
    夹进产能区间 [102, 204]。prompt 是官方七段结构的**草稿**——subject_definitions
    与人声质地要出片前手工补全。"""
    notes: List[str] = []
    segments: List[dict] = []
    t = 0.0
    for n, p in enumerate(doc["panels"]):
        raw, frames = snap_frames(p["seconds"], fps)
        if raw != frames:
            notes.append(f"{p['id']} {p['seconds']}s→{raw} 帧不在产能区间（102~204、17 的整数倍），"
                         f"段长已对齐到 {frames} 帧（{frames / fps:.2f}s）")
        m = (meta[n] if n < len(meta) else {})
        snd = (m.get("sound") or "").strip()
        voice = (m.get("voice") or "").strip().lower()
        # @代称 是 NG 线的绑定方式；r2v 线靠 refs 槽位绑定，写回普通名字
        shot_plain = re.sub(r"@([A-Za-z0-9_]+)", r"\1", p["shot"])
        prompt_lines = [
            "subject_definitions: identity comes from the attached reference images, not from text descriptions.",
            f"summary: {p['title']}.",
            "retention_analysis: identity strictly preserved from <Picture 1>; location partially preserved (fixed architectural anchors).",
            f"detailed_description: {shot_plain}",
            f"overall_soundscape: {snd}" if snd else "overall_soundscape: quiet location ambience; no dialogue",
            "non_diegetic_music: N/A",
        ]
        if voice and voice != "none":
            prompt_lines.append("Audio: reference")
        refs = []
        ridx = 1
        for l in p["layers"][1:]:  # 人物在前
            src = l.get("src") or {}
            refs.append({"index": ridx, "imageFile": src.get("filename", ""),
                         "fileName": "", "type": "input", "subfolder": src.get("subfolder", "")})
            ridx += 1
        bg = p["layers"][0] if p["layers"] else None
        if bg is not None:
            src = bg.get("src") or {}
            refs.append({"index": ridx, "imageFile": src.get("filename", ""),
                         "fileName": "", "type": "input", "subfolder": src.get("subfolder", "")})
        segments.append({
            "id": f"seg_{n + 1:03d}", "start": round(t, 3),
            "length": frames, "frameCount": frames,
            "durationSec": round(frames / fps, 3),
            "prompt": "\n".join(prompt_lines),
            "negativePrompt": NEG_PROMPT_02,
            "taskType": "r2v", "refs": refs, "refAudios": [], "refVideos": [], "genImage": "",
        })
        t += frames / fps
    return segments, t, notes


def patch_workflow(template_path: str, doc: dict, meta: List[dict], out_path: str,
                   fps: int = 24) -> List[str]:
    wf = json.load(io.open(template_path, encoding="utf-8"))
    notes: List[str] = []
    board = director02 = None
    for n in wf.get("nodes", []):
        if n.get("type") == "NGStoryboard" and board is None:
            board = n
        elif n.get("type") == "MiniMaxH3Director" and director02 is None:
            director02 = n

    if board is not None:
        # ---- NG 线（06 故事板）：原路径不动
        board.setdefault("widgets_values", [""])
        board["widgets_values"][0] = json.dumps(doc, ensure_ascii=False)
        director = next((n for n in wf.get("nodes", []) if n.get("type") == "NGH3Director"), None)
        if director is not None and len(director.get("widgets_values", [])) > 2:
            wv = director["widgets_values"]
            try:
                old = json.loads(wv[1])
            except Exception:
                old = {}
            shots, t = [], 0.0
            for p in doc["panels"]:
                shots.append({
                    "id": f"sb-{p['id']}", "start": round(t, 2), "end": round(t + p["seconds"], 2),
                    "text": p["shot"], "media": [], "spoken": [], "locked_fields": [], "draft": None,
                })
                t += p["seconds"]
            new = {
                "format": "h3-director-shots", "schema_version": 1, "shots": shots,
                "audio": old.get("audio", []), "audio_lanes": old.get("audio_lanes", []),
                "look": old.get("look", ""),
            }
            wv[1] = json.dumps(new, ensure_ascii=False)
            wv[2] = round(t, 2)
            notes.append(f"Director 已写入 {len(shots)} 个 shot、Duration={t:.2f}s（media 留空，"
                         f"进 ComfyUI 后按 Use in Director → Send to Director 补故事板卡）")
        else:
            notes.append("模板里没找到 NGH3Director 或参数不足，只替换了故事板")
        notes.append("角色卡仍是模板里的示例人物（Luna / Inferna），记得在 ComfyUI 里换成你的身份板并改卡名——@代称 要与卡名一致")
    elif director02 is not None:
        # ---- 02 线（通用 r2v）：panels → segments
        wi, tl = find_timeline_widget(director02)
        if tl is None:
            raise SystemExit("MiniMaxH3Director 里找不到含 segments 的时间线 JSON，无法注入")
        segments, t, seg_notes = build_segments_02(doc, meta, fps)
        notes.extend(seg_notes)
        tl["segments"] = segments
        tl["totalFrames"] = int(round(t * fps))
        tl["durationSec"] = round(t, 3)
        director02["widgets_values"][wi] = json.dumps(tl, ensure_ascii=False)
        notes.append(f"MiniMaxH3Director 已写入 {len(segments)} 个 segment、总时长 {t:.2f}s"
                     f"（taskType=r2v、refs=人物+场景、negativePrompt 已填英文）")
        notes.append("音色参考是手工步骤：refAudios 全部留空——出片前在 Director 里给有台词的段挂上 wav，"
                     "并确认段尾有 Audio: reference")
        notes.append("refs 现在指向分镜抠图/占位图；正式出片建议换成身份板 SHEET 与场景板 PLATE "
                     "（参考图是语义参考，抠图缩不出脸）")
        notes.append("prompt 是七段结构草稿：subject_definitions、人声质地、道具音/环境底的空间词"
                     "建议按 voice-layer-craft.md 手工补全后再跑 25 步")
        out_ratio = doc.get("aspect", "")
        if "9:16" in str(out_ratio) or "vertical" in str(out_ratio):
            notes.append(f"分镜画幅是 {out_ratio}，模板 output 固定 16:9（1344x768）——竖屏出片把 "
                         f"output.aspectRatio 改 9:16、width/height 改 768x1344")
    else:
        raise SystemExit("模板里没有 NGStoryboard 也没有 MiniMaxH3Director 节点")
    io.open(out_path, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
    return notes


# ---------------------------------------------------------------- CLI

def parse_kv(items: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for it in items or []:
        if "=" in it:
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--out", required=True)
    ap.add_argument("--visual", help="《视觉设定.md》，用来取 画面代称 与画幅；同目录存在则自动读")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--aspect")
    ap.add_argument("--bg", action="append", default=[], help='背景图；"地点名=文件" 或只给文件')
    ap.add_argument("--figure", action="append", default=[], help='人物抠图；"名字=文件.webp"')
    ap.add_argument("--cast", action="append", default=[], help='中文名=画面代称；没有《视觉设定.md》时补')
    ap.add_argument("--max-panels", type=int, default=9)
    ap.add_argument("--scene", help="只转换指定场次：逗号分隔场次 ID（SC01 或 EP001-SC001），"
                                    "按分镜「来源」字段匹配")
    ap.add_argument("--shots", help="只转换指定镜：逗号分隔镜号尾段或区间（001,004 或 001-005）")
    ap.add_argument("--storyboard-id")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--idea")
    ap.add_argument("--workflow", help="06-故事板-双角色.json 模板，注入后另存")
    ap.add_argument("--out-workflow")
    ap.add_argument("--json-report", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.storyboard):
        print(f"找不到 {a.storyboard}")
        return 2
    text = read_text(a.storyboard)

    visual_path = a.visual
    if not visual_path:
        guess = os.path.join(os.path.dirname(os.path.abspath(a.storyboard)), "视觉设定.md")
        visual_path = guess if os.path.exists(guess) else None
    visual_text = read_text(visual_path) if visual_path else ""

    bg_items = parse_kv(a.bg)
    a.bg_map = {k: v for k, v in bg_items.items() if k}
    a.bg_default = next((v for k, v in bg_items.items() if not k), "")
    a.bg_name = next((k for k in bg_items if k), "Background")
    a.fig_map = parse_kv(a.figure)
    # 未给出抠图时按 06 模板的示例素材顺序占位，保证面板能画出来
    placeholders = ["h3-example-luna-figure.webp", "h3-example-inferna-figure.webp"]
    a.fig_placeholder = {}

    a.scene_sel = [s.strip() for s in (a.scene or "").split(",") if s.strip()]
    a.shot_sel = [s.strip() for s in (a.shots or "").split(",") if s.strip()]

    shots = split_shots(text)
    if not shots:
        print("没解析到 `## SHOT-xxx · 名称` 镜头块")
        return 1

    # 先按出镜顺序分配占位图，再交给 build
    cast = parse_cast(visual_text) if visual_text else {}
    order: List[str] = []
    for _sid, _t, block in shots:
        for m in PERSON_RE.finditer(pick(fields_of(block), "视觉依据")):
            n = m.group(1).strip()
            if n not in order:
                order.append(n)
    for i, cn in enumerate(order):
        if i < len(placeholders):
            a.fig_placeholder[cn] = placeholders[i]

    try:
        doc, notes, _titles, meta = build(text, visual_text, a)
    except SystemExit as exc:
        print(exc)
        return 1
    except Exception as exc:  # 解析期异常统一报错，不吞
        print(f"转换失败：{exc}")
        return 2

    io.open(a.out, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"写出 {a.out}（{len(doc['panels'])} 个面板 / {len(doc['library'])} 条素材）")
    for p in doc["panels"]:
        parts = []
        for l in p["layers"][1:]:  # 第 0 层恒为背景
            parts.append(f"{l['name']} x={l['x']:.2f} y={l['y']:.2f} s={l['scale']:.2f}")
        print(f"  {p['id']} {p['seconds']:>5.2f}s {p['title'][:20]:<22} {' | '.join(parts) or '（无人物图层）'}")

    if a.workflow:
        out_wf = a.out_workflow or os.path.splitext(a.out)[0] + ".workflow.json"
        notes.extend(patch_workflow(a.workflow, doc, meta, out_wf, fps=a.fps))
        print(f"写出 {out_wf}")

    if notes:
        print(f"\n提示（{len(notes)}）：")
        for n in notes:
            print(f"  - {n}")
    if a.json_report:
        print("\n" + json.dumps({"notes": notes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
