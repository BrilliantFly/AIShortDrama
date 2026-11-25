# LoRA 底座与功能详细清单

> 整理时间：2026-11-25
> 范围：本地已安装 5 个 + 候选推荐 228 个（第六至第十七部分累计 228 个，含十二轮 V67概念组件库/黑白单色/间谍青春 15 个）| 末尾汇总部分为全量速查表 + 按场景搭配推荐
> 存放位置：本文件同步存放于 `D:\AIShortDrama\2_工作流\LoRA底座与功能详细清单.md`，与工作流配置同目录便于调取
> 底座判断方法：读取 .safetensors 文件头 metadata（`ss_base_model_version` / `base_model` / `modelspec.architecture`）+ tensor 命名前缀，不依赖文件名

---

## 第一部分：本地已安装的 LoRA（5 个）

### A. Krea2 底座（3 个）— 图像风格 LoRA

存放路径：`D:\AIShortDrama\999_参考\模型\`（未放入 ComfyUI 的 models/loras，当前工作流不会自动识别）

#### 1. 90年代电影感（武侠片）.safetensors — 218 MB

| 项目 | 内容 |
|---|---|
| **底座** | Krea2（训练源 `krea/Krea-2-Raw`） |
| **判断依据** | `ss_base_model_version=krea2`；`modelspec.architecture=krea2/lora`；`ss_sd_model_name=urn:air:krea2:repository:huggingface:krea/Krea-2-Raw@main.tar`；tensor 前缀 `diffusion_model.blocks.*` |
| **具体功能** | 90 年代港式武侠片质感：胶片颗粒、低饱和暖调、钨丝灯内景、复古戏服与布景氛围。纯风格层，不改人物身份与构图 |
| **训练参数** | rank 32 / alpha 32；159 张训练图；epoch 1（step 1800/2000）；bf16；1024×1024；ai-toolkit 0.12.14；Civitai 在线训练 |
| **适用** | Krea2 文生图 / 图生图工作流 |
| **不适用** | H3 视频、Z-Image、SDXL、FLUX |

#### 2. 90年代电影感（美国派）.safetensors — 218 MB

| 项目 | 内容 |
|---|---|
| **底座** | Krea2（训练源 `krea/Krea-2-Raw`） |
| **判断依据** | 同上：`ss_base_model_version=krea2`，`modelspec.architecture=krea2/lora` |
| **具体功能** | 90 年代美式青春片质感：高饱和日光、暖肤色、校园/街景怀旧氛围。与「武侠片」同一训练体系、不同数据集 |
| **训练参数** | rank 32 / alpha 32；362 张训练图；epoch 3（step 1000/2000）；bf16；1024×1024；ai-toolkit 0.12.14 |
| **适用** | Krea2 文生图 / 图生图工作流 |
| **不适用** | H3 视频、Z-Image、SDXL、FLUX |

#### 3. DVD感（强度1.5）.safetensors — 436 MB

| 项目 | 内容 |
|---|---|
| **底座** | Krea2 |
| **判断依据** | `ss_base_model_version=krea2`；`ss_output_name=Krea2_Otherworld Photography`；tensor 维度 `[64, 6144]` → rank 64 |
| **具体功能** | 「异世界摄影 / DVD 感」风格：模拟 DVD 压缩画质、异世感色调与胶片瑕疵。文件名标注推荐强度 1.5（较高，属强风格化） |
| **训练参数** | rank 64；step 1650 / epoch 2；ai-toolkit 0.12.2 |
| **适用** | Krea2 文生图 / 图生图工作流 |
| **不适用** | H3 视频、Z-Image、SDXL、FLUX |

### B. MiniMax H3 底座（2 个）— 视频加速 LoRA（非风格）

存放路径：`D:\ComfyUI-aki-v3.2\ComfyUI\models\loras\`

#### 4. minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors — 1865 MB

| 项目 | 内容 |
|---|---|
| **底座** | MiniMax H3（fl2va） |
| **判断依据** | `base_model=Comfy-Org/MiniMax-H3 minimax_h3_fl2va_bf16.safetensors`；tensor 含 H3 特有的 `qkv_proj.alpha`、`mlp.fc1.alpha`；共 624 tensor |
| **具体功能** | **FL2V（首帧图生视频）8 步 turbo 加速**：把 H3 常规采样压缩到 8 步出片，用于快速样片迭代。功能是「加速」，**不提供电影调色** |
| **训练参数** | rank 128 / alpha 8.0；training_scale 0.0625；由 Diffusers PEFT 转为 ComfyUI generic LoRA；QKV 融合 + SwiGLU 映射已处理 |
| **适用** | minimax_h3_director / H3 图生视频工作流 |
| **不适用** | 图像模型、Krea2、Z-Image |

#### 5. minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors — 1865 MB

| 项目 | 内容 |
|---|---|
| **底座** | MiniMax H3（fl2va） |
| **判断依据** | 同 #4：`base_model=Comfy-Org/MiniMax-H3 ...`，624 tensor，同款 QKV 融合参数 |
| **具体功能** | **R2V（参考图生视频）4 步 turbo 加速**：比 8 步版更快，适合批量试镜/运镜验证。同为「加速」用途，**非风格 LoRA** |
| **训练参数** | rank 128 / alpha 8.0；training_scale 0.0625；v0.1 早期版本 |
| **适用** | minimax_h3_director / H3 参考生视频工作流 |
| **不适用** | 图像模型、Krea2、Z-Image |

---

## 第二部分：候选推荐 LoRA（22 个，按底座分组）

### C. MiniMax H3 视频风格 LoRA（6 个）

> 只有这一类能驱动 H3 视频风格；#4/#5 的 turbo 加速 LoRA 可与风格 LoRA 叠加使用。

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| Minimax H3 Cinematic V2 | MiniMax H3 | 通用电影质感；专项改善肢体稳定、自动剪切、长镜头连续性、高动态拖影 | 无触发词；0.85 | [2890588](https://civitai.com/models/2890588) |
| Minimax H3 Cinematic 官方版 | MiniMax H3 | 抑制塑料感与过锐；长镜头更连贯；武侠/都市/悬疑/广告通用 | 无触发词（已移除 DY）；标准 0.7 / 高动态 0.5 / 低噪 0.6 | [2937734](https://civitai.com/models/2937734) |
| 90s Hong Kong Wuxia Film Style | MiniMax H3 | 90 年代港片武侠：胶片颗粒、低饱和、暖钨丝灯、复古戏服；I2V/T2V 通吃 | `90s_wuxia_style`；画面 0.6，音频 ≤ 0.3 | [2954281](https://civitai.com/models/2954281) |
| CinemaGrade | MiniMax H3 | 电影调色 / 真实感增强，只改画质不改主体 | `cinemagradestyle` 放开头；1.0（ep35 柔和 / ep50 更强） | [2927223](https://civitai.com/models/2927223) |
| 1920s Silent Film（Aged Celluloid） | MiniMax H3 | 1920 年代默片：颗粒、划痕、闪烁、跳帧、化学污渍；三档衰减强度 | `aged_celluloid` + 退化关键词；1.0 | [2968359](https://civitai.com/models/2968359) |
| 16mm Found Footage | MiniMax H3 | 16mm 黑白伪纪录片/恐怖：真实胶片扫描颗粒、深焦无虚化、手持晃动 | `foundfootage16` 开头；0.8–1.0 | [3015094](https://civitai.com/models/3015094) |

### D. Krea2 图像风格 LoRA（3 个候选）

> 与本地已装的 3 个同底座。Civitai 上 Krea2 已是个独立生态（约 13K LoRA），注意只下标注 Krea2 的版本。

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| V67 Film Noir | Krea2（另有 FLUX 版） | 1940–50s 黑色电影：高对比明暗法、硬主光、百叶窗阴影、烟雾 | `film noir style` + 2–4 个 noir 词 | [3010470](https://civitai.com/models/3010470) |
| V67 National Geographic | Krea2（另有 FLUX 版） | 国家地理纪实摄影：黄金时刻、自然光、环境叙事、超细节纹理 | `(National Geographic:1.3)` + 纪实词 | [2554517](https://civitai.com/models/2554517) |
| YFG Obs | Krea2（另有 Flux.2 Klein 版） | 暗黑电影高对比情绪：深阴影、主体隔离、工业/反乌托邦基调 | `YFG-Obs style`；1.0–1.25 | [2413599](https://civitai.com/models/2413599) |

### E. Z-Image Turbo 图像 LoRA（11 个）

> 用于三视图 / 角色资产。底座为 ZImageTurbo，与 Krea2、H3 互不通用。

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| Cinematic Shot | ZImageTurbo | 通用宽银幕电影感，社区评分极高 | 无触发词，`cinematic` 即可 | [432586](https://civitai.com/models/432586) |
| Cinema01 | ZImageTurbo | 宽银幕叙事构图：noir/科幻/惊悚/动作 | `cinema01`，1.0 | [2515897](https://civitai.com/models/2515897) |
| Cinematic Slider (Stackable) | ZImageTurbo | Rank1 电影感滑块，10MB，可与风格 LoRA 叠加 | 无触发词，2.0–12.0（3–4 起） | [2599083](https://civitai.com/models/2599083) |
| Cinematic Photography | ZImageTurbo | 电影摄影 / 人像 / 时尚 | `c1n3m4t1c`，0.9 | [2905465](https://civitai.com/models/2905465) |
| Lumacore Dark Fantasy V3 | ZImageTurbo | 暗黑奇幻 / 赛博朋克 / 霓虹体积光 | `lumacore`，0.7–1.0 | [2506381](https://civitai.com/models/2506381) |
| V67 Film Noir | ZImageTurbo（另有多底座版） | 1940–50s 黑色电影硬光百叶窗阴影 | `film noir style` + noir 词 | [3010470](https://civitai.com/models/3010470) |
| Cinematic Portrait Lighting | ZImageTurbo + SDXL 双版 | 人像布光：方向光、深阴影、高对比面部光 | `cinelightX` / `velatrix`，0.5–1.0 | [2595570](https://civitai.com/models/2595570) |
| Cyberpunk 50s | ZImageTurbo | 1950s 复古未来主义：Kodachrome 调色、镀铬与霓虹 | `cy50s`，0.7–1.0；shift 7.0 / dpmpp_2m+sgm_uniform / 8 steps | [2459421](https://civitai.com/models/2459421) |
| Retro Photography Filter | ZImageTurbo | 做旧：棕褐/黑白、划痕、灰尘、褪色对比 | `RetroPhotographyFilter`，0.4–1.0（须指定 sepia 或 B&W） | [2543934](https://civitai.com/models/2543934) |
| YFG ChatGPT 4o Style | ZImageTurbo | 暗调电影感 + 克制胶片颗粒 | 无触发词，0.8 最佳 | [1470117](https://civitai.com/models/1470117) |
| ta86_Chromatic Sin Circuit | 多底座（ZIT/Flux/SDXL） | noir + 赛博几何风格化，材质由光与几何定义 | `csinc`，0.6–1.0 | [2285571](https://civitai.com/models/2285571) |

### F. FLUX / SDXL 图像 LoRA（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| FLUX.1-dev-LoRA-Cinematic | Flux.1 D | 两套风格：`cinematic_1940s` 黑白 noir / `cinematic_octane` 现代暖调梦幻胶片 | 对应触发词 | [1351798](https://civitai.com/models/1351798) |
| Technically Color Flux | Flux.1 D | 1950–60s 经典胶片色彩：高饱和、浓郁明暗、梦幻质感 | `t3chnic4lly`，0.7–0.9 | [1791850](https://civitai.com/models/1791850) |
| Cinematic Nostagia | Flux.1 D | 怀旧胶片色调、低光氛围、雾气街景 | `in the style of cinnem3n` 放末尾；cfg 1.5–2，30–40 steps | [2244145](https://civitai.com/models/2244145) |
| psxFilm | Flux.1 D | 胶片摄影风格（18MB 轻量） | `psxfilm` | [2036457](https://civitai.com/models/2036457) |
| Technixl Classic Cinema Color | SDXL 1.0 | 中世纪彩色胶片调色层：饱和原色、暖肤色、哑光暗部 | `technixl` | [2193235](https://civitai.com/models/2193235) |

---

## 第三部分：底座兼容性矩阵

| LoRA 底座 ↓ \ 底座模型 → | Krea2 | MiniMax H3 | Z-Image Turbo | FLUX.1 D | SDXL |
|---|---|---|---|---|---|
| **Krea2** | ✅ 可用 | ❌ | ❌ | ❌ | ❌ |
| **MiniMax H3** | ❌ | ✅ 可用 | ❌ | ❌ | ❌ |
| **Z-Image Turbo** | ❌ | ❌ | ✅ 可用 | ❌ | ❌ |
| **FLUX.1 D** | ❌ 需单独 Krea2 版 | ❌ | ❌ | ✅ 可用 | ❌ |
| **SDXL** | ❌ | ❌ | ❌ | ❌ | ✅ 可用 |

**关键规则**：
- Krea2 与 FLUX 架构相近但 tensor 维度/命名不同，**不能混用**，必须下载作者单独发布的 Krea2 版本。
- H3 是视频 DiT，与所有图像模型完全不兼容。
- 同名不同底座的例子很多（如 V67 Film Noir 同时有 Krea2 / ZIT / FLUX 三版），下载时必须核对 Base Model 字段。

---

## 第四部分：如何自行判断一个 LoRA 的底座

1. **读文件头 metadata**（最可靠）：
   - `ss_base_model_version` → krea2 / flux / sdxl / z-image 等
   - `modelspec.architecture` → 如 `krea2/lora`
   - `base_model` → H3 的 turbo LoRA 会写明 `Comfy-Org/MiniMax-H3`
   - `ss_sd_model_name` → 训练源模型，可反推底座
2. **看 tensor 命名前缀**（metadata 缺失时）：
   - `diffusion_model.blocks.*.attn.gate/wq/wk/wv` + `txtfusion` → Krea2 / FLUX 系
   - `diffusion_model.blocks.*.attn.qkv_proj.alpha` + `mlp.fc1.alpha` → MiniMax H3
   - `lora_unet_*` / `lora_te*` → SDXL 系
3. **看文件大小辅助判断**：
   - Krea2 rank32 ≈ 218 MB，rank64 ≈ 436 MB
   - H3 rank128 turbo ≈ 1865 MB
   - Z-Image 常见 162 MB / 302 MB
4. **验证方式**：在 ComfyUI 用 `LoraLoaderModelOnly` 加载，底座不符会直接报错或不生效。

---

## 第五部分：使用注意事项

1. **本地 3 个 Krea2 LoRA 目前无法使用**：它们放在 `999_参考\模型\`，未进入 ComfyUI 的 `models/loras/`；且 Krea2 底座模型、qwen3vl_4b 文本编码器、seedvr2 放大器均缺失，需补齐这三项。
2. **视频 ≠ 图像**：H3 工作流要视频 LoRA；图像 LoRA 只能作用于首帧/参考图。
3. **三视图一致性**：风格 LoRA 会改脸型/光照，应放在 inswapper 换脸之前，强度压 0.4–0.6。
4. **H3 音频权衡**：风格 LoRA 权重 >0.3 易引发音效失真；追画面就调高权重并关闭音频，后期配音。
5. **颗粒保真**：胶片颗粒是编码器最先丢弃的信息，导出用 CRF≤16 + `-tune grain`。
6. **授权范围**：MiniMax H3 LoRA 受 H3 Community License 约束，授权排除欧盟、英国、韩国、美国。

---

## 第六部分：补充清单（2026-11-25 二轮挖掘，8 个新增）

> 重点补充 Krea2 生态（你本地三个 LoRA 的底座）和几个实用款。以下均为页面明确标注底座，非本地实测。

### G. Krea2 图像 LoRA 新增（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| Cinematic Krea2 | Krea 2 | 地下城/夜间纪实电影感：低调荧光、明显胶片颗粒、烟雾、深黑+红色灯带点缀、gritty 35mm | 无需触发词；1.0；7000 steps | [2904880](https://civitai.com/models/2904880/cinematic-krea2) |
| Krea 2 Dead Light Style | Krea 2 | 1940–50s Kodachrome/Autochrome 褪色：琥珀锈色+紫红阴影、重颗粒、水渍裂纹、低调单光源长阴影；适合静物/复古室内/惊悚氛围板 | `ddlt_style`；2000 steps/10 epochs | [2874810](https://civitai.com/models/2874810) |
| CineVivid | Krea 2（另有 MiniMax H3 Image beta 版） | 只改观感不改主体：方向光、深对比、材质强化（湿沥青/缎面/黄铜/玻璃/蒸汽/皮肤）。**Krea2 版 rank32/10000 steps**；H3 版为图像 beta、7350 steps | `cinevivid` 开头（可选）；0.55–0.75 推荐（1.0 会过锐）；Euler+Simple，8–10 steps，CFG 1，配 Krea2 Turbo + qwen3vl 4b + qwen image vae | [3059975](https://civitai.com/models/3059975/cinevivid) |
| Experimental Vintage Film | Krea 2 | 复古收尾：色差、电影噪点、褪色，常作副 LoRA 叠在主风格上。权重 -1≈动漫 / +1≈复古胶片，0.5 平衡 | 无明确触发词；0.5 起；441.81 MB（rank64 级） | [2971561](https://civitai.com/models/2971561) |
| VASILIY ANDREEV 电影 noir 人像 | Krea2 | 电影剧照式 noir 人像：伦勃朗光/分割光、戏剧化阴影、去饱和 teal-amber、50/85mm f1.2 浅景深、胶片颗粒 | `cinematic portrait photography in the style of Vasiliy Andreev` 等；0.95–1.0；8 steps + Euler A + Bong Tangent（保颗粒防过锐） | [3037684](https://civitai.com/models/3037684) |

### H. MiniMax H3 视频 LoRA 新增（1 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| Minimax H3 Cinematic Look（解决张量报错） | MiniMax H3 | 真实电影质感，专项解决塑料感/过锐/生硬光照/AI 味；20000 steps。与官方版同源但保留触发词 | `DY`；0.7（标准）/ 0.5（高动态）；147.92 MB | [2908686](https://civitai.com/models/2908686) |

> 说明：与官方版（[2937734](https://civitai.com/models/2937734)，591 MB，已移除触发词）功能相近，区别在于触发词与体积。官方版更省事，这个适合想手动控制触发词或用旧工作流的情况。

### I. Z-Image Turbo 图像 LoRA 新增（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| Nostalgic Cinema | ZImageTurbo | 80s–90s 复古电影/电视质感：需叙事性长提示词（年代+摄影介质+服装+光线），越具体越好；皮肤水珠、轻颗粒、自然肤色 | 注入 `1980s/1990s, cinematic scene, color film, slight film grain` 等年代词 | [2143490](https://civitai.com/models/2143490) |
| Film Grain & Muted Cinematic Color Grading | ZImageTurbo（另有 Krea2 版） | 收尾型风格：细腻胶片颗粒+低饱和电影调色+柔和亮部滚降+自然对比；不改主体构图，适合统一整批图调性 | 0.7–1.0；648.81 MB（rank64 级）；写实/摄影底模效果最佳 | [2787410](https://civitai.com/models/2787410) |

### J. 本轮挖掘的关键发现

1. **Krea2 生态已成熟**：Civitai 上 Krea 2 有约 13K LoRA、72M+ 生成图。Raw（无蒸馏、全引导，约 52 steps/CFG 3.5）和 Turbo（8 步、无 CFG）两个开源权重；**在 Raw 上训练的 LoRA 可直接迁移到 Turbo 上跑**，这是 Krea2 生态的重要特性。
2. **跨底座双发成常态**：CineVivid（Krea2 + H3 Image beta）、Film Grain & Muted（ZIT + Krea2）、V67 系列（多底座）——下载时务必选对版本标签。
3. **CineVivid 有 MiniMax H3 Image 版**：目前是早期 beta、仅 SFW，属**图像** LoRA 而非视频 LoRA；若你要的是 H3 视频风格，仍应用第六部分 H 组或第二部分 C 组的视频 LoRA。
4. **Krea2 可用的完整配置链**（来自 CineVivid 实测）：Krea 2 Turbo fp8 底座 + qwen3vl 4b fp8（type=krea2）文本编码器 + qwen image vae + Euler/Simple 8–10 steps/CFG 1。这正好对应你此前缺失的那几件文件。

---

## 第七部分：跨底座扩展清单（2026-11-25 三轮挖掘，20 个新增）

> 本轮不再局限于你当前模型，把 Qwen Image 2.1 / Flux.2 Klein 9B / Wan 2.2 / HunyuanVideo 等新底座的优质电影风格 LoRA 一并纳入；同时发现大量"一个 LoRA 多底座通吃"的系列，单独标注。

### K. 「一个 LoRA 多底座」系列（重点推荐，省下载量）

> 这类 LoRA 的作者会为每个底座单独导出一份文件，风格一致。你只需按手上有的底座下对应版本。

| 系列 | 功能 | 可用底座 | 触发词 / 强度 | 链接 |
|---|---|---|---|---|
| **GrainScape UltraReal V2** | 复古胶片/模拟摄影：Kodak Tri-X 风格深颗粒、B&W 强反差、自然浅景深；2048 训练，V2 修复重复脸和竖条纹 | Qwen2.1 / Krea2 / Z-Image Turbo / Flux.dev / Moss，共 5 版 | Qwen2.1 版 0.7；ZIT 版 0.85–0.9 + guidance 3.5 + res2s_ode/res2m_ode + beta | [1332651](https://civitai.com/models/1332651) |
| **1950s Scifi Movies** | 50 年代科幻片：宇航服、笨重机器人、月球地貌。窄训练但风格纯正 | Krea2 / Flux.2 Klein 9B / ZIT / HunyuanVideo 1.5 / Wan 2.2 T2V 14B(Low+High) / Diffusers / Comfy，共 8 版 | `50s_scifi`；Wan 用 25 steps(15/10)、0.8 强度、dpm++_sde | [1359530](https://civitai.com/models/1359530) |
| **1980s SciFi Movies** | 80 年代模拟感赛博朋克/太空（刻意不训练太空歌剧）。Krea2 用 "futuristic" 别用 "cyberpunk" | MiniMax H3 FL2V / ZIT / Krea2 / HunyuanVideo / Wan 2.2 T2V 14B(Low+High) / Diffusers | 0.9；Krea2 避开 cyberpunk 标签 | [1802714](https://civitai.com/models/1802714) |
| **Cinematic Shot (zylo)** | 通用电影感宽银幕，社区 809 评价"压倒性好评" | Krea2（zy_Cinematic_Shot_K2）/ Z-Image Turbo / XL / FLUX 共 4 版 | `zy_cinematic`（可选）；训练于风景图 | [432586](https://civitai.com/models/432586) |
| **Cinematic Photography (c1n3m4t1c)** | 用高质量电影摄影照片训练（非模糊剧照），出图清晰不糊 | ZIT / Qwen 2512 / Flux.2 Klein 9B 共 3 版 | `c1n3m4t1c`；Qwen 版 0.8；Klein 版 1.0 | ZIT[2905465](https://civitai.com/models/2905465) / Qwen[2885438](https://civitai.com/models/2885438) / Klein[2842250](https://civitai.com/models/2842250) |
| **Candid Film** | 胶片写真写实风，1000 张高质量图 + Gemini 3 Flash 打标 | Flux.2 Klein 9B / Chroma 双版 | 无需触发词；analog/vintage/film 有助于生效 | [2313101](https://civitai.com/models/2313101) |
| **ta86 Dustbound Grit Western** | 西部片：黄金日光、沙尘、画笔质感、牛仔帽左轮酒馆、半写实 | SDXL / Flux / Z-Image（SDXL+ZIT 同触发词） | `dustbound_grit`；SDXL 0.4–0.8 / Flux 1–2（推荐 2.0） | [2188885](https://civitai.com/models/2188885) |
| **V67 Film Noir** | 1940–50s noir（前册已列，这里补充其多底座属性） | Krea2 / FLUX（Schnell/Dev/Pro）/ Moss 等 | `film noir style` + 2–4 noir 词 | [3010470](https://civitai.com/models/3010470) |

### L. Krea2 底座新增（港片/武侠/镜别控制 —— 与 EP001 高度相关）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Wong Kar-wai Movie Cinematic Style** | Krea 2 | 王家卫/杜可风 90s 港片：碎片化轮廓光、高光泛光雾、湿玻璃、框中框、融化散景、漏光暗角；男女通用无固定脸；适合茶餐厅/雨街/出租车后座/隧道/复古室内 | `wkw1`；0.6–0.75（浓烈情绪 0.8–0.9）。负面词：clean sharp lighting, oversmooth skin, perfectly round bokeh | [3023454](https://civitai.com/models/3023454) |
| **90s Movie Grit — Martial Arts Mayhem** | Krea 2 | 90 年代功夫片粗粝感：约 300 帧手选电影画面，复刻颗粒/配色/构图，附带怪物强化 | `mamay style`（可选）；1920×880、8 steps、CFG1、Euler/Simple、强度 1.35 | [2833506](https://civitai.com/models/2833506) |
| **Krea2_PhantomLight_HanfuPhoto** | Krea2 Turbo | 汉服/敦煌飞天/武侠女侠东方美学：35mm 胶片、体积光、刺绣与银饰细节、竹林雨檐对决；也含赛博哥特汉服 | `PhantomLight, HanfuPhoto, cinematic 35mm film photography`；0.8–1.0（默认 0.85），8 steps、CFG1、Euler/DPM++2M，832×1216 或 1024×1536 | [2817414](https://civitai.com/models/2817414) |
| **Krea2_ShadowWuxia_Realism** | Krea2 Turbo | 暗黑武侠男性/BJD 瓷面武士：传统深色长袍、皮甲肩甲、低调打光、雾、轮廓光；可直接 4K | `shadow wuxia realism, male wuxia warrior, bjd male doll, dramatic shadow lighting`；0.8–1.0，8 steps、CFG1 | [2847913](https://civitai.com/models/2847913) |
| **Sergio Leone Style Portraitizer** | Krea 2 RAW | 意大利式西部片：强直射阳光+深对比阴影、35mm 颗粒、1960s Technicolor 琥珀色调；可迁移到现代题材/赛博朋克 | `trg_Sergio, in sergioleone style` + 光线词；1.0–1.4（自适应学习率抗烧） | [2951227](https://civitai.com/models/2951227) |
| **Forgotten Cinema — Technicolor Dreams** | Krea 2（另有 H3 配套） | 1940–70s 老电影：色彩分离、年代布光、古典构图、绘景幕布、制片厂质感；刻意抑制"现代脸+复古滤镜"违和 | 触发词可选（建议先不用）；配 Krea2 Rebalance 1.0 + 提示加 `cinematic`；可直接写年代 | [2981349](https://civitai.com/models/2981349) |
| **Astro Cinema V02** | Krea 2 | **镜头/构图控制型**：近景→极远景、航拍、荷兰角、建立镜头、高/低角度、过肩、俯拍，含电影打光与颗粒/光晕/调色 | `ASTROCINEMAV01K2T` 放开头；1.0；1852 张标注图训练 | [2831431](https://civitai.com/models/2831431) |
| **CineShot** | Krea 2 | 叙事构图/紧致取景/低 key 色调/负空间；收尾型风格，适合安静细节与人物 | `frameveil cinematic style`；0.65–1.0，Euler/Simple | [3020428](https://civitai.com/models/3020428) |
| **V67 Ultra Vision** | Krea 2 | 超电影感 HDR：体积光/上帝光、微对比、浅景深变形宽银幕、光线追踪反射、次表面散射；指定表面与光源效果最佳 | `(Ultra Vision:1.2)` 必须放开头；0.85；负面词排除 flat lighting / overprocessed HDR halos；1–2 主体最佳 | [3047373](https://civitai.com/models/3047373) |

### M. Qwen Image 2.1 底座新增（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Dot Film — Hard Flash & Gritty Film Grain** | Qwen Image 2.1 | 夜间人像/暗街：硬闪光灯 + 粗颗粒；三档 checkpoint(500/750/1000) 可对比 | 无触发词；1.0；1024×1024、40 steps、Euler/Simple、CFG 1（街景可 2–3） | [2999989](https://civitai.com/models/2999989) |
| **Krea2 35mm Film Texture & Realism** | Qwen Image 2.1 | 35mm 电影质感：皮肤毛孔、织物纹理、自然高光/阴影滚降、去除塑料感；**完整保留 T2I + 多图编辑 + 角色一致性 + 文字渲染**；零触发词 | 无需触发词；384 blocks 全训练 | [3010645](https://civitai.com/models/3010645) |
| **Cinematic Control [Qwen]** | Qwen | 增强电影感（工具型） | 0.5–0.8 | [2375886](https://civitai.com/models/2375886) |

### N. Flux.2 Klein 9B 底座新增（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Movie Clips** | Flux.2 Klein 9B | 电影片段截图质感：带胶片噪点与模糊；两个权重文件（660/880 steps） | `CinematicMovieClip`；79 MB | [2351523](https://civitai.com/models/2351523) |
| **Grit & Glamour** | Flux.2 Klein 9B-base | 强个性角色：写实+风格化电影打磨、皮肤/配饰/眼神细节、戏剧化轮廓光；金饰/链/眼镜/皇冠等配饰擅长 | 无明确触发词；290 steps/10 epochs | [2534861](https://civitai.com/models/2534861) |
| **Klein Cinematic Animation / Realistic Slider** | Flux.2 Klein 9B | **概念滑块**：现实↔3D 电影动画风格双向转换，I2I/T2I 均可 | 0–2.5（满效果）；19.78 MB | [2332400](https://civitai.com/models/2332400) |

### O. 视频模型 LoRA 新增（Wan 2.2 / HunyuanVideo，3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **1950s Scifi Movies（Wan 2.2 版）** | Wan Video 2.2 T2V-A14B（Low+High 双文件） | 50 年代科幻；**Low noise 文件对风格影响最大**；25 steps(15/10)、0.8、dpm++_sde，High 用 Q4 gguf / Low 用 Q6 | `50s_scifi`；585 MB | [1359530](https://civitai.com/models/1359530) |
| **Atmospheric Artistic Styles — MistForge** | Hunyuan Video | 体积光/漏光/雾/烟/光束、冷调薄雾与热蒸汽；非传统胶片风格，专攻氛围电影感 | 触发词见页面；0.8；307 MB | [1266246](https://civitai.com/models/1266246) |
| **1980s SciFi Movies（Hunyuan 版）** | Hunyuan Video | 80s 模拟赛博朋克；避坑：Krea2 别用 cyberpunk 标签、ZIT 别用 space station、Hunyuan 喜欢现代 ISS 素材但 futuristic soldier 会像 Halo | 0.9；312 MB | [1802714](https://civitai.com/models/1802714) |

### P. SDXL / Z-Image 经典款补录（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Japanese Film Style** | ZImageTurbo | 日式胶片：自然轻颗粒、暖色调、怀旧氛围，人像/风景通用；个人使用非商用 | `日式胶片风`；0.6–0.8，约 15 steps | [2345235](https://civitai.com/models/2345235) |
| **Wizard's Vintage Cinematic Scene** | SDXL 1.0 | 粗粝电影场景、黑白胶片；**偏黑泽明电影**（有日本文化倾向，非目标题材可在负面词加 asian/japanese）；1536×1152 训练 | `vintage cinematic scene`（+ `black and white photo`）；PixelWave 10 底模、Euler+Align Your Steps、20–30 steps、CFG 5–7 | [498945](https://civitai.com/models/498945) |

### Q. 本轮关键发现

1. **"多底座系列"是最大机会**：GrainScape、1950s/1980s Scifi、Cinematic Shot、Cinematic Photography、Candid Film、ta86 Western 都用同一风格分别导出各底座版本。你换底座也能复用同一审美，不必重新找风格。
2. **王家卫风格 LoRA 已有 Krea2 版**（wkw1，223 MB）——跟 EP001「同学会暗恋」的情绪调性高度契合，且 Krea2 是你本地已有 LoRA 的底座，补齐底座模型后可直接用。
3. **港片/武侠 Krea2 集群**：90s Movie Grit、PhantomLight Hanfu、ShadowWuxia、Sergio Leone、Forgotten Cinema Technicolor —— 这一组几乎覆盖 EP001 的所有视觉方向。
4. **镜头控制型 LoRA**（Astro Cinema V02 / CineShot）与你关心的"机位/运镜"直接相关：前者明确训练了航拍、荷兰角、建立镜头、过肩、俯拍等镜头语言，可替代纯文字描述。
5. **Qwen Image 2.1 值得关注**：Krea2 35mm Texture 那款明确保留多图编辑/角色一致性/文字渲染，适合角色连续性要求高的场景；Qwen 底座生态正在快速起量。

---

## 第八部分：港台电影 / 外国科技大片 / 更多类型（2026-11-25 四轮挖掘，23 个新增）

> 本轮按「地域片种 + 电影类型」维度扩充：香港动作片、港台/东亚胶片审美、外国科技大片（银翼杀手/科幻史诗）、动画电影（吉卜力系）、武士时代剧，以及通用电影镜头与调色工具。均为页面标注底座，非本地实测。
> 与 EP001 最相关的仍集中在 Krea2 组——补齐底座后可直接用。

### R. 香港电影 / 港式动作片（1 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Hong Kong Action Cinema style** | SDXL 1.0 | 80–90 年代香港动作片：枪战、爆破、街头追车、警匪对峙。训练自大量老港片。已知副作用：易偏绿、偶尔出现周润发脸 | `Hong Kong action cinema style`；建议叠 Kodak Motion Picture Film 0.4–0.5 校正偏绿，或负面词加 green / Chow Yun-fat | [361831](https://civitai.com/models/361831) |

> 补充：同作者的 Cinematic 系列还有 Dutch Angle（荷兰角）、Split Screen（分屏）、Low/High Angle（低/高角度）、POV、Split Diopter（深浅对焦）、Music Video 等镜头语言 LoRA，需要控镜头时可去作者主页翻。

### S. 港台 / 东亚胶片审美（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **TJFilm Style V2** | Krea 2（另有 Z-Image 版） | 中文作者训练，模拟真实胶片摄影：强化光影、质感与近景景深，人像皮肤呈胶片通透感、去 AI 塑料感。V2 颗粒更稳定 | `vifilm`；1.0；Euler+Simple 或 ddim_uniform，25 steps、CFG 3；想加颗粒可补 `film grain`，但避免堆砌风格词 | [2840370](https://civitai.com/models/2840370) |
| **Ray Krea2 Style Loras（合集）** | Krea 2 | 一个页面多款东亚向风格：① `cinematic film style` — Kodak Vision3 250D + 徕卡味，东亚强化/中国元素；② `Fujifilm style` — 日系胶片、亚裔强化；③ `Hisoul style` — Higgsfield Soul，艺术感性；④ `Photography style` — 通用视觉冲击；⑤ `Lotus Blossoms` — 稳定肢体、增强东亚女性（0.15–0.8）。另外有丝袜/连裤袜语义修复 LoRA | 均无触发词；0.4–1.2（推荐 1） | [2802215](https://civitai.com/models/2802215) |
| **Midjourney Japanese Girl** | Krea 2 | 日系女性人像：柔和胶片色、暖侧光、深阴影、背景虚化与典型「MJ 脸」；附 Contax T2 / Leica M6 / Canon R5 等多款相机预设句 | `mjjpg` 开头；0.8–1.0；qwen3vl_4b + qwen_image_vae，8 steps、CFG1、Euler/Simple，832×1248 | [3004496](https://civitai.com/models/3004496) |

### T. 外国科技大片 / 科幻电影（7 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Blade Runner 2049** | Flux.2 Klein 9B | 74 帧精挑画面训练，复刻银翼杀手 2049 世界：赛博朋克氛围、粗野主义未来建筑、阴郁打光调色、反乌托邦色调。短提示词即可生效 | 无需触发词；长描述效果更好；316 MB | [2420155](https://civitai.com/models/2420155) |
| **Blade Runner (1982)** | Flux.2 Klein 9B | 1982 原版：雨夜湿街、霓虹、烟雾、粗粝质感、层次丰富的城市细节。避坑：F2K9B 底模讨厌 `Android` / `Sheep` 两词 | 无需触发词；长描述效果更好；316 MB | [2436395](https://civitai.com/models/2436395) |
| **Orion Expedition** | Krea 2 | 硬科幻大片：遥远行星、未知世界探索、巨型飞船、太空战、外星人、赛博城市、生化人。风格灵活不锁死，需自己写细节提示 | er_sde + Simple；0.9–1.0；Krea2 Rebalance 节点可选（约 80% 成功样本没用） | [3003215](https://civitai.com/models/3003215) |
| **Lumen Blockbuster Experience** | Krea 2 | 现代院线大片质感 + 写实增强，定位「给每个场景一点电影感」。设计为可与其它 LoRA 叠加，与 Orion Expedition 搭配尤佳 | 示例图元数据含工作流；447 MB（fp32），可配 krea2RealVae_v10 | [3006646](https://civitai.com/models/3006646) |
| **Pure Cinema (Preview)** | Krea 2 | ARRI/好莱坞专业电影摄影：电影肖像、氛围光与构图、可供视频模型动画化的起始帧与分镜。预览版（正式版待众筹） | `c1nem4tic`；触发词必需；1.46 GB、768 tensors；显存最低 1.3 GB / 推荐 2.7 GB | [3012562](https://civitai.com/models/3012562) |
| **V67 Synthography** | Krea 2（V2 另有 Flux / Ernie 版） | 雨夜合成美学：雨滴变铬、霓虹化雾，受维伦纽瓦（银翼杀手2049/沙丘）、Gregory Crewdson、Ridley Scott 影响。雨势可用 gentle rain / heavy downpour 等词控制 | `(Synthography:1.2)` 放开头；0.85；负面词必须排除 bright / sunny / vibrant；1–3 主体最佳 | [2811717](https://civitai.com/models/2811717) |
| **Singularity OmniCine V1** | LTX-Video 2.3 22B（视频） | 视频模型 LoRA：首帧/尾帧控制、参考图生视频、按文本时间线精确切镜（0–5s 分段），修复手指脚趾畸变、口型与「AI 僵硬感」，兼容 2D/3D/超写实 | 需按专属「电影时间线结构」写提示（场景→动作时间线→镜头时间线→环境→对白→音频）；权重 0.8–1.0；建议 ltx-2.3-22b-distilled-1.1_fp8 | [2610733](https://civitai.com/models/2610733) |

### U. 动画电影 / 吉卜力系（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Retro Ghibli (Porco Rosso)** | Krea2 / Klein 9B / Qwen2512 / Qwen / Flux / Anima（6 版） | 《红猪》风格：复古、颗粒更重、色彩更低饱和。作者另有《魔女宅急便》近亲版 | `ghibli style`；Krea2 1.0；Klein 9B 4 steps/CFG1；Qwen 用 Lightning 5 steps/CFG1 | [1153088](https://civitai.com/models/1153088) |
| **Dark Ghibli Fairytales** | 超多底座（Krea2 / ZIT / ZIB / Qwen2.1 / Klein9B / Flux / Wan2.2 T2I / Chroma / Illustrious / Pony / SDXL 等 20+） | 吉卜力 × 暗黑童话：水彩背景 + 赛璐璐角色、空灵光、奇幻自然、诡秘而迷人；受宫崎骏、Brian Froud、Kay Nielsen 影响 | `Studio Ghibli Dark Fairytale`；0.8；2000 steps | [1349631](https://civitai.com/models/1349631) |
| **Princess Kaguya style** | Krea2 / Klein9B / Flux / Qwen2512（4 版） | 高畑勋《辉夜姬物语》：手绘线条、柔和留白、水墨质感；Krea2 版强度偏高 | `kaguya style`；Krea2 1.0–1.5；Klein 9B 1.0–1.2，4 steps/CFG1 | [837740](https://civitai.com/models/837740) |
| **V67 Ghibli Look** | Krea 2 | 把吉卜力美学**翻译进写实摄影**（不是动画）：云如角色、光不刺眼、自然有呼吸感、建筑与地貌共生、对从未去过之地的乡愁 | 触发词组可组合：`ghiblume`（核心）+ `soffione`（日常魔法）+ `miyazake`（朦胧梦境）+ `nimbusoft`（云）+ `pastelskies` + `lushverdant` + `horizonwhisper` | [2431791](https://civitai.com/models/2431791) |
| **Studio Ghibli by Fortnox** | Krea 2 | 泛吉卜力：手绘动画、浓郁手绘背景、柔自然光、温和不艳的色彩。提示搭配 rolling clouds / golden hour / cozy interior / flying machine | `ghibli_style`；1.0；2000 steps/10 epochs | [2882798](https://civitai.com/models/2882798) |

### V. 武士 / 时代剧（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Samurai Cinema Realism** | 页面未标注（参数含 CLIP Strength，推测 SDXL/SD1 系，下载前核对） | 1950–60 年代「剑斗时代剧」：高反差黑白、银盐颗粒、冷峻孤独的武士道美学，强调锐利目光与真实面部细节 | 模型强度 0.55–0.6；CLIP 0.7；dpmpp_2m_sde_karras、30 steps、CFG 5 | [2509629](https://civitai.com/models/2509629) |
| **Ghost Dog: The Way of the Samurai (1999)** | Krea 2 | 1999 年吉姆·贾木许电影：低饱和土色（棕/灰/褪色绿）、柔散射光、中景与略低机位、安静张力 | `ghstdgwysm1999`；1.0（可下调与其他 LoRA 融合）；2000 steps/2 epochs | [2956451](https://civitai.com/models/2956451) |

### W. 通用电影镜头 / 调色工具（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Cinematic Movie Still** | Krea 2 | 电影剧照质感：变形宽银幕镜头光晕、情绪化调色、浅景深、真 35mm 轻颗粒；硬轮廓光、画内实用光源、三分法构图、负空间 | `cinematic movie still`；1.0；用横向画幅、场景式提示；3400 steps | [2840790](https://civitai.com/models/2840790) |
| **Cinematic Color Grading / Color Scheme** | ZIB / ZIT / XL / F1D 多版 | 可调用光线/色调词：`cinematic film style` + 黑白/日光/月光/暖光/冷光/任意颜色主题；既能调色也能配色方案 | 按提示词选择光线词；0.5–1.2 自调 | [541698](https://civitai.com/models/541698) |
| **cinematic feeling** | Illustrious | 概念型：注入电影布光、氛围与纵深但不破坏原画风。Neutral 版保风格，Dramatic 版（LoKr）更暗更有戏剧性 | `cinematic feeling`；Neutral 0.7–0.9 / Dramatic 0.6–0.8；可叠 volumetric lighting / rim light / lens flare | [2144422](https://civitai.com/models/2144422) |
| **Cinematic Slider – Stackable** | ZImageTurbo | Rank 1 滑块，几乎不与其他 LoRA 抢权重。2–4 轻微优化；5–7 构图收紧、景深加深；8–10 全电影感（老胶片调色） | 无触发词；推荐 2.0–12.0（起始 3–4）；仅 10 MB | [2599083](https://civitai.com/models/2599083) |
| **Technicolor Style** | Krea 2 / ZIT 双版 | 黄金时代好莱坞：自然胶片颗粒、柔和电影布光、温暖浓郁的中世纪色彩，适合经典爱情/西部/年代剧/复古科幻 | `technic0lou_r`；Krea2 0.8–1.2 / ZIT 0.5–0.8；175 MB | [2629410](https://civitai.com/models/2629410) |

### X. 本轮关键发现

1. **港片资源分两代**：H3 版（90s Hong Kong Wuxia，62 MB，视频用）与 SDXL 老款（Hong Kong Action Cinema，870 MB，图像用）。后者是 2024 年训练的经典款，偏绿需校正；你要港式警匪/枪战可用它，要武侠仍优先 H3 或 Krea2 的王家卫/90s Grit。
2. **「导演名 + 电影名」类 LoRA 正在增多**：Blade Runner 82/2049、Ghost Dog、红猪、辉夜姬等都以单部电影帧训练，风格纯正但题材窄，适合做风格参考板而非通用调色。
3. **跨底座系列又添两支**：Dark Ghibli Fairytales（20+ 底座）、Retro Ghibli（6 底座）、Technicolor（Krea2+ZIT）——再次印证「换底座不换审美」的选 LoRA 策略。
4. **两套「吉卜力」完全不同**：Retro Ghibli / Kaguya 是真动画风格；V67 Ghibli Look 是把吉卜力光感翻译到**实拍摄影**——后者更适合 EP001 的真人向场景。
5. **LTX OmniCine 是少数带「时间线切镜」的视频 LoRA**：如果你的 H3  workflow 之后要换视频底座，这套按秒写镜头/对白的提示框架值得直接借鉴。

---

## 第九部分：武侠功夫 / 华语青春 / 更多类型（2026-11-25 五轮挖掘，20 个新增）

> 本轮聚焦「香港武侠」与「台湾偶像剧」两个指定方向，并补齐港片喜剧、鬼片、仙侠国漫等。
> **先说结论**：Civitai 上**没有**以「台湾偶像剧 / 台剧」命名的专门 LoRA——这是平台类目缺口。可用三条替代路径：① 日系胶片 + 华语青年角色 LoRA 自组台剧感；② 王家卫/Krea2 情绪片做文艺爱情；③ Cineluxe / SATIN 做偶像剧柔焦质感。详见 Y 组。

### Y. 台湾偶像剧 / 华语青春（替代方案，4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Krea2 Japanese film style** | Krea 2 | 日系模拟胶片、专业摄影师视角。台剧/华语青春最常用的底味——高明度、低对比、自然光散射 | `jiaopian`；1.0；krea2-turbo 训练 | [2816521](https://civitai.com/models/2816521) |
| **SATIN 绸缎胶片** | ZImageTurbo | 极致日系空气感人像：135 胶片通透感、去塑料味、毛孔与绒毛质感、高明度低对比，**每张都像电影剧照**。最接近偶像剧柔焦剧照的一款 | 无明确触发词；0.7–0.8（最佳平衡点）；81 MB | [2436970](https://civitai.com/models/2436970) |
| **Moody Gal – Cici** | Krea 2 | 22 岁中国艺术院校女生角色（虚构）：慢热温柔、数字媒体专业、画廊策展助理、随身银色腋下包、低饱和宽松穿搭。可直接当台剧女主角用 | 角色 LoRA，按页面提示词调用 | [3002891](https://civitai.com/models/3002891) |
| **Cineluxe Style** | Krea 2 | 用 GPT 图像训练的电影梦境感：柔焦、雾化光晕、bloom、发丝细节、戏剧轮廓光、抛光胶片质感。适合偶像剧式浪漫/情绪特写 | `cineluxe_style` 放开头；0.6–1.0（推荐 0.6 起）；配 `bokeh / rim lighting / dreamy atmosphere` 等词 | [2892074](https://civitai.com/models/2892074) |

> 组合建议：`SATIN`（ZIT）/ `jiaopian`（Krea2）打底 + `Cici` 角色 + 王家卫 `wkw1` 少量叠加（0.3–0.5），可拼出台剧爱情剧照感。

### Z. 香港武侠 / 功夫片（6 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Vintage Shaolin by AK** | Krea2 / Flux.1 D / ZIT（3 版） | 复古少林：古建、宝塔、僧侣、自然环境，老电影质感。Krea2 版 218 MB | `Vintage, Shaolin`；Krea2 218MB；Flux 用 Euler/20 steps | [2631251](https://civitai.com/models/2631251) |
| **1970s Martial Arts** | HunyuanVideo（视频） | 70 年代（含部分 80s）功夫片：Capture 打斗动作 + 典型机位，低角度竹林对战、传统服饰、摇镜。已知短板：快速动作会糊、长片段易跑偏 | 用训练集式自然语言提示（写明服装/机位/动作）；312 MB | [1405211](https://civitai.com/models/1405211) |
| **武侠 Wuxia V2** | SD 1.5 | 经典武侠画风，简单利落构图，2186 条评价「压倒性好评」。增加中式服装、背景、肢体，强化武器与龙元素 | `gu wuxia holding weapon dragon` / `weapon, sword`；96 MB | [76637](https://civitai.com/models/76637) |
| **Martial Arts Style Actions** | SD 1.5 | 武侠动作/山水/中式建筑/黑白。**注意**：不加背景描述时人物会直接变成武术动作，可用于风景、动作或融合 | 触发词含 `landscape, Mountain, Water, Sun, Chinese Architecture, Black and white images`；仅 18 MB | [195167](https://civitai.com/models/195167) |
| **Classic Fighting Tournaments – HK Late 80s** | Flux.1 | 80–90 年代港片擂台比武：围观人群、龙雕像、火把、书法牌匾、阳台栏杆、欢呼观众——街头霸王/真人快打式场景源头 | 提示词参考 `bl00dsp0rt, two men standing on white carpet, crowd, dragon statues, torches...` | [1865653](https://civitai.com/models/1865653) |
| **MiniMax H3 8-Step Wushu Motion Control** | MiniMax H3（工作流） | **武术打斗动作控制**完整工作流：hybrid FL2VA/Ref2VA bf16 + LightX2V 8步 turbo + wushu_e3(0.75)/Motion Repair(0.5)/spatial physics(0.3)，10-step euler，24fps 带音频 MP4。适合打斗、兵器、快速冲击镜头 | 一句一动作（击打→闪避→收势），给对打双方留够头顶空间，先测短片再渲全长 | [2942484](https://civitai.com/models/2942484) |

> 你已有的武侠资源对照：H3 视频风格 = 90s Hong Kong Wuxia（62MB，`90s_wuxia_style`，画面 0.6 / 音频 ≤0.3）；Krea2 图像 = PhantomLight Hanfu、ShadowWuxia、90s Movie Grit。本组主要补「70 年代邵氏感」和「打斗动作控制」。

### AA. 仙侠 / 国漫（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Chinese Fantasy Xianxia 仙侠古风** | Qwen-Image 2.1 | 古风人像/仙侠角色：姿态柔美有张力、服饰材质、光影纵深。**V2 Strong** 风格重但牺牲底模通透；**V3 均衡版** 推荐。非固定人脸，可与角色 LoRA 叠加 | 无触发词；0.2–0.3 轻 / 0.4–0.6 标准 / 0.7–0.8 强 / 0.9+ 玄学抽奖；崩手或过暗把 CFG 拉到 2.0–4.0 | [2979853](https://civitai.com/models/2979853) |
| **小白（青蛇/白蛇）** | Krea 2 | 《白蛇：缘起》追光动画 3D 风格角色：剑眉、凤眼红眼影、红唇长发、银蛇发簪、白汉服。适合仙侠/古风 3D 动画 | `snake`；1.0–1.5（推荐 1.5）；现代/赛博服装会破风格 | [3007857](https://civitai.com/models/3007857) |
| **凡人修仙传 – 柳玉** | Krea 2 | 国漫《凡人修仙传》角色 LoRA：黑长发、发饰耳环、绿衣中式服装、手镯 | `liuyu, 1girl, black hair, long hair, hair ornament, earrings, dress, green dress, chinese clothes, bracelet, sash`；223 MB | [2998679](https://civitai.com/models/2998679) |

### AB. 港片喜剧 / 鬼片（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Goofballs** | Krea2 / ZIT / Wan 2.1-2.2（3 版） | 夸张变形人脸卡通：长脸、巨眼、大耳、蒜鼻、巨唇。Krea2 版头型与表情最多样。**可借来做周星驰式无厘头丑角**，但非港片专用风格 | `caricature` + `u61y big eyes big nose big ears long face exaggerated features`；1.0；Krea2 用 er_sde/simple，ZIT 9 steps res_multistep/simple | [1898850](https://civitai.com/models/1898850) |
| **Ghost_Style** | SDXL | 幽灵/半透明魂体：薄纱幽魂、发光眼、雾气、月光、哥特与赛博鬼魅多场景。港片僵尸/阴阳片可作风格基底 | `Ghost_Style` + 场景词；0.7–0.9；1024²，25–35 steps、CFG 5–7、DPM++2M Karras | [3022876](https://civitai.com/models/3022876) |
| **V67 Dark Horror Atmosphere** | Flux（另有其它底座版） | 高级恐怖氛围：废弃疗养院、教堂地下室、雾林、无脸高个、稻草人、生锈霉斑、闪烁灯光。**不含血腥**，靠构图制造不安 | `dkh atmos` 放提示词中；0.5–0.8；负面词排除 bright/sunny/colorful/modern | [2537838](https://civitai.com/models/2537838) |
| **Minimax Ghost (Halloween)** | MiniMax H3（视频） | 视频鬼怪：黑烟/雾状异形幽灵横向冲出、消散重组、选择性绿/蓝色调、雨夜桥面。**副作用**：普通场景也会变暗+重颗粒+随机闪光 | 0.7；v0.2 用视频片段训练，需写细节与 exotic creature ghost / exotic feminine ghost | [2938527](https://civitai.com/models/2938527) |

### AC. 通用电影感（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Krea 2 Aesthetic** | Krea 2（Medium/Large） | 增强 Krea2 原生能力：去 AI 塑料感、真实皮肤毛流、锐利风景、精准文字渲染、生产级质感。类似「通用画质+审美增强器」 | 长触发串 `(Krea 2 Aesthetic, Moodboards:1.1), Aesthetic Diversity, ...` 或短版 `Krea photorealism, Krea aesthetic`；0.78–0.90；推荐 Large 模型、Creativity 40–50 | [2748721](https://civitai.com/models/2748721) |
| **V0id** | Krea 2（另有 Flux2 Klein 版） | 光影/阴影/虚化/辉光/雾/镜头光晕/对比/机位的氛围型电影感，偏情绪化海报感，**不是超写实日常摄影** | 无明确触发词；作者实测 1 / 1.5 / 2 三档对比图见页面；435 MB | [2559636](https://civitai.com/models/2559636) |

### AD. 本轮关键发现

1. **台湾偶像剧是类目空白，不是资源空白**：Civitai 没有台剧分类，但 `SATIN`（135 胶片空气感）+ `Cici`（华语艺术院校女生）+ `jiaopian`（日系胶片）+ 少量 `wkw1`（王家卫情绪）拼起来，比找单一 LoRA 更接近台剧质感。
2. **武侠资源集中在「风格」而非「动作」**：90s HK Wuxia（H3）调色打光、Vintage Shaolin 场景、武侠 V2 构图——真正解决「怎么打」的只有 MiniMax H3 8-Step Wushu（工作流，含 Motion Repair + 空间物理）和 1970s Martial Arts（Hunyuan）。你做打斗镜头优先看这两个。
3. **周星驰无厘头没有现成 LoRA**：目前只有 `Goofballs` 这类通用丑角变形 LoRA 可借，加上提示词写具体场景（如「乱发卷+白蕾丝睡袍+上海滩石阶」）才能接近。这类角色风格更适合用「角色参考图 + inswapper」路线，而不是风格 LoRA。
4. **仙侠古风 LoRA 都在 Qwen-Image 2.1**：仙侠古风(2979853)是 Qwen2.1，小白/柳玉是 Krea2 角色款。若走国漫 3D 路线，Qwen2.1 的 V3 均衡版是首选。
5. **鬼片视频 LoRA 只找到 H3 一款**：Minimax Ghost 的副作用（暗化+颗粒）反而适合港片阴阳/僵尸氛围，但会污染普通场景，建议单独开一条生成链。

---

## 第十部分：美国科技 / 韩系人像 / 星际系列（2026-11-25 六轮挖掘，14 个新增）

> 本轮聚焦「美国科技大片」与「韩剧」方向。
> **韩剧同样无专门风格 LoRA**（与台剧情况一致）——Civitai 上韩国向资源以「韩系写实人像 + 韩国偶像角色」为主，需自己叠加电影感 LoRA 才能出剧照质感。见 AE 组说明。

### AE. 韩系人像 / 偶像（6 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **CHAEWON (chaewonXCV)** | ZIT / Krea2 / SD1.5（3 版） | 超写实韩国偶像：鹿眼、精致鼻梁、暗色波波头+空气刘海、水光玻璃肌、纤细身材。服装标签完全解耦，可自由换首尔街拍/Y2K 偶像/慵懒衬衫等 | `chaewonXCV`；ZIT/Krea2 按页，SD1.5 用 0.6–0.85（推荐 0.7–0.73，majicMIX/CyberRealistic 需 Clip Skip 2） | [2994783](https://civitai.com/models/2994783) |
| **NexBlend 04 Asian Realistic** | ZImageTurbo | 韩系审美写实人像：干净通透皮肤、精致东亚五官、现代韩妆。高权重稳定——1.0 标准，1.7+ 仍不崩 | `nexblend`；1.0–1.7+ | [2595202](https://civitai.com/models/2595202) |
| **NexBlend 07 Asian Realistic** | ZImageTurbo | 同上系列新版本，韩系干净皮肤 + 现代妆容 | `nexblend`；1.0 起 | [2744691](https://civitai.com/models/2744691) |
| **Moody Gal – Nari** | Krea2 / Zimage | 25 岁韩国女 DJ 角色：夜店/音乐节舞台高冷气场、私下善良。60+ 张精选图训练；另含 Mimi/Irene/Huihui/Vivian/Weiwei/Veronica/Yoki/Lili/Hana/Rina 等 15 款同系列 | 角色 LoRA；0.8；Krea2 版 327 MB | [2662271](https://civitai.com/models/2662271) |
| **Seo Yuna – Korean Dreamscape** | Krea 2 | 21 岁首尔时尚模特+数字媒体学生（虚构）：弘大街拍、独立画廊、城市夜景；兼赛博朋克/梦境奇幻。附 40 条提示词包（20 写实 + 20 奇幻） | `Seo Yuna` 开头（难场景加 `, woman`）；0.85–0.95；8 steps、CFG1、Euler/Simple | [3022915](https://civitai.com/models/3022915) |
| **Famegrid Realism** | Krea2 / ZIT / Qwen（多版） | 现代社交媒体质感写实：自然姿态、可信皮肤、干净构图、专业打光。适合 K-pop 风人物/ lifestyle。Qwen 版触发 `IGMODEL`（影响力人物）+ `rlskn`（皮肤细节） | `famegrid`（Krea2/ZIT）；er_sde、guidance1、8–16 steps；Qwen 权重 1.0–2.0 | [2088956](https://civitai.com/models/2088956) |

> **韩剧质感配方**：`NexBlend 04`（ZIT，韩系皮肤）或 `CHAEWON`（角色）打底 + `Vision Vanguard 22`（低 key 高对比）或 `wkw1`（情绪光）少量 + `Cineluxe`（柔焦梦境）。目前没有单款 LoRA 能直接出「韩剧剧照」。

### AF. 美国科技 / 星际科幻（8 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **2020s Sci-Fi Movie** | 多底座（Krea2 / Anima / Klein4B / Klein9B / ZIT / Flux / Chroma / Illustrious / SDXL / SD1） | 当代科幻电影感：气候科技、神经接口、被淹城市、火星居所、城市废墟、更落地的 AI 与科技。V2 重制版 | `ArsMovieStill` 或 `Movie still from a 2020s Sci-Fi movie`；1.0；Klein4B 版 88 MB | [929073](https://civitai.com/models/929073) |
| **Orion Expedition（新增 H3 视频版）** | **MiniMax H3**（原 Krea2 版见第八部分） | 同一作者的科幻系列新增 H3 版：星舰舰桥与船员、异星世界、赛博朋克/反乌托邦未来，**带对白/音效/配乐**。Krea2 版继续用于出图，H3 版用于动态 | H3 版权重 1.0，提示词须按 MiniMax H3 格式写（`integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music`）；Krea2 版 er_sde+simple、0.9–1.0 | [3003215](https://civitai.com/models/3003215) |
| **Sci-Fi Cinema** | LTXV 2.3（另有 MiniMax H3 版） | 未来城市、异星世界、飞船内饰、空间站、全息界面、霓虹街道。视频模型风格 LoRA，98 条好评 | `srx_scififilm`；1.0；LTX 版 322 MB | [2692151](https://civitai.com/models/2692151) |
| **Star Trek TNG Cinematic Style** | Krea2 / Flux / SDXL / Pony（多版） | 《星际迷航：下一代》全剧氛围：近 400 张剧照训练（K2 版），4mp 分辨率最佳；男性易出现数据脸 | `tng`；K2 版 218MB，6000 steps/20 epochs | [598337](https://civitai.com/models/598337) |
| **Star Trek TNG style** | ZImageBase | TNG/DS9 时代（1987–1999）复古未来主义：明显胶片颗粒、真实打光、星际舰队制服准确性。**强制提示词前缀**，缺前缀会退化为普通科幻 | 前缀必写：`startrek_filmstyle, startrek style, strtrk_filmstyle, retre0 film style, film grain, wearing startrek uniform,` 再接 `A photo-realistic [角度] shot depicting...`；避开 neon/vaporwave | [2765097](https://civitai.com/models/2765097) |
| **Star Trek TNG – the next generation** | Krea 2 | 场景/道具向：LCARS UI、舰桥、船员宿舍、相位枪、企业号 D、观察镜。作者注明部分道具（相位枪/传送室）准确度不足 | 多个触发词：`Star Trek tng` / `LCARS UI` / `Visor` / `Phaser` / `U.S.S. Enterprise NCC-1701-D` / `The Bridge`；218 MB | [2878784](https://civitai.com/models/2878784) |
| **Vision Vanguard 22** | Krea 2 | 高对比写实电影摄影：深低 key 阴影、细节纹理、精准景深、自然光。适合韩剧/美剧式人物近景 | 无触发词；0.85–1.0（1.0 更粗粝，0.85 皮肤更顺）；Base 用 CFG2.5–4.5/35–50 steps，Turbo 用 CFG1/8–9 steps；建议 512 训练、1024 生成 | [2756232](https://civitai.com/models/2756232) |
| **Cinematography_Lighting_Base** | Illustrious | 电影布光基础层：戏剧化阴影、窗光、月光、胶片氛围。可作打光底模叠在角色 LoRA 上 | `cinematography_lighting_base`；Clip Skip 1 | [2477404](https://civitai.com/models/2477404) |

### AG. 本轮关键发现

1. **韩剧 = 韩系人像 + 电影感叠加**：`NexBlend 04`（韩系干净皮肤）或 `CHAEWON`（偶像角色）+ `Vision Vanguard 22`（低 key 高对比）是目前最接近韩剧剧照的组合；纯「韩剧风格」LoRA 仍不存在。
2. **Orion Expedition 现在双底座**：Krea2 版出图、MiniMax H3 版出带声音视频（提示词格式完全不同），是少数「同一审美跨图/视频」的系列。
3. **Star Trek 出了 3 款不同侧重点**：598337 抓全剧氛围、2765097 抓 80–90s 胶片复古（有强制前缀）、2878784 抓舰桥道具。按需要选，别混用。
4. **ZImageTurbo 的韩系皮肤 LoRA 权重普遍偏高稳定**：NexBlend 系列 1.0–1.7 都不崩，适合需要强化的东亚面孔。

---

---

## 第十二部分：欧洲艺术片 / 纪实摄影 / 恐怖片 / 胶片型号 / 广告 MV（2026-11-25 七轮挖掘，18 个新增 + 5 个参数补充）

> 本轮按类型横向扩展：欧洲作者电影、70s Italian Giallo、纪实/街头摄影、80s 恐怖片、具体胶片型号（Portra / Vision3）、1983 广告与 H3 视频新风格。全部为页面标注底座，非本地实测。

### R. 欧洲 / 意大利类型片（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Giallostyle — Gritty 70's Italian Thriller** | Krea 2（另有 ZIT、SDXL 版） | 意大利 70 年代 Giallo 惊悚片：高饱和血色、强反差、变形镜头眩光、谋杀悬疑氛围；4000 steps。K2 版为最终版 | 权重 0.6–0.7 起步，最高 1.0（过强会压倒画面）；SDXL 版 0.5 偏"高清" / 1.0 极端粗粝 | [2138328](https://civitai.com/models/2138328) |
| **Les Amants Diaboliques** | Krea 2 | 法国作者动画：极简黑色勾线、平涂色块（暗调/深黑/血红/裸色）、无复杂渐变；人物略棱角化、玩偶感；适合戏剧性叙事、分身、神秘题材 | `LesAmantsDiaboliques`；1.0；218 MB | [2864566](https://civitai.com/models/2864566) |
| **085 — In the Shadows** | Krea 2 | 逆光剪影式 noir：主体部分或全部隐入暗影，颗粒黑白；默认爱在人物后放树木枝叶，不需要可显式指定场景 | `n0vuschr0ma style`；不够暗可加 `obscured by shadows`；218 MB | [2809346](https://civitai.com/models/2809346) |

### S. 纪实 / 街头摄影 / 新闻摄影（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Photojournalism Quality** | ZIT + Krea 2 双版 | 1970s 新闻摄影：Kodak Tri-X 400 / Kodachrome 64 重颗粒、压暗黑色+过曝高光、去饱和琥珀调；适合战地、街头抗议、深夜警务、名人抓拍、环境肖像 | `(Photojournalism quality:1.3), analog press style, documentary film look, grainy news photography, 1970s newspaper photo...` 整串放开头；搭配 V67 DSLR + V67 Natural Color Palette | [2742204](https://civitai.com/models/2742204) |
| **V67 Street Photo** | Krea 2 + ZIT 双版 | 街头纪实：35/50mm、自然光、黄金时刻/霓虹夜、湿地反光、电影调色、低饱和高对比、浅景深、运动模糊；2000 steps | `(Street Photo:1.1), candid street photography, documentary style, urban reportage, unposed, authentic...` 整串放开头；218 MB | [2998016](https://civitai.com/models/2998016) |
| **RAD26 — Raw Authenticity Documentary** | ZIT | 真实纪录片：自然光、胶片颗粒、杂乱环境、真实情绪；750 steps 免费预览版（轻量风格影响，适合与其他 LoRA 叠加做"真实性打底"），完整包 1500/2250/3000 steps 在 Patreon | 无特定触发词；1.0；162 MB | [2532790](https://civitai.com/models/2532790) |
| **V67 Photorealistic** | Krea 2 | 非摆拍写实：受 Magnum、Annie Leibovitz、何藩、Saul Leiter、森山大道及 Deakins/Doyle/Lubezki 影响；内置 20 条摄影概念与排错表（脸僵改用背影/剪影/运动中） | `(phtreal, photorealistic:1.1)` **必须放最开头**（逗号不是句号）；0.85；胶片可选 Portra 400 / Cinestill 800T / Tri-X 400 / Vision3 5219 | [3017569](https://civitai.com/models/3017569) |

### T. 胶片型号 / 摄影机模拟（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Analog Photo — Kodak Portra 400** | Krea 2 + ZIT 双版 | 经典 Portra 400：颗粒、轻微软化、良好对比、压暗黑色、真实胶片颗粒；ZIT 版 81 MB，K2 版 218 MB | ZIT 版 `Kodak Portra Photograph`；两版均 0.5–1.0 | [2184875](https://civitai.com/models/2184875) |
| **ARRIFLEX 435 + Kodak Vision3 200T/500T** | Z-Image（zib 版 / F1D 版） | ARRIFLEX 435 摄影机 + 柯达 Vision3 200T/500T 电影胶片模拟，35mm 高反差；训练集为《耶稣受难记》，**容易冒出固定群众演员脸**，可加 `male/female`、负面词写 `man/woman` 缓解 | `kodak film daylight style / moonlight night blue themed / warm light / Overcast sunlight`；162 MB | [1304800](https://civitai.com/models/1304800) |

### U. 恐怖 / 惊悚片（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| ⭐ **1980s Horror Movies** | **多底座 9 版**：MOSS / **MiniMax H3 FL2V** / Krea 2 / ZIT / Flux.2 Klein 9B / Wan 2.2 T2V 14B(Low+High) / Diffusers / Comfy | 80s 恐怖片：僵尸、狼人、身体恐怖、血腥氛围；H3 版 295.8 MB、185 epochs、59 好评。作者用 Qwen3-VL 按 H3 偏好重打标；Wan 版 **Low noise 文件对风格影响最大** | H3 版 1.0；MOSS 版 0.9；Wan 用 Low+High 双文件 | [1592586](https://civitai.com/models/1592586) |
| ⭐ **16mm Found Footage**（= Deep Woods Footage） | **MiniMax H3 视频** | 《布莱尔女巫》式伪纪录片：真实从胶片扫描提取的银盐颗粒、压暗但可读的阴影、光源光晕、软边角；深焦无浅景深；夜间手电筒树林/帐篷内透光/白天阴郁树林 | `foundfootage16` 开头；白天 0.8 / 夜戏 0.9–1.0；>1.1 颗粒会帧间碎裂像下雨；导出 CRF≤16 + `-tune grain` | [3015094](https://civitai.com/models/3015094) |
| **hellraiser** | Krea 2（兼容 SDXL/Illustrious/Pony） | 80s 英式超自然恐怖的**空场景背景** LoRA：哥特工业地狱维度、黑色石迷宫、悬浮黑色菱形、锁链、琥珀底光+冷月灰蓝；11 个连通地点，**全无人物**，中央留空供你后期放角色 | `h3llr4is3r`；0.8–1.0；负面词排除 humans/people/gore；218 MB | [2968383](https://civitai.com/models/2968383) |
| **Horror Style** | Krea 2 | 氛围型恐怖：拉长肢体、畸形身体、恐怖谷、獠牙；以黑白单色为主但彩色也能用；支持 furry/anthro | `H0r10r, sc@r1, monochrome, black and white`（furry/anthro 可选）；1.0；218 MB | [2785722](https://civitai.com/models/2785722) |
| **Film Noir Movie with Selective Colors** | MiniMax H3 视频 | 黑白 noir + **局部彩色**：珠宝、血、红/橙被专门训练成发光色；"sin city"式选择性着色 | `film noir` 放提示词；1.0；295.8 MB。**不要写不需要的颜色**，否则会意外上色 | [2934763](https://civitai.com/models/2934763) |

### V. 广告 / MV / H3 视频新风格（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **80s Commercial Essential 1983** | MiniMax H3 视频 | 1983 年电视广告质感；由 Krea2 原版转换而来。**最佳用法：给 H3 铅笔分镜草图 + 角色参考，让 LoRA 填质感**（写实首帧只能强化已有内容） | `com80style` 放开头；1.0；有 ep35/ep50 两档，先试 35；68 MB | [2918721](https://civitai.com/models/2918721) |
| **KreaLand** | MiniMax H3 视频 | 风光/ landscape 风格；同为 Krea2→H3 转换实验版，非剪枝通用 | `krealandstyle` 放开头；1.0；ep35/ep50 两档；68 MB | [2919337](https://civitai.com/models/2919337) |
| ⭐ **Cinematic Version 无张量报错版** | MiniMax H3 视频 | 官方电影感 LoRA 的**剪枝与非剪枝通用版**：稳定肢体、减少自动切镜、长镜头连续性、优化高速运动拖影/残影；112 好评 | 无需触发词；标准 0.7 / 高动态 0.5 / low noise 0.6 / high noise 0.5；295.8 MB | [2937713](https://civitai.com/models/2937713) |
| **Blackened — Dark Noir** | Krea 2 | 近单色黑/炭灰/烟灰，锐利高光、克制深红点缀、图形化深影、雾、湿反光街面、戏剧轮廓光；适合肖像、时尚编辑、侦探、哥特、海报 | 无需触发词（`blackened` 可选）；0.8–1.0；56 MB | [2838147](https://civitai.com/models/2838147) |

### W. 已有条目的关键参数补充（5 个）

| LoRA | 补充内容 |
|---|---|
| **80sfilm** [2913743](https://civitai.com/models/2913743) | 训练自《壮志凌云》《深渊》《贝弗利山警探2》《高地人》《异形2》《致命诱惑》《虎胆龙威》等真实 80s 影片帧；**权重范围 1.0–3.0**（0.7–1.0 轻叠、1.0–1.5 标准、1.5–3.0 戏剧化强推），Turbo 8–10 steps 实测；提示词差异会导致效果强弱不一，不够就加权重 |
| **Technicolor Style** [2629410](https://civitai.com/models/2629410) | Krea2 版 0.8–1.2 / ZIT 版 0.5–0.8；满权重会改变服装发型车辆（年代感），低权重只保留胶片打光，适合 70s/80s 氛围；126 好评 |
| **V67 Film Noir** [3010470](https://civitai.com/models/3010470) | 新增详细镜头词表：`fedora detective`、`venetian blind shadows`、`femme fatale`、`rain slicked streets`、`hard key lighting`、`35mm film grain`、`film noir style`；负面词排除 flat lighting / phone camera / harsh flash；灵感来自 John Alton、Nicholas Musuraca、Gregg Toland 摄影 |
| **CinemaGrade** [2927223](https://civitai.com/models/2927223) | `cinemagradestyle` 放开头；两个文件 ep35 较软 / ep50 更强；由 Krea2 版经 rank8 H3 转换训练（150 张 Krea2 生成图、blocks 0-3,6-47、shift 0.6667） |
| **16mm Found Footage** [3015094](https://civitai.com/models/3015094) | 见 T 组完整参数；注意 `foundfootage16` 必须开头，且亮度要用场景描述而非"brighter exposure"（会压平光衰） |

### X. 本轮关键发现

1. **Krea2 → H3 的转换链条已经跑通**：CinemaGrade、80s Commercial 1983、KreaLand 都是「Krea2 图像 LoRA 出 150 张图 → Qwen3-VL 重打标 → rank8 H3 训练（blocks 0-3,6-47、shift 0.6667、50 epochs）」产出。你本地有三个 Krea2 电影风格 LoRA，**理论上可照此配方转成自己的 H3 风格 LoRA**——这比找现成 H3 版本更可控。
2. **多底座系列再添一员**：1980s Horror Movies 一口气发了 9 个底座版本（含 H3 FL2V、Krea2、ZIT、Wan 2.2、Klein 9B）。"一次调色、全底座复用"已是主流发布方式。
3. **纪实摄影类 LoRA 可用作"真实性打底"**：RAD26 明确说轻量风格影响、适合与其他风格 LoRA 叠加；V67 的 Photojournalism / Street Photo / Photorealistic 三款都要求**触发词整串放开头并带权重**，位置错误会明显掉效果。
4. **两个"容易翻车"的点**：ARRIFLEX 435(Vision3) 训练集单一会冒固定脸；H3 选择性着色 noir 只要提示词写了不需要的颜色就会意外上色。两者都要靠负面词/提示词精细控制。
5. **H3 视频 LoRA 的通用最佳实践**：铅笔分镜草图 + 角色参考 > 写实首帧。风格 LoRA 在"留白"的画面里填充质感，写实首帧上只能强化已有内容——这跟你现有 minimax_h3_director 的用法可以直接结合。

---

---

## 第十三部分：VHS 复古录像 / 3D 动画电影 / 新海诚 / 定格动画 / 历史战争（2026-11-25 八轮挖掘，19 个新增 + 3 个参数补充）

> 本轮主攻此前完全没覆盖的品类：VHS/ MiniDV/ CRT 复古录像、皮克斯式 3D CGI、新海诚电影动画（含 H3 视频版）、定格/黏土动画、战争历史片。全部为页面标注底座，非本地实测。

### Y. VHS / MiniDV / CRT 复古录像（5 个，全新品类）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| ⭐ **2000s Analog Core** | **Krea2 / ZIT / Qwen / Flux 多版**（ZIT 版 v3） | 2000s 模拟录像：VHS、VHS-C、Hi8 混合训练；**带时间戳/日期戳**（Qwen 版最准）、VHS 停顿抖动、低分辨率；419 好评。低清 VHS 用 704×704 约 0.5MP + `amateur quality, low resolution`；Hi8 用 1024×1024 约 1MP | 唯一需要的触发词 `v8s`；K2 版 0.8 / ZIT 0.9（配 res_2s_ode + beta）；别混太多触发词 | [1134895](https://civitai.com/models/1134895) |
| ⭐ **VHS Style** | **K2 / SDXL / Flux / Pony 多版**（Realistic v1–v3 + Artistic） | Realistic 版用真实 VHS 录像帧训练（v3 数据集最大），Artistic 版是模拟 VHS 特效/故障美学；65 好评 | `vhs`；K2 版 3000 steps / 218 MB | [430136](https://civitai.com/models/430136) |
| **Retro TV & VHS Aesthetic (Fortnox)** | Krea 2 | 1980s 广播电视+旧磁带：CRT 荧光粉辉光、扫描线、模拟磁噪、色边、软焦；四种风格修饰词分别对应霓虹渗色、跟踪故障（found footage/模拟恐怖）、VHS 暂停抖动（UFO 目击）、广播图文、CRT 边框 | `vhs80s_bcast` + 修饰词（1–2 个）；**权重 1.7**（偏高）；218 MB | [3006382](https://civitai.com/models/3006382) |
| ⭐ **Neon VHS Dreams** | **MiniMax H3 视频 + Krea2 双版** | 80s 中后期模拟质感：复古调色、VHS 纹理、复古**音频/音乐质感**一并生成；H3 版 568.82 MB、108 好评 | 无需触发词；H3 版 0.85–0.95；直接自然描述运镜与场景动态即可 | [2987989](https://civitai.com/models/2987989) |
| **MiniDV Nostalgia** | MiniMax H3 视频 | 2000s 初家用 DV：软细节、失焦、曝光不均、手持晃动、随意构图；96 好评。**⚠️ 训练集无音频，会削弱 H3 原生音频生成能力**，目前建议纯画面使用 | `y2km1n1dv`；0.9；62.59 MB | [2924023](https://civitai.com/models/2924023) |

### Z. 3D 动画电影（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| ⭐ **Pixar – Disney 3D Style** | Krea 2（另有 ZIT 版 2833916） | CGI 3D 动画电影质感，卡通化人物与柔光渲染；274 好评。作者声明**训练图全为 AI 生成，未用任何皮克斯/迪士尼素材** | `3dpixar` 放开头；1.0；218 MB | [2831766](https://civitai.com/models/2831766) |
| **Pure-Pixar 3D** | Krea 2 | 皮克斯+写实混合的高端 3D 动画；附 33 MB 训练数据包 | `KR2Pix`（核心）；1.0；218 MB。加强词：`Disney Pixar style`、`polished stylized 3D animated movie aesthetic` | [2977241](https://civitai.com/models/2977241) |

### AA. 新海诚 / 日本动画电影（3 个，含 H3 视频版）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| ⭐ **Environmental Anime Style Mix (Makoto Shinkai)** | **MiniMax H3 + LTX 2.3 双版** | 《你的名字》228 张**纯环境镜头**训练（极少人物特写），1536×864；把新海诚的镜头构图、镜头光晕、散景、前景摆放、动画光照"烧进" LoRA，不写这些词也会出现。132 好评；相当于环境细节增强器 | `2d anime style, art by makoto shinkai`；1.0；H3 版 284 MB（LTX 版触发 `ANIMSTY, SHW_YN`） | [2650155](https://civitai.com/models/2650155) |
| **Shinkai Makoto 3-in-1** | Krea2 / Anima | 500+ 张《你的名字》《天气之子》《铃芽之旅》原画+设定集；四种效果可组合：`Shinkai Makoto Style` 单独=综合，`+ Your Name Style`=你的名字，`+ Weathering With You Style`=天气之子，`+ Suzume no Tojimari Style`=铃芽之旅；内置三角色词 `Miyamizu Mitsuha` / `Amano Hina` / `Iwato Suzume` | `Shinkai Makoto Style` + 影片后缀；0.6–1.3。作者加了**文件内防盗水印**，不影响出图 | [2912863](https://civitai.com/models/2912863) |
| **Your Name Artstyle** | 未标注（推测 Flux 系） | 逐帧精选《你的名字》4K 片源 1509 张原画截帧，压到 1024 训练；采用"暴力删标"把新海诚标志性云层/丁达尔光/高反差明暗/黄昏**强制绑定到单一触发词**，提示词极简 | `yourname style`；0.6–1.0（过高色彩会过软）；euler 25 steps / 1024+ / CFG≥3.5 | [2745715](https://civitai.com/models/2745715) |

### AB. 定格 / 黏土动画（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Claymation Style** | Krea 2 | 真实定格黏土：柔软哑光黏土质感、指纹与工具痕、可爱比例；保留角色身份；435 MB（rank 高） | `claymation` / `claymation style`；0.1–1.2，常用 0.85–1.0 | [2803827](https://civitai.com/models/2803827) |
| **051 – Made of Clay** | Krea 2 | 黏土雕塑+完整场景，背景倾向失焦；换不同黏土词出不同质感 | `n0vuschr0ma style` + `made of clay`/`stop-motion animation`/`claymation`/`play-doh`；218 MB | [2785861](https://civitai.com/models/2785861) |
| **Oddarium（Wes Anderson 双媒介）** | Krea 2 | 韦斯·安德森式：强迫症对称、克制配色、面无表情角色、精心布置的空间。**一个 LoRA 两种媒介**：`oddarium, photograph` 走暖调摄影/复古室内，`oddarium, claymation` 走雕塑性质的定格人偶/微缩世界；可加 `handcrafted puppet`、`miniature set` 强化 | `oddarium` + `photograph`/`claymation`；8 steps / CFG1 / Euler/Simple（非 Turbo 版要调高两者）；218 MB | [2872676](https://civitai.com/models/2872676) |
| **ModelingClay** | **MiniMax H3 / MOSS / Krea2 / SDXL / Pony / Illustrious 六版** | 橡皮泥/黏土定格角色，适合把一整组角色与场景统一成同一系列质感；H3 版走 text-to-video | `ModelingClay_TeraWatt`；**K2 版要 1.5–3.0 才明显**（又一个高权重例外） | [3025654](https://civitai.com/models/3025654) |
| **[Krea2] – Stopmotion Goth** | Krea 2 | 哥特暗黑定格动画：手工质感、纹理环境、黏土般外观；Beta v0.5。副作用：女性角色不描述外貌时高概率长成某蓝发主角姐姐的脸 | `57OPM`；配 `still from a stop-motion film`、`plastic and fabric textures`；218 MB | [2866599](https://civitai.com/models/2866599) |

### AC. 印度 / 南亚（2 个，风格类稀缺）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Y2K Indian Aphrodite** | ZIT / Flux.2 Klein 9B 等 | Y2K 印度美学：宝莱坞式 Y2K 造型、低腰牛仔、分层首饰、35mm 胶片颗粒、色差；**ZIT 版胶片颗粒与怀旧氛围最强，Klein 版全身环境镜头最佳** | `y2kindianaphrodite`；0.75–0.85；CFG 3.5–5 / 20–30 steps / Euler | [2723805](https://civitai.com/models/2723805) |
| **REALISTIC INDIAN WOMAN** | ZIT + Krea2 Raw/Turbo | 自然肤色质感、纱丽/莱亨加/寺庙首饰/-bindis，也能现代休闲装；35mm 直闪抓拍；K2 版 16 图精训、无服装串味 | `realistic_indian_woman`（ZIT 版 `RIWPIndian_woman`）；0.7–0.8，推荐 0.8 | [2345524](https://civitai.com/models/2345524) |

> 说明：Civitai 上印度方向绝大多数是**特定人物角色 LoRA**（如 Krea 2 Thara / Piyali），不是"印度电影风格"；那个类目仍是空白，上面两个是能用来做风格化人物最接近的。

### AD. 历史 / 战争（1 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **AmericanRev** | Krea 2 | 美国独立战争/历史战争剧处理：暗色烟熏调色、手绘战场笔触、墨线勾边、交叉排线阴影、粗布/尘土/提灯；带 1980s 手绘动画写实剧质感 | `americanrev` **放提示词末尾**；0.7（低了太弱，高了过火）；218 MB | [2756731](https://civitai.com/models/2756731) |

### AE. 参数补充（3 个）

| LoRA | 补充内容 |
|---|---|
| **Cinematic Shot** [432586](https://civitai.com/models/432586) | Krea2 版触发词是 `zy_cinematic`（可选，无触发词也行，但写 `cinematic`/`cinematic still image` 有帮助），训练于风景图；ZIT 版无需触发词。社区评价 889 条压倒性好评 |
| **Minimax H3 Cinematic 官方版** [2937734](https://civitai.com/models/2937734) | 用户实测反馈：**数据集 steadicam 太多，推车/车拍等动态镜头容易被做成静态**；需要强运动时考虑不用该 LoRA，或压到 0.5 并显式写运镜 |
| **Technicolor Style ZIT 版** [2629410](https://civitai.com/models/2629410) | ZIT 版有独立触发词 `technic0lou_r`，强度 0.8（K2 版无触发词、0.8–1.2）；两版不是同一权重文件，别下错 |

### AF. 本轮关键发现

1. **VHS/复古介质是 Civitai 上最成熟的"时代质感"品类**：2000s Analog Core 有 419 好评、VHS Style 有 65 好评、Neon VHS Dreams 有 108 好评，且多底座齐全。**时间戳/日期戳**是 2000s Analog Core 的独有能力（Qwen 版最准），这是别的胶片 LoRA 给不了的。
2. **音频副作用要注意**：MiniDV Nostalgia（H3）因训练集无音频会削弱 H3 原生音频生成；反过来 Neon VHS Dreams（H3）明确把 80s 音乐/音频质感一起训练了。做视频选哪个取决于你要不要原声。
3. **两个"权重必须调高"的例外**：Retro TV & VHS(1.7)、ModelingClay K2 版(1.5–3.0)。常规风格 LoRA 0.5–1.0 的经验在这里不适用。
4. **H3 视频 LoRA 的题材边界继续扩展**：这次新增了 MiniDV 手持、80s VHS 霓虹、新海诚环境动画、黏土定格、橡皮泥定格（六底座含 H3）。H3 已不只是"真人电影感"工具。
5. **定格动画 LoRA 常带角色副作用**：Stopmotion Goth 会串到固定脸、051 Made of Clay 背景默认失焦、Oddarium 要显式写 `photograph` 或 `claymation` 才能选媒介。用这类 LoRA 时提示词要比平时更具体。

---

## 第十四部分：摄影师打光 / 蒸汽朋克 / 苏俄电影 / 游戏电影化 / H3 工作流（2026-11-25 九轮挖掘，24 个新增）

> 本轮补齐此前空白的「按摄影师/打光流派」类目、蒸汽朋克/复古未来、苏俄与拉美地域电影、游戏过场电影化，以及 3 个能直接用于 EP001 的 H3 视频工作流。全部为本轮新发现，已与文档既有条目去重（V67 Photorealistic / Ultra Vision / CineVivid / CinemaGrade / 官方 H3 / Blackened / Cinematic Movie Still 均为旧条目，不重复收录）。

### R. 摄影师 / 打光流派型 LoRA（3 个）

> 这类不绑定某部电影，而是复刻大师摄影指导的光影语言，适合需要「按情绪调光」而非「按年代套滤镜」的场景。

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **The Revenant style** | Krea 2 | 复刻 Lubezki（《荒野猎人》）100% 自然光哲学：拒绝人工布光，只用蓝调时刻（blue hour）、阴天顶光、篝火闪烁光；超广角、粗糙毛皮/风化皮肤/破烂冬衣、去饱和冷色、鲜红血液点缀 | `trg_rev` 系列触发词（low-key natural light / harsh overcast daylight / pale blue hour / flickering campfire / chiaroscuro 等）；112 MB，bf16，792 tensors | [2964180](https://civitai.com/models/2964180) |
| **V67 Lighting** | Krea 2（另有 Flux / Ernie 版） | 灵感来自 Deakins / Lubezki / Storaro + 卡拉瓦乔/伦勃朗/维米尔 + Fan Ho；10 类核心打光（体积光/明暗对比/霓虹/黄金时刻/月光/火光等），20 个精确触发词。雾量可用 `light mist`/`thick fog`/`volumetric haze` 控；1–2 人最佳，>3 人会稀释光焦点 | `(Lighting:1.1)` **必须放提示词开头**（小数点不是逗号）；效果不足提到 0.85；负面词必加 flat lighting/overexposed/underexposed/low contrast | [2939697](https://civitai.com/models/2939697) |
| **V67 HDR Intense** | Krea 2（另有 Flux / Ernie 版） | 高动态范围专精：亮部发光+阴影保细节、色彩浓郁、每道光晕都可控；同一 V67 家族的打光方法论，20+ 触发词 | `(HDR Intense:1.1)` **必须放开头**；0.85；负面词排除 low dynamic range / overprocessed HDR halos | [3046504](https://civitai.com/models/3046504) |

### S. 蒸汽朋克 / 复古未来主义（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **KREA2_RetroFied_V2** | Krea 2 | 蒸汽朋克+柴油朋克+中世纪科幻混合：机械细节、机器人肖像、纪念碑式建筑、未来城市天际线，也覆盖漫画插画；6000 steps/8 epochs，配 Epoch7 增强（950 图） | `RETR0K2`；0.8–0.85，CFG1；218 MB | [2790408](https://civitai.com/models/2790408) |
| **V67 Steampunk 蒸汽朋克本质** | Flux / Flux.2 Klein 9B / Krea 2（Mac 优化：Anima / ZIT / SDXL / Ernie） | 维多利亚时代+机械齿轮；多底座参数齐全：K2 权重 0.6–0.8/CFG3.5–4.5/20–30 steps/DPM++2M Karras；ZIT 权重 0.7–0.9/CFG2.5–3.5/4–8 steps；Klein 9B 0.6–0.8/CFG3–4 | `steampunk style` 放末尾；也可用 `victorian steampunk`/`brass and gears` | [2420916](https://civitai.com/models/2420916) |
| **Steampunk - CE** | Krea 2（另有 ZIT / ZIT Turbo / Qwen / Flux.2 Klein 9B / Flux.1 D / SDXL 版） | 用 Raw 训练、Raw+Turbo 通用；各底座版本齐全，适合跨底座复用同一审美 | `steampunk`；0.8；218 MB | [1641978](https://civitai.com/models/1641978) |
| **Retrofuturism by Fortnox** | Krea 2 | 黄金时代科幻概念艺术+实体电影感：流线型镀铬、真空管辉光、水粉/油画笔触、尘土飞扬的行星景观；两种渲染模式——插画（gouache/1970s covers）与电影写实（35mm grain/practical effects）；2500 steps/10 epochs | `rtrftrsm style` / `retrofuturism` / `vintage sci fi concept art`；1.0；218 MB | [3007092](https://civitai.com/models/3007092) |
| **DC Steampunk** | Krea 2 Raw（Turbo 通用） | 维多利亚工业世界：精密发条人物、巨械、飞船、氛围建筑；即使普通提示词也能出强蒸汽朋克感；10000 steps/rank64/GPT4.1 打标/646 图 | `DCST3AMPUNK.`；1.0；436 MB。短板：偶有 Midjourney 塑料脸，建议叠 0.2–0.3 写实 LoRA；建议 2K+ 分辨率 | [2997560](https://civitai.com/models/2997560) |

### T. 苏俄 / 东欧地域电影（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **ALEKSANDR DEYNEKA 苏联纪念碑动态** | Krea 2 | 1930s 苏联先锋派 OST 美学：极端透视（仰视/俯视）、动态对角线、运动员式理想化人体、平涂色块+锐利几何阴影、纯净蓝天/混凝土灰/耀眼白/红色点缀；伞兵、矿工、共青团员被处理成工业时代的古典浮雕 | `oil painting in the manner of Aleksandr Deyneka` / `Soviet monumentalism` / `OST society aesthetic`；0.85–1.0；8 steps + Euler A + Bong Tangent，1536×1024 / 1024×1536 | [2987600](https://civitai.com/models/2987600) |
| **V67 Soviet Russia** | Krea 2（另有 Flux / Ernie 版） | 苏俄审美全集：塔可夫斯基《潜行者》《飞向太空》的景观、CCCP 宇宙构成主义建筑、东正教金顶、法贝热工艺、俄罗斯民间艺术、冷战航天、Svema 胶片；不歌颂任何政权，capture 20 世纪重量感 | 触发串放最前；0.85–0.90；偶发西里尔文字可写 `CCCP`/`Russian text` 强化；加 1940s/1960s USSR 压住现代感 | [2837620](https://civitai.com/models/2837620) |
| **Sovdark — 阴郁苏联摄影** | Krea 2 Base（Turbo 通用） | 晚期/后苏联阴郁：赫鲁晓夫楼、淹没的地下室、锈蚀游乐场、公共厨房、钠灯冬院；低饱和、重阴影、雾、颗粒、静默恐惧；城市衰败 / 阈限空间 / 悬疑氛围；约 100 张手标图 | `sovdark` **放开头**；0.8–1.0（1.0 全阴郁，0.7 轻触）；8 steps/CFG1/Euler-Simple，832×1216。可叠 Mr4k Sk4zka(0.5) 做斯拉夫怪物、Cheap Phone Photo(0.5) 做「翻到的旧手机照片」 | [3020101](https://civitai.com/models/3020101) |
| **Soyuzmultfilm 苏联动画** | Krea 2 | 苏联联盟动画厂手绘赛璐璐：粗黑墨线勾人物与前景道具、无边框背景、平涂无阴影色块、手绘背景纹理；2000 steps/25 epochs/80 图（源自《Nu Pogodi!》） | `soyuzmultfilmstyle, [主体], Cel animation style, thick black ink outlines, borderless background, flat unshaded colors, hand-painted background texture`；1.0；112 MB | [2817513](https://civitai.com/models/2817513) |

### U. 拉美 / 中东北非（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Día de Muertos 亡灵节** | ZImageTurbo（另有 Krea 2 版） | 墨西哥亡灵节：写实肖像+墨西哥民间艺术+复古 calavera 插画+暖调电影光；橙/紫/粉/深黑，金盏花瓣、糖骷髅、烛光祭坛、巨型木偶游行 | `(dia de muertos style:1.1)` + calavera / catrina / cempasúchil / papel picado / ofrenda 等；162 MB | [2505576](https://civitai.com/models/2505576) |
| **Tukano Raw Film** | Krea 2 | 墨西哥街头真实感：鹅卵石路、殖民建筑立面、电网、传统市场、墨西哥女性的日常装与刺绣礼服；粗 35mm 颗粒、自然光、高对比「脏写实」；2000 steps/10 epochs | `TknRwFlm`；1–2（1.0 纯环境/传统服饰聚焦）；218 MB | [2814290](https://civitai.com/models/2814290) |
| **Y2K MENA Aphrodite** | ZImageTurbo（另有 Flux Klein 9B 版） | 2000 初中东/北非女性自然美：暖调电影光、真实胶片颗粒、Y2K 层叠珠宝、年代准确时装；全身电影感/生活抓拍/情绪氛围构图；200 图 | `Y2K MENA Aphrodite`；1.0；Clip Skip 1；162 MB | [2705805](https://civitai.com/models/2705805) |

### V. 游戏过场电影化（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **GTA style VI** | Krea 2 / Krea 2 Turbo（另有 ZIT 版） | 复刻《GTA6》预告片的霓虹电影感迈阿密：浓郁色彩、湿润反光、HDR 纵深、傍晚城市层次、细腻颗粒与自然景深；城市/人像/车辆/动态瞬间；50 epochs | `gta6style` **放开头**；1.0；Turbo 8 steps/CFG1/Euler-Simple/1344×768；K2 原始 25 steps/CFG4/1024×576 | [2113254](https://civitai.com/models/2113254) |
| **Ellie — The Last of Us** | Krea 2 | 100+ 张游戏内截图训练的角色 LoRA；复刻 Naughty Dog 电影化渲染质感，可作游戏过场/写实末世题材角色模板 | `ellie14`；游戏风格提示词：`The Last of Us Part I remake, Naughty Dog cinematic rendering, AAA PlayStation game graphics, in-game cinematic, filmic rendering` | [2836448](https://civitai.com/models/2836448) |

### W. 超级英雄 / 动画风格（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Krea 2 DCAU Art Style** | Krea 2 | 布鲁斯·蒂姆宇宙（正义联盟动画）画风：美式超级英雄卡通；服装依赖底模数据集，作者计划后续版本贴近剧集；6 epochs | `dcau` / `superhero` / `animated` / `cartoon` / `justice league`；fp32 447 MB | [2875820](https://civitai.com/models/2875820) |
| **Strange Cover Universe of Marvel** | Flux.1 D | 1988–1992 复古漫画封面：粗线条、鲜艳配色、动态姿势、底部黄色标题条；可输入英雄/反派英文名+年份 | `Strange cover` / `TitanS cover` / `Special Strange cover`；584 MB；负面词写 `no naked, perfect body with perfect head, two arms and two legs` | [2470928](https://civitai.com/models/2470928) |
| **Jessica Cruz — Green Lantern** | Krea 2 | 绿灯侠角色，绿色能量构造（拳/盾/翼/盔甲/能量衣）表现力强；写实/电影/漫画/动画多风格通吃，2000 steps/10 epochs | `greencruz`；1.0；`cutout-suit` / `classic-suit` 两套服装 | [2880059](https://civitai.com/models/2880059) |
| **Power Girl** | Krea 2 / ZIT / Pony | 写实向超女角色：金发短波波头、蓝眼、白色连体衣+红披风+金绳，强调身份稳定不漂移成泛金发超英；ZIT 版用自然语言提示而非 tag 堆 | `dcpowergirl` **放开头**；写实全身/半身英雄照最佳 | [2439556](https://civitai.com/models/2439556) |

### X. H3 视频工作流（3 个，与 EP001 直接相关）

> 这三项是 **workflow/工具**，不是风格 LoRA 权重本身，但直接决定 H3 出片的速度与打斗可信度，故一并收录。

| 名称 | 类型 | 具体功能 | 关键参数 | 链接 |
|---|---|---|---|---|
| **MiniMax H3 Action Director 9 Combat Presets** | 工作流（H3） | 一张图覆盖文生视频/首尾帧/双人参考三种模式，9 种格斗预设：A0 基础拳脚、A1 高动态修复、A2 双人攻防（默认）、A3 综合武术、A4 刀剑兵器、A5 枪斗、A6 持续枪战、A7 近身枪斗、A8 通用动作修复。自动挂 H3_Combat_V2(0.65)+H3_Fight_Flow_V1(0.25)；可选 3D latent 放大到 1344×768；原生音频输出 | 三种模式 20/20/25 steps；秒数自动换算 17n+5 帧@24fps；依赖 fl2va_pruned_int8_convrot + qwen3vl_32b + video/audio VAE + latent upscaler + ref lora | [3003606](https://civitai.com/models/3003606) |
| **MiniMax H3 TaoMate 3 Step Acceleration** | 工作流（H3） | 两遍式加速：Pass1 用 TaoMate-H3 step3000 LoRA 以 3 步 euler 快速草稿；Pass2 用 SelfLift+完整 Wushu LoRA 栈细化到 2K。Wushu 栈：wushu_e3(0.75)+H3_Combat_V2(0.35)+camera motion(0.35)+spatial physics(0.3)+Motion Repair(0.2)+weapon combat(0.1)；1080P 近 1 帧/秒基准 | 混合 FL2VA/Ref2VA bf16 + Qwen3-VL 32B INT8 ConvRot；3-step simple；24fps MP4。注意图中有多条旁路分支，只保留活动分支 | [2942481](https://civitai.com/models/2942481) |
| **Enzino MiniMax H3 WF** | 工具包（H3） | ComfyUI 一体化 H3 工作流：4 种生成模式（文/图/首尾帧/3 图参考）+ 提示词助手（电影镜头、18 种运镜、对白、旁白、音效、音乐）+ 3 个 LoRA 独立控制 + 15 秒时长 + 实时预览 + 1080p/1440p 放大 + H.264/AAC 导出；8GB 显存优化（SageAttention/Flash Attention/EasyCache/OOM 自动重试） | 需较新 ComfyUI 原生 H3 支持；解压到 custom_nodes 后加载 workflows/enzino_h3_wf.json；免费版已有完整链，Full Edition 付费 | [3002944](https://civitai.com/models/3002944) |

### Y. 电影布局（1 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **cinematic_layout_style 电影布局风格** | Krea 2 | 中文作者电影/概念/风格布局 LoRA，附 19KB 提示词 txt；436 MB；页面有「画质缩水/LoRA 无效」警告，建议先小样测试 | `cinematic_layout_style`；1.0 | [2785466](https://civitai.com/models/2785466) |

### Z. 本轮关键发现

1. **打光流派独立于电影流派**：V67 Lighting / HDR Intense、The Revenant 这类 LoRA 只教「怎么打光」，不绑定年代/地域，可以叠在港片武侠、科幻等任何主风格之上做二次调光。触发词位置敏感（必须开头）是 V67 家族通病。
2. **H3 打斗链已经工程化**：Action Director 把它们做成了 9 个预设开关，TaoMate 做到 3 步加速+两遍细化。你的 EP001 武侠打斗镜头可以直接套 A2（双人攻防）/A4（刀剑）/A5（枪斗）+ Wushu 栈，不必自己逐个 LoRA 试权重。
3. **Krea2 跨底座复用再添 3 例**：V67 Steampunk、Steampunk-CE 都出了 Flux/Klein/ZIT/SDXL/Ernie 全版本，Retrofuturism 和多数苏俄 LoRA 属 V67 家族（同作者按底座分别导出）。换底座不必重找风格。
4. **地域空白继续缩小但不能硬凑**：苏俄、墨西哥、中东已有专门 LoRA；但「北欧犯罪剧」「印度宝莱坞」本轮仍只搜到通用电影感或人物 LoRA，没有地域风格专款，已如实不收录。
5. **多布光 LoRA 冲突要注意**：V67 Lighting / HDR Intense / Ultra Vision 是同一作者的三款打光 LoRA，功能重叠，不要一次全叠——按场景选一款即可，否则光效互相稀释。

---

## 第十五部分：中式美学 / V67 滤镜与绘画 / 动态姿势 / 90s 怀旧（2026-11-25 十轮挖掘，18 个新增）

> 本轮聚焦此前空白的中国古典美学与绘画流派、电影后期滤镜、姿势/机位控制概念 LoRA，以及 90s 怀旧胶片。已与文档既有条目去重（Ray 合集 2802215、王家卫 3023454、90s Movie Grit 2833506、H3 90s Wuxia 2954281 等均为旧条目）。

### AA. 中式美学 / 国风（6 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **MJ 中式美学** | Krea 2（另有 MOSS-Image 版） | Midjourney/Nijourney 风格的中式美学；5000 steps；MOSS 版有发型/眼睛/面部高度重复问题，仅 8-step 工作流勉强可用 | `MJCN_Style`；218 MB | [2948991](https://civitai.com/models/2948991) |
| **国风幻想游戏美宣** | Krea 2 | 中国幻想商业游戏美术：精细数字绘画、电影化光影、华丽材质、少量水墨笔触与东方装饰；适合古风角色立绘、剧情卡面、横版 KV、战场叙事、动态战斗 | `gqmtdx7` **放开头**；0.8–2.3（建议从 1.2 起，高权重强化国风/华丽服饰/古建/美宣质感） | [2869230](https://civitai.com/models/2869230) |
| **V67 China Word** | ZImageTurbo（另有 Krea2 / Ernie 版） | 传统中国与未来科技融合：春节/生肖/烟花/舞狮/红灯笼/剪纸/孔明灯/庙会/乡村/木雕/舞龙/熊猫；古今交汇主题 | `(China Word:1.2)` + 具体元素词；162 MB | [2522859](https://civitai.com/models/2522859) |
| **Gray Ink 灰墨** | Krea 2 Raw→Turbo（另有 ZIT / Illustrious-XL 版） | 中国水墨插画：细密深色墨线+灰纸纹理、洇染、大面积扫描阴影；源自公版中国插画版画。**三底座文件不可互换** | `zxy_grayink_style`；0.6–1.0（0.8 起）；K2 Turbo 1280 steps/rank32、ZIT 1000 steps/9 steps/CFG1、Illustrious 28 steps/CFG5 | [2960333](https://civitai.com/models/2960333) |
| **V67 Beautiful Oriental Painting** | ZIT / Krea 2（V67 绘画家族） | 古典中国美人：丹凤眼、玉肌、水墨与油画混合、雾山与红灯笼；唐代审美+油画质感，适合人像 | `(Beautiful oriental painting:1.1)` + chinese beauty portrait / painterly chinese face 等 | [2580026](https://civitai.com/models/2580026) |
| **Absolute CINEMA** | Krea 2（另有 MOSS / Chroma 版） | 136 张电影剧照训练，专门避免「stock/精修广告感」，让画面像真正演员出演的电影；Krea2 版为 8-step Turbo 用 | 权重 1.0；作者另有 retro 80s 版 | [1960106](https://civitai.com/models/1960106) |

### AB. V67 后期滤镜与绘画家族（5 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Cinematic Filters** | Flux / ZIT / Krea 2 | 把 20 种电影后期滤镜直接内建：黎明黄金时刻、夜极光、复古模拟、颗粒光晕、teal-orange、抬黑位、三分构图柔光、薄雾扩散、压暗阴影、暖高光冷阴影、bleach bypass、halation、齿孔/边缘标记、粉彩褪色、低对比等；免外部调色软件 | `(cinematic filter:1.2)` + 具体滤镜词；162 MB | [2512256](https://civitai.com/models/2512256) |
| **V67 Photo Painting** | Krea 2 / ZIT 等 | 绘画家族基石：超写实摄影清晰度+古典绘画笔触/画布纹理，「像照片但有绘画的灵魂」；常作 binding 层与 Museum-quality 等叠加 | `photo_painting` + oil_painting_style / palette_knife_style / canvas_texture / visible_brushstrokes | [2430955](https://civitai.com/models/2430955) |
| **V67 Museum-quality Oil Painting** | ZIT / Krea 2 | 博物馆级油画：鲜艳色彩、8K 细节、写实与笔触可控融合；常与 Photo Painting/东方绘画/数字文艺复兴做绑定层 | `(Museum-quality oil painting:1.1)` | [2757925](https://civitai.com/models/2757925) |
| **V67 Beautiful European Painting** | Krea 2 / ZIT 等 | 欧洲古典油画：文艺复兴肖像、卡拉瓦乔式明暗、正式优雅；与 Museum-quality 叠加加深黑色丰富色彩 | 按家族触发词 | [3030918](https://civitai.com/models/3030918) |
| **CinemaGrade Krea2 原版** | Krea 2 | 电影级调色+现实增强，是 H3 版 CinemaGrade 的来源（用户此前记录的 Krea2→H3 转换链即源于此）；训练于高质量电影调色图，情绪化真实输出+天然颗粒与镜头光晕 | `a3sthet1c` 放开头（可省略求更轻效果）；0.9；建议双阶段 Krea2 工作流+WAN VAE，第二阶段用 turbo distill 12 steps | [2902077](https://civitai.com/models/2902077) |

### AC. 姿势 / 机位控制概念 LoRA（1 个，与运镜关注点相关）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **More Dynamic Poses** | Krea 2（另有 ZIT / Illustrious / Anima 版） | 让角色脱离静态正面呆站：更多姿态/肢体语言/不对称、更强运动感、时尚/动作/电影姿势；高/低/后/侧/俯拍/地面/非常规机位；融合 Posing Dynamics/Warrior Poses/K-Pop Poses 经验 | `PoseDaal`；0.5–1.5（1.0 甜点，1.2–1.5 更激进）；可叠其他 LoRA；提示给意图+机位即可，不必描述每个肢体 | [2914130](https://civitai.com/models/2914130) |

### AD. 90s 怀旧 / 港风（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Back To 90s** | Krea 2 | 90 年代一次性胶片相机：直接闪光、粗颗粒、暖调复古色、柔和焦点；把干净数字图变成真实的 90s 实体照片 | `90s color photograph`；1.0；3000 steps/10 epochs | [2850091](https://civitai.com/models/2850091) |
| **80/90s 怀旧摄影（含港风）** | SDXL 1.0 | 80–90 年代中国/香港日常小场景怀旧摄影；接近 1 会有老照片模糊感 | 无专门触发词；权重 <0.8 推荐；334 MB | [135036](https://civitai.com/models/135036) |

### AE. 舞台 / 人物地域（4 个，补充类目）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Pop Idols 48** | ZIT / Krea 2 | J-Pop / K-Pop 偶像舞台：日式制服到韩式华丽舞台装、偶像姿势、闪耀舞台灯、群舞氛围；含 AKB48/乃木坂46 等 10 组风格；全 18+ | `(Pop idols 48, J-Pop, K-Pop:1.1)` + pop48 style / 48 hand sign / fanlight stick ocean 等 | [2694651](https://civitai.com/models/2694651) |
| **东南亚/泰国女性** | Krea 2（另有 ZIT / Flux Klein 9B 版） | 真实东南亚女性 20–40 岁，写实人像；含有限 NSFW 数据，可用 `young`/`mature` 控年龄 | 无明确触发；1.0（可到 1.5）；3000 steps | [2180115](https://civitai.com/models/2180115) |
| **Nastya Volkova 俄罗斯芭蕾** | Krea 2 | 角色 LoRA：芭蕾/时尚编辑/人像/生活/电影场景；附俄英双提示词包（芭蕾、日常、时尚、电影、成人场景） | `nastya volkova`；1.0；Krea2 Rebalance 4.0 / 4 steps / CFG1 / Euler-Simple / 4MP | [2999886](https://civitai.com/models/2999886) |
| **Krea2_YuYe_style 暗黑电影美学** | Krea 2 | 雨夜朦胧模糊风格（中文作者「雨夜」）；权重建议 2 才出效果 | 无明确触发；**2.0**（高权重例外）；218 MB | [2805002](https://civitai.com/models/2805002) |

### AF. 本轮关键发现

1. **V67 已成体系化「组件库」**：同一作者 angelomaiota 把打光/滤镜/绘画/地域拆成独立组件，可单独用也可叠加组成统一美学。本轮新增的 Cinematic Filters（后期）、Photo Painting / Museum-quality / Oriental / European（绘画）都是这套组件，触发词多为 `(组件名:1.1)` 放开头。
2. **V67 Cinematic Filters 是最实用的一款**：把 teal-orange / bleach bypass / halation / 齿孔边缘标记等 20 种 LUT 内建，省掉外部调色；注意与 V67 打光三件套（Lighting/HDR/Ultra Vision）功能不同——滤镜管「后期调色」，打光管「现场布光」，可以分层叠加。
3. **概念 LoRA 补齐「动态姿势」空白**：More Dynamic Poses（PoseDaal）专治 AI 静态呆站，明确训练了高低俯仰/后侧/地面机位，与 Astro Cinema V02（镜头语言）互补——一个管人物姿态，一个管摄影机，可叠加使用。
4. **绘画流派 LoRA 密集出现**：V67 Photo Painting / Museum-quality / Oriental / European + 灰墨 + MJ 中式美学，说明「摄影写实 + 绘画质感」混合是 Krea2/ZIT 的新热点；这类偏插画/美宣，EP001 真人向场景慎用，但适合概念板与古风支线。
5. **CinemaGrade Krea2 原版终于收录**：此前只记录了从它转换出的 H3 版，本轮补上源头；想自制 H3 风格 LoRA 时应从这里取 150 张图。

---

## 第十六部分：时尚商业 / 导演流派 / 自然建筑 / 赛博星空 / H3新风格（2026-11-25 十一轮挖掘，27 个新增）

> 本轮扫描此前未覆盖的时尚杂志、商业广告、建筑空间、自然微距、星空天文、导演流派等品类。26 个 LoRA + 1 个导演型 checkpoint（Serendipity，单列说明）。以下均为页面标注底座与参数，非本地实测。

### R. 时尚 / 杂志 / 商业摄影（6 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **VOGUE BY STX V4** | Krea 2 | 高端生活方式/杂志人像"人性修复器"：去 AI 塑料感、真实皮肤（雀斑/毛孔/发丝）、黄金时刻穿窗光、香烟体积烟、街头动态模糊；织物物理精准（针织毛衣/粗斜纹牛仔），自带复古 35mm 柔颗粒 | 无需固定触发词，靠提示词驱动；218 MB，4000 steps/20 epochs | [2901040](https://civitai.com/models/2901040/vogue-by-stx) |
| **LuxCinema PhotoReal** | Krea 2 | 名流/高定时装棚拍：柔和方向主光 + 文艺复兴式明暗、深天鹅绒褶皱、金线刺绣反光、皮肤毛孔与散落发丝；作者声称不用负面词 | `lux` 必须放开头；0.8–1.0（0.85 干净面部 / 1.0 织物纹理最大化）；CFG 1.2–1.6、25–30 steps；382 MB | [2854999](https://civitai.com/models/2854999) |
| **Stylized Commercial** | Krea 2（另有 ZIT 版） | 高端广告/产品/品牌视觉：干净构图、平涂插画审美、大胆配色、精致阴影；适合香水瓶/奢侈品/生活方式 | `stcom`；Raw 0.9 / Turbo 1.0；提示含 "premium commercial advertising" | [2872288](https://civitai.com/models/2872288/stylized-commercial) |
| **Luma Krea2** | Krea 2 | **风格无关的画质增强层**：更深黑位、主体分离、跟随提示词配色的饱和度、皮肤/织物/树叶微细节；跨写实/动漫/美食/建筑/ wildlife 通用，不把非写实风格拉回写实 | 无触发词；0.2 轻增强 / 0.5 甜点 / 0.7–0.8 编辑级 / 1.0 杂志级 | [2950530](https://civitai.com/models/2950530) |
| **High-Fashion Editorial** | SDXL 1.0 | Vogue/Harper's Bazaar 式高级时装：戏剧化影棚/外景光、雕塑感造型、成熟配色、留白构图、绘画感皮肤与织物 | `3d1tor14l`；0.85（0.6–1.0）；EMA sampler 最佳；88.75 MB | [2665442](https://civitai.com/models/2665442) |
| **Event Horizon KreaLoraLab（合集入口）** | Krea 2 | Electric Dreams 出品的 **40+ 款 Krea2 LoRA 合集**（持续扩容至近 50）：German Expressionism、Giallostyle、70sHorror、Noirstyle、Technicolor Decó、Living 50/70/80s、RetroCyberpunk、N64/PSX 游戏机、Diorama 微缩、POV、Kuniyoshi、Beardsley、Maya Lanez 等。基于 Event Horizon 底模测试，其他 K2 底模效果可能不同 | 各子款独立触发词；Ko-fi 打包获取 | [2958510](https://civitai.com/models/2958510) |

### S. 导演 / 流派电影风格（6 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **German Expressionism** | ZImageTurbo | 20 世纪初德国表现主义：扭曲建筑、倾斜墙面、夸张垂直/对角线、手绘布景感；单一硬光源、深黑亮白、角度化长影；默片颗粒/闪烁/门框抖动/软边、正色性胶片调；人物戏剧化姿态而非写实 | 无需触发词；0.7；7000 steps/14 epochs；121.7 MB | [2254403](https://civitai.com/models/2254403/german-expressionism) |
| **Twin Peaks by Fortnox** | Krea 2 | 大卫·林奇《双峰》90s 纪录剧质感：暖琥珀+森林绿、柔焦扩散辉光、35mm 颗粒、明暗对比、小镇怪诞不安；红房间/红窗帘/人字纹地板、樱桃派咖啡、转盘电话 | `twinpeaks_style`；1.0；218 MB | [2879929](https://civitai.com/models/2879929/twin-peaks-by-fortnox) |
| **韦斯·安德森画风（Andesen style）** | Krea 2 | 韦斯·安德森美学：对称构图、有限配色、复古室内、精心摆放的物件 | 无触发词，建议让 AI 写韦斯·安德森电影感提示词；建议配合作者人像 LoRA；223.81 MB | [2900396](https://civitai.com/models/2900396/wes-andersonstyle-aesthetic) |
| **mhDreamy** | Krea 2 | 梦幻艺术片单帧：暖金实用光穿雾、高光柔和滚降、干净深阴影、轮廓光剪影、轻颗粒；**重打光而非重画主体**，雾/雨/夜街/烛光室内/黄金时刻最佳 | `mhDreamy, dreamy golden-lit ethereal illustration`；量化(int8/nf4/fp8)用 2.0、raw bf16 用 1.0–1.5；动漫 <0.6；负面加 text/watermark/signboard/letters；218 MB | [2973085](https://civitai.com/models/2973085/mhdreamy-dreamy-cinematic-style-krea-2) |
| **Oddling Reverie** | MOSS Image（另有 Krea2 / ZIT 版） | 电影超现实：奇异小生物、超大表情眼、不完美解剖、绒毛/旧织物触感；暖琥珀高光+深青阴影、柔光浅景深、童年怀旧又诡异 | 无明确触发词；138.43 MB；三底座不可混用 | [3029966](https://civitai.com/models/3029966/oddling-reverie) |
| **Serendipity V2/V3（导演型 checkpoint）** | Krea 2 Turbo **checkpoint（非 LoRA）** | 作者用自家摄影档案训练后**直接 merge 进 Krea2 Turbo 底模**：过肩镜头、极端前后景散景、广角尺度、全身腾空/武术姿态、悬浮物件物理、体积光/上帝光。定位"导演"：Soliloquy 拍特写，Serendipity 拍电影 | 用 wide shot / over-the-shoulder / low-angle tracking / anamorphic flare 等镜头词；分层描述前中后景 | [2844869](https://civitai.com/models/2844869/serendipity) |

### T. 自然 / 动物 / 微距（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Apollo Krea2 Style** | Krea 2 | 1969 NASA 阿波罗档案：土星五号发射台、地球地平线、重颗粒、褪色低对比阴影；复古纪实太空片 | `Apollo` + `In the style of a vintage 1969 documentary`；218 MB | [2756270](https://civitai.com/models/2756270/apollo-krea2-style) |
| **Whimsical Taiga Macro (Evgeniya Levina)** | Krea 2 | 西伯利亚泰加森林童话微距：巨型蘑菇当房屋、松鼠花栗鼠小道具、雪覆春花、苔藓桌面与橡果杯；深绿苔藓质感、北境漫射光；硬核微距+童话布景 | `macro wildlife photography in the manner of Evgeniya Levina`；0.85–1.0（1.0 锁定微距景深）；1536×1024 或 1024×1536；218 MB | [2985614](https://civitai.com/models/2985614) |
| **Animal Kingdom (rkwildlens)** | Krea 2 | 极端超广角鱼眼怼脸动物：镜头离脸几厘米、低机位仰拍、爪子伸向观众、远处大风景；画面内低太阳星芒+金色 HDR；含半水下分割/洞内/空中俯冲/微距露珠多种构图 | `rkwildlens` 放开头；1.0；**竖屏 9:16 训练（941×1672）**；218 MB | [3008017](https://civitai.com/models/3008017) |

### U. 建筑 / 空间 / 场景控制（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Brutalist interior design** | Krea 2（另有 FLUX 版） | 粗野主义室内：混凝土、暗淡色调、极简效率感；社区反馈是"时尚/前卫人像与机构场景（办公室/学校/中性墙）的最佳背景板" | 推荐 0.4–0.5（页面写 1.0，实测低权重更稳）；218 MB | [1636847](https://civitai.com/models/1636847/brutalist-interior-design) |
| **Decaying Brutalism (Buildings)** | Krea 2（另有 Anima/FLUX 版） | 衰败粗野主义建筑群；同页含 Brutalist Church Interior、Modern Office Building 等 436 项建筑合集 | 按页；218 MB | [3030909](https://civitai.com/models/3030909/decaying-brutalism-buildings-krea2-ad) |
| **Steampunk Interior** | Krea 2（另有多底座） | 蒸汽朋克室内建筑：`SteIntArc`；15–35 steps、CFG 2.5–5 | `SteIntArc`；0.8–1.25 | [2873466](https://civitai.com/models/2873466/steampunk-interior-architecture-buildings-krea2-ad) |
| **Visual Sci-Fi Minimalism** | Krea 2 | 纪念碑式科幻极简：巨型未来建筑、朴素混凝土内景、广阔沙漠/雾工业景；广角建立镜头、剪影、体积光、低饱和；**刻意避开赛博朋克杂物**，走维伦纽瓦式干净硬科幻 | 主触发 `Devastator2049`；另有 `TitleCardPoster`/`hud49`/`holo49`/`HoltzmanShield`/`monochrome infrared-style` 子令牌；0.7–1.2（1.0 甜点）；6286 steps/11 epochs | [3055545](https://civitai.com/models/3055545/visual-sci-fi-minimalism-krea2) |

### V. 赛博朋克 / 星空 / synthwave（4 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **CYBERPUNK – NEON DECAY** | **MiniMax H3 视频版** + Krea2 双版 | H3 赛博朋克视频：从霓虹巨城/雨街到锈蚀工坊、企业玻璃大厅；**不锁死青粉配色**，调色跟随提示词；材质训练充分（锈/玻璃/铬/湿路面/线缆）。配套 Krea2 版可先出图再转视频 | `neon-decay`；1.0 起；H3 版 295.8 MB，2000 steps/15 epochs | [2951853](https://civitai.com/models/2951853) |
| **V67 Cyberpunk** | FLUX / Krea2 / ZIT 三版 | 1960s 复古未来赛博朋克：旧皮夹克、发光义体、湿沥青霓虹小巷、Syd Mead 式数字绘画；雨夜、朋克叛逆+高科技颓废 | `(cyberpunk:1.2)` + retro-futuristic / neon-lit / rainy street 等；ZIT 版 162 MB | [2475476](https://civitai.com/models/2475476/v67-cyberpunk) |
| **V67 Stars and Galaxies** | FLUX / Flux.2 / Krea2 / ZIT 四版 | 深空天文：旋涡星系、发射/反射/暗星云、行星环系、彗尾、黑洞吸积盘、引力透镜、空间站与宇航员；`V67` 前缀 + 12 类关键词 | `(starfield, galactic core:1.2)` 等；218 MB；四底座不可混用 | [2507359](https://civitai.com/models/2507359/v67-stars-and-galaxies) |
| **Synthwave-Style** | ZIT（另有 KREA2 alpha / SDXL V2 / IL 等） | 80s synthwave/vaporwave 世界变形：霓虹、复古车、线框山、合成天空；**整场景 morph** 而非只改色调 | `synthworld`；0.4–0.6（ZIT 版 Z-Image 权重偏重，作者建议 0.4 起）；SDXL/IL 版效果最佳 | [1463207](https://civitai.com/models/1463207/synthwave-style) |

### W. 单部电影风格（2 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **2 Fast 2 Furious 2003** | Krea 2 | 《速度与激情2》2003 胶片：阳光下明黄轿车、棕榈树商业街、低机位追车、湿夜警灯、手动挡换挡特写、沙尘翻车；高饱和明亮色调 | `2fst2frs2003`；1.0 起（更低权重更易叠加）；2000 steps/3 epochs | [2981065](https://civitai.com/models/2981065) |
| **Hot Rod 2007** | Krea 2 | 《Hot Rod》2007 喜剧：车库焊接火花、泥地摩托跳台、红白蓝横幅记分牌、泳池后院、柔和阴天漫射；土褐+红+浅蓝配色 | `htrd2007`；1.0 起；2000 steps/3 epochs | [2997875](https://civitai.com/models/2997875/hot-rod-2007-movie-lora-style) |

### X. H3 视频新增（1 个，含可复用转换配方）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **KuroDrive（黑白汽车插画）H3 版** | MiniMax H3（fl2va） | 单色汽车插画风格视频；**H3 底模会往写实拉，需提高权重到 1.3–2.0**；两个权重文件 ep35（柔和）/ep50（更强），先试 35 | `kurodrivestyle` 放开头；1.0 起，实际常需 1.3–2.0；68.31 MB；`LoraLoaderModelOnly` 加载 | [2919290](https://civitai.com/models/2919290/kurodrive-monochrome-automotive-illustration-minimax-h3-style-lora) |

### Y. 本轮关键发现

1. **Krea2 → H3 转换配方再获独立佐证**：KuroDrive H3 版作者公开的训练参数与之前 CinemaGrade/80s Commercial/KreaLand 完全一致——150 张 Krea2 生成图（每个主体唯一、50% 人物、每条 caption 含电影镜头词汇）→ rank8 / blocks 0-3,6-47 / shift 0.6667 / LR 2e-4 / adamw / 50 epochs。你本地三个 Krea2 电影风格 LoRA 可按此自制 H3 版。
2. **"先出图再转视频"成标准链路**：NEON DECAY、KuroDrive 均同时提供 Krea2 图像版与 H3 视频版，作者明确建议 Krea2 出静帧 → H3 让世界动起来。风格一致性靠同一 LoRA 家族而非提示词硬凑。
3. **插画类 H3 LoRA 需要超权重**：KuroDrive 从 1.0 起调到 1.3–2.0 才压过 H3 的写实先验；这跟写实类 H3 风格（Cinematic V2 0.5–0.7）方向完全相反。
4. **checkpoint 与 LoRA 要分清**：Serendipity 是 merge 进 Krea2 Turbo 的独立 checkpoint，不是放进 `models/loras/` 的权重；它解决的是"镜头调度/空间深度"，与风格 LoRA 职能不同。
5. **类目仍有空白**：本轮"静物美食/体育赛事/公路片"未搜到专门电影风格 LoRA，只返回通用电影感或已收录条目，未硬凑。

---

## 第十七部分：V67 概念组件库 / 黑白单色 / 间谍青春 / H3艺术家风格（2026-11-25 十二轮挖掘，15 个新增）

> 本轮最大发现：V67 作者为 Promptyx 站点训练了 **10 个"概念组件 LoRA"**，职能与之前收录的 V67 风格 LoRA 完全不同——它们不提供固定审美，而是把提示词的一个维度（打光/镜头/配色/氛围/天气/年代/姿势等）做成可叠加的控制层。这批全部非本地实测，依据页面标注。

### Z. V67 概念组件库（10 个，Promptyx 体系）

> 用法：先从 Promptyx（perchance.org/promptyx）的 Boosters 菜单选项目生成提示词串，再配合对应组件 LoRA。触发词统一为 `(组件名:1.1)` 放提示词开头。除 Lighting 已在此前收录外，其余 9 个均为本轮新增。当前只有 Krea2 版，作者计划扩展到 Flux / ZIT / Ernie。

| 组件 LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **V67 Camera & Lens** | Krea 2（另有 ZIT 版） | 相机/镜头概念控制：旁轴/SLR/DSLR/微单/中画幅、微距、广角、长焦、定焦/变焦、手动对焦、光圈/快门/ISO、镜头光晕、玻璃反射、bokeh；把"摄影器材语言"注入出图 | `(V67 Camera & Lens:1.1)` 开头 + CamLens/camera/lens/analog/rangefinder/macro 等；218 MB，2000 steps/3 epochs | [2949466](https://civitai.com/models/2949466/v67-camera-and-lens) |
| **V67 Color Palette** | Krea 2（另MOSS/ZIT/Flux 2） | 配色板控制：深靛蓝、电青、酸橙绿、暖珊瑚、奶油白、霓虹点缀、高对比、复古未来、赛博氛围、编辑时尚、产品摄影、极简、光泽反射、体积光；内置 6 种组合配方（Neon Duo / Acid Pop / Cyber Twilight 等） | `(Color Palette:1.1)` 开头；0.65–0.85；218 MB | [2554165](https://civitai.com/models/2554165/v67-color-palette) |
| **V67 Mood & Atmosphere** | Krea 2 | 情绪/氛围维度控制 | `(Mood & Atmosphere:1.1)` 开头 | [2958327](https://civitai.com/models/2958327/v67-mood-and-atmosphere) |
| **V67 Quality Boost** | Krea 2 | 画质增强维度（非固定风格） | `(Quality Boost:1.1)` 开头 | [2966205](https://civitai.com/models/2966205/v67-quality-boost) |
| **V67 Environment & Weather** | Krea 2 | 环境/天气维度：雨雾风雪、时间气候 | `(Environment & Weather:1.1)` 开头 | [2967611](https://civitai.com/models/2967611/v67-environment-and-weather) |
| **V67 Artist Style** | Krea 2 | 艺术家风格维度控制 | `(Artist Style:1.1)` 开头 | [2969806](https://civitai.com/models/2969806/v67-artist-style) |
| **V67 Era & Genre** | Krea 2 | 年代/类型维度：1940s/70s/80s + noir/sci-fi/western 等 | `(Era & Genre:1.1)` 开头 | [2970592](https://civitai.com/models/2970592/v67-era-and-genre) |
| **V67 Creature & Character** | Krea 2 | 生物/角色维度控制 | `(Creature & Character:1.1)` 开头 | [2972167](https://civitai.com/models/2972167/v67-creature-character) |
| **V67 Pose & Framing** | Krea 2 | 姿势/构图维度：与 More Dynamic Poses、Astro Cinema V02 职能相近但走 V67 提示词体系 | `(Pose & Framing:1.1)` 开头 | [2972585](https://civitai.com/models/2972585/v67-pose-and-framing) |
| **V67 Robotics**（补充，同体系扩展） | Flux / Krea 2 | 机器人/机甲概念控制：维多利亚蒸汽机器人、1950s复古、赛博义体、重型机甲、异形无人机、太空采矿船；需显式写材质（黄铜/钢/铬/锈/陶瓷）和年代，否则材质发平 | `V67 [class] + [era] + [materials] + [action] + [setting] + [lighting]`；材质平就加到 0.75–0.8；ZIT 偏软用 CFG1.2–1.8 | [2507831](https://civitai.com/models/2507831/v67-robotics) |

### AA. 黑白单色 / 暗调（3 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **DC Obsidian Monochrome v2** | Krea 2 Raw（另ZIT/Flux Klein 9B/SDXL版） | 极暗单色+粗颗粒+高光溢出，模仿 mertzv2 黑白影像；v2 Raw 版能自主保持灰度/颗粒，v1 需提示词强制。可换色（蓝/橙/绿单色） | K2 Raw v2：`DCOBMON.`；v1：`DCOBMON. black monochrome image of`（换色改 black 为 blue 等）；ZIT/Klein：`DCOBMON.`；结尾加 `heavy film grain and rough texture cover the frame` | [2411024](https://civitai.com/models/2411024/dc-obsidian-monochrome) |
| **YFG Spy World 50s** | Krea 2（另有 Flux 版） | 50 年代冷战间谍片：风衣/软呢帽/晚礼服、微型相机与窃听器、复古未来城市、低饱和+暗角、noir 布光；中世纪现代宅邸/秘密实验室场景 | `YFG-SpyWorld50s` + spy/espionage/cold war/surveillance 词；0.6–0.8（可 0.05–2.0）；218 MB | [1091414](https://civitai.com/models/1091414/yfg-spy-world-50s-flux-or-krea) |
| **Last Days of Film — Early 1990s** | ZImageTurbo | 80末90初胶片写实：**最佳用法是低降噪 img2img（denoise 0.4–0.8）+ 权重 0.75**，也可当放大器（denoise 0.3–0.6）；做旧细节强，直接 T2I 易出重复脸 | 权重 0.75；可配 Flux2 Klein 出初稿再 ZIT 精修；162 MB | [2335283](https://civitai.com/models/2335283/last-days-of-film-early-1990s) |

### AB. 青春校园 / 单部电影（1 个）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **Cruel Intentions 1999** | Krea 2 | 《危险性关系》1999 青春片：马术场、常春藤庄园石阶、钢桁架桥城市天际线、金色午后阳光、绿色草坪与红高跟鞋；高饱和明亮青春色调 | `crlintntns1999`；1.0 起；2000 steps/4 epochs；218 MB | [2953789](https://civitai.com/models/2953789/cruel-intentions-1999-movie-lora-style) |

### AC. MiniMax H3 艺术家风格（1 个，转换配方同源）

| LoRA | 底座 | 具体功能 | 触发词 / 推荐强度 | 链接 |
|---|---|---|---|---|
| **KreaAlex（Bradhamel 艺术家风格）** | MiniMax H3（fl2va） | Bradhamel 绘画/插画风格视频；**插画类需 1.3–2.0 超权重**压过写实先验；ep35 柔和/ep50 更强；本地 WanGP pruned 20B 1920×1080 两遍式可跑 | `bradhamstyle` 放开头；1.0 起常需上调；68.31 MB；转换配方与 CinemaGrade/KuroDrive 完全一致 | [2918791](https://civitai.com/models/2918791/kreaalex-minimax-h3-style-lora) |

### AD. 本轮关键发现

1. **V67 概念组件库是"提示词维度化"的完整方法论**：10 个组件分别控制打光、镜头、配色、氛围、画质、天气、艺术家、年代类型、生物角色、姿势构图。它们**不提供固定审美**，而是把提示词的一个维度训练成可控层。这跟你之前关注的"机位/运镜"直接相关——Pose & Framing + Camera & Lens 可以替代大量文字描述。
2. **组件 LoRA 与风格 LoRA 可分层叠加**：`(Camera & Lens:1.1)` + `(Color Palette:1.1)` + 主风格 LoRA（如王家卫 `wkw1`）三层分工明确。但**V67 打光三件套内部仍不要叠**（此前排错第 15 条）。
3. **触发词格式是小数点**：V67 家族统一 `(组件名:1.1)` 放最前面，不是逗号，也不接受简写。写错会静默失效。
4. **H3 艺术家风格转换已五例互证**：CinemaGrade、80s Commercial、KreaLand、KuroDrive、KreaAlex 全部用同一配方（150 张 Krea2 图 → rank8 / blocks 0-3,6-47 / shift 0.6667 / LR 2e-4 / 50 epochs）。这批 H3 风格 LoRA 的作者（hoodtronik）已形成转换流水线，你本地三个 Krea2 LoRA 可复刻。
5. **类目空白**：本轮"灾难片""体育赛事""歌舞片""婚礼家庭"仍未搜到专门风格 LoRA，返回结果都是通用电影感或已收录条目，未硬凑。

---

# 第十一部分：汇总速查与搭配推荐

> 本部分是全文档的「索引层」：先按底座给出全量汇总表（方便按你手上的模型找 LoRA），再按实际生产场景给出搭配配方（直接抄参数）。
> 收录总数：**本地 5 + 候选 228 = 233 个**（含 1 个导演型 checkpoint Serendipity，非 LoRA）。

## 一、按底座汇总速查（全量）

> 图例：⭐ = 社区高口碑（好评 100+ 或压倒性好评）；🔥 = 与 EP001 / 你的工作流强相关。

### 1. MiniMax H3 —— 视频 LoRA（23 个 + 2 个本地加速）+ 3 个工作流

| LoRA | 风格 / 功能 | 推荐权重 | 备注 |
|---|---|---|---|
| 🔥 Action Director 9格斗预设 (3003606) | 工作流：9 种格斗预设 | A2 攻防/A4 刀剑/A5 枪斗 | 自动挂 Combat 0.65+FightFlow 0.25；可选 3D 放大 1344×768 |
| 🔥 TaoMate 3步加速 (2942481) | 工作流：3 步草稿+Wushu 细化 | 两遍式 | 近 1 帧/秒；Pass2 SelfLift+Wushu 栈细化到 2K |
| Enzino H3 WF (3002944) | 工具包：4 模式+18 运镜助手 | — | 8GB 显存优化；实时预览+1080p/1440p 放大 |
| 🔥⭐ 90s Hong Kong Wuxia (2954281) | 90 年代港片武侠胶片 | 画面 0.6 / 音频 ≤0.3 | 权重>0.3 音频失真；100 段 5s 片段训练 |
| 🔥 Cinematic V2 (2890588) | 通用电影质感 | 0.85 | 首选打底 |
| ⭐ 官方版 Cinematic (2937734) | 通用电影感 | 0.7 | 已移除触发词，省事 |
| Cinematic Look DY版 (2908686) | 修塑料感/过锐 | 0.5–0.7 | 专项解决张量报错 |
| CinemaGrade (2927223) | 电影调色 | 按页 | — |
| 1920s Silent Film (2968359) | 默片老化胶片 | 按页 | — |
| 16mm Found Footage (3015094) | 伪纪录片 | 按页 | — |
| 🔥 Orion Expedition H3版 (3003215) | 科幻/星舰/赛博 | 1.0 | 需 H3 格式提示词（三段式） |
| Sci-Fi Cinema H3版 (2692151) | 未来城市/飞船/全息 | 1.0 | 另有 LTX 版 |
| Minimax Ghost (2938527) | 鬼怪/黑烟幽灵 | 0.7 | 副作用：普通场景也会变暗+颗粒 |
| 🔥 Wushu Motion Control (2942484) | 武术打斗动作 | 工作流 | wushu_e3 0.75 + Motion Repair 0.5 + 空间物理 0.3 |
| ⭐Cinematic 无张量报错版 (2937713) | 剪枝/非剪枝通用电影感 | 0.7 / 高动态 0.5 | 稳定肢体、减少自动切镜 |
| 1980s Horror Movies (1592586) | 80s 僵尸/身体恐怖 | 1.0 | 9 底座系列，`foundfootage16` 类 |
| 16mm Found Footage (3015094) | 伪纪录片/ Blair Witch | 0.8 日 / 0.9–1.0 夜 | `foundfootage16` 开头；CRF≤16 |
| Film Noir Selective Colors (2934763) | 黑白 noir + 局部彩色 | 1.0 | 别写不需要的颜色 |
| 80s Commercial 1983 (2918721) / KreaLand (2919337) | 广告质感 / 风光 | 1.0 | `com80style`/`krealandstyle`；分镜草图+角色参考效果最佳 |
| Neon VHS Dreams (2987989) | 80s VHS 霓虹 + 复古音频 | 0.85–0.95 | 无触发词；自带 80s 音乐质感 |
| MiniDV Nostalgia (2924023) | 2000s 家用 DV 手持 | 0.9 | `y2km1n1dv`；**会削弱 H3 原生音频** |
| 🔥 NEON DECAY (2951853) | 赛博朋克：霓虹巨城/锈蚀工坊/企业玻璃厅 | 1.0 | `neon-decay`；配色跟提示词走，不锁青粉；另有 Krea2 版可先出图 |
| KuroDrive (2919290) | 黑白汽车插画 | 1.3–2.0（需超权重） | `kurodrivestyle`；H3 写实先验会冲淡插画感；ep35 柔和/ep50 强 |
| KreaAlex (2918791) | Bradhamel 艺术家绘画风格 | 1.3–2.0（需超权重） | `bradhamstyle`；转换配方同源；ep35 柔和/ep50 强 |
| Environmental Anime 新海诚 (2650155) | 2D 动画环境/镜头光晕 | 1.0 | `2d anime style, art by makoto shinkai` |
| ModelingClay H3版 (3025654) | 黏土定格 | 按页 | 六底座系列之一 |
| 本地 fl2v_turbo_8step | 图生视频 8 步加速 | — | 加速用，非风格 |
| 本地 ref2v_turbo_4step | 参考生视频 4 步加速 | — | 加速用，非风格 |

### 2. Krea2 —— 图像 LoRA（主力，约 141 个）

| 类别 | LoRA（链接号） | 推荐权重 |
|---|---|---|
| **通用电影感** | ⭐Cinematic Movie Still(2840790)、Pure Cinema(3012562,`c1nem4tic`)、CineShot(3020428,`frameveil cinematic style`)、V0id(2559636)、Vision Vanguard 22(2756232)、YFG Looxe(2800521)、V67 Krea2 Aesthetic(2748721,0.78–0.9) | 0.65–1.0 |
| **胶片复古** | ⭐TJFilm V2(2840370,`vifilm`)、80sfilm(2913743)、Technicolor(2629410)、Forgotten Cinema Technicolor(2981349)、Dead Light(2874810,`ddlt_style`)、Experimental Vintage(2971561,-1~+1)、Ray合集(2802215) | 0.5–1.5 |
| **🔥港片/武侠** | 🔥王家卫(3023454,`wkw1`,0.6–0.75)、90s Movie Grit(2833506,`mamay style`,1.35)、PhantomLight Hanfu(2817414,0.85)、ShadowWuxia(2847913,0.8–1.0)、Vintage Shaolin(2631251)、武侠场景类见下 | 0.6–1.35 |
| **其他地域/类型** | Samurai Cinema(2509629)、Ghost Dog(2956451)、Sergio Leone(2951227,1.0–1.4)、Forgotten Cinema(2981349)、Midjourney Japanese Girl(3004496)、Krea2 Japanese film(2816521,`jiaopian`)、Star Trek TNG(598337/2878784) | 0.8–1.4 |
| **动画/吉卜力** | Retro Ghibli红猪(1153088)、Princess Kaguya(837740,1.0–1.5)、Ghibli by Fortnox(2882798)、Dark Ghibli(1349631)、V67 Ghibli Look(2431791)、Ivyfilm(2940797) | 0.8–1.5 |
| **科幻大片** | Orion Expedition(3003215,er_sde+simple)、Lumen Blockbuster(3006646)、V67 Synthography(2811717,(Synthography:1.2))、V67 Ultra Vision(3047373) | 0.85–1.0 |
| **韩系人像** | CHAEWON(2994783)、Seo Yuna(3022915,0.85–0.95)、Nari/Moody Gal系列(2662271)、Famegrid(2088956) | 0.8–1.0 |
| **镜头控制** | Astro Cinema V02(2831431,`ASTROCINEMAV01K2T`,0.7–1.0) | 0.7–1.0 |
| **仙侠/角色** | 小白白蛇(3007857,1.5)、凡人柳玉(2998679)、Art3mis RPO(3032242,1.2) | 1.0–1.5 |
| **能力增强** | CineVivid(3059975,0.55–0.75)、Krea2 35mm Texture(3010645,Qwen2.1版)、TJFilm(2840370)、V67 Photorealistic(3017569,`phtreal`开头) | 0.5–0.85 |
| **欧洲/类型片** | Giallostyle 70s(2138328,0.6–0.7)、Les Amants Diaboliques 法国动画(2864566,1.0)、085 In the Shadows(2809346,`n0vuschr0ma style`) | 0.6–1.0 |
| **纪实/街头** | V67 Photojournalism(2742204,权重1.3开头)、V67 Street Photo(2998016,权重1.1开头) | 按页 |
| **恐怖/暗黑** | hellraiser 空场景(2968383,0.8–1.0)、Horror Style(2785722,1.0)、Blackened Dark Noir(2838147,0.8–1.0) | 0.8–1.0 |
| **胶片型号** | Kodak Portra 400(2184875,0.5–1.0)、80sfilm(2913743,1.0–3.0) | 0.5–3.0 |
| **VHS/复古录像** | ⭐2000s Analog Core(1134895,`v8s`,0.8,带时间戳)、⭐VHS Style(430136,`vhs`)、Retro TV&VHS(3006382,`vhs80s_bcast`,**1.7**)、Neon VHS K2版(2987989) | 0.8–1.7 |
| **3D/动画电影** | ⭐Pixar-Disney 3D(2831766,`3dpixar`,1.0)、Pure-Pixar(2977241,`KR2Pix`)、Shinkai 3in1(2912863,0.6–1.3) | 0.6–1.3 |
| **定格/黏土** | Claymation(2803827,0.85–1.0)、Made of Clay(2785861)、Oddarium Wes Anderson(2872676,`oddarium`+媒介词)、ModelingClay(**1.5–3.0**)、Stopmotion Goth(2866599,`57OPM`) | 0.85–3.0 |
| **历史战争** | AmericanRev(2756731,`americanrev`放末尾,0.7) | 0.7 |
| **🔥摄影师打光** | The Revenant(2964180,Lubezki自然光)、V67 Lighting(2939697,`(Lighting:1.1)`开头)、V67 HDR Intense(3046504,`(HDR Intense:1.1)`开头) | 0.85–1.0 |
| **蒸汽朋克/复古未来** | RetroFied V2(2790408,`RETR0K2`,0.85)、V67 Steampunk(2420916,0.6–0.8)、Steampunk CE(1641978,0.8)、Retrofuturism(3007092,`rtrftrsm style`,1.0)、DC Steampunk(2997560,`DCST3AMPUNK.`,1.0) | 0.6–1.0 |
| **苏俄/东欧** | Deyneka苏联先锋(2987600,0.85–1.0)、V67 Soviet Russia(2837620,0.85–0.9)、Sovdark阴郁苏联(3020101,`sovdark`开头,0.8–1.0)、Soyuzmultfilm动画(2817513,1.0) | 0.8–1.0 |
| **拉美/中东** | V67 Día de Muertos(2505576,ZIT/K2)、Tukano Raw Film(2814290,`TknRwFlm`,1–2) | 1.0–2.0 |
| **游戏电影化** | GTA style VI(2113254,`gta6style`,1.0)、Ellie TLOU(2836448,`ellie14`) | 1.0 |
| **超级英雄/DC动画** | DCAU Art(2875820)、Jessica Cruz(2880059,`greencruz`)、Power Girl(2439556,`dcpowergirl`)、cinematic_layout(2785466,有缩水警告) | 1.0 |
| **🔥V67后期滤镜** | V67 Cinematic Filters(2512256,`(cinematic filter:1.2)`开头,20种LUT) | 按页 |
| **V67绘画家族** | Photo Painting(2430955)、Museum-quality Oil(2757925,`(…:1.1)`)、Oriental Painting(2580026)、European Painting(3030918) | 按页 |
| **中式/国风** | MJ中式美学(2948991,`MJCN_Style`)、国风游戏美宣(2869230,`gqmtdx7`,0.8–2.3)、China Word(2522859,ZIT/K2)、灰墨(2960333,`zxy_grayink_style`,0.8)、Absolute CINEMA(1960106) | 0.8–2.3 |
| **🔥动态姿势/机位** | More Dynamic Poses(2914130,`PoseDaal`,1.0，高低俯仰/后侧/地面机位) | 0.5–1.5 |
| **90s怀旧/港风** | Back To 90s(2850091,`90s color photograph`)、YuYe暗黑(2805002,**2.0**)、港风怀旧(135036,SDXL,<0.8) | 1.0–2.0 |
| **舞台/人物补充** | V67 Pop Idols 48(2694651,J/K-Pop舞台)、东南亚女性(2180115,ZIT/K2/Klein)、Nastya芭蕾(2999886) | 1.0 |
| **🔥时尚/商业摄影** | VOGUE BY STX(2901040,去塑料感+皮肤织物)、LuxCinema(2854999,`lux`开头,0.8–1.0)、Stylized Commercial(2872288,`stcom`,1.0)、Luma(2950530,风格无关增强,0.5甜点) | 0.5–1.0 |
| **导演流派** | Twin Peaks(2879929,`twinpeaks_style`)、韦斯安德森(2900396,无触发词)、mhDreamy(2973085,量化版**2.0**)、Oddling Reverie(3029966,K2版) | 1.0–2.0 |
| **自然/微距/动物** | Apollo 1969 NASA(2756270)、Taiga Macro(2985614,0.85–1.0)、Animal Kingdom(3008017,`rkwildlens`,竖屏9:16) | 0.85–1.0 |
| **建筑/空间** | Brutalist Interior(1636847,**0.4–0.5**)、Decaying Brutalism(3030909)、Steampunk Interior(2873466,`SteIntArc`,0.8–1.25)、Visual Sci-Fi Minimalism(3055545,`Devastator2049`,0.7–1.2) | 0.4–1.25 |
| **赛博/星空/Synthwave** | NEON DECAY K2版(2951853,`neon-decay`)、V67 Cyberpunk(2475476,`(cyberpunk:1.2)`)、V67 Stars&Galaxies(2507359,`(starfield…:1.2)`)、Synthwave(1463207,`synthworld`,0.4–0.6) | 0.4–1.2 |
| **单部电影** | 2 Fast 2 Furious 2003(2981065,`2fst2frs2003`)、Hot Rod 2007(2997875,`htrd2007`)、Cruel Intentions 1999(2953789,`crlintntns1999`) | 1.0 |
| **🔥V67概念组件库** | Camera&Lens(2949466)、Color Palette(2554165)、Mood&Atmosphere(2958327)、Quality Boost(2966205)、Environment&Weather(2967611)、Artist Style(2969806)、Era&Genre(2970592)、Creature&Character(2972167)、Pose&Framing(2972585)、Robotics(2507831) | `(组件名:1.1)` 开头 |
| **黑白/间谍/复古** | DC Obsidian Monochrome v2(2411024,`DCOBMON.`)、YFG Spy World 50s(1091414,0.6–0.8) | 0.6–1.0 |

### 3. Z-Image Turbo —— 图像 LoRA（24 个）

| LoRA | 风格 / 功能 | 推荐权重 |
|---|---|---|
| ⭐Cinematic Shot (432586) | 通用宽银幕，4.5k 好评 | 0.8–1.0 |
| ⭐Cinema01 (2515897) | 大片场景/叙事构图，`cinema01` | 0.7–1.0 |
| Cinematic Slider (2599083) | Rank1 可叠加滑块 | 2.0–12.0（起始 3–4） |
| Nostalgic Cinema (2143490) | 80–90s 叙事长提示词 | 按页 |
| Film Grain & Muted (2787410) | 收尾调色（另有 Krea2 版） | 0.7–1.0 |
| Japanese Film Style (2345235) | 日式胶片，`日式胶片风` | 0.6–0.8 |
| SATIN 绸缎胶片 (2436970) | 日系空气感人像 | 0.7–0.8 |
| Technicolor (2629410) | 黄金时代好莱坞 | 0.5–0.8 |
| Cinematic Color Grading (541698) | 光线/色调词控制 | 0.5–1.2 |
| NexBlend 04/07 (2595202/2744691) | 韩系干净皮肤，`nexblend` | 1.0–1.7 |
| CHAEWON ZIT版 (2994783) | 韩国偶像角色 | 0.7–0.85 |
| Famegrid ZIT版 (2088956) | 社媒写实人像 | 1.0–2.0 |
| Star Trek TNG style (2765097) | 复古科幻，强制前缀 | 1.0 |
| psxFilm / Retro Filter (2036457/2543934) | 复古滤镜类 | 按页 |
| V67 Photojournalism (2742204) | 70s 新闻摄影重颗粒 | 权重1.3整串开头 |
| Kodak Portra 400 (2184875) | 经典 Portra 颗粒/软化 | 0.5–1.0 |
| ARRIFLEX 435 Vision3 (1304800) | 摄影机+胶片模拟 | 按页；易冒固定脸 |
| RAD26 Documentary (2532790) | 纪实真实性打底 | 1.0 |
| 2000s Analog Core (1134895) | VHS/VHS-C/Hi8 录像 | `v8s`；0.9 |
| Pixar-Disney 3D (2833916) | 3D 动画电影 | 1.0 |
| Y2K Indian Aphrodite (2723805) | Y2K 印度美学 | 0.75–0.85 |
| V67 China Word (2522859) | 传统中国+未来科技，`(China Word:1.2)` | 按页 |
| Gray Ink 灰墨 (2960333) | 水墨插画，`zxy_grayink_style` | 0.6–1.0 |
| V67 Cinematic Filters (2512256) | 20种后期滤镜，`(cinematic filter:1.2)` | 按页 |
| V67 Beautiful Oriental Painting (2580026) | 古典中国美人 | 按页 |
| German Expressionism (2254403) | 20s表现主义/默片/扭曲布景 | 0.7 |
| V67 Cyberpunk (2475476) | 复古未来赛博朋克 | 按页 |
| Last Days of Film 1990s (2335283) | 80末90初胶片写实/放大器 | 0.75；img2img denoise 0.4–0.8 |

### 4. FLUX / Flux.2 Klein —— 图像 LoRA（14 个）

| LoRA | 底座 | 推荐权重 |
|---|---|---|
| Blade Runner 2049 (2420155) | Klein 9B | 1.0 |
| Blade Runner 1982 (2436395) | Klein 9B | 1.0 |
| 2020s Sci-Fi Movie (929073) | Klein 4B/9B 等 | 1.0 |
| Movie Clips (2351523) | Klein 9B | 按页 |
| Grit & Glamour (2534861) | Klein 9B | 按页 |
| Cinematic Animation Slider (2332400) | Klein 9B | 0–2.5 |
| Cinematic Photography (2842250) | Klein 9B | 1.0 |
| V67 Synthography V2 (2811717) | Flux.1 D | 0.85 |
| Cinematic 1940s / Octane (1351798) | FLUX | 按页 |
| Technically Color Flux (1791850) | FLUX | 0.7–0.9 |
| Cinematic Nostagia (2244145) | FLUX | 按页 |
| Giallostyle 70s Thriller (2138328) | K2/ZIT/XL 多版 | 0.5–1.0 |
| 2000s Analog Core (1134895) | FLUX 版模拟录像 | 按页 |
| V67 Cinematic Filters (2512256) | 20种后期滤镜，另有FLUX版 | 按页 |

### 5. Qwen Image 2.1 / 其他底座（11 个）

| LoRA | 底座 | 推荐权重 |
|---|---|---|
| 仙侠古风 V3 均衡 (2979853) | Qwen 2.1 | 0.4–0.6（崩手拉 CFG 2–4） |
| Krea2 35mm Texture (3010645) | Qwen 2.1 | 插件式 |
| Dot Film 硬闪粗颗粒 (2999989) | Qwen 2.1 | 1.0 |
| Cinematic Photography Qwen版 (2885438) | Qwen 2512 | 0.8 |
| Cinematic Control (2375886) | Qwen | 0.5–0.8 |
| Singularity OmniCine (2610733) | LTX 2.3 视频 | 0.8–1.0 |
| 1970s Martial Arts (1405211) | Hunyuan 视频 | 按页 |
| 1950s Scifi Wan版 (1359530) | Wan 2.2 | 0.8 |
| 2000s Analog Core (1134895) | Qwen 版时间戳最准 | 按页 |
| Your Name Artstyle (2745715) | 未标注(推测Flux系) | 0.6–1.0 |
| LTX 新海诚环境 (2650155) | LTX 2.3 | `ANIMSTY, SHW_YN` |

### 6. SDXL / SD1.5 经典款（9 个）

| LoRA | 底座 | 备注 |
|---|---|---|
| Hong Kong Action Cinema (361831) | SDXL | 偏绿需叠 Kodak 0.4–0.5 |
| 武侠 Wuxia V2 (76637) | SD 1.5 | 2186 好评，`weapon,sword` |
| Martial Arts Style Actions (195167) | SD 1.5 | 不加背景会变武术动作 |
| Wizard's Vintage Cinematic (498945) | SDXL | 偏黑泽明 |
| Cinematic Color Grading XL版 (541698) | SDXL/F1D | — |
| Technixl Classic Cinema (2193235) | SDXL | 中世纪调色层 |
| VHS Style (430136) | SDXL/Flux/Pony | `vhs` |
| ModelingClay (3025654) | SDXL/Pony/Illustrious | 黏土定格 |
| High-Fashion Editorial (2665442) | SDXL | Vogue杂志时装，`3d1tor14l`，0.85，EMA sampler |

---

## 二、搭配推荐（按场景直接抄）

> 通用原则：**底座一致才能叠**；风格 LoRA 1–2 个为主，第三个用 Rank1 滑块（Cinematic Slider）收尾；权重总和别超过约 2.0，否则过锐/崩脸。
> 你的固定参数（ZIT 出图）：20 steps / cfg 4.0 / euler+simple / shift 3.0 / negative prompt ≤10 词。

### 场景 A：EP001 同学会暗恋（文艺港片情绪）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 出图（首帧/参考图） | Krea2 | 王家卫 `wkw1`(0.6–0.75) + CineShot `frameveil cinematic style`(0.7) 收尾 | Turbo 8–10 steps / CFG1 / Euler+Simple；配 qwen3vl_4b(type=krea2) + qwen image vae |
| 出图（ZIT 备选） | ZIT | Cinematic Shot(0.8) + Cinematic Slider(3–4) | 20 steps / cfg4 / euler+simple / shift3 |
| 视频 | H3 | Cinematic V2(0.85) 或 官方版(0.7) | 图生视频；风格权重>0.3 会伤音频，配音后期做 |
| 避免 | — | 风格 LoRA 别放在 inswapper 换脸后；三视图场景权重压 0.4–0.6 | — |

### 场景 B：港片武侠打斗

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 武侠氛围图 | Krea2 | PhantomLight Hanfu(0.85) 或 ShadowWuxia(0.9) + Astro Cinema(0.8) 控镜头 | 8 steps / CFG1 / Euler |
| 打斗视频 | H3 | Wushu 工作流：wushu_e3(0.75) + Motion Repair(0.5) + spatial physics(0.3) + fl2v 8步 turbo | 10-step simple / euler / 24fps；一句一动作，留够头顶空间 |
| 武侠调色视频 | H3 | 90s HK Wuxia(画面 0.6 / 音频 0.2–0.3) | 要音效就压 0.2–0.3；要画面就 0.6 + 后期配音 |
| 70s 邵氏感视频 | Hunyuan | 1970s Martial Arts | 避快速动作与长片段 |

### 场景 C：美国科技 / 科幻大片

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 科幻出图 | Krea2 | Orion Expedition(0.9–1.0) + Lumen Blockbuster(0.6–0.8) | er_sde+simple；Krea2 Rebalance 可选（80% 样本没用） |
| 科幻出图（ZIT） | ZIT | Cinema01(0.8) + Cinematic Slider(4–6) | 20 steps / cfg4 |
| 赛博雨夜 | Krea2 | V67 Synthography(0.85) + (Synthography:1.2) 放开头 | 负面词排除 bright/sunny/vibrant；1–3 主体 |
| 科幻视频 | H3 | Orion Expedition H3版(1.0) 或 Sci-Fi Cinema H3版(1.0) | H3 三段式提示词：`integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music` |
| 星际迷航 | Krea2 | Star Trek TNG(598337) 抓氛围；ZIT 版(2765097) 必写强制前缀 | K2 版 4mp 最佳 |

### 场景 D：韩剧 / 台剧 / 华语青春

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 韩系男/女主角 | ZIT | NexBlend 04(1.0–1.3) 或 CHAEWON(0.7–0.85) | 20 steps / cfg4；高权重稳定 |
| 韩剧剧照质感 | Krea2 | Vision Vanguard 22(0.85) + CHAEWON(0.8) | Turbo 8–9 steps / CFG1，低 key 高对比 |
| 台剧柔焦 | ZIT | SATIN(0.7–0.8) + Cici 角色(0.8) | 高明度低对比，日系空气感 |
| 台剧情绪版 | Krea2 | jiaopian(1.0) + 王家卫 wkw1(0.3–0.5) + Cineluxe(0.6) | 8 steps / CFG1 |
| 偶像剧梦境特写 | Krea2 | Cineluxe(0.6) + bokeh/rim lighting/dreamy 提示词 | 0.6–1.0 |

### 场景 E：胶片质感 / 老电影（通用收尾）

| 目标 | 首选 LoRA | 叠法 |
|---|---|---|
| 真实胶片颗粒（Krea2） | TJFilm V2(1.0) | 单独用；想加强补 `film grain`，别堆风格词 |
| 黄金时代好莱坞 | Technicolor(Krea2 0.8–1.2 / ZIT 0.5–0.8) | 配 `movie still, vintage, 1950s` |
| 老电影无现代感 | Forgotten Cinema Technicolor | Krea2 Rebalance 1.0 + 提示加 `cinematic`，建议先不写触发词 |
| 局部复古副层 | Experimental Vintage(0.5) | 与主风格叠；-1 动漫 / +1 复古 |
| 黑白/默片 | 1920s Silent Film(H3) / Samurai Cinema(SDXL系) | 视频走 H3，图走 Krea2/SDXL |
| 动画电影风 | Retro Ghibli(1.0) / Kaguya(1.0–1.5) | Krea2 Turbo 10 steps / CFG1 |

### 场景 F：纪实 / 街头 / 恐怖片（本轮新增）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 70s 新闻纪实 | Krea2 | V67 Photojournalism（`(Photojournalism quality:1.3)` 整串开头）+ V67 DSLR + Natural Color Palette | 8–10 steps / CFG1；重颗粒压暗黑色 |
| 街头抓拍 | Krea2/ZIT | V67 Street Photo（`(Street Photo:1.1)` 开头）+ 写实打底 | 35/50mm、自然光、unposed |
| 真实性打底 | ZIT | RAD26(1.0) 叠在主风格上 | 轻量影响，专治 AI 味 |
| 伪纪录片恐怖视频 | H3 | 16mm Found Footage(`foundfootage16`) 0.8–1.0 | 夜戏 0.9–1.0；亮度靠场景描述；CRF≤16 + `-tune grain` |
| 80s 恐怖片视频 | H3 | 1980s Horror Movies(1.0) | 僵尸/身体恐怖；9 底座可复用 |
| 意大利 Giallo | Krea2 | Giallostyle(0.6–0.7) | 高饱和血色+强反差；配 `venetian blind shadows`/`hard key lighting` |
| noir 局部彩色 | H3 | Film Noir Selective Colors(1.0) | 只写需要的颜色，其余上负面词 |

### 场景 G：复古录像 / 动画电影（本轮新增）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 2000s 家庭录像 | Krea2 | 2000s Analog Core(`v8s`,0.8) + `amateur quality, low resolution` | 704×704 做 VHS / 1024×1024 做 Hi8；要时间戳用 Qwen 版 |
| 80s 广播/VHS 故障 | Krea2 | Retro TV&VHS(`vhs80s_bcast`) + 1–2 个修饰词 | **权重 1.7**（例外高权重） |
| 80s VHS 视频（带音频） | H3 | Neon VHS Dreams(0.85–0.95) | 自带复古音乐质感；自然描述运镜即可 |
| 初代 DV 手持视频 | H3 | MiniDV Nostalgia(`y2km1n1dv`,0.9) | **无原生音频**，配音后期做 |
| 3D 动画电影 | Krea2 | Pixar-Disney 3D(`3dpixar`,1.0) 或 Pure-Pixar(`KR2Pix`) | 8 steps / CFG1 |
| 新海诚环境动画 | H3/LTX | Environmental Anime(`2d anime style, art by makoto shinkai`) | 环境镜头为主，人物特写别指望 |
| 新海诚静态图 | Krea2 | Shinkai 3in1(0.6–1.3) + 影片后缀词 | 或 Flux 版 `yourname style`(0.6–1.0,CFG≥3.5) |
| 定格黏土动画 | Krea2 | Claymation(0.85–1.0) 或 Oddarium+`claymation` | ModelingClay K2 版需 1.5–3.0 |
| 韦斯·安德森对称构图 | Krea2 | Oddarium+`photograph`（摄影）/ +`claymation`（人偶） | 8 steps / CFG1；简单描述即可，别过度提示 |

### 场景 H：角色一致性（三视图 / 连续镜头）

| 环节 | 做法 | 参数 |
|---|---|---|
| 排版底板 | Z-Image Turbo（负责构图/三视图排版） | 你的参数：20 steps / cfg4 / euler+simple / shift3 |
| 光照微调（可选） | Qwen-Edit | 仅光照，不改排版 |
| 面部统一 | inswapper + insightface（同一人物） | 风格 LoRA 放在换脸**前** |
| 新人物 | 提示词调优，不用 inswapper | — |
| 风格 LoRA 权重 | 三视图场景压 0.4–0.6 | 避免破坏全身露脚构图 |
| 构图硬约束 | 提示词明确 full body / feet / shoes / ground | 防踝部裁切 |

### 场景 I：H3 武侠/动作视频（本轮新增，直接可用）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 打斗动作（首选） | H3 工作流 | Action Director(3003606) 选预设 A2 双人攻防 / A4 刀剑 / A5 枪斗 | 自动挂 Combat 0.65 + FightFlow 0.25；T2V 20 steps，参考模式 25 steps |
| 快速出草稿 | H3 工作流 | TaoMate 3步(2942481) Pass1 三步 euler 草稿 → Pass2 SelfLift+Wushu 细化到 2K | Wushu 栈 e3 0.75/Combat 0.35/camera 0.35/physics 0.3 |
| 电影调色叠加 | H3 | Cinematic V2(0.85) 或官方版(0.7) | 权重>0.3 伤音频；要原声压 0.2–0.3 后期配音 |
| 一体化出片 | H3 工具包 | Enzino H3 WF(3002944)：4 模式 + 18 运镜助手 + 3 LoRA 独立控制 | 8GB 显存可跑；15s 上限；H.264/AAC 导出 |
| 时长换算 | H3 | 秒数 → 17n+5 帧 @24fps | 别填任意秒数 |

### 场景 J：按摄影师打光二次调色（本轮新增）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| Lubezki 自然光 | Krea2 | The Revenant(2964180) 叠在任意主风格上 | `trg_revlow-key natural light` 等；蓝调时刻/阴天顶光 |
| Deakins/Storaro 光效 | Krea2/Flux | V67 Lighting(2939697) 或 HDR Intense(3046504) | `(Lighting:1.1)` / `(HDR Intense:1.1)` **必须放开头**；**与 Ultra Vision 三选一，不要全叠** |
| 维多利亚机械 | Krea2 | DC Steampunk(2997560,1.0) + 叠 0.2 写实 LoRA 抗塑料脸 | 2K+ 分辨率；`DCST3AMPUNK.` |
| 苏俄阴郁 | Krea2 | Sovdark(3020101,0.8–1.0) | `sovdark` 放开头；8 steps/CFG1 |
| 游戏过场 | Krea2 | GTA style VI(2113254,1.0) | `gta6style` 放开头；Turbo 8 steps/1344×768 |

### 场景 K：后期滤镜 / 国风 / 动态姿势（本轮新增）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 后期调色（免外部软件） | K2/ZIT/Flux | V67 Cinematic Filters(2512256)：选 teal-orange / bleach bypass / halation / 齿孔边缘标记 | `(cinematic filter:1.2)` 放开头 + 具体滤镜词 |
| 现场布光 vs 后期 | — | 现场打光用 V67 Lighting/HDR/Ultra Vision（三选一）；后期调色用 Cinematic Filters——**职能不同可分层叠加** | 别把这四类混作一类全叠 |
| 古装/国风支线 | Krea2 | 国风游戏美宣(2869230,`gqmtdx7`,1.2) 或 MJ中式美学(2948991,`MJCN_Style`) | 偏商业美宣/插画，EP001 真人向慎用 |
| 中国水墨概念板 | K2/ZIT | 灰墨(2960333,`zxy_grayink_style`,0.8) | 三底座文件不可互换；ZIT 9 steps/CFG1 |
| 人物不呆站 | Krea2 | More Dynamic Poses(2914130,`PoseDaal`,1.0) 叠主风格 | 0.5–1.5；给意图+机位词，不必逐肢体描述；可与 Astro Cinema V02 叠加 |
| 90s 怀旧抓拍 | Krea2 | Back To 90s(2850091,`90s color photograph`,1.0) | 直接闪光+粗颗粒+暖调 |
| 绘画质感混合 | K2/ZIT | Photo Painting(2430955) + Museum-quality(2757925,`(…:1.1)`) | 绑定层组合；偏插画 |

### 场景 L：时尚大片 / 导演风格 / 赛博视频（十一轮新增）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 时尚杂志/人像去塑料感 | Krea2 | VOGUE BY STX(2901040) 或 LuxCinema(2854999,`lux`开头,0.8–1.0) | VOGUE 无需触发词；LuxCinema CFG1.2–1.6/25–30 steps |
| 商业广告/产品 | Krea2 | Stylized Commercial(2872288,`stcom`,Raw0.9/Turbo1.0) | 干净平涂+大胆配色 |
| 通用画质增强（跨风格） | Krea2 | Luma(2950530,0.5甜点) | 不改主体只加对比/材质；高档位会收紧构图 |
| 大卫·林奇《双峰》 | Krea2 | Twin Peaks(2879929,`twinpeaks_style`,1.0) | 暖琥珀+森林绿+35mm 颗粒；红房间/小城镇怪诞 |
| 韦斯·安德森对称 | Krea2 | 韦斯安德森画风(2900396,无触发词) 或 Oddarium(2872676,`oddarium, photograph`) | 让 AI 写韦氏电影感提示词；对称+有限配色 |
| 梦幻艺术片（重打光） | Krea2 | mhDreamy(2973085,`mhDreamy, dreamy golden-lit ethereal illustration`) | **量化版 2.0 / raw bf16 1.0–1.5**；负面加 text/watermark 防触发词入画 |
| 赛博朋克视频 | **H3** | NEON DECAY(2951853,`neon-decay`,1.0) | 配色跟提示词走；可先 Krea2 版出图再 H3 转视频 |
| 黑白汽车插画视频 | **H3** | KuroDrive(2919290,`kurodrivestyle`,**1.3–2.0**) | 插画类需超权重压过写实先验；ep35 柔和/ep50 强 |
| 硬科幻建立镜头 | Krea2 | Visual Sci-Fi Minimalism(3055545,`Devastator2049`,1.0) | 避赛博杂物；巨构/混凝土/雾工业；配 er_sde+simple |
| 自然微距/竖屏动物 | Krea2 | Taiga Macro(2985614,0.85–1.0) / Animal Kingdom(3008017,`rkwildlens`,1.0) | Animal Kingdom 竖屏 9:16 训练（941×1672） |

### 场景 M：提示词维度化控制（十二轮新增，V67 组件库）

| 环节 | 底座 | 配方 | 参数 |
|---|---|---|---|
| 精确控制镜头器材感 | Krea2 | V67 Camera & Lens(2949466) | `(V67 Camera & Lens:1.1)` 开头 + rangefinder/macro/中画幅/镜头光晕等词 |
| 锁定配色板 | Krea2 | V67 Color Palette(2554165) | `(Color Palette:1.1)` 开头，0.65–0.85；选 Neon Duo/Cyber Twilight 等组合 |
| 年代+类型锚定 | Krea2 | V67 Era & Genre(2970592) | `(Era & Genre:1.1)` 开头 + 1940s/noir 等 |
| 姿势+构图 | Krea2 | V67 Pose & Framing(2972585) | `(Pose & Framing:1.1)` 开头；与 More Dynamic Poses 二选一 |
| 组合示例（EP001 文艺港片） | Krea2 | Camera & Lens + Color Palette + 主风格 wkw1(3023454,0.6–0.75) | 三层分工：器材/配色/风格；**打光三件套内部仍不要叠** |
| 黑白单色 | Krea2 | DC Obsidian Monochrome v2(2411024) | `DCOBMON.`；可换色为蓝/橙单色 |
| 50s 间谍片 | Krea2 | YFG Spy World 50s(1091414) | `YFG-SpyWorld50s`；0.6–0.8；风衣/窃听器/暗角 |
| 90s 胶片放大 | ZIT | Last Days of Film(2335283,0.75) | img2img denoise 0.4–0.8；可配 Flux2 Klein 出初稿 |
| 艺术家插画 H3 视频 | **H3** | KreaAlex(2918791,`bradhamstyle`,**1.3–2.0**) | 插画类需超权重；ep35 柔和/ep50 强 |

---

## 三、下载与排错清单

1. **底座不匹配 = 白下**：Z-Image LoRA 装到 FLUX 不生效；H3 视频 LoRA 不能给 Krea2 用。下载前看页面 Base Model 标签。
2. **同名不同底座**：`90年代电影感（武侠片）` 本地版是 Krea2(218MB)，`90s Hong Kong Wuxia` 是 H3(62MB)，不是同一个文件。
3. **判断底座三看**：metadata(`ss_base_model_version` / `base_model`) → tensor 前缀(`diffusion_model.blocks.*` = Krea2/Flux系) → 文件大小。
4. **Krea2 完整配置链**（你本地缺这三件）：Krea2 Turbo fp8 底座 + `qwen3vl_4b_fp8_scaled`(type=krea2) + `qwen_image_vae`，Euler/Simple 8–10 steps / CFG1。
5. **H3 音频保护**：风格 LoRA 权重 >0.3 会音频失真；要原生音频压 0.2–0.3，要画面质量设 0.6 并关音频后期配音。
6. **胶片颗粒导出**：CRF ≤16 + `-tune grain`，否则颗粒被编码抹掉。
7. **负面词上限**：你的 ZIT 参数约定 negative prompt ≤10 词；需要更多负面约束时优先靠 LoRA 和采样参数解决。
8. **权重范围别照搬**：80sfilm 可用到 1.0–3.0（H3 风格 LoRA 通常 ≤1.0），Cinematic Slider 用 2–12，常规风格 LoRA 0.5–1.0；看每张卡页的 Usage Tips 而非通用经验。
9. **V67 系列触发词位置敏感**：`(Photojournalism quality:1.3)` / `(Street Photo:1.1)` / `(phtreal, photorealistic:1.1)` 必须放提示词开头，挪到后面权重影响会明显下降。
10. **H3 风格 LoRA 自制路线**：Krea2 LoRA → 150 张生成图 → Qwen3-VL 重打标 → rank8 / blocks 0-3,6-47 / shift 0.6667 / 50 epochs。你本地有三个 Krea2 电影风格 LoRA，可照此配方转 H3 版。
11. **H3 音频副作用排查**：部分风格 LoRA 训练时无音频（如 MiniDV Nostalgia），会削弱 H3 原生音频生成；Neon VHS Dreams 则专门训练了复古音乐质感。选 LoRA 前先看卡片有没有音频说明。
12. **官方 H3 电影感的动态短板**：社区实测数据集 steadicam 偏多，推车/车拍等强运动镜头容易被做成静态；需要强运动时压权重到 0.5 并在提示词显式写运镜，或换其他 LoRA。
13. **VHS 分辨率要配合权重**：2000s Analog Core 低清 VHS 感要主动降分辨率到 ~0.5MP（704×704），Hi8 感用 ~1MP（1024×1024）；光靠 LoRA 权重做不出老的扫描线质感。
14. **V67 家族触发词带小数点**：`(Lighting:1.1)` / `(HDR Intense:1.1)` / `(Ultra Vision:1.2)` 是小数点不是逗号，写错会静默失效；且必须放提示词最前面。
15. **打光 LoRA 不要叠加**：V67 Lighting / HDR Intense / Ultra Vision 是同作者三款功能重叠的打光 LoRA，叠一起会互相稀释光效——按场景选一款。
16. **H3 工作流 ≠ 风格 LoRA**：Action Director / TaoMate / Enzino 是 workflow 或工具包（JSON/zip），不是放进 models/loras 的权重；它们负责编排 LoRA 组合和采样，风格仍由 Cinematic / 90s Wuxia 等风格 LoRA 提供。别把工作流文件当 LoRA 加载。
17. **Gray Ink 灰墨三底座文件不可混用**：Krea2 Raw→Turbo / ZIT / Illustrious-XL 三个版本训练参数不同，页面明确警告「not interchangeable」，只下与你底座匹配的那一个。
18. **绘画质感 LoRA 与真人向题材冲突**：V67 Photo Painting / Oriental / European、MJ中式美学、国风游戏美宣偏插画/美宣；EP001 真人文艺向只适合做概念板或古风支线，别直接套在写实主线上。
19. **插画类 H3 LoRA 要超权重**：KuroDrive(2919290) 从 1.0 起调到 1.3–2.0 才压过 H3 写实先验；这与写实类 H3 风格（Cinematic V2 0.5–0.7）方向相反。判断依据：风格离写实越远，权重越要往上加。
20. **mhDreamy 权重取决于精度**：int8/nf4/fp8 量化版吞 delta 需用 2.0，raw bf16 版用 1.0–1.5；动漫底模下压到 0.6 以下否则会变厚涂半写实。触发词可能印在招牌上，负面词加 text/watermark/signboard/letters。
21. **Serendipity 是 checkpoint 不是 LoRA**：它是 merge 进 Krea2 Turbo 的独立底模（负责镜头调度/空间深度），要放 `models/checkpoints/` 或 `diffusion_models/`，不能当 LoRA 加载；与风格 LoRA 职能不同可叠加。
22. **Krea2→H3 自制配方已五例互证**：CinemaGrade、80s Commercial、KreaLand、KuroDrive、KreaAlex 均用 150 张 Krea2 图（主体唯一/50% 人物/caption 含电影镜头词）→ rank8 / blocks 0-3,6-47 / shift 0.6667 / LR 2e-4 / adamw / 50 epochs。你本地三个 Krea2 电影风格 LoRA 可照此转 H3 版。
23. **V67 概念组件 ≠ V67 风格 LoRA**：组件库（Camera & Lens / Color Palette / Mood / Era & Genre 等 10 个）只控制提示词的一个维度、不提供固定审美；风格 LoRA（Synthography / Film Noir / Steampunk 等）提供完整调性。两者可分层叠加，但触发词都是 `(组件名:1.1)` 放最开头、小数点不是逗号。
24. **V67 组件当前只有 Krea2 版**：作者明确表示计划扩展到 Flux / ZIT / Ernie，但截至本轮仅 Krea2 可用；别拿 Krea2 组件往 ZIT 上挂。
25. **Last Days of Film 不要纯 T2I 用**：它在低降噪 img2img（denoise 0.4–0.8）+ 权重 0.75 下才发挥细节/做旧优势，直接文生图容易出重复脸；当放大器用 denoise 0.3–0.6。
