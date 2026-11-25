#!/usr/bin/env python3
"""Read-only storyboard/timeline validation. No network or media generation."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(data, base=Path('.')):
    errors, notices = [], []
    if not isinstance(data, dict):
        return ['清单根节点必须是对象'], notices, 0.0
    if data.get('schema_version') != 1:
        errors.append('schema_version 必须为 1')
    for key in ('scope_id', 'revision'):
        if not nonempty(data.get(key)):
            errors.append(f'缺少 {key}')
    shots, pages = data.get('shots'), data.get('pages')
    if not isinstance(shots, list) or not shots:
        return errors + ['shots 必须是非空列表'], notices, 0.0
    if not isinstance(pages, list) or not pages:
        return errors + ['pages 必须是非空列表'], notices, 0.0
    lookup, order = {}, {}
    previous_end, runtime = 0.0, 0.0
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f'镜头 {index + 1} 不是对象')
            continue
        sid = shot.get('shot_id')
        if not nonempty(sid):
            errors.append(f'镜头 {index + 1} 缺少 shot_id')
            continue
        if sid in lookup:
            errors.append(f'重复镜号 {sid}')
            continue
        lookup[sid], order[sid] = shot, index
        for key in ('scene_id', 'unit_id'):
            if not nonempty(shot.get(key)):
                errors.append(f'{sid} 缺少 {key}')
        beats = shot.get('source_beats')
        if not isinstance(beats, list) or not beats or not all(nonempty(b) for b in beats):
            errors.append(f'{sid} 缺少来源节拍')
        if not isinstance(shot.get('dialogue'), str):
            errors.append(f'{sid} dialogue 必须为字符串（无台词用空字符串）')
        start, end = shot.get('start'), shot.get('end')
        if not number(start) or not number(end) or start < 0 or end <= start:
            errors.append(f'{sid} 时间区间无效')
            continue
        if abs(start - previous_end) > 0.001:
            errors.append(f'{sid} 与上一镜时间不连续或重叠')
        previous_end = end
        runtime += end - start
    seen_pages, covered = set(), set()
    last_order, last_at = -1, -1.0
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            errors.append(f'页面 {page_index + 1} 不是对象')
            continue
        pid = page.get('page_id')
        if not nonempty(pid):
            errors.append(f'页面 {page_index + 1} 缺少 page_id')
            pid = f'页面{page_index + 1}'
        if pid in seen_pages:
            errors.append(f'重复页面 {pid}')
        seen_pages.add(pid)
        if page.get('revision') != data.get('revision') and page.get('status') != 'stale':
            errors.append(f'{pid} 版本不同却未标记过期')
        ratio = page.get('aspect_ratio', '')
        try:
            width, height = map(float, ratio.split(':'))
            assert number(width) and number(height) and width > 0 and height > 0
        except (ValueError, AttributeError, AssertionError):
            errors.append(f'{pid} 单格画幅无效')
        status = page.get('status')
        if status not in {'pending', 'generated', 'approved', 'failed', 'stale'}:
            errors.append(f'{pid} 状态无效')
        if status != 'approved':
            notices.append(f'{pid}: {status}，不是已验收分镜')
        if status in {'generated', 'approved'}:
            image_path = page.get('image_path')
            if not nonempty(image_path) or not (base / image_path).is_file():
                errors.append(f'{pid} 缺少实际图片文件')
        qa = page.get('visual_qa')
        if status == 'approved' and (
            not isinstance(qa, dict) or qa.get('passed') is not True or not nonempty(qa.get('notes'))
        ):
            errors.append(f'{pid} 缺少看图验收结论')
        panels = page.get('panels')
        if not isinstance(panels, list) or len(panels) != 9:
            errors.append(f'{pid} 必须恰好九格')
            continue
        blank_seen, active = False, 0
        for cell, panel in enumerate(panels, 1):
            label = f'{pid}/格{cell:02}'
            if not isinstance(panel, dict) or type(panel.get('cell')) is not int or panel.get('cell') != cell:
                errors.append(f'{label} 格号或顺序错误')
                continue
            if panel.get('unused') is True:
                blank_seen = True
                if any(key in panel for key in ('shot_id', 'at')):
                    errors.append(f'{label} 未用格不应拥有镜头或时间')
                continue
            active += 1
            if blank_seen:
                errors.append(f'{label} 有效画面出现在未用格之后')
            sid = panel.get('shot_id')
            if not nonempty(sid) or sid not in lookup:
                errors.append(f'{label} 未知镜号')
                continue
            shot = lookup[sid]
            covered.add(sid)
            if shot.get('scene_id') != page.get('scene_id'):
                errors.append(f'{label} 跨越所属场景')
            at = panel.get('at')
            if not number(at) or not number(shot.get('start')) or not number(shot.get('end')):
                errors.append(f'{label} 缺少合法时间')
            else:
                if not shot['start'] <= at <= shot['end']:
                    errors.append(f'{label} 关键帧超出镜头时间')
                if order[sid] < last_order or at < last_at or (order[sid] == last_order and at <= last_at):
                    errors.append(f'{label} 倒序或重复关键帧')
                last_order, last_at = order[sid], at
            for key in ('frame_label', 'visual', 'continuity'):
                if not nonempty(panel.get(key)):
                    errors.append(f'{label} 缺少 {key}')
        if not active:
            errors.append(f'{pid} 没有任何实际分镜格')
    missing = set(lookup) - covered
    if missing:
        errors.append('未绘制的镜头：' + ', '.join(sorted(missing)))
    return errors, notices, round(runtime, 3)


def main():
    if len(sys.argv) != 2:
        print('用法：python storyboard_manifest_lint.py <清单.json>')
        return 2
    path = Path(sys.argv[1]).resolve()
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        errors, notices, runtime = validate(data, path.parent)
    except (OSError, ValueError, TypeError) as exc:
        print(f'读取失败：{exc}')
        return 2
    for message in notices:
        print('状态：' + message)
    for message in errors:
        print('错误：' + message)
    print(f'唯一镜头总时长：{runtime:g} 秒；' + ('结构未通过' if errors else '结构通过（不代替看图与原文核对）'))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
