#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考图预处理工具（prep_ref2 / prep_ref3 补齐）

背景：N4 出图链 02 号卡的便签写明 ref_band_flat.png / ref_face_hd.png
由 prep_ref2.py / prep_ref3.py 生成，但这两个脚本全库缺失。本文件补齐确定性、
可复现的“规范化预处理”能力——不是自动抠图/自动换脸，不臆造输入。

设计边界（遵守经验库口径）：
- 输入必须由用户明确给出（--src）——一张已裁好的全身条 / 人脸图，或出图链 A1 的
  底板-脚全.png；脚本不做主体检测、不自动判断哪块是人脸。
- 只做确定性的图像规范化：裁切 → 压平光影（低对比 + 中性色温）→ 指定尺寸输出。
  光影压平用 PIL/ImageEnhance，不调用任何生成模型，输出逐次可复现。
- 若用户已有 ComfyUI/input 下现成的 ref_band_flat.png / ref_face_hd.png，
  用 --src 指过去再输出即可（等价于“原样规范化”，用于重跑出板）。

用法：
  PY="$COMFYUI_PY"
  $PY prep_refs.py band --src "$COMFYUI_ROOT/input/底板-脚全.png" \
      --crop 0,180,1024,1100 --out "$COMFYUI_ROOT/input/ref_band_flat.png"
  $PY prep_refs.py face --src "$COMFYUI_ROOT/input/微信图片_xxx.jpg" \
      --crop 300,120,900,720 --out "$COMFYUI_ROOT/input/ref_face_hd.png"
  $PY prep_refs.py inspect --dir "$COMFYUI_ROOT/input"
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def default_input_root() -> Path:
    """ComfyUI input 根：环境变量 COMFYUI_INPUT / COMFYUI_ROOT，跨机可移植。"""
    env_in = os.environ.get('COMFYUI_INPUT')
    if env_in and Path(env_in).is_dir():
        return Path(env_in)
    env_root = os.environ.get('COMFYUI_ROOT')
    if env_root and (Path(env_root) / 'input').is_dir():
        return Path(env_root) / 'input'
    return Path('input')  # 未配置时用当前目录下的 input，避免硬编码盘符


def parse_crop(s: str | None):
    if not s:
        return None
    parts = [int(x) for x in s.split(',')]
    if len(parts) != 4:
        raise SystemExit('--crop 需要 4 个整数：left,top,right,bottom')
    if parts[2] <= parts[0] or parts[3] <= parts[1]:
        raise SystemExit('--crop 区域无效')
    return tuple(parts)


def flatten(im: Image.Image, strength: float) -> Image.Image:
    """压平光影：降对比 + 轻微提亮，使参考图不把源图阴影带进 QwenEdit 换人段。"""
    im = ImageEnhance.Contrast(im).enhance(1.0 - 0.35 * strength)
    im = ImageEnhance.Brightness(im).enhance(1.0 + 0.08 * strength)
    # 温和中性化：与原图 50% 混合，避免彻底丢掉肤色
    neutral = ImageOps.autocontrast(im, cutoff=2)
    return Image.blend(im, neutral, 0.25 * strength)


def main():
    ap = argparse.ArgumentParser(description='N4 参考图规范化预处理（确定性，非自动抠图）')
    sub = ap.add_subparsers(dest='mode', required=True)

    def common(p):
        p.add_argument('--src', required=True, help='输入图（用户明确指定的已裁好源图）')
        p.add_argument('--out', required=True, help='输出图路径')
        p.add_argument('--crop', default=None, help='裁切 left,top,right,bottom（按源图像素）')
        p.add_argument('--width', type=int, default=None, help='输出宽（face 默认 640）')
        p.add_argument('--height', type=int, default=None, help='输出高（face 默认 846）')
        p.add_argument('--flatten', type=float, default=1.0, help='光影压平强度 0~1（默认 1）')

    common(sub.add_parser('band', help='全身参考条 → ref_band_flat.png（默认 512×1254）'))
    common(sub.add_parser('face', help='人脸参考 → ref_face_hd.png（默认 640×846）'))

    ip = sub.add_parser('inspect', help='列出 input 目录下已有参考图规格')
    ip.add_argument('--dir', default=default_input_root())

    a = ap.parse_args()
    if a.mode == 'inspect':
        d = Path(a.dir)
        for f in sorted(d.glob('ref_*.png')) + sorted(d.glob('ref_*.jpg')):
            with Image.open(f) as im:
                print(f.name, im.size, im.mode)
        return

    src, out = Path(a.src), Path(a.out)
    if not src.exists():
        raise SystemExit(f'输入不存在：{src}')
    if not 0 <= a.flatten <= 1:
        raise SystemExit('--flatten 必须在 0~1')
    w = a.width or (640 if a.mode == 'face' else 512)
    h = a.height or (846 if a.mode == 'face' else 1254)

    im = Image.open(src).convert('RGB')
    crop = parse_crop(a.crop)
    if crop:
        if crop[2] > im.width or crop[3] > im.height:
            raise SystemExit(
                f'裁切超出源图范围：crop={crop}，源图={im.size}。'
                '请先查看源图尺寸再给 --crop（本脚本不会自动猜区域）。'
            )
        im = im.crop(crop)
    im = flatten(im, a.flatten)
    # 等比缩放后居中补灰底到目标尺寸（不拉伸变形）
    im.thumbnail((w, h), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (w, h), (128, 128, 128))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    print(f'OK {a.mode}: {src.name} -> {out} ({w}×{h}, crop={crop}, flatten={a.flatten})')


if __name__ == '__main__':
    main()
