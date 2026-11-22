# -*- coding: utf-8 -*-
"""把 6 个档位分支改动文件同步到工作台 short-drama-storyboard（先备份、后逐字节校验）"""
import os
import shutil
import hashlib

R = r'D:\AIShortDrama\3_漫剧SKILLS'
SRC = os.path.join(R, r'2_分镜\1_主SKILLS\drama-skills-main\drama-skills-main\skills\short-drama-storyboard')
DST = r'C:\Users\Administrator\.workbuddy\skills\short-drama-storyboard'
BACKUP = os.path.join(R, r'_工作台档位同步前备份_20261122')

FILES = [
    r'references\shot-craft.md',
    r'references\index.md',
    r'references\ng-storyboard-export.md',
    r'references\manual-to-storyboard.md',
    r'scripts\storyboard_to_ng.py',
    r'scripts\storyboard_lint.py',
]


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


print('=== 1 · 备份工作台当前版（改动前融合版）===')
os.makedirs(BACKUP, exist_ok=True)
for rel in FILES:
    s = os.path.join(DST, rel)
    d = os.path.join(BACKUP, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if not os.path.exists(d):
        shutil.copy2(s, d)
    print('  %-45s %s' % (rel, md5(d)[:10]))

print('\n=== 2 · 覆盖同步 ===')
for rel in FILES:
    s, d = os.path.join(SRC, rel), os.path.join(DST, rel)
    shutil.copy2(s, d)
    print('  synced', rel)

print('\n=== 3 · 逐字节校验 ===')
allok = True
for rel in FILES:
    s, d = os.path.join(SRC, rel), os.path.join(DST, rel)
    ok = md5(s) == md5(d)
    allok &= ok
    t = open(d, encoding='utf-8').read()
    has = '档位分支' in t or 'generate 双声线档' in t or '--audio-mode' in t
    print('  %-45s 一致=%s | 注记=%s | %d bytes' % (rel, ok, has, os.path.getsize(d)))
    allok &= has

print('\n=== 4 · 备份保存的是改动前版本（应无本次注记）===')
for rel in FILES:
    t = open(os.path.join(BACKUP, rel), encoding='utf-8').read()
    has = '2026-11-22 补全回灌' in t or '--audio-mode' in t
    print('  %-45s 含本次新增=%s' % (rel, has))
    allok &= not has

# 清理 py_compile 噪音
for root in (SRC, DST):
    pc = os.path.join(root, 'scripts', '__pycache__')
    if os.path.isdir(pc):
        shutil.rmtree(pc)
        print('\n  清理 pycache:', pc)

print('\n总判定:', 'PASS ✅' if allok else 'FAIL ❌')
print('工作台:', DST)
print('回退备份:', BACKUP)
