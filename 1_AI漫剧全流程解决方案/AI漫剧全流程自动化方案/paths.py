# -*- coding: utf-8 -*-
"""跨电脑可移植的外部环境路径解析。

背景：本仓库会被 clone 到不同电脑，ComfyUI 的安装盘符/目录各不相同。
早期脚本把 `D:/ComfyUI-aki-v3.2/ComfyUI/input` 硬编码为默认值，换机即失效。

本模块统一按以下优先级解析（首次命中的路径存在即用）：
  1. 环境变量 COMFYUI_ROOT  —— 指向 ComfyUI 安装根（含 input/ 与 output/ 子目录）
  2. 环境变量 COMFYUI_INPUT / COMFYUI_OUTPUT —— 直接指定单一目录，优先级高于 ROOT
  3. 常见位置自动探测（Windows / Linux / macOS 多盘符与常见目录名）
  4. 回退到历史默认值（本机原值），并给出提示

脚本里把 `default=Path("D:/.../input")` 换成 `default=default_input_root()` 即可，
行为：本机探测到原路径→完全不变；换电脑→自动探测或读环境变量；都没有→回退+提示。

设置方法（换电脑后一次性配置，写入 shell 配置或运行前 export）：
  Windows PowerShell:  $env:COMFYUI_ROOT = "E:\\AI\\ComfyUI"
  Windows CMD:         set COMFYUI_ROOT=E:\\AI\\ComfyUI
  Git Bash / Linux:    export COMFYUI_ROOT=/opt/ComfyUI
"""
from pathlib import Path
import os
import sys

HISTORICAL_ROOT = Path("D:/ComfyUI-aki-v3.2/ComfyUI")


def _first_existing(candidates):
    """返回第一个存在的目录；都不存在则返回 None。"""
    for p in candidates:
        try:
            if p and p.is_dir():
                return p
        except OSError:
            continue
    return None


def comfy_root():
    """探测 ComfyUI 安装根目录，找不到返回 None。"""
    # 1) 环境变量（最高优先级）
    env_root = os.environ.get("COMFYUI_ROOT")
    if env_root:
        p = Path(env_root).expanduser()
        if p.is_dir():
            return p

    # 2) 常见位置探测：从环境变量指定的搜索根 + 各盘符 + 用户目录
    names = ["ComfyUI", "ComfyUI-aki-v3.2/ComfyUI", "ComfyUI_windows_portable/ComfyUI",
             "comfyui", "ComfyUI-aki/ComfyUI"]
    search_bases = []
    for base_env in ("COMFYUI_SEARCH_ROOT",):
        v = os.environ.get(base_env)
        if v and Path(v).is_dir():
            search_bases.append(Path(v))

    if sys.platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            d = Path(f"{letter}:/")
            if d.exists():
                search_bases.append(d)
        search_bases.append(Path.home())
    else:
        search_bases += [Path("/opt"), Path("/home"), Path.home(), Path("/mnt")]

    for base in search_bases:
        for name in names:
            cand = base / name
            if cand.is_dir() and (cand / "input").is_dir():
                return cand
    return None


def default_input_root():
    """ComfyUI input 目录：环境变量 > 探测 > 历史默认值。"""
    env_in = os.environ.get("COMFYUI_INPUT")
    if env_in and Path(env_in).is_dir():
        return Path(env_in)
    env_root = os.environ.get("COMFYUI_ROOT")
    if env_root and (Path(env_root) / "input").is_dir():
        return Path(env_root) / "input"
    root = comfy_root()
    if root:
        return root / "input"
    return HISTORICAL_ROOT / "input"   # 回退：原行为不变


def default_output_root():
    """ComfyUI output 目录：环境变量 > 探测 > 历史默认值。"""
    env_out = os.environ.get("COMFYUI_OUTPUT")
    if env_out and Path(env_out).is_dir():
        return Path(env_out)
    env_root = os.environ.get("COMFYUI_ROOT")
    if env_root and (Path(env_root) / "output").is_dir():
        return Path(env_root) / "output"
    root = comfy_root()
    if root:
        return root / "output"
    return HISTORICAL_ROOT / "output"  # 回退：原行为不变


def describe():
    """打印当前解析结果，便于换电脑后自检。"""
    return (
        f"COMFYUI_ROOT(env)={os.environ.get('COMFYUI_ROOT', '<未设置>')}\n"
        f"探测到根目录    ={comfy_root()}\n"
        f"input 根        ={default_input_root()}\n"
        f"output 根       ={default_output_root()}"
    )


if __name__ == "__main__":
    print(describe())
