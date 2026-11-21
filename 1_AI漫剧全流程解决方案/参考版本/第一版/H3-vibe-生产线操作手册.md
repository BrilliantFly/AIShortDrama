# H3 漫剧 / 短剧自动化生产线操作手册

**路线**：`novelist + drama + vibe + H3 导演台（r2v）`
**版本**：2026-11-18 · 基于本机 `F:\skills\` 现役资产实证整理
**适用**：连续叙事的漫剧 / 仿真人短剧，多镜头、需要跨镜角色一致、带对白与音色

---

## 0. 文档定位与总纲

### 0.1 一句话总纲

> **H3 导演台那一层，ComfyUI 只当渲染器。** 工作流节点、连线、UNET、采样器一律不改；渲染阶段改的只有两样：`input/` 里的素材，和 `MiniMaxH3Director` 的 `timeline_data`。自动化发生在 H3 **之前**。
>
> 注意口径：若前半段按 `N5-ComfyUI实现卡.md` 也用 ComfyUI 出板与每镜帧，那台 ComfyUI 是**另一条出图工作流**（需新建节点），不属于这句「不改节点」的范围；「不改节点」只约束 H3 出片工作流。

整条链路分三层：

| 层 | 范围 | 产物 | 是否碰 ComfyUI |
|---|---|---|---|
| 上游 · 内容生产 | N1 novelist → N2 drama → N3 资产契约 | 分镜 Markdown + 提示词文本 | 否 |
| 中游 · 资产与装配 | N4 参考板出图 → N5 vibe 每镜格 → N6 音色 → N7 入库 → N8 体检 → N9 装配 | 图片 / wav / CSV / 工作流副本 JSON | 出图环节可选在 ComfyUI |
| 下游 · 渲染 | N10 试错 → N11 审片 → N12 出片 → N13 归档 | mp4 | 是，只读输入 |

### 0.2 路线定线依据（为什么是 r2v）

- `fl2va` 只提供音频 `lock`（原音直贴、台词不可改），不提供 `ref` 借音色；`09-H3导演台-NG版/_上游文档/docs/NG-shot-audio.md:46` 写死 `In FL2VA only lock is offered`。
- drama 官方 `skills/short-drama-video-prompts/references/minimax-h3.md:68-73` 的模式表：

  | 本镜绑定的图 | H3 模式 | 正文结构 |
  |---|---|---|
  | 无图，明确文生视频 | Base | 三段 |
  | 只有一张 `用途：起始帧` | `first_frame` | 三段 |
  | 起始帧 + 结束帧 | `first_last_frame` | 三段 |
  | **起始帧 + 人物／地点／道具图同时存在** | **`reference`（full-reference）** | **六段** |

  本链路正好落在第四行。`:81-84` 补充说明：「H3 的首/尾帧输入与参考输入**互斥**……整组统一走 full-reference，起始帧也以 `reference_image` 送入」。所以**不是「选了 r2v」，是「链路结构决定了只能是 r2v」**；而 `<Audio N>` 音色参考只存在于六段式里，这又反过来解释了为什么 `fl2va` 走不通。

### 0.3 证据边界（必须先读）

1. **本机未找到名为 `vibe` 的已安装 skill**。`F:\skills\` 全盘（含隐藏目录、各 `_backup_*`）与 `C:\Users\Administrator\.workbuddy\skills\`（只有 `agent-browser-core`、`h3-prompt-writing`）均无匹配；`F:\skills` 内 `vibe` 字符串检索零命中。
   **重要更正（2026-11-18，据用户提供的 `deepseek_markdown_20261118_103154 (1).md` 复核）**：上一版把 vibe 定性成「只是环节名、现网无现成程序」，**这个结论是错的**，原因是检索方向只覆盖了同名商业 App，漏掉了「代码渲染 / Agent Skill」这条线。现网 `vibe` 至少有三种所指，均为真实存在的东西：

   | 所指 | 实例 | 产出 | 与本链路的关系 |
   |---|---|---|---|
   | ① 商业 App「VIBE AI Video Generator」 | `vibeaiapp.com` / `vibeclips.ai` / `bestaivideo.app` | 聚合 Kling/Sora/Veo/Wan/Seedance 的文/图生**视频** | 与 H3 同层，是替代路线 |
   | ② **代码渲染「Vibe Video」程序／Agent Skill** | `github.com/buerivan/vibe-video`（agent 写代码 → 无头浏览器逐帧渲染 → FFmpeg）、`harshil1712/vibe-video-generator`（Claude+Remotion）、awesomeskills 的 `vibe-video` skill（Canvas/JS + ffmpeg，15–60 秒） | **MP4 成片**（动态分镜／知识短片） | 与 H3 同层，是替代路线；**不是 N5 的静帧** |
   | ③ 伞状标签「Vibe 工具」 | 文档第 9 节把 `infinite-creation`、`Jellyfish`、`AIComicBuilder`、`Nomi`、`drama-skills`、`Vibe Video (VS Code)` 统称为「开源 Vibe 工具」 | 各不相同 | 其中 `infinite-creation` 与本链路几乎同构，见 6.1 |

   另更正：`vibecontent.net` **不是** Instagram 文案站（那是 `vibecontent.site`，不同域名）；`vibecontent.net/workflows/nomi` 是开源 AI 视频工作流目录站。会话日志里的 `host=vibecontent.net` 很可能正是在查这类工作流，**与本链路有关，不是无关记录**。
   → **定线（用户已确认，2026-11-18）**：本链路的 vibe 指「③ 里的一个环节」——**前半段用现成程序出每镜漫画静帧，后半段交给 H3 导演台**。即 vibe = 每镜一张静帧 PNG（`SHOT-<EP>-<镜号>.png`），身份一致性外置给 H3 三张固定参考板；② 的代码渲染程序产出 MP4、与 H3 并列，已明确**排除**（不是上游，不能填 `<Picture 1>`）。落地方案见 `漫画前置-H3混合路线-实现方案.md`，N5 逐镜执行见 `N5-逐镜漫画格操作卡.md`，出图引擎换成本地 ComfyUI 见 `N5-ComfyUI实现卡.md`。0.3 以上三种所指保留为情报背景，不再是待选路线。
2. **drama 现役版以 `F:\skills\drama-skills-main\drama-skills-main\` 为准**，外层同名目录是壳，另有多个 `_backup_20261118_*` 历史版本，不采信。
3. **三处路径当前不可访问**：`F:\skills\工作流\01-分镜图片\`（README 提到过但不存在）、`D:\ComfyUI资产\`、`D:\ComfyUI-aki-v3.2\ComfyUI\input`。需按 N0 重建或改配置，否则所有 `refs[].imageFile` 落空。

### 0.4 术语

| 术语 | 含义 |
|---|---|
| 参考板（board / sheet / plate） | 少量、**全片固定**的身份与空间锚，占 H3 `<Picture 2/3/4>` |
| 每镜关键帧（vibe 格） | **每镜一张**、逐镜变化的起始构图，占 H3 `<Picture 1>` |
| 整页 storyboard sheet | drama 的 3×3／4×3 格预览图，**不进生产链**，不能当参考图 |
| `REF-...` / `PLAN-...` | drama 的图片槽位：前者图已在项目内，后者图未进项目、只写挂图计划 |
| `顺序` | drama 槽位里的编号，决定 `<Picture N>`；本链路做「槽位固定化」 |
| 六段式 | `subject_definitions` / `summary` / `retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music` + 段尾 `Audio:` |

---

## 1. 全链路节点总览

| 节点 | 名称 | 输入 | 工具 / 技能 | 输出 | 落盘 | 门禁 |
|---|---|---|---|---|---|---|
| N0 | 项目初始化 | — | 文件系统 | 目录骨架、命名表 | `项目根/` | 路径可写 |
| N1 | 小说创作 | 创意 | novelist | 大纲／人物／场景／章节 | `novels/<名>/` | 世界观与年代设定齐全 |
| N2 | 全流程分镜 | 小说 | drama 8 子阶段 | 剧本／视觉设定／图片提示词／分镜／视频提示词 | `剧集/<EP>/` | `storyboard_lint.py` |
| N3 | 资产契约整理 | drama 产物 | 人工／脚本 | C/S/P 出图块、画风基底、槽位表 | `剧集/<EP>/导出/` | 锚点逐字一致 |
| **N4** | **参考板出图** | **N3 出图块** | **ComfyUI 文生图 / 外部工具 / produce** | **SHEET／PLATE／PAIR／PROPS** | **`input/<项目>/`** | **逐张审脸、审构图** |
| N5 | vibe 逐镜格 | N2 分镜 + **N4 参考板** | vibe | 每镜漫画静帧 | `input/<项目>/frames/` | 起始构图审片 |
| N6 | 音色资产 | 剧本对白 | 录音／TTS | 干净人声 wav ≥10s | `input/<项目>/voices/` | 试听、无底噪 |
| N7 | 入库 + 填表 | N2/N4/N5/N6 | 编辑器 | `shotlist.csv` | 工作区 | 一行一镜 |
| N8 | 体检 | CSV | `csv_to_timeline.py --check-only` | 错误／提醒清单 | 控制台 | 0 ERROR |
| N9 | 装配 | CSV + 底座工作流 | `csv_to_timeline.py` | 工作流副本 JSON | `out/` | 拓扑不变校验 |
| N10 | 01 试错 | 副本 | ComfyUI 通用01 | 低清预览 mp4 | `output/.../` | 构图／动作／画风 |
| N11 | 审片回退 | 预览 | 人工 | 修改指令 | — | 四类问题分流 |
| N12 | 02 出片 / 03 精修 | 锁定后的副本 | ComfyUI 通用02／03 | 正式 mp4 | `output/minimax_seg_export/<时间戳>/` | 逐段验收 |
| N13 | 归档 | 成片 + 全部中间产物 | 文件系统 | 可复现项目包 | `项目根/archive/` | 可回溯到镜号 |

---

## 2. 节点逐项操作

### N0 · 项目初始化

**目的**：把散落的 skill 产物收敛到一个可回溯的项目根，避免后期 `refs[].imageFile` 找不到文件。

**操作**
1. 建目录骨架：

```
<项目根>/
├─ 01-文本/          novelist + drama 的 Markdown（复制一份，不改原件）
├─ 02-资产/
│   ├─ chars/        角色定妆板 IMG-*-SHEET.png
│   ├─ scenes/       场景板 IMG-*-PLATE.png
│   ├─ props/        道具板、服装站位板 IMG-*-PAIR.png
│   ├─ frames/       vibe 每镜格 SHOT-*.png
│   └─ voices/       音色 REF-*.wav
├─ 03-分镜表/        shotlist.csv
├─ 04-工作流副本/    装配产物 JSON
└─ 05-成片/          mp4 + 归档清单
```

2. 选底座工作流：`F:\skills\工作流\02-H3漫剧流程\H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json`（**母版／空白模板**）。
   - 6 个 `H3-EP001-出片-*` 工作流的文件内便签都写着「**由 `H3-通用02-高清主线` 填充生成，勿当模板复用**」——它们是已填好具体镜头内容的**出片实例**，不是模板。
   - 结构实证：通用02 与 EP001 S004 的 13 节点／11 连线、UNET／CLIP／VAE、25step／cfg 1.0／1344×768／res_multistep+simple／shift 12-3、frameRate 24、refMaxSize 1344 完全一致，连 Director 节点标题都叫「EP001 高清版」。差异集中在 `segments` 内容（通用02 = 1 段 124 帧 1 槽占位；S004 = 1 段 102 帧 4 槽实填）与三处底座残留。脚本整体替换 `segments` 并规范化残留，按便签意图用通用02 更规范。
   - **三处底座残留差异**（装配时已处理／说明）：
     - `output.continuityEnabled`：通用02 = **True**、S004 = **False**（S004 便签写「continuity 关闭：各段独立，各自从自己的起始帧起」）。用通用02 当底座，多段连续组默认就开启 22 帧 latent 接力，符合 README 第五节；脚本继承底座值、不擅自改语义。
     - `video.width/height` 与 `global.sourceWidth/Height`：通用02 残留 **960×544**（快出预览尺寸），与 `output` 的 1344×768 不符；S004 是 1344×768。脚本装配时统一同步成 `output` 尺寸。
     - `SaveVideo` 前缀：通用02 = `video/通用_高清`、S004 = `video/EP001_004`。脚本自动改成 `video/<输出副本名>`，避免多组共用前缀互相覆盖；可用 `--save-prefix` 覆盖。
   - 实测：两种底座各装配一份，除便签文本与 `output.continuityEnabled` 外**完全一致**。
   - `H3-EP001-出片-参考音色-S004-...` 的正确用途是**格式参考范例**：对照它的六段式 prompt、4 槽位顺序、段尾 `Audio: reference`，不要拿它当底座改。
   - **两代槽位约定**：通用02 便签写「Picture 1 身份板 → Picture 2 场景板」，EP001 实战是「Picture 1 每镜帧／2 角色板／3 场景板／4 服装站位板」。脚本整体替换 segments，不受便签文字影响，一律以 EP001 实战约定填 CSV。
   - 通用01／03 分别是试错与精修档，不作底座。
3. **确认 ComfyUI 的 `input/` 真实路径**，填进 `--input-root`。本机三处候选均不存在，需先建好或改配置。
4. 不要用 `09-H3导演台-NG版`：要求 ComfyUI ≥ 0.37，本机记录 0.30.2，打开会大面积红框。
5. 保留权威原件：README 标注 `D:\ComfyUI资产\1-工作流\01-通用-H3\` 为权威、GUI 侧边栏为同步副本。**任何改动都另存副本**。

**验收**：`input/` 可写、底座 JSON 能被 `json.load` 解析、目录名不含空格与非 ASCII 路径问题。

---

### N1 · novelist 创作

**输入**：一句创意／题材。
**工具**：`chinese-novelist-skill-master`（`SKILL.md` 第二阶段规划）。

**产物**（全部落 `novels/[小说名称]/`）：

| 文件 | 内容 | 下游用途 |
|---|---|---|
| `00-大纲.md` | 世界观与**年代设定**（必含小节） | drama 时代锚点、服装剪裁与材质 |
| `01-人物档案.md` | 年龄/职业／**外貌特征**／性格／背景／惯用兵器 | drama 识别锚点、本集造型；道具在此登记 |
| `02-场景设定.md` | `LOC001` 空间布局、感官锚点（含光线）、**视觉要点**（主色／材质／标志性物件／构图） | drama 地点条目； novelist 自述「唯一事实来源」 |
| `第NN章.md` | 正文，每章 3000–5000 字 | drama 剧本改编 |
| `对白清单.csv` | 改编时才出：场次/镜序/说话人/台词/字数/预计秒数/留白秒/情绪/建议镜型 | drama 剧本对白与段长估算 |

**关键**：novelist **不出图**。`references/visual-settings-mapping.md` 已把文字字段映射成 drama 视觉设定，并给出角色参考板三段式排版（左侧主视图特写 85mm 浅景深 + 右上正/侧/背三视图 + 右下五格表情板，`:46-53`）。`SKILL.md:329-341` 明确「主资产出图：人物图片提示词一律按 drama-skills 的影棚模特卡角色参考板三段式」，交的仍是**文本**。

**验收**：`00-大纲.md` 有世界观与年代设定；`02-场景设定.md` 的 LOC 条目带视觉要点；人物档案外貌特征非泛泛而谈（要可画）。

---

### N2 · drama 全流程分镜（8 个子阶段）

drama 是 **11 个 skill 组成的套件 + creator-first 五份 Markdown**，不是单一「分镜生成器」。现役版默认落 `剧集/<EP>/`，**不落盘 JSON/JSONL、不建覆盖表**（`docs/comic-drama-workflow.md:37-38`）。

| # | 子技能 | 产物 | 关键字段 / 命名 |
|---|---|---|---|
| 1 | `short-drama-write` | `剧本.md` | `## EP001-SC001 内 · 地点 · 时间/天气`；`[VO]/[OS]/[SFX]/[画面文字]/[连续性]/[转场]`；末尾「声音分层」 |
| 2 | `short-drama-assets` | `视觉设定.md` | `## 人物/地点/道具 · [名称]`；`识别锚点`、`本集造型`、`画面代称`、`连续性锁 LOCK-XXX · 锁面：[逐字短语]`、`项目视觉方向` |
| 3 | `short-drama-image-prompts` | `图片提示词.md` | `## IMG-... · 中文名`、`- 参考：`、`### 可复制提示词`；`-SHEET` 角色板 / `-PLATE` 场景板 / 道具板 |
| 4 | `short-drama-storyboard` | `分镜.md` + `分镜.csv` | `## SHOT-...`、`### 冻结关键帧提示词`、可选 `### 收尾关键帧提示词`；`- 来源/时长/目的/景别机位/运镜/起点/唯一动作/终点/图片提示词项/输入参考图/视觉依据/声音`；脚本消费列 `export_frames`、`音色`、`验收基线`、`refs` |
| 5 | `short-drama-video-prompts` | `视频提示词.md` | `## MOTION-...`；`分镜/时长/生成方式/输入参考图/静态视觉锚点/起始帧/状态链/终点` + `### 可复制提示词`；H3 走六段式 |
| 6 | `short-drama-produce` | `制作成果/images/` | `preview → 显式确认 → run`；`source` + `source_entry`（`IMG-*`/`MOTION-*`/`SHOT-*`）、`reference_bindings` |
| 7 | `short-drama-edit` | `剪辑单.md`、`制作成果/成片/` | 转场、音色登记、`[VO]` 字幕 |
| 8 | `short-drama-review` | `审查/<EP>-审查.md` | 用可见 ID 指向问题 |

**逐镜硬约束**（`short-drama-storyboard/SKILL.md`）：
- 每镜写清唯一职责、来源、时长、景别/机位、运镜、起点、唯一主要动作、终点和声音（`:53`）。
- **有台词镜头必须标 `镜型：SOLO / OTS / DUO`**；`length` 取 **17 的整数倍**（`:135-151`）——这正是 H3 帧网格的来源。
- `分镜.csv` 另补 `export_frames`（写帧不写秒）、`音色`、`验收基线`、`refs` 四列供脚本消费。
- 冻结关键帧只写该瞬间**能看见**的内容，不写动作结果（`:152`）。
- 一集关键帧要像同一部片：每条正文用**同一句画风**，每场景同一句光与色温；先出该场景一张中远景作定调图并接受，其余镜头把它作为最后一张参考，只取色调／光线／质感，不取构图（`:154`）。

**槽位语法**（`short-drama-storyboard/SKILL.md:179-185`）：

```
REF-<slot>（顺序：<n>）· <项目相对路径>《<中文名称>》（用途：<用途>；控制：<范围>；不得控制：<范围>）
```

`用途` 只能取九词之一：身份／造型状态／地理／构图／尺度／效果／起始帧／结束帧／风格（`skills/short-drama/references/reference-roles.md:20-30`）。创作者在项目外出图时用 `PLAN-...`，语法相同，只把路径换成 `IMG-...` 或 `SHOT-...` 条目 ID（`:200-203`）。

**门禁**：

```
python <drama>/skills/short-drama-storyboard/scripts/storyboard_lint.py 分镜.md --csv 分镜.csv
```

检查「这一镜交给单轨生成端能不能出声」+ 人物互动站位与视角有无机位语言，以及 `export_frames` 网格、参考图来源、音色/验收基线、打斗三要素、场级节奏。配套 `references/shot-handoff.md` 规定镜间交接：**后一镜的起始帧，必须是前一镜真实结束的那一帧**，同一文件名在前镜 `结束帧` 与后镜 `起始帧` 里路径逐字相同。

**验收**：lint 通过；每个 `REF-/PLAN-` 槽位有 `顺序` 和合法 `用途`；`分镜.csv` 四列齐全；有台词镜都有镜型与音色。

**坑**：`12-H3提示词-官方指南/README.md:107` 记录过一个真实事故——「用『顺序』当身份，顺序就会漂」（SHOT-023 把两个角色的槽位对调了）。修正办法 `README.md:109` 写得很明确：**槽位固定化**，`<Picture 1>` 永远是冻结关键帧、`<Picture 2>` 永远是该角色、没用到的编号留空不重排。本手册 N9 的装配脚本就是按这条实现的。

---

### N3 · drama → 视觉资产契约整理

**目的**：把 drama 的 Markdown 收敛成「可直接出图」的清单，不让出图环节重新理解剧本。

**操作**
1. 导出出图块：用 `short-drama-image-prompts` 的 `references/asset-export-blocks.md`，把 `视觉设定.md` + `图片提示词.md` 导出为编号块，产物 `剧集/<EP>/导出/asset-blocks.md`，前缀 **C**（人物）/ **S**（场景）/ **P**（道具）。该文件明确是**导出视图**，原项目文档仍是唯一真相，导出块不回写。
2. 逐字带走锚点：人物块的五官／发型／服装段取 `视觉设定.md` 的识别锚点与连续性锁（`:37-40`）；风格前缀统一（`:52`「同一人物的多视角/表情格请用**同一张参考图 + 同一风格前缀**」）。
3. 锁定项目画风：从 `视觉设定.md` 的「项目视觉方向」读取，按 `short-drama-storyboard/references/comic-keyframe-lexicon.md:48-63` 的 8 种基底选一种并写成**可观察**写法：

   | 赛璐璐动画帧 | 厚涂漫画 | 平涂漫画 | 国风条漫 |
   |---|---|---|---|
   | 日系二次元漫剧 | 复古港漫 | 水彩叙事 | 极简叙事漫画 |

   例：赛璐璐 = 清晰轮廓线、平整色块、层数克制的硬边阴影。词表 `:119` 要求按「事实 → 视觉语言投影 → 可读性约束」顺序写。
4. 生成槽位固定表：把每镜的 `输入参考图` 按 `顺序` 列成一张全片统一的表，强制 Picture 1/2/3/4 语义固定。

**输出**：`导出/asset-blocks.md`（C/S/P 块）、`画风基底.md`（一句全片统一画风句）、`槽位固定表.md`。

**验收**：同一个人物在所有 C 块里锚点逐字一致；画风句只有一条；槽位表里 `<Picture 2>` 不出现两个不同角色。

---

### N4 · 参考板出图 ★ 回答「vibe 之前要不要用 ComfyUI」

> **结论：需要这一步，而且必须排在 vibe 之前；但严格说需要的是「参考板出图」这个环节，ComfyUI 只是三种实现里最顺手的一种——你本地库里目前没有现成的 ComfyUI 工作流做这件事。**

#### 4.1 为什么这一步省不掉

1. **H3 的输入结构强制要求**。r2v 的 `refs` 是 4 个固定槽：`<Picture 1>` 每镜关键帧（vibe 出，每镜换）、`<Picture 2>` 角色板、`<Picture 3>` 场景板、`<Picture 4>` 服装／双人站位板。后三张是**全片固定的身份锚**，与每镜帧是两类东西，vibe 不会顺带产出。
2. **vibe 出每镜格时也要挂它们**。`docs/comic-drama-workflow.md:155` 的原文：「漫剧人物好看但每镜不像同一个人 → 回到 `视觉设定.md` 收紧可见识别锚点；分镜可引用同一 `IMG-...` 提示词条目来对齐意图，但**只有生产 job 的 `references` 实际传入同一图片文件时才共享像素依据**」。`storyboard-sheet-recipe.md:26` 更直接：「**参考图强制入模**：项目里已有角色参考板、地点板等真实图片时，必须作为参考图传给出图模型」。只给文字、不给像素，跨镜必漂。
3. **模型模式表倒推顺序**。`minimax-h3.md:73` 规定「起始帧 + 人物／地点／道具图同时存在 → full-reference 六段式」，`:81-84` 说明首/尾帧与参考输入互斥、整组统一走 reference。也就是说「先有板、后有帧、一起提交」是模型输入结构，不是流程偏好。
4. **工具侧也印证**。09 NG 版 Qwen Image 2.1 的 `+ Figure from a sheet` 要求先把 character sheet 放进 Image card（`_上游文档/GUIDE.md:617-620,634-636`）；只有 `+ Background` 能从文字画空场景。即便想在 ComfyUI 里画每镜格，也得先有角色板。

#### 4.2 参考板清单与规格

| 板 | drama 来源 | 内容 | H3 槽 | 生命周期 | 命名 |
|---|---|---|---|---|---|
| 角色定妆板 | C 块 / `IMG-*-SHEET` 提示词 | 三段式：主视图特写 + 正/侧/背三视图 + 五格表情板；锚点逐字取自识别锚点与连续性锁 | `<Picture 2>` | **全片固定** | `IMG-<角色>-SHEET.png` |
| 场景板 | S 块 / `IMG-*-PLATE` | 双联空镜地点板；地理锚点从地点条目取，只换光态与天气（`empty-shot-recipe.md:16-19`） | `<Picture 3>` | 同场景固定 | `IMG-<地点>-PLATE.png` |
| 服装／双人站位板 | C 块 / `IMG-*-PAIR` | 两人**面对面、一左一右**，服装逐字锁定；供 DUO 镜 | `<Picture 4>` | **全片固定** | `IMG-<项目>-PAIR.png` |
| 道具板（可选） | P 块 | 识别特征 + 状态序列 | 按需 | 按需 | `IMG-<道具>-PROPS.png` |

**统一规格**：PNG，≥1344 宽，16:9（非 16:9 会被裁，`ref_max_size=1344` 不降采样）。**一个参考只给一个职责**——`12-H3提示词-官方指南/README.md:83` 提醒「每段只挂这一段需要的图（身份板 + 场景板），别把三视图四张全挂，参考图等权平均会串味」。

#### 4.3 三条实现路径对比

| 路径 | 做法 | 产物落点 | 优点 | 门槛 / 现状 |
|---|---|---|---|---|
| **A · ComfyUI 文生图（推荐补齐）** | 新建 Qwen Image / Flux / SDXL 文生图工作流，把 N3 的 C/S/P 块逐条出图，直落 `input/` | `input/<项目>/{chars,scenes,props}/` | 与 H3 同一台机器闭环；路径／尺寸／命名一次配好；画崩可只重出一张板，批量可复现 | **本地库里没有现成工作流**。`F:\skills\工作流\` 约 100 个 JSON 全是 H3 导演台族（`NGH3Director`/`MiniMaxH3Director` + UNET/CLIP/VAE），无独立 `KSampler`/`QwenImage`/`Flux` 文生图节点。09 NG 的 Qwen 还需 ComfyUI ≥ 0.37（本机 0.30.2） |
| **B · 外部生图工具（drama 原生支持，最快跑通）** | 把 `导出/asset-blocks.md` 的 C/S/P 编号块粘到**即梦「图片 4.0」＝ Seedream 4.0**（中文最强、≤14 参考图、0.2 元/张）或 Nano Banana Pro，人工下载 | 手动拷进 `input/` | 零开发；drama 已把锚点逐字带走、风格前缀写好；**同一模型可在 N5 继续用于逐镜格**，工具链不换 | 人工搬运；图片不进 drama 项目，只能用 `PLAN-...` 槽位，且这些镜头**不能转生产技能**（`comic-drama-workflow.md:160`） |
| **C · `$short-drama-produce`** | `preview → 显式确认 → run`，job 带 `source`/`source_entry`/`reference_bindings` | `剧集/<EP>/制作成果/images/` | 官方路径，能绑成 `REF-...`，可追溯审计 | 需项目外 **adapter + 凭据**（`short-drama/SKILL.md:59-60`）；本链路未配置 |

**建议**：首次跑通用 **B**（最快拿到能用的板，验证整条链路）；跑通后把 **A** 建成固定工作流，让「drama 文字 → 参考板 → `input/`」自动化，这才是「生产线」的完整形态；C 只在已有 adapter 时用。N4 与 N5 可以用**同一个生图模型**（推荐 Seedream 4.0），这样画风、身份锚、参考图语法全链路一致；N5 的三条现成路线与对接规范见 5.1。

#### 4.4 走 A 时的落地做法

1. 建一个最小文生图工作流：Load Checkpoint（Qwen Image / Flux / SDXL）→ CLIP Text Encode（正向／负向）→ KSampler → VAE Decode → Save Image。
   - **正向** = N3 的 C/S/P 块正文。`asset-export-blocks.md` 的「单块格式」已含风格前缀 + 逐字锚点 + 画幅标注，可原样粘贴，不要改写。
   - **负向** = 块内自带的基线 `text, watermark, extra fingers, distorted face, plastic texture, generic face`（后两项为抗 AI 味词）；动画／古风块追加 `3d render, cgi` 防写实化跑偏，场景空镜可加 `cluttered`。**不要把 `--ar`／`--s` 之类平台参数混进正文**，它们在即梦等平台不生效，只会污染提示词。
   - **画幅**按块尾标注：人物参考板 16:9 横、头像特写 1:1、地点板 16:9。
2. Save Image 的 `filename_prefix` 直接设成 `IMG-<角色>-SHEET` 等，输出目录指向 ComfyUI `input/<项目>/chars/` 等。
3. **同一人物的多视角／表情格必须用同一张参考图 + 同一风格前缀**（`asset-export-blocks.md:52`），不要每个视角重新抽卡，否则板本身就先漂移了。
4. 出图后逐张人工审：脸型、发型轮廓、服装剪裁与颜色、双人站位是否肩并肩（并肩构图会被忠实放大）、有无多余人物／血迹／文字。**这一步是 N11 审片的前移**，在这里改成本最低。
5. 审定后冻结，全片不再换；文件名登记进 N7 的 CSV。

#### 4.5 顺序结论

```
drama 文字设定 → N4 参考板（少量、全片固定、管身份与空间）
                → N5 vibe 每镜格（每镜一张、管该镜起始构图，必须挂 N4 的板）
                → N9 装配（板占 Picture 2/3/4，格占 Picture 1）
                → H3 r2v 一次提交
```

**三类「图」不要混淆**：参考板（进生产、固定）、vibe 每镜格（进生产、逐镜换）、整页 storyboard sheet（`storyboard-sheet-recipe.md:3-5` 明确「**不进生产链、不替代《分镜.md》、不作为任何 `REF-...` 槽位的图片来源**」，路径 `剧集/<EP>/预览/storyboard-<场景ID>.png`，只是给创作者看片子长什么样）。

---

### N5 · vibe 逐镜漫画格

**输入**（drama 产物 → vibe 的完整交接见第 3 章）：每镜 `### 冻结关键帧提示词` + 景别/机位/运镜/时长/起点/终点 + 项目画风句 + **N4 的三张参考板** + `视觉依据`。

#### 5.0 定位辨析（先读）

本节点要的是**每镜一张静帧 PNG**，填 H3 的 `<Picture 1>` 起始构图。若「vibe」指的是文档里那类**代码渲染程序**（`vibe-video`：agent 写代码 → 无头浏览器逐帧截屏 → FFmpeg 合成 MP4），它产出的是**视频成片**，不是静帧，**不能直接填 N5 这个槽**；它与 H3 导演台是**并列的另一条出片路线**（文档第 11 节结论「不是 ComfyUI」），不是 H3 的上游。强行把它的 MP4 截帧当参考图是绕路，且丢失了 drama 分镜的逐镜构图控制。定位辨析见 0.3，同构的现成程序见 6.1。**定线已确认：N5 按「出静帧环节」执行，代码渲染类程序不进入本链路。**

#### 5.1 现成实现选型（2026-11-18 现网核查）

没有名为 vibe 的现成服务能做这件事，但下面三类工具可直接承担。**共同硬门槛是「参考图入模」**——`comic-drama-workflow.md:155` 写死「只有生产 job 的 references 实际传入同一图片文件时才共享像素依据」，纯文字角色锚不算；下列三者都满足。

| 路线 | 具体工具 | 中文分镜提示词 | 多参考图 | 逐镜方式 | 成本 | 自动化 |
|---|---|---|---|---|---|---|
| **A · 在线 API（推荐）** | 即梦「图片 4.0」/ 火山方舟 `doubao-seedream-4-0-20260415` | 最强，中文语义理解优于 Nano Banana | 单次 ≤10（4.0）／≤14（4.5、5.0 lite） | **一镜一调**；组图模式一次最多 15 张关联图 | 火山方舟 0.2 元/张（文生图、图生图同价），IPM 500 | 可写脚本，与 `csv_to_timeline.py` 共用同一份 `shotlist.csv` |
| **B · 在线 API（备选）** | Nano Banana Pro（Gemini 3 Pro Image） | 弱，中文常需翻译 | ≤14 混合参考／5 角色一致／6 张独立参考 | 一次 1 张，N 镜 = N 次调用 | 约 $0.134/张（1K/2K）、$0.24（4K） | 可脚本但贵且慢；适合单张封面／定调图 |
| **C · 本地 ComfyUI** | `Qwen-Image 2.1`（生成＋编辑合一，≤16 参考槽）／`Qwen-Image-Edit-2511`（≤3 张，Apache 2.0） | 强 | 前 3 槽固定给三张板；2.1 多余槽留空，2511 无余量给上一镜回灌；ControlNet 锁姿态 | Batch Prompts 一行一镜，或 `/prompt` API 逐镜注入 | 0（电费） | 板帧同源最干净；需显卡、模型、插件、画风 LoRA；**2.1 仅非商用** |

- 路线 A 官方明确把 “Storyboards and comic pages that keep one character across frames” 列为能力项，`/images/generations` 支持图片与文本混合输入，是唯一同时满足「中文 + 多参考图 + 批量 + 国内合规 API + 低价」的。
- 路线 C 有可下载的现成工作流（Qwen Image Edit storyboard：参考图组 / Previous Scene / Batch Prompts / ControlNet / Qwen Image Edit 五个分组）。**注意**：网上另有一套「Qwen3-VL 看图自动写分镜 → Qwen-Image-Edit 逐镜出图」的 19 节点工作流，它会自己重写分镜，与本链路 drama 已产出的分镜冲突——用 C 时**必须跳过 `Qwen3_VQA` 节点**，把 drama 的冻结关键帧直接灌进 `easy promptLine` / Batch Prompts。
- 本机 ComfyUI 记录为 0.30.2，上 Qwen-Image 2.1 前先确认版本要求（09 NG 版需 ≥ 0.37）。
- **商用定线以 `N5-ComfyUI实现卡.md` 1.1–1.3 为准（2026-11-19 核准，覆盖本节以上表述）**：`Qwen-Image-Edit-2511` 本身就是 **20.4B**，与 20B 的 `Qwen-Image` 基座／`Qwen-Image-2512` 是**三个独立 checkpoint**，不是「小模型 + 基座」的加载关系；`Qwen-Image 2.1` 是 7B 且 Research License **仅非商用、商用排除**。正确分工是「基座／2512 文生图出底图与 N4 板 → 2511 带参考图编辑派生每镜」，单押 2511 出不了全新构图。**最关键**：全链路能否商用由 **MiniMax H3 Community License** 决定（排除美/欧/英/韩、年营收 >2000 万美元需书面授权、UI 强制署名 `MiniMax H3`、禁止用输出蒸馏其他模型、AUP 20 条），换成 Apache 2.0 出图引擎或即梦 API 都绕不开。另有现成工程 `comfy-h3-container`（Docker + H3 r2v + 2511 修图 + SDXL 设定表，12GB 显存，自带许可证清单）可作底座，但 SDXL＋2511 双模型板帧不同源，需按 1.1 重排。
- **路线 C 的 ComfyUI 落地（2026-11-19 补充）**：官方已有 `Qwen-Image 2.1`（文生图＋指令编辑**同一 checkpoint**，原生 2K，`Text Encode Qwen Image 2.1` 最多 16 个参考槽，按槽位顺序拼成 VAE latent）与 `Qwen-Image-Edit-2511`（`TextEncodeQwenImageEditPlus` 最多 3 张图，正好被三张板占满）。**许可证是硬约束**：`Qwen-Image 2.1` 为 Qwen Research License **仅限非商业用途**，商用需向模型方授权且产品文档须标注 `Built with Qwen`；`Qwen-Image-Edit-2511`／Qwen-Image 基座为 **Apache 2.0**。逐镜排队三选一：`Load Text File` 一行一镜、`VRGDG_StoryBoardCreator`（`auto_queue` 自排队 + `redo_indexes` 单镜重跑）、ComfyUI `/prompt` API 脚本（与 `csv_to_timeline.py` 同构，**推荐**）。三个必避语义坑：编辑模型把 SHEET 当 `image_1` 会导致每镜都是定妆站姿、编辑模板自建空 latent 会尺寸偏移、`Qwen3_VQA` 之类自动分镜节点会覆盖 drama。完整节点清单与切换清单见 `N5-ComfyUI实现卡.md`。

**计费口径（2026-11-19 火山方舟官方「模型价格」页核准）**

| 项 | 官方口径 | 对本链路的影响 |
|---|---|---|
| 输出图单价 | `doubao-seedream-4-0` **0.20 元/张**，文生图／图生图同价 | 每镜成功出 1 张帧计 0.20 元；100 镜约 20 元 |
| **输入图单价** | **免费** | **每镜挂 3 张参考板（SHEET/PLATE/PAIR）不额外计费**，这是逐镜参考图链路的成本优势 |
| 失败与审核 | 因审核等原因未成功输出的图片**不计费** | 试错抽卡只按成功张数算，重出图成本可控 |
| 组图 | 按实际生成的图片数量计费 | 佐证「一镜一张」不会比组图更贵 |
| 限流 | IPM 500 | 批量逐镜足够，无需削峰 |
| 公式 | 单次请求费用 = Σ(输入图 × 单价) + Σ(输出图 × 单价) | 输入项恒为 0 |

**网页／App 与 API 是两套收费体系，别混算**：即梦网页端是「每日免费积分 + 会员订阅制」——免费层每日约 60~100 积分、当日清零、默认 720P 带水印；单月购买基础 79 元（725 积分）／标准 239 元（2210）／高级 649 元（6160），连续包月 69／199／499，年付另有折扣；会员权益含「图片 4.0 2K 限时免费」（基础／标准）与「4K 限时免费」（高级）。**积分消耗随模型与清晰度浮动，第三方口径从 1~2 积分/张到 8~16 积分/张互相矛盾，一律以生成前界面显示的预计积分为准**；且积分制「失败也扣积分」。所以批量逐镜与脚本化调用走 API 更划算、重试成本更可控，网页端只适合前 2~3 镜的手工验证。以上价格均为 2026-11-19 公开资料，档位与活动调整频繁，以下单页实时价格为准。

**版本现状**：官方价格页现同时列 `seedream-5-5 / 5-0-flash / 5-0-lite / 4-5 / 4-0`（分别 0.13 起／0.12／0.22／0.25／0.20 元/张）。**按价格 4.0 并非最低**（5-0-flash 0.12、5-5 0.13 起都比它便宜）；`doubao-seedream-4-0-250828` 标记即将下线，若仍用 4.0 首推 `doubao-seedream-4-0-20260415`。本链路锁定 4.0 的理由是**画风与同源板已按它对齐**，不是价格——**不要因为 5.0-flash 更便宜而中途换模型**，换引擎会破坏 N4/N5 同源定线（方案 4.4.3）。确需换型号时，N4 三张板与全部每镜帧必须一起重出。

#### 5.2 操作

1. 按 `分镜.md` 的 `## SHOT-...` 顺序逐镜生成，**一镜一调、一镜一张**，不画整页漫画。
2. 每镜把 N4 的角色板／场景板／服装板作为参考图传入（像素级身份锚），文字只负责该镜「这一个瞬间」的构图、人物位置、光位、情绪；不写动作结果。
3. 全片复用同一句画风句与同一色温描述；同场景先用一张中远景定调图，其余镜头只取色调／光线／质感，不取构图（`short-drama-storyboard/SKILL.md:154`）。
4. 输出命名 `SHOT-<EP>-<镜号>.png`，落到 `input/<项目>/frames/`（本链路示例用 `frames_v4/`）。
5. **不生成对白气泡、字幕、文字、logo**——这些在 H3 阶段由 prompt 与音频层处理，画面里出现文字会被忠实放大。

#### 5.3 drama 提示词的重组规范（不能原样粘贴）

`### 冻结关键帧提示词` 是写给 H3 图生视频的，带 `<Picture N>` / `视觉依据` / `顺序` 等 H3 语义标签，Seedream 与 Qwen 都不认。每镜出图 prompt 按四段重组：

```
[1 身份锚]   C 编号块逐字复制（脸型／发型／服装／辨识物，全片不变）
[2 本镜正文]   该镜「### 冻结关键帧提示词」全文（只写这一瞬间看得见的）
[3 画风句]   项目视觉方向 + comic-keyframe-lexicon 基底，全片同一句
[4 约束]   16:9 横画幅；无对白气泡、无字幕、无文字、无 logo
```

`<Picture N>` 一律改成工具的引用写法（Seedream：`Image 1` / `Image 2`…；Qwen：参考图槽位），并**按 drama `- 输入参考图` 的 `顺序` 固定不重排**；某镜缺图留空槽，绝不前移补位（`12-H3提示词-官方指南/README.md:109`）。

#### 5.4 输出与验收

**输出**：`frames_v4/SHOT-EP001-004.png` 等，一镜一张；16:9、输出 ≥1344 宽（Seedream 用 2560×1440 预设后下采样），不用 9:16。

**验收（起始构图审片）**：谁左谁右、是否并肩、有无多余人物／血迹绷带／现代物品／文字、16:9、≥1344 宽、画风与定调图一致。`<Picture 1>` 的构图 **prompt 压不过它**，画错只能重出图。

#### 5.5 三个必踩的坑

1. **别用「一次 9~15 张组图」代替逐镜**。组图只保证风格与角色一致，画面由模型自行分发，**不保证每镜景别机位精确对应 drama**；而 H3 `<Picture 1>` 是起始构图且 prompt 压不过它，构图错整镜废。组图只适合出同场景的备选／定调图。
2. **参考图分两类，别混淆**：N4 的板（SHEET/PLATE/PAIR，全片固定）是给 vibe 出图当身份锚的；vibe 出的每镜格是给 H3 `<Picture 1>` 的。整页 storyboard sheet 不进生产链（`storyboard-sheet-recipe.md:3-5`）。
3. **画风必须同步**：出的是漫画格，N7/N9 的 negative 里要删掉「卡通／动画感」、改掉真人实拍类描述，否则参考图与提示词互相打架。

> 建议落地顺序：先用路线 A 的即梦网页手工跑 3~5 镜，验证「三张板 + 冻结关键帧」的重组效果；跑通后写一个 `frames_from_shotlist.py`，读 `shotlist.csv` 逐镜调火山方舟 API，产物直落 `input/<项目>/frames/`。届时这份 CSV 同时被出帧脚本和 `csv_to_timeline.py` 消费，N4→N5→N9 就闭环了。

---

### N6 · 音色资产

**输入**：`剧本.md` 对白 + `分镜.csv` 的 `音色` 列。
**操作**：每个说话人准备一段**干净人声 ≥10s**、无底噪无配乐的 wav；按角色命名 `REF-<角色>.wav`，落 `input/<项目>/voices/`。
**约束**：`Audio: reference` 的段必须挂 `ref_voice`；`Audio: none` 的静默段可不挂。EP001 实战里连静默段也挂了音色（只在 prompt 写 no speech），两种都可行，但**同一项目要统一选一种**。
**坑**：段长必须 ≥ 台词朗读时长，否则音轨被截断；中文负向对 H3 近乎无效，重要禁项写进正向。

---

### N7 · 资产入库 + 填分镜表

**操作**
1. 把 N4/N5/N6 的产物按 N0 的目录树放好，文件名带镜号或角色名。
2. 复制 `shotlist_vibe_template.csv`，**一行 = 一个 segment**，逐列填：

| CSV 列 | 来源 | 落到 timeline_data |
|---|---|---|
| `shot_id` | `分镜.md` 的 `SHOT-...` | `segments[].id`（脚本按序号重编 `seg_00N`） |
| `continuity_group` | 按 `shot-handoff.md` 的连续段人工分组 | 同一组一份工作流、一次提交 |
| `length_frames` | `分镜.csv` 的 `export_frames` | `length` / `frameCount`（H3 token 网格 **17n 或 5+17n**，常用 102/124/136；124 = 5+17×7 不是 17 的整数倍） |
| `frame_key` | N5 的每镜格 | `refs[0]` / `<Picture 1>` |
| `ref_role_sheet` | N4 角色板 | `refs[1]` / `<Picture 2>` |
| `ref_scene_plate` | N4 场景板 | `refs[2]` / `<Picture 3>` |
| `ref_costume_pair` | N4 服装站位板 | `refs[3]` / `<Picture 4>` |
| `ref_voice` | N6 | `refAudios[0]` / `<Audio 1>` |
| `subject_definitions` … `non_diegetic_music` | `视频提示词.md` 六段式 | 拼成段 `prompt` |
| `audio_tag` | 有对白 `reference` / 静默 `none` | 段尾 `Audio:` |
| `negative_prompt` / `seed` | 项目统一 | `negativePrompt` / `widgets[4]` |

3. **画风同步（必做）**：vibe 出的是漫画格，必须删掉 negative 里「卡通／动画感」，并把「真人实拍电影质感」类描述改成 N3 的画风句。不改会参考图与提示词互相打架——这一步比任何节点改动都影响成片。

---

### N8 · 体检门禁

```
python csv_to_timeline.py --check-only
```

自动检查：字段齐全／帧数网格（17n 或 5+17n）／段长 vs 台词朗读时长／prompt 完全一致（整图缓存）／角色板全片是否唯一／漫画格与负向禁项冲突／`input/` 资产缺失／音频标签与音色文件配套。

**有 ERROR 先修 CSV，不进渲染。** WARN 逐条判断；`input 根目录不存在` 说明 N0 的路径还没配好。

---

### N9 · 装配

```
python csv_to_timeline.py --csv shotlist.csv ^
  --workflow "F:\skills\工作流\02-H3漫剧流程\H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json" ^
  --out out\H3-vibe-<EP>-<组>.json --seed 42 ^
  --input-root "<ComfyUI 真实 input 路径>"
```

脚本行为：
- 按 `continuity_group` 分组，**每组各出一份 JSON**（同组必须一次提交，否则 22 帧 latent 接力失效）。
- 拼六段式 `prompt`（`subject_definitions:` … `non_diegetic_music:` … `Audio: <tag>`）。
- `refs` 固定 4 槽，**编号固定语义、绝不重排**；缺图留空槽，不把后面的号往前挪。
- `genImage` 恒为空（6 个 EP001 出片工作流实证：从未使用）。
- 只改 `widgets_values[11]`（timeline_data 字符串）、`[10]`（totalFrames）、`[4]`（seed）；节点、连线、UNET、采样器一律不动。
- 顺带规范化底座残留：把 `video`／`global.sourceWidth/Height` 同步成 `output` 分辨率；`SaveVideo` 前缀自动设为 `video/<输出副本名>`（`--save-prefix` 可覆盖）。`output.continuityEnabled` 等语义字段原样继承底座。
- 强制 `--out ≠ --workflow`，**禁止覆盖权威原件**。
- 时间轴 `start` 累加、`totalFrames` 重算、`durationSec = totalFrames / frameRate`（帧率从底座自动读，不用手填）。

**验收**：`json.load` 可解析；对比底座节点数／连线数一致；UNET 仍是 `minimax_h3_ref2va_*`；`<Picture 1>` 逐镜换、2/3/4 全片固定。

---

### N10 · 01 快出预览（试错）

**操作**：把副本拖进 ComfyUI → 确认 `input/` 素材路径对得上 → 时间线**整组一次提交**。用 `H3-通用01-快出预览-r2v-4step-960x544.json` 同款参数（4step / 960×544，约 2–4 min）跑构图、动作、运镜、画风。

**铁律**：**有对白镜头禁止 generate + 4 步**。`02-H3漫剧流程/README.md` 实测：4 步下音频 latent 只更新 4 次，波形不静音（mean −14 dB）但语音语义崩坏——「有声音、听不懂」。无对白空镜／动作镜可用 4 步且成片可直接交付；有对白镜必须走 25step + 参考音色。

**验收**：构图、动作幅度、画风统一、镜间衔接、无崩手崩脸。

---

### N11 · 审片回退

| 审片发现 | 回退到 | 动作 |
|---|---|---|
| 起始帧画错（并肩／多余人物／血迹绷带） | **N5**（甚至 N4） | 重出该镜格；prompt 压不过 `<Picture 1>` |
| 变脸／画风跳 | **N4** | 查 `<Picture 2/4>` 是否全片固定不换；收紧 `视觉设定.md` 识别锚点 |
| 动作／台词／音色不对、台词被截断 | **N7** | 改 CSV 的 `detailed_description` / `length_frames` / `ref_voice` |
| 改了 prompt 没出新文件 | **N7** | 微调几个字**打破整图缓存**（token 完全一致会命中缓存） |

**共同前提**：任何回退都先用 01 复验，确认后再上 02。不要直接重跑 25step。

---

### N12 · 02 出片 / 03 精修

- **02**：`H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json` 同款参数（25step / cfg 1.0 / 1344×768 / res_multistep+simple / shift 12-3，约 15–25 min 每 5s）。对白段挂参考音频、段尾 `Audio: reference`，台词逐字写进 prompt 可随时改词重跑，口型由 AV latent 自动驱动。
- **03**：关键镜头仍嫌细节差时用 `H3-通用03-二采精修-refine-25step-1344x768.json`（25–40 min）。
- 成片落 `output/minimax_seg_export/<时间戳>/seg_XXXX.mp4`。

**坑**：`output.continuityOverlapFrames=22`，段间靠 latent 接力。`continuityEnabled` 由底座决定、脚本继承不擅改：**当前底座通用02 = `True`**（多段连续组默认开启 22 帧接力，符合「同组一次提交」）；EP001 S004 实例是 `False`（便签写「各段独立」），但那只是出片实例、不是底座。若改用其他底座，出片前请核对这一项，别按 EP001 的 `False` 推断当前链路。

---

### N13 · 归档

把「小说文本 + drama 五份 Markdown + 导出块 + 全部参考板 + 每镜格 + 音色 + CSV + 工作流副本 + 成片 + seed」按镜号归档，保证任何一镜都能回溯到它的起始帧与提示词。排除凭据与生产工具隐藏状态。

---

## 3. drama 产物 → vibe 输入契约 ★

用户特别指出 drama 是**全流程分镜 skills**，这一章把「drama 哪些产物用在 vibe 上」逐项说清。

### 3.1 直接喂给 vibe 的产物

| drama 产物 | 具体字段 | 在 vibe 里的作用 | 是否必须 |
|---|---|---|---|
| `分镜.md` · `### 冻结关键帧提示词` | 整条画面描述（含构图、景别、光位、画风词、排除项） | **每镜格的主体 prompt**，决定这一镜「拍什么」 | 必须 |
| `分镜.md` · `- 景别机位 / - 运镜 / - 时长 / - 起点 / - 唯一动作 / - 终点` | 镜头语言 | 决定构图、视角、帧数；`终点` 供 `shot-handoff` 交接 | 必须 |
| `分镜.md` · `- 视觉依据` | `《视觉设定.md》·<人物\|造型\|地点\|道具>「名称」（控制：范围）` | 告诉 vibe 这一镜该引用哪张板、控制什么 | 必须 |
| `分镜.md` · `- 输入参考图`（`REF-/PLAN-` 槽位，含 `顺序/用途/控制/不得控制`） | 槽位表 | **vibe 挂图顺序**，直接对应 `<Picture N>` | 必须 |
| `视觉设定.md` · 人物条目 | `识别锚点` / `本集造型` / `画面代称` / `连续性锁` | 生成角色板的文字锚；vibe 逐镜复用的身份依据 | 必须 |
| `视觉设定.md` · 地点条目 | 空间布局 / 固定锚点 / 感官锚点里的光线与材质 | 生成场景板；vibe 同场景光色一致 | 必须 |
| `视觉设定.md` · 道具条目 | 识别特征 + 状态序列 | 道具板；跨镜道具不换样 | 按需 |
| `视觉设定.md` · `项目视觉方向` + `comic-keyframe-lexicon.md` | 8 种画风基底之一 + 可观察写法 | **全片统一画风句**，vibe 每条正文复用 | 必须 |
| `图片提示词.md` · `IMG-*-SHEET / -PLATE / -PAIR` 的 `### 可复制提示词` | 板子提示词 | N4 出参考板的输入；出的板再回喂 vibe | 必须（经 N4） |
| `导出/asset-blocks.md` · C/S/P 编号块 | 锚点逐字带走 + 风格前缀 | N4 出图时直接粘贴 | 推荐 |
| `storyboard-sheet-recipe.md` · 格图排版 | 3×3/4×3 网格、每格 16:9、镜号时长标签 | 仅供**人工预览** | 否，且**不进生产链** |

### 3.2 不喂给 vibe 的产物

| 产物 | 去向 | 原因 |
|---|---|---|
| `视频提示词.md`（MOTION-* 六段式） | **直接进 H3**（N7/N9） | 它描述的是动态与声音，不是静帧画面；vibe 只需要冻结关键帧那一段 |
| `剧本.md` 的对白 | 进 H3 的 `detailed_description` 与音频层 | 台词影响口型与时长，不进漫画格画面（画面里不写气泡文字） |
| `剪辑单.md` | N13 归档 / 后期 | 与逐镜生成无关 |
| `制作成果/成片/` | 后期 | 下游产物 |
| **整页 storyboard sheet** | 人工预览 | `storyboard-sheet-recipe.md:3-5` 明确不替代《分镜.md》、不作为任何 `REF-` 槽位图片来源 |

### 3.3 交接语法：`顺序` → `<Picture N>`

`minimax-h3.md:129-139` 给出了完整映射：

```text
REF-SHOT-START（顺序：1；用途：起始帧）  -> <Picture 1>
REF-XIAOYU-SHEET（顺序：2；用途：身份） -> <Picture 2>
REF-STUDY-PLATE（顺序：3；用途：地理）   -> <Picture 3>
```

「这份清单不依赖文件路径，只依赖 `顺序` 和 `用途`……把 `REF-` 换成 `PLAN-`，定位符换成 `SHOT-...` 或 `IMG-...`，正文一个字都不用改。创作者按 `顺序` 在生成界面里挂图，`<Picture N>` 就对得上。」

**本链路的加固**：按 `12-H3提示词-官方指南/README.md:109` 做**槽位固定化**——全片统一 Picture 1 = 每镜格、2 = 角色板、3 = 场景板、4 = 服装站位板，缺图留空不重排。这样即使某镜少了道具板，也不会把角色板挤到 3 号位导致跨镜串味。

### 3.4 `用途` 九词 → H3 职责

`skills/short-drama/references/reference-roles.md:20-30`：身份（只管稳定脸型体态）／造型状态／地理（只管空间关系）／构图（只管占画比例）／尺度／效果／起始帧／结束帧／风格。**一个参考只给一个职责**，冲突参考会让模型在两者之间摇摆。

### 3.5 drama 与「漫画／外部生图」的对接原文

- `docs/comic-drama-workflow.md:19-21`：「视频提示词.md（动态漫剧） └─ 静态漫剧：关键帧切换 + 配音，可跳过」；`:109-110`「只做关键帧切换 + 配音的静态漫剧时，本步可以跳过，**分镜关键帧与图片提示词直接进入生产预览**」。
- `short-drama-image-prompts/SKILL.md:3`：「**不生成图片，也不调用供应商**」；`:9-11`「`IMG-...` 是提示词条目的稳定 ID；**实际图片须由创作者提供，或来自经确认的生产结果**」。→ 这正是 N4 存在的理由。
- `comic-drama-workflow.md:160`：「在网页界面里自己出图，被要求先在套件里生成参考图 → 让分镜把这一镜要挂的图写成 `PLAN-...` 槽位……视频提示词照常产出，只是这些镜头不能转生产技能」。→ 对应 4.3 的 B 路径。
- drama 全盘**无 `vibe` 字样**，交接是以「漫剧形态 / 项目外生图工具 / `PLAN-` 槽位」表述的，不是绑定某个具体工具。

---

## 4. 分镜表 → timeline_data 映射（速查）

| CSV 列 | timeline_data |
|---|---|
| `shot_id` + 序号 | `segments[].id` = `seg_001`… |
| `length_frames` | `length` / `frameCount` / `durationSec` |
| 累加 | `start` = 前段 `start + length`；`totalFrames` = 总和 |
| 六段式 6 列 + `audio_tag` | 拼成 `prompt`，段尾 `Audio: <tag>` |
| `negative_prompt` | `negativePrompt` |
| `frame_key` / `ref_role_sheet` / `ref_scene_plate` / `ref_costume_pair` | `refs[0..3]` 的 `imageFile`，`index` 固定 1..4 |
| `ref_voice` | `refAudios[0].audioFile`（index 0） |
| `seed` | `widgets_values[4]` |

`genImage` 恒为 `{"imageFile":"","fileName":""}`；`refVideos` 恒为 `[]`；`taskType` 段内为空；`global.prompt` 为空。

---

## 5. 端到端命令速查

```bash
# N2 门禁
python <drama>/skills/short-drama-storyboard/scripts/storyboard_lint.py 分镜.md --csv 分镜.csv

# N8 体检（不写文件）
python csv_to_timeline.py --check-only --input-root "<ComfyUI input>"

# N9 装配
python csv_to_timeline.py --csv shotlist.csv \
  --workflow "F:/skills/工作流/02-H3漫剧流程/H3-通用02-高清主线-参考音色对白-r2v-25step-1344x768.json" \
  --out out/H3-vibe-EP001-G01.json --seed 42 \
  --input-root "<ComfyUI input>"

# 底座已是通用02 默认值，--workflow 可省略；自定义 SaveVideo 前缀
python csv_to_timeline.py --group G02 --out out/H3-vibe-G02.json --save-prefix "video/EP001_G02"

# 只装配某个连续组 / 做真人写实向（不改画风告警逻辑）
python csv_to_timeline.py --group G01 --style live --out out/x.json
```

ComfyUI 内：拖副本 → 核对 `input/` 素材 → 整组一次提交 → 01 试错 → 审片 → 02 出片。

---

## 6. 常见坑与待办缺口

| 坑 | 处理 |
|---|---|
| 参考图与提示词画风打架 | N7 删 negative 的「卡通／动画感」，改真人实拍词为漫画向 |
| 跨镜变脸 | N4 板全片固定；`comic-drama-workflow.md:155`：只有 references 实际传入同一图片文件才共享像素依据 |
| `<Picture N>` 顺序漂 | 槽位固定化，缺图留空不重排（`12-官方指南/README.md:109`） |
| 4step + 对白 = 乱码语音 | 对白镜必须 25step + 参考音色 |
| 中文 negative 几乎无效 | 重要禁项写进正向 prompt |
| prompt token 完全一致不出新文件 | 微调几个字破缓存 |
| 首帧元素被忠实放大 | 出片前审起始帧素材，画错重出图而非改 prompt |
| 分多次提交连续组 | 22 帧 latent 接力失效，场景乱跳；同组一次提交 |
| `genImage` 被误当成落点 | 6 个 EP001 实证全为空；漫画格挂 `refs` index 1 |

**当前链路缺口（需补齐才能完全自动化）**：

1. **N4 无现成 ComfyUI 文生图工作流** —— 建议按 4.4 新建；但现网已有可直接用的在线模型（即梦 / Seedream 4.0），按 4.3 B 即可先跑通，**不再是阻塞项**，只是「全本地自动化」的缺口。
2. **vibe 所指已定线，不再待确认**（2026-11-18 用户确认）——链路 =「前半段现成程序出漫画静帧 + 后半段 H3 r2v」，见 0.3 与 `漫画前置-H3混合路线-实现方案.md`。`vibe-video` 这类代码渲染程序产出 MP4、与 H3 并列，已排除（见 0.3、6.1、6.2）。**当前真正待办是选哪套出图工具**（Seedream 4.0 / 分镜表工作台 / 本地 ComfyUI），以及出帧脚本尚未实现，见下方第 3 条。
3. **出帧脚本仍缺** —— 若按 N5 现状（出静帧），需要一个 `frames_from_shotlist.py` 把 `shotlist.csv` → 逐镜图自动化，并与 `csv_to_timeline.py` 共用同一份表；若改用 `infinite-creation`，这一步由它内置的资产生成接管。
4. **三处路径悬空** —— `01-分镜图片/`、`D:\ComfyUI资产\`、`D:\ComfyUI-aki-v3.2\ComfyUI\input` 均不存在，需重建或改 `--input-root`。
5. **drama 与 H3 之间无官方装配层** —— drama 交 Markdown，H3 要 `timeline_data` JSON；目前由工作区自制 `csv_to_timeline.py` 承担。
6. **continuity_group 是工作区自制字段** —— drama 现役版 `分镜.csv` 只有 `export_frames/音色/验收基线/refs`，连续组需按 `shot-handoff.md` 人工划分。
7. **09 NG 版不可用** —— 需 ComfyUI ≥ 0.37，本机 0.30.2；且 `+ Figure from a sheet` 本就要求先有角色板。
8. **官方格式版本差异** —— `minimax-h3.md:104-116`（2026-11-16 核对）要求 `summary` 带 `[keyframe completion]` / `[reference generation]` / `[audio reference]` 之类任务类型前缀；EP001 出片工作流的实战模板未带前缀但已跑通。追求格式合规可加，不影响现有链路。

### 6.1 现成的同构开源程序（2026-11-18 核实）

文档第 9 节列的项目多数真实存在，其中 **`infinite-creation`（`github.com/SwotAtmk/infinite-creation`，MIT）几乎就是本手册整条生产线的现成工业级实现**：

```
小说/剧本 → 剧本 + 大纲 → 人物圣经(bible) + 风格指南(style)【一致性锚点】
→ 人物/场景/道具/语音资产（Qwen-Image 2.1 文生图·图生图 + Qwen3-TTS）
→ 分镜脚本 → 逐镜视频（MiniMax H3 Ref2VA：参考图 + 参考音 → 带语音视频）
→ 自审重试 → ffmpeg 合并成片
```

- **与本链路的对应**：`人物圣经／风格指南` = N3 的视觉设定；`canonical 参考图跨镜复用` = N4 的板 + `<Picture 2/3/4>` 全片固定；`MiniMax H3 Ref2VA` = N12 的 r2v 出片；**`Qwen-Image 2.1 文生图/图生图` 正好补上 N4「本地无现成文生图工作流」这个缺口**。
- 内置 27 个 `SKILL.md`，约一半是中文漫剧／短剧技能，含 `h3-prompt-writing`。本机 `C:\Users\Administrator\.workbuddy\skills\h3-prompt-writing\SKILL.md` frontmatter 写明 `author: MiniMax`、`version 1.0.0`，覆盖 T2VA／I2VA／FL2VA／L2VA／Ref2VA 六段式，与本手册 0.2 的 r2v 定线同源。
- 工程能力：断点续跑、分镜级审查／单镜重生成、项目隔离、显存维护、在线预览。参考硬件 RTX 3080（20GB），README 称 8GB 显存可跑；本机 ComfyUI 0.30.2 需确认是否满足其要求。

其余已核实项目（可作组件或替代方案）：

| 项目 | 核实状态 | 与本链路的关系 |
|---|---|---|
| `Nomi`（`github.com/aqm857886159/Nomi`，AGPL-3.0，v0.24） | 真实 | 本地优先工作台：**一镜一行**分镜表（prompt／首帧／模型／时长）、参考卡锁角色、可接**本地 ComfyUI**、MCP 24 工具；相当于 `shotlist.csv` + 装配层的 GUI 版 |
| `AIComicBuilder`（`twwch/AIComicBuilder`，Apache-2.0，约 2k stars） | 真实 | 剧本 → 角色四视图 → 智能分镜 → 逐镜首尾帧 → 视频插帧 → FFmpeg；底层调 Seedance／可灵／Veo，**非 H3** |
| `Jellyfish`（Forget-C，Apache-2.0） | 真实 | 竖屏短剧六步流水线；三栏分镜编辑器支持首／尾帧独立提示词 |
| `story-to-handdrawn-video`（`gnipbao`，MIT，约 2.3k stars） | 真实 | Remotion + 327 风格资产，**参考图保持系列视觉语言不漂移**；输出 3:4 手绘翻页 MP4，属代码渲染路线 |
| `vibe-video`（`buerivan`）、`vibe-video-generator`（`harshil1712`）、awesomeskills `vibe-video` skill | 真实 | 文档第 2 节描述的「代码 → 逐帧渲染 → FFmpeg」程序／Skill，产出氛围／知识短片 |
| `motion-kit`／`agent-storyboard`／`ArcReel`／`openvideo-studio`／`open-source-video-gen-skill`／`Vibe Video (VS Code)`／`animdsl` | **未逐一核实** | 文档第 9/10 节提及，本轮检索未直接命中，采用前需自行验证 |

**文档自身的两处小出入**：① 第 153／254 行称 drama-skills 是「12 个技能」，本地现役版实证为 **11 个 skill**；② 第 11 节结论「Vibe 视频不是 ComfyUI」只对代码渲染路线成立，但第 9 节把 ComfyUI + MiniMax H3 的 `infinite-creation` 也列进「Vibe 工具」——说明文档里的 Vibe 是**伞状范式标签**，不是单一程序名。

**给本链路的判断**：若目标是「自己可控、逐镜可审、沿用 drama 五份 Markdown + H3 r2v」，继续按本手册走；若目标是「尽快全自动出片、接受换一套工程」，优先评估 `infinite-creation`（同构度最高）或 `Nomi`（只替换资产与装配层）。二者可混用：用 `infinite-creation` 的 Qwen-Image 2.1 出板补 N4，N5／N9 仍用本手册的表驱动装配。

### 6.2 「生成漫画 → H3 导演台」是不是另一条流程（据上传文档复核）

**结论：流程骨架相同，差异不在先后顺序，而在「漫画」的形态与「谁做图生视频」。** 文档里的「生成漫画」实际指向三种终点，只有第一类与 H3 相接：

| 终点 | 文档里的项目 | 产出物 | 与 H3 的关系 |
|---|---|---|---|
| ① 出**静帧／首尾帧**再图生视频 | `infinite-creation`（Qwen-Image 2.1 → **MiniMax H3 Ref2VA**）、`AIComicBuilder` 角色四视图＋逐镜首尾帧、`Jellyfish` 首/尾帧提示词、`Nomi` 一镜一行的「首帧」、`agent-storyboard` 逐镜生成图片 | 每镜 PNG／首尾帧 | **与 N4→N5→N9→N12 同一位置**；`infinite-creation` 就是本手册整条链路的现成实现 |
| ② 出**动态漫画 MP4**（代码渲染） | `vibe-video` 系列、Remotion／`motion-kit`、`story-to-handdrawn-video` 终产物 | MP4 成片 | **与 H3 并列／替代**，不是上游；文档第 11 节「不是 ComfyUI」只针对这一类 |
| ③ 一体化流水线**自带视频模型** | `AIComicBuilder`／`Jellyfish` 完整流程（调 Seedance／可灵／Veo、烧录字幕） | MP4 成片 | **H3 被替换掉**，不再有 `<Picture N>` 与 `timeline_data` |

→ 文档第 11 节「Vibe 视频不是 ComfyUI」与第 9 节把 `infinite-creation`（ComfyUI + MiniMax H3）列为「Vibe 工具」自相矛盾；用户所指的「生成漫画再给 H3」正是第 9 节这条，**它与本手册不不同，是同一条流程的现成实现**。

**但「漫画」不能直接填 `<Picture 1>`，中间必须补一道转换层**（这是唯一实质差异）：

| # | 漫画常见形态 | H3 `<Picture 1>` 契约 | 不处理的后果 |
|---|---|---|---|
| 1 | 整页／条漫／多格绘本 | 每镜**一张**独立起始帧 | 一页多格被当成一格放大，分格线忠实保留 |
| 2 | 竖版／页面比例（`story-to-handdrawn-video` 为 3:4） | 16:9、≥1344 宽 | 非 16:9 被裁切，构图丢失 |
| 3 | 对白气泡、手写体字幕、拟声词、logo | 画面**无任何文字** | 被忠实放大，且与 H3 音频层台词重复 |
| 4 | 角色 Sheet／风格锚／图层部件**内嵌在程序里** | 导出成独立文件挂 `refs` 的 `<Picture 2/3/4>`，**全片固定** | 只留在程序图层里，H3 拿不到像素锚 → 跨镜变脸 |
| 5 | 后期配音／烧录字幕 | 对白镜 `refAudios` + 段尾 `Audio: reference` + 25step | 文档工具多不带音色层，接 H3 需另补 N6 |

**真正的分野是「解耦 vs 内聚」，不是先后**：一体化工具把出图、分镜、图生视频、字幕、合成打包在一个程序里，甚至自带视频模型，drama 的逐镜控制与 `shotlist.csv` 的可重跑性会被它的「智能分镜」接管；本手册把出图与渲染解耦，drama 五份 Markdown／CSV 是唯一真源，出图工具可换，H3 只吃 `timeline_data`。**只借这些工具的「出图／角色资产」半段、后半段仍走 N9 装配 + H3，流程与本手册完全一致**；整套交给它们则等于换工程，H3 导演台被替换。

**落地判断**：想少写代码且保留 H3 → 用 `Nomi`（一镜一行 + 首帧 + 可接本地 ComfyUI）出帧，首帧当 `<Picture 1>`，三张板与音色按 N4／N6 补齐；想全自动 → `infinite-creation` 整条替代（先确认本机 ComfyUI 0.30.2 是否满足）。两者都不改变「先有板、后有帧、板全片固定、帧每镜换」这条输入结构。

---

## 附录 A · 证据索引

| 结论 | 文件与位置 |
|---|---|
| novelist 产物与三段式角色板 | `chinese-novelist-skill-master/SKILL.md:173-179,329-341`；`references/visual-settings-mapping.md:8-20,46-53` |
| drama 路由与五份 Markdown | `drama-skills-main/drama-skills-main/skills/short-drama/SKILL.md:13-31` |
| 分镜逐镜字段 / 17n / 镜型 | `skills/short-drama-storyboard/SKILL.md:53,135-154,179-203` |
| REF-/PLAN- 用途九词 | `skills/short-drama/references/reference-roles.md:17-30` |
| H3 模式表 / 六段式 / 顺序→Picture N | `skills/short-drama-video-prompts/references/minimax-h3.md:66-84,90-100,104-116,120-139` |
| 一致性必须传同一图片文件 | `docs/comic-drama-workflow.md:155`；`references/storyboard-sheet-recipe.md:3-5,26` |
| drama 不出图 | `skills/short-drama-image-prompts/SKILL.md:3,9-11,77-78`；`skills/short-drama/SKILL.md:57-60` |
| 外部出图 C/S/P 块 | `skills/short-drama-image-prompts/references/asset-export-blocks.md:3-5,37-40,52,54-58` |
| 8 种画风基底 | `skills/short-drama-storyboard/references/comic-keyframe-lexicon.md:48-67,119` |
| 槽位固定化教训 | `12-H3提示词-官方指南/README.md:83,102,107-109,113` |
| 4step 语音崩坏 / 三档节奏 | `工作流/02-H3漫剧流程/README.md` 二、三节 |
| FL2VA 只有 lock | `工作流/09-H3导演台-NG版/_上游文档/docs/NG-shot-audio.md:46` |
| Qwen 需先有 character sheet | `工作流/09-H3导演台-NG版/_上游文档/GUIDE.md:617-620,634-636` |
| 09 NG 需 ComfyUI ≥ 0.37 | `工作流/09-H3导演台-NG版/README.md:27` |
| EP001 出片工作流由通用02 填充生成、勿当模板复用 | 6 个 `H3-EP001-出片-*.json` 内 `MarkdownNote` 便签（S004 为 node 16）；通用02 与 S004 拓扑参数比对见 N0 |

## 附录 B · 已交付文件（工作区根目录）

| 文件 | 作用 |
|---|---|
| `H3-vibe-生产线操作手册.md` | 本文档 |
| `csv_to_timeline.py` | CSV → `timeline_data` 装配器（含 `--check-only` 体检） |
| `shotlist_vibe_template.csv` | 19 字段分镜表模板，含 S004 对白镜 / S006 静默镜示例 |
| `out/H3-vibe-EP001-G01.json` | 实跑装配产物（底座通用02）：2 段 / 248 帧 / 10.333s，节点 13 连线 11；尺寸已同步 1344×768、SaveVideo 前缀 `video/H3-vibe-EP001-G01`、`continuityEnabled=True` |
