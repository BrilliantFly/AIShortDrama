# 剧本配音流水线 · 情绪 / 语速 / 音量 / 真人互动对白

> **权威方向（2026-11-22 用户规定）：本流水线的源文件在 `2_工作流/02-漫剧/03-配音流水线/`；
> 主干方案 `1_AI漫剧全流程解决方案/AI漫剧全流程自动化方案/配音流水线/` 为副本。
> 修改一律先改 `2_工作流`，再同步回主干方案副本，保持字节一致。**

从剧本到成段对白音轨的独立流水线。核心思路：**逐句合成、逐句控制表演，再按时间轴拼成一场有来有回的对话**——不是把整段台词一次丢给 TTS。

产出可直接接 H3 `source` 档（原声 mux + 音频驱动口型）、LatentSync 对口型，或只当「带情绪的参考音频」喂给现役主线。

---

## 1. 这条线能控什么

| 维度 | 落在哪一层 | 参数 | 取值范围 |
|---|---|---|---|
| **音色（身份）** | 每角色一条参考音频，跨句固定 | `ref_audio` → `LoadAudio` | 相对 `ComfyUI/input/` 的路径 |
| **情感** | IndexTTS2 八维情绪向量 | `emotion_vector` | happy/angry/sad/afraid/disgusted/melancholic/surprised/calm，**和 ≤ 1.5** |
| **语速** | TTS 原生参数 | `speech_speed` | 0.25~4.0（急促 1.2 / 正常 1.0 / 缓慢 0.85） |
| **声音大小** | 后期逐句增益 | `gain_db` | 耳语 −9 / 压低 −6 / 正常 0 / 喊 +5 dB |
| **句内停顿** | TTS 原生参数 | `interval_silence_ms` | 长文本自动分段的段间静默，按句长 200/280/380 |
| **句间停顿 / 抢话** | 后期时间轴 | `gap_before` | 换人接话 0.35s / 同一人续说 0.5s / 抢话负值 −0.2~−0.5s（重叠） |
| **可复现** | 稳定 seed | `seed` | 由 `line_id` 哈希派生，不会因单句重跑而变 |

**身份与表演必须分开**（对齐 `voice-direction.md`）：参考音频只承担音色，不能把「这条里的情绪 / 语速 / 录音空间」带进角色。情绪、语速、音量属于本场表演，逐句写在配音本里。

**语速与音量不重复施加**：语速在 TTS 层 `speech_speed`，音量在后期 `volume(dB)`——改音量不用重跑一次几十分钟的 TTS。`assemble --post-speed` 只在「没有跑过 TTS、直接用现成 wav」时才需要开。

---

## 2. 文件

| 文件 | 用途 |
|---|---|
| `IndexTTS2-情感配音工作台.json` | **ComfyUI GUI 可直接打开**，单句试听调参用；带 20 个 widget 索引对照表 |
| `voice_pipeline.py` | 四段流水线：`parse` / `plan` / `render` / `assemble`，`run` 一条龙 |
| `voice_map.json` | 参数词表：12 种情绪处方、语速/音量/停顿/抢话关键词、互动规则、API 节点表、官方默认参数 |
| `voice_sheet.example.csv` | 《同学会暗恋》走廊重逢 8 句真实台词的示例配音本 |
| `README.md` | 本文件 |

---

## 3. 安装前提（本机当前**未装**节点包）

```
cd "$COMFYUI_ROOT/custom_nodes"
git clone https://github.com/snicolast/ComfyUI-IndexTTS2
"$COMFYUI_PY" -m pip install wetext
"$COMFYUI_PY" -m pip install -r ComfyUI-IndexTTS2/requirements.txt
```

模型 `IndexTeam/IndexTTS-2` 放 `custom_nodes/ComfyUI-IndexTTS2/checkpoints/`。仅 Windows、未启用 DeepSpeed。装完重启 ComfyUI。

> 节点包没装也能验证整条链：`render --dry` 不连服务；`render --from-wavs <目录>` 用现成 wav 跳过 TTS，`assemble` 的音量/停顿/抢话/响度归一全部可跑可验收。**模型和权重由你手动下载，本流水线不改任何第三方文件。**

---

## 4. 五步命令

在 `配音流水线/` 目录下，用带 `imageio_ffmpeg` 的 ComfyUI Python 跑：

```bash
PY="$COMFYUI_PY"   # 见 路径约定.md，COMFYUI_PY 指向 ComfyUI 的 python.exe

# 1 剧本 → 配音本（也支持 drama skill 的 voice-record-sheet.jsonl）
$PY voice_pipeline.py parse \
  --script "<项目根>/小说/剧本.md" \
  --characters "林晚,沈屿" \
  --voice-refs "林晚=voices/linwan.wav;沈屿=voices/shenyu.wav" \
  --out _run/voice_sheet.csv

# 2 cue 自然语言 → 结构化表演参数（结果可人工再改 CSV 覆盖任意列）
$PY voice_pipeline.py plan --sheet _run/voice_sheet.csv --out _run/voice_plan.json

# 3 逐句合成（先 dry 看参数）
$PY voice_pipeline.py render --plan _run/voice_plan.json --wav-dir _run/wav --dry
$PY voice_pipeline.py render --plan _run/voice_plan.json --wav-dir _run/wav \
  --server 127.0.0.1:8188

# 4 时间轴混音
$PY voice_pipeline.py assemble --plan _run/voice_plan.json --wav-dir _run/wav \
  --out-dir _run/成片

# 或一条龙
$PY voice_pipeline.py run --script "<项目根>/小说/剧本.md" \
  --characters "林晚,沈屿" --voice-refs "林晚=voices/linwan.wav;沈屿=voices/shenyu.wav" \
  --out-dir _run
```

`render` 支持断点续跑（目标 wav 已存在即跳过）、`--only VL-006,S004` 单句重跑、`--force` 强制重出、单句失败不中断整批。

**配音本列**：`line_id, shot, speaker, text, channel, cue, ref_audio, emotion, speed, gain_db, pause_after, overlap`。后五列是**可选覆盖**，留空就按 `voice_map.json` 的关键词与互动规则自动推断；填了就以填的为准。`cue` 写自然语言即可（"说得太快"、"停半拍"、"压低声音"）。

---

## 5. 真人互动感怎么来的

`plan` 与 `assemble` 里四条规则共同作用：

1. **换人接话 0.35s / 同一人续说 0.5s** —— 不再每句等同样长；
2. **负 gap 重叠** —— cue 含「接得太快 / 抢话 / 打断」时下一句提前进入，形成抢话；
3. **情绪抖动** —— 同一说话人连续两句同情绪时，给非主导情绪维加 0.08 微扰，避免连读像念稿；
4. **尾白 1.0s + 整段 EBU R128 响度归一（−16 LUFS）** —— 句间音量起伏保留，整体不过载。

`对白时间线.csv` 会逐句列出 `start_s / end_s / gap_before_s / emotion / speed / gain_db`，可以直接给剪辑、字幕与质检核对。

---

## 6. 下游衔接（三选一）

| 路线 | 怎么用 | 约束 |
|---|---|---|
| **source 档原声** | `2_工作流/归档/H3-通用02-对白原声-source-4step-1152x640.json`：`audioMode=source` + `Audio: fully_copy`，音轨原样 mux、参考音频驱动口型 | 4step turbo 档；**台词文本必须与音频逐字一致**，段长 ≥ 音频时长。README 标注该路线「已弃用」，取用前自行评估 |
| **LatentSync 对口型** | `归档/_备份-2026-11-15/.../H3-LatentSync-口型对齐-单段.json` | 输出 25fps 而原段 24fps，要按时间线裁剪、不能直接拼；音频补静音到段尾会让嘴动到段尾 |
| **只当带情绪参考音频** | 把产出的 wav 挂到现役 `generate` 档的 `<Audio 1>` | 经验库 4.0：参考音频只锁音色 F0，情绪不会随之迁移；4.6 第③点把它列为最后手段，音色也会跟着变 |

> 现役主线 `H3-通用02-高清主线-参考音色对白` 是 `generate` + `Audio: reference` 音画同生，H3 源码**没有 emotion/prosody 参数**。要精确控情绪，只能走本流水线先出配音，再决定贴音轨的方式。

---

## 7. 已知边界

- `parse` 从剧本「」抽台词并按上下文猜说话人，是启发式；**结果必须人工核对 `speaker` 列**，`cue` 也可直接改写。已有 `voice-record-sheet.jsonl` 时优先用它（说话人是权威的）。
- 批量 `render` 不接 `emotion_audio`：官方源码确认 `emotion_vector` 与第二条音频同时存在时向量优先、音频被忽略，接了只会造成误解。GUI 工作台保留该节点供手动「借情绪」试听。
- `interval_silence_ms` 只管长文本自动分段的段内静默；真正的句间停顿与抢话在后期时间轴，别指望它。
- `loudnorm` 为单遍动态模式；对响度极敏感的成片建议再过一遍两遍式归一化。
- 同一段超过约 20 句时 `amix` 输入数较多，建议按 `shot` 分组混音（脚本已自动另出 `shots/*.wav`）。
- 本流水线**不修改** `2_工作流/` 下任何原版 JSON；GUI 工作台是另存的新文件。
