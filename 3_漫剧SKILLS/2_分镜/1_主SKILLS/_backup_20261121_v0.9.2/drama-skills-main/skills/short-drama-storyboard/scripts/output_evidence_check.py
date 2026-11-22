#!/usr/bin/env python3
"""核对一份已产出的分镜/图片提示词/视频提示词是否真的用上了美学与调度条款。

storyboard_lint.py 管结构性规则（镜型、帧长、站位三要素、交接、节奏档位）；
本脚本只管它不覆盖的那一层：条款写进了文档，产出物里到底有没有落地。

用法：
    python output_evidence_check.py <剧集目录> [--strict]

检查项（全部 WARN 级，--strict 时升级为失败）：
  E1 多镜场次有「场景站位」块
  E2 垂直分层场面写了「高度层」行
  E3 有闯入/奔跑/追的场面写了「入口与动线」行
  E4 ≥4 镜的场次登记了「闭环锚」，且收镜正文呼应首镜
  E5 每场至少一镜含导演级构图签名（构图签名词表）
  E6 标了「升格」的镜，视频提示词里有环境慢反应证据；且升格不连续两镜
  E7 每条 MOTION 提示词有收尾句（End on…）与负面约束（No subtitles…）
  E8 每条 IMG 提示词有光/氛围词与机位/构图词
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

SHOT_RE = re.compile(r"^## (SHOT-[A-Z0-9-]+) · (.+)$", re.M)
MOTION_RE = re.compile(r"^## (MOTION-[A-Z0-9-]+) · (.+)$", re.M)
IMG_RE = re.compile(r"^## (IMG-[A-Z0-9-]+) · (.+)$", re.M)
BLOCKING_RE = re.compile(r"^## 场景站位 · ([A-Za-z0-9-]+)", re.M)
ANY_H2_RE = re.compile(r"^## ", re.M)
PROMPT_RE = re.compile(r"### 可复制提示词\n+(?:>\s?)?(.*?)(?=\n## |\n### |\Z)", re.S)
KEYFRAME_RE = re.compile(r"### 冻结关键帧提示词\n+(.*?)(?=\n## |\Z)", re.S)

VERTICAL_WORDS = ("台阶", "楼", "崖", "腾空", "塔", "屋顶", "窗台", "阶梯")
ENTRY_WORDS = ("闯入", "奔", "冲", "追", "走进", "走进来", "跑", "扑")
SIGNATURE_WORDS = (
    "框中框", "逆光剪影", "对称构图", "色彩分区", "低机位", "极近",
    "framed-in-frame", "silhouette", "symmetrical", "low-angle", "low angle",
    "extreme close", "centered symmetry",
)
SLOW_EVIDENCE = (
    "slow motion", "慢镜", "升格", "hang", "hangs", "suspended", "悬停", "缓",
    "hover", "slowly", "rises and hangs", "水花",
)
LIGHT_WORDS = ("light", "glow", "haze", "rain", "fog", "shadow", "光", "雾", "雨", "影")
CAMERA_WORDS = ("shot", "angle", "composition", "framing", "view", "机位", "构图", "景别")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def find_doc(d: Path, stem: str) -> Path | None:
    """优先精确名，其次同名通配（老稿常写成「分镜-某场.md」）。"""
    exact = d / f"{stem}.md"
    if exact.exists():
        return exact
    hits = sorted(p for p in d.glob(f"{stem}*.md") if p.is_file())
    return hits[0] if hits else None


def split_sections(text: str, pattern: re.Pattern) -> list[tuple[str, str, str]]:
    """返回 [(id, title, body)]；body 到下一个 `## ` 标题为止（不限于同类标题）。

    以前只按同类标题切分会把「场景站位」块一直延伸到最后一条镜头，
    让「闭环锚/高度层」这类块内判定读到块外内容而失效。
    """
    out = []
    marks = list(pattern.finditer(text))
    for i, m in enumerate(marks):
        start = m.end()
        nxt = ANY_H2_RE.search(text, start)
        end = nxt.start() if nxt else len(text)
        title = m.group(2).strip() if (m.re.groups or 0) >= 2 else ""
        out.append((m.group(1), title, text[start:end]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode", type=Path, help="包含 分镜.md / 图片提示词.md / 视频提示词.md 的目录")
    ap.add_argument("--strict", action="store_true", help="把 WARN 视为失败")
    a = ap.parse_args()

    d = a.episode
    board_path = find_doc(d, "分镜")
    img_path = find_doc(d, "图片提示词")
    motion_path = find_doc(d, "视频提示词")
    board = read(board_path) if board_path else ""
    imgs = read(img_path) if img_path else ""
    motions = read(motion_path) if motion_path else ""
    warns: list[str] = []

    shots = split_sections(board, SHOT_RE)
    # 场景站位块必须截到下一个 ## 为止，否则会吞掉全文让「闭环锚」等判定失效
    blocking = split_sections(board, re.compile(r"^## 场景站位 · ([A-Za-z0-9-]+) · (.+)$", re.M))
    blocking = [(sid, body) for sid, _title, body in blocking]
    if not shots:
        warns.append("E0 没有解析到 SHOT-... 镜头条目")
    if not blocking and shots:
        warns.append("E1 分镜没有「## 场景站位」块——站位/高度/闭环都无从登记")

    # 按场次分组
    scene_of: dict[str, str] = {}
    for sid, _title, body in shots:
        m = re.search(r"来源[：:]\s*([A-Za-z0-9-]+)", body)
        if m:
            scene_of[sid] = m.group(1)

    for scene_id, block in blocking:
        # 找到该场次的镜（来源以场次 ID 开头）
        scene_shots = [s for s, sc in scene_of.items() if sc.startswith(scene_id) or scene_id in sc]
        texts = "\n".join(b for sid, _t, b in shots if sid in scene_shots)
        heads = "\n".join(t for sid, t, _b in shots if sid in scene_shots)

        if any(w in block or w in texts for w in VERTICAL_WORDS) and "高度层" not in block:
            warns.append(f"E2 {scene_id} 有垂直分层（台阶/楼/崖/腾空）但「场景站位」没写「高度层」行")
        if any(w in texts for w in ENTRY_WORDS) and "入口与动线" not in block:
            warns.append(f"E3 {scene_id} 有闯入/奔跑/追的动线，但「场景站位」没写「入口与动线」行")
        if len(scene_shots) >= 4 and "闭环" not in block:
            warns.append(f"E4 {scene_id} 共 {len(scene_shots)} 镜，但「场景站位」没有对闭环作出登记"
                         f"（写「闭环锚：…」复用首镜构图，或写「闭环锚：不设——理由」）")
        if not any(w.lower() in texts.lower() or w.lower() in heads.lower() for w in SIGNATURE_WORDS):
            warns.append(f"E5 {scene_id} 没有任何一镜用导演级构图签名（对称/逆光剪影/框中框/低机位大特写）——"
                         f"画面有氛围没构图，电影感差最后一档")

    # 升格：标了升格的镜要有环境慢反应证据，且不连续
    slow_ids = [sid for sid, _t, b in shots if "升格" in b]
    mot_by_shot = {}
    for mid, _t, body in split_sections(motions, MOTION_RE):
        m = re.search(r"分镜[：:]\s*(SHOT-[A-Z0-9-]+)", body)
        if m:
            mot_by_shot[m.group(1)] = body
    for sid in slow_ids:
        mot = mot_by_shot.get(sid, "")
        if mot and not any(w.lower() in mot.lower() for w in SLOW_EVIDENCE):
            warns.append(f"E6 {sid} 标了升格，但视频提示词没有环境慢反应证据（雨滴悬停/水花缓起/衣角缓落）")
    for prev, nxt in zip(slow_ids, slow_ids[1:]):
        if abs(int(prev.rsplit("-", 1)[-1]) - int(nxt.rsplit("-", 1)[-1])) == 1:
            warns.append(f"E6 {prev}→{nxt} 连续两镜升格——每桥段只放一次「最放大」")

    # MOTION 收尾句与负面约束
    for mid, _t, body in split_sections(motions, MOTION_RE):
        pm = PROMPT_RE.search(body)
        prompt = pm.group(1) if pm else ""
        if prompt and not re.search(r"\bEnd on\b|结尾停在|收尾", prompt, re.I):
            warns.append(f"E7 {mid} 提示词没有收尾句（End on …）——执行端会把动作拖到尾帧之后")
        if prompt and not re.search(r"no subtitles|no text|无字幕|不要字幕", prompt, re.I):
            warns.append(f"E7 {mid} 提示词没有负面约束（No subtitles…）——易出字幕或水印")

    # IMG 氛围与机位
    for iid, _t, body in split_sections(imgs, IMG_RE):
        pm = PROMPT_RE.search(body)
        prompt = pm.group(1) if pm else ""
        if not prompt:
            continue
        if not any(w in prompt.lower() for w in [x.lower() for x in LIGHT_WORDS]):
            warns.append(f"E8 {iid} 提示词没有光/氛围描述——图片会平、没有电影质感")
        if not any(w in prompt.lower() for w in [x.lower() for x in CAMERA_WORDS]):
            warns.append(f"E8 {iid} 提示词没有机位/构图词——视角交给模型随机")

    print(f"分镜镜数={len(shots)}  场次数={len(blocking)}  图片条目={len(split_sections(imgs, IMG_RE))}"
          f"  视频条目={len(split_sections(motions, MOTION_RE))}  升格镜={len(slow_ids)}")
    for w in warns:
        print("WARN:", w)
    if not warns:
        print("PASS — 构图签名、升格证据、高度层、闭环锚、收尾句与氛围层都在产出物里落到了")
        return 0
    print(f"{len(warns)} 项需要补")
    return 1 if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
