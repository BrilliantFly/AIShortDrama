#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frames_from_shotlist_comfy.py — 默认出帧脚本：本地 ComfyUI `/prompt` 三阶段驱动

路线：novelist → drama → 【本脚本 + 本地 ComfyUI】 → shotlist.csv → csv_to_timeline.py → H3 (r2v)

三阶段（对应 N5-ComfyUI实现卡.md 2.2，A3 槽位裁断）：
  Stage 0 · T2I（Qwen-Image 基座 / 2512）      : 四段重组 prompt → 底图，不挂任何板
  Pass 1 · 2511 编辑                            : image_1=底图 / image_2=SHEET / image_3=PLATE
  Pass 2 · 2511 编辑                            : image_1=Pass1 输出 / image_2=PAIR / image_3=留空
  → 只有 Pass 2 的最终帧进 input/<项目>/frames/ 并回填 frame_key。

`image_1` 永远是被编辑的目标图，绝不是 SHEET；Pass 2 的 image_3 即使有余量也留空，
绝不按镜重排。H3 侧 refs index 2/3/4 仍是三张独立板，底图/中间帧不挂 H3。

工作流模板（--workflow-template）
--------------------------------
真实 ComfyUI 节点 ID 由实机模板提供，本脚本只负责表驱动、槽位固定、命名、取回与回填。
模板 JSON 形如：

  {
    "stage0": { ...ComfyUI /prompt API 的 prompt dict... },
    "pass1":  { ... },
    "pass2":  { ... }
  }

其中字符串用 {{PROMPT}} / {{SEED}} / {{FILENAME}} / {{IMAGE_1}} / {{IMAGE_2}} /
{{IMAGE_3}} 占位，脚本递归替换。模板可从 --emit-workflows 导出的驱动计划照着搭。
不提供模板时只能跑 --dry-run / --emit-workflows / --emit-inputs-template（不连服务）。

命令示例
--------
  python frames_from_shotlist_comfy.py --emit-inputs-template out/n5_inputs.json
  python frames_from_shotlist_comfy.py --dry-run --inputs out/n5_inputs.json
  python frames_from_shotlist_comfy.py --emit-workflows out/wf --inputs out/n5_inputs.json
  python frames_from_shotlist_comfy.py --inputs out/n5_inputs.json \
      --workflow-template n5_comfy_template.json --server 127.0.0.1:8188 \
      --input-root "<ComfyUI input>" --seed 42
  python frames_from_shotlist_comfy.py --inputs out/n5_inputs.json --dry-run --only S004
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from frames_common import (  # noqa: E402
    BASE, DEFAULT_CSV, DEFAULT_MANIFEST,
    append_manifest, board_paths, compose_prompt, die, edit_instructions,
    emit_inputs_template, fill_frame_key, frame_rel, load_n5_inputs,
    load_shotlist_rows, out, seeds, selected_rows, validate_rows, work_rel,
)

DEFAULT_INPUT_ROOT = Path("D:/ComfyUI-aki-v3.2/ComfyUI/input")
STAGE_KEYS = ("stage0", "pass1", "pass2")
STAGE_TITLES = {
    "stage0": "Stage 0 · T2I 出底图（不挂板）",
    "pass1": "Pass 1 · 2511 锁身份 + 空间",
    "pass2": "Pass 2 · 2511 锁服装 / 站位",
}


def parse_args():
    ap = argparse.ArgumentParser(
        description="shotlist.csv → 本地 ComfyUI 逐镜出帧（T2I + 2511 两 pass）"
    )
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="分镜表 CSV")
    ap.add_argument("--inputs", type=Path, default=None,
                    help="四段重组材料 JSON（由 --emit-inputs-template 生成并填好）")
    ap.add_argument("--emit-inputs-template", type=Path, default=None,
                    help="生成待填材料模板后退出")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印每镜三阶段计划，不连 ComfyUI、不写图、不回填")
    ap.add_argument("--emit-workflows", type=Path, default=None,
                    help="把每镜三阶段驱动计划导出到目录（不连服务）")
    ap.add_argument("--server", default="127.0.0.1:8188", help="ComfyUI 地址 host:port")
    ap.add_argument("--workflow-template", type=Path, default=None,
                    help="三阶段 ComfyUI /prompt 模板 JSON（实跑必需）")
    ap.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT,
                    help="ComfyUI input 根目录，最终帧落 <root>/<frame_key>")
    ap.add_argument("--seed", type=int, default=42, help="基础 seed，三阶段按镜号递增")
    ap.add_argument("--group", default="", help="只出指定 continuity_group")
    ap.add_argument("--only", action="append", default=[],
                    help="只出指定镜号，可多次（单镜重跑）")
    ap.add_argument("--no-fill", action="store_true", help="不回填 shotlist.csv 的 frame_key")
    ap.add_argument("--force", action="store_true",
                    help="最终帧已存在也强制重出（默认跳过 >200KB 的成品，支持断点续跑）")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                    help="归档 JSONL（每镜一行：prompt / 槽位 / 3 个 seed / 输出 / 审片结论）")
    ap.add_argument("--timeout", type=int, default=900, help="单次 /history 轮询超时（秒）")
    return ap.parse_args()


def validate_template(template: dict) -> list[str]:
    """实跑前校验：每段必须是合法 /prompt dict，声明的 _output_node 需在段内且为 SaveImage。"""
    errs: list[str] = []
    stages = [k for k in STAGE_KEYS if k in template]
    if not stages:
        return ["模板无 stage0/pass1/pass2 任一段"]
    for k in stages:
        seg = template[k]
        if not isinstance(seg, dict):
            errs.append(f"{k} 不是 prompt dict")
            continue
        for nid, node in seg.items():
            if nid.startswith("_"):
                continue
            if not isinstance(node, dict) or "class_type" not in node:
                errs.append(f"{k}.{nid} 缺 class_type")
        expected = str(seg.get("_output_node", "") or template.get("_output_node", "") or "")
        if expected:
            node = seg.get(expected)
            if node is None:
                errs.append(f"{k}: 声明的输出节点 {expected} 不在该段")
            elif node.get("class_type") not in ("SaveImage", "SaveVideo"):
                errs.append(f"{k}: 输出节点 {expected} 是 {node.get('class_type')}，应为 SaveImage/SaveVideo")
    return errs


def render_template(wf, mapping: dict):
    """递归把 {{KEY}} 占位符替换成实际值。"""
    if isinstance(wf, str):
        for k, v in mapping.items():
            wf = wf.replace("{{" + k + "}}", str(v))
        return wf
    if isinstance(wf, dict):
        return {k: render_template(v, mapping) for k, v in wf.items()}
    if isinstance(wf, list):
        return [render_template(v, mapping) for v in wf]
    return wf


def build_plan(row: dict, inputs: dict | None, base_seed: int,
               errors: list[str]) -> dict:
    sid = row["shot_id"]
    prompt = compose_prompt(inputs, sid, errors)
    e1, e2 = edit_instructions(inputs)
    rel = frame_rel(row)
    base = work_rel(row, "base")
    p1 = work_rel(row, "p1")
    sheet, plate, pair = board_paths(row)
    # seed 从 shot_id 派生（实跑回灌）：全量/--only 单镜重跑得到相同 seed，可复现
    s0, s1, s2 = seeds(base_seed, sid)
    stages = [
        {
            "key": "stage0", "title": STAGE_TITLES["stage0"],
            "prompt": prompt or "<材料待填>", "seed": s0,
            "filename_prefix": Path(base).stem, "output_rel": base,
            "slots": {},
        },
        {
            "key": "pass1", "title": STAGE_TITLES["pass1"],
            "prompt": e1, "seed": s1,
            "filename_prefix": Path(p1).stem, "output_rel": p1,
            "slots": {"image_1": base, "image_2": sheet, "image_3": plate},
        },
        {
            "key": "pass2", "title": STAGE_TITLES["pass2"],
            "prompt": e2, "seed": s2,
            "filename_prefix": Path(rel).stem, "output_rel": rel,
            "slots": {"image_1": p1, "image_2": pair, "image_3": ""},
        },
    ]
    return {
        "shot_id": sid, "continuity_group": row["continuity_group"],
        "frame_key": rel, "engine": "local-comfyui",
        "stages": stages,
        "h3_boundary": {
            "refs_index_1": rel,
            "refs_index_2_3_4": [sheet, plate, pair],
            "internal_only": [base, p1],
        },
    }


def print_plan(plan: dict) -> None:
    out(f"\n[{plan['shot_id']}]  最终帧 -> {plan['frame_key']}")
    for s in plan["stages"]:
        slots = s["slots"]
        if slots:
            slot_txt = (
                f"image_1={slots['image_1'] or '(空)'} | "
                f"image_2={slots['image_2'] or '(空)'} | "
                f"image_3={slots['image_3'] or '(空·留空不重排)'}"
            )
        else:
            slot_txt = "无参考图槽（纯 T2I）"
        head = s["prompt"].splitlines()[0][:60] if s["prompt"] else ""
        out(f"  {s['title']}")
        out(f"    seed={s['seed']}  {slot_txt}")
        out(f"    prompt: {head}…")
        out(f"    -> {s['output_rel']}")


# ---------------------------------------------------------------- ComfyUI HTTP API

def post_prompt(server: str, wf: dict) -> str:
    body = json.dumps({"prompt": wf}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://{server}/prompt", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 实跑回灌：HTTP 400 多为 node_errors / 缺模型，读 body 给出结构化原因
        detail = e.read().decode("utf-8", errors="replace")[:800]
        die(f"ComfyUI /prompt 返回 HTTP {e.code}：{detail}")
    if "prompt_id" not in res:
        ne = res.get("node_errors") or {}
        detail = f" node_errors={json.dumps(ne, ensure_ascii=False)[:600]}" if ne else ""
        die(f"/prompt 未返回 prompt_id：{res}{detail}")
    return res["prompt_id"]


def wait_output(server: str, prompt_id: str, timeout: int,
                expected_node: str = "") -> dict:
    """取输出图。expected_node 指定时只认该节点；否则按 SaveImage 节点优先。

    实跑回灌：原版取「第一个含 images 节点」的 imgs[0]，多 SaveImage/Preview
    的工作流会取错图。模板可用 {{OUTPUT_NODE}} 声明唯一的最终保存节点 ID。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://{server}/history/{prompt_id}", timeout=30
            ) as r:
                hist = json.loads(r.read().decode("utf-8"))
            entry = hist.get(prompt_id) or {}
            outputs = entry.get("outputs") or {}
            if expected_node and expected_node in outputs:
                imgs = outputs[expected_node].get("images") or []
                if imgs:
                    return imgs[0]
            elif not expected_node:
                # 优先 SaveImage 类节点（id 数值最大的通常是最终保存节点）
                for nid in sorted(outputs, key=lambda x: (not str(x).isdigit(), int(x) if str(x).isdigit() else 0), reverse=True):
                    imgs = outputs[nid].get("images") or []
                    if imgs:
                        return imgs[0]
            if entry.get("status", {}).get("status_str") == "error":
                die(f"ComfyUI 执行报错：{entry.get('status')}")
        except urllib.error.HTTPError as he:
            out(f"  [WARN] /history HTTP {he.code}：{he.read().decode('utf-8', errors='replace')[:200]}")
        except Exception as e:  # 网络抖动时继续轮询
            out(f"  [WARN] /history 暂不可用：{e}")
        time.sleep(2)
    die(f"等待 ComfyUI 输出超时（{timeout}s）：prompt_id={prompt_id}"
        + (f"（期望节点 {expected_node} 未出图）" if expected_node else ""))


def fetch_image(server: str, meta: dict, dest: Path) -> None:
    params = {
        "filename": meta.get("filename", ""),
        "subfolder": meta.get("subfolder", ""),
        "type": meta.get("type", "output"),
    }
    url = f"http://{server}/view?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def run_live(args, plans: list[dict], template: dict) -> None:
    if not args.input_root.is_dir():
        die(f"实跑需要 ComfyUI input 根目录存在：{args.input_root}（或改 --input-root）")
    # 模板可声明输出节点：template["_output_node"] 全局，或 template[stage]["_output_node"]
    global_node = str(template.get("_output_node", "") or "")
    for plan in plans:
        sid = plan["shot_id"]
        final_dest = args.input_root / plan["frame_key"]
        # 断点续跑：最终帧已存在且 >200KB 就跳过（实跑 done() 口径）
        if not args.force and final_dest.is_file() and final_dest.stat().st_size > 200_000:
            out(f"\n===== 跳过 {sid}：最终帧已存在 {final_dest.stat().st_size//1024}KB"
                "（加 --force 强制重出）=====")
            continue
        out(f"\n===== 提交 {sid} =====")
        try:
            for stage in plan["stages"]:
                key = stage["key"]
                if key not in template:
                    die(f"工作流模板缺少 {key} 段")
                slots = stage["slots"]
                expected = str(template[key].get("_output_node", "") or "") or global_node
                mapping = {
                    "PROMPT": stage["prompt"],
                    "SEED": stage["seed"],
                    "FILENAME": stage["filename_prefix"],
                    "IMAGE_1": slots.get("image_1", ""),
                    "IMAGE_2": slots.get("image_2", ""),
                    "IMAGE_3": slots.get("image_3", ""),
                    "OUTPUT_NODE": expected,
                }
                wf = render_template(template[key], mapping)
                pid = post_prompt(args.server, wf)
                meta = wait_output(args.server, pid, args.timeout, expected)
                dest = args.input_root / stage["output_rel"]
                fetch_image(args.server, meta, dest)
                out(f"  [OK] {key} -> {dest}")
        except SystemExit:
            # 单镜失败不中断批量（实跑 n7_submit 口径）：die() 是 SystemExit(2)
            out(f"  [FAIL] {sid} 出帧失败，继续下一镜")
            continue
        if not args.no_fill:
            fill_frame_key(args.csv, sid, plan["frame_key"])
        append_manifest(args.manifest, {
            "shot_id": sid,
            "engine": "local-comfyui",
            "frame_key": plan["frame_key"],
            "prompts": {s["key"]: s["prompt"] for s in plan["stages"]},
            "slots": {s["key"]: s["slots"] for s in plan["stages"]},
            "seeds": {s["key"]: s["seed"] for s in plan["stages"]},
            "outputs": {s["key"]: s["output_rel"] for s in plan["stages"]},
            "qc_status": "待审",
        }, dedup_key="shot_id")
        out(f"  [OK] 回填 frame_key={plan['frame_key']}；归档 -> {args.manifest}")


def main() -> None:
    args = parse_args()
    rows = load_shotlist_rows(args.csv)

    if args.emit_inputs_template:
        emit_inputs_template(rows, args.emit_inputs_template)
        return

    selected = selected_rows(rows, args.group, args.only)
    out(f"分镜表：{args.csv}  ({len(selected)}/{len(rows)} 镜)   引擎：本地 ComfyUI")

    contract_errors = validate_rows(selected)
    if contract_errors:
        for e in contract_errors:
            out(f"  [ERROR] {e}")
        die("路径契约或三张板不齐，先修 shotlist.csv（路径须为 <项目>/{frames,chars,scenes,props,voices}/<文件名>）")

    inputs = load_n5_inputs(args.inputs)
    errors: list[str] = []
    plans = [build_plan(r, inputs, args.seed, errors) for r in selected]

    if errors:
        out("\n===== 四段重组材料校验 =====")
        for e in errors:
            out(f"  [ERROR] {e}")

    if args.dry_run:
        out("\n===== DRY RUN：不连 ComfyUI、不写图、不回填 =====")
        for p in plans:
            print_plan(p)
        out(f"\n材料状态：{'齐备' if not errors else '待填（见上）'}")
        out("提示：--emit-workflows 可导出每镜三阶段驱动计划；实跑需 --workflow-template。")
        sys.exit(1 if errors else 0)

    if args.emit_workflows:
        target = args.emit_workflows
        target.mkdir(parents=True, exist_ok=True)
        for p in plans:
            (target / f"{p['shot_id']}.plan.json").write_text(
                json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        out(f"\n[OK] 已导出 {len(plans)} 份三阶段驱动计划 -> {target}")
        out("     这是驱动计划（prompt / 槽位 / seed / 输出名），不是可直接 POST 的 ComfyUI 工作流；")
        out("     按它把三阶段模板的节点 ID 补齐后，用 --workflow-template 实跑。")
        if errors:
            out("     [NOTE] 材料仍有占位符，导出的 prompt 需先填好 --inputs。")
        return

    if errors:
        die("四段重组材料未齐备，禁止实跑（先用 --emit-inputs-template 生成并填好，再用 --inputs 指回）")
    if not args.workflow_template or not args.workflow_template.is_file():
        die("实跑需要 --workflow-template（三阶段 ComfyUI /prompt 模板 JSON）；"
            "未搭好模板前请用 --dry-run / --emit-workflows")
    template = json.loads(args.workflow_template.read_text(encoding="utf-8"))
    tpl_errs = validate_template(template)
    if tpl_errs:
        for e in tpl_errs:
            out(f"  [ERROR] 模板：{e}")
        die("工作流模板结构校验失败，先修模板再用 --workflow-template 实跑")
    if template.get("_single_stage"):
        # 本机降级路线（Z-Image Turbo 单阶段）：只跑 stage0，输出直接落最终帧
        out("[NOTE] 模板声明 _single_stage：本机 Z-Image 单阶段出帧，不跑 2511 pass1/pass2")
        for plan in plans:
            s0 = dict(plan["stages"][0])
            s0["output_rel"] = plan["frame_key"]
            s0["filename_prefix"] = Path(plan["frame_key"]).stem
            plan["stages"] = [s0]
    else:
        missing = [k for k in STAGE_KEYS if k not in template]
        if missing:
            die(f"工作流模板缺段：{', '.join(missing)}（应含 stage0 / pass1 / pass2）")
    run_live(args, plans, template)


if __name__ == "__main__":
    main()
