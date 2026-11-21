#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N17 · 背景音 / 音效混音与响度统一（ducking + 两遍 loudnorm + 可选字幕 / 变速 + 剪辑单记录）

依据（经验库 10.3、references/sound-and-subtitles.md）：
    edit_tool.py render 按剪辑单的 环境声 / 音效 / 配音 行铺底混入并做 loudnorm，
    但**不执行** ducking、交叉淡入、配乐进入/退出、静音。
    这些必须用外部 ffmpeg 命令完成，并把命令与实测值记进剪辑单；
    "写下声音方案"或 render 成功都不等于已经混音。

本脚本封装实测通过的侧链压低链，并额外提供：
    * 两遍 loudnorm：先测 measured_* 再 linear=true 归一化，避免单遍动态处理偏离目标
    * 第三遍测量输出的实际 LUFS / 真峰，写进记录（不把目标值当实测值）
    * 可选硬字幕烧录（libass；srt 自动转 ass，用相对文件名规避 Windows 路径转义）
    * 可选 ±5% 语速微调（atempo），超过阈值直接拒绝，防口型穿帮（经验库 10.2）
    * 把完整可复现命令 + 参数 + 实测值幂等写入剪辑单「## 混音记录」区块
    * 同目录另存 混音命令.txt

只依赖随包 tools/ffmpeg/ffmpeg.exe + ffprobe.exe，不需要 numpy / PIL / ComfyUI python。

用法（6_剪辑 下双击 activate.bat 后，或任意 Python 3.9+）：
  python tools/mix_background.py \
      --input 制作成果/成片/EP001-成片.mp4 \
      --bg    素材/bgm.wav|0.18 \
      --bg    素材/室内底噪.wav|0.10 \
      --out   制作成果/成片/EP001-混音成片.mp4 \
      --subtitles 制作成果/字幕.srt \
      --cut-list 剧集/EP001/剪辑单.md

  # 只做音频（无画面）：--input dialog.wav --out mixed.wav
  # 只打印不执行：--dry
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG_DIR = HERE / "ffmpeg"
AF = "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"

REC_START = "<!-- N17-MIX-RECORD:START -->"
REC_END = "<!-- N17-MIX-RECORD:END -->"


# ------------------------------------------------------------------ utilities

def exe(name: str) -> str:
    for cand in (FFMPEG_DIR / (name + ".exe"), FFMPEG_DIR / name):
        if cand.is_file():
            return str(cand)
    return name  # 退回 PATH（activate.bat 已设置）


def run(cmd: list[str], *, cwd: str | None = None, capture: bool = False):
    if capture:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    if r.returncode != 0:
        raise RuntimeError("命令失败 (exit %d): %s\n%s" %
                           (r.returncode, " ".join(shlex.quote(x) for x in cmd),
                            (r.stderr or "")[-1800:]))
    return r


def probe(path: Path) -> dict:
    r = run([exe("ffprobe"), "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(path)], capture=True)
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    out = {"duration": 0.0, "width": 0, "height": 0, "fps": 24.0, "has_video": False,
           "has_audio": False}
    try:
        out["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        pass
    for st in data.get("streams", []):
        ct = st.get("codec_type")
        if ct == "video":
            out["has_video"] = True
            out["width"] = int(st.get("width") or 0)
            out["height"] = int(st.get("height") or 0)
            rate = str(st.get("r_frame_rate") or "24/1")
            try:
                a, b = rate.split("/")
                out["fps"] = float(a) / float(b) if float(b) else 24.0
            except (ValueError, ZeroDivisionError):
                pass
        elif ct == "audio":
            out["has_audio"] = True
    return out


def loudness_measure(wav: Path, lufs: float, tp: float, lra: float) -> dict:
    """用 loudnorm print_format=json 测量实际 LUFS / 真峰 / LRA。"""
    f = ("loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (lufs, tp, lra))
    r = run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(wav),
             "-af", f, "-f", "null", "-"], capture=True)
    txt = r.stderr or ""
    m = re.search(r"\{\s*\"input_i\".*?\}", txt, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def parse_bg(items: list[str]) -> list[tuple[Path, float]]:
    out = []
    for raw in items:
        if "|" in raw:
            p, _, v = raw.rpartition("|")
            try:
                vol = float(v)
            except ValueError:
                vol = 0.18
        else:
            p, vol = raw, 0.18
        path = Path(p).resolve()
        if not path.is_file():
            raise SystemExit("[错误] 背景音文件不存在：%s" % path)
        out.append((path, vol))
    if not out:
        raise SystemExit("[错误] 至少需要一个 --bg；纯对白压静默请用 audio_tighten.py")
    return out


def fmt_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


# ------------------------------------------------------------------ filter graph

def build_graph(n_bg: int, bgs: list[tuple[Path, float]], args, duration: float) -> str:
    parts: list[str] = []
    dlg_filters = []
    if abs(args.tempo - 1.0) > 1e-6:
        dlg_filters.append("atempo=%.4f" % args.tempo)
    dlg_filters.append(AF)
    parts.append("[0:a]%s[dlg0]" % ",".join(dlg_filters))
    if args.no_duck:
        # 不压低时必须直连，否则 acompressor 的 duckkey 输出悬空会报 unconnected
        parts.append("[dlg0]anull[dlg]")
    else:
        parts.append("[dlg0]asplit=2[dlg][key]")
        parts.append("[key]highpass=f=200,acompressor=threshold=%.4f:ratio=%s:attack=%s:release=%s[duckkey]"
                     % (args.key_threshold, args.duck_ratio, args.duck_attack, args.duck_release))

    bg_labels = []
    for idx, (_, vol) in enumerate(bgs, 1):
        label = "bg%d" % (idx - 1)
        parts.append("[%d:a]volume=%.4f,%s[%s]" % (idx, vol, AF, label))
        bg_labels.append("[%s]" % label)
    if len(bg_labels) == 1:
        parts.append("%sanull[bgall]" % bg_labels[0])
    else:
        parts.append("%samix=inputs=%d:duration=first:dropout_transition=0,"
                     "alimiter=limit=0.95[bgall]" % ("".join(bg_labels), len(bg_labels)))

    if args.no_duck:
        parts.append("[bgall]anull[bgduck]")
    else:
        parts.append("[bgall][duckkey]sidechaincompress=threshold=%.4f:ratio=%s:"
                     "attack=%s:release=%s[bgduck]"
                     % (args.duck_threshold, args.duck_ratio,
                        args.duck_attack, args.duck_release))
    parts.append("[dlg][bgduck]amix=inputs=2:duration=first:dropout_transition=0,"
                 "alimiter=limit=0.95[premix]")
    return ";".join(parts)


# ------------------------------------------------------------------ cut list record

def write_cut_list_record(cut_list: Path, block: str) -> None:
    if cut_list.is_file():
        text = cut_list.read_text(encoding="utf-8")
    else:
        cut_list.parent.mkdir(parents=True, exist_ok=True)
        text = "# 剪辑单\n"
    if REC_START in text and REC_END in text:
        pre = text.split(REC_START)[0].rstrip()
        post = text.split(REC_END, 1)[1].lstrip("\n")
        text = pre + "\n\n" + block + ("\n\n" + post if post else "")
    else:
        text = text.rstrip() + "\n\n---\n\n" + block + "\n"
    cut_list.write_text(text, encoding="utf-8")


def build_record(args, bgs, info, cmds, measured, out_path, sub_note, tempo_note,
                 intermediate_note) -> str:
    lines = [
        REC_START,
        "## 混音记录（N17 · %s）" % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "> 由 `6_剪辑/tools/mix_background.py` 生成；本区块幂等覆盖，可重复执行。",
        "> `edit_tool.py render` 不做 ducking / 交叉淡入 / 配乐进出，本记录是外部混音的可复现凭证。",
        "",
        "- 输入（对白 / 主轨）：`%s`%s" % (args.input,
                                    "（含画面 %.0fx%.0f @ %.2ffps）" % (info["width"], info["height"], info["fps"])
                                    if info["has_video"] else "（纯音频）"),
        "- 背景音：" + "；".join("`%s` ×%.2f" % (p, v) for p, v in bgs),
        "- 输出：`%s`" % out_path,
        "- 对白压低（ducking）：%s" % ("关闭" if args.no_duck else
                                    "threshold=%.4f / ratio=%s / attack=%s / release=%s（侧链 highpass=200 + acompressor）"
                                    % (args.duck_threshold, args.duck_ratio, args.duck_attack, args.duck_release)),
        "- 响度：%s loudnorm，目标 I=%s LUFS / TP=%s dBTP / LRA=%s" %
        ("单遍" if args.single_pass else "两遍（先测 measured_* 再 linear=true）",
         args.lufs, args.tp, args.lra),
        "- 实测整片响度：**%s LUFS / %s dBTP / LRA %s**（第三遍测量，非目标值）" %
        (measured.get("input_i", "未测得"), measured.get("input_tp", "未测得"),
         measured.get("input_lra", "未测得")),
        "- 字幕：%s" % sub_note,
        "- 语速微调：%s" % tempo_note,
        "- 中间文件：%s" % intermediate_note,
        "- 仍需人工 / 剪辑单声明：接缝回听、有意静默、配乐进入退出、交叉淡入、画内文字避让。",
        "",
        "可复现命令（按顺序）：",
        "",
        "```bash",
    ]
    for c in cmds:
        lines.append(fmt_cmd(c))
    lines += ["```", "", REC_END]
    return "\n".join(lines)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="N17 背景音混音：ducking + 两遍 loudnorm + 可选字幕/变速 + 记入剪辑单")
    ap.add_argument("--input", type=Path, required=True, help="对白主轨：成片 mp4 或 wav")
    ap.add_argument("--bg", action="append", default=[],
                    help="背景音，可重复；格式 路径 或 路径|音量（默认 0.18）")
    ap.add_argument("--out", type=Path, required=True, help="输出 .mp4 / .wav / .m4a")
    ap.add_argument("--cut-list", type=Path, help="剪辑单.md；给则写入「混音记录」区块")
    ap.add_argument("--subtitles", type=Path, help="硬字幕 .srt / .ass（需 --out 为 mp4 且输入含画面）")
    ap.add_argument("--tempo", type=float, default=1.0,
                    help="对白整体变速 0.95~1.05（经验库 10.2：超过 5%% 口型穿帮）")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--tp", type=float, default=-1.5)
    ap.add_argument("--lra", type=float, default=11.0)
    ap.add_argument("--duck-threshold", type=float, default=0.02)
    ap.add_argument("--key-threshold", type=float, default=0.03)
    ap.add_argument("--duck-ratio", default="6")
    ap.add_argument("--duck-attack", default="20")
    ap.add_argument("--duck-release", default="400")
    ap.add_argument("--no-duck", action="store_true", help="只铺底不压低（纯环境声场景）")
    ap.add_argument("--single-pass", action="store_true", help="单遍 loudnorm（默认两遍线性）")
    ap.add_argument("--clean", action="store_true",
                    help="完成后删除 混音中间文件/（默认保留，保证命令可复现且交付含中间文件）")
    ap.add_argument("--dry", action="store_true", help="只打印命令，不执行")
    args = ap.parse_args()

    # 绝对路径：字幕烧录时 ffmpeg 的工作目录会切到临时目录
    args.input = args.input.resolve()
    args.out = args.out.resolve()
    if args.subtitles:
        args.subtitles = args.subtitles.resolve()
    if args.cut_list:
        args.cut_list = args.cut_list.resolve()
    if not args.input.is_file():
        raise SystemExit("[错误] 输入不存在：%s" % args.input)
    if not 0.95 <= args.tempo <= 1.05:
        raise SystemExit("[错误] --tempo 必须在 0.95~1.05；超过 5%% 会口型穿帮（经验库 10.2）")
    bgs = parse_bg(args.bg)
    info = probe(args.input)
    if not info["has_audio"]:
        raise SystemExit("[错误] 输入无音轨：%s" % args.input)
    suffix = args.out.suffix.lower()
    if suffix not in (".mp4", ".wav", ".m4a", ".aac"):
        raise SystemExit("[错误] --out 需为 .mp4 / .wav / .m4a / .aac")
    if args.subtitles:
        if not args.subtitles.is_file():
            raise SystemExit("[错误] 字幕文件不存在：%s" % args.subtitles)
        if suffix != ".mp4" or not info["has_video"]:
            raise SystemExit("[错误] 烧字幕需要 --out 为 .mp4 且 --input 含画面")
    if suffix == ".mp4" and not info["has_video"]:
        raise SystemExit("[错误] --out 为 mp4 但输入无画面；请给含画面的成片，或改输出 .wav")

    graph = build_graph(len(bgs), bgs, args, info["duration"])
    # 中间文件落在成片旁：命令可复现，且交付包自带「可继续编辑的中间文件」
    work = args.out.parent / "混音中间文件"
    work.mkdir(parents=True, exist_ok=True)
    premix = work / "premix.wav"
    mixed = work / "mixed.wav"

    premix_cmd = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                  "-i", str(args.input)]
    for p, _ in bgs:
        premix_cmd += ["-stream_loop", "-1", "-i", str(p)]
    premix_cmd += ["-filter_complex", graph, "-map", "[premix]"]
    if info["duration"] > 0:
        premix_cmd += ["-t", "%.3f" % info["duration"]]
    premix_cmd += ["-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(premix)]

    if args.single_pass:
        norm_af = "loudnorm=I=%s:TP=%s:LRA=%s:print_format=summary" % (args.lufs, args.tp, args.lra)
    else:
        norm_af = None  # 运行时按测量值拼装
    measure_cmd = [exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(premix),
                   "-af", "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (args.lufs, args.tp, args.lra),
                   "-f", "null", "-"]

    print("N17 背景音混音 · %s" % args.out)
    print("  对白：%s  (%.2fs, %s)" % (args.input, info["duration"],
                                     "含画面" if info["has_video"] else "纯音频"))
    for p, v in bgs:
        print("  背景：%s  ×%.2f" % (p, v))
    print("  ducking：%s / loudnorm：%s / tempo：%.3f" %
          ("关" if args.no_duck else "开", "单遍" if args.single_pass else "两遍", args.tempo))
    if args.dry:
        print("\n--- filter_complex ---\n" + graph)
        print("\n--- premix ---\n" + fmt_cmd(premix_cmd))
        print("\n--- measure ---\n" + fmt_cmd(measure_cmd))
        return 0

    recorded = [premix_cmd]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    run(premix_cmd)

    if args.single_pass:
        norm_cmd = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(premix), "-af", norm_af, "-ar", "48000", "-ac", "2",
                    "-c:a", "pcm_s16le", str(mixed)]
    else:
        first = loudness_measure(premix, args.lufs, args.tp, args.lra)
        if not first:
            print("[警告] 两遍测量失败，退回单遍 loudnorm", file=sys.stderr)
            norm_cmd = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(premix), "-af",
                        "loudnorm=I=%s:TP=%s:LRA=%s:print_format=summary" % (args.lufs, args.tp, args.lra),
                        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(mixed)]
        else:
            norm_af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:"
                       "measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true:print_format=summary"
                       % (args.lufs, args.tp, args.lra,
                          first.get("input_i", args.lufs), first.get("input_tp", args.tp),
                          first.get("input_lra", args.lra), first.get("input_thresh", -70),
                          first.get("target_offset", 0)))
            norm_cmd = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(premix), "-af", norm_af, "-ar", "48000", "-ac", "2",
                        "-c:a", "pcm_s16le", str(mixed)]
    recorded.append(norm_cmd)
    run(norm_cmd)
    measured = loudness_measure(mixed, args.lufs, args.tp, args.lra)

    sub_note = "无（未烧录）"
    tempo_note = "1.000（未变速）" if abs(args.tempo - 1.0) < 1e-6 else \
        "atempo=%.4f（±5%% 内，需回看口型同步）" % args.tempo

    if suffix == ".wav":
        shutil.copy2(mixed, args.out)
    elif suffix in (".m4a", ".aac"):
        c = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mixed),
             "-c:a", "aac", "-b:a", "192k", str(args.out)]
        recorded.append(c)
        run(c)
    else:  # mp4：把混音结果换回原画面，可选烧字幕
        vfilters = []
        if args.subtitles:
            sub = work / ("subs.ass" if args.subtitles.suffix.lower() == ".ass" else "subs.srt")
            shutil.copy2(args.subtitles, sub)
            if sub.suffix.lower() == ".srt":
                conv = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(sub), str(work / "subs.ass")]
                recorded.append(conv)
                run(conv)
            # 相对文件名 + cwd=work，规避 Windows 盘符冒号在 subtitles= 里的转义
            vfilters = ["-vf", "subtitles=subs.ass"]
            sub_note = "硬字幕 `%s`（libass 烧录，抽帧核对字号/折行/安全区）" % args.subtitles
        c = [exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(args.input), "-i", str(mixed)] + vfilters + [
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "libx264" if vfilters else "copy",
             "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-movflags", "+faststart", "-shortest", str(args.out)]
        # -c:v copy 时不能带 -crf/-preset/-pix_fmt
        if not vfilters:
            for flag in ("-crf", "-preset", "-pix_fmt"):
                i = c.index(flag)
                del c[i:i + 2]
        recorded.append(c)
        run(c, cwd=str(work))

    print("  输出：%s (%d B)" % (args.out, args.out.stat().st_size if args.out.exists() else 0))
    print("  实测响度：%s LUFS / %s dBTP" %
          (measured.get("input_i", "未测得"), measured.get("input_tp", "未测得")))

    cmd_file = args.out.parent / "混音命令.txt"
    cmd_file.write_text(
        "# N17 混音可复现命令 · %s\n\n" % datetime.now().strftime("%Y-%m-%d %H:%M") +
        "\n\n".join(fmt_cmd(c) for c in recorded) + "\n", encoding="utf-8")
    print("  命令记录：%s" % cmd_file)

    intermediate_note = "`%s`（premix.wav / mixed.wav / subs.ass）" % work
    if args.clean:
        shutil.rmtree(work, ignore_errors=True)
        intermediate_note += "；已用 --clean 清理，复现前需先重跑第 1 步生成 premix.wav"
        print("  中间文件：已清理（--clean）")

    if args.cut_list:
        block = build_record(args, bgs, info, recorded, measured, args.out,
                             sub_note, tempo_note, intermediate_note)
        write_cut_list_record(args.cut_list, block)
        print("  剪辑单记录：%s（## 混音记录，幂等覆盖）" % args.cut_list)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
