# MERGE MANIFEST — chinese-novelist 融合版

- 融合日期：2026-11-22
- 策略：**本地优先 + git 增量**（用户确认）
- 骨架：本地最新版并集 = 工作台加载版（11-19，SKILL.md 27319）∪ D 盘备份版（11-21 扩写），32 文件
- 增量：上游 git v2.3.2 独有 28 文件（`references/flows/`、`references/guides/`、`.mjs` 脚本等）全部补入
- 同名冲突 3 项：**一律保留本地版**
- 噪音过滤 9 项，原始快照中仍保留
- 融合版文件总数：60（另含本 manifest）
- 注意：本地 8 问流程与 git 三层问答为两套架构，此处并置共存，主 SKILL.md 走本地 8 问流程

## 回退 / 取用（绝对路径）
- 工作台加载版：`C:/Users/Administrator/.workbuddy/skills/chinese-novelist/`（未改动）
- D 盘本地备份版：`D:/AIShortDrama/3_漫剧SKILLS/1_剧本/1_主SKILLS/chinese-novelist-skill-master.backup-v1-20261121/`
- git v2.3.2 纯净快照：`D:/AIShortDrama/3_漫剧SKILLS/1_剧本/1_主SKILLS/_git_v2.3.2_纯净快照_20261122/`
- 全量差异与集成清单：`D:/AIShortDrama/3_漫剧SKILLS/SKILLS融合报告_20261122.md`
