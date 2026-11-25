#!/usr/bin/env python3
"""Regression tests for the HTML/manifest nine-grid delivery gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from storyboard_html_preview_lint import lint


def manifest() -> dict:
    return {
        "schema_version": 1,
        "scope_id": "test",
        "revision": "R1",
        "shots": [{"shot_id": "S1", "scene_id": "1", "unit_id": "H3-001", "start": 0, "end": 1, "source_beats": ["A1"], "dialogue": ""}],
        "pages": [{
            "page_id": "P1", "scene_id": "1", "revision": "R1", "aspect_ratio": "16:9", "status": "pending", "image_path": "", "visual_qa": {"passed": False, "notes": "pending"},
            "panels": [{"cell": 1, "shot_id": "S1", "at": 0.5, "frame_label": "S1", "visual": "动作", "continuity": "连续"}] + [{"cell": cell, "unused": True} for cell in range(2, 10)],
        }],
    }


def valid_html(section_tag: str = "section", include_page: bool = True) -> str:
    open_tag = f'<{section_tag} class="sb-preview" data-sb-page="P1" data-sb-scene="1" data-sb-revision="R1" data-sb-status="pending">' if include_page else f'<{section_tag} class="sb-preview">'
    cells = ['<article data-sb-cell="1" data-sb-shot="S1" data-sb-at="0.5">S1</article>']
    cells += [f'<article data-sb-cell="{cell}" data-sb-unused="true">未使用</article>' for cell in range(2, 10)]
    return "<!doctype html><html><body>" + open_tag + "".join(cells) + '<button data-sb-copy="draw">复制</button><pre id="draw" data-sb-drawing-prompt="true">绘图提示</pre>' + f'</{section_tag}></body></html>'


class PreviewTests(unittest.TestCase):
    def run_lint(self, html: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            html_path = base / "sheet.html"
            manifest_path = base / "board.json"
            html_path.write_text(html, encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest(), ensure_ascii=False), encoding="utf-8")
            return lint(html_path, manifest_path)

    def test_valid_pending_grid_passes(self) -> None:
        self.assertEqual(self.run_lint(valid_html()), [])

    def test_div_cannot_replace_section(self) -> None:
        errors = self.run_lint(valid_html(section_tag="div"))
        self.assertTrue(any("缺少对应" in error for error in errors))

    def test_missing_page_fails(self) -> None:
        errors = self.run_lint(valid_html(include_page=False))
        self.assertTrue(any("缺少 data-sb-page" in error or "缺少对应" in error for error in errors))

    def test_summary_cards_do_not_count_as_grid(self) -> None:
        html = '<!doctype html><html><body><section class="sb-preview" data-sb-page="P1" data-sb-scene="1" data-sb-revision="R1" data-sb-status="pending"><div>H3-001</div><pre id="draw" data-sb-drawing-prompt="true">绘图提示</pre><button data-sb-copy="draw">复制</button></section></body></html>'
        errors = self.run_lint(html)
        self.assertTrue(any("恰好九个" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
