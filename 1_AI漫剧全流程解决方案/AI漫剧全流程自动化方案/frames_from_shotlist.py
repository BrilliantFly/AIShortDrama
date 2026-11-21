#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frames_from_shotlist.py — 备选出帧脚本：火山方舟 / 即梦「图片 4.0」(Seedream 4.0) 在线 API

定位：当不想维护本地 ComfyUI 模型／显存时的备选引擎。默认引擎是
`frames_from_shotlist_comfy.py`；两者共用 `frames_common.py` 的四段重组、路径契约、
frame_key 回填与归档逻辑，差别只有「提交目标」与「阶段数」：

  * 在线版：一次请求把「四段 prompt + 三张板」交给 /images/generations，直接出最终帧
    （Seedream 4.0 单次支持 ≤10~14 张参考图，输入图不额外计费）。
  * 本地版：Stage 0 T2I → 2511 Pass 1 → Pass 2，三次 /prompt。

**换成在线引擎不能绕开 MiniMax H3 Community License**——全链路商用条件不变
（见 N5-ComfyUI实现卡.md 1.2）。

命令示例
--------
  python frames_from_shotlist.py --emit-inputs-template out/n5_inputs.json
  python frames_from_shotlist.py --dry-run --inputs out/n5_inputs.json
  set ARK_API_KEY=<你的 key>
  python frames_from_shotlist.py --inputs out/n5_inputs.json \
      --input-root "<ComfyUI input>" --seed 42
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

from frames_common import (  # noqa: E402
    BASE, DEFAULT_CSV, DEFAULT_MANIFEST,
    append_manifest, board_paths, compose_prompt, die,
    emit_inputs_template, fill_frame_key, frame_rel, load_n5_inputs,
    load_shotlist_rows, out, seeds, selected_rows, shot_number,
    validate_rows,
)

DEFAULT_INPUT_ROOT = Path("D:/ComfyUI-aki-v3.2/ComfyUI/input")
DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
DEFAULT_MODEL = "doubao-seedream-4-0-20260415"


def parse_args():
    ap = argparse.ArgumentParser(
        description="shotlist.csv → 火山方舟 Seedream 4.0 逐镜出帧（备选在线引擎）"
    )
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="分镜表 CSV")
    ap.add_argument("--inputs", type=Path, default=None,
                    help="四段重组材料 JSON（由 --emit-inputs-template 生成并填好）")
    ap.add_argument("--emit-inputs-template", type=Path, default=None,
                    help="生成待填材料模板后退出")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印每镜请求摘要，不调 API、不写图、不回填")
    ap.add_argument("--api-key-env", default="ARK_API_KEY",
                    help="存放火山方舟 API Key 的环境变量名（默认 ARK_API_KEY）")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="API 地址")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="模型 ID")
    ap.add_argument("--size", default="2560x1440",
                    help="出图尺寸，16:9；下采样到 ≥1344 宽后入库")
    ap.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT,
                    help="ComfyUI input 根目录，三张板从这里读、最终帧落这里")
    ap.add_argument("--seed", type=int, default=42, help="基础 seed，逐镜递增破缓存")
    ap.add_argument("--group", default="", help="只出指定 continuity_group")
    ap.add_argument("--only", action="append", default=[],
                    help="只出指定镜号，可多次（单镜重跑）")
    ap.add_argument("--no-fill", action="store_true", help="不回填 shotlist.csv 的 frame_key")
    ap.add_argument("--force", action="store_true",
                    help="最终帧已存在也强制重出（默认跳过 >200KB 的成品）")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                    help="归档 JSONL")
    return ap.parse_args()


def board_data_urls(row: dict, input_root: Path, strict: bool) -> tuple[list[str], list[str]]:
    urls, misses = [], []
    for rel in board_paths(row):
        p = input_root / rel
        if p.is_file():
            # 实跑回灌：PATH_CONTRACT 允许 .webp，旧版一律标 image/jpeg 会被 API 误判
            ext = p.suffix.lower()
            mime = {".png": "image/png", ".webp": "image/webp",
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/jpeg")
            urls.append(
                f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")
            )
        else:
            misses.append(rel)
            if strict:
                die(f"参考板不存在：{p}（三张板必须全片固定、不按镜重排）")
    return urls, misses


def build_request(row: dict, prompt: str, input_root: Path, seed: int,
                  model: str, size: str, strict: bool) -> tuple[dict, list[str]]:
    images, misses = board_data_urls(row, input_root, strict)
    return {
        "model": model,
        "prompt": prompt,
        "image": images,
        "size": size,
        "n": 1,
        "response_format": "url",
        "seed": seed,
        "watermark": False,
    }, misses


def post_generations(endpoint: str, api_key: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def save_result(res: dict, dest: Path) -> None:
    data = (res.get("data") or [])
    if not data:
        die(f"API 未返回图片：{res}")
    item = data[0]
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=180) as r:
            raw = r.read()
    elif item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    else:
        die(f"API 返回里既无 url 也无 b64_json：{item}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)


def main() -> None:
    args = parse_args()
    rows = load_shotlist_rows(args.csv)

    if args.emit_inputs_template:
        emit_inputs_template(rows, args.emit_inputs_template)
        return

    selected = selected_rows(rows, args.group, args.only)
    out(f"分镜表：{args.csv}  ({len(selected)}/{len(rows)} 镜)   引擎：即梦 / Seedream 4.0（备选）")

    contract_errors = validate_rows(selected)
    if contract_errors:
        for e in contract_errors:
            out(f"  [ERROR] {e}")
        die("路径契约或三张板不齐，先修 shotlist.csv")

    inputs = load_n5_inputs(args.inputs)
    errors: list[str] = []
    plans = []
    for r in selected:
        sid = r["shot_id"]
        prompt = compose_prompt(inputs, sid, errors)
        # seed 从 shot_id 派生（实跑回灌）：全量/--only 单镜重跑一致，可复现
        single = seeds(args.seed, sid)[0]
        plans.append({
            "shot_id": sid,
            "frame_key": frame_rel(r),
            "prompt": prompt or "<材料待填>",
            "seed": single,
            "boards": board_paths(r),
        })

    if errors:
        out("\n===== 四段重组材料校验 =====")
        for e in errors:
            out(f"  [ERROR] {e}")

    if args.dry_run:
        out("\n===== DRY RUN：不调 API、不写图、不回填 =====")
        for p in plans:
            payload, misses = build_request(
                next(r for r in selected if r["shot_id"] == p["shot_id"]),
                p["prompt"], args.input_root, p["seed"], args.model,
                args.size, strict=False,
            )
            head = p["prompt"].splitlines()[0][:60] if p["prompt"] else ""
            out(f"\n[{p['shot_id']}] -> {p['frame_key']}  seed={p['seed']}")
            out(f"  prompt: {head}…")
            out(f"  参考板 {len(payload['image'])} 张（输入图不计费）：{', '.join(p['boards'])}")
            if misses:
                out(f"  [WARN] 本地缺失 {len(misses)} 张板，实跑会阻断：{', '.join(misses)}")
            out(f"  单次请求：1 张输出 × 0.20 元；失败不计费")
        out(f"\n材料状态：{'齐备' if not errors else '待填（见上）'}")
        sys.exit(1 if errors else 0)

    if errors:
        die("四段重组材料未齐备，禁止实跑（先 --emit-inputs-template 填好再用 --inputs 指回）")
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        die(f"未找到 API Key：请设置环境变量 {args.api_key_env}（实跑必需；--dry-run 不需要）")
    if not args.input_root.is_dir():
        die(f"实跑需要 ComfyUI input 根目录存在：{args.input_root}（或改 --input-root）")

    for p, r in zip(plans, selected):
        payload, _ = build_request(
            r, p["prompt"], args.input_root, p["seed"], args.model,
            args.size, strict=True,
        )
        dest = args.input_root / p["frame_key"]
        if not args.force and dest.is_file() and dest.stat().st_size > 200_000:
            out(f"\n===== 跳过 {p['shot_id']}：最终帧已存在 {dest.stat().st_size//1024}KB"
                "（加 --force 强制重出）=====")
            continue
        out(f"\n===== 提交 {p['shot_id']} =====")
        res = post_generations(args.endpoint, api_key, payload)
        save_result(res, dest)
        if not args.no_fill:
            fill_frame_key(args.csv, p["shot_id"], p["frame_key"])
        append_manifest(args.manifest, {
            "shot_id": p["shot_id"],
            "engine": "seedream-api",
            "frame_key": p["frame_key"],
            "prompt": p["prompt"],
            "slots": {"image_1_2_3": p["boards"]},
            "seed": p["seed"],
            "outputs": {"final": p["frame_key"]},
            "qc_status": "待审",
        }, dedup_key="shot_id")
        out(f"  [OK] -> {dest}；回填 + 归档完成")


if __name__ == "__main__":
    main()
