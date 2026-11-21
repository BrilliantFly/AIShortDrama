# 6_剪辑 · 剪辑与交付层（N17）

> 用途：承接 N14 之后分叉出的 **片段版**，完成**剪辑决策与成片交付**——镜头取舍、`剪辑单.md`、背景音/音效、字幕、响度统一与交付验收。成片版仍由主干 N15/N16 产出，两版并列（见第六节）。
> 说明：本目录只放工具与说明，不改动 `3_漫剧SKILLS` 里的第三方原版；`tools/drama-edit/` 是只读副本。

## 一、已安装工具（2026-11-21）

| 路径 | 内容 | 状态 |
|---|---|---|
| `tools/ffmpeg/ffmpeg.exe` | FFmpeg 9.1 essentials（gyan.dev），含 libass 字幕、librubberband 变速、x264 | ✅ 实测 `-version` 通过 |
| `tools/ffmpeg/ffprobe.exe` | 媒体探测（时长/帧率/响度验收必需） | ✅ 实测 `-version` 通过 |
| `tools/ffmpeg/ffplay.exe` | 快速预览 | ✅ 随包 |
| `tools/drama-edit/scripts/edit_tool.py` | 剪辑单驱动的 `check` / `render` / `verify` | ✅ 两种 Python 下 `--help` 通过 |
| `tools/prepare_two_versions.py` | 两版产物适配器：逐镜片段归集 + `剪辑单.md` 草稿 + 上游骨架 + 成片版命令 | ✅ 合成素材实测 `check` 通过（`findings: []`） |
| `tools/mix_background.py` | ③ 背景音混音：多层铺底 + ducking + 两遍 loudnorm + 实测响度 + 字幕烧录 + 剪辑单记录 | ✅ 合成素材实测通过（详见第七节） |
| `tools/delivery_qc.py` | ④ 成片交付验收：对齐 `delivery-verify.md` 10 项，合并 `qc_gate` 报告 | ✅ 合成素材实测 10 项全出（详见第七节） |
| `tools/drama-edit/assets/remotion/` | Remotion 字幕渲染源码（18 文件，已补齐） | 只读副本 |
| `tools/drama-edit/references/` | 声音字幕音乐、交付验收、剪辑手法等参考 | 只读副本 |
| `tools/drama-edit/assets/剪辑单.md` | 剪辑单成稿样例 | 只读副本 |
| `activate.bat` | 双击后把 ffmpeg 目录加入当前命令行 PATH | 备用：手动把 `tools/ffmpeg` 加入系统 PATH |

来源：https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip （见 `tools/ffmpeg/SOURCE.txt`）。
注意本资料库根目录名末尾有零宽字符，命令行里建议从资源管理器复制路径。

## 二、你问的两件事，能不能在剪辑环节解决

### 1. 声音语速不自然 —— 只能缓解，根治在生成端

经验库 4.0 已定论：**参考音频只锁音色（F0），完全不控制语速**；语速/时机由 `overall_soundscape` 的 `On-screen dialogue:` 句和动作序列控制，4.1 的时机问题已在生成端 v3 解决，4.5 已宣布 H3 内部声音定版不再迭代。所以剪辑层能做和不能做：

| 做法 | 剪辑层可行性 | 工具 | 风险 |
|---|---|---|---|
| 压缩句间静默、调整接话间隔 | ✅ 推荐 | `audio_tighten.py`（N14）或 ffmpeg `silencedetect` + trim | 静默期不能有口型动作 |
| 整段取舍/重排、删掉念稿感重的镜 | ✅ 推荐 | `edit_tool.py` 的 `## CUT-...` | 需回写剪辑单说明未采用原因 |
| 轻微整体变速（±3~5%） | ⚠️ 谨慎 | ffmpeg `atempo=1.03` / `rubberband=tempo=1.03` | 超过 5% 口型明显不同步 |
| 把"平铺直叙"变成自然对话 | ❌ 做不到 | — | 根因在生成端提示词（情绪副词/接话感），见经验库 4.6 |

**结论**：语速的自然度不要指望在剪辑层修好；后期只收尾"间隔过长/静默过多/整段不合适"。

### 2. 背景音/音乐 —— 可以，而且剪辑层比生成端更合适

主干的 H3 六段式虽有 `non_diegetic_music`，但生成端音乐不可精确控制；剪辑层可以精确放进去：

- `edit_tool.py render` 按剪辑单的 **`环境声`** 行循环铺底、**`音效`** 行混入指定片段、**`配音`** 行播放独立声音文件，并对整片做 `loudnorm` 响度标准化（输出 48 kHz）。
- 但内置渲染**不做** ducking（对白压低）、交叉淡入、配乐进入/退出、静音——这些要用 ffmpeg 外部命令完成，并把命令记进剪辑单。**现已封装为 `tools/mix_background.py`**（见第七节），不必手工拼命令。

脚本内部使用的"背景音 + 对白压低 + 响度统一"滤镜链（已实测通过，供核对；日常直接跑第七节的脚本）：

```bash
ffmpeg -i dialog.wav -i bgm.wav -filter_complex ^
"[1:a]volume=0.18,aresample=48000[bg];[0:a]asplit=2[dlg][key];[key]highpass=f=200,acompressor=threshold=0.03:ratio=6:attack=20:release=300[duckkey];[bg][duckkey]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[bgduck];[dlg][bgduck]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]" ^
-map "[out]" -ar 48000 mixed.wav
```

要点：对白分支 `asplit` 出一路做侧链触发，音乐被 `sidechaincompress` 在对白处自动压低；`loudnorm` 目标可按交付规格改（`I=-16` 为常用值）。

## 三、`concat_xfade.py` 能不能解决？

**不能。** 它只做「按 CSV 顺序拼接 + 0.35s xfade 叠化 + acrossfade 音频交叉」，不做入出点切段、不做背景音混音、不做变速、不做响度统一、不烧字幕。分工如下：

| 需求 | `concat_xfade.py`（N15） | 剪辑层（N17） |
|---|---|---|
| 全段拼接 + 固定叠化 | ✅ 已实现 | 不必重复 |
| 入出点切段 / 镜头取舍 | ❌ | `edit_tool.py render` |
| 背景音 / 音效 / ducking | ❌ | `tools/mix_background.py`（ducking + 两遍 loudnorm + 剪辑单记录） |
| 字幕 / 画面文字 | ❌ | `edit_tool.py render`（ffmpeg libass 默认） |
| 整片响度统一 | ❌ | `loudnorm` |
| 成片验收 | `qc_gate.py` 逐镜门禁（F0/RMS/ASR TODO） | `tools/delivery_qc.py` 对齐 10 项，`--gate-report` 合并 qc_gate |

## 四、最短命令（双击 `activate.bat` 后）

```bash
python tools\drama-edit\scripts\edit_tool.py check 剧集/EP001 --project-root <项目根>
python tools\drama-edit\scripts\edit_tool.py render 剧集/EP001 --project-root <项目根>
python tools\drama-edit\scripts\edit_tool.py verify 剧集/EP001 --project-root <项目根>
python tools\mix_background.py --input <成片.mp4> --bg <bgm.wav>|0.18 --out <混音成片.mp4> --cut-list 剧集/EP001/剪辑单.md
python tools\delivery_qc.py --episode 剧集/EP001 --film <混音成片.mp4> --report <验收报告.md>
```

`check` 核对剪辑单与素材区间；`render` 切段/接镜/混音/烧字幕/统一响度；`verify` 报时长、切点亮度、疑似坏帧。**渲染成功不等于内容合格**，仍须按 `references/delivery-verify.md` 回听回看；自动化部分由 `delivery_qc.py` 出 10 项报告，人工项（回听/接缝/画内文字/ASR）仍标 TODO，不假装通过。

## 五、落地状态（2026-11-21 全部补齐）

1. ✅ **已交付** `tools/prepare_two_versions.py`：从 CSV / 逐镜 mp4 生成 `剪辑单.md` 草稿与片段工程，人工确认取舍即可。
2. ✅ **不再需要**：两版定线后 N17 的按 CUT 合成由 `edit_tool.py render` 承担，`concat_xfade.py` 只服务成片版。
3. ✅ **已交付** `tools/mix_background.py`：混音命令脚本化 + 两遍 loudnorm + 实测响度 + 字幕烧录 + 剪辑单「## 混音记录」幂等覆盖 + `混音命令.txt` / `混音中间文件/`。
4. ✅ **已交付** `tools/delivery_qc.py`：对齐 `delivery-verify.md` 10 项（边界帧/坏帧、字幕逐字、响度、未采用理由、接镜色彩、交付包），`--gate-report` 合并成片版 `qc_gate.py`。**取舍**：不改 `qc_gate.py` 本体——它是逐镜门禁，与成片级终验输入与职责不同，混改会动到已定版生产脚本。
5. ✅ 片段版工程内生成 `两版产物说明.md`，剪辑单随 `剧集/<EP>/` 归档；每次做完漫剧把新经验追加到 `99_经验库/工作流优化经验库.md`（此项为长期维护动作）。

## 六、两版产物（拓扑定线 · 2026-11-21）

N14 音轨精修之后**分叉**，不是对同一条成片拼两次：

| 版本 | 产出 | 去向 |
|---|---|---|
| **成片版** | `audio_tighten.py` → `concat_xfade.py` → `qc_gate.py` → 单一全片 mp4 | 归档 / 快速复现 / 对照基线 |
| **片段版** ★ | `prepare_two_versions.py` → 逐镜片段 + `剪辑单.md` 草稿 + `视频提示词.md` 骨架 | **专供 N17** 做取舍、入出点、背景音、字幕、响度与交付验收 |

生成片段版（双击 `activate.bat` 后执行，或任意 Python 3.9+）：

```bash
python tools\prepare_two_versions.py \
  --out-root <render_submit 的交付根> --csv <shotlist.csv> \
  --project-root <N17 工程根> --ep EP001 \
  --fixed-dir <音轨精修目录> --drama-dir <drama 项目目录> --verify
```

常用参数：`--dry` 只打印计划；`--force` 覆盖已有剪辑单；`--verify` 生成后自动跑 `edit_tool.py check`。产物：

```
剧集/EP001/
  剪辑单.md                    ← 人工定稿（草稿为每个 CUT 整段保留）
  视频提示词.md                ← MOTION-ID 骨架，供 check 核对来源 ID
  剧本.md / 分镜.md / ...      ← 有 --drama-dir 时复制真实文档，否则占位
  制作成果/videos/MOTION-EP001-*.mp4   ← 逐镜片段（未拼接）
  制作成果/片段清单.csv
  制作成果/成片版命令.md        ← 成片版三条命令，参数已填好
  制作成果/两版产物说明.md
```

**关键约束**：`edit_tool.py check` 会核对剪辑单里每个 `MOTION-...` 来源 ID 是否存在于 `视频提示词.md` 的 `## MOTION-...` 标题（且 `- 分镜：SHOT-...` 行供解析），所以片段版必须同时生成该骨架，否则报「来源不在《视频提示词.md》中」。合成 3 段 mp4 实测：`--help` / `--dry` / 生成 / `check` 全部通过，`check` 返回 `findings: []`。

## 七、混音与交付验收（③④ 已补齐 · 2026-11-21）

`render` 之后还有两步收尾。都在 `6_剪辑` 目录下执行（先双击 `activate.bat`，或任意 Python 3.9+；两个脚本只用随包 ffmpeg/ffprobe，不需要 ComfyUI python）。

```bash
# ③ 背景音 / 对白压低 / 响度 / 字幕（结果自动写进剪辑单）
python tools\mix_background.py \
  --input 剧集\EP001\制作成果\成片\EP001-成片.mp4 \
  --bg 素材\bgm.wav|0.18 --bg 素材\室内底噪.wav|0.10 \
  --out 剧集\EP001\制作成果\成片\EP001-混音成片.mp4 \
  --subtitles 剧集\EP001\制作成果\成片\字幕.srt \
  --cut-list 剧集\EP001\剪辑单.md

# ④ 成片交付验收（10 项，可合并成片版 qc_gate 报告）
python tools\delivery_qc.py \
  --episode 剧集\EP001 \
  --film 剧集\EP001\制作成果\成片\EP001-混音成片.mp4 \
  --gate-report 剧集\EP001\制作成果\成片\qc_report.json \
  --report 剧集\EP001\制作成果\成片\验收报告.md
```

**③ `mix_background.py` 要点**

- `--bg 路径|音量` 可重复；`-stream_loop -1` 循环铺底，对白 `asplit` 一路做侧链触发，`sidechaincompress` 在对白处自动压低音乐。
- 默认**两遍 loudnorm**（先测 `measured_*` 再 `linear=true`），第三遍再测实际 LUFS/真峰写进记录——不把目标值当实测值（`sound-and-subtitles.md` 明确要求）。
- 可选 `--subtitles`（srt 自动转 ass，libass 烧录）、`--tempo`（0.95~1.05，超阈值直接拒绝防口型穿帮）、`--no-duck`、`--single-pass`、`--dry`、`--clean`。
- 产物：`混音中间文件/`（premix.wav / mixed.wav / subs.ass）、`混音命令.txt`、剪辑单内 `<!-- N17-MIX-RECORD:START/END -->` 包裹的「## 混音记录」（**幂等覆盖**，重复执行不会堆叠）。中间文件保留正是 `delivery-verify.md` 要求的「可继续编辑的中间文件」。
- 追加该区块**不会破坏 `edit_tool.py check`**：它只认 `## CUT-...` 标题，其它 `## ` 标题会把 current 置 None，字段行进入 preamble。

**④ `delivery_qc.py` 要点**

- 10 项 = `delivery-verify.md` 表格 9 项（时长与切点 / 内容覆盖 / 台词 / 边界帧 / 声音 / 字幕 / 画内文字 / 画幅与帧率 / 接镜色彩）+「交付」1 项。
- 只用 ffmpeg/ffprobe：ffprobe 取时长画幅帧率；`loudnorm print_format=json` 实测整片响度；`signalstats,metadata=print` 逐帧统计 → 切点前后两帧亮度差 >20 列「请逐帧查看」、疑似坏帧、切点前后 5 帧亮度与 VAVG-UAVG 观测。
- 状态分 `PASS / WARN / FAIL / TODO / SKIP`，**区分实测、人工判断和未测项**；技术观测只指出该看哪里，不阻断交付；回听、接缝、画内文字、ASR 转写留人工 TODO。
- `--gate-report` 合并成片版 `qc_gate.py` 的逐镜 TODO；`--spec-width/height/fps/lufs` 覆盖交付规格；`--no-frames` 快速模式。输出 `验收报告.md` + `.json`。

**实测记录**：合成 6s 成片 + 2 条背景音 + srt → 两遍响度 -16.0 LUFS、字幕烧录成功、剪辑单记录幂等、追加后 `check` 仍 `findings: []`；验收脚本 10 项全出（故意写一条不在剧本的字幕被正确判 WARN），144 帧逐帧统计与 `--no-frames` 均通过。
