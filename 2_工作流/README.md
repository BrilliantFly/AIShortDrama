# workflows-v2 · ComfyUI 工作流精选库

从 `ComfyUI/user/default/workflows`（54 个）筛选而来：**同一条迭代线只留最优，不同用途全部保留**。

生成时间：2026-11-04（同日完成命名规范化）；2026-11-15 完成重复检测与清理，详见本目录 `工作流分析与重复检测-2026-11-15.md`。

## 〇·一、权威目录与同步规则（2026-11-15 起）

- **权威（主）目录：本文件夹 `D:/AIShortDrama/2_工作流/`** —— 改工作流只改这里（根目录名末尾含零宽字符 U+200C，脚本请用 `os.listdir` 前缀匹配）。
- **同步副本：`D:/ComfyUI-aki-v3.2/ComfyUI/user/default/workflows/`** —— 仅供 GUI 侧边栏直接打开，单向从资料库复制，**不要只在 GUI 侧改**（改完记得拷回来）。
- 通用三件套在「现役库 / 主干 `工作流底座/` / GUI / `归档/`」四处 MD5 一致（2026-11-21 核验）；`归档/` 内的文件不进 GUI 目录。原「29/29 完全同步」为 2026-11-15 历史统计。
- **项目卡归属（用户规定，强制 · 2026-11-22）**：规定原文——「项目卡工作流放在5漫剧里面，项目生成的工作流放5漫剧（不包括底座工作流），除非新增、修改工作流，不然一般02工作流一般不变。」即：项目/剧集专属工作流（如 `H3-EP001-出片-*`）一律放 `D:/AIShortDrama/5_漫剧/<项目名>/工作流/`；`2_工作流/02-漫剧/02-H3漫剧流程/` 只放通用工作流（通用01~04），**仅在新增或修改通用工作流时才改动**；底座工作流（`1_AI漫剧全流程解决方案/AI漫剧全流程自动化方案/工作流底座/` 下的通用卡）不迁，仍在原处供装配器默认读取。GUI 中项目卡副本迁到 `.../workflows/05-项目卡-<项目名>/`，不与通用卡混放。
- 清理移走的文件在 `D:/AIShortDrama/2_工作流/归档/_备份-2026-11-15/`（保留原目录结构）。原 `D:\ComfyUI资产\_备份-2026-11-15\` 为历史路径、已失效。

当前收录：**29 个工作流 + 2 个归档件**（2026-11-15：对白原声归档、两个 GUI 临时件移入备份、项目流程与通用合并为「漫剧」）。原 54 个里被淘汰的 22 个仍在 ComfyUI 目录原处，随时可取。

## 〇、命名规范

- **文件名范式：`模型-技术/用途-关键参数.json`**。模型标识统一为：`H3`（MiniMax H3）、`QwenEdit`、`ZImageTurbo`、`IndexTTS2`；技术名保留英文原词（如 `Multiframe参考`），不要意译成中文。
- 带旧前缀 `minimax_h3_director_*` / `video_minimax_h3_*` 的文件本身已含模型名，保持原名未改。
- 顶层结构（2026-11-15 起）：**01-基础源**（模板与专用线备份）→ **02-漫剧**（分镜图片 + H3漫剧流程，日常只看这里）。

## 一、主力工作流

**日常成片主力就是 `02-漫剧\02-H3漫剧流程\` 的通用三件套**（01 快出预览 → 02 高清主线·参考音色对白 → 03 二采精修，详见其内 README）；
分镜图片在 `02-漫剧/01-分镜图片/`：**2026-11-21 二次重组后，后续出图实际用 7 个工作流，全部平铺在根下并统一命名**——`01`~`03` 为 N4 角色板 / 三视图出图链（模型自行下载），`04`~`07` 为场景板 / 道具板 / 人像正侧板卡；5 个原版板卡原件移入 `_原版卡备份/`（未删除、可回退）。详见 `01-分镜图片/README.md` 与 `N4出图链-使用说明.md`。
EP001 原始时间线版（`EP001-ma-ch01-hd` / `EP001-ma-ch01-12step` 等）未收入本库，
仍留在 `ComfyUI\user\default\workflows\MiniMax H3 导演台\`，参数规格如下，供对照：

| 项 | 值 |
|---|---|
| 任务类型 | r2v（参考主体生视频） |
| 采样 | 25 步 / cfg 1.0 / res_multistep + simple |
| 画布 | 1344×768（短边 = 原生 768） |
| LoRA | 不挂（4步蒸馏权重拆掉） |
| 时间线 | 8 段 / 1479 帧 / 61.6s，帧长全为 17 的倍数 |
| 段间引导 | continuity ON，overlap 22 帧 |
| 导出 | exportMode=segments |

时间线里是 8 镜完整第一章，实际出片只挑打斗 4 镜（seg_ma005~008）：
提交时传 `--shots 5,6,7,8`，脚本会把这 4 段重排成 765 帧 / 31.9s 的独立整轴。

### 多帧参考 Multiframe Reference（H3 · 武侠武打）

位置：`01-基础源/05-H3-Multiframe参考/`

| 文件 | 参数 | 用途 |
|---|---|---|
| `H3-Multiframe参考-武侠武打-25step-1344x768.json` | 25步 / 1344×768 / 不挂LoRA | 正式出片 |
| `H3-Multiframe参考-武侠武打-4step-864x480.json` | 4步 / 864×480 / turbo LoRA | 调关键帧时快速试 |

这套和上面的 Director 时间线是**两种范式**，别混着理解：

- Director 是「一个 prompt 管一段，段与段之间接力」；
- Multiframe 是「一条 5 秒镜头里，把 4 张关键姿态图钉死在第 0 / 31 / 62 / 93 帧」。

武打最怕的就是动作糊成一团、中间几帧不知道在干嘛。钉 4 个 keypose 等于给动作定了节拍：
第 0 帧起势对峙 → 第 31 帧兵刃相击 → 第 62 帧剑脱手钉竹 → 第 93 帧后仰蹬腿扫膝。
模型必须在这几个时刻对上画面，中间自然插值，动作就不可能散。

**节点结构**（和官方 video_minimax_h3_r2v 模板同源）：

```
UNETLoader ─► [turbo LoRA（仅快版）] ─► MiniMaxH3SigmaShift(12/3) ─► BasicScheduler / BasicGuider
CLIPLoader ─┐
① 身份板 ────┼─► MiniMaxH3ReferenceToVideo ──positive──► AddGuide(帧0) ─► AddGuide(31)
② 场景板 ────┘                                          ─► AddGuide(62) ─► AddGuide(93) ─► BasicGuider
                                    └──LATENT──► 四个 AddGuide 共用同一份 AV latent
```

**用之前要做的两件事**：

1. ComfyUI 升到 **0.33.0 以上**（推荐 0.36.0+）。
   `MiniMaxH3AddGuide` 是 0.33.0 才加的节点，本机 0.30.2 打开会看到它红框报缺失，其余节点都正常。
2. 换图：① 身份板、② 场景板、关键帧 1~4。关键帧必须是**同一侧机位、同一光位**下的姿态定格，
   否则模型会在中间帧硬切场景——这是这套玩法唯一的硬性要求。

**依赖的模型**（本机 D 盘已全部就位，换机器时按此目录放）：

| 文件 | 大小 | 放哪 |
|---|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 19.5 GB | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.6 GB | `models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | 4.85 GB | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | 577 MB | `models/vae/` |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.82 GB | `models/loras/`（仅快版用） |

**三条容易踩的**：

- 帧号 = 秒 × 24，124 帧 = 5 秒，合法帧号 0~123。**改时长必须同步改 4 个 AddGuide 的 frame_idx**，否则报帧越界。
- `<Picture 1>` / `<Picture 2>` 只指 ① 身份板和 ② 场景板；关键帧是时间轴锚点，**不进 Picture 编号**，prompt 里别引用。
- 起始构图（谁左谁右、面对面还是肩并肩）由**关键帧 1** 决定，prompt 压不过它。不满意就重画那张。

## 一·二、Fun ControlNet Union · 动作迁移（01-基础源/08-H3-FunControlNetUnion）

**`H3-FunControlNetUnion-动作迁移-r2v-25step-1344x768.json`** —— 照着一段参考武打片 1:1 复刻动作。
基于 ComfyUI 官方 `video_minimax_h3_fun_controlnet_union` 模板本地化：已挂身份板/场景板 LoadImage、
分辨率提到 1344×768、全量步数改 25、prompt 换成武打模板、附中文说明卡。

| 项 | 值 |
|---|---|
| 核心节点 | `ModelPatchLoader` → `MiniMaxH3FunControlNetApply`（升级后才有） |
| 控制补丁 | `minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors` → `models/model_patches/`（Kijai/MiniMax-H3-experimental；2.0 版 13.5G 注入块翻倍，跟随更紧） |
| 控制模式 | 一个 Union 权重通吃 Pose/Depth/Canny/HED/MLSD，喂什么视频就是什么控制，无需切档 |
| 姿态提取 | 内置 SDPose 全身子图（RT-DETRv4 检人 + 133 关键点），多人打斗自动分人提取 |
| 参考锁定 | 跑在 ref2va 之上，身份板/场景板照常锁人锁景，音频分支不受控制影响 |
| 速度开关 | 右下 Boolean：false=25步无LoRA高清（默认）；true=4步turbo快出 |

**与 Multiframe 的分工**：Multiframe 是「自己编排 4 个关键姿势定节拍」；FunControl 是「照参考片复刻动作」。
武打戏可组合用：FunControl 复刻参考片的招式轨迹，Multiframe 修正关键帧构图。

**用法三条**：① LoadVideo 换成武打参考片（分辨率 32 的倍数，时长决定出片时长，17n+5 帧网格自动换算）；② 两个 LoadImage 换成身份板/场景板；③ 控制强度默认 1.0，画面僵硬降到 0.7~0.8，sigma_end 收到 0.6 可在锁完动作后释放细节。

## 二、必须知道的坑

1. **整轴要一次提交**。`--shots 5,6,7,8` 一次传入，不要拆成 4 次单独提交 ——
   拆开后每段都是 index=0、prev_idx=-1，段间 latent 接力 100% 失效，接缝会明显跳。
   实测接缝 MAE 45.1 → 19.0（-58%）靠的就是整轴一次跑。
2. **exportMode=segments 时，Director 节点只输出最后一段**。整轴成片要自己把
   `output/minimax_seg_export/<时间戳>/seg_0000~000N.mp4` 拼起来。
3. **4 步蒸馏 LoRA 不要跑 12 步**。蒸馏权重跑非 4 步会被过平滑，这是"画面糊"的头号原因。
   要清晰度就拆 LoRA 走 25 步；要速度就 4 步配 4step 权重。
4. **中文负面词对 H3 基本无效**。negativePrompt 里堆"血/水印/模糊"不起作用，
   要靠起始帧和正向 prompt 解决。
5. **起始帧决定构图，prompt 压不过图**。要两人面对面就得起始帧本身侧身面对面；
   喂人物板时别塞多人并肩群像板，模型会把并肩关系一起带进画面。
6. **参考图是等权平均**。r2v 里"起始帧"只是 `<Picture 1>`，和三视图/场景板/道具板地位相同，
   不是硬性首帧约束。图挂得越多越容易串味，能少挂就少挂。
7. **prompt 完全一致会命中整图缓存**，出现"20 秒跑完但没有新文件"。改一个字就能打破。
8. **段间开头半秒模糊是设计行为**（opening grade 12f / blur=64 的调色过渡），不是 bug。
9. **fl2v 会清空音轨**：`segment_ref_audios_for_context` 只放行 r2v/rv2v，
   `resolve_audio_mode` 只对 v2v/rv2v/r2v 认 source。要保留原声和对口型，别用 fl2v。

## 三、目录说明

```
D:\ComfyUI资产\1-工作流\
├─ README.md                      ← 本文件
├─ 工作流分析与重复检测-2026-11-15.md  ← 重复检测报告 + 执行记录
├─ 02-漫剧\                        漫剧生产只看这里
│  ├─ 01-分镜图片\                ★ 后续出图现役 7 个（根下平铺，统一命名）
│  │  ├─ 01~03                     N4 角色板 / 三视图出图链（模型自行下载）
│  │  ├─ 04~07                     场景板 / 道具板 / 人像正侧板卡
│  │  └─ _原版卡备份\              5 个原版板卡原件 + 原出图链子目录（未删除）
│  └─ 02-H3漫剧流程\              通用三件套：01 快出预览 → 02 高清主线·参考音色对白 → 03 二采精修（+ README）
├─ 01-基础源\
│  ├─ 01-H3-导演台通用\            5 种 taskType 干净模板（r2v/rv2v/t2v/v2v/fl2v）+ external_groups 分组版 2 个
│  ├─ 02-H3-二采流水线\            二采_加速：首采 8 步 → 二采放大 1920×1088（旧版 v2v 二采已归档）
│  ├─ 03-H3-Continuum\            第三方插件工作流（V38X2 / V39 两分支，3 个）
│  ├─ 04-H3-官方模板\              ComfyUI 官方最基础 taskType 模板（3 个）
│  ├─ 05-H3-Multiframe参考\        Multiframe Reference 武打工作流（2 个，需 ComfyUI ≥ 0.33.0）
│  ├─ 06-QwenEdit-三视图\          角色参考板：ZImageTurbo 底板 → QwenEdit 换人 → 分段合成（3 个）
│  ├─ 07-IndexTTS2-音频\           IndexTTS2 声音克隆
│  └─ 08-H3-FunControlNetUnion\    Fun ControlNet Union 动作迁移 + 全自动驱动器（切片→提交→拼接）
└─ 归档\                          对白原声（source/TTS 直通路线，已弃用）+ 二采放大 schema v4 旧版，勿用
```

## 四、被淘汰的 22 个（仍在原目录）

- `EP001-36镜-对白版-4step.json` —— 对白版 v1，被同族 v2 取代
- `EP001-36镜-对白版v2-4step.json` —— 对白版 v2，被 EP001-v3-source-12step 取代（v3 改正了逐镜参考图挂载）
- `EP001-v3-source_t960-4step.json` —— 与 v3-source 同一时刻，仅 4步/960x544，画质低一档
- `EP001-v3-source_ch01-12step.json` —— 14镜旧时间线，被 ma 版 8 镜武指分镜取代
- `EP001-fight-ch01-12step.json` —— fight 版 8 镜，被 ma 版取代（ma 是它的武指重写）
- `minimax_h3_director_加速版.json` —— 10-18 原始版 20步/864x480，被「清理版」取代
- `minimax_h3_director_加速版_流水线v2v.json` —— 被同族「流水线v2v_二采放大」取代
- `三视图-卡通-v1.json` —— 卡通风格旧版，被电影 v3 取代
- `三视图-电影-v1.json` —— 电影 v1，被 v2/v3 取代
- `三视图-电影-v2-参考图版.json` —— v2 中间态
- `三视图-电影-v2-人脸锁定版.json` —— v2 中间态
- `三视图-电影-v2-人脸精修版.json` —— v2 中间态
- `三视图-电影-v2-合并版.json` —— v2 合并态，被 v3-分段合成版取代
- `三视图-诊断版.json` —— 排查用临时版
- `三视图-电影-v3-第一段-底板.json` —— v3 拆分单段，被分段合成版整体取代
- `三视图-电影-v3-第二段-换人.json` —— v3 拆分单段，被分段合成版整体取代
- `三视图-电影-v3-最终版.json` —— v3 单文件版，分段合成版更新
- `MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.json` —— 与 V38X2.json 字节完全相同（md5 一致），纯重复
- `MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Follow.json` —— V38X2 实验分支，V39 已并入
- `MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Repeat.json` —— V38X2 实验分支，V39 已并入
- `MiniMax_H3_Continuum_V39.json` —— 被 V39_Turbo_Sample / V39_Reference_Inline 覆盖
- `MiniMax_H3_Continuum_V38x.json` —— 更早版本，被 V38X2 取代

## 五、迁移提醒

工作流里的图片路径写的是 `EP001/xxx.png`，指向 `ComfyUI/input/` 目录。
换机器或清空 input 后，要先把素材同步进 `ComfyUI/input/EP001/`，否则加载会报缺图。
