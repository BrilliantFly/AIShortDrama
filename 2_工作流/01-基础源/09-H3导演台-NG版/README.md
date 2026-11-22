# 09 · H3 导演台 NG 版（seesee75）

> 上游：`github.com/seesee75-commits/ComfyUI-MiniMaxH3-Director` · v1.0.1 · GPL-3.0 · ~350★
> 收录时间：2026-11-16 · 来源提交：main 分支浅克隆快照

这是目前把「多镜头 + 分段续接 + 声音连续」做得最完整的一套 H3 导演台。和 01-H3-导演台通用（AIMixer 版）是两代产品：AIMixer 那套一次 Run 只出约 15 秒，靠手拼；这套由规划器自动切段、自动续接。

## 一、十条工作流对照

| 文件（本库重命名） | 上游原名 | 干什么 | 关键点 |
|---|---|---|---|
| `H3-NG导演台-01-文生视频-三镜.json` | `H3 Director - 1 Text to video` | 纯文本出三镜 + 一句台词 | 最干净的起步模板 |
| `H3-NG导演台-02-角色与声音-图+音频.json` | `2 Characters and voice` | 图定人物身份、音频定嗓音 | 跨段保持同一张脸 |
| `H3-NG导演台-03-音乐视频-锁歌.json` | `3 Music video` | 歌手跟锁定的歌走 | Whisper 对歌词时间 |
| `H3-NG导演台-04-每镜首帧钉图.json` | `4 Shots from pictures` | 每镜严格起于指定图 | 首/尾帧模式 |
| `H3-NG导演台-05-每镜出静态图.json` | `5 Pictures` | 一镜出一张静帧而非视频 | 出分镜板用 |
| `H3-NG导演台-06-故事板-双角色.json` | `6 Storyboard` | 编号分镜板（可 Qwen 画）+ 双角色 | 故事板直送导演台 |
| `H3-NG导演台-07-控制视频-Pose驱动.json` | `7 Control video` | 人物照着另一段视频动（Pose/Edge/Depth/遮罩） | 走官方 H3 ControlNet |
| `H3-NG导演台-08-替换人物-遮罩Inpaint.json` | `8 Inpaint (replace a figure)` | 实拍里的人换成自己角色 | **视频填充/局部重绘主力** |
| `H3-NG导演台-09-自定义采样-原生节点.json` | `9 Custom sampling (advanced)` | 渲染循环改用 ComfyUI 原生采样器 | 要自己调 sigma/采样器时用 |
| `H3-NG导演台-00-Legacy时间线版.json` | `MiniMax H3 Director (Legacy)` | 老时间线导演台，一次 Run ≤15s | 旧工作流兼容入口 |

打开方式：ComfyUI 菜单 → 模板（Templates），搜 `H3 Director`，这十个模板都在；示例素材（图、人声、歌、走路视频及其 pose/mask）会在打开时自动拷进 `ComfyUI/input/`，文件名前缀 `h3-example-…`，不需要手动对路径。

## 二、环境门槛（先看这条）

- **ComfyUI ≥ 0.37.0**（上游用原生 loop 节点，实测版本 0.42）。本机现在是 **0.30.2，打开会大面积红框**，只有 Legacy 那条基本能跑。
- 依赖只多一个 OpenCV：`python -m pip install -r requirements.txt`（用 ComfyUI 自带的 python）。
- 显存：上游实测 16 GB 卡在 `1280×704 + Turbo LoRA` 下可跑；卡小就把渲染段降到 5 s、分辨率降一档。
- 磁盘：H3 权重 + 文本编码器 + VAE 约 **60 GB**。

## 三、模型配对表（错一个就出不了片）

| 用途 | 文件 | 放哪 |
|---|---|---|
| H3 模型 · 首尾帧 / 文生 / 图生 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `models/diffusion_models` |
| H3 模型 · 参考（R2V） | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `models/diffusion_models` |
| 文本编码器（type = `minimax`） | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders` |
| 视频 VAE | `minimax_h3_video_vae_fp16.safetensors` | `models/vae` |
| 音频 VAE | `minimax_h3_audio_vae_fp32.safetensors` | `models/vae` |
| 预览 VAE | `taeh3.safetensors` | `models/vae_approx` |
| Turbo LoRA · 首尾帧 | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | `models/loras` |
| Turbo LoRA · 参考 | `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | `models/loras` |

工作流里自带下载链接，打开时 ComfyUI 会提示缺哪个文件；也可以在 `设置 → Models` 里看导演台列出的全部文件清单（含缺失项）。

## 四、它到底怎么「填」

1. 规划器把你的时间线按 H3 合法帧网格切成一堆 **约 10 秒的渲染段**；
2. 段与段之间是**真续接**——上一段的画面和声音一起接进下一段，不是生成完再拼；
3. 拼合环节是 seam-aware 的，接缝位置和裁剪量用同一份对齐结果，避免各阶段各算一套。

长片参考：官方示例有 **3 分钟**（References 模式）和 **1 分钟**（首尾帧模式）成片。

## 五、四个坑

1. **UNET 不能混**：T2V / I2V / FL2V 用 `fl2va`；R2V / V2V / RV2V 必须 `ref2va`。
2. **CLIP Loader 的 type 必须选 `minimax`**，默认值不是它。
3. **段间引导默认关闭**，要手动开；重叠为 0 帧等于两段独立生成。
4. 爆显存先改三处：`设置 → 渲染段 5 s`、换 int8 视频 VAE、`Resolution → Fast`。

## 六、目录说明

- `_上游文档/GUIDE.md` —— 上游完整图文指南（模型、Studio、卡片、模式、声音、每个设置项、排错），最全，出问题先翻这个。
- `_上游文档/SKILL.md` —— 给 AI Agent 看的安装/排错检查表，让助手代装时直接喂它。
- `_上游文档/docs/NG-*.md` —— NG 各子系统（时间线、镜头、素材、Guide、声音、校验）的分册说明。
- `_上游文档/docs/legacy-director.md` —— Legacy 时间线版说明。
- `_上游原始文件名/` —— 未改名的原始 JSON，对照上游 issue/文档时用。
