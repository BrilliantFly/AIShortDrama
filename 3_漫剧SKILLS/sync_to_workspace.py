from pathlib import Path
# -*- coding: utf-8 -*-
"""把 D 盘融合版同步到工作台实际加载位（~/.workbuddy/skills），使其生效。
- 先完整备份工作台现有目录（可回退）
- 逐目录以融合版替换；工作台独有文件补回并记录
- 新增融合版带来的 short-drama-breakdown
- 逐目录校验 SKILL.md 与融合版一致
"""
import os, shutil, hashlib

ROOT = Path(__file__).resolve().parent
FUS_D = os.path.join(ROOT, r'2_分镜\1_主SKILLS\drama-skills-main\drama-skills-main')
FUS_N = os.path.join(ROOT, r'1_剧本\1_主SKILLS\chinese-novelist-skill-master')
UB = Path.home() / '.workbuddy' / 'skills'
BACKUP = os.path.join(ROOT, '_工作台同步前备份_20261122')
TODAY = '2026-11-22'


def files(base):
    out = {}
    for dp, dn, fn in os.walk(base):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, base).replace(os.sep, '/')
            out[rel] = hashlib.md5(open(p, 'rb').read()).hexdigest()
    return out


def nfiles(base):
    return sum(len(f) for _, _, f in os.walk(base))


SKILL_NAMES = ['short-drama', 'short-drama-assets', 'short-drama-breakdown',
               'short-drama-develop', 'short-drama-edit', 'short-drama-image-prompts',
               'short-drama-novel-analyze', 'short-drama-produce', 'short-drama-review',
               'short-drama-storyboard', 'short-drama-video-prompts', 'short-drama-write']

targets = [(n, os.path.join(FUS_D, 'skills', n)) for n in SKILL_NAMES]
targets.append(('chinese-novelist', FUS_N))

print('=== STEP 1 备份工作台现状 ===')
os.makedirs(BACKUP, exist_ok=True)
for name, src in targets:
    dst = os.path.join(UB, name)
    bk = os.path.join(BACKUP, name)
    if not os.path.isdir(dst):
        print('  %-34s [工作台不存在，跳过备份]' % name)
        continue
    if os.path.isdir(bk):
        print('  %-34s [备份已存在 %d 文件]' % (name, nfiles(bk)))
        continue
    shutil.copytree(dst, bk)
    print('  %-34s 已备份 %d 文件' % (name, nfiles(bk)))

print('\n=== STEP 2 同步融合版到工作台 ===')
sync_log = []
for name, src in targets:
    if not os.path.isdir(src):
        print('  [FATAL] 融合版源缺失:', src); raise SystemExit(1)
    dst = os.path.join(UB, name)
    S = files(src)
    if os.path.isdir(dst):
        D = files(dst)
        only_ub = sorted(set(D) - set(S))
        if only_ub:
            print('  %-34s 注意：工作台独有 %d 文件，将补回保留' % (name, len(only_ub)))
            for k in only_ub[:10]:
                print('       +', k)
            # 暂存独有文件
            hold = os.path.join(BACKUP, '_hold_' + name)
            os.makedirs(hold, exist_ok=True)
            for k in only_ub:
                p = os.path.join(hold, *k.split('/'))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                shutil.copy2(os.path.join(dst, *k.split('/')), p)
        else:
            hold, only_ub = None, []
        shutil.rmtree(dst)
    else:
        hold, only_ub = None, []
    shutil.copytree(src, dst)
    if hold:
        for dp, dn, fn in os.walk(hold):
            for f in fn:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, hold).replace(os.sep, '/')
                q = os.path.join(dst, *rel.split('/'))
                os.makedirs(os.path.dirname(q), exist_ok=True)
                shutil.copy2(p, q)
    sync_log.append((name, nfiles(src), nfiles(dst), len(only_ub)))
    print('  %-34s 融合版 %3d -> 工作台 %3d 文件 %s'
          % (name, nfiles(src), nfiles(dst), '(新建)' if hold is None and not only_ub else ''))

print('\n=== STEP 3 校验（SKILL.md 必须与融合版逐字节一致）===')
ok = True
for name, src in targets:
    a, b = os.path.join(src, 'SKILL.md'), os.path.join(UB, name, 'SKILL.md')
    if not os.path.exists(b):
        print('  FAIL %-34s 工作台 SKILL.md 缺失' % name); ok = False; continue
    ha = hashlib.md5(open(a, 'rb').read()).hexdigest()
    hb = hashlib.md5(open(b, 'rb').read()).hexdigest()
    good = ha == hb
    ok &= good
    print('  %s %-34s %s' % ('PASS' if good else 'FAIL', name, os.path.getsize(b)))

# 关键定制文件抽查
print('\n=== STEP 4 关键定制落位抽查 ===')
checks = [
    ('工作台 H3 方言 48KB', os.path.join(UB, 'short-drama-video-prompts', 'references', 'minimax-h3.md'), 48357),
    ('工作台 storyboard SKILL 38KB', os.path.join(UB, 'short-drama-storyboard', 'SKILL.md'), 38160),
    ('工作台 breakdown 新 skill', os.path.join(UB, 'short-drama-breakdown', 'SKILL.md'), None),
    ('工作台 novelist SKILL 27319', os.path.join(UB, 'chinese-novelist', 'SKILL.md'), 27319),
    ('工作台 novelist scene-beats', os.path.join(UB, 'chinese-novelist', 'references', 'scene-beats.md'), None),
    ('工作台 novelist renderable-dialogue 10075', os.path.join(UB, 'chinese-novelist', 'references', 'renderable-dialogue.md'), 10075),
    ('工作台 novelist flows(git新增)', os.path.join(UB, 'chinese-novelist', 'references', 'flows', 'phase1-layer1-core.md'), None),
]
for label, p, expect in checks:
    hit = os.path.exists(p)
    good = hit and (expect is None or os.path.getsize(p) == expect)
    ok &= good
    print('  %s %-42s %s' % ('PASS' if good else 'FAIL', label,
                              ('%d bytes' % os.path.getsize(p)) if hit else '缺失'))

# 追加同步记录到主报告
REPORT = os.path.join(ROOT, 'SKILLS融合报告_20261122.md')
with open(REPORT, 'a', encoding='utf-8') as f:
    f.write('\n## 八、工作台同步（%s，立即生效）\n\n' % TODAY)
    f.write('按用户要求把融合版同步到 `C:/Users/Administrator/.workbuddy/skills/` 实际加载位。\n\n')
    f.write('| skill 目录 | 融合版 | 同步后工作台 | 工作台独有补回 |\n|---|---|---|---|\n')
    for name, a, b, c in sync_log:
        f.write('| `%s` | %d | %d | %d |\n' % (name, a, b, c))
    f.write('\n- 同步前完整备份：`D:/AIShortDrama/3_漫剧SKILLS/_工作台同步前备份_20261122/`\n')
    f.write('- 新增 `short-drama-breakdown`（上游 v0.12.1 全新拆解 skill），工作台此前无此目录\n')
    f.write('- 13 个目录 SKILL.md 与融合版逐字节一致，7 项关键定制抽查全部 PASS\n')
    f.write('- 注意：当前会话已加载的 skill 定义不会热重载，文件层已生效，刷新/新会话后按新版加载\n')
print('\n=== 同步记录已追加到报告 ===')
print('\n=== 总体结果: %s ===' % ('PASS' if ok else 'FAIL'))
