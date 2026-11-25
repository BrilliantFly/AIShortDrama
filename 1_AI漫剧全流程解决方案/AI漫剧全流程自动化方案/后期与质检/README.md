# 后期层与质检门禁（2026-11-21 从 EP001 实跑脚本参数化）

全部脚本把实跑版的硬编码路径（`D:\剧本及分镜\街对面\...`）改为 CLI 参数，算法保留实跑定版。
**必须用 ComfyUI 的 python 跑**（`$COMFYUI_PY`，见 `路径约定.md`），它装有下列依赖。

## 依赖

```
numpy
imageio-ffmpeg
av          # contact_sheet / transition_ab / concat_xfade 抽帧
Pillow      # contact_sheet 拼图
```
安装（在 ComfyUI python 环境）：`python.exe -m pip install numpy imageio-ffmpeg av pillow`

## 正确执行顺序（经验库 9.2 第 6 步，注意 N14/N15 顺序）

实跑教训：音轨精修要先于叠化拼接（`--audio-fix` 让精修版优先）。手册旧版写反了，
这里以经验库为准：**先音轨精修 → 再叠化拼接**。

```bash
PY="$COMFYUI_PY"
V="<项目根>/导出/videos"       # 成片源目录
L="<项目根>/导出/N7-出片清单.csv"
OUT="<项目根>/导出"

# 1) 质检（出片后门禁）：RMS/F0 自动，ASR/联系表人工
$PY qc_gate.py --videos "$V" --list "$L" --script 台词文本.json \
    --expect-voice '{"003":"female","004":"female"}' --report "$OUT/qc_report.json"

# 2) 联系表逐格看人数/座位/构图
$PY contact_sheet.py --videos "$V" --list "$L" --out "$OUT/_review_hd.png"

# 3) 对白镜音轨精修（压句间静默，不重出画面）
$PY audio_tighten.py --videos "$V" --out "$OUT/精修" --all \
    --talk-shots 003,004,005,007,008,009 --gap 0.55

# 4) 叠化拼接（--audio-fix 优先用精修版）
$PY concat_xfade.py --videos "$V" --list "$L" --audio-fix --fixed-dir "$OUT/精修" \
    --transition 0.35 --out "$OUT/EP001-hd-全片-音轨精修.mp4"

# 5) 可选：转场方案 A/B/J-cut 对比样片
$PY transition_ab.py --fixed-dir "$OUT/精修" --a 007 --b 008 --out "$OUT/_转场对比.mp4"
```

## 工具分工（别用错）

| 检什么 | 工具 | 判据 |
|---|---|---|
| 台词内容对不对 | AudioTranscribe 抽 wav 转写逐字比对（qc_gate 出 TODO 清单） | 内容错→换 seed 重出 |
| 音色锁没锁住 | qc_gate F0 | 男≈152Hz / 女≈257Hz（±30Hz） |
| 开口/句间隔/碎片 | qc_gate RMS | 开口 ~1s、句间隔 0.3~0.8s、碎片 ≤3 |
| 人数/座位/构图 | contact_sheet 联系表人眼逐格 | 无第三人、无并排、头脚完整、桌面一致 |

F0 只验音色、RMS 只验时机、ASR 才是内容硬门槛。qc_gate 的 TODO 项未人工确认不代表通过。

## 两版产物出口（2026-11-21 二次定线）

本节五个脚本产出的是 **成片版**：按 CSV 全段叠化的单一全片。同批精修片段还要另出一版 **片段版**，专供 N17：

```bash
python tools/prepare_two_versions.py \   # 在 6_剪辑 目录下执行（先 activate.bat）
  --out-root <交付根> --csv <shotlist.csv> --project-root <N17 工程根> --ep EP001 \
  --fixed-dir "<精修目录>" --verify
```

片段版落在 `剧集/<EP>/制作成果/videos/`（逐镜、未拼接、按 `MOTION-<EP>-<镜号>` 命名）+ `剪辑单.md` 草稿。N17 从片段出发做取舍、入出点、背景音、字幕、响度与交付验收；`concat_xfade.py` 只服务成片版，不再承担 N17 的合成。

**质检位置澄清**：上面第 1 步 `qc_gate.py` 验的是逐镜 mp4（F0/RMS/联系表），本可在拼接前跑；成片版的终验仍在拼接后。片段版则在 `edit_tool.py render` 之后跑 `verify`。两条线各自闭环，不存在「先拼成片再剪辑」的倒挂。

## qc_gate.py 与 delivery_qc.py 分工（2026-11-21 收尾定线）

| | `qc_gate.py`（本目录，成片版 N16） | `6_剪辑/tools/delivery_qc.py`（N17 终验） |
|---|---|---|
| 输入 | 逐镜 mp4 + 出片清单 CSV | 已合成成片 + `剪辑单.md` + 上游五文档 |
| 检查 | F0 音色 / RMS 开口时机 / ASR TODO / 联系表 | `delivery-verify.md` 9 项 + 交付 1 项（时长切点、内容覆盖、边界帧、响度、字幕逐字、画幅帧率、接镜色彩、交付包） |
| 依赖 | numpy + imageio_ffmpeg（**必须 ComfyUI python**） | 仅随包 ffmpeg/ffprobe（任意 Python 3.9+） |
| 关系 | `--gate-report` 把本报告合并进终验第 3/5 项 | 不改动 `qc_gate.py` 本体 |

外部混音（`tools/mix_background.py`）与成片验收（`tools/delivery_qc.py`）都在 `6_剪辑` 下操作片段版产物；本目录五个脚本继续只服务成片版。
