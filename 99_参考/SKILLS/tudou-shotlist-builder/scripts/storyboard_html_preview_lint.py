#!/usr/bin/env python3
"""Validate that every storyboard-manifest page has a real visible HTML nine-grid."""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from html.parser import HTMLParser
from pathlib import Path


class PreviewParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.previews: list[dict] = []
        self.stack: list[dict] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): html.unescape(value or "").strip() for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self.attrs_dict(attrs)
        classes = set(values.get("class", "").split())
        parent = self.stack[-1] if self.stack else None
        node = {"tag": tag.lower(), "attrs": values, "preview": None}
        if tag.lower() == "section" and "sb-preview" in classes:
            node["preview"] = {"attrs": values, "cells": [], "copy_targets": set(), "drawing_ids": set(), "images": 0}
            self.previews.append(node["preview"])
        if parent and parent.get("preview"):
            node["preview"] = parent["preview"]
        preview = node.get("preview")
        if preview:
            if "data-sb-cell" in values:
                preview["cells"].append(values)
            if "data-sb-copy" in values:
                preview["copy_targets"].add(values["data-sb-copy"])
            if "data-sb-drawing-prompt" in values:
                prompt_id = values.get("id", "")
                if prompt_id:
                    preview["drawing_ids"].add(prompt_id)
            if tag.lower() == "img":
                preview["images"] += 1
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == lowered:
                del self.stack[index:]
                break


def close_enough(left: object, right: object) -> bool:
    try:
        return math.isclose(float(left), float(right), abs_tol=0.001)
    except (TypeError, ValueError):
        return False


def lint(html_path: Path, manifest_path: Path) -> list[str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    pages = data.get("pages")
    if not isinstance(pages, list):
        return ["manifest pages 必须是列表"]

    parser = PreviewParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    previews: dict[str, dict] = {}
    errors: list[str] = []
    for preview in parser.previews:
        page_id = preview["attrs"].get("data-sb-page", "")
        if not page_id:
            errors.append("HTML 九宫格 section 缺少 data-sb-page")
        elif page_id in previews:
            errors.append(f"HTML 九宫格页面重复：{page_id}")
        else:
            previews[page_id] = preview

    expected_ids = {page.get("page_id", "") for page in pages if isinstance(page, dict)}
    extra = set(previews) - expected_ids
    for page_id in sorted(extra):
        errors.append(f"HTML 存在 manifest 未声明的九宫格页面：{page_id}")

    for page in pages:
        if not isinstance(page, dict):
            errors.append("manifest 页面不是对象")
            continue
        page_id = page.get("page_id", "")
        prefix = page_id or "未命名页面"
        preview = previews.get(page_id)
        if not preview:
            errors.append(f"{prefix}: HTML 缺少对应的 <section class=sb-preview> 九宫格")
            continue
        attrs = preview["attrs"]
        for key, manifest_key in (("data-sb-scene", "scene_id"), ("data-sb-revision", "revision"), ("data-sb-status", "status")):
            if attrs.get(key) != str(page.get(manifest_key, "")):
                errors.append(f"{prefix}: {key} 与 manifest 不一致")
        if page.get("status") in {"generated", "approved"} and preview["images"] < 1:
            errors.append(f"{prefix}: {page.get('status')} 页面缺少实际分镜图片")

        cells = preview["cells"]
        numbers: list[int] = []
        by_cell: dict[int, dict] = {}
        for cell in cells:
            try:
                number = int(cell.get("data-sb-cell", ""))
            except ValueError:
                errors.append(f"{prefix}: 存在无法识别的 data-sb-cell")
                continue
            numbers.append(number)
            if number in by_cell:
                errors.append(f"{prefix}: 格{number}重复")
            by_cell[number] = cell
        if numbers != list(range(1, 10)):
            errors.append(f"{prefix}: 必须有按 1-9 顺序的恰好九个可见格，而不是摘要卡片")
            continue

        panels = page.get("panels")
        if not isinstance(panels, list) or len(panels) != 9:
            errors.append(f"{prefix}: manifest panels 不完整")
            continue
        for panel in panels:
            cell_number = panel.get("cell")
            if not isinstance(cell_number, int) or cell_number not in by_cell:
                continue
            cell = by_cell[cell_number]
            if panel.get("unused") is True:
                if cell.get("data-sb-unused", "").lower() != "true":
                    errors.append(f"{prefix}/格{cell_number}: manifest 未用格必须在 HTML 标记 data-sb-unused=true")
                continue
            if cell.get("data-sb-unused", "").lower() == "true":
                errors.append(f"{prefix}/格{cell_number}: 活动态格被错误标为未使用")
            if cell.get("data-sb-shot") != panel.get("shot_id"):
                errors.append(f"{prefix}/格{cell_number}: data-sb-shot 与 manifest 镜号不一致")
            if not close_enough(cell.get("data-sb-at"), panel.get("at")):
                errors.append(f"{prefix}/格{cell_number}: data-sb-at 与 manifest 时间不一致")

        if not preview["drawing_ids"]:
            errors.append(f"{prefix}: 缺少 data-sb-drawing-prompt 的绘图提示词")
        if not preview["copy_targets"] & preview["drawing_ids"]:
            errors.append(f"{prefix}: 缺少对应绘图提示词的复制按钮")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 HTML 是否真正嵌入了 manifest 的每一页九宫格")
    parser.add_argument("html_file", type=Path)
    parser.add_argument("manifest_file", type=Path)
    args = parser.parse_args()
    try:
        errors = lint(args.html_file, args.manifest_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"FAIL: {len(errors)} 个 HTML 九宫格问题")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: 每个 manifest 页面均有匹配的可见 HTML 九宫格、九格映射和绘图提示词")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
