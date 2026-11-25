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
   重设 SaveVideo 前缀。二者都可用 --save-prefix 覆盖。
2. 不覆盖权威原件：--out 必须是一个新路径，脚本强制检查。
3. <Picture N> 槽位固定语义、绝不重排（缺图就留空槽，不把后面的号往前挪）：
     1 = 每镜关键帧（vibe 漫画格，每镜换）
     2 = 角色定妆板（全片固定）
     3 = 场景板（同场景固定）
     4 = 服装 / 双人站位板（全片固定）
   Audio 1..3 = 角色参考音色（generate 双声线档可挂多条，见 ref_voice_2/3）。
4. 同 continuity_group 一次提交：一个组生成一份工作流，
   否则 22 帧 latent 接力失效、场景乱跳。
   （实跑 A 方案「每镜独立出片 + ffmpeg xfade」请用 --per-shot，见下。）
5. 脚本只做机械翻译 + 体检，不隐式改写画风词。
   画风冲突以 WARN 形式报出，由人在 CSV 里改（避免"改了不知道改了啥"）。

实跑回灌（2026-11-21，来源 <资料库根>/7_经验库/工作流优化经验库.md，均已验证）
---------------------------------------------------------------------------
* refs 引用：本项目导演台是 **0 基**（<Picture 1>=index 0），且 imageFile 只写
  文件名、目录进 subfolder。旧版本脚本用 1 基 + 整路径塞 imageFile，实机会
  引用错位 / 找不到图。默认已改为 0 基 + 路径拆分；换导演台版本时用
  --ref-base 1 切回，并用一张已知身份板做单镜实测。
  ⚠️ refAudios 恒 0 基，不随 --ref-base 改（经验库明确「audio 勿与图片一起改」）。
* 场景锁定：generate 档必须 global.prompt + global.commonEnabled=True 才会把
  场景圣经拼进每镜（prompt_batch 会强制 editMode=segment，留空 = 无锁定）。
  用 --scene-bible <文本> 注入；source/TTS 单轨档留空即可，两档勿混用。
* refAudioStamp：同名替换参考音频会命中缓存造成 8 秒「假完成」。装配时按音频
  md5[:10]+size 生成指纹戳写入 timeline 顶层，破缓存、不进提示词。
* 双声线：generate 档双人镜挂双板 + 双 <Audio>，CSV 用 ref_voice / ref_voice_2
  / ref_voice_3 声明，按声明顺序进 refAudios（0 基）。
* 对白节奏：挂音色的镜自动注入首句起点 + 0.3~0.5s 接话（--dialogue-pace，默认开）。
* seed 列生效：--seed 优先；不传则取本组第一行 seed 列；再无则沿用底座值。

用法
----
  # 只体检，不写文件（出片前的门禁）
  python csv_to_timeline.py --check-only

  # 常规装配（默认 0 基引用 + 自动场景锁建议）
  python csv_to_timeline.py --csv shotlist.csv --out out/H3-vibe-G01.json \
      --scene-bible scene_bible.txt --input-root "$COMFYUI_ROOT/input"

  # 每镜独立出片（实跑 A 方案：每镜一份单段 workflow，供 render_submit 逐镜提交 + xfade 拼接）
  python csv_to_timeline.py --csv shotlist.csv --out out/shots/G.json --per-shot \
      --scene-bible scene_bible.txt

  # 换导演台版本切回 1 基引用（务必先单镜实测）
  python csv_to_timeline.py --csv shotlist.csv --out out/x.json --ref-base 1

  # A1：同一份 CSV 装配 01 预览 + 02 出片两份副本，并自动校验 segments 与拓扑一致
  python csv_to_timeline.py --csv shotlist.csv --dual --out out/H3-vibe-G01.json

  # A1：事后独立复验两份副本（N11 审片结论对 02 是否有效）
  python csv_to_timeline.py --compare out/x_preview.json out/x_final.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from paths import default_input_root  # 跨电脑可移植：env COMFYUI_ROOT > 探测 > 回退

# ---------------------------------------------------------------- 常量配置

BASE = Path(__file__).resolve().parent

DEFAULT_CSV = BASE / "shotlist_vibe_template.csv"
# 通用02 是母版/空白模板。6 个 EP001 出片工作流的文件内便签都写着
# 「由 H3-通用02-高清主线 填充生成，勿当模板复用」——它们是出片实例，不是模板。
# 两者拓扑与采样参数完全一致，脚本整体替换 segments，用通用02 作底座更规范。
DEFAULT_WORKFLOW = BASE / "工作流底座" / "H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json"
DEFAULT_INPUT_ROOT = default_input_root()

# --dual 的 01 预览底座。与 02 的 output.continuityEnabled 同为 True（实测），
# 但尺寸 960x544 / 4step 不同；双份装配只允许这些「渲染档」字段不同。
DEFAULT_PREVIEW_WORKFLOW = BASE / "工作流底座" / "H3-通用01-快出预览-r2v-4step-960x544.json"

# 路径契约（A2 定线）：shotlist.csv 里一律写相对 input/ 根的
# <项目>/<类别>/<文件名>。类别与列一一对应，杜绝 frames_v4/ 与裸文件名。
# 校验为 ERROR 级：照旧命名填表会静默通过体检、直到 ComfyUI 加载才暴露。
PATH_CONTRACT = {
    "frame_key":        ("frames",  {".png", ".jpg", ".jpeg", ".webp"}),
    "ref_role_sheet":   ("chars",   {".png", ".jpg", ".jpeg", ".webp"}),
    "ref_scene_plate":  ("scenes",  {".png", ".jpg", ".jpeg", ".webp"}),
    "ref_costume_pair": ("props",   {".png", ".jpg", ".jpeg", ".webp"}),
    "ref_voice":        ("voices",  {".wav", ".mp3", ".flac", ".m4a"}),
    "ref_voice_2":      ("voices",  {".wav", ".mp3", ".flac", ".m4a"}),
    "ref_voice_3":      ("voices",  {".wav", ".mp3", ".flac", ".m4a"}),
}

# 官方 Ref2VA 六段式，段尾 Audio 标签。顺序不可改。
PROMPT_SECTIONS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]

# 固定槽位：(Picture 序号 1..4, CSV 列名, 职责说明)。序号即 prompt 里的 <Picture N>，
# 真正的 refs[].index 由 --ref-base 换算（默认 0 基 = 序号-1）。绝不重排、缺图留空槽。
REF_SLOTS = [
    (1, "frame_key",         "每镜关键帧 / vibe 漫画格"),
    (2, "ref_role_sheet",    "角色定妆板"),
    (3, "ref_scene_plate",   "场景板"),
    (4, "ref_costume_pair",  "服装 / 双人站位板"),
]

# 声线槽：按声明顺序进 refAudios，恒 0 基（与图片基数无关）。
VOICE_COLUMNS = ("ref_voice", "ref_voice_2", "ref_voice_3")

REQUIRED_COLUMNS = (
    ["shot_id", "continuity_group", "length_frames", "frame_key", "audio_tag"]
    + PROMPT_SECTIONS
    + [c for _, c, _ in REF_SLOTS]
    + ["ref_voice", "negative_prompt"]
)

# widgets_values 索引（经 6 个 EP001 出片工作流实证）
W_SEED = 4
W_FRAMERATE = 6
W_TOTALFRAMES = 10
W_TIMELINE = 11   # timeline_data JSON 字符串

# 对白节奏（generate 档；实跑 v4 定版：删掉音节读满与句末留白，避免字级碎片与 2s 空档）
PACE_GLOBAL = (
    "dialogue_direction: Natural connected conversational speech, smooth and low; "
    "words flow continuously within each line with only brief pauses between phrases; "
    "replies follow closely without long silent gaps. Do not rush, do not clip the words."
)

# 画风冲突词（中英双语，覆盖英文模板）
COMIC_NEG_BAD = ("卡通", "动画感", "cartoon", "anime", "animated", "animation")
LIVE_PROMPT_BAD = ("真人实拍", "film grain", "photoreal", "photographic", "live action", "realistic photo")


# ---------------------------------------------------------------- 工具函数

def out(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(2)


def split_input_path(rel: str) -> tuple[str, str]:
    """<项目>/<类别>/<文件名> → (subfolder, imageFile)。实机引用分开两字段。"""
    p = (rel or "").replace("\\", "/").strip()
    if not p:
        return "", ""
    if "/" in p:
        sub, name = p.rsplit("/", 1)
        return sub, name
    return "", p


def ref_obj(slot: int, rel_path: str, base: int) -> dict:
    """slot=<Picture N> 的 N；base=0 → index=N-1，base=1 → index=N。"""
    sub, name = split_input_path(rel_path)
    return {
        "index": slot - 1 + base,
        "imageFile": name,
        "fileName": name,
        "type": "input",
        "subfolder": sub,
    }


def voice_obj(rel_path: str, index: int) -> dict:
    """声线槽恒 0 基；index 为声明顺序 0,1,2。"""
    sub, name = split_input_path(rel_path)
    return {
        "index": index,
        "audioFile": name,
        "fileName": name,
        "type": "input",
        "subfolder": sub,
    }


def ref_audio_stamp(audios: list[dict], input_root: Path | None) -> str:
    """同名替换参考音频时破缓存：每条 md5[:10]-size，| 拼接，不进提示词。"""
    if not input_root or not audios:
        return ""
    parts: list[str] = []
    for a in audios:
        p = input_root / a.get("subfolder", "") / a.get("audioFile", "")
        if not p.is_file():
            continue
        h = hashlib.md5(p.read_bytes()).hexdigest()[:10]
        parts.append(f"{a['index']}:{h}-{p.stat().st_size}")
    return "|".join(parts)


def check_path_contract(row: dict, errors: list[str]) -> None:
    """A2：资产路径必须是相对 input/ 根的 <项目>/<类别>/<文件名>。"""
    sid = row["shot_id"] or "(空 shot_id)"
    for col, (folder, exts) in PATH_CONTRACT.items():
        v = (row.get(col) or "").strip()
        if not v:
            continue
        p = v.replace("\\", "/")
        bad_abs = p.startswith("/") or p.startswith("./") or bool(re.match(r"^[A-Za-z]:", p))
        bad_dotdot = ".." in p.split("/")
        if bad_abs or bad_dotdot:
            errors.append(
                f"{sid}: {col}={v!r} 不是相对 input/ 根的路径（禁绝对路径/盘符/./..）"
            )
            continue
        parts = p.split("/")
        if len(parts) != 3 or parts[1] != folder:
            got = parts[1] if len(parts) > 1 else "?"
            errors.append(
                f"{sid}: {col}={v!r} 应为 <项目>/{folder}/<文件名>（3 段），"
                f"实得 {len(parts)} 段 / 目录 {got!r}"
            )
            continue
        if Path(parts[2]).suffix.lower() not in exts:
            errors.append(
                f"{sid}: {col}={v!r} 扩展名应为 {'/'.join(sorted(exts))}"
            )


def load_rows(csv_path: Path) -> list[dict]:
    if not csv_path.is_file():
        die(f"分镜表不存在：{csv_path}")
    # utf-8-sig 吃掉 Excel 存出来的 BOM
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader if any((v or "").strip() for v in r.values())]
        fieldnames = list(reader.fieldnames or [])
    if not rows:
        die("分镜表没有数据行")
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        die("分镜表缺列：" + ", ".join(missing))
    optional_missing = [c for c in VOICE_COLUMNS[1:] if c not in fieldnames]
    if optional_missing:
        out(f"[NOTE] 分镜表无可选列 {', '.join(optional_missing)}，按单声线处理"
            "（双声线档请加 ref_voice_2/ref_voice_3 列）")
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


def inject_dialogue_timing(prompt: str, has_voice: bool) -> str:
    """generate 档：首句注入起点，后续句 0.3~0.5s 短停顿跟随；无音色则不注入。"""
    if not has_voice:
        return prompt
    first = (" (starts at about one second into the shot, natural connected "
             "conversational pace, softly and low)")
    follow = (" (the reply follows after a brief beat of 0.3 to 0.5 seconds at "
              "the same natural connected pace, no long silent gap; phrases inside "
              "the line flow with only brief pauses)")
    counter = {"n": 0}

    def _sub(m):
        counter["n"] += 1
        return m.group(1) + (first if counter["n"] == 1 else follow)

    new, total = re.subn(r"(On-screen dialogue:[^\n]*?」)", _sub, prompt)
    if total == 0:
        return prompt + "\n" + PACE_GLOBAL
    return new + "\n" + PACE_GLOBAL


def build_prompt(row: dict, dialogue_pace: bool = True) -> str:
    tag = row.get("audio_tag", "none")
    lines = [f"{k}: {row.get(k, '')}" for k in PROMPT_SECTIONS]
    lines.append(f"Audio: {tag}")
    prompt = "\n".join(lines)
    voices = [v for c in VOICE_COLUMNS if (v := (row.get(c) or "").strip())]
    # source 档（配音流水线逐句精控）不注入 generate 档的对话节奏：
    # 停顿/抢话已在 assemble 阶段处理，且必须保证 Audio: fully_copy 留在段尾供 H3 读取。
    if dialogue_pace and voices and tag != "fully_copy":
        prompt = inject_dialogue_timing(prompt, has_voice=True)
    return prompt


def build_segment(row: dict, seq: int, start: int, fps: float,
                  base: int, dialogue_pace: bool = True) -> dict:
    try:
        n = int(row["length_frames"])
    except ValueError:
        die(f"{row['shot_id']} 的 length_frames 不是整数：{row['length_frames']!r}")
    if n <= 0:
        die(f"{row['shot_id']} 的 length_frames 必须 > 0")

    refs = [ref_obj(slot, row.get(col, ""), base) for slot, col, _ in REF_SLOTS]
    voices = [v.strip() for c in VOICE_COLUMNS if (v := (row.get(c) or ""))]
    audios = [voice_obj(v, i) for i, v in enumerate(voices)]
    return {
        "id": f"seg_{seq:03d}",
        "start": start,
        "length": n,
        "frameCount": n,
        "durationSec": round(n / fps, 3),
        "prompt": build_prompt(row, dialogue_pace),
        "negativePrompt": row.get("negative_prompt", ""),
        "taskType": "",
        "refs": refs,
        "refAudios": audios,
        "refVideos": [],
        "genImage": {"imageFile": "", "fileName": ""},
    }


# ---------------------------------------------------------------- 体检门禁

def preflight(rows: list[dict], input_root: Path | None, fps: float,
              style_mode: str, strict_assets: bool = False,
              ref_base: int = 0) -> tuple[list[str], list[str]]:
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

        # A2：路径契约硬校验（不合规直接阻断，不再静默跳过）
        check_path_contract(r, errors)

        if r["continuity_group"] not in groups:
            groups.append(r["continuity_group"])

        # 帧数网格：EP001 实测用 17 的倍数 (102/136)，README 允许 5+17n (124)
        try:
            n = int(r["length_frames"])
        except (ValueError, TypeError):
            errors.append(f"{sid}: length_frames 不是整数：{r['length_frames']!r}")
            continue
        if n <= 0:
            errors.append(f"{sid}: length_frames 必须 > 0（实为 {n}）")
            continue

        # B5：duration_sec / qc_status 不再是死列
        ds = r.get("duration_sec", "")
        if ds:
            try:
                if abs(float(ds) - n / fps) > 0.011:
                    errors.append(
                        f"{sid}: duration_sec={ds} 与 length_frames/fps="
                        f"{n / fps:.3f} 不符（填错原本无任何提示，现直接阻断）"
                    )
            except ValueError:
                errors.append(f"{sid}: duration_sec={ds!r} 不是数字")
        qc = r.get("qc_status", "")
        if qc and qc not in ("通过", "已审", "pass", "ok", "PASS"):
            warns.append(f"{sid}: qc_status={qc!r}，N10 试错前请确认起始帧已验收")

        if n % 17 != 0 and (n - 5) % 17 != 0:
            warns.append(f"{sid}: {n} 帧不在 17n / 5+17n 网格上（H3 token 网格），建议 102/124/136")

        # 段长 vs 台词朗读时长：只数「」内中文（旧版数整段 detailed_description，英文模板永不告警）
        quoted = "".join(re.findall(r"「(.+?)」", r["detailed_description"]))
        dialogue = "".join(re.findall(r"[\u4e00-\u9fff]", quoted))
        need = len(dialogue) / 4.0
        dur = n / fps
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
        voices = [v.strip() for c in VOICE_COLUMNS if (v := (r.get(c) or "").strip())]
        if tag not in ("reference", "none", "fully_copy"):
            errors.append(f"{sid}: audio_tag 只能是 reference / none / fully_copy，实为 {tag!r}")
        if tag in ("reference", "fully_copy") and not voices:
            errors.append(f"{sid}: audio_tag={tag} 但没有 ref_voice"
                          f"（source 档需挂配音流水线切段音轨）")
        if tag == "none" and voices:
            warns.append(f"{sid}: audio_tag=none 却挂了 ref_voice（静默段保留 ref 写 'no speech' 也可，但要清楚选了哪种）")
        if len(voices) > 3:
            errors.append(f"{sid}: 声线最多 3 条（ref_voice/2/3），实得 {len(voices)}")

        # 画质/画风冲突（中英双语）
        neg = r["negative_prompt"]
        neg_l = neg.lower()
        if style_mode == "comic" and any(k in neg or k.lower() in neg_l for k in COMIC_NEG_BAD):
            warns.append(f"{sid}: vibe 是漫画格，但 negative_prompt 仍禁卡通/动画感（cartoon/anime）→ 参考图与提示词打架，必须删掉")
        if any(k in p or k.lower() in p.lower() for k in LIVE_PROMPT_BAD):
            warns.append(f"{sid}: prompt 里仍有真人实拍类画风词，vibe 漫画格需同步改成漫画向")

        # 槽位固定性
        role_sheets.add(r["ref_role_sheet"])
        frame_keys.append(r["frame_key"])
        for _, col, _ in REF_SLOTS:
            if r.get(col):
                assets.add(r[col])
        for v in voices:
            assets.add(v)

    # 单声线档：角色定妆板应全片唯一；双声线档：双人镜本就应挂双板，不告警
    has_duo = any(len([1 for c in VOICE_COLUMNS if (r.get(c) or "").strip()]) > 1 for r in rows)
    if not has_duo and len(role_sheets) > 1:
        warns.append("角色定妆板 <Picture 2> 全片不唯一 → 跨镜身份漂移风险：" + " / ".join(sorted(role_sheets)))
    if len(set(frame_keys)) < len(frame_keys):
        warns.append("多个镜头共用同一张 frame_key（<Picture 1> 每镜应各一张 vibe 格），确认是有意的空镜复用")

    # refs 基数提醒（不阻断）
    if ref_base == 1:
        warns.append("refs 使用 1 基（--ref-base 1）——本项目实跑验证为 0 基，换回前务必单镜实测确认无错位")

    # 资产存在性。默认只警告（vibe 图可能还没生成），--strict-assets 升级为 ERROR；
    if input_root and input_root.is_dir():
        miss = sorted(a for a in assets if not (input_root / a).is_file())
        if miss:
            msg = f"input/ 下缺失 {len(miss)} 个资产（若尚未出帧可忽略）：\n        " + "\n        ".join(miss)
            (errors if strict_assets else warns).append(msg)
    elif input_root:
        msg = f"[资产存在性检查未执行] input 根目录不存在：{input_root}"
        (errors if strict_assets else warns).append(msg)

    return errors, warns


# ---------------------------------------------------------------- 主流程

def apply_scene_lock(td: dict, scene_bible: str) -> None:
    """generate 档场景锁：global.prompt + commonEnabled=True。source/TTS 档勿用。"""
    g = td.get("global")
    if not isinstance(g, dict):
        return
    g["prompt"] = scene_bible
    g["commonEnabled"] = True


def assemble(rows: list[dict], workflow: Path, out_path: Path,
             fps: float, seed: int | None, save_prefix: str = "",
             scene_bible: str = "", dialogue_pace: bool = True,
             ref_base: int = 0, input_root: Path | None = None) -> None:
    doc = json.loads(workflow.read_text(encoding="utf-8"))
    node, widgets = find_director(doc)
    ti, td = find_timeline(widgets)
    if ti != W_TIMELINE:
        out(f"[NOTE] timeline_data 实际在 widgets[{ti}]（预设 {W_TIMELINE}），已按实际索引写回")

    segments, start = [], 0
    for i, r in enumerate(rows, 1):
        segments.append(build_segment(r, i, start, fps, ref_base, dialogue_pace))
        start += int(r["length_frames"])

    total = start
    td["segments"] = segments
    td["totalFrames"] = total
    td["durationSec"] = round(total / fps, 3)

    # 场景锁（generate 档）：global.prompt + commonEnabled=True
    if scene_bible:
        apply_scene_lock(td, scene_bible)

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

    # refAudioStamp：同名替换音频时破缓存（不进提示词）
    all_audios = [a for s in segments for a in s["refAudios"]]
    stamp = ref_audio_stamp(all_audios, input_root)
    if stamp:
        td["refAudioStamp"] = stamp

    widgets[ti] = json.dumps(td, ensure_ascii=False)
    widgets[W_TOTALFRAMES] = total
    # seed 列生效：--seed 优先 → 本组第一行 seed 列 → 沿用底座
    effective_seed = seed
    if effective_seed is None:
        for r in rows:
            sv = (r.get("seed") or "").strip()
            if sv:
                try:
                    effective_seed = int(sv)
                except ValueError:
                    out(f"[NOTE] {r['shot_id']} 的 seed={sv!r} 非整数，忽略")
                break
    if effective_seed is not None:
        widgets[W_SEED] = int(effective_seed)
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


def assemble_per_shot(rows: list[dict], workflow: Path, out_dir: Path,
                      fps: float, seed: int | None, scene_bible: str,
                      dialogue_pace: bool, ref_base: int,
                      input_root: Path | None) -> None:
    """实跑 A 方案：每镜一份单段 workflow，供 render_submit 逐镜提交 + xfade 拼接。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        sid_num = re.sub(r"\D", "", r["shot_id"]) or r["shot_id"]
        target = out_dir / f"SHOT-{sid_num.zfill(3)}.json"
        assemble([r], workflow, target, fps, seed, f"video/SHOT-{sid_num.zfill(3)}",
                 scene_bible, dialogue_pace, ref_base, input_root)
        out(f"  [OK] 单镜 {r['shot_id']} -> {target}")


# ---------------------------------------------------------------- 01/02 一致性校验（A1）

SEGMENT_FIELDS = (
    "id", "start", "length", "frameCount", "durationSec", "prompt",
    "negativePrompt", "taskType", "refs", "refAudios", "refVideos", "genImage",
)
TIMELINE_SCALARS = ("frameRate", "totalFrames", "durationSec")
# 场景锁字段也要一致，否则 01 审的场景在 02 变了
GLOBAL_FIELDS = ("prompt", "commonEnabled")
OUTPUT_SCALARS = (
    "continuityEnabled", "continuityOverlapFrames", "exportMode",
    "audioMode", "aspectRatio",
)


def load_doc(path: Path) -> dict:
    if not path.is_file():
        die(f"副本不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def extract_timeline(path: Path) -> dict:
    _, widgets = find_director(load_doc(path))
    _, td = find_timeline(widgets)
    return td


def _short(v, limit: int = 90) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= limit else s[:limit] + "…"


def topology_of(doc: dict) -> dict:
    """拓扑指纹：节点数/连线数/是否有 LoRA/UNET 类型。--dual 承诺「拓扑一致」。"""
    return {
        "nodes": len(doc.get("nodes", [])),
        "links": len(doc.get("links", [])),
        "lora": sum(1 for n in doc.get("nodes", []) if n.get("type") == "LoraLoaderModelOnly"),
        "unet": next((json.dumps(n.get("widgets_values", [])[:1], ensure_ascii=False)
                      for n in doc.get("nodes", []) if n.get("type") == "UNETLoader"), ""),
    }


def compare_timelines(td_a: dict, td_b: dict, name_a: str, name_b: str) -> list[str]:
    diffs: list[str] = []
    for k in TIMELINE_SCALARS:
        if td_a.get(k) != td_b.get(k):
            diffs.append(f"{k}: {name_a}={td_a.get(k)!r} / {name_b}={td_b.get(k)!r}")
    ga, gb = td_a.get("global", {}), td_b.get("global", {})
    for k in GLOBAL_FIELDS:
        if ga.get(k) != gb.get(k):
            diffs.append(f"global.{k}: {name_a}={_short(ga.get(k))} / {name_b}={_short(gb.get(k))}")
    oa, ob = td_a.get("output", {}), td_b.get("output", {})
    for k in OUTPUT_SCALARS:
        if oa.get(k) != ob.get(k):
            diffs.append(f"output.{k}: {name_a}={oa.get(k)!r} / {name_b}={ob.get(k)!r}")
    sa, sb = td_a.get("segments", []), td_b.get("segments", [])
    if len(sa) != len(sb):
        diffs.append(f"segments 段数：{name_a}={len(sa)} / {name_b}={len(sb)}")
    for i, (x, y) in enumerate(zip(sa, sb), 1):
        for k in SEGMENT_FIELDS:
            if x.get(k) != y.get(k):
                diffs.append(
                    f"segments[{i}].{k}: {name_a}={_short(x.get(k))} / "
                    f"{name_b}={_short(y.get(k))}"
                )
    return diffs


def compare_topology(doc_a: dict, doc_b: dict, name_a: str, name_b: str) -> list[str]:
    ta, tb = topology_of(doc_a), topology_of(doc_b)
    return [f"拓扑.{k}: {name_a}={ta[k]!r} / {name_b}={tb[k]!r}"
            for k in ta if ta[k] != tb[k]]


def cmd_compare(paths: list[Path]) -> int:
    a, b = paths
    out("===== 01 预览 / 02 出片 副本一致性校验 =====")
    out(f"  A: {a}")
    out(f"  B: {b}")
    da, db = load_doc(a), load_doc(b)
    diffs = compare_timelines(extract_timeline(a), extract_timeline(b), a.name, b.name)
    topo = compare_topology(da, db, a.name, b.name)
    if topo:
        out("  [NOTE] 拓扑差异（属渲染档预期：01 含 4step LoRA / 02 全量去噪，不影响 timeline 语义）：")
        for d in topo:
            out(f"    {d}")
    if diffs:
        for d in diffs:
            out(f"  [DIFF] {d}")
        out(f"结论：时间线不一致（{len(diffs)} 处）—— N11 审片结论对 02 无效，须重新装配")
        return 1
    if topo:
        out(f"结论：时间线/场景锁完全一致 ✅；拓扑 {len(topo)} 处差异属 01/02 渲染档预期，"
            "N11 的 01 审片结论（构图/动作/台词）可直接用于 02 出片")
    else:
        out("结论：segments / totalFrames / frameRate / 场景锁 / 拓扑全部一致，"
            "N11 的 01 审片结论可直接用于 02 出片")
    return 0


def run_dual(args, rows: list[dict], fps: float, groups: list[str],
             scene_bible: str) -> int:
    """A1：同一份 CSV 分别装配 01 预览 + 02 出片，并自动校验一致性。"""
    pw, fw = args.preview_workflow, args.workflow
    for wf in (pw, fw):
        if not wf.is_file():
            die(f"底座工作流不存在：{wf}")
    pf, ff = read_fps(pw, fps), read_fps(fw, fps)
    if pf != ff:
        die(f"两份底座 frameRate 不一致（01={pf} / 02={ff}），segments 无法对齐")
    fps = ff
    out(f"\n双份装配：01 预览底座 {pw.name}  /  02 出片底座 {fw.name}  fps={fps}")
    if args.save_prefix:
        die("--dual 下 --save-prefix 会静默忽略，已拒绝；两份副本各自按文件名派生前缀，避免误解")

    targets = [args.group] if args.group else groups
    all_ok = True
    for g in targets:
        grp_rows = [r for r in rows if r["continuity_group"] == g]
        stem = args.out.stem + (f"_{g}" if len(targets) > 1 else "")
        p_out = args.out.with_name(f"{stem}_preview.json")
        f_out = args.out.with_name(f"{stem}_final.json")
        for out_path, wf in ((p_out, pw), (f_out, fw)):
            if out_path.resolve() == wf.resolve():
                die(f"--out 不能等于底座工作流，禁止覆盖权威原件：{out_path}")
        for out_path, wf in ((p_out, pw), (f_out, fw)):
            assemble(grp_rows, wf, out_path, fps, args.seed, "",
                     scene_bible, not args.no_dialogue_pace, args.ref_base, args.input_root)
        total = sum(int(r["length_frames"]) for r in grp_rows)
        out(f"\n[OK] {g}: {len(grp_rows)} 段 / {total} 帧 / {total / fps:.3f}s")
        out(f"       01 预览 -> {p_out}")
        out(f"       02 出片 -> {f_out}")
        diffs = compare_timelines(extract_timeline(p_out), extract_timeline(f_out),
                                  p_out.name, f_out.name)
        topo = compare_topology(load_doc(p_out), load_doc(f_out), p_out.name, f_out.name)
        if diffs:
            all_ok = False
            for d in diffs:
                out(f"  [DIFF] {d}")
            out(f"  [FAIL] {g}: 时间线不一致，禁止拿 01 审片结论去跑 02")
        else:
            out(f"  [PASS] {g}: segments / 场景锁 / 时间线完全一致"
                + (f"（拓扑 {len(topo)} 处差异属渲染档预期，已注明）" if topo else ""))
            for d in topo:
                out(f"  [NOTE] {d}")
    return 0 if all_ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="分镜表 CSV → H3 导演台 timeline_data 装配器")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="分镜表 CSV")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW, help="底座工作流 JSON")
    ap.add_argument("--out", type=Path, default=BASE / "out" / "H3-vibe-assembled.json",
                    help="输出副本路径（必须不同于底座，禁止覆盖权威原件）")
    ap.add_argument("--group", default="", help="只装配指定 continuity_group；不填则每组各出一份")
    ap.add_argument("--seed", type=int, default=None, help="统一 seed（不传则用 CSV seed 列首行/底座值）")
    ap.add_argument("--save-prefix", default="",
                    help="SaveVideo 输出前缀；不填则自动用 video/<输出文件名>，避免多组共用底座前缀互相覆盖")
    ap.add_argument("--fps", type=float, default=24.0, help="帧率，默认 24（与底座 frameRate 保持一致）")
    ap.add_argument("--style", choices=["comic", "live"], default="comic",
                    help="画风模式，仅影响体检告警，不改写内容。vibe 漫画格选 comic")
    ap.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT,
                    help="ComfyUI input 目录，用于资产检查与 refAudioStamp 指纹")
    ap.add_argument("--check-only", action="store_true", help="只跑体检门禁，不写任何文件")
    ap.add_argument("--dual", action="store_true",
                    help="同一份 CSV 装配 01 预览 + 02 出片两份副本，并自动校验 segments+拓扑一致")
    ap.add_argument("--preview-workflow", type=Path, default=DEFAULT_PREVIEW_WORKFLOW,
                    help="--dual 时的 01 快出预览底座（默认 H3-通用01）")
    ap.add_argument("--compare", type=Path, nargs=2, metavar=("预览副本", "出片副本"),
                    help="不装配，只独立校验两份工作流副本的 segments+拓扑是否一致")
    ap.add_argument("--strict-assets", action="store_true",
                    help="资产缺失或 input 根不存在时升级为 ERROR（出片前建议开启）")
    ap.add_argument("--scene-bible", type=Path, default=None,
                    help="场景圣经文本文件 → global.prompt + commonEnabled=True（generate 档必须；source/TTS 档勿用）")
    ap.add_argument("--no-dialogue-pace", action="store_true",
                    help="关闭对白节奏注入（默认开启，仅对挂音色的镜生效）")
    ap.add_argument("--ref-base", type=int, choices=[0, 1], default=0,
                    help="refs[].index 基数：0=本项目实跑验证（默认），1=旧版/部分导演台；audio 恒 0 基")
    ap.add_argument("--per-shot", action="store_true",
                    help="每镜单独装配成一份单段 workflow（实跑 A 方案：逐镜提交 + xfade 拼接）")
    args = ap.parse_args()

    if args.compare:
        sys.exit(cmd_compare(args.compare))

    if args.dual and args.per_shot:
        die("--dual 与 --per-shot 互斥：前者是组装配 01/02 双副本，后者是逐镜单段")

    rows = load_rows(args.csv)
    fps = read_fps(args.workflow, args.fps)
    out(f"分镜表：{args.csv}  ({len(rows)} 行)   帧率：{fps}   refs 基数：{args.ref_base}")

    groups: list[str] = []
    for r in rows:
        if r["continuity_group"] not in groups:
            groups.append(r["continuity_group"])
    out(f"连续组：{', '.join(groups)}  —— 每组必须一次提交，不能分多次跑（--per-shot 除外）")

    if args.group and args.group not in groups:
        die(f"指定的 --group {args.group} 不存在，可选：{', '.join(groups)}")

    selected = [r for r in rows if not args.group or r["continuity_group"] == args.group]

    scene_bible = ""
    if args.scene_bible:
        if not args.scene_bible.is_file():
            die(f"场景圣经文件不存在：{args.scene_bible}")
        scene_bible = args.scene_bible.read_text(encoding="utf-8").strip()
        out(f"场景锁：已载入 {args.scene_bible}（{len(scene_bible)} 字）→ global.prompt + commonEnabled=True")
    else:
        out("[NOTE] 未给 --scene-bible：generate 档会场景漂移，source/TTS 档则可留空。"
            "本项目实跑需注入场景圣经")

    errors, warns = preflight(selected, args.input_root, fps, args.style,
                              args.strict_assets, args.ref_base)
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

    if args.dual:
        sys.exit(run_dual(args, rows, fps, groups, scene_bible))

    if args.per_shot:
        out("\nper-shot 模式：每镜一份单段 workflow（实跑 A 方案）")
        assemble_per_shot(selected, args.workflow, args.out, fps, args.seed,
                          scene_bible, not args.no_dialogue_pace, args.ref_base,
                          args.input_root)
        out(f"\n[OK] 共 {len(selected)} 份单镜 workflow -> {args.out}")
        out("下一步：用 render_submit.py 逐镜提交，再 audio_tighten.py → concat_xfade.py --audio-fix 拼接")
        return

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
        assemble(grp_rows, args.workflow, out_path, fps, args.seed, args.save_prefix,
                 scene_bible, not args.no_dialogue_pace, args.ref_base, args.input_root)
        total = sum(int(r["length_frames"]) for r in grp_rows)
        out(f"\n[OK] {g}: {len(grp_rows)} 段 / {total} 帧 / {total/fps:.3f}s  ->  {out_path}")
        for r in grp_rows:
            out(f"       {r['shot_id']:6s}  {int(r['length_frames']):3d}帧  "
                f"P1={r['frame_key'] or '(空)'}  Audio={r['audio_tag']}")

    out("\n下一步：推荐用 --dual 一次装配 01 预览 + 02 出片两份副本（自动校验 segments+拓扑一致）"
        "\n        把两份副本分别拖进 ComfyUI → 01 试错审片 → 结论直接用于 02 出片"
        "\n        事后复验：python csv_to_timeline.py --compare <01 副本> <02 副本>")


if __name__ == "__main__":
    main()
