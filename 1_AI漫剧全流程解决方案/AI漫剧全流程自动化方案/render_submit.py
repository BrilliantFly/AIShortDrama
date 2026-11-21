#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_submit.py — N7 出片提交与断点续跑层（实跑 n7_submit.py 参数化版）

把「每镜一份 H3 workflow JSON」提交给本地 ComfyUI 导演台，逐镜轮询、产物成对识别、
断点续跑、单镜失败隔离、CSV 状态回写。对应经验库 1.2/1.3/2.5(A)/4.4。

两种供料模式
------------
* --shots-dir DIR（推荐，配合 csv_to_timeline.py --per-shot）：
  目录里每份 JSON 是一镜的完整 /prompt（已含 refs 0 基/场景锁/双声线/refAudioStamp）。
  文件名 SHOT-004.json → 镜号 004。脚本直接 POST 这份 JSON，不再现场构造。
* --workflow TPL --segments JSON（兼容实跑 n7_submit 路线）：
  工作流底座 + N7-segments.json，用 build_api 现场构造单段 timeline。

关键实跑回灌（均来自 D:\\剧本及分镜\\工作流优化经验库.md，已验证）
------------------------------------------------------------------
* 断点续跑：DELIV 下 {shot}-{mode}*.mp4 >200KB 判完成，自动跳过（1.3）。
* 产物成对：SaveVideo 写 output/，导演台另写 output/minimax_seg_export/<ts>/seg_*.mp4；
  快照 diff 两个都算新产物，命名 -1（分段版，优先）/ -2（归档版）（1.2）。
* 失败隔离：单镜异常不中断批量，逐镜回写 CSV status（1.3）。
* 场景锁/破缓存/双声线/0 基：均已在 per-shot workflow 内固化，本脚本不重复注入。

用法
----
  # 主线：消费 --per-shot 产物，逐镜出片
  python render_submit.py --shots-dir out/shots --shots 004,008 \\
      --csv shotlist.csv --out-root D:/剧本及分镜/街对面/导出

  # 全量 + 断点续跑（已完成的自动跳过）
  python render_submit.py --shots-dir out/shots --all --csv shotlist.csv \\
      --out-root D:/剧本及分镜/街对面/导出

  # dry-run：只打印第一镜将 POST 的 JSON，不提交
  python render_submit.py --shots-dir out/shots --shots 004 --dry

  # 兼容实跑路线
  python render_submit.py --workflow H3-通用02....json --segments N7-segments.json \\
      --shots 004 --mode hd --out-root D:/剧本及分镜/街对面/导出
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

HOST = "http://127.0.0.1:8188"
WF_MODES = {
    "preview": ("H3-通用01-快出预览-r2v-4step-960x544.json", 4, 960, 544),
    "hd": ("H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json", 25, 1344, 768),
}
DONE_MIN_BYTES = 200_000


def out(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(2)


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        HOST + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path: str):
    with urllib.request.urlopen(HOST + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def gui_to_api(gui: dict) -> dict:
    """GUI 画布工作流（nodes/links）→ ComfyUI /prompt API 格式（节点id→class_type/inputs）。

    csv_to_timeline.py --per-shot 产出的是 GUI 格式，直接 POST 会被 /prompt 拒绝。
    本函数通用转换：widget 值按 node.inputs 里带 widget 标记的 name 顺序映射 widgets_values；
    连线输入从 links 数组还原成 [源节点id, 源插槽]；跳过 MarkdownNote 等注释节点。
    """
    link_src: dict[int, tuple[str, int]] = {}
    for l in gui.get("links", []):
        link_src[l[0]] = (str(l[1]), l[2])
    api: dict[str, dict] = {}
    for n in gui.get("nodes", []):
        ct = n.get("type")
        if not ct or ct in ("MarkdownNote", "Note"):
            continue
        inputs: dict = {}
        if ct == "MiniMaxH3Director":
            # 特判：H3Director 的 widgets_values 含隐藏 mode/分组项，序位与 widget 名不一一对应。
            # 用实跑 n7_submit.build_api 验证过的字段表；值从 widgets_values 按语义位置取。
            wv = list(n.get("widgets_values", []))
            inputs = {
                "task_type": wv[0] if len(wv) > 0 else "",
                "global_prompt": wv[1] if len(wv) > 1 else "",
                "bd_grp_sample": wv[2] if len(wv) > 2 else "采样设置",
                "cfg": wv[3] if len(wv) > 3 else 1.0,
                "seed": wv[4] if len(wv) > 4 else 0,
                "frame_rate": wv[6] if len(wv) > 6 else 24.0,
                "width": wv[7] if len(wv) > 7 else 1344,
                "height": wv[8] if len(wv) > 8 else 768,
                "ref_max_size": wv[9] if len(wv) > 9 else 1344,
                "total_frames": wv[10] if len(wv) > 10 else 0,
                "timeline_data": wv[11] if len(wv) > 11 else "{}",
                "bd_grp_advanced": wv[12] if len(wv) > 12 else "高级采样",
                "steps": wv[13] if len(wv) > 13 else 25,
                "sampler": wv[14] if len(wv) > 14 else "res_multistep",
                "scheduler": wv[15] if len(wv) > 15 else "simple",
                "shift_video": wv[16] if len(wv) > 16 else 12.0,
                "shift_audio": wv[17] if len(wv) > 17 else 3.0,
                "bd_grp_perf": wv[18] if len(wv) > 18 else "性能",
                "clear_vram_between_segments": True,
                "export_source_images": False,
            }
        else:
            widget_names = [i["name"] for i in n.get("inputs", []) if i.get("widget")]
            wv = list(n.get("widgets_values", []))
            # widget 值按顺序绑定；多出的值丢弃，少的值留空由 ComfyUI 默认值补
            for k, name in enumerate(widget_names):
                if k < len(wv):
                    inputs[name] = wv[k]
        for i in n.get("inputs", []):
            lk = i.get("link")
            if lk is not None and lk in link_src and i.get("name") not in inputs:
                inputs[i["name"]] = list(link_src[lk])
        api[str(n["id"])] = {"class_type": ct, "inputs": inputs}
    return api


def normalize_api(doc: dict) -> dict:
    """输入可能是 GUI 画布格式（含 nodes）或已是 API 格式，统一返回 API 格式。"""
    if "nodes" in doc and isinstance(doc["nodes"], list):
        return gui_to_api(doc)
    return doc


def submit_workflow(api: dict, client_id: str) -> str:
    resp = post("/prompt", {"prompt": api, "client_id": client_id})
    if "prompt_id" not in resp:
        raise RuntimeError(f"提交失败: {json.dumps(resp, ensure_ascii=False)[:800]}")
    return resp["prompt_id"]


def wait(pid: str, limit_min: int = 30) -> dict:
    t0 = time.time()
    while time.time() - t0 < limit_min * 60:
        h = get(f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed") or st.get("status_str") == "success":
                return h[pid]
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st, ensure_ascii=False)[:1200])
        time.sleep(8)
    raise TimeoutError(f"{pid} 超时（{limit_min} 分钟）")


def snapshot(comfy_out: Path, seg_export: Path) -> set[Path]:
    files: set[Path] = set()
    for root in (comfy_out, seg_export):
        if root.exists():
            files |= {p for p in root.rglob("*.mp4")}
    return files


def mark_status(csv_path: Path, shot: str, status: str, note: str = "") -> None:
    """逐镜回写状态，中断后可判断进度（1.3）。"""
    if not csv_path or not Path(csv_path).exists():
        return
    p = Path(csv_path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    key_col = "shot" if "shot" in rows[0] else ("shot_id" if "shot_id" in rows[0] else None)
    if not key_col:
        return
    for r in rows:
        if str(r[key_col]).endswith(shot):
            if "status" in r:
                r["status"] = status
            if note and "note" in r:
                r["note"] = note
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---- 兼容实跑路线：从 segments 现场构造 ----

def timeline_of(tpl: dict) -> dict:
    node = next(n for n in tpl["nodes"] if n.get("type") == "MiniMaxH3Director")
    return json.loads(node["widgets_values"][11])


def build_api_from_segments(seg: dict, mode: str, tpl: dict, input_root: Path) -> dict:
    """现场构造单段 timeline（实跑 n7_submit.build_api 的参数化移植）。

    注意：本路径复用 segments.json 里已 0 基的 refs / 双声线 ref_audios；
    场景锁与 refAudioStamp 由上游 n7_build/经验库流程保证，这里仅同步尺寸与 seed。
    """
    name, steps, w, h = WF_MODES[mode]
    tl = timeline_of(tpl)
    frames = int(seg["frames"])
    tl.update({"totalFrames": frames, "frameRate": 24.0, "durationSec": frames / 24.0,
               "width": w, "height": h, "refMaxSize": w, "timelineMode": "prompt_batch"})
    tl.setdefault("global", {})["sourceWidth"] = w
    tl["global"]["sourceHeight"] = h
    tl["output"].update({"mode": "fixed", "width": w, "height": h, "longEdge": w,
                         "audioMode": "generate", "exportMode": "segments"})
    refs = [{"index": r["index"], "imageFile": r["imageFile"], "fileName": r["imageFile"],
             "type": "input", "subfolder": r["subfolder"]} for r in seg["refs"]]
    ref_audios = [{"index": int(a["index"]), "audioFile": a["audioFile"],
                   "fileName": a["audioFile"], "type": "input", "subfolder": a["subfolder"]}
                  for a in seg.get("ref_audios", [])]
    tl["segments"] = [{
        "id": "seg_001", "start": 0, "length": frames, "frameCount": frames,
        "durationSec": round(frames / 24.0, 3), "prompt": seg["prompt"],
        "negativePrompt": seg.get("negative", ""), "taskType": "", "refs": refs,
        "refAudios": ref_audios, "refVideos": [], "genImage": {"imageFile": ""},
    }]
    tl["shots"] = []
    # 同名换音频破缓存（2.2）
    parts = []
    for a in ref_audios:
        p = input_root / a["subfolder"] / a["audioFile"]
        if p.exists():
            import hashlib
            parts.append(f"{a['index']}:{hashlib.md5(p.read_bytes()).hexdigest()[:10]}-{p.stat().st_size}")
    if parts:
        tl["refAudioStamp"] = "|".join(parts)
    has_lora = any(n["type"] == "LoraLoaderModelOnly" for n in tpl["nodes"])
    model_src = ["17", 0] if has_lora else ["1", 0]
    api = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "14": {"class_type": "PathchSageAttentionKJ", "inputs": {"model": model_src, "sage_attention": "disabled", "allow_compile": False}},
        "15": {"class_type": "MiniMaxH3MemoryEfficientSageAttentionPatch", "inputs": {"model": ["14", 0]}},
        "12": {"class_type": "MiniMaxH3Director", "inputs": {
            "model": ["15", 0], "video_vae": ["3", 0], "audio_vae": ["4", 0], "clip": ["2", 0],
            "task_type": "r2v — 参考主体生视频(Reference to Video)", "global_prompt": "",
            "bd_grp_sample": "采样设置", "cfg": 1.0, "seed": int(seg["seed"]),
            "frame_rate": 24.0, "width": w, "height": h, "ref_max_size": w,
            "total_frames": frames, "timeline_data": json.dumps(tl, ensure_ascii=False),
            "bd_grp_advanced": "高级采样", "steps": steps, "sampler": "res_multistep",
            "scheduler": "simple", "shift_video": 12.0, "shift_audio": 3.0,
            "bd_grp_perf": "性能", "clear_vram_between_segments": True,
            "export_source_images": False,
        }},
        "6": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "audio": ["12", 1], "fps": ["12", 2], "bit_depth": 8}},
        "7": {"class_type": "SaveVideo", "inputs": {"video": ["6", 0], "filename_prefix": seg["out_prefix"], "format": "auto", "codec": "auto"}},
    }
    if has_lora:
        api["17"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0],
            "lora_name": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
            "strength_model": 1.0}}
    return api


def collect_shots(args, shots_dir: Path | None, segments_path: Path | None) -> dict[str, dict]:
    """返回 {shot3: {'api': dict, 'out_prefix': str}}。"""
    result: dict[str, dict] = {}
    if shots_dir:
        if not shots_dir.is_dir():
            die(f"--shots-dir 不存在：{shots_dir}")
        for f in sorted(shots_dir.glob("*.json")):
            m = re.search(r"(\d{3})", f.stem)
            if not m:
                out(f"  [WARN] 跳过无法解析镜号的文件：{f.name}")
                continue
            doc = json.loads(f.read_text(encoding="utf-8"))
            api = normalize_api(doc)  # --per-shot 产出 GUI 格式，转 /prompt API 格式
            prefix = f"video/SHOT-{m.group(1)}"
            result[m.group(1)] = {"api": api, "out_prefix": prefix}
    else:
        if not segments_path or not segments_path.is_file():
            die("需给 --shots-dir 或 --segments")
        data = json.loads(segments_path.read_text(encoding="utf-8"))
        tpl_path = args.workflow
        if not tpl_path or not tpl_path.is_file():
            die("--segments 模式需要 --workflow 底座 JSON")
        tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
        for s in data["shots"]:
            n3 = s["shot"][-3:]
            result[n3] = {"api": build_api_from_segments(s, args.mode, tpl, args.input_root),
                          "out_prefix": s.get("out_prefix", f"video/SHOT-{n3}")}
    return result


def run(args) -> int:
    shots_map = collect_shots(args, args.shots_dir, args.segments)
    all_keys = sorted(shots_map)
    if args.shots:
        keys = [k.strip().zfill(3) for k in args.shots.split(",") if k.strip()]
    elif args.all:
        keys = all_keys
    else:
        die("给 --shots 或 --all")
    missing = [k for k in keys if k not in shots_map]
    if missing:
        die(f"镜号不存在：{missing}；可选：{all_keys}")

    outdir = args.out_root / "videos"
    outdir.mkdir(parents=True, exist_ok=True)
    if args.dry:
        sample = shots_map[keys[0]]["api"]
        out(f"[dry] {keys[0]} 将 POST {len(sample)} 个节点；前 1200 字：")
        out(json.dumps(sample, ensure_ascii=False)[:1200])
        return 0

    comfy_out = args.comfy_output
    seg_export = comfy_out / "minimax_seg_export"
    total, ok, skip, fails = len(keys), 0, 0, []

    for i, key in enumerate(keys, 1):
        # 断点续跑：>200KB 成片跳过
        existing = [p for p in outdir.glob(f"SHOT-*-{key}*.mp4")
                    if p.stat().st_size > DONE_MIN_BYTES]
        if existing and not args.force:
            out(f"[{i}/{total}] SHOT-{key} 已有成片，跳过（--force 强制重出）")
            skip += 1
            continue
        out(f"\n[{i}/{total}] === SHOT-{key} · 提交 · mode={args.mode} ===")
        t0 = time.time()
        before = snapshot(comfy_out, seg_export)
        try:
            api = shots_map[key]["api"]
            # per-shot workflow 的前缀按镜号规整，避免多镜互相覆盖
            for node in api.values():
                if node.get("class_type") == "SaveVideo":
                    node["inputs"]["filename_prefix"] = f"video/SHOT-{key}"
            pid = submit_workflow(api, f"render-{key}")
            out(f"  prompt_id {pid}  等待出片…")
            wait(pid, args.wait_min)
        except Exception as e:
            out(f"  ✗ 失败：{type(e).__name__}: {str(e)[:300]}")
            mark_status(args.csv, key, f"{args.mode} 失败")
            fails.append((key, str(e)[:120]))
            continue
        new = sorted(snapshot(comfy_out, seg_export) - before,
                     key=lambda p: p.stat().st_mtime)
        if not new:
            out("  ! 未发现新 mp4，检查 output 目录")
            mark_status(args.csv, key, f"{args.mode} 无产物")
            fails.append((key, "no mp4"))
            continue
        for j, src in enumerate(new):
            tag = "" if len(new) == 1 else f"-{j+1}"
            dst = outdir / f"SHOT-{key}-{args.mode}{tag}.mp4"
            shutil.copy2(src, dst)
            out(f"  ✓ {dst.name} {dst.stat().st_size/1024/1024:.1f}MB ← {src.relative_to(comfy_out)}")
        ok += 1
        dt = (time.time() - t0) / 60
        mark_status(args.csv, key, f"{args.mode} 已验证", f"{dt:.1f} 分钟")
        out(f"  用时 {dt:.1f} 分钟 · 成功 {ok}")

    out(f"\n===== 批量结束：成功 {ok} · 跳过 {skip} · 失败 {len(fails)} =====")
    for k, e in fails:
        out(f"  ✗ SHOT-{k}  {e}")
    return 1 if fails else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="每镜 H3 workflow → ComfyUI 提交 + 断点续跑")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--shots-dir", type=Path, help="--per-shot 产出的单镜 workflow 目录")
    src.add_argument("--segments", type=Path, help="N7-segments.json（兼容实跑路线）")
    ap.add_argument("--shots", default="", help="逗号分隔镜号后三位，如 004,008")
    ap.add_argument("--all", action="store_true", help="全部镜头")
    ap.add_argument("--mode", choices=list(WF_MODES), default="hd", help="档位（--segments 模式用）")
    ap.add_argument("--workflow", type=Path, help="H3 底座 JSON（--segments 模式必需）")
    ap.add_argument("--input-root", type=Path,
                    default=Path("D:/ComfyUI-aki-v3.2/ComfyUI/input"),
                    help="ComfyUI input 根（--segments 模式破缓存用）")
    ap.add_argument("--out-root", type=Path, required=True, help="成片交付根，成片落 <root>/videos/")
    ap.add_argument("--comfy-output", type=Path,
                    default=Path("D:/ComfyUI-aki-v3.2/ComfyUI/output"),
                    help="ComfyUI output 根（快照 diff 找产物）")
    ap.add_argument("--csv", type=Path, default=None, help="出片清单 CSV（回写 status）")
    ap.add_argument("--wait-min", type=int, default=30, help="单镜等待上限分钟")
    ap.add_argument("--force", action="store_true", help="已有成片也重出")
    ap.add_argument("--dry", action="store_true", help="只打印将提交的 JSON，不提交")
    args = ap.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
