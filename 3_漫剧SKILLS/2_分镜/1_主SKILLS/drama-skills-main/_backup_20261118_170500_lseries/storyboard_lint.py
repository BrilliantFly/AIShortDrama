#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分镜可渲染性 lint：把 `voicetrack-renderability.md` 与 `blocking-playbooks.md`
的规则变成可执行检查。

检查的是「这一镜交给单轨生成端能不能出声」+「人物互动站位与视角有没有机位语言」，
不是文学质量。

用法
  python storyboard_lint.py 分镜.md
  python storyboard_lint.py 分镜.md --fps 24 --ctx 22
  python storyboard_lint.py 分镜.md --strict      # 缺新字段也算失败（新项目用）
  python storyboard_lint.py 分镜.md --csv 分镜.csv # 同时导出机器可读表

退出码：0 全通过（允许 WARN）／1 有 FAIL／2 路径或解析错误
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("storyboard_lint.py requires Python 3.9 or newer")

SHOT_RE = re.compile(r"^##\s+(SHOT-[0-9A-Za-z\-]+)\s*[·:：]?\s*(.*)$", re.M)
# A2 修复：字段可加粗也可不加粗（references 示例为不加粗的「- 镜型：SOLO」）
FIELD_RE = re.compile(r"^-\s+(?:\*\*)?(.+?)(?:\*\*)?\s*[：:]\s*(.*)$", re.M)
QUOTE_RE = re.compile(r"「([^」]{1,60})」")
# A9 修复：台词原文除「」外，也认 <d>…</d> 与直角引号「』」等常见标记，
# 避免这些写法被当成无台词而跳过镜型/音色/DUO 全部检查。
TAG_QUOTE_RE = re.compile(r"<d>([^<]{1,60})</d>")
DECLARED_RE = re.compile(r"对白\s*([一二三四五六七八九十两\d]+)\s*句(?:以上)?")
CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10}

# 说话人识别：优先认 [VO]/[OS]<名字>：台词；其次认「名字 + 说话动词 + 「台词」」
SPEAK_VERBS = ("问路", "问道", "追问", "反问", "低声道", "低声", "接话", "接口", "打趣", "嘟囔",
               "问", "答", "说", "道", "喊", "喝", "叫", "笑", "念", "骂")
_VERB_ALT = "|".join(sorted(SPEAK_VERBS, key=len, reverse=True))
SPEAKER_RE = re.compile(r"([\u4e00-\u9fa5]{2,4})(?:" + _VERB_ALT + r")$")
# A7 修复：[VO]/[OS] 画外音说话人，如 [VO]令狐冲：… / [OS]向问天
VO_SPEAKER_RE = re.compile(r"\[(?:VO|OS)\]\s*([\u4e00-\u9fa5]{2,4})\s*[：:]")
# A4 修复：12 字是文档规划门槛（≥12 须拆/单独成镜），15 字是单镜装不下的硬上限
ADVISE_CHARS = 12       # ≥12 字提示拆/单独成镜（WARN，对齐 voicetrack-renderability.md §八）
MAX_CHARS = 15          # >15 字硬上限（FAIL，保留原门禁不动）
# A6 修复：文档默认「一句一镜最稳」，2 句是单轨能容的硬上限
ADVISE_LINES = 1        # >1 句提示拆分（WARN）
MAX_LINES = 2           # >2 句硬上限（FAIL，保留原门禁不动）

# ---- 打斗镜判据（见 references/action-choreography.md）
FIGHT_STRONG = ("出招", "交手", "对打", "对招", "招名", "兵刃相接", "格挡", "拆解",
                "反制", "拆招", "接刃", "过招", "刀剑相")
WEAPON_WORDS = ("剑尖", "剑锋", "剑身", "剑刃", "剑势", "刀尖", "刀锋", "刀背",
                "刀刃", "刀身", "刀势", "兵器")
STRIKE_VERBS = ("点", "压", "挑", "斩", "劈", "扫", "撩", "刺", "撞", "崩", "格",
                "架", "削", "切", "戳", "翻", "绕", "接")
DUEL_SYNC = ("同一时刻", "与此同时", "同时", "同一拍", "攻守", "反制", "拆解", "格开", "压住")
FACING_WORDS = ("面对面", "相对而立", "正面相对", "对峙", "面对", "facing", "face each other")
# H1 修复：团战关键帧正文多为英文，左右站位与距离需双语识别
SIDE_WORDS = ("画面左", "画面右", "左侧", "右侧",
              "left side", "right side", "screen left", "screen right",
              "left third", "right third", "frame left", "frame right")
# A8 修复：打斗「空间三要素」之距离/步数（详见 action-choreography.md）
DISTANCE_WORDS = ("步", "尺", "米", "臂距", "身位")
DISTANCE_RE = re.compile(r"(?:相距|距离|相隔)\s*[约近满\d一二三四五六七八九十两]+?\s*(?:步|尺|米|臂|身位)")
DISTANCE_RE_EN = re.compile(r"(?:across|within|about|some|only)\s+(?:one|two|three|four|five|six|half|ten|\d+)\s+(?:pace|paces|step|steps|feet|meters)|\b(?:one|two|three|four|five|six|ten|\d+)\s+paces?\b(?:\s+apart|\s+away)?")
DISTANCE_ANY = (DISTANCE_RE, DISTANCE_RE_EN)
# K1 场级节奏：景别档识别（中英双语，按优先级顺序命中即止；blocking-playbooks §5d）
SIZE_TIERS = (
    ("特写/插入", re.compile(r"macro insert|macro|insert shot|extreme close|特写|插入镜头", re.I)),
    ("近景", re.compile(r"close[- ]?up|closeup|tight (?:two|single)|近景", re.I)),
    ("中景", re.compile(r"medium[- ]wide|medium (?:shot|two|close)|medium shot|中景", re.I)),
    ("大景", re.compile(r"extreme wide|wide (?:shot|establishing|two|panorama)|establishing|panorama|aerial|大全景|远景|全景", re.I)),
)
SIZE_RUN_LIMIT = 4     # 同场连续同档上限
MAX_REF_IMAGES = 9
FIGHT_MIN_REFS = 4      # 起始帧 + A 身份 + B 身份 + 场景
# 槽位起点：REF-xxx（顺序：n）· 或 PLAN-xxx（顺序：n）·
# H1 附带修复：槽位正则此前只认全角括号/冒号，半角写法（所有验证稿的实际用法）
# 全部解析为空——交接帧、IMG 起始帧检查一直在空转。现兼容全/半角。
SLOT_START_RE = re.compile(r"(?:REF|PLAN)-[A-Za-z0-9\-]+[（(]顺序[：:]\d+[）)]·")
SLOT_USE_RE = re.compile(r"用途[：:]([^；;）)]+)")
IMG_NAME_RE = re.compile(r"([A-Za-z0-9\-_]+\.(?:png|jpg|jpeg|webp))")
# 路径正则：允许中文目录与「·」，用于取出带中文的图名（IMG_NAME_RE 只认 ASCII）
PATH_RE = re.compile(r"([^\s《》（）；;「」]+\.(?:png|jpg|jpeg|webp))")

# ---- 站位与视角检查（见 references/blocking-playbooks.md §1b）
# 「场景站位」块标题：## 场景站位 · EP001-SC001 · 旧走廊
# 场次 ID 兼容自拟编号（S01-SC01、SC01、EC001 等），不写死 EP 前缀——
# 写死会让交接帧/场景站位/正反打三项跨镜核对在非 EP 编号下静默失效。
SCENE_RE = re.compile(r"([A-Za-z]{1,4}\d+(?:-SC\d+)?)")
BLOCKING_RE = re.compile(r"^##\s+场景站位\s*·\s*([A-Za-z]{1,4}\d+(?:-SC\d+)?)", re.M)
# 机位翻译词汇：把抽象关系翻成本镜机位下看得见的样子（谁前景谁后景、隔着什么、画面哪侧）。
# blocking-playbooks §1b 实测：只写抽象关系，Seedance 2.0 九次把两人放到桌子同侧；
# 写成机位语言后三次全对。中文/英文各一套（关键帧正文两种语言都常见）。
CAMERA_WORDS_CN = ("机位", "前景", "后景", "背对镜头", "面对镜头", "面向镜头", "画面左",
                   "画面右", "过肩", "肩后", "背对", "隔着", "占画", "侧脸")
CAMERA_WORDS_EN = ("camera", "foreground", "background", "over-the-shoulder",
                   "over the shoulder", "facing the camera", "back to camera",
                   "back turned", "left side", "right side", "frame left",
                   "frame right", "behind", "between")
# OTS 镜正文必须能看出「谁的肩在前景」——缺了会生成正面双人镜头（视角不对）
OTS_WORDS_CN = ("过肩", "肩后", "背影", "背对镜头", "背对")
OTS_WORDS_EN = ("over-the-shoulder", "over the shoulder", "shoulder",
                "back to camera", "back turned")
# H 系列修复后补的「肩归属」检查：只出现「过肩/over-the-shoulder」这个术语
# 不算写清归属（谁的肩？）——归属=前景肩属于谁、或明确背对镜头的写法
OTS_ATTRIB_CN_RE = re.compile(r"前景肩|肩后|[一-龥]{1,5}的肩|背影|背对镜头")
OTS_ATTRIB_EN_RE = re.compile(
    r"(?:over|past|across|beyond)\s+(?:his|her|their|its|the)\s+shoulder"
    r"|shoulder\s+(?:in\s+the\s+)?(?:foreground|left|right)"
    r"|foreground\s+shoulder|back\s+to\s+camera|back\s+turned"
    r"|camera\s+behind\b|(?:his|her|their|its)\s+shoulder\b"
    r"|\b(?:shoulder|back)\b[^.;\n]{0,40}\b(?:fill|fills|in|occupy|occupies)\s+"
    r"the\s+(?:left|right)\s+foreground", re.I)
# 画外视线方向（正反打互补核对用）：中文「看向画左」/ 英文 "looking toward screen left"
# 英文补 "looks off toward the left" 类自然写法（off=画外信号），此前只认 screen left/right
GAZE_CN_RE = re.compile(r"看向(?:画外|画)(左|右)")
GAZE_EN_RE = re.compile(
    r"(?:looking|gazing|staring|turning)\s+(?:toward\s+|to\s+)?screen\s+(left|right)"
    r"|(?:looks?|looking|gazes?|gazing|stares?|staring|peers?|peering)\s+off\s+"
    r"(?:toward\s+|to\s+|at\s+)?(?:the\s+)?(left|right)",
    re.I)
GAZE_SIDE_MAP = {"left": "左", "right": "右"}
# 画外视线没写看向谁（❌「看向画右」后无目标名）
GAZE_NO_TARGET_CN_RE = re.compile(r"看向(?:画外|画)(?:左|右)侧?(?=[，。；、！？]|$)")
GAZE_NO_TARGET_EN_RE = re.compile(
    r"(?:looking|gazing|staring)\s+(?:toward\s+|to\s+)?screen\s+(?:left|right)(?=[.。;；!！?？]|$)"
    r"|(?:looks?|looking|gazes?|gazing|stares?|staring|peers?|peering)\s+off\s+"
    r"(?:toward\s+|to\s+|at\s+)?(?:the\s+)?(?:left|right)"
    r"(?:\s+(?:side|edge)(?:\s+of\s+(?:the\s+)?frame)?)?(?=[.。;；!！?？]|$)", re.I)


def gaze_side(body: str) -> str:
    """取本镜关键帧正文的画外视线方向（左/右），双语识别；没有返回空。"""
    m = GAZE_CN_RE.search(body)
    if m:
        return m.group(1)
    m = GAZE_EN_RE.search(body)
    if m:
        side = m.group(1) or m.group(2)   # 两个分支的捕获组编号不同
        return GAZE_SIDE_MAP.get((side or "").lower(), "")
    return ""


def align17k5(n: int) -> int:
    if n <= 5:
        return 5
    return ((n - 5 + 16) // 17) * 17 + 5


def predict_export(length: int, ctx: int, first: bool) -> int:
    if first or ctx <= 0:
        return length
    return align17k5(length + ctx) - ctx


def split_shots(text: str) -> list[tuple[str, str, str]]:
    marks = list(SHOT_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.start():end]))
    return out


def fields_of(block: str) -> dict[str, str]:
    d: dict[str, str] = {}
    # 只取镜头字段区（### 之前），避免把冻结关键帧正文里的短句当字段
    head = block.split("\n###", 1)[0]
    for m in FIELD_RE.finditer(head):
        d[m.group(1).strip()] = m.group(2).strip()
    return d


def pick(d: dict[str, str], *names: str) -> str | None:
    for n in names:
        for k, v in d.items():
            if n in k:
                return v
    return None


def guess_speakers(line: str) -> list[str]:
    """从「声音」字段里猜说话人。

    A7 修复：除原「名字 + 说话动词 + 「台词」」句式外，也认
    `[VO]名字：` / `[OS]名字：` / `[VO]名字「台词」` 等画外音写法，
    否则画外台词会被当成无说话人，多说话人 DUO 违规漏检。
    """
    out = []
    # 画外音说话人：[VO]/[OS] 显式标注，优先收集
    for m in VO_SPEAKER_RE.finditer(line):
        out.append(m.group(1))
    # 显式说话人后面的「台词」不再重复计入同一人
    quoted = []
    for m in QUOTE_RE.finditer(line):
        head = line[max(0, m.start() - 16):m.start()]
        head = re.sub(r"[，,、；;：:（(）)「」\s\[\]VOOS]+$", "", head)
        hit = SPEAKER_RE.search(head)
        if hit:
            quoted.append(hit.group(1))
    for name in quoted:
        if name not in out:
            out.append(name)
    return out


def parse_seconds(v: str | None) -> float | None:
    if not v:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:s|秒)", v)
    return float(m.group(1)) if m else None


def declared_lines(sound: str) -> int:
    """「对白六句」这类只报数量、不写原文的写法，也要算成有台词。"""
    total = 0
    for m in DECLARED_RE.finditer(sound):
        raw = m.group(1)
        total += CN_NUM.get(raw, int(raw) if raw.isdigit() else 0)
    return total


def parse_ref_slots(refs: str) -> list[tuple[str, str]]:
    """把「输入参考图」拆成 (用途, 文件名)。没有文件名（PLAN 写条目名）时返回空文件名。"""
    starts = [m.start() for m in SLOT_START_RE.finditer(refs)]
    if not starts:
        return []
    out: list[tuple[str, str]] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(refs)
        chunk = refs[s:e]
        use = SLOT_USE_RE.search(chunk)
        # 取路径最后一段作文件名：中文名（SHOT-008·断流_END.png）IMG_NAME_RE 抓不到
        path = PATH_RE.search(chunk)
        name = path.group(1).rsplit("/", 1)[-1] if path else ""
        out.append(((use.group(1).strip() if use else ""), name))
    return out


def is_fight_shot(action: str, block: str) -> bool:
    """判定打斗镜：强信号词命中，或「兵刃部位词 + 击打动词」同时出现。

    只提「背上背着一把剑」不算打斗——必须有兵刃参与动作，否则问路、按背这类镜会被误报。
    """
    text = (action or "") + block.split("\n###", 1)[0]
    if any(w in text for w in FIGHT_STRONG):
        return True
    return any(w in text for w in WEAPON_WORDS) and any(v in text for v in STRIKE_VERBS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--ctx", type=int, default=22, help="continuityOverlapFrames；关闭连续链时传 0")
    ap.add_argument("--strict", action="store_true", help="缺 镜型/音色/验收基线 也算失败")
    ap.add_argument("--csv")
    a = ap.parse_args()

    if not os.path.exists(a.storyboard):
        print(f"找不到 {a.storyboard}")
        return 2
    text = io.open(a.storyboard, encoding="utf-8").read()
    shots = split_shots(text)
    if not shots:
        print("没解析到 `## SHOT-xxx · 名称` 镜头块")
        return 2

    fails, warns, rows = [], [], []
    handoffs: list[dict] = []   # 每镜的交接槽位，循环后逐缝核对
    seconds_only: list[str] = []
    total_design = total_actual = 0

    for idx, (sid, title, block) in enumerate(shots):
        f = fields_of(block)
        sound = pick(f, "声音", "音效") or ""
        kind = (pick(f, "镜型") or "").upper()
        frames_field = pick(f, "export_frames", "帧数")
        dur = parse_seconds(pick(f, "时长", "镜长"))
        voice = pick(f, "音色")
        base = pick(f, "验收基线")
        refs = pick(f, "输入参考图", "参考图") or ""

        # A9：合并「」与 <d> 两种台词标记，避免 <d>…</d> 写法整镜漏检
        quotes = QUOTE_RE.findall(sound) + TAG_QUOTE_RE.findall(sound)
        declared = declared_lines(sound)
        n_lines = max(len(quotes), declared)
        # A9：声音字段含引号/台词样文本却一条都没识别到 → 提示可能用了未支持的标记
        if not n_lines and re.search(r"[「」<>]|对白", sound):
            warns.append(f"{sid} 声音字段含台词样文本但未识别到台词原文，"
                         f"请确认用「」或 <d></d> 标注（否则镜型/音色/DUO 检查会跳过）")
        speakers = guess_speakers(sound)
        uniq = []
        for s in speakers:
            if s not in uniq:
                uniq.append(s)

        # 1 时长 / 帧数
        # A1：区分「写了合法帧数」与「只写秒数」。秒是推导量，只写秒数的镜头
        #     按文档只提示补 export_frames，不拿推导帧去套 17 网格直接 FAIL。
        seconds_only_here = False
        if frames_field:
            m = re.search(r"\d+", frames_field)
            length = int(m.group()) if m else 0
        elif dur is not None:
            length = int(round(dur * a.fps))
            seconds_only.append(f"{sid}({dur:g}s→{length})")
            seconds_only_here = True
        else:
            length = 0
            if n_lines:
                warns.append(f"{sid} 有台词但没有可得出的镜长")
        if length:
            # 首段没有前文语境，不受 ctx 网格约束
            if not (idx == 0 and a.ctx > 0) and length % 17 != (5 - a.ctx) % 17:
                exp = predict_export(length, a.ctx, idx == 0)
                msg = (f"{sid} length={length} 与 ctx={a.ctx} 不匹配，导出会变成 {exp}"
                       f"（{exp - length:+d} 帧）")
                # A1：只写秒数 → WARN（提示补合法帧数）；写死帧数 → FAIL
                if seconds_only_here:
                    warns.append(msg + "；本镜只写了秒数，请改用 export_frames 写合法帧数")
                else:
                    (fails if a.strict else warns).append(msg)
            total_design += length
            total_actual += predict_export(length, a.ctx, idx == 0)

        # 2 镜型与台词
        if n_lines:
            if not kind:
                (fails if a.strict else warns).append(
                    f"{sid} 有台词但未标 `镜型`（SOLO/OTS），下游无法判是否可渲染")
            elif kind == "DUO":
                fails.append(f"{sid} 镜型=DUO 却带 {n_lines} 句台词 —— DUO 不得有台词，必须拆镜")
            elif kind not in ("SOLO", "OTS"):
                fails.append(f"{sid} 镜型 `{kind}` 不是 SOLO/OTS/DUO")
            # A6 分级：>1 句提示拆分（WARN），>2 句硬上限（FAIL）
            if n_lines > MAX_LINES:
                fails.append(f"{sid} 一镜 {n_lines} 句台词（硬上限 {MAX_LINES}）")
            elif n_lines > ADVISE_LINES:
                warns.append(f"{sid} 一镜 {n_lines} 句台词——文档默认「一句一镜最稳」，"
                             f"两句同镜需确认单轨能分别对口型")
            if len(uniq) > 1:
                fails.append(f"{sid} 同镜出现 {len(uniq)} 个说话人（{'、'.join(uniq)}）—— 单轨只能一条音色")
            if declared and not quotes:
                warns.append(f"{sid} 只写「对白{declared}句」没写台词原文，出片后无从比对")
            for q in quotes:
                # A4 分级：≥12 字提示拆/单独成镜（WARN），>15 字硬上限（FAIL）
                if len(q) > MAX_CHARS:
                    fails.append(f"{sid} 台词 {len(q)} 字超过硬上限 {MAX_CHARS}：「{q[:18]}…」")
                elif len(q) >= ADVISE_CHARS:
                    warns.append(f"{sid} 台词 {len(q)} 字（≥{ADVISE_CHARS}），"
                                 f"按文档须单独成镜或按语义拆开：「{q[:18]}…」")

        # 3 音色与验收基线
        if n_lines:
            if not voice:
                (fails if a.strict else warns).append(f"{sid} 有台词但没写 `音色`")
            if not base:
                (fails if a.strict else warns).append(f"{sid} 有台词但没写 `验收基线`（预期台词/最短发声秒/最长静音秒）")

        # 4 参考图（按槽位用途判，不再一刀切禁 IMG）
        action = pick(f, "唯一动作", "动作") or ""
        duel = pick(f, "对招")
        fight = is_fight_shot(action, block)
        slots = parse_ref_slots(refs)
        src = pick(f, "来源") or ""
        m_scene = SCENE_RE.search(src)
        scene = m_scene.group(1) if m_scene else ""
        if src and not scene:
            warns.append(f"{sid} `来源`（{src}）解析不出场次 ID——交接帧、场景站位、"
                         f"正反打互补三项跨镜核对对本镜跳过；请按 EP001-SC001 这类"
                         f"「编号-场次」格式书写（S01-SC01 等自拟编号也可）")
        visual_basis = pick(f, "视觉依据") or ""
        # 关键帧正文（### 之后的部分）：站位/视角检查的对象
        body = block.split("\n###", 1)[1] if "\n###" in block else ""
        body_low = body.lower()
        # H1：英文词表匹配需大小写不敏感——正文里 "Facing"/"Left side" 也要命中
        body_ci = body + "\n" + body_low
        handoffs.append({
            "sid": sid,
            "scene": scene,
            "fight": fight,
            "start": next((n for u, n in slots if u == "起始帧"), ""),
            "end": next((n for u, n in slots if u == "结束帧"), ""),
            # H1 附带修复：分镜阶段结束帧按 shot-handoff.md 应写 PLAN-（路径待生成，
            # 文件名解析为空）——这是合法的交接意图声明，「缺交接」提醒不应触发；
            # 同图硬核对只对已落地文件名（REF-）生效，顺延逻辑不变
            "has_end": any(u == "结束帧" for u, _ in slots),
            # K1 场级节奏：本镜景别档（关键帧正文识别，中英双语）
            "size": next((t for t, rx in SIZE_TIERS if rx.search(body)), ""),
            # 正反打互补核对用：本镜关键帧正文里「看向画左/画右」的方向
            "gaze": gaze_side(body),
        })
        n_refs = len(re.findall(r"\.(?:png|jpg|jpeg|webp)", refs))
        if not refs:
            warns.append(f"{sid} 没有 `输入参考图`（无锚点镜，一致性只能靠文本）")
        else:
            for use, name in slots:
                if use == "起始帧" and name.upper().startswith("IMG-"):
                    fails.append(f"{sid} 用 IMG 条目（{name}）当 `用途：起始帧`——"
                                 f"多格排版板会被照抄成分屏，应换成该镜冻结关键帧起始帧")
            if n_refs > MAX_REF_IMAGES:
                fails.append(f"{sid} 挂 {n_refs} 张参考图，超过执行端上限 {MAX_REF_IMAGES}")

        # 5 打斗镜：双主语、面对面、参考图配给
        # H1 修复：三要素（朝向/左右站位/距离）的检查范围 = 「唯一动作」字段 OR
        # 冻结关键帧正文。团战镜字段区往往只写动作链，站位/距离写在正文里；
        # 只扫字段会让已写清的镜被大量误报（黑木崖压测：12 镜 15 条同类 WARN）。
        # 画外在场人数提前到此处计算（H6 群像豁免要用）
        n_persons = visual_basis.count("人物「") - len(
            re.findall(r"画外[：:]人物「", visual_basis))
        if n_persons < 0:
            n_persons = 0
        if fight:
            if not duel:
                (fails if a.strict else warns).append(
                    f"{sid} 判为打斗镜但没有 `对招` 列（攻=… → 守=… ｜结果=…），无法确认双主语")
            if not any(w in action for w in DUEL_SYNC):
                warns.append(f"{sid} 打斗镜的唯一动作没有攻守同步标记"
                             f"（「同一时刻」/「与此同时」/「反制」）——生成端会做成单人动作")
            if not any(w in action for w in FACING_WORDS) and \
               not any(w in body_ci for w in FACING_WORDS):
                warns.append(f"{sid} 打斗镜没写朝向（「面对面」「面对镜头」或正文双人相向）——易出并肩站立")
            if not any(w in action for w in SIDE_WORDS) and \
               not any(w in body_ci for w in SIDE_WORDS):
                warns.append(f"{sid} 打斗镜没写左右站位（谁在画面哪侧）——易出站位乱跳")
            # A8：空间三要素之「距离/步数」，文档必写、原脚本漏检
            if not any(rx.search(action) or rx.search(body_ci) for rx in DISTANCE_ANY):
                warns.append(f"{sid} 打斗镜没写距离（如「相距三步」「相隔一臂」「three paces」，字段或正文任一即可）——"
                             f"空间三要素缺一，易出两人并肩或站位乱跳")
            # H6 群像豁免：视觉依据没点名任何具名人物（纯群演镜）不适用
            # 「双方身份板」配给——无名人物无身份板可挂，只按普通锚点检查。
            is_crowd_fight = n_persons == 0 or "群演" in visual_basis
            if n_refs and n_refs < FIGHT_MIN_REFS and not is_crowd_fight:
                (fails if a.strict else warns).append(
                    f"{sid} 打斗镜只挂 {n_refs} 张参考图（建议 ≥{FIGHT_MIN_REFS}："
                    f"起始帧 + 双方身份板 + 场景板；纯群演镜免身份板）")

        # 5b 人物互动站位与视角（见 references/blocking-playbooks.md §1b）
        #     n_persons 已在打斗检查块之前计算（H6 群像豁免共用）
        if n_persons >= 2 and body:
            # 5b-1 占位：两人在场的关键帧正文必须有机位语言，只写抽象关系会被放到同一侧
            has_camera = (any(w in body for w in CAMERA_WORDS_CN)
                          or any(w in body_low for w in CAMERA_WORDS_EN))
            if not has_camera:
                warns.append(f"{sid} 关键帧正文写了两人同框但无机位语言"
                             f"（机位/前景后景/画面左右/隔着什么/背对镜头）——"
                             f"只写「隔桌相对」「facing each other」这类抽象关系时，"
                             f"生成端常把两人放到同一侧（blocking-playbooks §1b：实测九次同侧）")
            # 5b-2 镜型一致性：画面两人、一人发声应为 OTS；SOLO 是单人镜
            if kind == "SOLO" and n_lines:
                warns.append(f"{sid} 视觉依据列了 {n_persons} 个人物但镜型=SOLO——"
                             f"两人同框且只有一人发声应标 OTS，口型才落到说话人脸上"
                             f"（voicetrack-renderability §二）")
        if kind == "OTS" and body:
            has_ots = (any(w in body for w in OTS_WORDS_CN)
                       or any(w in body_low for w in OTS_WORDS_EN))
            # 肩归属：术语词（过肩/over-the-shoulder）不算归属——必须能读出
            # 「谁的肩/前景肩/背影/背对镜头」，否则生成端拍出正面双人镜头
            has_attrib = bool(OTS_ATTRIB_CN_RE.search(body)
                              or OTS_ATTRIB_EN_RE.search(body))
            if not has_ots or not has_attrib:
                if not has_ots:
                    # 5b-3 视角：OTS 必须能看出「谁的肩在前景」
                    warns.append(f"{sid} 镜型=OTS 但关键帧正文没写「过肩/前景肩/背对镜头」——"
                                 f"缺前景肩归属会生成正面双人镜头，视角与镜型不符")
                else:
                    warns.append(f"{sid} 镜型=OTS 只写了过肩术语，没写肩归属（谁的肩在前景？）——"
                                 f"应写「令狐冲的肩在前景」/「over her shoulder」/「背影」，"
                                 f"否则生成端拍出正面双人镜头，视角与镜型不符")
        if body and (GAZE_NO_TARGET_CN_RE.search(body) or GAZE_NO_TARGET_EN_RE.search(body)):
            # 5b-4 画外视线没写看向谁（❌「看向画右」——看向谁？）
            warns.append(f"{sid} 画外视线只写了方向没写看向谁——正反打靠两镜视线"
                         f"互补才接得上，应写「看向画外左侧门口的赵经理」这类带目标的写法")

        rows.append({
            "镜号": sid, "名称": title, "镜型": kind or "", "帧数": length or "",
            "台词数": n_lines, "说话人": "/".join(uniq), "音色": voice or "",
            "参考图": n_refs, "结束帧": "有" if any(u == "结束帧" for u, _ in slots) else "",
            "打斗": "是" if fight else "", "对招": "有" if duel else "",
        })

    # 6 镜间交接帧（见 references/shot-handoff.md）
    #    同场景相邻镜：前一镜交出的结束帧，必须就是后一镜的起始帧（同一路径），换图等于没接。
    for prev, nxt in zip(handoffs, handoffs[1:]):
        same_scene = bool(prev["scene"]) and prev["scene"] == nxt["scene"]
        if prev["end"]:
            if not nxt["start"]:
                fails.append(f"{prev['sid']} 交了结束帧（{prev['end']}），但 {nxt['sid']} 没有 `用途：起始帧`"
                             f"——下一镜会从自己的图起手，动作接不住")
            elif nxt["start"] != prev["end"]:
                fails.append(f"{prev['sid']}→{nxt['sid']} 交接帧不同图："
                             f"结束帧 {prev['end']} vs 起始帧 {nxt['start']}——下游跟图不跟字，等于没接")
        elif same_scene and prev["fight"] and not prev["has_end"]:
            (fails if a.strict else warns).append(
                f"{prev['sid']}→{nxt['sid']} 同场连续打斗缺交接：{prev['sid']} 没有 `用途：结束帧`，"
                f"{nxt['sid']} 的起始帧只能另出一张——两镜各自起手，动作接不住")

    # 7 站位与视角的跨镜核对（见 references/blocking-playbooks.md §1b）
    # 7a 多镜场次缺「场景站位」块：每镜只能各自猜站位，换镜就乱跳
    scene_counts: dict[str, int] = {}
    for h in handoffs:
        if h["scene"]:
            scene_counts[h["scene"]] = scene_counts.get(h["scene"], 0) + 1
    blocking_scenes = set(BLOCKING_RE.findall(text))
    for scene, n in scene_counts.items():
        if n >= 2 and scene not in blocking_scenes:
            warns.append(f"场次 {scene} 拍了 {n} 镜但没有「## 场景站位 · {scene}」块——"
                         f"每镜只能各自猜站位，正反打与越轴无从核对（blocking-playbooks §1b）")
    # 7b 正反打屏幕方向互补：相邻同场两镜「看向画左/画右」同向 → 读成看同一画外第三者
    for prev, nxt in zip(handoffs, handoffs[1:]):
        if (prev["scene"] and prev["scene"] == nxt["scene"]
                and prev["gaze"] and prev["gaze"] == nxt["gaze"]):
            warns.append(f"{prev['sid']}→{nxt['sid']} 两镜视线都看向画{prev['gaze']}——"
                         f"正反打屏幕方向应互补（一边向左、一边向右），"
                         f"同向会被读成两人在看同一个画外第三者（blocking-playbooks §正反打）")

    # 7c K1 场级节奏：同场连续同景别档 ≥4 镜 → 节奏失效（blocking-playbooks §5d）
    #     只统计正文能识别出景别档的镜；跨场清零。武打镜另有全集聚合配额，两者并行。
    run_scene, run_tier, run_len = "", "", 0
    for h in handoffs + [{"scene": "", "size": ""}]:   # 哨兵触发末段结算
        if h["scene"] == run_scene and h["size"] and h["size"] == run_tier:
            run_len += 1
        else:
            if run_len >= SIZE_RUN_LIMIT:
                warns.append(f"场次 {run_scene} 连续 {run_len} 镜同落「{run_tier}」档——"
                             f"节奏平均用力，高潮前缺那一拍静（blocking-playbooks §5d 动静交替）")
            run_scene, run_tier, run_len = h["scene"], h["size"], (1 if h["size"] else 0)

    if seconds_only:
        warns.insert(0, f"{len(seconds_only)} 镜只写秒数未写 `export_frames`："
                        + "、".join(seconds_only[:8]) + ("…" if len(seconds_only) > 8 else ""))

    print(f"镜头数={len(shots)}  fps={a.fps}  ctx={a.ctx}  有台词镜={sum(1 for r in rows if r['台词数'])}"
          f"  打斗镜={sum(1 for r in rows if r['打斗'])}"
          f"  交接缝={sum(1 for p in handoffs if p['end'])}"
          f"  多镜场次={sum(1 for n in scene_counts.values() if n >= 2)}"
          f"  缺站位块={sum(1 for s, n in scene_counts.items() if n >= 2 and s not in blocking_scenes)}")
    if total_design:
        print(f"设计 {total_design} 帧 / {total_design / a.fps:.2f}s   "
              f"预测成片 {total_actual} 帧 / {total_actual / a.fps:.2f}s  "
              f"漂移 {total_actual - total_design:+d} 帧")
    if a.csv:
        with io.open(a.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"分镜表: {a.csv}")

    for m in warns[:20]:
        print("WARN:", m)
    if len(warns) > 20:
        print(f"WARN: …还有 {len(warns) - 20} 条同类提示")
    if fails:
        for m in fails[:25]:
            print("FAIL:", m)
        if len(fails) > 25:
            print(f"FAIL: …还有 {len(fails) - 25} 条")
        print(f"\n{len(fails)} 项不通过")
        return 1
    print("\nPASS — 镜型、台词体量、帧长、参考图都对得上")
    return 0


if __name__ == "__main__":
    sys.exit(main())
