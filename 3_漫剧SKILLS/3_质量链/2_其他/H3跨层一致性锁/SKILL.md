---
name: H3跨层一致性锁
description: 检查「分镜诊断 → 视频提示词 → CSV → 装配 JSON」四层是否单一事实源一致，锁住运镜意图落地、全身露脚景别、CAST+SET 继承、四槽顺序与 global/段级分工。用户说「跨层一致性」「提示词和分镜对不上」「装配丢细节」「全身露脚」「CAST+SET」「N2 到 N7 别漏东西」时用。只定位不一致并给回写要求，不改剧本与分镜职责。
agent_created: true
---

# H3 跨层一致性锁

> 知识型 Skill（无 CLI）。在 N2 写完提示词后、N7 装配前由 Agent 主动调用；也是「完美视频」提升点的统一收口处。
> 依据：经验库第 18 章（CSV 装配信息丢失）、13.3/11.8（起始帧 CAST+SET）、30.7/30.9（运镜诊断正交）、31 章（本次体检）。

## 一、要解决的根因（一句话）

**写对了不等于用上了。** 办公室 15 镜实测：视频提示词.md 写好了身份与几何，CSV 装配层却掏空成 `on-screen speaker` / `office scene plate`，90 处 `[Shot N]` 全变 `[Shot 1]`；EP001 实测：出图工作流已修成全身露脚，分镜和提示词里仍留着「胸上 / waist-up」。两层各写各的，就是返工来源。

## 二、四层事实源与允许改的字段

| 层 | 文件 | 权威内容 | 谁负责 |
|---|---|---|---|
| ① 分镜诊断 | `分镜.md`【导演运镜诊断】 | 情绪、镜内可变项（焦点/光/缓推）、落点锚 | 导演运镜 Skill |
| ② 提示词 | `视频提示词.md` 六段式 | 镜头句、动作、台词、声音、全身景别 | drama video-prompts + 本 Skill 回写 |
| ③ 装配中间 | `shotlist.csv` 六列 | 逐字复制②，不改不简化 | csv_to_timeline.py |
| ④ 出片 JSON | `H3-*.json` timeline_data | 由③装配，段 prompt 与 refs 对齐 | 门禁校验 |

**铁律**：②是唯一事实源。③必须逐字来自②；④必须逐字来自③。禁止在③④里"顺手简化"或"通用模板化"。

## 三、五道锁（逐条查）

1. **运镜落地锁**：每镜诊断写「缓推/极缓推」的，提示词 `detailed_description` 必须有 `slow push / dolly in` 镜头句；诊断写「固定/彻底固定」的，提示词必须明写 `no push / camera locked`。二者矛盾即 FAIL。
2. **景别锁**：全片统一 `full-body wide two-shot, head to shoes visible, terrazzo floor underfoot`，禁 `胸上 / 腰部以上 / chest-up / waist-up / upper body shot`。起始帧图已是全身，文字半身会直接把构图拉回半身。
3. **CAST+SET 继承锁**：每张起始帧 prompt 与每段 `subject_definitions` 必须自带逐字复用的 CAST（性别/年龄/发型/服装）+ SET（场景板几何与光向），不能只写动作。四槽顺序固定：`<Picture 1>` 起始帧 / `2` 说话人板 / `3` 场景板 / `4` 双人身份站位板。
4. **镜号与槽位锁**：`[Shot N]` 的 N 必须等于该段镜号；`refAudios` 恒 0 基；`Audio: reference / fully_copy / none` 三路路由与台词归属一致。
5. **global/段级分工锁**：`global.prompt` 只写**场景几何**（同场景同一空间），不写机位与站位；站位/动作只写段级 `detailed_description`，避免全局锚压平镜间差异。

## 四、脚本门禁

```bash
python h3_lint/check_camera_landing.py 分镜/分镜.md 分镜/视频提示词.md
python h3_lint/check_castset_slot.py 分镜/视频提示词.md --expect-shots 5
python csv_to_timeline.py --check-only --strict-assets
python <drama>/storyboard_lint.py 分镜.md --csv 分镜.csv
python h3_lint/md_to_h3_lint.py 分镜/视频提示词.md -o out/视频提示词_lint视图.html --lint
```

`check_camera_landing.py` 抓 ①⑤ 冲突；`check_castset_slot.py` 抓 ②③④ 缺项；后三个是既有门禁。全部 PASS 才算 N2→N7 一致性闭环。

## 五、回写纪律（重要）

- 只**新增或修正提示词层字段**，不改剧本、不分镜职责、不冻结关键帧、不改时长。
- 每次回写前备份 `.bak-<日期>`；回写后重跑四层门禁，禁止只改一处不校验下游。
- 若一致性修复需要动工作流结构（i2v / 首尾帧锁 / global 场景锁默认化），按项目规定走 `2_工作流` 权威库 → `工作流底座` → GUI 副本的顺序，禁止反向或直接改底座。

## 六、与其它技能的分工

| 技能 | 分工 |
|---|---|
| `导演运镜与机位构图` | 产出诊断；本 Skill 保证诊断进提示词 |
| `H3成片质量审片` | 出片后媒体层验收；本 Skill 是出片前文本层防控 |
| `short-drama-review` | 通用跨环节审查；本 Skill 只管 H3 四层事实源 |
