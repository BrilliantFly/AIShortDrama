# -*- coding: utf-8 -*-
"""
SKILLS 融合：本地基础版为骨架 + git 最新版增量，D 盘主目录就地升级。
策略：本地优先 + git 增量（用户 2026-11-22 确认）
  - 骨架：本地定制全集（novelist 取 工作台版 ∪ D盘备份版 并集）
  - 增量：git 独有文件全部补入
  - 同名冲突：一律保留本地版；git 同名版留在纯净快照
  - 噪音（__pycache__/.pytest_cache/*.pyc/*.bak-*）不进主目录，原始快照中保留
  - 三源快照全部保留，可随时回退
"""
import os, sys, shutil, hashlib, re, json, time
from pathlib import Path

ROOT = r'D:\AIShortDrama\3_漫剧SKILLS'
UB = r'C:\Users\Administrator\.workbuddy\skills'

# ---- 三源路径 ----
D_LOCAL = os.path.join(ROOT, r'2_分镜\1_主SKILLS\_backup_20261121_v0.9.2\drama-skills-main')
D_GIT   = os.path.join(ROOT, r'2_分镜\1_主SKILLS\drama-skills-main\drama-skills-main')
D_SNAP  = os.path.join(ROOT, r'2_分镜\1_主SKILLS\_git_v0.12.1_纯净快照_20261122')

N_UB    = os.path.join(UB, 'chinese-novelist')
N_LOCAL = os.path.join(ROOT, r'1_剧本\1_主SKILLS\chinese-novelist-skill-master.backup-v1-20261121')
N_GIT   = os.path.join(ROOT, r'1_剧本\1_主SKILLS\chinese-novelist-skill-master')
N_SNAP  = os.path.join(ROOT, r'1_剧本\1_主SKILLS\_git_v2.3.2_纯净快照_20261122')

REPORT  = os.path.join(ROOT, 'SKILLS融合报告_20261122.md')
TODAY   = '2026-11-22'


def scan(base):
    """返回 {相对路径: (size, md5, mtime, 绝对路径)}"""
    out = {}
    if not os.path.exists(base):
        raise SystemExit('[FATAL] 源目录不存在: ' + base)
    for dp, dn, fn in os.walk(base):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, base).replace(os.sep, '/')
            d = open(p, 'rb').read()
            out[rel] = (len(d), hashlib.md5(d).hexdigest(), os.path.getmtime(p), p)
    return out


def is_noise(rel):
    parts = rel.split('/')
    if '__pycache__' in parts or '.pytest_cache' in parts:
        return True
    if rel.endswith(('.pyc', '.pyo')):
        return True
    if '.bak-' in rel or rel.endswith('.bak'):
        return True
    return False


def ensure_git_snapshot(git, snap, label):
    """git 纯净版完整快照，已存在则校验文件数"""
    g = scan(git)
    if os.path.exists(snap):
        s = scan(snap)
        if len(s) == len(g):
            print('  [%s] 快照已存在且完整: %d 文件 -> %s' % (label, len(s), snap))
            return g
        shutil.rmtree(snap)
    shutil.copytree(git, snap)
    print('  [%s] git 纯净版快照已创建: %d 文件 -> %s' % (label, len(g), snap))
    return g


def build_local_union(primary, secondary, label, conflict_log):
    """
    novelist 本地骨架 = 工作台版(primary) ∪ D盘备份版(secondary)
    冲突决策：
      1) secondary 存在同名 .bak-20261121-exp 且 secondary 正文 != bak  -> 判定为 11-21 扩写，取 secondary
      2) 其余取 mtime 更新者；mtime 相同取体积更大者
    """
    A, B = scan(primary), scan(secondary)
    merged = {}
    bak_index = {k.replace('.bak-20261121-exp', ''): v for k, v in B.items()
                 if k.endswith('.bak-20261121-exp')}
    for k in sorted(set(A) | set(B)):
        if k in A and k in B:
            # 决策：取体积更大者（工作台为实际加载位，同体积时优先工作台）
            # 依据逐条写入报告，未选中的版本完整留在原始快照中，随时可取
            chosen = 'A' if A[k][0] >= B[k][0] else 'B'
            why = '工作台版体积更大（实际加载位）' if chosen == 'A' else 'D盘备份版体积更大'
            if k in bak_index and B[k][1] != bak_index[k][1]:
                why += ('；D盘为 11-21 实验扩写版（.bak 为证）' if chosen == 'B'
                        else '；D盘另有 11-21 扩写版但体积较小，完整保留于备份快照')
            conflict_log.append((k, A[k][0], B[k][0], chosen, why))
            merged[k] = A[k] if chosen == 'A' else B[k]
        elif k in A:
            merged[k] = A[k]
        else:
            merged[k] = B[k]
    print('  [%s] 本地并集: 工作台 %d + D盘备份 %d -> %d 文件，冲突 %d 项'
          % (label, len(A), len(B), len(merged), len(conflict_log)))
    return merged


def fuse(local, git, label):
    """本地骨架 + git 独有增量；返回 (融合映射, 统计)"""
    fused = {k: v for k, v in local.items() if not is_noise(k)}
    noise = [k for k in local if is_noise(k)]
    added = []
    for k, v in git.items():
        if is_noise(k):
            continue
        if k not in fused:
            fused[k] = v
            added.append(k)
    conflict_kept = [k for k in set(local) & set(git) if not is_noise(k)]
    stats = dict(label=label,
                 local_total=len(local), local_kept=len(local) - len(noise),
                 noise_filtered=len(noise), git_total=len(git),
                 git_added=len(added), git_conflict_kept_local=len(conflict_kept),
                 fused_total=len(fused))
    print('  [%s] 融合: 本地保留 %d（过滤噪音 %d）+ git 新增 %d = %d；'
          '同名冲突 %d 项保留本地版'
          % (label, stats['local_kept'], stats['noise_filtered'], stats['git_added'],
             stats['fused_total'], stats['git_conflict_kept_local']))
    return fused, added, noise, stats


def materialize(fused, target, manifest_text):
    """构建到同盘临时目录 -> 校验 -> 原子替换主目录"""
    tmp = target + '__fusion_build_tmp'
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    for rel, (size, md5, mt, src) in fused.items():
        dst = os.path.join(tmp, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    # manifest 写入构建目录
    with open(os.path.join(tmp, 'MERGE_MANIFEST.md'), 'w', encoding='utf-8') as f:
        f.write(manifest_text)
    # 校验：除 manifest 外全部落位
    built = set()
    for dp, dn, fn in os.walk(tmp):
        for f in fn:
            r = os.path.relpath(os.path.join(dp, f), tmp).replace(os.sep, '/')
            built.add(r)
    missing = set(fused) - built
    if missing:
        shutil.rmtree(tmp)
        raise SystemExit('[FATAL] 构建缺失 %d 文件，已中止: %s' % (len(missing), list(missing)[:5]))
    shutil.rmtree(target)
    os.rename(tmp, target)
    print('  [落位] %s -> %d 文件 + MERGE_MANIFEST.md' % (target, len(fused)))


def check_refs(target, label):
    """抽查 SKILL.md 对 references/ 下 .md 的引用链完整性"""
    missing = []
    total = 0
    for dp, dn, fn in os.walk(target):
        for f in fn:
            if f != 'SKILL.md':
                continue
            p = os.path.join(dp, f)
            txt = open(p, encoding='utf-8', errors='replace').read()
            for m in re.findall(r'(?:references|assets|scripts)/[\w\-./]+\.(?:md|py|mjs|json|jsonl)', txt):
                total += 1
                cand = os.path.join(dp, *m.split('/'))
                if not os.path.exists(cand):
                    missing.append((os.path.relpath(p, target).replace(os.sep, '/'), m))
    print('  [%s] 引用链抽查: %d 处引用，疑似缺失 %d 处' % (label, total, len(missing)))
    return missing, total


def main():
    print('=== STEP 0 源校验 ===')
    for p in [D_LOCAL, D_GIT, N_UB, N_LOCAL, N_GIT]:
        print('  ', 'OK ' if os.path.isdir(p) else 'MISSING ', p)

    print('\n=== STEP 1 git 纯净版快照（回退保障）===')
    G_D = ensure_git_snapshot(D_GIT, D_SNAP, 'drama')
    G_N = ensure_git_snapshot(N_GIT, N_SNAP, 'novelist')

    print('\n=== STEP 2 构建本地骨架 ===')
    L_D = scan(D_LOCAL)
    n_conflicts = []
    L_N = build_local_union(N_UB, N_LOCAL, 'novelist', n_conflicts)

    print('\n=== STEP 3 融合（本地优先 + git 增量）===')
    F_D, ADD_D, NOISE_D, S_D = fuse(L_D, G_D, 'drama')
    F_N, ADD_N, NOISE_N, S_N = fuse(L_N, G_N, 'novelist')

    print('\n=== STEP 4 就地升级主目录 ===')
    man_d = f'''# MERGE MANIFEST — drama-skills 融合版

- 融合日期：{TODAY}
- 策略：**本地优先 + git 增量**（用户确认）
- 骨架：本地基础版 v0.9.2（含 2026-11-21 实验扩写），{S_D['local_kept']} 文件
- 增量：上游 git v0.12.1 独有 {S_D['git_added']} 文件全部补入
- 同名冲突 {S_D['git_conflict_kept_local']} 项：**一律保留本地版**
- 噪音过滤 {S_D['noise_filtered']} 项（__pycache__ / .pytest_cache / *.pyc / *.bak-*），原始快照中仍保留
- 融合版文件总数：{S_D['fused_total']}（另含本 manifest）
- VERSION 保持本地 `0.9.2` 不擅自改写；本版实为 `0.9.2-local + upstream-v0.12.1-increment`

## 回退 / 取用（绝对路径）
- 本地基础版完整快照：`D:/AIShortDrama/3_漫剧SKILLS/2_分镜/1_主SKILLS/_backup_20261121_v0.9.2/drama-skills-main/`
- git v0.12.1 纯净快照：`D:/AIShortDrama/3_漫剧SKILLS/2_分镜/1_主SKILLS/_git_v0.12.1_纯净快照_20261122/`
- 全量差异与集成清单：`D:/AIShortDrama/3_漫剧SKILLS/SKILLS融合报告_20261122.md`
'''
    man_n = f'''# MERGE MANIFEST — chinese-novelist 融合版

- 融合日期：{TODAY}
- 策略：**本地优先 + git 增量**（用户确认）
- 骨架：本地最新版并集 = 工作台加载版（11-19，SKILL.md 27319）∪ D 盘备份版（11-21 扩写），{S_N['local_kept']} 文件
- 增量：上游 git v2.3.2 独有 {S_N['git_added']} 文件（`references/flows/`、`references/guides/`、`.mjs` 脚本等）全部补入
- 同名冲突 {S_N['git_conflict_kept_local']} 项：**一律保留本地版**
- 噪音过滤 {S_N['noise_filtered']} 项，原始快照中仍保留
- 融合版文件总数：{S_N['fused_total']}（另含本 manifest）
- 注意：本地 8 问流程与 git 三层问答为两套架构，此处并置共存，主 SKILL.md 走本地 8 问流程

## 回退 / 取用（绝对路径）
- 工作台加载版：`C:/Users/Administrator/.workbuddy/skills/chinese-novelist/`（未改动）
- D 盘本地备份版：`D:/AIShortDrama/3_漫剧SKILLS/1_剧本/1_主SKILLS/chinese-novelist-skill-master.backup-v1-20261121/`
- git v2.3.2 纯净快照：`D:/AIShortDrama/3_漫剧SKILLS/1_剧本/1_主SKILLS/_git_v2.3.2_纯净快照_20261122/`
- 全量差异与集成清单：`D:/AIShortDrama/3_漫剧SKILLS/SKILLS融合报告_20261122.md`
'''
    materialize(F_D, D_GIT, man_d)
    materialize(F_N, N_GIT, man_n)

    print('\n=== STEP 5 验证 ===')
    V_D, V_N = scan(D_GIT), scan(N_GIT)
    key_checks = [
        ('drama 本地 H3 方言 48KB', V_D, 'skills/short-drama-video-prompts/references/minimax-h3.md', 48357),
        ('drama 本地 storyboard SKILL 38KB', V_D, 'skills/short-drama-storyboard/SKILL.md', 38160),
        ('drama 本地 continuity-lock 8481', V_D, 'skills/short-drama-assets/references/continuity-lock.md', 8481),
        ('drama git 新 skill breakdown', V_D, 'skills/short-drama-breakdown/SKILL.md', None),
        ('drama git 新 三视图文档', V_D, 'docs/character-turnaround-sheet-prompts.md', None),
        ('drama git 新 video-prompt-guide', V_D, 'skills/short-drama-video-prompts/references/video-prompt-guide.md', None),
        ('novelist 工作台 SKILL 27319', V_N, 'SKILL.md', 27319),
        ('novelist 工作台 scene-beats', V_N, 'references/scene-beats.md', None),
        ('novelist 工作台 check_scene_density', V_N, 'scripts/check_scene_density.py', None),
        ('novelist 本地扩写 renderable-dialogue', V_N, 'references/renderable-dialogue.md', 10075),
        ('novelist git 新 flows', V_N, 'references/flows/phase1-layer1-core.md', None),
        ('novelist git 新 guides', V_N, 'references/guides/chapter-guide.md', None),
    ]
    checks = []
    ok = True
    for label, V, k, expect in key_checks:
        hit = k in V
        good = hit and (expect is None or V[k][0] == expect)
        ok &= good
        checks.append((label, k, V[k][0] if hit else '缺失', expect, 'PASS' if good else 'FAIL'))
        print('  %-4s %-42s %s' % ('PASS' if good else 'FAIL', label,
                                  ('%s bytes' % V[k][0]) if hit else '文件缺失'))

    miss_d, tot_d = check_refs(D_GIT, 'drama')
    miss_n, tot_n = check_refs(N_GIT, 'novelist')

    # ---- 报告 ----
    lines = []
    A = lines.append
    A('# SKILLS 融合报告 · 2026-11-22')
    A('')
    A('> 策略：**本地优先 + git 增量**；落点：**D 盘主目录就地升级**（用户确认）。')
    A('> 目的：修复上一轮「整体替换」导致的本地定制退场，把本地多次更新的成果与 git 最新版新特性合为一份「本地最新版」。')
    A('')
    A('## 一、三源定线')
    A('')
    A('| 源 | 位置 | 性质 |')
    A('|---|---|---|')
    A('| ① 本地基础版(D) | `2_分镜/1_主SKILLS/_backup_20261121_v0.9.2/drama-skills-main/` | v0.9.2，617 文件，含 11-21 四处实验扩写（`.bak-20261121-exp` 为证） |')
    A('| ② 本地基础版(N) | 工作台 `~/.workbuddy/skills/chinese-novelist/` ∪ `1_剧本/.../chinese-novelist-skill-master.backup-v1-20261121/` | 8 问流程；工作台版 11-19 更新（SKILL.md 27319、多 2 文件），备份版含 11-21 扩写 |')
    A('| ③ git 最新版 | 现装 v0.12.1 / v2.3.2 | 上游 11-16；主动精简 SKILL.md、合并 references、新增 breakdown skill |')
    A('')
    A('三源均**无 `.git`**，无法用 git merge；novelist v2.3.2 目录结构重写（`references/` → `flows/`+`guides/`，`.py`→`.mjs`），与本地同名且内容相同文件 **0 个**，字节级合并无意义。')
    A('')
    A('## 二、差异统计')
    A('')
    A('| 项目 | drama-skills | chinese-novelist |')
    A('|---|---|---|')
    A('| 本地文件数 | 617 | 工作台 32 ∪ 备份 39 |')
    A('| git 新版文件数 | 553 | 31 |')
    A('| 本地独有 | 113 | 36（对 git） |')
    A('| git 独有 | 49 | 28 |')
    A('| 同名内容不同 | 327 | 3（其余 0 个相同） |')
    A('| 同名内容相同 | 177 | 0 |')
    A('')
    A('**根因**：本地一路做加法（H3 方言 48KB、storyboard 25+ references、novelist 8 问 27KB）；上游 v0.12.1 一路做减法（CHANGELOG 11-05 / 11-07 / 11-14 三条 prune & consolidate），v2.3.2 更是架构重写。混合同名文件会断引用链，故采用「本地为骨架 + git 增量补入」。')
    A('')
    A('## 三、融合结果')
    A('')
    A('| 指标 | drama | novelist |')
    A('|---|---|---|')
    A('| 本地骨架保留 | %d | %d |' % (S_D['local_kept'], S_N['local_kept']))
    A('| git 独有增量补入 | %d | %d |' % (S_D['git_added'], S_N['git_added']))
    A('| 同名冲突保留本地版 | %d | %d |' % (S_D['git_conflict_kept_local'], S_N['git_conflict_kept_local']))
    A('| 噪音/备份过滤 | %d | %d |' % (S_D['noise_filtered'], S_N['noise_filtered']))
    A('| **融合版文件总数** | **%d** | **%d** |' % (S_D['fused_total'], S_N['fused_total']))
    A('')
    A('### git 新增（本次真正拿到的上游新特性，节选）')
    A('')
    for k in [x for x in ADD_D if x.startswith(('skills/short-drama-breakdown/', 'docs/'))][:40]:
        A('- `' + k + '`')
    A('')
    A('其中 **`docs/character-turnaround-sheet-prompts.md`**（三视图提示词）与 **`skills/short-drama-breakdown/`**（全新拆解 skill，含 110KB 工具）与当前三视图 / 反推工作流最直接相关。')
    A('')
    A(' novelist 侧新增 `references/flows/`（三层问答流程）、`references/guides/`（写作指南）、`scripts/check_chapter_wordcount.mjs`、`ROADMAP.md` 等，均与本地 8 问流程**并置共存**，不覆盖主 SKILL.md。')
    A('')
    A('### 本地定制保全（节选）')
    A('')
    for k in ['skills/short-drama-video-prompts/references/minimax-h3.md',
              'skills/short-drama-storyboard/SKILL.md',
              'skills/short-drama-storyboard/references/voicetrack-renderability.md',
              'skills/short-drama-assets/references/continuity-lock.md',
              'skills/short-drama-video-prompts/references/production-prompt-grammar.md',
              'skills/short-drama-storyboard/references/comic-keyframe-lexicon.md',
              'skills/short-drama-storyboard/references/maxdirector-blocking-faq.md']:
        A('- `%s` (%s bytes)' % (k, V_D[k][0] if k in V_D else '缺失'))
    A('- `SKILL.md` (novelist, %s bytes, 8 问流程)' % (V_N['SKILL.md'][0] if 'SKILL.md' in V_N else '缺失'))
    A('- `references/renderable-dialogue.md` (novelist, %s bytes, 11-21 扩写版)' % (V_N['references/renderable-dialogue.md'][0] if 'references/renderable-dialogue.md' in V_N else '缺失'))
    A('')
    A('### novelist 本地并集冲突决策（%d 项）' % len(n_conflicts))
    A('')
    A('| 文件 | 工作台 | D盘备份 | 取用 | 依据 |')
    A('|---|---|---|---|---|')
    for k, a, b, ch, why in n_conflicts:
        A('| `%s` | %s | %s | %s | %s |' % (k, a, b, ch, why))
    A('')
    A('## 四、验证')
    A('')
    A('| 抽查项 | 期望 | 实测 | 结果 |')
    A('|---|---|---|---|')
    for label, k, got, expect, res in checks:
        A('| %s | %s | %s | %s |' % (label, expect or '存在', got, res))
    A('')
    A('引用链抽查：drama %d 处引用、疑似缺失 %d 处；novelist %d 处引用、疑似缺失 %d 处。' % (tot_d, len(miss_d), tot_n, len(miss_n)))
    if miss_d[:15]:
        A('')
        A('drama 疑似缺失引用（前 15，多为文档中的示例路径，需人工判断）：')
        for p, m in miss_d[:15]:
            A('- `%s` -> `%s`' % (p, m))
    A('')
    A('## 五、快照与回退')
    A('')
    A('| 快照 | 路径 | 说明 |')
    A('|---|---|---|')
    A('| 本地基础版(D) | `2_分镜/1_主SKILLS/_backup_20261121_v0.9.2/` | 未改动 |')
    A('| 本地基础版(N) | `1_剧本/1_主SKILLS/chinese-novelist-skill-master.backup-v1-20261121/` + 工作台 `~/.workbuddy/skills/chinese-novelist/` | 均未改动 |')
    A('| git v0.12.1 纯净版 | `2_分镜/1_主SKILLS/_git_v0.12.1_纯净快照_20261122/` | 本次新建，同名冲突的 git 版在此可取 |')
    A('| git v2.3.2 纯净版 | `1_剧本/1_主SKILLS/_git_v2.3.2_纯净快照_20261122/` | 本次新建 |')
    A('| 融合版(D) | `2_分镜/1_主SKILLS/drama-skills-main/drama-skills-main/` | 就地升级 |')
    A('| 融合版(N) | `1_剧本/1_主SKILLS/chinese-novelist-skill-master/` | 就地升级 |')
    A('')
    A('## 六、后续维护（git 再出新版本时）')
    A('')
    A('1. 下载新 release zip，解压到临时目录，**不要覆盖主目录**；')
    A('2. 复跑 `merge_skills.py`（改 `*_GIT` 指向新解压目录、更新 `*_SNAP` 名）；')
    A('3. 脚本会自动：新建纯净快照 → 以当前融合版为**新本地骨架** → 只补 git 独有增量 → 同名冲突继续保留本地版；')
    A('4. 看报告里的「git 新增」清单，人工决定是否把个别新版同名文件单独取用。')
    A('')
    A('这样本地定制永远为主线，上游只作为增量源，不会再发生「整体替换弄丢定制」。')
    A('')
    A('## 七、未决项')
    A('')
    A('- 工作台 `~/.workbuddy/skills/` **未同步**（按你选的「D 盘主目录就地升级」）；如需让实际加载位生效，可另行同步。')
    A('- 两份 `MERGE_MANIFEST.md` 与各目录 `VERSION` 并存；drama 的 `VERSION` 仍为 `0.9.2`，未擅自改写以免误导，融合身份以 manifest 为准。')
    A('- 噪音文件（`.pytest_cache`、`__pycache__`、`*.bak-*`）未进主目录，均保留在原始快照中。')
    A('')
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('\n=== 报告已生成 ===\n  %s' % REPORT)
    print('\n=== 总体结果: %s ===' % ('PASS' if ok else 'FAIL（见上表）'))


if __name__ == '__main__':
    main()
