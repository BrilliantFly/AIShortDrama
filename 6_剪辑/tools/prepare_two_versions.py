#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N14 之后「两版产物」适配器 —— 成片版 / 片段版分叉。

背景（2026-11-21 拓扑定线）：
    主干 N15 的 concat_xfade.py 按 CSV 全段叠化拼出「成片版」；
    N17 的 edit_tool.py 需要「片段版」（未拼接的逐镜素材 + 剪辑单.md）才能做镜头取舍与入出点。
    两者是并列的产物线，不是对同一条成片拼两次。

本脚本只负责**片段版实体**与**成片版可执行命令**，不重复实现拼接、不改任何第三方原版：

    成片版 = 现有 audio_tighten.py -> concat_xfade.py -> qc_gate.py（命令写入 成片版命令.md）
    片段版 = 剧集/<EP>/制作成果/videos/MOTION-<EP>-<镜号>.mp4
             + 剧集/<EP>/剪辑单.md（草稿，整段保留，待人工确认可用带）
             + 剧集/<EP>/视频提示词.md 等上游文档骨架（供 edit_tool.py check 核对来源 ID）
             + 剧集/<EP>/制作成果/片段清单.csv

用法（在 6_剪辑 目录双击 activate.bat 后，或任意 Python 3.9+）：
    python tools/prepare_two_versions.py \
        --out-root  <render_submit.py --out-root 的交付根> \
        --project-root <N17 工程根> \
        --ep EP001 \
        --csv <shotlist.csv> \
        --fixed-dir <音轨精修输出目录>   # 可选，优先使用精修版
    python tools/prepare_two_versions.py ... --verify   # 生成后自动跑 edit_tool.py check
    python tools/prepare_two_versions.py ... --dry      # 只打印计划
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG_DIR = HERE / "ffmpeg"
DRAMA_EDIT = HERE / "drama-edit" / "scripts" / "edit_tool.py"
COMFY_PY = "D:/ComfyUI-aki-v3.2/python/python.exe"

VIDEO_RE = re.compile(r"SHOT-(\d{3,})-hd(?:-(\d+))?\.mp4$", re.IGNORECASE)
FIXED_RE = re.compile(r"SHOT-(\d{3,})-hd-音轨精修\.mp4$", re.IGNORECASE)
CSV_SHOT_RE = re.compile(r"[A-Za-z]*?(\d{3,})$")

UPSTREAM_DOCS = ("剧本.md", "分镜.md", "视频提示词.md", "视觉设定.md", "图片提示词.md")


# ---------------------------------------------------------------- utilities

def ffprobe_exe() -> str:
    for name in ("ffprobe.exe", "ffprobe"):
        p = FFMPEG_DIR / name
        if p.is_file():
            return str(p)
    return "ffprobe"  # 退回 PATH（activate.bat 已设置）


def probe_media(path: Path) -> dict:
    """返回 duration / width / height / fps；探测失败给安全默认值。"""
    cmd = [ffprobe_exe(), "-v", "error", "-show_entries",
           "format=duration", "-show_entries",
           "stream=width,height,r_frame_rate", "-of", "json", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        data = json.loads(r.stdout or "{}")
    except Exception:
        data = {}
    out = {"duration": 0.0, "width": 0, "height": 0, "fps": 24}
    try:
        out["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        pass
    for st in data.get("streams", []):
        if st.get("width"):
            out["width"] = int(st["width"])
            out["height"] = int(st.get("height", 0) or 0)
            rate = str(st.get("r_frame_rate", "24/1"))
            try:
                a, b = rate.split("/")
                out["fps"] = round(float(a) / float(b)) if float(b) else 24
            except (ValueError, ZeroDivisionError):
                pass
            break
    return out


def read_csv_order(csv_path: Path) -> list[dict]:
    """读 19 字段 shotlist，返回按表顺序的镜号与时长。"""
    rows = []
    if not csv_path or not csv_path.is_file():
        return rows
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = (row.get("shot_id") or "").strip()
            m = CSV_SHOT_RE.search(sid)
            if not m:
                continue
            try:
                dur = float(row.get("duration_sec") or 0)
            except ValueError:
                dur = 0.0
            rows.append({"num": m.group(1), "duration": dur,
                         "summary": (row.get("summary") or "").strip()})
    return rows


def collect_videos(videos_dir: Path, fixed_dir: Path | None) -> dict[str, Path]:
    """镜号(3位) -> 实际素材路径。优先级：音轨精修版 > -1 > 无后缀 > -2。"""
    chosen: dict[str, tuple[int, Path]] = {}
    if fixed_dir and fixed_dir.is_dir():
        for p in sorted(fixed_dir.glob("*.mp4")):
            m = FIXED_RE.match(p.name)
            if m:
                chosen[m.group(1)] = (0, p)
    if videos_dir.is_dir():
        for p in sorted(videos_dir.glob("*.mp4")):
            m = VIDEO_RE.match(p.name)
            if not m:
                continue
            num, tag = m.group(1), m.group(2)
            rank = 1 if tag == "1" else (2 if tag is None else 3 + int(tag))
            if num not in chosen or rank < chosen[num][0]:
                chosen[num] = (rank, p)
    return {k: v[1] for k, v in chosen.items()}


def ensure_doc(dst: Path, text: str, force: bool) -> str:
    if dst.exists() and not force:
        return "保留(已存在)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return "生成"


# ---------------------------------------------------------------- builders

def build_motion_doc(ep: str, items: list[dict]) -> str:
    lines = [
        f"# {ep} 视频提示词（N17 接口适配骨架）",
        "",
        "> 由 `prepare_two_versions.py` 生成，用途是让 `edit_tool.py check` 能核对 MOTION 来源 ID。",
        "> 若上游 drama 项目已有真实《视频提示词.md》，请用 `--drama-dir` 指向它；本骨架不改写上游语义。",
        "",
    ]
    for it in items:
        lines += [
            f"## {it['motion']}",
            "",
            f"- 分镜：SHOT-{ep}-{it['num']}",
            f"- 说明：由主干 shot_id 映射，逐镜素材见 制作成果/videos/{it['motion']}.mp4",
            "",
        ]
    return "\n".join(lines)


def build_cut_list(ep: str, items: list[dict], meta: dict) -> str:
    total = sum(it["duration"] for it in items)
    w, h, fps = meta.get("width", 0), meta.get("height", 0), meta.get("fps", 24)
    lines = [
        f"# {ep} 剪辑单（草稿 · 由 prepare_two_versions.py 生成）",
        "",
        f"- 成片目标时长：{total:.2f} 秒",
        f"- 画幅与帧率：{w}x{h} · {fps}fps",
        "- 交付响度：-16 LUFS",
        "- 字幕：待定（生成端画面无文字，字幕在 N17 后期烧录）",
        "",
        "> 草稿规则：每个 CUT 整段保留，入点 0、出点为素材实测时长。",
        "> 人工确认可用带后改写入/出点与取舍理由；未采用镜头在此行下方登记理由。",
        "",
    ]
    for idx, it in enumerate(items, 1):
        d = it["duration"]
        lines += [
            f"## CUT-{ep}-{idx:03d} · 镜头 {it['num']}（草稿）",
            "",
            f"- 来源：{it['motion']} · 制作成果/videos/{it['motion']}.mp4",
            "- 入点：0.00",
            f"- 出点：{d:.2f}",
            f"- 时长：{d:.2f}",
            "- 取舍：整段保留（草稿，待人工标可用带）",
            "- 声音：保留原声",
            "- 字幕：无",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def build_film_commands(args, shots: list[str], film_out: Path) -> str:
    py = args.py
    post = args.post_dir
    v = args.videos
    fixed = f' --audio-fix --fixed-dir "{args.fixed_dir}"' if args.fixed_dir and args.fixed_dir.is_dir() else ""
    talk = ",".join(shots)
    return "\n".join([
        f"# {args.ep} 成片版命令（activate.bat 环境下执行；由 prepare_two_versions.py 生成）",
        "",
        "成片版 = N14 音轨精修 → N15 叠化拼接 → N16 质检，输出单一全片 mp4。",
        "片段版已生成在 剧集/<EP>/，两者互不取代。",
        "",
        "```bash",
        f'"{py}" "{post}/audio_tighten.py" --videos "{v}" --out "{args.fixed_dir or (args.out_root / "精修")}" --all --talk-shots {talk}',
        f'"{py}" "{post}/concat_xfade.py" --videos "{v}" --list "{args.csv or (args.out_root / "N7-出片清单.csv")}"{fixed} --transition 0.35 --out "{film_out}"',
        f'"{py}" "{post}/qc_gate.py" --videos "{v}" --list "{args.csv or (args.out_root / "N7-出片清单.csv")}" --report "{film_out.parent / "qc_report.json"}"',
        "```",
        "",
        "注：后期脚本依赖 numpy / imageio-ffmpeg / av / Pillow，必须用 ComfyUI 的 python 跑。",
    ]) + "\n"


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="N14 之后生成两版产物：成片版（命令）+ 片段版（N17 可消费的工程与剪辑单）")
    ap.add_argument("--out-root", type=Path, required=True,
                    help="render_submit.py 的 --out-root 交付根（其下 videos/ 放逐镜 mp4）")
    ap.add_argument("--videos", type=Path, help="逐镜 mp4 目录，默认 <out-root>/videos")
    ap.add_argument("--fixed-dir", type=Path, help="音轨精修输出目录（优先使用，N14 产物）")
    ap.add_argument("--csv", type=Path, help="shotlist.csv（提供镜序与时长；缺省按文件名排序）")
    ap.add_argument("--project-root", type=Path, required=True, help="N17 工程根（其下建 剧集/<EP>/）")
    ap.add_argument("--ep", required=True, help="集号，如 EP001")
    ap.add_argument("--drama-dir", type=Path, help="上游 drama 项目目录（含 剧本.md 等，优先复制真实文档）")
    ap.add_argument("--post-dir", type=Path, help="后期与质检脚本目录（用于生成成片版命令）")
    ap.add_argument("--py", default=COMFY_PY, help="ComfyUI python.exe（后期脚本依赖）")
    ap.add_argument("--film-out", type=Path, help="成片版输出 mp4，默认 <out-root>/成片/<EP>-全片.mp4")
    ap.add_argument("--dry", action="store_true", help="只打印计划，不写文件")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的剪辑单/文档骨架（默认保护人工编辑）")
    ap.add_argument("--verify", action="store_true", help="生成后自动执行 edit_tool.py check")
    args = ap.parse_args()

    # 让下游 edit_tool.py 的 check/render 能探测到随包 ffmpeg/ffprobe
    if FFMPEG_DIR.is_dir() and str(FFMPEG_DIR) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

    args.videos = args.videos or (args.out_root / "videos")
    if args.post_dir is None:
        # 从本文件位置反推，避免硬编码含零宽字符的根目录名
        args.post_dir = (HERE.parent.parent / "1_AI漫剧全流程解决方案" /
                        "AI漫剧全流程自动化方案" / "后期与质检")
    film_out = args.film_out or (args.out_root / "成片" / f"{args.ep}-全片.mp4")

    found = collect_videos(args.videos, args.fixed_dir)
    if not found:
        print(f"[错误] 在 {args.videos} 未找到 SHOT-<镜号>-hd*.mp4；先用 N12 出片。", file=sys.stderr)
        return 2

    csv_rows = read_csv_order(args.csv)
    order = [r["num"] for r in csv_rows if r["num"] in found]
    order += [n for n in sorted(found) if n not in order]
    csv_dur = {r["num"]: r["duration"] for r in csv_rows}

    ep_dir = args.project_root / "剧集" / args.ep
    media_dir = ep_dir / "制作成果" / "videos"
    items = []
    for num in order:
        src = found[num]
        info = probe_media(src)
        dur = csv_dur.get(num) or info["duration"]
        motion = f"MOTION-{args.ep}-{num}"
        items.append({"num": num, "motion": motion, "src": src,
                      "dst": media_dir / f"{motion}.mp4", "duration": dur,
                      "info": info})

    print(f"两版产物 · {args.ep}")
    print(f"  成片版：{film_out}")
    print(f"  片段版：{media_dir}  ({len(items)} 段)")
    if args.dry:
        for it in items:
            print(f"    {it['motion']:22s} <- {it['src'].name}  {it['duration']:.2f}s")
        return 0

    media_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        shutil.copy2(it["src"], it["dst"])   # 复制不移动：主干产物保持原样

    meta = items[0]["info"]
    print("  " + ensure_doc(ep_dir / "剪辑单.md", build_cut_list(args.ep, items, meta), args.force) + " 剪辑单.md")
    print("  " + ensure_doc(ep_dir / "视频提示词.md", build_motion_doc(args.ep, items), args.force) + " 视频提示词.md")

    for name in UPSTREAM_DOCS:
        dst = ep_dir / name
        if name == "视频提示词.md":
            continue
        if dst.exists() and not args.force:
            print(f"  保留(已存在) {name}")
            continue
        src = (args.drama_dir / name) if args.drama_dir and (args.drama_dir / name).is_file() else None
        if src:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  复制上游 {name}")
        else:
            ensure_doc(dst, f"# {args.ep} {name[:-3]}（接口占位）\n\n> 由 prepare_two_versions.py 生成，"
                            f"待用 --drama-dir 指向真实上游文档后替换。\n", args.force)
            print(f"  占位 {name}")

    manifest = ep_dir / "制作成果" / "片段清单.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cut", "motion_id", "shot_id", "source_file", "clip_file",
                    "duration_sec", "width", "height", "fps"])
        for i, it in enumerate(items, 1):
            w.writerow([f"CUT-{args.ep}-{i:03d}", it["motion"], f"S{it['num']}",
                        it["src"].name, it["dst"].name, f"{it['duration']:.3f}",
                        it["info"]["width"], it["info"]["height"], it["info"]["fps"]])
    print(f"  生成 片段清单.csv")

    (film_out.parent).mkdir(parents=True, exist_ok=True)
    ensure_doc(ep_dir / "制作成果" / "成片版命令.md",
               build_film_commands(args, order, film_out), True)
    print(f"  生成 成片版命令.md")

    ensure_doc(ep_dir / "制作成果" / "两版产物说明.md", "\n".join([
        f"# {args.ep} 两版产物（2026-11-21 拓扑定线）", "",
        "| 版本 | 位置 | 用途 |", "|---|---|---|",
        f"| 成片版 | `{film_out}` | N15 叠化拼接的完整片，N16 质检后归档；可复现、快 |",
        f"| 片段版 | `剧集/{args.ep}/制作成果/videos/` + `剧集/{args.ep}/剪辑单.md` | **专供 N17**：人工取舍、入出点、转场、背景音、字幕、响度、交付验收 |", "",
        "两版并列，不是对同一条成片拼两次：成片版按 CSV 全段直出，片段版保留逐镜素材供剪辑层重新合成。",
        "", "工作流：", "",
        "1. 人工编辑 `剪辑单.md`（可用带、入出点、未采用镜头理由、字幕、音效、音色登记）。",
        "2. `python tools/drama-edit/scripts/edit_tool.py check 剧集/<EP> --project-root <工程根>`",
        "3. `... render ...` 产出 `制作成果/成片/`；`... verify ...` 出测量值。",
        "4. 把本次新经验追加到 `99_经验库/工作流优化经验库.md`。",
    ]) + "\n", True)

    if args.verify:
        if not DRAMA_EDIT.is_file():
            print("[警告] 未找到 edit_tool.py，跳过 check", file=sys.stderr)
            return 0
        cmd = [sys.executable, str(DRAMA_EDIT), "check", str(ep_dir),
               "--project-root", str(args.project_root)]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print("--- edit_tool.py check ---")
        print((r.stdout or "")[-2500:])
        if r.stderr:
            print("stderr:", r.stderr[-800:])
        print("check exit:", r.returncode)
        return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
