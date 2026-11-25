#!/usr/bin/env python3
"""质量链统一编排器：把分散的门禁脚本按阶段串成一条可执行链。

设计目标（用户 2026-11-25 要求）：
1. 按步骤执行、不遗漏 —— 每个阶段要过哪些门禁，集中在这一份清单里；
2. 可扩展 —— 加一道门禁 = 往 GATES 里加一条 dict，不用改执行逻辑；
3. 跨机 —— 不硬编码盘符，路径全部由 --project-root / --repo 推导。

用法：
  # 列出全部编排项（不执行）
  python run_quality_chain.py --list

  # 按阶段跑（n2 / csv / delivery / all）
  python run_quality_chain.py --stage n2 \
      --project-root <剧集目录> --expect-shots 5 --drama-root <drama-skill 脚本目录>

  python run_quality_chain.py --stage csv \
      --project-root <项目根> --csv shotlist.csv --input-root "$COMFYUI_ROOT/input"

  python run_quality_chain.py --stage delivery \
      --seg 'out/seg_*.mp4' --archive out/整片.mp4 --expect 5 --width 1344 --height 768

阶段与节点对应：
  n2       -> N2  交 N3 前（文本层：分镜诊断 / 提示词 / H3 lint）
  csv      -> N8  装配前（CSV 层：镜号 / 拆段 / 资产体检）
  delivery -> N17 交付前（媒体层：分辨率 / 段数 / 尾段误交）
  all      -> 依次跑全部（缺参数的门禁自动 SKIP 并说明，不算 FAIL）

注意：Skill 调用（导演运镜 / 跨层锁 / 成片审片）是知识型、无 CLI，
不能塞进本脚本；它们在手册 2.x「质量链统一编排」表里按节点手工调用，
本脚本只负责其中的「脚本门禁」行。
"""
from __future__ import annotations
import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../h3_lint
PLAN = HERE.parent                              # .../AI漫剧全流程自动化方案

# ---------------------------------------------------------------------------
# 可扩展清单：加一道门禁，只需往这里加一条 dict。
# stage: n2 / csv / delivery
# key: 唯一标识；label: 打印名；build(ctx)->list[str] 命令；
# needed: 该门禁要求的 ctx 键，缺任一则 SKIP（不判 FAIL）。
# ---------------------------------------------------------------------------
GATES = [
    dict(stage="n2", key="storyboard_lint", label="N2① drama storyboard 本体 lint",
         needed=["drama_root", "storyboard"],
         build=lambda c: [sys.executable, str(Path(c["drama_root"]) / "storyboard_lint.py"),
                          str(c["storyboard"])] + (["--csv", str(c["storyboard_csv"])] if c.get("storyboard_csv") else [])),
    dict(stage="n2", key="check_n2_skills", label="N2② 防忘：每镜诊断段+情绪曲线",
         needed=["storyboard"],
         build=lambda c: [sys.executable, str(HERE / "check_n2_skills.py"), str(c["storyboard"]),
                          "--expect-shots", str(c.get("expect_shots", 0))]),
    dict(stage="n2", key="check_camera_landing", label="N2③a 运镜落地：诊断 vs 提示词+景别+道具尺度",
         needed=["storyboard", "prompts"],
         build=lambda c: [sys.executable, str(HERE / "check_camera_landing.py"),
                          str(c["storyboard"]), str(c["prompts"])]),
    dict(stage="n2", key="check_castset_slot", label="N2③b CAST+SET/四槽/镜型分流/镜号",
         needed=["prompts"],
         build=lambda c: [sys.executable, str(HERE / "check_castset_slot.py"), str(c["prompts"]),
                          "--expect-shots", str(c.get("expect_shots", 0))]
                         + (["--storyboard", str(c["storyboard"])] if c.get("storyboard") else [])
                         + (["--solo-shots", c["solo_shots"]] if c.get("solo_shots") else [])),
    dict(stage="n2", key="md_to_h3_lint", label="N2④ H3 提示词 lint（桥接校验视图）",
         needed=["prompts", "out_dir"],
         build=lambda c: ([sys.executable, str(HERE / "md_to_h3_lint.py"), str(c["prompts"]),
                           "-o", str(Path(c["out_dir"]) / "视频提示词_lint视图.html"), "--lint"])),

    dict(stage="csv", key="check_prompt_content", label="CSV① 镜号/Picture2/模板体检",
         needed=["csv"],
         build=lambda c: [sys.executable, str(HERE / "check_prompt_content.py"), str(c["csv"])]
                         + (["--prompt-md", str(c["prompts"])] if c.get("prompts") else [])),
    dict(stage="csv", key="check_segment_length", label="CSV② 单段 ≤144 帧 / 17n 网格",
         needed=["csv"],
         build=lambda c: [sys.executable, str(HERE / "check_segment_length.py"), str(c["csv"])]),
    dict(stage="csv", key="csv_check_only", label="CSV③ 装配体检 --check-only",
         needed=["csv"],
         build=lambda c: [sys.executable, str(PLAN / "csv_to_timeline.py"), "--csv", str(c["csv"]),
                          "--check-only"] + (["--input-root", str(c["input_root"])] if c.get("input_root") else [])),

    dict(stage="delivery", key="check_delivery_media", label="交付 段数/规格/尾段误交",
         needed=["segs"],
         build=lambda c: [sys.executable, str(HERE / "check_delivery_media.py")] + list(c["segs"])
                         + (["--archive", str(c["archive"])] if c.get("archive") else [])
                         + (["--expect", str(c["expect_shots"])] if c.get("expect_shots") else [])
                         + (["--width", str(c["width"])] if c.get("width") else [])
                         + (["--height", str(c["height"])] if c.get("height") else [])),
    dict(stage="delivery", key="check_review_report", label="交付 审片痕迹：各档位报告是否落盘",
         needed=["review_dir"],
         build=lambda c: [sys.executable, str(HERE / "check_review_report.py"), str(c["review_dir"]),
                          "--expect", c.get("review_expect", "preview,final")]),
]

STAGES = ["n2", "csv", "delivery"]


def resolve_project(ctx: dict) -> None:
    """根据 --project-root 补齐分镜/提示词/shotlist 的默认位置（找不到就留空，由 SKIP 处理）。"""
    root = ctx.get("project_root")
    if not root:
        return
    root = Path(root)
    ctx.setdefault("storyboard", next((str(p) for p in
        [root / "分镜.md", root / "分镜" / "分镜.md"] if p.exists()), None))
    ctx.setdefault("prompts", next((str(p) for p in
        [root / "视频提示词.md", root / "分镜" / "视频提示词.md"] if p.exists()), None))
    ctx.setdefault("storyboard_csv", next((str(p) for p in
        [root / "分镜.csv", root / "分镜" / "分镜.csv"] if p.exists()), None))
    ctx.setdefault("csv", next((str(p) for p in
        [root / "shotlist.csv", root / "03-分镜表" / "shotlist.csv"] if p.exists()), None))
    ctx.setdefault("out_dir", str(root / "out"))
    Path(ctx["out_dir"]).mkdir(parents=True, exist_ok=True)


def run_gate(g: dict, ctx: dict) -> tuple[str, str]:
    missing = [k for k in g["needed"] if not ctx.get(k)]
    if missing:
        return "SKIP", "缺参数: " + ", ".join(missing)
    cmd = g["build"](ctx)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        return "FAIL", f"执行异常: {type(e).__name__}: {e}"
    tail = (r.stdout + r.stderr).strip().splitlines()
    detail = " / ".join(tail[-3:])[:300] if tail else "(无输出)"
    return ("PASS" if r.returncode == 0 else "FAIL"), detail


def main() -> int:
    ap = argparse.ArgumentParser(description="质量链统一编排器（数据驱动、可扩展、跨机）")
    ap.add_argument("--stage", choices=STAGES + ["all"], default="all")
    ap.add_argument("--list", action="store_true", help="列出全部编排项后退出")
    ap.add_argument("--project-root", help="剧集/项目目录，用于自动定位分镜/提示词/CSV")
    ap.add_argument("--storyboard", help="分镜.md 路径（覆盖自动定位）")
    ap.add_argument("--prompts", "--prompt-md", dest="prompts", help="视频提示词.md 路径（--prompt-md 为门禁脚本同义别名）")
    ap.add_argument("--storyboard-csv", help="分镜.csv 路径（storyboard_lint 可选）")
    ap.add_argument("--csv", help="shotlist.csv 路径")
    ap.add_argument("--expect-shots", type=int, default=0, help="期望镜数")
    ap.add_argument("--drama-root", help="drama storyboard_lint.py 所在脚本目录")
    ap.add_argument("--input-root", help="ComfyUI input 根（csv --check-only 用）")
    ap.add_argument("--out-dir", help="校验视图输出目录")
    ap.add_argument("--seg", action="append", default=[], help="分段 mp4，可重复或含通配符")
    ap.add_argument("--archive", help="归档整片 mp4（用于尾段误交检查）")
    ap.add_argument("--review-dir", help="审片报告目录（如 生产线/out）；给了才跑审片痕迹门禁")
    ap.add_argument("--review-expect", default="preview,final", help="需要哪些审片报告档位，逗号分隔")
    ap.add_argument("--width", type=int); ap.add_argument("--height", type=int)
    args = ap.parse_args()

    if args.list:
        for st in STAGES:
            print(f"[{st}]")
            for g in GATES:
                if g["stage"] == st:
                    print(f"  - {g['key']:<22} {g['label']}  (needs: {', '.join(g['needed'])})")
        return 0

    ctx = {k: v for k, v in vars(args).items() if v not in (None, "", [], 0)}
    resolve_project(ctx)
    # 展开分段通配符
    if "seg" in ctx:
        expanded = []
        for s in ctx["seg"]:
            hits = sorted(glob.glob(s))
            expanded.extend(hits if hits else [s])
        ctx["segs"] = expanded
    if args.expect_shots:
        ctx["expect_shots"] = args.expect_shots

    stages = STAGES if args.stage == "all" else [args.stage]
    results = []
    print("=" * 72)
    print(f"质量链编排  stage={args.stage}  (脚本门禁层；Skill 调用见手册 2.x 编排表)")
    print("=" * 72)
    for st in stages:
        print(f"\n── {st} ──")
        for g in GATES:
            if g["stage"] != st:
                continue
            status, detail = run_gate(g, ctx)
            results.append((st, g["key"], status))
            print(f"  [{status:4}] {g['key']:<22} {detail}")

    fail = [r for r in results if r[2] == "FAIL"]
    skip = [r for r in results if r[2] == "SKIP"]
    print("\n" + "=" * 72)
    print(f"汇总: PASS {sum(1 for r in results if r[2]=='PASS')} / "
          f"FAIL {len(fail)} / SKIP {len(skip)}  共 {len(results)} 项")
    if fail:
        print("失败项(必须处理才能过闸): " + ", ".join(f"{s}:{k}" for s, k, _ in fail))
    if skip:
        print("跳过项(缺参数，非失败): " + ", ".join(f"{s}:{k}" for s, k, _ in skip))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
