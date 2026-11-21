# 08-H3-FunControlNetUnion · 武打动作迁移 + 全自动出片

把参考武打片的动作 1:1 搬进自己的场景。本目录 = 工作流 + 切片脚本 + 全自动驱动器。

## 文件清单

| 文件 | 作用 |
|---|---|
| `H3-FunControlNetUnion-动作迁移-r2v-25step-1344x768.json` | 手动工作流（ComfyUI 直接打开） |
| `detect_action_cuts.py` | **切点自动检测**：参考片 → 候选动作段（时间码已算好） |
| `make_action_clips.py` | 切片脚本：参考片 → 对齐 H3 约束的动作单元 |
| `auto_fight_pipeline.py` | 全自动驱动器：切片→改参→提交→监控→拼接 |
| `shots.template.csv` | 出片任务清单模板（按镜一行） |

## 新片入库流程：检测 → 审 → 切

```bash
# 1. 自动检测切点，出候选清单（几十秒，不用 GPU）
python detect_action_cuts.py --src "D:/参考/武打片B.mp4"
#    → candidates.csv（label 预填 候选NN，orient 待填）
#    → candidates.md（逐段运动强度：高/中/低，低密度段可直接删）

# 2. 人工审：删不要的行、填动作名和朝向、需要变形填 fx
#    这一步机器做不了：动作叫什么、朝哪边、哪招好看

# 3. 切片入库
python make_action_clips.py --src "D:/参考/武打片B.mp4" \
    --cuts candidates.csv --out "D:/剧本及分镜/动作素材库"
```

检测原理（纯 ffmpeg + numpy，无 AI 模型）：

| 手段 | 作用 |
|---|---|
| `scdet` 滤镜 | 检测镜头切换点（硬剪辑点） |
| 8fps 灰度帧差 | 运动强度曲线，找动作起落的“谷底” |
| 递归二分 | 超 6 秒的段在运动谷底再切，直到全部合规 |
| 顺序吸附 | 每段对齐 17n+5 帧网格，相邻段绝不重叠 |

参数：`--thresh`（默认 12，越小越敏感）、`--min-len 1.0`、`--max-len 6.0`、`--min-frames 22`。
实测 34s 打斗片出 11 段候选，硬切点（9.61s / 32.56s）全部命中，段长均在 2~6 秒。

## 全自动用法

1. 编辑 `shots.csv`（复制 template 改名），每行一镜：

```
shot,clip,scene,identity,prompt
1,拔刀突进,EP001/场景板.png,EP001/身份板.png,"正向提示词…"          ← 短标签
2,AUTO:D:/某参考片.mp4|12.0|15.5|mirror|侧面|格挡,…,"…"            ← 现场切片
3,ACT003_后仰蹬腿_侧面_20-22.6s_124f_speed0.5.mp4,…,"…"           ← 完整文件名
```

- `clip` 三种写法（按 通用库 → 项目库 顺序检索）：
  - **短标签**（推荐）：`拔刀突进`、`ACT003`——唯一匹配即通过，有歧义会报错列出候选
  - **完整文件名**：精确无损
  - **AUTO 现场切片**：`AUTO:源片|起秒|止秒|fx|朝向|动作名`，库中已有同名动作则直接复用，
    没有才切，切完**自动入通用库沉淀**（全项目共享）
- `scene/identity` 是 ComfyUI `input/` 下的相对路径
- prompt 用 `<Picture 1>`（身份板）`<Picture 2>`（场景板）引用，结尾带 `Audio: none` 或音频指令

2. 三种模式：

```
python auto_fight_pipeline.py --jobs shots.csv --mode dry        # 干跑：出计划+补丁后工作流，不提交
python auto_fight_pipeline.py --jobs shots.csv --mode validate   # 校验：服务端验图，报告缺节点/模型
python auto_fight_pipeline.py --jobs shots.csv --mode run        # 正式：逐镜出片+自动拼接
python auto_fight_pipeline.py --jobs shots.csv --mode run --only 2,3   # 只跑指定镜
```

`run` 模式逐镜产出 `<前缀>_<镜号>.mp4`（前缀默认 EP001，`--prefix` 可改）到输出目录，
最后 ffmpeg concat 成 `<前缀>_打斗段_全自动.mp4`（同参数录制，stream copy 无损拼接）。

## 动作素材库：两级结构

| 库 | 路径 | 定位 |
|---|---|---|
| **通用库** | `D:\剧本及分镜\动作素材库\` | 全项目共享的动作单元，AUTO 现切的切片默认入这里沉淀 |
| 项目库 | `D:\剧本及分镜\一剑问天\…\EP001\动作素材库\` | 本项目专用切片（原库保留不动） |

检索顺序：通用库 → 项目库；同文件名两库都有副本时按文件名去重不冲突。
其他剧集（EP002、别的小说项目）直接写短标签调用通用库，无需配置。
切片自动对齐：帧数 17n+5 网格 / 分辨率 32 倍数（≤1344×768 框）/ 24fps 无音轨；
每个文件名自带 `朝向_起止秒_帧数_变形` 标记，用于对齐该镜场景板机位。

## 前置条件（升级前 run/validate 会报缺节点，属预期）

- ComfyUI ≥ 0.33（MiniMaxH3FunControlNetApply + SDPose 子图）
- `minimax_h3_fun_controlnet_union(_2.0)_pruned_int8_convrot.safetensors` → `models/model_patches/`
- ComfyUI 服务在 8188 端口运行

## 切片脚本单独用

```
python make_action_clips.py --src <参考武打片.mp4> --cuts cuts.csv --out <素材库目录>
```

切片自动对齐：帧数 17n+5 网格 / 分辨率 32 倍数（≤1344×768 框）/ 24fps 无音轨。
cuts.csv 列：`label,orient,start,end,fx`，fx 可组合 `mirror` / `speed:0.5` / `reverse`。
素材库在 `D:\剧本及分镜\一剑问天\分镜\剧集\EP001\动作素材库\`（含索引.csv）。

## 常见坑

1. 朝向拧：切片的朝向标记必须和该镜场景板机位一致
2. 画面僵硬：控制强度降 0.7~0.8；sigma_end 收到 0.6 释放细节
3. 改时长去改切片，不要改 PrimitiveFloat（它会自动按切片时长填）
4. 拼接要求所有镜同分辨率同帧率——都从同一模板出片天然满足
