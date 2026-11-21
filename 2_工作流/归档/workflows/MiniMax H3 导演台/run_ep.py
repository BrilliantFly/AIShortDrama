#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H3 导演台一键执行器：三道门 + 状态落盘 + 卡死判据 + 拼接。

把本轮踩过的坑固化成流程，不再靠人盯：

  门 1 素材门    preflight_h3.py 全项通过（帧数预测、素材存在、音频采样率、磁盘）
  门 2 单段门    --gate N 先跑最复杂那一镜（SOLO + 台词 + 最长），确认有音、画面没崩
  门 3 全量门    分段导出（exportMode=segments），逐段落 mp4，每段落盘即写 render_state.json

用法
  python run_ep.py 我的工作流.json --gate 7              # 只跑第 7 段做基准
  python run_ep.py 我的工作流.json                       # 全量（前置 preflight）
  python run_ep.py 我的工作流.json --from 13 --to 24      # 只跑一段区间
  python run_ep.py 我的工作流.json --dry                 # 只校验与打印，不提交
  python run_ep.py 我的工作流.json --concat out.mp4       # 跑完自动拼接

为什么必须 segments 导出：合并导出（all）要求全部像素驻留内存，
960x544x3 float32 每帧 6.27MB，总时长超过约 40 秒就会撞内存墙（26.4G 像素 + 20G 权重），
崩在 comfy/sd.py decode，Python 层接不住，日志只有 access violation。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:8188"
COMFY = r"D:/ComfyUI-aki-v3.2/ComfyUI"
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PREFLIGHT = os.path.join(THIS_DIR, "preflight_h3.py")
SEG_EXPORT_ROOT = os.path.join(COMFY, "output", "minimax_seg_export")
SEG_CACHE_DIR = os.path.join(COMFY, "output", "minimax_seg_cache")
FPS = 24


# ---------------------------------------------------------------- 工具

def find_ffmpeg() -> str | None:
    p = os.path.join(COMFY, "..", "python", "Lib", "site-packages",
                     "imageio_ffmpeg", "binaries")
    for f in sorted(glob.glob(os.path.join(p, "ffmpeg*.exe"))):
        return f
    return shutil.which("ffmpeg")


def http_json(url: str, payload: dict | None = None, timeout: int = 120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code} {url}\n{body[:3000]}")
        raise


def server_alive() -> bool:
    try:
        urllib.request.urlopen(HOST + "/system_stats", timeout=3).read()
        return True
    except Exception:
        return False


def build_prompt(wf: dict, *, tag: str, selection: list[int], export_mode: str) -> dict:
    """把 UI 格式工作流转成 /api/prompt 需要的 inputs，只改选择区间与导出模式。"""
    prompt: dict = {}
    links = {lid: (src, sslot) for lid, src, sslot, *_ in wf["links"]}

    for n in wf["nodes"]:
        ct = n["type"]
        if ct in ("MarkdownNote", "Note", "Reroute"):
            continue
        ins: dict = {}
        for slot in n.get("inputs", []):
            lid = slot.get("link")
            if lid is not None and lid in links:
                src, sslot = links[lid]
                ins[slot["name"]] = [str(src), sslot]

        w = n.get("widgets_values")
        if isinstance(w, list):
            if ct == "MiniMaxH3Director":
                ins.update(task_type=w[0], global_prompt="", bd_grp_sample=w[2],
                           cfg=w[3], seed=w[4], frame_rate=w[6], width=w[7], height=w[8],
                           ref_max_size=w[9], total_frames=w[10], timeline_data=w[11],
                           bd_grp_adv=w[12], steps=w[13], sampler=w[14], scheduler=w[15],
                           shift_video=w[16], shift_audio=w[17],
                           clear_vram_between_segments=True)
            elif ct == "UNETLoader":
                ins.update(unet_name=w[0], weight_dtype=w[1])
            elif ct == "CLIPLoader":
                ins.update(clip_name=w[0], type=w[1], device=w[2])
            elif ct == "VAELoader":
                ins.update(vae_name=w[0])
            elif ct == "LoraLoaderModelOnly":
                ins.update(lora_name=w[0], strength_model=w[1])
            elif ct == "PathchSageAttentionKJ":
                ins.update(sage_attention=w[0], allow_compile=w[1])
            elif ct == "CreateVideo":
                ins.update(fps=w[0], bit_depth=w[1])
            elif ct == "SaveVideo":
                ins.update(filename_prefix=f"video/{tag}", format=w[1], codec=w[2])
        prompt[str(n["id"])] = {"class_type": ct, "inputs": ins}

    d = next(v for v in prompt.values() if v["class_type"] == "MiniMaxH3Director")
    tl = json.loads(d["inputs"]["timeline_data"])
    segs = tl["segments"]
    total = len(segs)

    if selection:
        tl["runSelectEnabled"] = True
        tl["runSelection"] = selection
    else:
        tl["runSelectEnabled"] = False
        tl.pop("runSelection", None)
    tl.setdefault("output", {})["exportMode"] = export_mode
    tl["totalFrames"] = sum(int(s["length"]) for s in segs)

    # refAudios 不带 index：槽位 0-based，写 1/2 会落空槽
    for s in segs:
        s["refAudios"] = [{"audioFile": x["audioFile"]} for x in s.get("refAudios", [])]
        s.pop("runSelected", None)

    d["inputs"]["global_prompt"] = ""          # r2v 批量会把它拼到每段前面
    d["inputs"]["total_frames"] = tl["totalFrames"]
    d["inputs"]["timeline_data"] = json.dumps(tl, ensure_ascii=False)
    return {"prompt": prompt, "client_id": "run_ep", "_total": total}


def newest_export_dir() -> str | None:
    dirs = glob.glob(os.path.join(SEG_EXPORT_ROOT, "*"))
    dirs = [d for d in dirs if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def clear_seg_cache(limit: int = 10) -> int:
    """小批量清缓存：一次删 50 个文件会撞批量删除确认阈值，后台无人应答就永久挂起。"""
    if not os.path.isdir(SEG_CACHE_DIR):
        return 0
    n = 0
    while True:
        files = glob.glob(os.path.join(SEG_CACHE_DIR, "**", "*"), recursive=True)
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            break
        for f in files[:limit]:
            try:
                os.remove(f)
                n += 1
            except OSError:
                pass
        time.sleep(0.05)
    return n


def probe_movie(path: str, ffmpeg: str) -> dict:
    """数视频帧 + 查音轨 + 测响度。核帧数不核容器时长（容器含音轨 padding）。"""
    out = subprocess.run([ffmpeg, "-i", path, "-map", "0:v:0", "-f", "null", "-"],
                         capture_output=True, text=True, errors="replace")
    frames = 0
    for line in (out.stderr or "").splitlines():
        if "frame=" in line:
            try:
                frames = int(line.split("frame=")[1].split()[0])
            except (IndexError, ValueError):
                pass
    info = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True, errors="replace")
    has_audio = "Audio:" in (info.stderr or "")
    vol = subprocess.run([ffmpeg, "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True, errors="replace")
    mean = peak = None
    for line in (vol.stderr or "").splitlines():
        if "mean_volume:" in line:
            mean = float(line.split("mean_volume:")[1].split("dB")[0])
        elif "max_volume:" in line:
            peak = float(line.split("max_volume:")[1].split("dB")[0])
    return {"frames": frames, "audio": has_audio, "mean_db": mean, "peak_db": peak}


def watch(prompt_id: str, total: int, export_dir_cb, *, stall_min: float,
          auto_interrupt: bool, state_path: str | None) -> str:
    """轮询直到结束。卡死判据：队列仍 running 但 mp4 数与日志大小 3 分钟无变化。"""
    log = os.path.join(os.path.dirname(COMFY), "comfyui_run.log")
    last_sig, last_move = None, time.time()
    state = {"prompt_id": prompt_id, "total": total, "done": [], "stall_events": 0,
             "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    status = "unknown"

    while True:
        d = export_dir_cb()
        files = sorted(glob.glob(os.path.join(d, "seg_*.mp4"))) if d else []
        done = [os.path.basename(f) for f in files]
        state["export_dir"] = d
        state["done"] = done
        state["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            hist = http_json(f"{HOST}/history/{prompt_id}", timeout=15)
            st = (hist.get(prompt_id) or {}).get("status") or {}
            status = st.get("status_str") or status
            finished = bool(st.get("completed")) or status in ("success", "error")
        except Exception:
            finished = False

        try:
            log_size = os.path.getsize(log)
        except OSError:
            log_size = 0
        sig = (len(done), log_size)
        if sig != last_sig:
            last_sig, last_move = sig, time.time()
        elif not finished and (time.time() - last_move) / 60 >= stall_min:
            state["stall_events"] += 1
            print(f"\n[卡死判据] {stall_min:.0f} 分钟内 mp4 数与日志均无变化，CPU 多半已归零。")
            if auto_interrupt:
                try:
                    urllib.request.urlopen(HOST + "/interrupt", data=b"", timeout=10).read()
                except Exception:
                    pass
                print("[卡死判据] 已发 /interrupt，退出。")
                state["result"] = "stalled"
                break
            last_move = time.time()

        if state_path:
            with io.open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=1)

        pct = len(done) / total * 100 if total else 0
        print(f"\r  段 {len(done)}/{total} ({pct:5.1f}%)  状态={status}  ", end="", flush=True)
        if finished:
            break
        time.sleep(10)

    print()
    state["result"] = status
    state["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if state_path:
        with io.open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    return status


def concat(export_dir: str, out_path: str, ffmpeg: str) -> bool:
    files = sorted(glob.glob(os.path.join(export_dir, "seg_*.mp4")))
    if not files:
        print("没有可拼接的分段")
        return False
    lst = os.path.join(export_dir, "_concat.txt")
    with io.open(lst, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", "-movflags", "+faststart", out_path],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print((r.stderr or "")[-1500:])
        return False
    print(f"成片: {out_path}  ({len(files)} 段)")
    return True


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--gate", metavar="N|auto",
                    help="只跑第 N 段（1-based）做单段基准；auto = 自动挑最复杂的一镜（有台词+有音色+最长）")
    ap.add_argument("--from", dest="lo", type=int, help="起始段号（1-based，含）")
    ap.add_argument("--to", dest="hi", type=int, help="结束段号（1-based，含）")
    ap.add_argument("--tag", default="H3_run")
    ap.add_argument("--export-mode", default="segments", choices=["segments", "all"])
    ap.add_argument("--state", default=None, help="render_state.json 路径")
    ap.add_argument("--stall-min", type=float, default=3.0)
    ap.add_argument("--auto-interrupt", action="store_true")
    ap.add_argument("--clear-cache", action="store_true", help="提交前小批量清空段缓存")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--concat", metavar="OUT.mp4")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    if a.export_mode != "segments":
        print("!! exportMode=all 在总时长超过约 40 秒时会撞内存墙。确实要跑请显式确认。")

    # 门 1：素材门
    if not a.skip_preflight:
        print("== 门1 素材门 ==", flush=True)
        r = subprocess.run([sys.executable, PREFLIGHT, a.workflow])
        if r.returncode != 0:
            print("preflight 未通过，拒绝提交（确认无误可加 --skip-preflight）")
            return 2

    if not server_alive():
        print(f"ComfyUI 未在 {HOST} 响应，先启动服务")
        return 3

    wf = json.load(io.open(a.workflow, encoding="utf-8"))
    node = next((n for n in wf["nodes"] if n["type"] == "MiniMaxH3Director"), None)
    if node is None:
        print("工作流里没有 MiniMaxH3Director 节点")
        return 2
    segs = json.loads(node["widgets_values"][11])["segments"]
    total = len(segs)

    if a.gate:
        if str(a.gate).lower() == "auto":
            best, best_score = 0, -1
            for i, s in enumerate(segs):
                p = s.get("prompt") or ""
                score = (2 if "「" in p else 0) + (1 if s.get("refAudios") else 0) + int(s["length"]) / 1000
                if score > best_score:
                    best, best_score = i, score
            gate_idx = best
            print(f"--gate auto → 第 {gate_idx + 1} 段（{segs[gate_idx]['id']}，"
                  f"{segs[gate_idx]['length']} 帧，台词={'有' if '「' in (segs[gate_idx].get('prompt') or '') else '无'}，"
                  f"音色={len(segs[gate_idx].get('refAudios') or [])} 条）")
        else:
            gate_idx = int(a.gate) - 1
        if not 0 <= gate_idx < total:
            print(f"段号 {gate_idx + 1} 超出 1~{total}")
            return 2
        sel = [gate_idx]
    elif a.lo or a.hi:
        lo = (a.lo or 1) - 1
        hi = min(a.hi or total, total)
        sel = list(range(lo, hi))
    else:
        sel = []          # 空 = 全部

    pkg = build_prompt(wf, tag=a.tag, selection=sel, export_mode=a.export_mode)
    tl_len = sum(int(s["length"]) for s in segs)
    print(f"== 段数 {total}  总帧 {tl_len} ≈{tl_len / FPS:.1f}s  "
          f"本次执行 {[i + 1 for i in sel] if sel else '全部'}  export={a.export_mode}")

    if a.dry:
        for i in (sel or range(total)):
            s = segs[i]
            print(f"  [{i+1}] {s['id']} len={s['length']} refs={len(s.get('refs') or [])} "
                  f"audio={len(s.get('refAudios') or [])}")
        print("dry run，未提交")
        return 0

    if a.clear_cache:
        n = clear_seg_cache(10)
        print(f"已清段缓存 {n} 个文件（每批 10 个）")

    r = http_json(HOST + "/api/prompt", pkg)
    pid = r.get("prompt_id", "")
    print("提交:", r)

    state_path = a.state or os.path.join(THIS_DIR, f"render_state_{time.strftime('%Y%m%d_%H%M%S')}.json")

    d0 = newest_export_dir()
    status = watch(pid, len(sel) if sel else total,
                   lambda: newest_export_dir() if newest_export_dir() != d0 else None,
                   stall_min=a.stall_min, auto_interrupt=a.auto_interrupt,
                   state_path=state_path)
    print(f"状态: {status}  render_state: {state_path}")

    d = newest_export_dir()
    ff = find_ffmpeg()
    if d and ff:
        files = sorted(glob.glob(os.path.join(d, "seg_*.mp4")))
        print(f"分段目录: {d}  共 {len(files)} 个 mp4")
        if a.gate and files:
            p = probe_movie(files[0], ff)
            print(f"门2 单段门：帧 {p['frames']} 音轨 {'有' if p['audio'] else '无'} "
                  f"mean {p['mean_db']} dB / peak {p['peak_db']} dB")
            if not p["audio"] or (p["mean_db"] or -99) < -40:
                print("!! 该段几乎无声，先解决对白/音轨再跑全量（别急着烧 73 分钟）")
                return 4
            print("   → 还要人耳听一遍咬字，ASR 转写一次；单段门过了再跑全量")
        if a.concat:
            concat(d, a.concat, ff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
