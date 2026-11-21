#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游生成器：从 drama《视频提示词.md》生成生产线三件套。

实跑 n7_build.py 泛化：解析 `## MOTION-<EP>-<NNN> · 标题` 块，抽取时长/参考图/六段式，
自动生成：
  1. shotlist.csv          —— csv_to_timeline.py / frames_common.py 的输入（19+列）
  2. n5_inputs.json        —— 出帧四段材料草稿（identity/frozen_keyframe 需人工补）
  3. scene_bible.txt       —— 场景圣经草稿（从各镜 detailed_description 的公共场景句抽取提示）

生成的 CSV 是草稿：PLAN→资产路径映射需按项目改 --plan-map，身份块/冻结关键帧需人工填。
脚本不臆造——解析不到的字段留空并标注，绝不从详细描写反推起始帧（经验库边界）。

用法：
  python prepare_project.py --motion-md <视频提示词.md> --project 街对面 --ep EP001 \\
      --out-dir out/prepared \\
      --plan-map 'PLAN-SU-SHEET=街对面/chars/IMG-SU-SHEET.png;PLAN-CAFE=街对面/scenes/IMG-CAFE.png'
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

SECTIONS = ["subject_definitions", "summary", "retention_analysis",
            "detailed_description", "overall_soundscape", "non_diegetic_music"]


def snap(n: int) -> int:
    """向上对齐 H3 的 17k+5 帧网格（实跑 n7_build.snap）。"""
    n = max(5, int(round(n)))
    while n % 17 != 5:
        n += 1
    return n


def parse_motion(md: Path) -> list[dict]:
    lines = md.read_text(encoding="utf-8").splitlines()
    shots: list[dict] = []
    cur: dict | None = None
    in_prompt = False
    for ln in lines:
        m = re.match(r"^## MOTION-[^-]+?-(\d{3})\s*·\s*(.+?)\s*$", ln)
        m2 = re.match(r"^## MOTION-\w+-(\d{3})\s*·\s*(.+?)\s*$", ln)
        mm = m or m2
        if mm:
            if cur:
                shots.append(cur)
            cur = {"num": mm.group(1), "title": mm.group(2), "prompt": {}, "meta": {}}
            in_prompt = False
            continue
        if cur is None:
            continue
        if ln.startswith("### 可复制提示词"):
            in_prompt = True
            continue
        if ln.startswith("## "):
            in_prompt = False
            continue
        if in_prompt:
            if ln.startswith("> "):
                body = ln[2:].strip()
                if ":" in body:
                    k, v = body.split(":", 1)
                    if k.strip() in SECTIONS:
                        cur["prompt"][k.strip()] = v.strip()
            continue
        for key, field in (("- 时长：", "dur"), ("- 生成方式：", "mode"),
                           ("- 输入参考图：", "refs"), ("- 起始帧：", "start"),
                           ("- 状态链：", "chain"), ("- 终点：", "end")):
            if ln.startswith(key):
                cur["meta"][field] = ln[len(key):].strip()
                break
    if cur:
        shots.append(cur)
    return shots


def parse_plan_map(spec: str) -> dict[str, str]:
    out = {}
    for part in spec.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip().replace("\\", "/")
    return out


def refs_paths(spec: str, shot_num: str, project: str, plan_map: dict, ep: str = "") -> list[str]:
    """从「PLAN-X（顺序：N）· 文件名《...》」抽取，按 order 返回 4 槽路径（缺留空）。"""
    slots: dict[int, str] = {}
    for m in re.finditer(r"(PLAN-[A-Z0-9-]+)（顺序：(\d+)）·\s*([^\s《]+)", spec):
        plan, order, fname = m.group(1), int(m.group(2)), m.group(3)
        order -= 1  # 提示词里 <Picture N> 是 1 基
        if plan == "PLAN-SHOT-START":
            label = ep or project
            path = f"{project}/frames/SHOT-{label}-{shot_num}.png"
        elif plan in plan_map:
            path = plan_map[plan]
        else:
            path = f"{project}/unmapped/{fname}"  # 未映射，显式标注便于人工补
        if 0 <= order < 4:
            slots[order] = path
    return [slots.get(i, "") for i in range(4)]


def build_scene_bible_draft(shots: list[dict]) -> str:
    """从各镜 detailed_description 抽最长公共场景句作草稿（只是草稿，需人工定稿）。"""
    frags = []
    for s in shots:
        d = s["prompt"].get("detailed_description", "")
        # 抓第一句含场景/room/table/window 的短句
        for sent in re.split(r"(?<=[.;。])\s+", d):
            if re.search(r"\b(room|cafe|window|table|stair|floor|corridor)\b", sent, re.I) and 20 < len(sent) < 260:
                frags.append(sent.strip())
                break
    if not frags:
        return "scene_bible (fixed location): <人工填写：唯一场景、窗位/楼梯方位、桌面固定道具与位置、光线方向、色调>"
    common = max(set(frags), key=frags.count)
    return ("scene_bible (fixed location bible, applies to every shot, never contradict it):\n"
            + common + "\n"
            + "Furniture positions, window layout, prop placement and light direction stay identical in every shot; "
              "only camera angle and which characters are in frame may change.\n"
            + "# NOTE: 草稿，仅取各镜高频场景句。请人工补全位置级道具锁定（经验库 3.6）后再用 --scene-bible 装配。")


def main() -> None:
    ap = argparse.ArgumentParser(description="视频提示词.md → shotlist.csv / n5_inputs / scene_bible 草稿")
    ap.add_argument("--motion-md", type=Path, required=True)
    ap.add_argument("--project", required=True, help="项目名（资产 subfolder 第一段）")
    ap.add_argument("--ep", default="", help="集号（用于起始帧命名，可空）")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--plan-map", default="", help="'PLAN-X=相对input路径;PLAN-Y=...'")
    ap.add_argument("--negative", default=("text, subtitles, watermark, occlusion, panel grid, extra persons, "
                                            "modern objects, blur, ghosting, deformed fingers, cropped feet"))
    a = ap.parse_args()

    shots = parse_motion(a.motion_md)
    if not shots:
        raise SystemExit("未解析到任何 ## MOTION-* 块")
    plan_map = parse_plan_map(a.plan_map)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    csv_rows: list[dict] = []
    n5_shots: dict = {}
    for s in shots:
        n = s["num"]
        dur = float(re.sub(r"[^0-9.]", "", s["meta"].get("dur", "4.25")) or 4.25)
        frames = snap(dur * a.fps)
        p1, p2, p3, p4 = refs_paths(s["meta"].get("refs", ""), n, a.project, plan_map, a.ep)
        block = s["prompt"]
        # 台词可能在 detailed_description（lips synced）或 overall_soundscape，扫全部六段式
        dialogue = " / ".join(re.findall(r"「(.+?)」", " ".join(block.values())))
        sound = block.get("overall_soundscape", "")
        has_dlg = bool(dialogue)
        audio_tag = "reference" if has_dlg else "none"
        voice = plan_map.get("PLAN-VOICE", "")
        row = {
            "shot_id": f"S{n}", "continuity_group": "G01",
            "length_frames": frames, "duration_sec": round(frames / a.fps, 3),
            "frame_key": p1, "ref_role_sheet": p2, "ref_scene_plate": p3,
            "ref_costume_pair": p4, "ref_voice": voice if audio_tag == "reference" else "",
            "ref_voice_2": "", "ref_voice_3": "",
            **{k: block.get(k, "") for k in SECTIONS},
            "audio_tag": audio_tag, "negative_prompt": a.negative,
            "seed": 42020000 + int(n) * 17, "qc_status": "待审",
        }
        csv_rows.append(row)
        n5_shots[f"S{n}"] = {
            "identity_block": "<人工填：C 编号块逐字复制 asset-blocks.md>",
            "frozen_keyframe": s["meta"].get("start", "") or "<人工填：该镜冻结关键帧提示词>",
        }

    csv_path = a.out_dir / "shotlist.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        w.writerows(csv_rows)

    n5 = {
        "_note": "出帧四段材料草稿。identity_block/frozen_keyframe 需人工补全；style_sentence 全片同一句。",
        "style_sentence": "<人工填：项目视觉方向 + comic-keyframe-lexicon 基底>",
        "constraints": ("16:9 landscape; no speech bubbles, no subtitles, no text, no logo, no panel lines, "
                        "no watermark; no extra persons; if two characters share the frame they face each other "
                        "left and right, never side by side"),
        "edit1_instruction": "Preserve exactly the opening composition of image_1. Lock identity from image_2, space from image_3. No motion, no text.",
        "edit2_instruction": "Keep identity and composition from image_1. Match outfit and positions from image_2. No text, no extra persons.",
        "shots": n5_shots,
    }
    n5_path = a.out_dir / "n5_inputs.json"
    n5_path.write_text(json.dumps(n5, ensure_ascii=False, indent=2), encoding="utf-8")

    bible = build_scene_bible_draft(shots)
    bible_path = a.out_dir / "scene_bible.txt"
    bible_path.write_text(bible, encoding="utf-8")

    print(f"OK  {len(shots)} 镜 → {csv_path} / {n5_path} / {bible_path}")
    has_voice = any(r["ref_voice"] for r in csv_rows)
    print("注意：" + ("ref_voice 已按 PLAN-VOICE 填入，请核对声音声明顺序是否对应 ref_voice_2/3；"
                    if has_voice else "未在 plan-map 声明 PLAN-VOICE，对白镜的 ref_voice 留空需人工补；")
          + "n5_inputs 的身份块/冻结关键帧需人工补全。")


if __name__ == "__main__":
    main()
