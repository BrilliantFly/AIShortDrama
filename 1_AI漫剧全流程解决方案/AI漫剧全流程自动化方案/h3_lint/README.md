# h3_lint — drama → tudou H3 契约校验工具集

## 定位
这是「校验视图」工具集，不是生产提示词生成器。经验库 30.4/30.5 记录了完整根因。

**关键事实**：drama 产出的 `视频提示词.md` 与 tudou lint 是**两套契约**：
- drama：中文用「」直引台词（本机 Qwen3-VL 方言，经验库 11.5 已验证 `<d>` 会让台词不落地）
- tudou lint：要求 HTML 双提示词表，中文块 `中文审稿版｜H3-XXX｜N秒` + 英文六段 + `<d>[zh]` + `<Subject>/<Audio>` 绑定 + boundary

桥接器 `md_to_h3_lint.py` 把 drama 的 md 转成 lint 可审的 HTML，**只做安全对齐**（retention 拆行、Subject/Audio 定义补齐、台词字数按 lint 口径计算），不改台词语义。生成的 HTML 仅用于校验，不可当生产提示词。

## 文件
- `md_to_h3_lint.py` — 桥接器（本次新增）
- `h3_prompt_lint.py` / `h3_unit_lint.py` — 两个主校验器
- `h3_regression_tests.py` — lint 自检（回归测试）
- 其余 8 个 — upload order / boundary contact sheet / storyboard preview / manifest 等辅助校验
- 以上从 `99_参考\SKILLS\tudou-shotlist-builder\scripts\` 同步，**原版未改动**（源路径 2026-11-25 由 `99_参考` 改名重组为 `99_参考`）
- `check_camera_landing.py` — 新增·运镜落地门禁：诊断缓推 vs 提示词 no push、半身景别、道具尺度（经验库 31）
- `check_castset_slot.py` — 新增·四层事实源门禁：CAST+SET 继承、四槽顺序、`[Shot N]` 镜号；**镜型分档（2026-11-25）**：DUO 镜判全身露脚，SOLO/OTS 反应镜豁免半身（允许特写）。镜型来源优先级：提示词块内 `镜型：` > `--solo-shots 2,4` > `--storyboard 分镜.md` 解析 > 默认按 DUO 保守判
- `check_delivery_media.py` — 新增·成片交付门禁：段数/分辨率/码率/尾段误交（ffprobe 可选）
- `check_prompt_content.py` / `check_segment_length.py` — CSV 层门禁：镜号/空模板 + 段长/17n 网格
- `check_review_report.py` — 审片痕迹门禁：查各档位（preview/final/delivery）审片报告是否落盘，防漏审片
- `run_quality_chain.py` — **质量链统一编排器**：数据驱动按阶段串跑上面所有门禁（见下）

## 用法

### 推荐：一键编排器（可扩展、跨机）
```bash
python h3_lint/run_quality_chain.py --list     # 列出全部编排项
python h3_lint/run_quality_chain.py --stage n2 --project-root <剧集目录> --expect-shots 5 \
  --drama-root <资料库根>/3_漫剧SKILLS/2_分镜/1_主SKILLS/drama-skills-main/drama-skills-main/skills/short-drama-storyboard/scripts
python h3_lint/run_quality_chain.py --stage csv --project-root <项目根> --csv shotlist.csv
python h3_lint/run_quality_chain.py --stage delivery --seg 'out/seg_*.mp4' --archive out/整片.mp4 \
  --expect 5 --review-dir 生产线/out --review-expect preview,final
# --stage all：能跑的跑，缺参数的门禁 SKIP（不算 FAIL）
```
加门禁 = 在脚本顶部 `GATES` 加一条 dict；Skill 调用无 CLI，不在本脚本内，见手册 2.x 编排表。

### 单条门禁（排障用）
```bash
# 【防忘门禁·先跑】检查导演运镜诊断是否做了（漏做→RC=1→交不了 N3）
python h3_lint/check_n2_skills.py "<项目根>/分镜/分镜.md" --expect-shots 5

# 【第4重·跨层门禁】诊断有没有落进提示词 + 全身景别 + CAST+SET（经验库 31）
python h3_lint/check_camera_landing.py "<项目根>/分镜/分镜.md" "<项目根>/分镜/视频提示词.md"
python h3_lint/check_castset_slot.py "<项目根>/分镜/视频提示词.md" --expect-shots 5 --storyboard "<项目根>/分镜/分镜.md"
#   SOLO 特写镜豁免：分镜标 `镜型：SOLO`（或临时 --solo-shots 2,4）；DUO 镜仍判全身

# 【成片门禁】段数/规格/尾段误交（ffprobe 不在 PATH 时用 --ffprobe 指定）
python h3_lint/check_delivery_media.py out/seg_*.mp4 --archive out/整片.mp4 --expect 5

# 生成校验视图 HTML + 直接跑两个 lint（推荐）
python h3_lint/md_to_h3_lint.py "<项目根>/分镜/视频提示词.md" \
  -o "<项目根>/out/视频提示词_lint视图.html" --lint

# 单独复跑
python h3_lint/h3_prompt_lint.py out/视频提示词_lint视图.html
python h3_lint/h3_unit_lint.py  out/视频提示词_lint视图.html

# 校验器自检（确认 lint 本身没坏）
python h3_lint/h3_regression_tests.py
```

## 实测结果（2026-11-24，EP001 5 镜）
- T1 回归自检：PASS
- T2 桥接后 `h3_prompt_lint.py`：**PASS**（5 paired units）
- T2 桥接后 `h3_unit_lint.py`：**PASS**（5 units，字数 0/4/22/20/0 全部匹配）

## 维护约定
- 上游 `99_参考\SKILLS\tudou-shotlist-builder\scripts\` 更新时，同步到本目录并复核桥接器
- 三 skill 分工协议（经验库 29 章）的 N2 第 4 步调用的就是本目录工具
- 真实内容问题（如台词字数超 40 硬限、density warning）由 lint 报出，不得通过改桥接器掩盖
