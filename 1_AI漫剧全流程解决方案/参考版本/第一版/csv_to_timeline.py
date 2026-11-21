#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
csv_to_timeline.py
把分镜表 (shotlist CSV) 机械装配成 H3 导演台的 timeline_data。

路线：novelist + drama + vibe + H3 导演台 (r2v)

设计原则
--------
1. 不改工作流拓扑：只替换 MiniMaxH3Director 节点 widgets_values 里的
   timeline_data 字符串，以及随之变化的 totalFrames / seed。
   不增删节点、不碰连线、不动 UNET / 采样器 / 分辨率。
   另外做两处「底座残留规范化」：把 timeline_data 里 video/sourceWidth 等
   尺寸同步成 output 的分辨率（通用02 母版残留 960x544），以及按输出副本
   重设 SaveVideo 前缀（避免 EP001 实例自带的 video/EP001_004 或通用前缀
   被多个组共用而互相覆盖）。二者都可用 --save-prefix 覆盖。
2. 不覆盖权威原件：--out 必须是一个新路径，脚本强制检查。
3. <Picture N> 槽位固定语义、绝不重排（缺图就留空槽，不把后面的号往前挪）：
     1 = 每镜关键帧（vibe 漫画格，每镜换）
     2 = 角色定妆板（全片固定）
     3 = 场景板（同场景固定）
     4 = 服装 / 双人站位板（全片固定）
     Audio 1 (index 0) = 角色参考音色
4. 同 continuity_group 一次提交：一个组生成一份工作流，
   否则 22 帧 latent 接力失效、场景乱跳。
5. 脚本只做机械翻译 + 体检，不隐式改写画风词。
   画风冲突以 WARN 形式报出，由人在 CSV 里改（避免"改了不知道改了啥"）。

用法
----
  # 只体检，不写文件（出片前的门禁）
  python csv_to_timeline.py --check-only

  # 装配（默认用通用02 母版做底座；EP001 S004 仅作格式参考范例）
  python csv_to_timeline.py --csv shotlist_vibe_template.csv \
      --out out/H3-vibe-EP001-G01.json

  # 指定底座 / 指定组 / 指定 seed / 指定 input 根目录
  python csv_to_timeline.py --csv shotlist.csv \
      --workflow "F:/skills/工作流/02-H3漫剧流程/H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json" \
      --out out/H3-vibe.json --group G01 --seed 42 \
      --input-root "D:/ComfyUI-aki-v3.2/ComfyUI/input"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量配置

BASE = Path(__file__).resolve().parent

DEFAULT_CSV = BASE / "shotlist_vibe_template.csv"
# 通用02 是母版/空白模板。6 个 EP001 出片工作流的文件内便签都写着
# 「由 H3-通用02-高清主线 填充生成，勿当模板复用」——它们是出片实例，不是模板。
# 两者拓扑与采样参数完全一致，脚本整体替换 segments，用通用02 作底座更规范。
DEFAULT_WORKFLOW = Path(
    "F:/skills/工作流/02-H3漫剧流程/"
    "H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json"
)
DEFAULT_INPUT_ROOT = Path("D:/ComfyUI-aki-v3.2/ComfyUI/input")

# 官方 Ref2VA 六段式，段尾 Audio 标签。顺序不可改。
PROMPT_SECTIONS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]

# 固定槽位：(index, CSV 列名, 职责说明)。index 即 prompt 里的 <Picture N>。
REF_SLOTS = [
    (1, "frame_key",         "每镜关键帧 / vibe 漫画格"),
    (2, "ref_role_sheet",    "角色定妆板"),
    (3, "ref_scene_plate",   "场景板"),
    (4, "ref_costume_pair",  "服装 / 双人站位板"),
]

REQUIRED_COLUMNS = (
    ["shot_id", "continuity_group", "length_frames", "frame_key", "audio_tag"]
    + PROMPT_SECTIONS
    + [c for _, c, _ in REF_SLOTS]
    + ["ref_voice", "negative_prompt", "seed"]
)

# widgets_values 索引（经 6 个 EP001 出片工作流实证）
W_SEED = 4
W_FRAMERATE = 6
W_TOTALFRAMES = 10
W_TIMELINE = 11   # timeline_data JSON 字符串


# ---------------------------------------------------------------- 工具函数

def out(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(2)


def ref_obj(index: int, image_file: str) -> dict:
    return {
        "index": index,
        "imageFile": image_file or "",
        "fileName": "",
        "type": "input",
        "subfolder": "",
    }


def audio_obj(audio_file: str) -> dict:
    return {
        "index": 0,
        "audioFile": audio_file or "",
        "fileName": "",
        "type": "input",
        "subfolder": "",
    }


def load_rows(csv_path: Path) -> list[dict]:
    if not csv_path.is_file():
        die(f"分镜表不存在：{csv_path}")
    # utf-8-sig 吃掉 Excel 存出来的 BOM
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader if any((v or "").strip() for v in r.values())]
    if not rows:
        die("分镜表没有数据行")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        die("分镜表缺列：" + ", ".join(missing))
    return [{k: (v or "").strip() for k, v in r.items()} for r in rows]


def find_director(doc: dict) -> tuple[dict, list]:
    for node in doc.get("nodes", []):
        if node.get("type") == "MiniMaxH3Director":
            return node, node.get("widgets_values", [])
    die("工作流里找不到 MiniMaxH3Director 节点——请确认选的是 H3 导演台工作流")


def find_timeline(widgets: list) -> tuple[int, dict]:
    """稳健定位 timeline_data：找能解析且含 segments 键的 JSON 字符串。"""
    for i, x in enumerate(widgets):
        if isinstance(x, str) and x.strip().startswith("{") and "segments" in x:
            try:
                td = json.loads(x)
            except json.JSONDecodeError:
                continue
            if isinstance(td, dict) and "segments" in td:
                return i, td
    die("widgets_values 里找不到 timeline_data JSON")


def read_fps(workflow: Path, fallback: float) -> float:
    """帧率以底座工作流的 timeline_data.frameRate 为准，避免手填错。"""
    if not workflow.is_file():
        return fallback
    try:
        doc = json.loads(workflow.read_text(encoding="utf-8"))
        _, widgets = find_director(doc)
        _, td = find_timeline(widgets)
        return float(td.get("frameRate") or widgets[W_FRAMERATE] or fallback)
    except Exception:
        return fallback


def build_prompt(row: dict) -> str:
    lines = [f"{k}: {row.get(k, '')}" for k in PROMPT_SECTIONS]
    lines.append(f"Audio: {row.get('audio_tag', 'none')}")
    return "\n".join(lines)


def build_segment(row: dict, seq: int, start: int, fps: float) -> dict:
    try:
        n = int(row["length_frames"])
    except ValueError:
        die(f"{row['shot_id']} 的 length_frames 不是整数：{row['length_frames']!r}")
    if n <= 0:
        die(f"{row['shot_id']} 的 length_frames 必须 > 0")

    refs = [ref_obj(idx, row.get(col, "")) for idx, col, _ in REF_SLOTS]
    voice = row.get("ref_voice", "")
    return {
        "id": f"seg_{seq:03d}",
        "start": start,
        "length": n,
        "frameCount": n,
        "durationSec": round(n / fps, 3),
        "prompt": build_prompt(row),
        "negativePrompt": row.get("negative_prompt", ""),
        "taskType": "",
        "refs": refs,
        "refAudios": [audio_obj(voice)] if voice else [],
        "refVideos": [],
        "genImage": {"imageFile": "", "fileName": ""},
    }


# ---------------------------------------------------------------- 体检门禁

def preflight(rows: list[dict], input_root: Path | None, fps: float,
              style_mode: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []

    seen_ids: set[str] = set()
    prompts: dict[str, str] = {}
    role_sheets: set[str] = set()
    frame_keys: list[str] = []
    assets: set[str] = set()
    groups: list[str] = []

    for r in rows:
        sid = r["shot_id"] or "(空 shot_id)"
        if sid in seen_ids:
            errors.append(f"{sid}: shot_id 重复")
        seen_ids.add(sid)

        if r["continuity_group"] not in groups:
            groups.append(r["continuity_group"])

        # 帧数网格：EP001 实测用 17 的倍数 (102/136)，README 允许 5+17n (124)
        n = int(r["length_frames"])
        if n % 17 != 0 and (n - 5) % 17 != 0:
            warns.append(f"{sid}: {n} 帧不在 17n / 5+17n 网格上（H3 token 网格），建议 102/124/136")

        # 段长 vs 台词朗读时长（中文约 4 字/秒，粗估）
        dur = n / fps
        dialogue = "".join(re.findall(r"[\u4e00-\u9fff]", r["detailed_description"]))
        need = len(dialogue) / 4.0
        if need > dur:
            warns.append(f"{sid}: 段长 {dur:.2f}s < 台词粗估 {need:.2f}s，音轨可能被截断")

        # prompt 完全一致会触发整图缓存
        p = build_prompt(r)
        if p in prompts:
            warns.append(f"{sid}: 与 {prompts[p]} 的 prompt 完全一致，会触发整图缓存（改几个字破缓存）")
        else:
            prompts[p] = sid

        # 音频标签与音色文件配套
        tag = r["audio_tag"]
        if tag not in ("reference", "none"):
            errors.append(f"{sid}: audio_tag 只能是 reference / none，实为 {tag!r}")
        if tag == "reference" and not r["ref_voice"]:
            errors.append(f"{sid}: audio_tag=reference 但没有 ref_voice，无法锁定音色")
        if tag == "none" and r["ref_voice"]:
            warns.append(f"{sid}: audio_tag=none 却挂了 ref_voice（实战里静默段有时保留 ref 写 'no speech'，两种都可，但要清楚选了哪种）")

        # 画质/画风冲突
        neg = r["negative_prompt"]
        if style_mode == "comic" and ("卡通" in neg or "动画感" in neg):
            warns.append(f"{sid}: vibe 是漫画格，但 negative_prompt 仍禁「卡通/动画感」→ 参考图与提示词打架，必须删掉这两项")
        if "真人实拍" in p or "film grain" in p.lower():
            warns.append(f"{sid}: prompt 里仍有真人实拍类画风词，vibe 漫画格需同步改成漫画向")

        # 槽位固定性
        role_sheets.add(r["ref_role_sheet"])
        frame_keys.append(r["frame_key"])
        for _, col, _ in REF_SLOTS:
            if r.get(col):
                assets.add(r[col])
        if r.get("ref_voice"):
            assets.add(r["ref_voice"])

    if len(role_sheets) > 1:
        warns.append("角色定妆板 <Picture 2> 全片不唯一 → 跨镜身份漂移风险：" + " / ".join(sorted(role_sheets)))
    if len(set(frame_keys)) < len(frame_keys):
        warns.append("多个镜头共用同一张 frame_key（<Picture 1> 每镜应各一张 vibe 格），确认是有意的空镜复用")

    # 资产存在性（只警告，不阻断：vibe 图可能还没生成）
    if input_root and input_root.is_dir():
        miss = sorted(a for a in assets if not (input_root / a).is_file())
        if miss:
            warns.append(f"input/ 下缺失 {len(miss)} 个资产（若尚未生成 vibe 图可忽略）：\n        " + "\n        ".join(miss))
    elif input_root:
        warns.append(f"input 根目录不存在，跳过资产存在性检查：{input_root}")

    return errors, warns


# ---------------------------------------------------------------- 主流程

def assemble(rows: list[dict], workflow: Path, out_path: Path,
             fps: float, seed: int | None, save_prefix: str = "") -> None:
    doc = json.loads(workflow.read_text(encoding="utf-8"))
    node, widgets = find_director(doc)
    ti, td = find_timeline(widgets)
    if ti != W_TIMELINE:
        out(f"[NOTE] timeline_data 实际在 widgets[{ti}]（预设 {W_TIMELINE}），已按实际索引写回")

    segments, start = [], 0
    for i, r in enumerate(rows, 1):
        segments.append(build_segment(r, i, start, fps))
        start += int(r["length_frames"])

    total = start
    td["segments"] = segments
    td["totalFrames"] = total
    td["durationSec"] = round(total / fps, 3)

    # 底座残留规范化 1：通用02 母版的 video/sourceWidth 是 960x544（快出预览尺寸），
    # 与 output 的 1344x768 不符；统一同步，避免残留尺寸带进正式副本。
    ow = td.get("output", {}).get("width")
    oh = td.get("output", {}).get("height")
    if ow and oh:
        video = td.get("video")
        if isinstance(video, dict):
            for k in ("width", "storageWidth", "height", "storageHeight"):
                if k in video:
                    video[k] = ow if k in ("width", "storageWidth") else oh
        g = td.get("global")
        if isinstance(g, dict):
            g["sourceWidth"] = ow
            g["sourceHeight"] = oh

    widgets[ti] = json.dumps(td, ensure_ascii=False)
    widgets[W_TOTALFRAMES] = total
    if seed is not None:
        widgets[W_SEED] = int(seed)
    node["widgets_values"] = widgets

    # 底座残留规范化 2：SaveVideo 前缀。EP001 实例自带 video/EP001_004，
    # 通用02 自带 video/通用_高清；多组装配时若沿用会互相覆盖，改为按副本命名。
    for n in doc["nodes"]:
        if n.get("type") == "SaveVideo":
            wv = n.get("widgets_values")
            if wv:
                wv[0] = save_prefix or f"video/{out_path.stem}"
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="分镜表 CSV → H3 导演台 timeline_data 装配器")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="分镜表 CSV")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW, help="底座工作流 JSON")
    ap.add_argument("--out", type=Path, default=BASE / "out" / "H3-vibe-assembled.json",
                    help="输出副本路径（必须不同于底座，禁止覆盖权威原件）")
    ap.add_argument("--group", default="", help="只装配指定 continuity_group；不填则每组各出一份")
    ap.add_argument("--seed", type=int, default=None, help="统一 seed（不填则沿用底座值）")
    ap.add_argument("--save-prefix", default="",
                    help="SaveVideo 输出前缀；不填则自动用 video/<输出文件名>，避免多组共用底座前缀互相覆盖")
    ap.add_argument("--fps", type=float, default=24.0, help="帧率，默认 24（与底座 frameRate 保持一致）")
    ap.add_argument("--style", choices=["comic", "live"], default="comic",
                    help="画风模式，仅影响体检告警，不改写内容。vibe 漫画格选 comic")
    ap.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT,
                    help="ComfyUI input 目录，用于检查参考资产是否已就位")
    ap.add_argument("--check-only", action="store_true", help="只跑体检门禁，不写任何文件")
    args = ap.parse_args()

    rows = load_rows(args.csv)
    fps = read_fps(args.workflow, args.fps)
    out(f"分镜表：{args.csv}  ({len(rows)} 行)   帧率：{fps}")

    groups: list[str] = []
    for r in rows:
        if r["continuity_group"] not in groups:
            groups.append(r["continuity_group"])
    out(f"连续组：{', '.join(groups)}  —— 每组必须一次提交，不能分多次跑")

    if args.group and args.group not in groups:
        die(f"指定的 --group {args.group} 不存在，可选：{', '.join(groups)}")

    selected = [r for r in rows if not args.group or r["continuity_group"] == args.group]

    errors, warns = preflight(selected, args.input_root, fps, args.style)
    out("")
    out(f"===== 体检：{len(errors)} 个错误 / {len(warns)} 条提醒 =====")
    for e in errors:
        out(f"  [ERROR] {e}")
    for w in warns:
        out(f"  [WARN ] {w}")
    if not errors and not warns:
        out("  全部通过")

    if args.check_only:
        out("\n--check-only：未写任何文件")
        sys.exit(1 if errors else 0)
    if errors:
        die("体检有错误，先修分镜表再装配（加 --check-only 可反复自检）")

    if not args.workflow.is_file():
        die(f"底座工作流不存在：{args.workflow}")

    targets = [args.group] if args.group else groups
    for g in targets:
        grp_rows = [r for r in rows if r["continuity_group"] == g]
        if len(targets) == 1:
            out_path = args.out
        else:
            out_path = args.out.with_name(f"{args.out.stem}_{g}{args.out.suffix}")
        if out_path.resolve() == args.workflow.resolve():
            die(f"--out 不能等于底座工作流，禁止覆盖权威原件：{out_path}")
        if out_path.exists():
            out(f"[NOTE] 覆盖已有副本 {out_path}")
        assemble(grp_rows, args.workflow, out_path, fps, args.seed, args.save_prefix)
        total = sum(int(r["length_frames"]) for r in grp_rows)
        out(f"\n[OK] {g}: {len(grp_rows)} 段 / {total} 帧 / {total/fps:.3f}s  ->  {out_path}")
        for r in grp_rows:
            out(f"       {r['shot_id']:6s}  {int(r['length_frames']):3d}帧  "
                f"P1={r['frame_key'] or '(空)'}  Audio={r['audio_tag']}")

    out("\n下一步：把副本拖进 ComfyUI → 先跑 01 快出预览试错 → 审片 → 再跑 02 出片")


if __name__ == "__main__":
    main()
