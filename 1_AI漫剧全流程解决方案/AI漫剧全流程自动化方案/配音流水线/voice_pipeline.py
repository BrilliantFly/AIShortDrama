#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""剧本配音流水线：剧本 → 逐句配音（情绪/语速/音量/停顿/抢话）→ 真人互动对白音轨。

四段：
  parse     剧本.md / 配音本.jsonl → voice_sheet.csv
  plan      performance_cue 自然语言 → 情绪8维 / speech_speed / gain_db / gap / seed
  render    逐句构造 IndexTTS2 Advanced API prompt 提交 ComfyUI → wav/<line_id>.wav
  assemble  时间轴混音（音量/停顿/抢话重叠/响度归一）→ 对白_full.wav + 对白时间线.csv

设计边界（对齐 voice-direction.md 与经验库 4.0/4.6）：
  · 音色参考音频 = 身份，同一角色跨句固定，不携带情绪/语速/录音空间
  · 情绪、语速、音量、停顿 = 表演，逐句可变
  · 语速在 TTS 层用 speech_speed 控制；音量在后期用 volume(dB) 控制，
    这样改音量不必重跑 TTS；两者不重复施加
  · 句间停顿与抢话在后期时间轴做（TTS 的 interval_silence_ms 只管长文本内部断句）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_MAP = ROOT / "voice_map.json"
SHEET_COLUMNS = [
    "line_id", "shot", "speaker", "text", "channel", "cue", "ref_audio",
    "emotion", "speed", "gain_db", "pause_after", "overlap",
]


def out(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    raise SystemExit("[FAIL] " + str(msg))


def load_map(path: Path) -> dict:
    if not path.is_file():
        die(f"参数词表不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_sheet(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for col in SHEET_COLUMNS:
        for r in rows:
            r.setdefault(col, "")
    return rows


def write_sheet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in SHEET_COLUMNS})


# --------------------------------------------------------------------------
# parse
# --------------------------------------------------------------------------

def discover_characters(text: str) -> list[str]:
    """从「## 人物」段的 - **名字**（男，27） 抽角色名。"""
    m = re.search(r"##\s*人物(.*?)(?=\n##\s|\Z)", text, re.S)
    if not m:
        return []
    names = re.findall(r"\*\*([\u4e00-\u9fff]{2,6})\*\*", m.group(1))
    return list(dict.fromkeys(names))


def parse_voice_refs(spec: str) -> dict:
    refs = {}
    for part in (spec or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            refs[k.strip()] = v.strip().replace("\\", "/")
    return refs


def clean_cue(s: str) -> str:
    s = re.sub(r"「.+?」", " ", s)
    s = re.sub(r"[*_#>|（）()【】\[\]]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()[:60]


def pick_speaker(after: str, before: str, prev_line: str,
                 chars: list[str], fallback: str) -> str:
    """按距离台词由近到远找说话人；同一段里取出现位置最早的角色名。

    剧本常见写法是「台词」+「某人说」，所以台词紧随的 after 最可靠；
    prev_line 只作最后兜底，避免上一行的人名串到本句。
    """
    for ctx in (after, before, prev_line):
        hits = [(ctx.find(n), n) for n in chars if n in ctx]
        if hits:
            return min(hits)[1]
    if re.search(r"他说|她说|又都|自己先", f"{after} {before}"):
        return fallback or ""
    return ""


def parse_markdown(path: Path, args) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    chars = [c.strip() for c in (args.characters or "").split(",") if c.strip()]
    if not chars:
        chars = discover_characters(text)
    if not chars:
        out("  [WARN] 未识别到角色名，建议用 --characters 显式指定")
    refs = parse_voice_refs(args.voice_refs)
    prefix = args.shot_prefix or "S"

    lines = text.splitlines()
    rows: list[dict] = []
    paragraph = 0
    prev_line = ""
    prev_speaker = ""
    seq = 0
    skipped = 0
    for raw in lines:
        if not raw.strip():
            paragraph += 1
            continue
        if "「" not in raw:
            prev_line = raw
            continue
        spans = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"「(.+?)」", raw)]
        for i, (s, e, line_text) in enumerate(spans):
            t = line_text.strip()
            # 剧本里的拟声/音效常用「啪」「哐」这类无标点短「」，不是台词
            if len(t) <= 2 and not re.search(r"[。！？…、，,.!?]", t):
                skipped += 1
                continue
            seq += 1
            before = raw[:s]
            next_start = spans[i + 1][0] if i + 1 < len(spans) else len(raw)
            after = raw[e:next_start]
            ctx_all = f"{before} {after} {prev_line}"
            speaker = pick_speaker(after, before, prev_line, chars, prev_speaker) or prev_speaker
            if speaker:
                prev_speaker = speaker
            cue = clean_cue(f"{before} {after}")
            channel = "VO" if re.search(r"画外|旁白|VO|OS|内心", ctx_all) else "sync"
            shot = f"{prefix}{paragraph:03d}"
            rows.append({
                "line_id": f"VL-{seq:03d}",
                "shot": shot,
                "speaker": speaker,
                "text": t,
                "channel": channel,
                "cue": cue,
                "ref_audio": refs.get(speaker, f"voices/{speaker or 'unknown'}.wav"),
                "emotion": "", "speed": "", "gain_db": "",
                "pause_after": "", "overlap": "",
            })
        prev_line = raw
    if skipped:
        out(f"  [INFO] 跳过 {skipped} 条疑似音效/拟声「」")
    if not rows:
        die("剧本里没找到「」台词；若是 jsonl/csv 配音本请直接作为输入")
    return rows


def parse_jsonl(path: Path, args) -> list[dict]:
    refs = parse_voice_refs(args.voice_refs)
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        if d.get("record_type") or "line_text" not in d:
            continue
        speaker = d.get("speaker_display", "")
        src = (d.get("source_ref") or {}).get("record_id", "")
        m = re.search(r"SC(\d+)", src)
        shot = f"{args.shot_prefix or 'S'}{int(m.group(1)):03d}" if m else f"{args.shot_prefix or 'S'}001"
        rows.append({
            "line_id": d.get("line_id", f"VL-{len(rows)+1:03d}"),
            "shot": shot,
            "speaker": speaker,
            "text": d.get("line_text", "").strip(),
            "channel": d.get("channel", "sync"),
            "cue": d.get("performance_cue") or "",
            "ref_audio": refs.get(speaker, f"voices/{speaker or 'unknown'}.wav"),
            "emotion": "", "speed": "", "gain_db": "",
            "pause_after": "", "overlap": "",
        })
    return rows


def cmd_parse(args) -> None:
    src = Path(args.script)
    if not src.is_file():
        die(f"剧本不存在：{src}")
    if src.suffix.lower() == ".jsonl":
        rows = parse_jsonl(src, args)
    elif src.suffix.lower() == ".csv":
        rows = read_sheet(src)
    else:
        rows = parse_markdown(src, args)
    dst = Path(args.out)
    write_sheet(dst, rows)
    missing = sorted({r["speaker"] for r in rows if not r["speaker"]})
    out(f"OK  {len(rows)} 句 → {dst}")
    out(f"    角色：{', '.join(sorted({r['speaker'] for r in rows if r['speaker']})) or '未识别'}")
    if missing:
        out("    [WARN] 有句子未识别说话人，请人工补 speaker 列")
    out("    下一步：plan（cue → 情绪/语速/音量/停顿），或直接编辑 CSV 覆盖任意列")
    for r in rows[:3]:
        out(f"      {r['line_id']} [{r['speaker']}] {r['text'][:24]} | cue={r['cue'][:30]}")


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def match_keyword(cue: str, table: dict, default):
    """长关键词优先，避免「太快」抢掉「说得太快」。"""
    for key in sorted(table, key=len, reverse=True):
        if key in cue:
            return table[key]
    return default


def stable_seed(line_id: str, base: int = 20261122) -> int:
    h = hashlib.md5(line_id.encode("utf-8")).hexdigest()
    return base + int(h[:6], 16) % 100000


def validate_vector(vec: list, mapping: dict, tag: str) -> list[float]:
    vec = [float(v) for v in vec]
    if len(vec) != 8:
        die(f"{tag} 情绪向量必须 8 维，实际 {len(vec)}")
    cap = float(mapping["emotion_vector_sum_max"])
    total = sum(vec)
    if any(v < 0 for v in vec):
        die(f"{tag} 情绪向量有负值")
    if total > cap + 1e-6:
        vec = [v * (cap - 0.01) / total for v in vec]
    return [round(v, 3) for v in vec]


def cmd_plan(args) -> None:
    mapping = load_map(Path(args.map))
    rows = read_sheet(Path(args.sheet))
    inter = mapping["interaction"]
    lines = []
    prev_speaker = None
    prev_emotion = None
    for r in rows:
        cue = (r.get("cue") or "").strip()
        speaker = (r.get("speaker") or "").strip()
        line_text = (r.get("text") or "").strip()
        if not line_text:
            continue

        emotion = (r.get("emotion") or "").strip() or match_keyword(
            cue, mapping["emotion_keywords"], mapping["default_emotion"])
        if emotion not in mapping["emotions"]:
            die(f"{r['line_id']} 未知情绪 '{emotion}'，可用：{', '.join(mapping['emotions'])}")
        vec = validate_vector(list(mapping["emotions"][emotion]), mapping, r["line_id"])

        # 同一说话人连续同情绪：给非主导维加微小起伏，避免连读像念稿
        jit = float(inter.get("emotion_jitter", 0) or 0)
        if jit > 0 and speaker == prev_speaker and emotion == prev_emotion:
            idx = min(range(8), key=lambda k: vec[k])
            vec[idx] = round(vec[idx] + jit, 3)
            vec = validate_vector(vec, mapping, r["line_id"])

        def num(col, table, default, cast=float):
            raw = (r.get(col) or "").strip()
            return cast(raw) if raw else cast(match_keyword(cue, table, default))

        speed = num("speed", mapping["speed_keywords"], 1.0)
        gain_db = num("gain_db", mapping["volume_keywords"], 0.0)
        # pause_keywords 未命中时返回 None，需单独处理（不能走 num 的 cast）
        if (r.get("pause_after") or "").strip():
            pause_explicit = float(r["pause_after"])
        else:
            p = match_keyword(cue, mapping["pause_keywords"], None)
            pause_explicit = float(p) if p is not None else None
        overlap = num("overlap", mapping["overlap_keywords"], 0.0)

        if overlap:
            gap = float(overlap)
        elif pause_explicit is not None:
            gap = float(pause_explicit)
        elif prev_speaker is None:
            gap = 0.0
        elif speaker != prev_speaker:
            gap = float(inter["gap_speaker_switch"])
        else:
            gap = float(inter["gap_same_speaker"])
        gap = max(float(inter["min_gap"]), gap)

        n_chars = len(re.findall(r"[\u4e00-\u9fff]", line_text))
        interval = 200 if n_chars <= 24 else (280 if n_chars <= 45 else 380)

        lines.append({
            "line_id": r["line_id"],
            "shot": r.get("shot") or "S001",
            "speaker": speaker,
            "text": line_text,
            "channel": r.get("channel") or "sync",
            "cue": cue,
            "ref_audio": r.get("ref_audio") or "",
            "emotion": emotion,
            "emotion_vector": vec,
            "speed": round(float(speed), 3),
            "gain_db": round(float(gain_db), 2),
            "interval_silence_ms": interval,
            "seed": stable_seed(r["line_id"]),
            "gap_before": round(gap, 3),
        })
        prev_speaker, prev_emotion = speaker, emotion

    plan = {
        "project": args.project,
        "source": str(Path(args.sheet).resolve()),
        "map": str(Path(args.map).resolve()),
        "lines": lines,
    }
    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    out(f"OK  {len(lines)} 句 → {dst}")
    for l in lines[:6]:
        out(f"    {l['line_id']} [{l['speaker']}/{l['emotion']}] "
            f"speed={l['speed']} gain={l['gain_db']:+.1f}dB gap={l['gap_before']:+.2f}s "
            f"seed={l['seed']} | {l['text'][:20]}")
    out("    下一步：render（逐句合成）或 assemble --post-speed（已有 wav 时）")


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def build_api_prompt(line: dict, mapping: dict) -> dict:
    """直接构造官方 API 格式，不依赖 GUI 序列化的 widget 顺序。

    批量模式不接 emotion_audio：源码确认 emotion_vector 与 emotion_audio 同时存在时
    向量优先、第二条音频被忽略，接了反而造成误解。
    """
    ct = mapping["api_nodes"]["class_types"]
    d = mapping["tts_defaults"]
    order = mapping["emotion_vector_order"]
    emo = {name: float(line["emotion_vector"][i]) for i, name in enumerate(order)}
    save = mapping["save_audio_defaults"]

    adv = {
        "audio": ["1", 0],
        "text": line["text"],
        "emotion_control_weight": float(d["emotion_control_weight"]),
        "emotion_vector": ["3", 0],
        "use_random_style": bool(d["use_random_style"]),
        "interval_silence_ms": int(line["interval_silence_ms"]),
        "max_text_tokens_per_segment": int(d["max_text_tokens_per_segment"]),
        "seed": int(line["seed"]),
        "do_sample": bool(d["do_sample"]),
        "temperature": float(d["temperature"]),
        "top_p": float(d["top_p"]),
        "top_k": int(d["top_k"]),
        "repetition_penalty": float(d["repetition_penalty"]),
        "length_penalty": float(d["length_penalty"]),
        "num_beams": int(d["num_beams"]),
        "max_mel_tokens": int(d["max_mel_tokens"]),
        "typical_sampling": bool(d["typical_sampling"]),
        "typical_mass": float(d["typical_mass"]),
        "speech_speed": float(line["speed"]),
        "use_fp16": bool(d["use_fp16"]),
        "output_gain": float(d["output_gain"]),
    }
    return {
        "1": {"class_type": ct["LoadAudio"], "inputs": {"audio": line["ref_audio"]}},
        "3": {"class_type": ct["IndexTTS2EmotionVector"], "inputs": emo},
        "4": {"class_type": ct["IndexTTS2Advanced"], "inputs": adv},
        "5": {"class_type": ct["IndexTTS2SaveAudio"], "inputs": {
            "audio": ["4", 0],
            "name": f"tts2_{line['line_id']}",
            "format": save["format"],
            "normalize_peak": bool(save["normalize_peak"]),
            "wav_pcm": save["wav_pcm"],
            "mp3_bitrate": save["mp3_bitrate"],
        }},
    }


def http_json(url: str, payload=None, timeout: int = 60) -> dict:
    if payload is None:
        req = urllib.request.Request(url)
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def find_audio_item(hist: dict, prompt_id: str) -> dict | None:
    entry = hist.get(prompt_id) or {}
    for node_out in (entry.get("outputs") or {}).values():
        for holder in (node_out, node_out.get("ui") or {}):
            items = holder.get("audio") or []
            if items:
                return items[0]
    return None


def download_audio(server: str, item: dict, dest: Path) -> bool:
    q = urllib.parse.urlencode({
        "filename": item.get("filename", ""),
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output"),
    })
    url = f"http://{server}/view?{q}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        if len(data) < 1024:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as e:
        out(f"    [WARN] /view 取回失败：{e}")
        return False


def cmd_render(args) -> None:
    mapping = load_map(Path(args.map))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    lines = plan["lines"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        lines = [l for l in lines if l["line_id"] in wanted or l["shot"] in wanted]
    wav_dir = Path(args.wav_dir)
    wav_dir.mkdir(parents=True, exist_ok=True)
    manifest = wav_dir / "render_manifest.jsonl"
    done = set()
    if manifest.is_file() and not args.force:
        for ln in manifest.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(ln)["line_id"])
            except Exception:
                pass

    # --from-wavs：跳过 TTS，直接用已有 wav 验证后期链
    if args.from_wavs:
        src = Path(args.from_wavs)
        copied = 0
        for l in lines:
            dst = wav_dir / f"{l['line_id']}.wav"
            candidate = src / f"{l['line_id']}.wav"
            if not candidate.is_file():
                cand2 = list(src.glob(f"*{l['line_id']}*.wav"))
                candidate = cand2[0] if cand2 else candidate
            if candidate.is_file() and not dst.is_file():
                shutil.copy2(candidate, dst)
                copied += 1
        out(f"OK  --from-wavs：复制 {copied} 条 → {wav_dir}（跳过 TTS）")
        return

    if args.dry:
        out(f"DRY  将提交 {len(lines)} 句，API 节点：LoadAudio / EmotionVector / Advanced / SaveAudio")
        for l in lines[:4]:
            api = build_api_prompt(l, mapping)
            a = api["4"]["inputs"]
            out(f"    {l['line_id']} text={l['text'][:18]!r} emo={l['emotion']} "
                f"speed={a['speech_speed']} seed={a['seed']} "
                f"interval={a['interval_silence_ms']}ms ref={l['ref_audio']}")
        out("    （未连接 ComfyUI。装好节点包后用不带 --dry 的本命令实跑）")
        return

    server = args.server.strip().replace("http://", "").rstrip("/")
    failures = []
    with manifest.open("a", encoding="utf-8") as mf:
        for l in lines:
            lid = l["line_id"]
            dst = wav_dir / f"{lid}.wav"
            if dst.is_file() and dst.stat().st_size > 1024 and not args.force:
                out(f"  [SKIP] {lid} 已完成")
                continue
            api = build_api_prompt(l, mapping)
            out(f"  [RUN ] {lid} [{l['speaker']}/{l['emotion']}] {l['text'][:20]}")
            try:
                res = http_json(f"http://{server}/prompt", {"prompt": api, "client_id": "voice_pipeline"}, timeout=60)
                pid = res.get("prompt_id")
                if not pid:
                    raise RuntimeError(f"/prompt 未返回 prompt_id：{str(res)[:300]}")
                item = None
                deadline = time.time() + args.timeout
                while time.time() < deadline:
                    try:
                        hist = http_json(f"http://{server}/history/{pid}", timeout=30)
                        item = find_audio_item(hist, pid)
                        if item:
                            break
                        entry = hist.get(pid) or {}
                        st = (entry.get("status") or {}).get("status_str")
                        if st == "error":
                            raise RuntimeError(f"ComfyUI 执行报错：{str(entry.get('status'))[:300]}")
                    except RuntimeError:
                        raise
                    except Exception:
                        pass
                    time.sleep(2)
                if not item:
                    raise RuntimeError(f"等待输出超时（{args.timeout}s）")
                if not download_audio(server, item, dst):
                    raise RuntimeError("音频取回失败（/view 返回空或过小）")
                mf.write(json.dumps({"line_id": lid, "prompt_id": pid,
                                     "wav": str(dst), "params": {
                                         "emotion": l["emotion"], "emotion_vector": l["emotion_vector"],
                                         "speed": l["speed"], "seed": l["seed"],
                                         "interval_silence_ms": l["interval_silence_ms"],
                                         "ref_audio": l["ref_audio"]}}, ensure_ascii=False) + "\n")
                mf.flush()
                out(f"  [OK  ] {lid} -> {dst}")
            except Exception as e:
                failures.append((lid, str(e)))
                out(f"  [FAIL] {lid}: {e}")
    out(f"完成：{len(lines) - len(failures)}/{len(lines)} 成功；wav → {wav_dir}")
    if failures:
        out("失败清单（可单独 --only 重跑）：")
        for lid, err in failures:
            out(f"  {lid}: {err[:160]}")


# --------------------------------------------------------------------------
# assemble
# --------------------------------------------------------------------------

def ffmpeg_exe(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            die("找不到 ffmpeg；请用 --ffmpeg 指定（ComfyUI 环境自带 imageio_ffmpeg）")
        return exe


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def run_ffmpeg(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        die("ffmpeg 失败：\n" + p.stderr.decode("utf-8", "replace")[-1200:])


def process_line(ffmpeg: str, src: Path, dst: Path, gain_db: float,
                 speed: float, post_speed: bool, sr: int) -> None:
    filters = []
    if abs(gain_db) > 1e-6:
        filters.append(f"volume={gain_db}dB")
    if post_speed and abs(speed - 1.0) > 1e-6:
        s = max(0.5, min(2.0, float(speed)))
        filters.append(f"atempo={s:.3f}")
    af = ",".join(filters) if filters else "anull"
    cmd = [ffmpeg, "-y", "-i", str(src), "-af", af,
           "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    run_ffmpeg(cmd)


def mix_timeline(ffmpeg: str, entries: list[dict], total: float,
                 out_path: Path, mapping: dict, loudnorm: bool) -> None:
    if not entries:
        return
    sr = int(mapping["assembly"]["sample_rate"])
    a = mapping["assembly"]
    cmd = [ffmpeg, "-y"]
    for e in entries:
        cmd += ["-i", str(e["proc"])]
    parts = []
    for i, e in enumerate(entries):
        ms = int(round(max(0.0, e["start"]) * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    chain = "".join(f"[a{i}]" for i in range(len(entries)))
    tail = f"amix=inputs={len(entries)}:duration=longest:normalize=0"
    post = "apad"
    if loudnorm:
        post += (f",loudnorm=I={a['loudnorm_I']}:TP={a['loudnorm_TP']}"
                 f":LRA={a['loudnorm_LRA']}")
    fc = ";".join(parts) + f";{chain}{tail},{post}[out]"
    cmd += ["-filter_complex", fc, "-map", "[out]", "-t", f"{total:.3f}",
            "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", str(out_path)]
    run_ffmpeg(cmd)


def cmd_assemble(args) -> None:
    mapping = load_map(Path(args.map))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    lines = plan["lines"]
    wav_dir = Path(args.wav_dir)
    out_dir = Path(args.out_dir)
    proc_dir = out_dir / "_processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_exe(args.ffmpeg)
    sr = int(mapping["assembly"]["sample_rate"])

    missing = [l["line_id"] for l in lines if not (wav_dir / f"{l['line_id']}.wav").is_file()]
    if missing:
        die(f"缺 wav：{', '.join(missing)}；先跑 render，或用 --from-wavs 提供现成音频")

    entries, timeline = [], []
    cursor = 0.0
    for i, l in enumerate(lines):
        src = wav_dir / f"{l['line_id']}.wav"
        dst = proc_dir / f"{l['line_id']}.wav"
        process_line(ffmpeg, src, dst, float(l["gain_db"]), float(l["speed"]),
                     bool(args.post_speed), sr)
        dur = wav_duration(dst)
        gap = 0.0 if i == 0 else float(l["gap_before"])
        start = max(0.0, cursor + gap)
        end = start + dur
        cursor = end
        entries.append({"line_id": l["line_id"], "shot": l["shot"],
                        "start": start, "end": end, "proc": dst})
        timeline.append({
            "line_id": l["line_id"], "shot": l["shot"], "speaker": l["speaker"],
            "channel": l["channel"], "start_s": round(start, 3), "end_s": round(end, 3),
            "duration_s": round(dur, 3), "gap_before_s": round(gap, 3),
            "emotion": l["emotion"], "speed": l["speed"], "gain_db": l["gain_db"],
            "text": l["text"],
        })

    tail = float(mapping["interaction"]["gap_tail"])
    total = cursor + tail
    full = out_dir / "对白_full.wav"
    mix_timeline(ffmpeg, entries, total, full, mapping, not args.no_loudnorm)
    out(f"OK  整段对白 → {full}（{total:.2f}s，{len(entries)} 句）")

    # 按镜另出一份，时间轴相对该镜首句
    shots: dict[str, list] = {}
    for e, t in zip(entries, timeline):
        shots.setdefault(e["shot"], []).append((e, t))
    shot_dir = out_dir / "shots"
    shot_dir.mkdir(exist_ok=True)
    for shot, group in shots.items():
        base = group[0][0]["start"]
        shifted = [{"proc": e["proc"], "start": max(0.0, e["start"] - base),
                    "end": e["end"] - base} for e, _ in group]
        stotal = max(x["end"] for x in shifted) + tail
        mix_timeline(ffmpeg, shifted, stotal, shot_dir / f"{shot}.wav",
                     mapping, not args.no_loudnorm)
    out(f"OK  分镜音轨 {len(shots)} 份 → {shot_dir}")

    tl_path = out_dir / "对白时间线.csv"
    with tl_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(timeline[0].keys()))
        w.writeheader()
        w.writerows(timeline)
    mf = {
        "plan": str(Path(args.plan).resolve()),
        "total_seconds": round(total, 3),
        "sample_rate": sr,
        "post_speed_applied": bool(args.post_speed),
        "loudnorm": not args.no_loudnorm,
        "interaction": mapping["interaction"],
        "timeline": timeline,
    }
    (out_dir / "assembly_manifest.json").write_text(
        json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    out(f"OK  时间线 → {tl_path} / assembly_manifest.json")
    for t in timeline[:6]:
        flag = "重叠" if t["gap_before_s"] < 0 else "   "
        out(f"    {t['start_s']:6.2f}-{t['end_s']:6.2f} {flag} "
            f"[{t['speaker']}/{t['emotion']}] {t['gain_db']:+.0f}dB x{t['speed']} | {t['text'][:18]}")


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def cmd_run(args) -> None:
    work = Path(args.out_dir)
    sheet = work / "voice_sheet.csv"
    plan = work / "voice_plan.json"
    wav_dir = work / "wav"
    final = work / "成片"
    work.mkdir(parents=True, exist_ok=True)

    out("=== 1/4 parse ===")
    cmd_parse(argparse.Namespace(script=args.script, out=str(sheet),
                                 characters=args.characters, voice_refs=args.voice_refs,
                                 shot_prefix=args.shot_prefix))
    out("=== 2/4 plan ===")
    cmd_plan(argparse.Namespace(sheet=str(sheet), out=str(plan), map=args.map,
                                project=args.project))
    if args.dry:
        out("=== 3/4 render (dry) ===")
        cmd_render(argparse.Namespace(plan=str(plan), map=args.map, wav_dir=str(wav_dir),
                                      server=args.server, dry=True, from_wavs=None,
                                      only=None, force=False, timeout=args.timeout))
        out("DRY 完成：装好节点包后去掉 --dry 即可实跑；或用 --from-wavs 验证后期链")
        return
    out("=== 3/4 render ===")
    cmd_render(argparse.Namespace(plan=str(plan), map=args.map, wav_dir=str(wav_dir),
                                  server=args.server, dry=False, from_wavs=args.from_wavs,
                                  only=args.only, force=args.force, timeout=args.timeout))
    out("=== 4/4 assemble ===")
    cmd_assemble(argparse.Namespace(plan=str(plan), map=args.map, wav_dir=str(wav_dir),
                                    out_dir=str(final), ffmpeg=args.ffmpeg,
                                    post_speed=args.post_speed, no_loudnorm=False))
    out(f"全部完成 → {final}")


def main() -> None:
    ap = argparse.ArgumentParser(description="剧本配音流水线（情绪/语速/音量/互动对白）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--map", default=str(DEFAULT_MAP), help="参数词表 voice_map.json")

    p = sub.add_parser("parse", help="剧本/配音本 → voice_sheet.csv")
    p.add_argument("--script", required=True, help="剧本.md / 配音本.jsonl / 已是配音本.csv")
    p.add_argument("--out", required=True)
    p.add_argument("--characters", default="", help="角色名，逗号分隔；留空则从「## 人物」抽")
    p.add_argument("--voice-refs", default="", help="角色音色参考，'林晚=voices/linwan.wav;沈屿=...'")
    p.add_argument("--shot-prefix", default="S")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("plan", help="cue → 情绪/语速/音量/停顿/抢话/seed")
    p.add_argument("--sheet", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--project", default="")
    common(p)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("render", help="逐句合成 wav（可断点续跑）")
    p.add_argument("--plan", required=True)
    p.add_argument("--wav-dir", required=True)
    p.add_argument("--server", default="127.0.0.1:8188")
    p.add_argument("--dry", action="store_true", help="只打印将提交的参数，不连 ComfyUI")
    p.add_argument("--from-wavs", default=None, help="跳过 TTS，直接采用现成 wav 目录")
    p.add_argument("--only", default=None, help="只跑指定 line_id/shot，逗号分隔")
    p.add_argument("--force", action="store_true", help="已有 wav 也重跑")
    p.add_argument("--timeout", type=int, default=900)
    common(p)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("assemble", help="时间轴混音 → 整段对白音轨 + 时间线 CSV")
    p.add_argument("--plan", required=True)
    p.add_argument("--wav-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--post-speed", action="store_true",
                   help="后期再施加快慢（默认语速已由 TTS 的 speech_speed 承担）")
    p.add_argument("--no-loudnorm", action="store_true")
    common(p)
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("run", help="parse → plan → render → assemble 一条龙")
    p.add_argument("--script", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--project", default="")
    p.add_argument("--characters", default="")
    p.add_argument("--voice-refs", default="")
    p.add_argument("--shot-prefix", default="S")
    p.add_argument("--server", default="127.0.0.1:8188")
    p.add_argument("--from-wavs", default=None)
    p.add_argument("--only", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--post-speed", action="store_true")
    p.add_argument("--dry", action="store_true")
    common(p)
    p.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
