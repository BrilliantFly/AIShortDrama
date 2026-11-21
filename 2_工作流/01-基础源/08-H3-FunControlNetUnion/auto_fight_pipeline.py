# -*- coding: utf-8 -*-
"""
武侠打斗全自动出片驱动器：切片 → 修改工作流 → API 提交 → 监控 → 拼接。

依赖：
  - 同目录 make_action_clips.py（AUTO 切片用）
  - ComfyUI 已运行，且已升级到支持 MiniMaxH3FunControlNetApply / SDPose 子图的版本
  - FunControl Union 补丁已放入 models/model_patches/

用法：
  干跑（只生成计划与补丁后的工作流，不提交）：
    python auto_fight_pipeline.py --jobs shots.csv --mode dry
  校验（向 ComfyUI 提交一次，报告缺什么节点/模型，不入队执行——缺节点时服务端直接拒收）：
    python auto_fight_pipeline.py --jobs shots.csv --mode validate
  正式跑（逐镜出片 + 拼接）：
    python auto_fight_pipeline.py --jobs shots.csv --mode run
  只跑指定镜：
    python auto_fight_pipeline.py --jobs shots.csv --mode run --only 2,3

shots.csv 列：shot,clip,scene,identity,prompt
  clip     切片的三种写法（按顺序检索 通用库 --lib → 项目库）：
             ① 完整文件名   ACT003_后仰蹬腿_侧面_20-22.6s_124f_speed0.5.mp4
             ② 短标签       ACT003          （唯一匹配才通过，有歧义会报错列出候选）
             ③ AUTO:源片|起秒|止秒|fx|朝向|动作名  现场切片，切完自动入通用库沉淀
  scene    场景板（ComfyUI input 相对路径，如 EP001/IMG-015·断竹与竹坡.png）
  identity 身份板（同上）
  prompt   该镜正向提示词（引号包裹）
"""
import argparse, csv, io, json, os, random, re, shutil, subprocess, sys, time, urllib.request

FF = r"D:/ComfyUI-aki-v3.2/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
DEFAULT_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "H3-FunControlNetUnion-动作迁移-r2v-25step-1344x768.json")
UNIVERSAL_LIB = r"D:/剧本及分镜/动作素材库"      # 通用库：全项目共享，AUTO 切片默认入这里
PROJECT_LIB = r"D:/剧本及分镜/一剑问天/分镜/剧集/EP001/动作素材库"   # 项目库：本项目专用
COMFY_INPUT = r"D:/ComfyUI-aki-v3.2/ComfyUI/input"
COMFY_OUTPUT = r"D:/ComfyUI-aki-v3.2/ComfyUI/output"

def http_json(method, url, payload=None, timeout=15):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

# ────────────────────────── GUI → API 转换 ──────────────────────────
SOCKET_TYPES = {"IMAGE","MASK","LATENT","MODEL","CLIP","VAE","CONDITIONING","AUDIO","VIDEO",
                "GUIDER","SAMPLER","SIGMAS","NOISE","MODEL_PATCH","WEBCAM","LOAD_IMAGE"}

def gui_to_api(wf, obj_info):
    linkmap = {l[0]: (l[1], l[2]) for l in wf["links"]}
    api, problems = {}, []
    for n in wf["nodes"]:
        t = n["type"]
        if t == "MarkdownNote":
            continue
        ci = obj_info.get(t)
        if ci is None:
            problems.append(f"节点缺失（需升级/装插件）: {t}")
            continue
        defs = []   # (name, is_socket)
        for sec in ("required", "optional"):
            for k, v in (ci.get("input", {}).get(sec) or {}).items():
                typ = v[0] if isinstance(v, list) else v
                defs.append((k, isinstance(typ, str) and typ.upper() in SOCKET_TYPES))
        linked = {}
        for slot in n.get("inputs", []):
            if slot.get("link") is not None and slot["link"] in linkmap:
                src, sslot = linkmap[slot["link"]]
                linked[slot["name"]] = [str(src), sslot]
        # widget 顺序 = 服务器 schema 的非 socket 顺序（与 GUI 渲染一致）
        widget_order = [k for k, sock in defs if not sock]
        wv = list(n.get("widgets_values") or [])
        inputs = {}
        for k, sock in defs:
            if k in linked:
                inputs[k] = linked[k]
            elif not sock:
                i = widget_order.index(k)
                if i < len(wv):
                    v = wv[i]
                    inputs[k] = v[0] if isinstance(v, list) and v else v
        for name, v in linked.items():        # 动态 socket（如 ref_images.ref_image_N）
            inputs.setdefault(name, v)
        api[str(n["id"])] = {"class_type": t, "inputs": inputs, "_meta": {"title": t}}
    _assert_critical(api, problems)
    return api, problems

def _assert_critical(api, problems):
    """关键链路断言：连线缺失立即报错，避免静默错图。"""
    ref = next((v for v in api.values() if v["class_type"] == "MiniMaxH3ReferenceToVideo"), None)
    if ref:
        for k in ("clip", "vae", "audio_vae", "prompt", "width", "height", "length"):
            if k not in ref["inputs"]:
                problems.append(f"ReferenceToVideo 缺连线 {k}")
    app = next((v for v in api.values() if v["class_type"] == "MiniMaxH3FunControlNetApply"), None)
    if app:
        for k in ("model", "model_patch", "vae", "control_video"):
            if k not in app["inputs"]:
                problems.append(f"FunControlApply 缺连线 {k}")
    sch = next((v for v in api.values() if v["class_type"] == "BasicScheduler"), None)
    if sch:
        if "steps" not in sch["inputs"]:
            problems.append("BasicScheduler 缺 steps 连线")
        elif not isinstance(sch["inputs"].get("denoise"), (int, float)):
            problems.append(f"BasicScheduler denoise 异常: {sch['inputs'].get('denoise')}")

# ────────────────────────── 补丁工作流 ──────────────────────────
def patch_workflow(wf, job):
    lv = next((n for n in wf["nodes"] if n["type"] == "LoadVideo"), None)
    imgs = sorted([n for n in wf["nodes"] if n["type"] == "LoadImage"], key=lambda x: x["id"])
    prompt_n = next((n for n in wf["nodes"] if n["type"] == "PrimitiveStringMultiline"), None)
    dur_n = next((n for n in wf["nodes"] if n["type"] == "PrimitiveFloat"), None)
    noise = next((n for n in wf["nodes"] if n["type"] == "RandomNoise"), None)
    save = next((n for n in wf["nodes"] if n["type"] == "SaveVideo"), None)
    if not all((lv, len(imgs) >= 2, prompt_n, dur_n, noise, save)):
        raise RuntimeError("模板缺少关键节点，检查工作流文件")

    lv["widgets_values"][0] = job["clip_rel"]
    # 按模板默认值识别身份板/场景板，识别不到则按 id 顺序
    idn = next((n for n in imgs if "IMG-004" in (n["widgets_values"][0] or "")), imgs[0])
    scn = next((n for n in imgs if n is not idn and "IMG-015" in (n["widgets_values"][0] or "")),
               imgs[1] if len(imgs) > 1 else imgs[0])
    scn["widgets_values"][0] = job["scene"]
    idn["widgets_values"][0] = job["identity"]
    prompt_n["widgets_values"][0] = job["prompt"]
    dur_n["widgets_values"][0] = round(job["clip_sec"], 2)
    noise["widgets_values"][0] = random.randint(1, 2**48)
    save["widgets_values"][0] = f"FunControl/{job['shot']}"

def probe_duration(path):
    p = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    if not m:
        raise RuntimeError(f"读不到时长: {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

def find_in_libs(name, libs):
    """在多级库里找切片：先精确文件名，再唯一短标签匹配。返回绝对路径或 None。"""
    for lib in libs:
        p = os.path.join(lib, name)
        if os.path.exists(p):
            return p
    hits = {}                                   # 短标签模糊匹配（按文件名去重：两级库常有同份副本）
    for lib in libs:
        for f in os.listdir(lib):
            if f.startswith("ACT") and name in f and f.endswith(".mp4"):
                hits[f] = os.path.join(lib, f)
    if len(hits) == 1:
        return next(iter(hits.values()))
    if len(hits) > 1:
        raise RuntimeError(f"切片标签有歧义「{name}」，请写完整文件名，候选：\n  " +
                           "\n  ".join(hits))
    return None

def ensure_clip(job, libs, auto_lib):
    """解析 clip 字段：完整名/短标签/AUTO 现场切片。返回 (绝对路径, input相对路径, 秒)。"""
    spec = job["clip"].strip()
    if spec.startswith("AUTO:"):
        parts = spec[5:].split("|")
        if len(parts) != 6:
            raise RuntimeError(f"AUTO 格式应为 源片|起秒|止秒|fx|朝向|动作名: {spec}")
        src, s, e, fx, orient, label = [p.strip() for p in parts]
        # 已有同名动作切片则直接复用（跨项目沉淀，不重复切）
        reuse = find_in_libs(label, libs)
        if reuse:
            print(f"   [AUTO] 复用已有切片 {os.path.basename(reuse)}")
            spec = os.path.basename(reuse)
        else:
            cuts = os.path.join(auto_lib, "auto_cuts.csv")   # 通用库永久登记
            new = not os.path.exists(cuts)
            with io.open(cuts, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if new: w.writerow(["label", "orient", "start", "end", "fx"])
                w.writerow([label, orient, s, e, fx])
            subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "make_action_clips.py"), "--src", src, "--cuts", cuts,
                            "--out", auto_lib], check=True)
            os.remove(cuts)                  # 用完即清，登记表由索引.csv 长期维护
            found = find_in_libs(label, libs)
            if not found:
                raise RuntimeError(f"AUTO 切片后未找到产物（label={label}）")
            spec = os.path.basename(found)
            print(f"   [AUTO] 已切片入库 {spec}")
    src_path = find_in_libs(spec, libs)
    if not src_path:
        raise RuntimeError(f"切片在所有库中都不存在: {spec}（检索：{', '.join(libs)}）")
    spec = os.path.basename(src_path)          # 短标签 → 解析出的真实文件名
    dst = os.path.join(COMFY_INPUT, "actions", spec)   # 通用 input/actions，与项目无关
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst):
        shutil.copy2(src_path, dst)
    return src_path, f"actions/{spec}", probe_duration(src_path)

# ────────────────────────── 主流程 ──────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--mode", choices=["dry", "validate", "run"], default="dry")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--lib", default=UNIVERSAL_LIB,
                    help=f"通用动作库（AUTO 切片入库处，默认 {UNIVERSAL_LIB}）")
    ap.add_argument("--prefix", default="EP001", help="成片文件名前缀")
    ap.add_argument("--out", default=r"D:/剧本及分镜/一剑问天/分镜/剧集/EP001/制作成果/FunControl")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.makedirs("tmp", exist_ok=True)
    libs = [a.lib] + ([PROJECT_LIB] if os.path.normpath(a.lib) != os.path.normpath(PROJECT_LIB) else [])

    jobs = [r for r in csv.DictReader(io.open(a.jobs, encoding="utf-8-sig"))]
    if a.only:
        want = {s.strip() for s in a.only.split(",")}
        jobs = [j for j in jobs if j["shot"] in want]
    wf_tpl = json.load(io.open(a.template, encoding="utf-8"))
    print(f"任务 {len(jobs)} 镜 · 模板 {os.path.basename(a.template)} · 模式 {a.mode}\n")

    for job in jobs:
        print(f"── 镜 {job['shot']} ─────────────────────────")
        src, rel, sec = ensure_clip(job, libs, a.lib)
        job["clip_rel"], job["clip_sec"] = rel, sec
        for k in ("scene", "identity"):
            if not os.path.exists(os.path.join(COMFY_INPUT, job[k])):
                raise RuntimeError(f"素材不在 input 目录: {job[k]}")
        print(f"   切片 {rel}  {sec:.2f}s")
        print(f"   场景 {job['scene']} / 身份 {job['identity']}")
        print(f"   prompt {job['prompt'][:40]}...")

        wf = json.loads(json.dumps(wf_tpl))          # 深拷贝
        patch_workflow(wf, job)
        gui_path = f"tmp/funcontrol_{job['shot']}_gui.json"
        io.open(gui_path, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))

        obj = http_json("GET", f"{a.server}/object_info", timeout=60)
        api, problems = gui_to_api(wf, obj)
        api_path = f"tmp/funcontrol_{job['shot']}_api.json"
        io.open(api_path, "w", encoding="utf-8").write(json.dumps(api, ensure_ascii=False, indent=1))
        print(f"   GUI→API: {len(api)} 节点 → {api_path}")
        if problems:
            print("   ⚠ " + "; ".join(sorted(set(problems))))

        if a.mode == "dry":
            print("   [dry] 未提交\n"); continue
        try:
            r = http_json("POST", f"{a.server}/prompt",
                          {"prompt": api, "client_id": "auto_fight"}, timeout=60)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            print(f"   ❌ 服务端拒收: {body[:400]}\n")
            if a.mode == "validate":
                sys.exit(2)
            continue
        pid = r["prompt_id"]
        print(f"   提交 prompt_id={pid}")

        if a.mode == "validate":
            print("   [validate] 服务端接受图结构（未等出片）\n"); continue

        # ── 监控
        t0, done = time.time(), False
        while time.time() - t0 < 3600:
            time.sleep(10)
            h = http_json("GET", f"{a.server}/history/{pid}")
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error":
                    print("   ❌ 出错:", json.dumps(st.get("messages", []), ensure_ascii=False)[:300])
                    break
                outs = h[pid].get("outputs", {})
                vids = []
                for o in outs.values():
                    for key in ("gifs", "images", "videos"):
                        for item in o.get(key, []):
                            f_ = item.get("filename", "")
                            if f_.endswith(".mp4"):
                                vids.append(os.path.join(COMFY_OUTPUT, item.get("subfolder", ""), f_))
                if vids:
                    dst = os.path.join(a.out, f"{a.prefix}_{job['shot']}.mp4")
                    shutil.copy2(max(vids, key=os.path.getmtime), dst)
                    print(f"   ✅ {dst}  {os.path.getsize(dst)//1024}KB  用时 {int(time.time()-t0)}s")
                    done = True
                    break
        if not done and a.mode == "run":
            print("   ⚠ 超时/未取到产物")

    # ── 拼接
    if a.mode == "run":
        parts = sorted([f for f in os.listdir(a.out)
                        if re.match(rf"{re.escape(a.prefix)}_\d+\.mp4$", f)])
        if len(parts) >= 2:
            lst = os.path.join(a.out, "concat.txt")
            io.open(lst, "w", encoding="utf-8").write(
                "".join(f"file '{p}'\n" for p in parts))
            final = os.path.join(a.out, f"{a.prefix}_打斗段_全自动.mp4")
            subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
                            "-safe", "0", "-i", lst, "-c", "copy", final], check=True)
            print(f"\n拼接完成：{final}")

if __name__ == "__main__":
    main()
