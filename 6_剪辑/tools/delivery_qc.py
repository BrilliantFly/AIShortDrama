#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""N17 · 成片交付验收（对齐 references/delivery-verify.md 的 9 项 + 交付 1 项）

与 后期与质检/qc_gate.py 的分工（重要）：
    qc_gate.py    = 成片版 N16 的「逐镜门禁」：F0 / RMS / ASR TODO / 联系表，输入是逐镜 mp4。
    delivery_qc.py = 片段版 N17 的「成片终验」：输入是**已合成的成片 + 剪辑单 + 上游文档**，
                     对齐 delivery-verify.md 的 10 项。可用 --gate-report 把 qc_gate 结果并入。
    两者不互相替代，也不改动 qc_gate.py 本体（保持已定版生产脚本稳定）。

delivery-verify.md 开宗明义要求「区分实测结果、人工判断和未测项」，本脚本据此把每项标成：
    PASS 实测达标 / WARN 需人工看 / FAIL 内容类不符 / TODO 人工门禁 / SKIP 缺输入
技术观测（边界帧、接镜色彩）只列出「该看哪里」，**不阻断交付**——与原文一致。

自动化范围（只用随包 ffmpeg/ffprobe，不需要 numpy / PIL / ComfyUI python）：
    * 时长、切点、画幅、帧率：ffprobe + 剪辑单 CUT 时长
    * 整片响度 / 真峰：loudnorm print_format=json 实测（不把目标值当实测值）
    * 边界帧 / 接镜色彩：signalstats + metadata=print 逐帧 YAVG / UAVG / VAVG
    * 字幕逐字：剪辑单「字幕」行归一化后是否出自《剧本.md》
    * 内容覆盖 / 未采用理由 / 交付包文件齐备性
人工门禁（脚本只生成待办清单，不假装通过）：回听、接缝、画内文字、接镜色彩创作意图、ASR 转写。

用法（6_剪辑 下双击 activate.bat 后，或任意 Python 3.9+）：
  python tools/delivery_qc.py \
      --episode 剧集/EP001 \
      --film    剧集/EP001/制作成果/成片/EP001-成片.mp4 \
      --gate-report 制作成果/成片/qc_report.json \
      --report  剧集/EP001/制作成果/成片/验收报告.md
  # 快速模式（跳过逐帧统计）：--no-frames
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG_DIR = HERE / "ffmpeg"

CUT_HEADING = re.compile(r"^##\s+(CUT-[^\s·]+)\s*(?:·\s*(.*))?$")
MOTION_HEADING = re.compile(r"^##\s+(MOTION-[^\s·]+)", re.M)
FIELD = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*)$")
PUNCT = re.compile(r"[\s，。、；：？！,.!?;:\"“”「」『』（）()\[\]【】—\-…·]+")
QUOTED = re.compile(r"[「“\"']([^」”\"']{2,})[」”\"']")

STATUS_ORDER = {"FAIL": 0, "WARN": 1, "TODO": 2, "SKIP": 3, "PASS": 4}


# ------------------------------------------------------------------ utilities

def exe(name: str) -> str:
    for cand in (FFMPEG_DIR / (name + ".exe"), FFMPEG_DIR / name):
        if cand.is_file():
            return str(cand)
    return name


def run(cmd: list[str], capture: bool = True):
    return subprocess.run(cmd, capture_output=capture, text=True,
                          encoding="utf-8", errors="replace", timeout=1200)


def probe(path: Path) -> dict:
    r = run([exe("ffprobe"), "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
             "-of", "json", str(path)])
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    out = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0,
           "video_codec": "", "audio_codec": "", "has_video": False, "has_audio": False}
    try:
        out["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        pass
    for st in data.get("streams", []):
        if st.get("codec_type") == "video":
            out["has_video"] = True
            out["width"] = int(st.get("width") or 0)
            out["height"] = int(st.get("height") or 0)
            out["video_codec"] = st.get("codec_name", "")
            rate = str(st.get("r_frame_rate") or "0/1")
            try:
                a, b = rate.split("/")
                out["fps"] = float(a) / float(b) if float(b) else 0.0
            except (ValueError, ZeroDivisionError):
                pass
        elif st.get("codec_type") == "audio":
            out["has_audio"] = True
            out["audio_codec"] = st.get("codec_name", "")
    return out


def measure_loudness(film: Path, lufs: float) -> dict:
    r = run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(film),
             "-af", "loudnorm=I=%s:TP=-1.5:LRA=11:print_format=json" % lufs,
             "-f", "null", "-"])
    m = re.search(r"\{\s*\"input_i\".*?\}", r.stderr or "", re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def frame_stats(film: Path) -> list[dict]:
    """逐帧 YAVG / UAVG / VAVG；失败返回空列表（验收按未测处理）。"""
    r = run([exe("ffmpeg"), "-hide_banner", "-v", "error", "-i", str(film),
             "-vf", "signalstats,metadata=print:file=-", "-an", "-f", "null", "-"])
    frames: list[dict] = []
    cur: dict = {}
    for line in (r.stdout or "").splitlines():
        if line.startswith("frame:"):
            if cur:
                frames.append(cur)
                cur = {}
            continue
        m = re.match(r"lavfi\.signalstats\.(YAVG|UAVG|VAVG)=([-\d.]+)", line)
        if m:
            cur[m.group(1)] = float(m.group(2))
    if cur:
        frames.append(cur)
    return frames


def norm_text(s: str) -> str:
    return PUNCT.sub("", s).strip()


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


# ------------------------------------------------------------------ cut list parsing

def parse_cut_list(path: Path) -> dict:
    txt = read_text(path)
    out = {"cuts": [], "meta": {}, "unused": [], "subtitles": [],
           "on_screen_text": [], "mix_record": False, "exists": path.is_file()}
    current = None
    for raw in txt.splitlines():
        h = CUT_HEADING.match(raw)
        if h:
            current = {"id": h.group(1), "title": (h.group(2) or "").strip(), "fields": {}}
            out["cuts"].append(current)
            continue
        if raw.startswith("## "):
            current = None
            continue
        f = FIELD.match(raw)
        if not f:
            continue
        key, val = f.group(1).strip(), f.group(2).strip()
        if current:
            current["fields"][key] = val
        else:
            out["meta"].setdefault(key, val)
            if key == "未采用镜头":
                out["unused"].extend(x.strip() for x in re.split(r"[；;]", val) if x.strip())
        # 只统计 CUT 内的字幕/画面文字行：元数据与「## 混音记录」区块不算镜头条目
        if current and key == "字幕" and val and val not in ("无", "待定"):
            out["subtitles"].append((current["id"], val))
        if current and key == "画面文字" and val:
            out["on_screen_text"].append((current["id"], val))
    out["mix_record"] = "N17-MIX-RECORD:START" in txt
    return out


def fnum(v) -> float:
    try:
        return float(str(v).strip().replace("秒", "").replace("s", ""))
    except (ValueError, TypeError):
        return 0.0


# ------------------------------------------------------------------ checks

def check_all(args, film: Path, ep: Path, cl: dict, info: dict,
              frames: list[dict], loud: dict, gate: dict) -> list[dict]:
    checks: list[dict] = []

    def add(no, name, status, measured, manual="", detail=None):
        checks.append({"no": no, "name": name, "status": status,
                       "measured": measured, "manual": manual, "detail": detail or []})

    # 1 时长与切点
    cut_durations = [fnum(c["fields"].get("时长", 0)) for c in cl["cuts"]]
    cut_total = sum(cut_durations)
    target = fnum(cl["meta"].get("成片目标时长", 0))
    diff = abs(info["duration"] - cut_total)
    d1 = ["CUT 时长合计 %.2fs；成片实测 %.2fs；差 %.2fs" % (cut_total, info["duration"], diff),
          "目标时长声明：%s" % (("%.2fs" % target) if target else "未声明"),
          "切点（累计秒 / 帧号）：" + (", ".join(
              "%.2fs@f%d" % (sum(cut_durations[:i + 1]), round(sum(cut_durations[:i + 1]) * info["fps"]))
              for i in range(len(cut_durations) - 1)) or "无（单段）")]
    st1 = "PASS" if diff <= 0.5 else "WARN"
    if not cl["exists"] or not info["duration"]:
        st1 = "SKIP"
    add(1, "时长与切点", st1, "成片 %.2fs / CUT 合计 %.2fs" % (info["duration"], cut_total),
        "对照实际渲染区间、帧边界与用户时长要求", d1)

    # 2 内容覆盖
    motion_ids = set(MOTION_HEADING.findall(read_text(ep / "视频提示词.md")))
    cut_sources = set()
    for c in cl["cuts"]:
        for m in re.findall(r"MOTION-[A-Za-z0-9-]+", c["fields"].get("来源", "")):
            cut_sources.add(m)
    unused_no_reason = [u for u in cl["unused"] if not re.search(r"理由|原因|因为|质量|缺失|重复", u)]
    docs = {n: (ep / n).is_file() for n in
            ("剧本.md", "分镜.md", "视频提示词.md", "视觉设定.md", "剪辑单.md")}
    d2 = ["剪辑单 CUT %d 个 / 视频提示词 MOTION %d 个 / 已引用 %d 个" %
          (len(cl["cuts"]), len(motion_ids), len(cut_sources)),
          "未采用镜头 %d 条%s" % (len(cl["unused"]),
                                "；无理由：" + "、".join(unused_no_reason) if unused_no_reason else "，均有理由"),
          "上游文档：" + "，".join("%s=%s" % (k, "有" if v else "缺") for k, v in docs.items())]
    st2 = "FAIL" if not docs["剪辑单.md"] else ("WARN" if (
        cl["cuts"] and len(cut_sources) != len(motion_ids)) or unused_no_reason or not all(docs.values())
        else "PASS")
    add(2, "内容覆盖", st2, "CUT %d / MOTION %d / 未采用 %d" %
        (len(cl["cuts"]), len(motion_ids), len(cl["unused"])),
        "对照分镜与视频提示词，确认必要内容有承载、未采用镜头写明原因", d2)

    # 3 台词
    script = read_text(ep / "剧本.md")
    lines = QUOTED.findall(script)
    gate_todo = []
    for shot, entry in (gate.get("shots") or {}).items():
        for k, v in entry.items():
            if isinstance(v, dict) and v.get("status") == "TODO":
                gate_todo.append("镜 %s · %s" % (shot, k))
    d3 = ["《剧本.md》可识别台词 %d 句" % len(lines),
          "qc_gate 合并：%s" % ("已提供，人工待办 %d 项" % len(gate_todo) if gate else "未提供（--gate-report）"),
          "ASR 待办：" + ("；".join(gate_todo[:12]) if gate_todo else "无")]
    add(3, "台词", "TODO", "剧本台词 %d 句 / qc_gate 待办 %d 项" % (len(lines), len(gate_todo)),
        "成片上回听、必要时转写辅助，逐句对照剧本；内容错→回生成端换 seed 重出", d3)

    # 4 边界帧
    cut_points = []
    acc = 0.0
    for i, d in enumerate(cut_durations[:-1]):
        acc += d
        cut_points.append((cl["cuts"][i + 1]["id"], round(acc * info["fps"])))
    yavg = [f.get("YAVG", 0.0) for f in frames]
    jump, bad = [], []
    for cid, fi in cut_points:
        if 0 < fi < len(yavg):
            delta = abs(yavg[fi] - yavg[fi - 1])
            if delta > 20:
                jump.append("%s · f%d 亮度差 %.1f（>20，请逐帧查看）" % (cid, fi, delta))
    for i in range(1, len(yavg) - 1):
        if (abs(yavg[i - 1] - yavg[i + 1]) < 8 and
                abs(yavg[i] - yavg[i - 1]) > 20 and abs(yavg[i] - yavg[i + 1]) > 20):
            bad.append("f%d（YAVG %.1f，前后 %.1f/%.1f）" % (i, yavg[i], yavg[i - 1], yavg[i + 1]))
    d4 = ["逐帧统计：%d 帧；切点 %d 个" % (len(frames), len(cut_points)),
          "切点亮度突变 %d 处" % len(jump), "疑似坏帧 %d 帧" % len(bad)]
    d4 += ["请逐帧查看 · " + x for x in jump[:15]]
    d4 += ["疑似坏帧 · " + x for x in bad[:15]]
    if not frames:
        d4.append("未测原因：逐帧统计失败或用了 --no-frames（verify 的技术测量未执行）")
    add(4, "边界帧", "WARN" if (jump or bad) else ("SKIP" if not frames else "PASS"),
        "切点突变 %d / 疑似坏帧 %d" % (len(jump), len(bad)),
        "查看剪辑点前后，检查意外黑白帧、画面断裂与漂移；有意黑场按创作意图判断，不判错", d4)

    # 5 声音
    lu = loud.get("input_i", "未测得")
    tp = loud.get("input_tp", "未测得")
    declared = cl["meta"].get("交付响度", "未声明")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*LUFS", declared)
    target_lu = float(m.group(1)) if m else args.spec_lufs
    try:
        lu_dev = abs(float(lu) - target_lu)
        lu_status = "PASS" if lu_dev <= 1.0 else "WARN"
    except (ValueError, TypeError):
        lu_status = "SKIP"
    d5 = ["整片实测 %s LUFS / %s dBTP / LRA %s（第三遍测量）" %
          (lu, tp, loud.get("input_lra", "未测得")),
          "剪辑单声明响度：%s；目标 %s LUFS" % (declared, target_lu),
          "外部混音记录：%s" % ("有（剪辑单 ## 混音记录）" if cl["mix_record"] else "无/未声明"),
          "未测：接缝底噪、对白清晰度、已声明静默的相对响度"]
    if not loud:
        lu_status = "SKIP"
        d5.append("未测原因：ffmpeg 响度测量失败")
    add(5, "声音", lu_status, "%s LUFS / %s dBTP" % (lu, tp),
        "回听接缝、对白清晰度与已声明静默；整片达标不代表各句都清楚", d5)

    # 6 字幕
    script_norm = norm_text(script)
    sub_miss = []
    for cid, val in cl["subtitles"]:
        clean = re.sub(r"[(（]重点[:：][^)）]*[)）]", "", val).strip()
        if clean and norm_text(clean) and norm_text(clean) not in script_norm:
            sub_miss.append("%s · %s" % (cid, clean))
    d6 = ["剪辑单字幕行 %d 条；逐字比对《剧本.md》未匹配 %d 条" %
          (len(cl["subtitles"]), len(sub_miss)),
          "对比规则：忽略标点与空白（与 edit_tool.py check 一致）；逐字及标点照抄仍须人工核对"]
    d6 += ["未匹配 · " + x for x in sub_miss[:15]]
    if not cl["subtitles"]:
        d6.append("未测原因：剪辑单未登记字幕行（或全部为「无」）")
    st6 = "WARN" if sub_miss else ("SKIP" if not cl["subtitles"] else "PASS")
    add(6, "字幕", st6, "%d 条 / 未匹配 %d" % (len(cl["subtitles"]), len(sub_miss)),
        "检查逐字内容、发声时间、字号、折行、安全区与画内文字避让（需抽帧）", d6)

    # 7 画内文字
    policy = "有" if (ep / "视觉设定.md").is_file() else "缺"
    d7 = ["剪辑单「画面文字」登记 %d 条" % len(cl["on_screen_text"]),
          "《视觉设定.md》文字政策：%s" % policy,
          "主干 N5 硬约束为「画面无任何文字」，画内文字如存在必须是后期烧录且登记在案"]
    d7 += ["登记 · %s · %s" % (c, v[:70]) for c, v in cl["on_screen_text"][:10]]
    add(7, "画内文字", "TODO", "%d 条登记" % len(cl["on_screen_text"]),
        "按剧本与视觉设定的文字政策检查载体、可读性与指定文字", d7)

    # 8 画幅与帧率
    decl = cl["meta"].get("画幅与帧率", "")
    mw = re.search(r"(\d+)\s*[x×]\s*(\d+)", decl)
    mf = re.search(r"(\d+(?:\.\d+)?)\s*fps", decl, re.I)
    spec_w = args.spec_width or (int(mw.group(1)) if mw else 0)
    spec_h = args.spec_height or (int(mw.group(2)) if mw else 0)
    spec_fps = args.spec_fps or (float(mf.group(1)) if mf else 0)
    ok_wh = (not spec_w or spec_w == info["width"]) and (not spec_h or spec_h == info["height"])
    ok_fps = not spec_fps or abs(spec_fps - info["fps"]) <= 0.05
    d8 = ["ffprobe：%dx%d @ %.3ffps，视频 %s / 音频 %s" %
          (info["width"], info["height"], info["fps"], info["video_codec"], info["audio_codec"]),
          "交付规格：%s" % (("%dx%d @ %.2ffps" % (spec_w, spec_h, spec_fps)) if spec_w else "未给定，仅记录实测"),
          "剪辑单声明：%s" % (decl or "未声明")]
    add(8, "画幅与帧率", "PASS" if (ok_wh and ok_fps and info["has_video"]) else "WARN",
        "%dx%d @ %.2ffps" % (info["width"], info["height"], info["fps"]),
        "对照交付规格；竖屏短剧通常为 9:16 / 24 或 30fps", d8)

    # 9 接镜色彩
    color = []
    for cid, fi in cut_points:
        pre = frames[max(0, fi - 5):fi]
        post = frames[fi:fi + 5]
        if not pre or not post:
            continue
        py = sum(f.get("YAVG", 0) for f in pre) / len(pre)
        qy = sum(f.get("YAVG", 0) for f in post) / len(post)
        pbr = sum(f.get("VAVG", 0) - f.get("UAVG", 0) for f in pre) / len(pre)
        qbr = sum(f.get("VAVG", 0) - f.get("UAVG", 0) for f in post) / len(post)
        if abs(qy - py) > 15 or abs(qbr - pbr) > 15:
            color.append("%s · f%d 亮度差 %+.1f / 蓝减红差 %+.1f" % (cid, fi, qy - py, qbr - pbr))
    d9 = ["同场景切点前后各 5 帧平均亮度与「VAVG-UAVG」色度观测（不是成片局部残差）",
          "疑似过冲 %d 处；不要求各场景接近同一均值" % len(color)]
    d9 += ["观测 · " + x for x in color[:15]]
    if not frames:
        d9.append("未测原因：逐帧统计不可用")
    add(9, "接镜色彩", "WARN" if color else ("SKIP" if not frames else "PASS"),
        "疑似过冲 %d 处" % len(color),
        "先看 verify 点名的切点，比较可比区域确认校正没过冲；有意光态变化按创作意图判断", d9)

    # 10 交付包
    media = ep / "制作成果"
    out_dir = film.parent
    package = {
        "成片": film,
        "剪辑单": ep / "剪辑单.md",
        "可继续编辑中间文件": media / "videos",
        "混音中间文件": out_dir / "混音中间文件",
        "混音命令记录": out_dir / "混音命令.txt",
        "两版产物说明": media / "两版产物说明.md",
        "片段清单": media / "片段清单.csv",
        "字幕工程": out_dir / "字幕.srt",
    }
    present = [k for k, p in package.items() if p.exists()]
    missing = [k for k, p in package.items() if not p.exists()]
    d10 = ["齐备：" + ("、".join(present) or "无"),
           "缺：" + ("、".join(missing) or "无"),
           "说明：字幕工程/混音中间文件按实际是否使用判断，未使用不算缺项；" +
           "剪辑单与中间文件应纳入 N13 归档清单"]
    add(10, "交付", "PASS" if film.is_file() and (ep / "剪辑单.md").is_file() else "FAIL",
        "齐备 %d / 缺 %d" % (len(present), len(missing)),
        "给出成片、剪辑单、可继续编辑中间文件与外部混音/字幕工程；说明缺口、取舍与未测原因", d10)
    return checks


# ------------------------------------------------------------------ report

def render_md(args, film, ep, info, checks, gate) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [
        "# N17 成片交付验收报告",
        "",
        "> 生成：`6_剪辑/tools/delivery_qc.py` · %s" % now,
        "> 依据：`tools/drama-edit/references/delivery-verify.md` 9 项 + 交付 1 项。",
        "> **区分实测结果、人工判断和未测项**：`verify` 的技术测量不能替代回听与画面检查；",
        "> 技术观测（边界帧 / 接镜色彩）只指出该看哪里，**不阻断交付**。",
        "",
        "- 成片：`%s`" % film,
        "- 工程：`%s`" % ep,
        "- 实测：%.2fs · %dx%d @ %.2ffps · %s / %s" %
        (info["duration"], info["width"], info["height"], info["fps"],
         info["video_codec"], info["audio_codec"]),
        "- 成片版门禁合并：%s" % ("是（qc_gate 报告）" if gate else "否（--gate-report 未提供）"),
        "",
        "| # | 项 | 状态 | 实测 | 人工 / 未测 |",
        "|---|---|---|---|---|",
    ]
    for c in checks:
        L.append("| %d | %s | **%s** | %s | %s |" %
                 (c["no"], c["name"], c["status"],
                  c["measured"].replace("|", "/"), c["manual"].replace("|", "/")))
    counts = {}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    L += ["", "**汇总**：" + " / ".join("%s %d" % (k, v) for k, v in sorted(
        counts.items(), key=lambda kv: STATUS_ORDER.get(kv[0], 9))), ""]
    for c in checks:
        L += ["---", "", "## %d. %s · %s" % (c["no"], c["name"], c["status"]), "",
              "实测：%s" % c["measured"], "", "人工 / 未测：%s" % c["manual"], ""]
        for d in c["detail"]:
            L.append("- " + d)
        L.append("")
    L += ["---", "", "## 交付结论", "",
          "渲染成功只证明工具完成执行，成片的内容判断需要观看和回听；",
          "正式审查由 `$short-drama-review` 或创作者进行（delivery-verify.md 原文）。",
          "需要补素材、改台词或改分镜时，指出对应镜头与发生时间并交回负责阶段。", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="N17 成片交付验收：对齐 delivery-verify.md 10 项")
    ap.add_argument("--episode", type=Path, required=True, help="剧集目录（剧集/<EP>）")
    ap.add_argument("--film", type=Path, help="成片 mp4；缺省在 <episode>/制作成果/成片/ 下找")
    ap.add_argument("--gate-report", type=Path, help="成片版 qc_gate.py 的 qc_report.json（可选合并）")
    ap.add_argument("--report", type=Path, help="验收报告 .md 输出")
    ap.add_argument("--json", type=Path, help="验收报告 .json 输出")
    ap.add_argument("--spec-width", type=int, default=0)
    ap.add_argument("--spec-height", type=int, default=0)
    ap.add_argument("--spec-fps", type=float, default=0.0)
    ap.add_argument("--spec-lufs", type=float, default=-16.0)
    ap.add_argument("--no-frames", action="store_true", help="跳过逐帧统计（快速模式）")
    args = ap.parse_args()

    ep = args.episode.resolve()
    if not ep.is_dir():
        raise SystemExit("[错误] 剧集目录不存在：%s" % ep)
    film = args.film
    if film is None:
        cands = sorted((ep / "制作成果" / "成片").glob("*.mp4")) if (ep / "制作成果" / "成片").is_dir() else []
        if not cands:
            raise SystemExit("[错误] 未找到成片，请用 --film 指定")
        film = cands[0]
    film = film.resolve()
    if not film.is_file():
        raise SystemExit("[错误] 成片不存在：%s" % film)
    args.report = (args.report or film.parent / "验收报告.md").resolve()
    args.json = (args.json or film.parent / "验收报告.json").resolve()
    args.report.parent.mkdir(parents=True, exist_ok=True)

    cl = parse_cut_list(ep / "剪辑单.md")
    info = probe(film)
    gate = {}
    if args.gate_report and args.gate_report.is_file():
        try:
            gate = json.loads(args.gate_report.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print("[警告] qc_gate 报告读取失败，忽略：%s" % e, file=sys.stderr)
    if not info["has_audio"]:
        print("[警告] 成片无音轨，声音项按未测处理", file=sys.stderr)
    loud = measure_loudness(film, args.spec_lufs) if info["has_audio"] else {}
    frames = [] if args.no_frames else frame_stats(film)

    print("N17 交付验收 · %s" % film)
    print("  %.2fs · %dx%d @ %.2ffps · 逐帧 %d · 响度 %s" %
          (info["duration"], info["width"], info["height"], info["fps"],
           len(frames), loud.get("input_i", "未测得")))
    checks = check_all(args, film, ep, cl, info, frames, loud, gate)
    md = render_md(args, film, ep, info, checks, gate)
    args.report.write_text(md, encoding="utf-8")
    payload = {"tool": "delivery_qc", "generated": datetime.now().isoformat(timespec="seconds"),
               "film": str(film), "episode": str(ep), "probe": info,
               "loudness": loud, "frames_analyzed": len(frames),
               "gate_merged": bool(gate), "checks": checks}
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in checks:
        print("  %2d %-8s %s | %s" % (c["no"], c["status"], c["name"], c["measured"]))
    print("  报告：%s" % args.report)
    print("  JSON：%s" % args.json)
    return 1 if any(c["status"] == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
