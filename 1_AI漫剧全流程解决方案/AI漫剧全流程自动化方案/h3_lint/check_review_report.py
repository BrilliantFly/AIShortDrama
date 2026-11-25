#!/usr/bin/env python3
"""审片痕迹门禁：确认每个需要的审片节点都留下了审片报告。

为什么需要：H3成片质量审片是知识型 Skill（无 CLI），无法用命令证明"当时调了"。
本门禁退而查"产物痕迹"——报告文件在不在、档位齐不齐。报告缺失 => RC=1。
注意：报告存在只能证明"有输出"，不能证明"是 Skill 调的"；硬证据仍是会话 Skill(...) 调用记录。

用法：
  python check_review_report.py <目录> --expect preview,final
  python check_review_report.py <目录> --expect preview,final,delivery --strict
  # 自定义命名：--pattern '审片报告_*.md'（默认）

识别规则（报告文件名需含档位关键字，大小写不敏感）：
  preview  -> 文件名含 preview / 预览 / 4step
  final    -> 文件名含 final / 成片 / 25step / 正式
  delivery -> 文件名含 delivery / 交付
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

LABELS = {
    "preview": ["preview", "预览", "4step"],
    "final": ["final", "成片", "25step", "正式"],
    "delivery": ["delivery", "交付"],
}


def main() -> int:
    ap = argparse.ArgumentParser(description="审片痕迹门禁：检查各节点审片报告是否落盘")
    ap.add_argument("directory", help="审片报告所在目录（如 生产线/out）")
    ap.add_argument("--expect", default="preview,final", help="需要哪些档位，逗号分隔（默认 preview,final）")
    ap.add_argument("--pattern", default="审片报告_*.md", help="报告文件 glob 模式")
    ap.add_argument("--strict", action="store_true", help="报告数不足即 FAIL；默认也 FAIL，--strict 额外要求每档至少一份")
    args = ap.parse_args()

    d = Path(args.directory)
    if not d.is_dir():
        print(f"FAIL：目录不存在 {d}")
        return 1
    files = sorted(d.glob(args.pattern))
    if not files:
        print(f"FAIL：{d} 下找不到任何匹配 {args.pattern} 的审片报告（成片审片可能漏做）")
        return 1

    expect = [x.strip() for x in args.expect.split(",") if x.strip()]
    unknown = [x for x in expect if x not in LABELS]
    if unknown:
        print(f"FAIL：未知档位 {unknown}，可选 {list(LABELS)}")
        return 1

    print(f"目录：{d}")
    print(f"报告文件 {len(files)} 份：")
    for f in files:
        print("  -", f.name)

    missing = []
    for stage in expect:
        kws = LABELS[stage]
        hit = [f for f in files if any(k.lower() in f.name.lower() for k in kws)]
        mark = "OK" if hit else "MISS"
        print(f"  [{mark:4}] {stage} -> {', '.join(f.name for f in hit) if hit else '无匹配报告'}")
        if not hit:
            missing.append(stage)

    print("=" * 60)
    if missing:
        print("FAIL：缺审片报告档位 -> " + ", ".join(missing))
        print("提示：回对应节点重跑 H3成片质量审片；门禁绿≠Skill调用过，核对会话 Skill(...) 记录")
        return 1
    print(f"PASS：{len(expect)} 个档位审片报告齐全（{', '.join(expect)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
