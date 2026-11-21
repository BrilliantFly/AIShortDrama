# N5 · ComfyUI 实现卡（逐镜漫画格本地版）

> **状态**：设计态实现方案，按「组件可用」假定编写；不涉安装、版本、凭据、显存、路径可达性（属实施阶段）。
> **位置**：把 `N5-逐镜漫画格操作卡.md` **1.1 的出图引擎**从「即梦 / Seedream 4.0」换成本地 ComfyUI 工作流的替代实现。
> **路线**：`novelist → drama → 【N4 三张板 + N5 每镜帧，同一个 ComfyUI 工作流】 → L3 适配 → shotlist.csv → csv_to_timeline.py → H3 导演台 (r2v)`。
> **核查日期**：2026-11-19（ComfyUI 官方文档与公开工作流资料）。

---

## 0. 结论与边界

**能换，而且换完更符合方案 4.4 的同源定线**：板与帧由**同一个工作流、同一支画风 LoRA、同一模型家族**产出，天然满足「同一份文件、两处复用」，不再有即梦版「N4 与 N5 是否真同源」的核对成本。
>
> 措辞校准：按 1.1 的**商用**分工，这并非「同一个 checkpoint」——基座／`Qwen-Image-2512` 负责 T2I 出底图与 N4 板，`Qwen-Image-Edit-2511` 负责带参考图编辑派生每镜，是**同一 Qwen-Image 家族内两个 checkpoint**（均 Apache 2.0、同一画风 LoRA）。只有非商用验证用 `Qwen-Image 2.1` 时才是单 checkpoint 生成＋编辑合一。此处「同源」指同一工作流／同一 LoRA／同一份板文件，不是单权重。

**只换生产者，不换流程**：drama 五份 Markdown、四段重组 prompt、槽位固定化、三张板规格、`shotlist.csv` 19 字段、`csv_to_timeline.py`、N6 音色、01/02/03 出片节奏、起始构图审片清单**全部不变**。N7 之后零改动。

**但会新增两笔代价，切换前必须先认**：

| 新增代价 | 说明 |
|---|---|
| **商用许可证**（最容易被漏） | 出图侧：`Qwen-Image 2.1` 是 **Qwen Research License，仅非商业用途**；`Qwen-Image-Edit-2511`／Qwen-Image 基座／`Qwen-Image-2512` 都是 **Apache 2.0**。但**真正决定成片能否商用的是 H3 视频权重的 MiniMax H3 Community License**（地域／营收／署名／蒸馏），见 1.2 |
| **画风要自己锁** | ComfyUI 没有「开箱即用的漫画风」，需加载画风 LoRA 或把风格板挂进参考槽，全片同一 LoRA、同一强度；即梦版是模型自带 |

> 若目标是「全本地零费用、可重跑、完全可控」→ 换 ComfyUI 合适。若只想省掉出图侧的许可核对 → 即梦 API（0.20 元/张、输入图免费、失败不计费）最省事；但**换成即梦并不能绕开 H3 Community License**，全链路商用条件不变（见 1.2）。

---

## 1. 先选模型：许可证是硬约束 ★

### 1.1 先厘清概念：2511 本身就是 20B，不是「小模型 + 基座」

上一版把「Qwen-Image-Edit-2511（及 20B Qwen-Image 基座）」写成一个条目，容易被读成加载关系。核准后（2026-11-19）实际是**同一 Qwen-Image 家族里四个独立 checkpoint**，各是一份完整权重，不是叠加：

| 权重 | 发布 / 参数 | 能力 | 参考图 | 许可证 | 商用判定 |
|---|---|---|---|---|---|
| **Qwen-Image 基座** | 2025-08 · **20.4B MMDiT** | 文生图（T2I）+ 原生编辑；中英文字渲染最强；最高 3584² | 文生图无原生多参考图槽 | **Apache 2.0** | 可商用 |
| **Qwen-Image-2512** | 2025-12-31 · **20B** | 基座刷新版：真人质感／自然纹理／文字渲染更强；官方 Text-to-Image 模板（1328²、1664×928 为 16:9） | **无原生编辑工具**（纯 T2I，No native editing tools） | **Apache 2.0** | 可商用；**出 N4 板与全新构图最合适** |
| **Qwen-Image-Edit-2511** | 2025-12-23 · **20.4B** | **指令编辑**：图像漂移更小、单人／多人角色一致性增强、内置原需 LoRA 的能力、多图参考 | `TextEncodeQwenImageEditPlus` 多张输入（图 1／图 2／图 3）；GGUF Q3_K_S 9.2GB / Q4_K_S 12.4GB 可在 12GB 卡跑 | **Apache 2.0**（链路含 GGUF 量化、Lightning LoRA、Qwen2.5-VL 编码器均 Apache-2.0，允许商用含游戏素材） | 可商用；**但它是编辑模型，必须有源图**，见 2.3 |
| **Qwen-Image 2.1** | 更新版 · **7B** | 生成 + 编辑合一；原生 2K；8-step Turbo | `Text Encode Qwen Image 2.1` 最多 **16 槽** | **Qwen Research License：仅非商业用途**，商用须单独授权并标注 `Built with Qwen` | **商用排除** |
| 即梦图片 4.0 / Seedream 4.0 | 商业 API | 文生图 + 编辑，中文最强 | ≤10~14 张，0.20 元/张、输入图免费 | 商业 API 条款 | 可商用，合规最清晰 |

> **关键**：「2511 + 20B 基座」不是二选一，而是**分工组合**——基座／2512 负责「从文字出全新构图」（N4 三张板、每镜起始构图的底图），2511 负责「带参考图把底图改成本镜的表情／角度／机位／时段并锁住角色」。单押 2511 做不了 N5：编辑模型出不了全新构图（2.3）。

### 1.2 商用真正的瓶颈不在出图，在 H3

把出图引擎换成 Apache 2.0 只解决了整条链路**最宽松**的一环。决定「成片能不能商用」的是 **MiniMax H3 视频权重**的 `MiniMax H3 COMMUNITY LICENSE AGREEMENT`（License date 2026-08-02）：

| 约束 | 条款要点 | 对本链路的影响 |
|---|---|---|
| **地域** | Applicable Territory = 全球**排除**欧盟／英国／韩国／美国；排除区内不得使用、修改、分发、展示权重或其输出 | 中国大陆可本地部署；面向美/欧/英/韩发行或团队在这些地区 → 本地权重路径不授权，须走官方 API／Hailuo（条款另计） |
| **营收门槛** | 商用产品／服务年营收 **> 2000 万美元**（含关联方）须事先取得书面授权（`api@minimax.io`） | 短剧团队通常远低于此，免授权 |
| **强制署名** | 商用产品或服务 UI 必须**显著展示 "MiniMax H3"**；再分发须附 LICENSE 副本与 `NOTICE` 文件 | 成片／播放器／产品界面要留标识位 |
| **禁止蒸馏** | Section V.3：不得用 H3 或其输出改进任何其他 AI 模型（含用合成数据训练） | 别把 H3 成片拿去训角色 LoRA 或喂给别的模型 |
| **AUP 20 条** | 含「公共环境发布机器生成内容须清晰显著披露」「不得未经同意冒充真人」等 | 与国内 2025-03 起 AI 内容强制标识同向；仿真人短剧尤其注意肖像／声音授权 |
| **托管服务** | Section V.5：对外提供生成服务须实现并维护合理的技术与组织防护、举报机制 | 做成 SaaS／平台时是实质合规负担，非自用出片可略 |
| 输出归属 | Section VI.4：MiniMax 不主张输出权利，输出由使用者负责 | 成片可自有，但责任自负 |

两处需自行核实、口径可能叠加：
- **H3-Image**（2026-11-11 的 33.1B 图像模型）用的是 `MiniMax-H3-Image Community License`，**营收门槛 100 万美元**（比视频版 2000 万严 20 倍）、同样排除美/欧/英/韩、托管服务无门槛即需授权。若将来用 H3-Image 出图，别把两套门槛混用。
- 有资料引述 **ComfyUI 官方指南**：本地生成的视频商用需另购 MiniMax 商业许可（经 Comfy 销售），Comfy Cloud 生成的已含商用权。这与 Community License 的关系需向 Comfy／MiniMax 核实现行口径。

**判定**：中国大陆团队、年营收 < 2000 万美元、只做自用出片 → 全链路可商用；出图侧 Apache 2.0 无额外负担，只要履行署名／标识／不蒸馏／AUP。若发行含排除地区或做成托管服务，**先处理 H3 授权，这比选哪个出图模型重要得多**。

### 1.3 已有一个几乎现成的 ComfyUI 工程

`github.com/SilenWang/comfy-h3-container`（Docker 一键、12GB 显存、`--lowvram` + GGUF + Turbo 4 步）把本链路前后半段装进了同一个 ComfyUI，且**明确列了许可证清单**：

| 它的工作流 | 对应本链路 | 关键说明 |
|---|---|---|
| `minimax_h3_r2v` | 后半段 H3 参考生视频 | 最多 9 图 / 3 视频 / 3 音频参考，锁人物长相／风格／音色 |
| `qwen_image_edit_reference` | **N5 逐镜帧** | 图 1 = 基准图（锁长相／构图／上色）、图 2 = 表情／角度／风格参考；原文「一致性靠每次带参考图而不是靠更大的模型」「图 1 全项目复用同一张定妆图」——与方案 4.4 同源定线吻合 |
| `qwen_image_edit_multiangle` | N5 机位变化 | 一张基准图 + 96 机位提示词（方位 8 × 仰俯 4 × 距离 3），叠多角度 LoRA |
| `anime_character_sheet` / `anime_character_9views` / `anime_scene_t2i` | **N4 三视图／场景板** | SDXL 二次元底模（Illustrious XL v2.0 / Animagine XL 4.0，OpenRAIL-M / OpenRAIL++-M，可商用但须遵守各自使用限制），一次出 3×3 设定表 / 同 seed 九向单图 / 场景图 |
| `qwen_image_edit_gguf_lightning` | 批量出素材 | 4 步 Lightning；20B 模型在 12GB 卡上建议走这档 |

许可证清单原文：Qwen-Image-Edit-2511 主模型／unsloth GGUF 量化／lightx2v Lightning LoRA／Qwen2.5-VL-7B 文本编码器**均为 Apache-2.0，允许商用（含游戏素材）**，须随附许可副本；MiniMax H3 权重为 Community License（注意地区限制）；SDXL 底模为 OpenRAIL 系（可商用但有限制条款）。

**但两点与本方案定线冲突，不能直接照搬**：
1. 它把「凭空出图」交给 **SDXL 底模**、「改图」交给 2511，是**两套模型**，违反方案 4.4.3 的板帧同源。要合规则需把 20B 文生图（基座／2512）纳入同一 Qwen 家族，或先跑 2~3 镜对齐 SDXL 与 2511 的画风差异。
2. 它自己写明「**换姿势／换角度、需要严格构图控制时 2511 不擅长，那是 SDXL + ControlNet（OpenPose）的活**」——正面印证 2.3 的编辑模型语义坑：drama 逐镜景别机位不能只靠 2511。

**用法建议**：把它当「省掉自己搭 Docker／下权重／调 12GB 低显存」的底座，模板与许可证清单直接复用；但 N4/N5 的模型分工按 1.1 重排，drama 冻结关键帧仍按操作卡四段重组灌入，别用它的自动分镜。

---

## 2. 工作流结构：共享层固定，只有每镜层变化

这是 ComfyUI 版唯一需要新建的东西。核心原则与后半段 `csv_to_timeline.py` 完全同构：**把全片不变的部分钉死，只让每镜 prompt 变化**。故事板工作流的公开共识也是「共享层（checkpoint／固定 seed／角色参考／风格／分辨率）恒定，每镜只换 prompt 与 pose」。

### 2.1 节点清单

| 分组 | 节点 | 作用 | 生命周期 |
|---|---|---|---|
| 模型 | `UNETLoader` | 载入所选 Qwen 主模型 | 全片固定 |
| 模型 | `CLIPLoader`（`qwen_2.5_vl_7b_fp8_scaled`） | 文本／视觉编码 | 全片固定 |
| 模型 | `VAELoader`（`qwen_image_vae`） | 解码与参考 latent | 全片固定 |
| 风格 | `LoraLoaderModelOnly` | **漫画风 LoRA**；可选 Lightning 4-step 加速 LoRA | 全片固定、同一强度 |
| 参考 | `LoadImage` × 3 | 三张板，见 2.2 | 全片固定、同一路径 |
| 编码 | `TextEncodeQwenImageEditPlus`（2511）或 `Text Encode Qwen Image 2.1`（2.1） | 接收四段重组 prompt + 参考图，输出 conditioning | 每镜换 prompt |
| 采样 | `KSampler`（+ `ModelSamplingAuraFlow`／`CFGNorm` 视模板而定） | 固定 seed、固定 steps／CFG | 全片固定（seed 可逐镜微调破缓存） |
| 尺寸 | `EmptyLatentImage` / Resolution Selector | **16:9、宽 ≥1344**（如 1344×768 或 1536×864） | 全片固定 |
| 构图（可选） | `ControlNetLoader` + `ControlNetApply`（OpenPose / Depth） | 锁每镜站位与景别 | 每镜换控制图 |
| 输出 | `VAEDecode` → `SaveImage` | `filename_prefix = SHOT-<EP>-`，输出 PNG | 每镜一张 |

> 按 2511 官方模板还会有 `FluxKontextMultiReferenceLatentMethod`／`ImageScaleToTotalPixels` 等辅助节点；按模板加载即可，不要自行增删影响参考槽位顺序。

### 2.2 槽位固定化（与操作卡第 4 章一一对应）

| 工具槽位 | 挂什么 | 文件 | 对应 H3 | 规矩 |
|---|---|---|---|---|
| `image_1` | 身份板 SHEET | `IMG-<角色>-SHEET.png` | `refs` index 2 | 一张三段式，**不拆四张** |
| `image_2` | 场景板 PLATE | `IMG-<场景>-PLATE.png` | `refs` index 3 | 同场景固定 |
| `image_3` | 服装／站位板 PAIR | `IMG-<...>-PAIR.png` | `refs` index 4 | 全片固定 |

三条不变：**一个参考只给一个职责**（官方指南 README:83）、**编号固定语义、缺图留空不重排**（README:109，SHOT-023 事故）、**SHEET 绝不进 `<Picture 1>`**（否则每镜开场都是标准站姿定妆照）。`Qwen-Image 2.1` 有 16 槽时，前 3 槽仍按此表固定，多余的槽**保持空置**，不要顺手把「上一镜尾帧」塞进第 4 槽后逐镜重排。

### 2.3 三个必避的语义坑 ★

| 坑 | 表现 | 规避 |
|---|---|---|
| **编辑模型 ≠ 文生图** | `Qwen-Image-Edit-2511` 里 `image_1` 是**被编辑的目标图**，输出会保留它的构图；把 SHEET 当 `image_1` 会得到「每镜都是定妆站姿」。且它是编辑模型，**每次请求必须至少有一张源图**（官方文档原话），出不了全新构图 | 按 1.1 分工：**基座／`Qwen-Image-2512` 的 Text-to-Image 模板**出全新构图（底图／N4 板）→ **2511 带参考图编辑**派生每镜。商用线上不要退回 `Qwen-Image 2.1`（Research License）；若非商用验证可用 2.1 生成＋编辑合一 |
| **尺寸偏移** | 编辑模型（`Qwen-Image 2.1` 编辑模式／2511）的 latent 尺寸跟随第一张参考图，自建空 latent 会导致编辑结果偏移 | 文生图侧用 `EmptySD3LatentImage` / Resolution Selector 明确设 16:9 ≥1344（如 1664×928）；编辑侧不要自建空 latent 去凑 16:9 |
| **「换机位/换姿势」不是编辑强项** | 现成工程文档明写「换姿势／换角度、需要严格构图控制时 2511 不擅长，那是 SDXL + ControlNet（OpenPose）的活」 | drama 逐镜景别机位靠底图 + ControlNet 锁，不靠 2511 自己想象；2511 只负责「保住身份」的那部分改动 |
| **跳过自动分镜节点** | 网上「Qwen3-VL 看图自动写分镜 → 逐镜出图」的工作流会自己重写分镜，覆盖 drama 已设计好的镜头 | 跳过 `Qwen3_VQA` 之类节点，把 drama 的冻结关键帧四段重组结果**直接灌进**文本编码节点／Batch Prompts（手册 5.1 已记） |

另两条：`≤3 张参考图` 在 2511 下被三张板占满，**没有余量**给「上一镜回灌」；固定 seed 复用、prompt 完全一致会命中缓存需微调破缓存（与 `csv_to_timeline.py` 的装配规则一致）。

---

## 3. 逐镜排队：三种驱动方式

| 方式 | 做法 | 优势 | 判定 |
|---|---|---|---|
| **A · ComfyUI HTTP API 脚本（推荐）** | `frames_from_shotlist_comfy.py` 读同一份 `shotlist.csv`，逐行把四段 prompt 与三张板路径注入工作流 JSON → `POST /prompt` → 轮询 `/history` → 把输出落到 `input/<项目>/frames/SHOT-<EP>-<nnn>.png` → 回填 `frame_key` | 与 `csv_to_timeline.py` **完全同构**，两级流水线闭环；单镜重跑只需指定镜号 | **首选** |
| B · 文本列表节点 | `Load Text File` 读 `script.txt`（一行一镜）→ 连到文本编码节点 → seed 递增 → `SaveImage` 用 `%counter%` 命名 | 零代码，先跑 2~3 镜验证最省事 | 适合阶段 1 小样 |
| C · 故事板排队节点／GUI | `VRGDG_StoryBoardCreator`（`prompt_list` + `auto_queue` 自排队，支持 `redo_indexes` 单镜重跑）／`SceneQueue`（画廊式，标准节点，占位符含 subject/appearance/wardrobe/pose/scene/style，自带 manga_demo 8 帧漫画） | 单镜回退与可视化友好 | 可选，引入第三方插件依赖 |

**推荐 A**，因为它把「一镜一行」的表驱动契约从后半段延伸到前半段：同一份 `shotlist.csv` 同时被出帧脚本与装配脚本消费，N4→N5→N9 才真正闭环。脚本接口设计（阶段 3 再固化，本卡不实现）：

```
读 shotlist.csv → 按 shot_id 循环:
    prompt = 四段重组(identity_block, frozen_keyframe, style_sentence, constraints)
    wf     = 载入固定工作流模板 JSON
    wf.set(文本编码节点.prompt, prompt)
    wf.set(LoadImage[1..3].image, 三张板路径)      # 槽位固定，缺图留空
    wf.set(KSampler.seed, base_seed + shot_index)   # 破缓存
    wf.set(SaveImage.filename_prefix, SHOT-<EP>-<nnn>)
    POST /prompt → 轮询 /history → 复制 PNG 到 frames/
回填 frame_key；输出「镜号 / prompt / 槽位 / seed / 输出名 / 审片结论」一行归档
```

> 与即梦版 `frames_from_shotlist.py` 的唯一差别是**提交目标**：一个打火山方舟 `/images/generations`，一个打本地 `/prompt`。上游重组逻辑与下游回填逻辑可完全复用。

---

## 4. 与现有契约的对接（这一段决定「后半段零改动」）

| 产物 | 目录 | 命名 | 回填 CSV 列 | 谁填 |
|---|---|---|---|---|
| 每镜漫画格 | `input/<项目>/frames/` | `SHOT-<EP>-<nnn>.png` | `frame_key` | 本卡（N5） |
| 三张板 | `chars/` `scenes/` `props/` | `IMG-*-SHEET/-PLATE/-PAIR.png` | `ref_*` 三列 | N4（同一工作流出）／L3 汇总 |
| 音色 | `voices/` | `REF-*.wav` | `ref_voice` | N6（不变） |
| 六段式视频 prompt | — | — | 六段式列 | drama 直接进 H3，不给 N5 |

**输出规格不变**：16:9、宽 ≥1344、独立单帧、画面无任何文字（气泡／字幕／拟声词／logo／分格线）。最有效的做法仍是在 `[4 约束]` 里直接禁，而不是出图后修。

**L3 可跳过条件不变**：若工作流直出「单帧 + 16:9 + 无文字 + 独立文件」，转换层 1 拆格／2 定画幅／3 去文字整体跳过，只剩 4 板入库汇总与 5 音色回填（操作卡第 9 章）。

---

## 5. 切换清单：什么变、什么不变

| 不变（占绝大多数） | 变 |
|---|---|
| drama 五份 Markdown 与唯一真源地位 | N4/N5 的生产者 → 同一个 ComfyUI 工作流 |
| 四段重组 prompt 模板与 S004 示例 | 出图成本 → 0 元/张（电费），不再有 API 账单 |
| 槽位固定化表、`<Picture N>` 编号语义 | 逐镜驱动 → 脚本／文本列表／排队节点 |
| 三张板规格（SHEET 三段式、不拆四张） | 画风 → 需自己加载 LoRA 或风格板 |
| `shotlist.csv` 19 字段与 `frame_key` 回填规则 | 参考图上限 → 2511 的 3 张（刚好）／2.1 的 16 张 |
| `csv_to_timeline.py`、H3 r2v、25step、段尾 `Audio: reference` | 新增：出图侧许可证（1.1）、**全链路 H3 Community License 合规**（1.2）、显存与模型文件、插件依赖 |
| 起始构图审片清单与「一票否决回 Step 2/4」 | 新增：文生图／编辑模型分工、尺寸偏移规避、机位靠 ControlNet |
| 01 快出预览 → 02 出片 → 03 精修的节奏 | 失败重跑 → ComfyUI 失败不产生输出（等价于即梦「未成功不计费」） |

---

## 6. 即梦 API vs ComfyUI 对照

| 维度 | 即梦图片 4.0 / 火山方舟 | ComfyUI 本地 |
|---|---|---|
| 单张成本 | 0.20 元输出，**输入图免费**，审核未成功不计费 | 0（电费）；需显卡与模型文件 |
| 中文分镜语义 | 最强，开箱即用 | 强（Qwen 中文好），需调优 prompt |
| 参考图 | ≤10~14 张，输入不额外收费 | 2511 多张（图1/2/3）；2.1 ≤16 但商用排除 |
| 全新构图 | 天然文生图（一个模型全包） | **需分工**：基座／2512 出底图 → 2511 编辑派生（1.1、2.3） |
| 漫画画风 | 模型自带 | 需 LoRA／风格板 |
| 出图侧许可 | 商业 API，合规清晰 | **2.1 仅非商用**；2511／基座／2512 Apache 2.0 |
| **全链路商用** | **同样受 H3 Community License 约束** | **同样受 H3 Community License 约束**（换出图引擎不解决，见 1.2） |
| 自动化 | 脚本调 HTTP API | 脚本调 `/prompt`，与装配器同构 |
| N4/N5 同源 | 需刻意保证同一模型 | 可同源，但**若采用现成工程的 SDXL＋2511 双模型则不同源**（1.3） |
| 主要门槛 | 凭据、网络 | 显卡、模型、插件、许可证、现成工程选型 |

---

## 7. 起步与验收（先跑 2~3 镜）

1. 按第 1 章定线：先确认 **1.2 的全链路 H3 商用条件**（地域／营收／署名／标识）满足，再按 1.1 分工选模型——基座／2512 走 Text-to-Image 出底图与 N4 板，2511 走参考编辑出每镜派生；固定 checkpoint／CLIP／VAE／画风 LoRA／seed／16:9 尺寸。有现成底座可直接复用 `comfy-h3-container`（1.3）。
2. 按 2.2 挂好三张板，槽位固定不重排；按 2.3 确认走的是文生图模式、尺寸由 Resolution Selector 给、自动分镜节点已跳过。
3. 选 **1 对白镜 + 1 静默镜 + 1 双人镜**，用方式 B 跑通，逐镜检查「谁左谁右／无并肩／无文字／16:9／画风一致／只画一个瞬间」。
4. 回填 `frame_key` → `python csv_to_timeline.py --check-only` → 01 快出预览，确认 H3 忠实保留 `<Picture 1>` 构图。
5. 出口达标后再切方式 A 批量；任何一条没达标，回 Step 2/4 重出该镜，**不要试图在 H3 用 prompt 纠正**。

---

## 8. 风险表

| 风险 | 后果 | 处置 |
|---|---|---|
| 用 `Qwen-Image 2.1` 做商业短剧 | 违反「仅非商用」许可，需授权并标注 `Built with Qwen` | 1.1 先定模型；商用走 2511／基座／2512 或即梦 API |
| **只核对出图侧许可证就以为可商用** | 忽略 **H3 Community License**（排除美/欧/英/韩、营收 2000 万美元门槛、强制署名、禁止蒸馏、AUP），成片发行才踩雷 | 1.2 全链路合规清单；发行含排除地区先处理 H3 授权 |
| 把 SHEET 当 `image_1` 走编辑模式 | 每镜开场都是定妆站姿，毁掉 drama 景别；且 2511 出不了全新构图 | 2.3；基座/2512 文生图出底图优先 |
| 直接照搬现成工程 `comfy-h3-container` | SDXL 底模＋2511 是两套模型，板帧不同源；且换机位不是 2511 强项 | 1.3 两点冲突；按 1.1 重排分工，机位交 ControlNet |
| 编辑模板自建空 latent | 输出偏移、构图失控 | 2.3 第二条 |
| 参考图槽位按镜重排 | 跨镜变脸（SHOT-023 型事故） | 2.2 槽位固定化，缺图留空 |
| 画风 LoRA 每镜换／强度变 | 画风每镜跳 | 全片同一 LoRA、同一强度 |
| 组图模式代替逐镜 | 画面由模型自行分发，景别机位不对应 drama | 一镜一张；组图只做定调／备选 |
| 工作流自己写分镜 | drama 逐镜控制失效、装配层失去意义 | 跳过 `Qwen3_VQA`，守方案 3.5 模式 X |
| 负向词仍留「卡通／动画感」 | 参考图与提示词打架 | 后半段画风同步删负向禁项、正向改漫画向 |
| 实施阶段环境不满足 | 工作流打不开／红框 | 属实施阶段确认项，本卡按「组件可用」假定编写 |

---

## 9. 与其他交付物的关系

| 文件 | 关系 |
|---|---|
| `N5-逐镜漫画格操作卡.md` | 主操作卡；本卡是它 **1.1 工具定线**中「出图引擎」的 ComfyUI 替代实现，Step 1–8 与审片清单全部沿用 |
| `漫画前置-H3混合路线-实现方案.md` | 设计态方案；本卡对应 **L2 出图步**，并落实 4.4.2 判定②「漫画程序本身跑在 ComfyUI 里＝同源」 |
| `H3-vibe-生产线操作手册.md` | 主文档；本卡细化 **5.1 路线 C**，并补充许可证与节点级结构 |
| `shotlist_vibe_template.csv` | 19 字段契约；本卡 N5 **只回填 `frame_key`** |
| `csv_to_timeline.py` | 后半段装配器；本卡不碰，且方式 A 的脚本与它同构 |
| `comfy-h3-container`（外部开源工程） | 1.3；ComfyUI + MiniMax H3 r2v + Qwen-Image-Edit-2511 + SDXL 设定表的一体化 Docker 底座，可复用模板与许可证清单，但模型分工需按 1.1 重排 |
| 本卡 | ComfyUI 版 N5 的节点、槽位、驱动、对接、风险；**1.1 模型谱系／1.2 全链路商用合规／1.3 现成工程**为本轮核准新增 |
