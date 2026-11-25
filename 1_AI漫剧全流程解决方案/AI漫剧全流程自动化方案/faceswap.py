#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换脸层（实跑 n4_faceswap.py + n5_faceswap.py 参数化）：ReActor + inswapper 锁身份。

经验库第五章：板帧同源（Z-Image），身份靠 inswapper 把参考脸换到所有板与起始帧，
再交给 H3 的 SHEET 板统一。规范：
  * 板换脸：源脸 FACE-SRC-*.png → 角色板，input_faces_index 覆盖三视图+表情格全部
  * 逐帧换脸：双人镜男先女后链换；纯男/纯女单换；无脸镜（道具特写）跳过
  * detect_gender_input 只换目标图对应性别的脸，检测不到则原样输出（不报错）

用法（用 ComfyUI python 跑；需 ComfyUI 装 ReActor + inswapper_128 + codeformer）：
  # 板换脸：--mode board
  python faceswap.py --mode board --server 127.0.0.1:8188 \\
      --jobs-config board_jobs.json --input-root <ComfyUI/input>

  # 逐帧换脸：--mode frames
  python faceswap.py --mode frames --server 127.0.0.1:8188 \\
      --frames-dir <input>/<项目>/frames --plan 011:male,female;006:skip \\
      --src-female <input>/<项目>/chars/FACE-SRC-SU.png \\
      --src-male   <input>/<项目>/chars/FACE-SRC-CHEN.png \\
      --out-prefix <项目>/swapframes --only 011,027

board_jobs.json 格式（相对 input 根）：
  [{"src":"项目/chars/FACE-SRC-SU.png","tgt":"项目/chars/IMG-SU-SHEET.png",
    "prefix":"项目/swap/IMG-SU-SHEET-swapped","faces":"0,1,2,3,4,5,6,7,8"}, ...]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from paths import default_input_root  # 跨电脑可移植


def post(host: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        host + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def get(host: str, path: str):
    with urllib.request.urlopen(host + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_done(host: str, pid: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = get(host, "/history/" + pid)
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") in ("success", "error") or st.get("completed"):
                return h[pid]
        time.sleep(3)
    return None


def build_swap(src: str, tgt: str, prefix: str, gender: str = "no",
               face_index: str = "0,1,2,3,4,5,6,7,8") -> dict:
    """ReActor 换脸 API dict（实跑节点结构 1源 2目标 3ReActor 4Save）。"""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": src, "upload": "image"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": tgt, "upload": "image"}},
        "3": {"class_type": "ReActorFaceSwap", "inputs": {
            "enabled": True,
            "input_image": ["2", 0], "source_image": ["1", 0],
            "swap_model": "inswapper_128.onnx",
            "facedetection": "retinaface_resnet50",
            "face_restore_model": "codeformer-v0.1.0.pth",
            "face_restore_visibility": 0.8, "codeformer_weight": 0.5,
            "detect_gender_input": gender, "detect_gender_source": "no",
            "input_faces_index": face_index, "source_faces_index": "0",
            "console_log_level": 1,
        }},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["3", 0]}},
    }


def fetch(host: str, meta: dict, dest: Path) -> None:
    q = urllib.parse.urlencode({"filename": meta.get("filename", ""),
                                "subfolder": meta.get("subfolder", ""),
                                "type": meta.get("type", "output")})
    with urllib.request.urlopen(host + "/view?" + q, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def first_output(h: dict):
    for o in (h.get("outputs") or {}).values():
        for im in o.get("images", []):
            return im
    return None


def run_board(args) -> None:
    jobs = json.loads(Path(args.jobs_config).read_text(encoding="utf-8"))
    for job in jobs:
        src = (Path(args.input_root) / job["src"]).as_posix().replace("\\", "/")
        tgt = job["tgt"]
        api = build_swap(src, tgt, job["prefix"], "no", job.get("faces", "0,1,2,3,4,5,6,7,8"))
        print(f"\n=== 板换脸 {tgt} (源 {job['src']}) ===")
        res = post(args.host, "/prompt", {"prompt": api, "client_id": "fs_board"})
        pid = res.get("prompt_id")
        if res.get("node_errors"):
            print("  node_errors:", json.dumps(res["node_errors"], ensure_ascii=False)[:600])
        if not pid:
            print("  无 prompt_id"); continue
        h = wait_done(args.host, pid, args.timeout)
        if not h or h.get("status", {}).get("status_str") == "error":
            print("  FAIL", (h or {}).get("status", {}))
            continue
        print("  DONE 输出:", [im.get("filename") for o in (h.get("outputs") or {}).values()
                              for im in o.get("images", [])])


def parse_plan(plan_str: str) -> dict[str, list[str]]:
    plan: dict[str, list[str]] = {}
    for part in plan_str.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        n, spec = part.split(":", 1)
        n = "".join(c for c in n if c.isdigit())[-3:].zfill(3)
        spec = spec.strip().lower()
        if spec in ("skip", "none", ""):
            plan[n] = []
        else:
            order = [g.strip() for g in spec.split(",") if g.strip() in ("male", "female")]
            # 实跑规范：男先女后（链换时女性结果喂给男性会丢脸，故先男后女）
            plan[n] = sorted(order, key=lambda g: 0 if g == "male" else 1)
    return plan


def run_frames(args) -> None:
    frames_dir = Path(args.frames_dir)
    srcs = {"female": args.src_female, "male": args.src_male}
    for g, p in srcs.items():
        if not p:
            print(f"[ERROR] 缺源脸 --src-{g}")
            raise SystemExit(2)
    plan = parse_plan(args.plan)
    files = sorted(f for f in os.listdir(frames_dir)
                   if f.endswith(".png") and not f.startswith("_tmp_"))
    if args.only:
        want = {"SHOT-" + s.strip().zfill(3) + ".png" for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f in want]
    print(f"N5 换脸：{len(files)} 帧 | suffix={args.suffix or '(覆盖式)'}")

    for f in files:
        digits = "".join(c for c in f if c.isdigit())[-3:]
        n = digits.zfill(3)
        genders = plan.get(n, ["male", "female"])
        if not genders:
            print(f"  #{n}: skip（无脸镜）")
            continue
        final = frames_dir / f"SHOT-{n}{args.suffix}.png"
        cur_rel = (Path(args.frames_rel) / f).as_posix().replace("\\", "/")
        changed = []
        for g in genders:
            src = (Path(args.input_root) / srcs[g]).as_posix().replace("\\", "/") \
                if not Path(srcs[g]).is_absolute() else Path(srcs[g]).as_posix().replace("\\", "/")
            api = build_swap(src, cur_rel, args.out_prefix + f"/SHOT-{n}-{g}{args.suffix}", g)
            try:
                res = post(args.host, "/prompt", {"prompt": api, "client_id": f"fs_{n}_{g}"})
                pid = res.get("prompt_id")
                if not pid:
                    print(f"  #{n} {g}: WARN 无 prompt_id"); continue
                h = wait_done(args.host, pid, args.timeout)
                meta = first_output(h or {})
                if not meta:
                    print(f"  #{n} {g}: WARN 无输出"); continue
                tmp = frames_dir / f"_tmp_{n}_{g}.png"
                fetch(args.host, meta, tmp)
                cur_rel = (Path(args.frames_rel) / tmp.name).as_posix().replace("\\", "/")
                changed.append(g)
            except Exception as e:
                print(f"  #{n} {g}: WARN {type(e).__name__}: {str(e)[:120]}")
        # 链末结果落到最终文件
        if changed:
            last = frames_dir / f"_tmp_{n}_{changed[-1]}.png"
            if last.exists():
                shutil.copy2(last, final)
        for g in ("male", "female"):
            tmp = frames_dir / f"_tmp_{n}_{g}.png"
            if tmp.exists():
                os.remove(tmp)
        print(f"  #{n}: {'+'.join(changed) or '无变化'} -> {final.name}")
        if args.manifest:
            with open(args.manifest, "a", encoding="utf-8") as mf:
                mf.write(json.dumps({"n": n, "genders": changed, "suffix": args.suffix},
                                    ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="ReActor+inswapper 换脸（板/逐帧）")
    ap.add_argument("--mode", choices=["board", "frames"], required=True)
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--input-root", type=Path, default=default_input_root())
    ap.add_argument("--jobs-config", help="board 模式：换脸任务 JSON")
    ap.add_argument("--frames-dir", type=Path, help="frames 模式：帧目录")
    ap.add_argument("--frames-rel", default="", help="frames 模式：帧相对 input 根路径（默认用项目名推导）")
    ap.add_argument("--plan", default="", help="frames 模式：如 '011:male,female;006:skip'")
    ap.add_argument("--src-female", default="", help="frames 模式：女源脸相对 input 根或绝对路径")
    ap.add_argument("--src-male", default="", help="frames 模式：男源脸")
    ap.add_argument("--out-prefix", default="", help="frames 模式：SaveImage 前缀")
    ap.add_argument("--only", default="", help="frames 模式：只处理镜号，逗号分隔")
    ap.add_argument("--suffix", default="", help="输出后缀，如 _t1")
    ap.add_argument("--manifest", default="", help="manifest JSONL 路径")
    args = ap.parse_args()
    if args.mode == "board":
        if not args.jobs_config:
            ap.error("board 模式需 --jobs-config")
        run_board(args)
    else:
        if not args.frames_rel:
            args.frames_rel = Path(args.frames_dir).name  # 兜底：取目录名作 subfolder
        run_frames(args)


if __name__ == "__main__":
    main()
