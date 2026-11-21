#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frames_common.py — 前半段「逐镜漫画格」出帧脚本的共享层

被两个前端复用：
  * frames_from_shotlist_comfy.py  (默认：本地 ComfyUI /prompt，三阶段)
  * frames_from_shotlist.py        (备选：火山方舟 Seedream /images/generations)

职责（不碰 H3 装配层）：
  1. 读同一份 shotlist.csv（直接复用 csv_to_timeline.load_rows，保证 19 字段契约唯一真源）
  2. 四段重组出图 prompt（drama 冻结关键帧 + C 身份块 + 全片画风句 + 约束）
  3. 相对 input/ 根的路径契约校验（复用装配器的 PATH_CONTRACT / check_path_contract）
  4. 每镜路径推导、三阶段 seed、frame_key 回填、归档 manifest

重要边界
--------
* drama 的「### 冻结关键帧提示词」与 C/S/P 编号块**不在 shotlist.csv 里**（CSV 装的是 H3
  六段式视频 prompt）。因此四段重组所需材料由 --inputs 指向的 JSON 提供，脚本绝不从
  detailed_description 臆造起始帧——那是动作结果，画进 <Picture 1> 会毁掉整镜。
  用 --emit-inputs-template 生成待填模板。
* N5 只回填 frame_key；三张板、音色、六段式由 N4/N6/drama 负责，脚本不越界改这些列。
* 默认本地 ComfyUI 路线里，底图与 Pass 1 中间帧是内部产物，落 work/，不进 frames/、不挂 H3。
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

# 路径契约与 CSV 读取直接复用后半段装配器，避免两处口径漂移
from csv_to_timeline import (  # noqa: E402
    PATH_CONTRACT,
    check_path_contract,
    load_rows as load_shotlist_rows,
)

BASE = Path(__file__).resolve().parent
DEFAULT_CSV = BASE / "shotlist_vibe_template.csv"
DEFAULT_MANIFEST = BASE / "out" / "frames_manifest.jsonl"

DEFAULT_CONSTRAINTS = (
    "16:9 landscape; no speech bubbles, no subtitles, no text, no logo, "
    "no panel lines, no watermark; no extra persons; if two characters share "
    "the frame they face each other left and right, never side by side"
)
DEFAULT_EDIT1 = (
    "Preserve exactly the opening composition, subject placement and light "
    "direction of image_1. Lock the character identity, face shape, hairstyle "
    "and costume from image_2 (character sheet). Lock the space, depth and "
    "window order from image_3 (scene plate). Do not change camera angle or "
    "pose; add no motion, no text."
)
DEFAULT_EDIT2 = (
    "Keep identity and composition from image_1. Match the outfit details and "
    "the two-person standing positions from image_2 (costume/position pair). "
    "No text, no speech bubbles, no extra persons."
)

# 出图工具不认的 H3 / drama 语义标签（操作卡 Step 2 验收）
H3_LABELS = re.compile(
    r"<Picture\s*\d+>|<Subject\s*\d+>|<Audio\s*\d+>|REF-[A-Z0-9\-]+|"
    r"顺序\s*[：:]|视觉依据\s*[：:]|用途\s*[：:]"
)


def out(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(2)


# ---------------------------------------------------------------- 材料（四段重组）

def default_inputs_template(rows: list[dict]) -> dict:
    return {
        "_note": (
            "逐镜出图材料。identity_block 逐字复制 drama 导出/asset-blocks.md 的 C 编号块；"
            "frozen_keyframe 取该镜 分镜.md 的 ### 冻结关键帧提示词（去掉 <Picture N>/REF-/顺序 等 "
            "H3 标签，只写这一瞬间看得见的）；style_sentence 全片同一句；constraints 全片同一份。"
            "不要把 视频提示词.md 的六段式或台词填进来。"
        ),
        "style_sentence": "<项目视觉方向 + comic-keyframe-lexicon 基底，全片同一句>",
        "constraints": DEFAULT_CONSTRAINTS,
        "edit1_instruction": DEFAULT_EDIT1,
        "edit2_instruction": DEFAULT_EDIT2,
        "shots": {
            r["shot_id"]: {
                "identity_block": "<C 编号块逐字复制：脸型／发型／服装／辨识物，全片不变>",
                "frozen_keyframe": "<该镜冻结关键帧提示词，去掉 H3 标签，只写这一瞬间>",
            }
            for r in rows
        },
    }


def emit_inputs_template(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(default_inputs_template(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out(f"[OK] 已生成待填材料模板：{path}")
    out("     填好 identity_block / frozen_keyframe / style_sentence 后，用 --inputs 指回它。")


def load_n5_inputs(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.is_file():
        die(f"--inputs 指向的材料文件不存在：{path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("shots"), dict):
        die("--inputs JSON 必须含 shots 字典（键为 shot_id）")
    return doc


def compose_prompt(inputs: dict | None, shot_id: str,
                   errors: list[str]) -> str | None:
    """四段重组。材料缺失时返回 None 并把原因写进 errors（由调用方决定阻断还是演示）。"""
    if inputs is None:
        errors.append(
            f"{shot_id}: 缺 --inputs 材料（drama 冻结关键帧 / C 编号块 / 画风句）；"
            "先用 --emit-inputs-template 生成并填好，再用 --inputs 指回"
        )
        return None
    shots = inputs.get("shots", {})
    m = shots.get(shot_id)
    if not isinstance(m, dict):
        errors.append(f"{shot_id}: --inputs 里没有该镜的四段材料")
        return None
    identity = (m.get("identity_block") or "").strip()
    keyframe = (m.get("frozen_keyframe") or "").strip()
    style = (inputs.get("style_sentence") or "").strip()
    constraints = (inputs.get("constraints") or DEFAULT_CONSTRAINTS).strip()
    for label, value in (("identity_block", identity),
                         ("frozen_keyframe", keyframe),
                         ("style_sentence", style)):
        if not value or value.startswith("<"):
            errors.append(f"{shot_id}: {label} 未填写（仍是占位符）")
    prompt = (
        f"[1 身份锚]\n{identity}\n\n"
        f"[2 本镜正文]\n{keyframe}\n\n"
        f"[3 画风句]\n{style}\n\n"
        f"[4 约束]\n{constraints}"
    )
    bad = sorted(set(H3_LABELS.findall(prompt)))
    if bad:
        errors.append(f"{shot_id}: 重组后 prompt 仍含 H3/drama 标签 {bad}，出图工具不认")
    return prompt


def edit_instructions(inputs: dict | None) -> tuple[str, str]:
    if not inputs:
        return DEFAULT_EDIT1, DEFAULT_EDIT2
    return (
        (inputs.get("edit1_instruction") or DEFAULT_EDIT1).strip(),
        (inputs.get("edit2_instruction") or DEFAULT_EDIT2).strip(),
    )


# ---------------------------------------------------------------- 路径与 seed

def project_of(row: dict) -> str:
    for col in ("frame_key", "ref_role_sheet", "ref_scene_plate",
                "ref_costume_pair", "ref_voice"):
        v = (row.get(col) or "").replace("\\", "/")
        if v:
            return v.split("/")[0]
    return "PROJECT"


def frame_rel(row: dict) -> str:
    """最终帧相对 input/ 根的路径；CSV 已填则用 CSV，否则按 <项目>/frames/ 推导。"""
    v = (row.get("frame_key") or "").replace("\\", "/")
    if v:
        return v
    proj = project_of(row)
    num = re.sub(r"\D", "", row["shot_id"]) or row["shot_id"]
    return f"{proj}/frames/SHOT-{proj}-{num.zfill(3)}.png"


def work_rel(row: dict, suffix: str) -> str:
    """中间产物：<项目>/work/<帧名>_<suffix>.png（不进 frames/、不挂 H3）。"""
    p = frame_rel(row).split("/")
    stem = Path(p[-1]).stem
    return "/".join(p[:-2] + ["work", f"{stem}_{suffix}.png"])


def board_paths(row: dict) -> tuple[str, str, str]:
    return (
        (row.get("ref_role_sheet") or "").replace("\\", "/"),
        (row.get("ref_scene_plate") or "").replace("\\", "/"),
        (row.get("ref_costume_pair") or "").replace("\\", "/"),
    )


def shot_number(row: dict) -> int:
    """从 shot_id 提取稳定镜号（S004→4 / SHOT-EP001-004→4）。
    seed 必须由镜号派生，不能用筛选后的序号——否则 --only 单镜重跑会撞车/漂移。"""
    digits = re.sub(r"\D", "", row.get("shot_id", ""))
    if not digits:
        die(f"shot_id 里没有数字，无法派生稳定 seed：{row.get('shot_id')!r}")
    return int(digits)


def seeds(base_seed: int, shot_id_or_row) -> tuple[int, int, int]:
    """三阶段各一个 seed，破缓存且可回溯（实现卡 3 章）。

    实跑回灌 2026-11-21：seed 从 shot_id 数字派生，保证全量跑与 --only 单镜重跑
    得到相同 seed（旧版用 enumerate(selected,1) 序号，单镜重跑 seed 漂移且撞车）。
    兼容传入 int（旧调用）但此时不保证跨筛选稳定，建议一律传 shot_id/row。
    """
    if isinstance(shot_id_or_row, dict):
        num = shot_number(shot_id_or_row)
    elif isinstance(shot_id_or_row, int):
        num = shot_id_or_row
    else:
        m = re.sub(r"\D", "", str(shot_id_or_row))
        num = int(m) if m else 1
    s = base_seed + num * 3
    return s, s + 1, s + 2


def validate_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    for r in rows:
        check_path_contract(r, errors)
        sheet, plate, pair = board_paths(r)
        if not sheet or not plate or not pair:
            errors.append(
                f"{r['shot_id']}: 三张板路径未填齐（SHEET/PLATE/PAIR），禁止按镜重排或前移补位"
            )
    return errors


# ---------------------------------------------------------------- 回填与归档

def fill_frame_key(csv_path: Path, shot_id: str, rel: str) -> None:
    """只改 frame_key 一列，其余列逐字保留。

    实跑回灌：原版读 utf-8-sig / 写 utf-8 无 BOM，回填后 Excel 打开中文乱码；
    且非原子写，中途失败会损坏 CSV。改为保留 BOM + 临时文件原子替换。
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    hit = 0
    for r in rows:
        if (r.get("shot_id") or "").strip() == shot_id:
            r["frame_key"] = rel
            hit += 1
    if not hit:
        die(f"回填失败：CSV 里找不到 shot_id={shot_id}")
    if hit > 1:
        out(f"  [WARN] shot_id={shot_id} 有 {hit} 行，已全部回填 frame_key（请检查是否重复行）")
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    # utf-8-sig 写回 BOM，Excel 中文不乱码；先写临时文件再原子替换
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)


def append_manifest(path: Path, record: dict, dedup_key: str = "") -> None:
    """归档 JSONL。dedup_key 非空时按该字段去重（同 shot 重跑不重复追加历史）。

    实跑回灌：断点续跑重出某镜会再写一行 manifest，导致同一镜多条历史；
    传 dedup_key='shot_id' 可让最新一条覆盖同键旧记录，manifest 保持每镜一行。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    if dedup_key and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        records = [r for r in records if r.get(dedup_key) != record.get(dedup_key)]
    elif path.exists():
        return _append_raw(path, record)
    records.append(record)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _append_raw(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def selected_rows(rows: list[dict], group: str, only: list[str]) -> list[dict]:
    result = [r for r in rows if (not group or r["continuity_group"] == group)]
    if only:
        wanted = set(only)
        missing = wanted - {r["shot_id"] for r in result}
        if missing:
            die(f"--only 指定的镜号不存在：{', '.join(sorted(missing))}")
        result = [r for r in result if r["shot_id"] in wanted]
    return result
