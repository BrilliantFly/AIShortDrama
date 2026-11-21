#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单镜口径探针：实测导演台的 refs 基数 / imageFile-subfolder 写法 / Audio 槽位。

待核实分歧（经验库 2.1 + 文档调整清单）：
  * refs[].index 是 0 基还是 1 基？（本项目实跑 0 基，drama 文档/第二版旧脚本 1 基）
  * imageFile 只写文件名 + subfolder 分目录，还是整路径塞 imageFile？
  * refAudios 是否恒 0 基？（经验库：audio 勿与图片一起改）

本脚本生成两份探针 workflow（--ref-base 0 与 1），各自只挂一张「已知身份板」到
<Picture 2>，prompt 要求模型复述画面人物。人工跑一次对照片，哪版锁定到正确人物，
就用哪版基数装配全片。不连服务、不改任何现有文件，只输出两份 JSON 供 GUI 拖入。

用法：
  python probe_refs.py --workflow 工作流底座/H3-通用02....json \\
      --sheet "街对面/chars/IMG-SU-SHEET.png" \\
      --out-dir out/probe --seed 42
  # 若音色也要验音频槽：加 --voice "街对面/voices/V-SU-tone-ref.wav"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def split_path(rel: str) -> tuple[str, str]:
    p = (rel or "").replace("\\", "/").strip()
    if "/" in p:
        sub, name = p.rsplit("/", 1)
        return sub, name
    return "", p


def build_probe(workflow: Path, sheet: str, voice: str, base: int,
                seed: int, fps: float) -> dict:
    doc = json.loads(workflow.read_text(encoding="utf-8"))
    node = next((n for n in doc.get("nodes", []) if n.get("type") == "MiniMaxH3Director"), None)
    if not node:
        raise SystemExit("底座里找不到 MiniMaxH3Director")
    wv = node["widgets_values"]
    ti = next(i for i, x in enumerate(wv)
              if isinstance(x, str) and x.strip().startswith("{") and "segments" in x)
    td = json.loads(wv[ti])

    sub, name = split_path(sheet)
    # 关键：base=0 → index=1（<Picture 2>）；base=1 → index=2
    refs = [
        {"index": base, "imageFile": "", "fileName": "", "type": "input", "subfolder": ""},
        {"index": 1 + base, "imageFile": name, "fileName": name, "type": "input", "subfolder": sub},
    ]
    audios = []
    if voice:
        vsub, vname = split_path(voice)
        audios = [{"index": 0, "audioFile": vname, "fileName": vname,
                   "type": "input", "subfolder": vsub}]

    frames = 102
    td["segments"] = [{
        "id": "seg_probe", "start": 0, "length": frames, "frameCount": frames,
        "durationSec": round(frames / fps, 3),
        "prompt": ("PROBE TEST. Single person, static medium close-up, neutral light. "
                   "Reproduce EXACTLY the person and face shown in <Picture 2>. "
                   "Do not add anyone else. Hold still through the last frame."),
        "negativePrompt": "text, subtitles, watermark, extra persons, deformed face",
        "taskType": "", "refs": refs, "refAudios": audios, "refVideos": [],
        "genImage": {"imageFile": "", "fileName": ""},
    }]
    td["totalFrames"] = frames
    td["durationSec"] = round(frames / fps, 3)
    wv[ti] = json.dumps(td, ensure_ascii=False)
    wv[4] = int(seed)
    for n in doc["nodes"]:
        if n.get("type") == "SaveVideo" and n.get("widgets_values"):
            n["widgets_values"][0] = f"video/PROBE_refbase{base}"
            break
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description="refs 口径单镜探针（生成 0基/1基两份对比）")
    ap.add_argument("--workflow", type=Path, required=True)
    ap.add_argument("--sheet", required=True, help="已知身份板相对 input 根路径，如 街对面/chars/IMG-SU-SHEET.png")
    ap.add_argument("--voice", default="", help="可选：参考音色相对 input 根路径（验 audio 槽）")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fps", type=float, default=24.0)
    a = ap.parse_args()

    a.out_dir.mkdir(parents=True, exist_ok=True)
    for base in (0, 1):
        doc = build_probe(a.workflow, a.sheet, a.voice, base, a.seed, a.fps)
        p = a.out_dir / f"probe_refbase{base}.json"
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] ref-base={base} -> {p}")
    print("\n === 实测步骤 ===")
    print(" 1. 确认 --sheet 指的身份板在 ComfyUI input/ 下真实存在且是唯一可辨的人。")
    print(" 2. 把两份 probe_refbase*.json 分别拖进 ComfyUI，各出一次片（同 seed）。")
    print(" 3. 抽两片的中点帧：哪一片的人物脸与身份板一致，哪版的 refs 基数就是对的。")
    print(" 4. 若 0 基对 → csv_to_timeline 用默认；若 1 基对 → 装配全片加 --ref-base 1。")
    print(" 5. 音色槽：两份探针的 refAudios 都是 index 0；若只有 0 基片音色对，说明 audio 也是 0 基（经验库结论）。")


if __name__ == "__main__":
    main()
