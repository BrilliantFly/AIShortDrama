from pathlib import Path
# -*- coding: utf-8 -*-
"""2026-11-22 补全回灌：分镜 skill 里残留「一句一镜」单轨档口径的文件加档位分支注记。

约定（沿用 11-21 文档调整清单）：
- 只加注记 / 加可选开关，不改第三方正文结论；
- storyboard_lint.py 新增 --audio-mode，默认 source 时行为逐字不变；
- 所有待改文件先备份到统一目录（不污染 skill 包）。
"""
import os
import shutil
import py_compile
import hashlib

R = Path(__file__).resolve().parent
BASE = os.path.join(R, r'2_分镜\1_主SKILLS\drama-skills-main\drama-skills-main\skills\short-drama-storyboard')
BACKUP = os.path.join(R, r'_分镜档位调整前备份_20261122')

NOTE = (
    '> **档位分支（2026-11-22 补全回灌）**：上文「一句一镜 / DUO 不得带台词」**只在 '
    '`source` + TTS 单轨音轨档成立**。若下游是 **H3 `generate` + 双声线参考音色档**，按 '
    '[镜型规则档位分支](../SKILL.md) 执行：对话戏禁用一句一镜，2~3 句对白合并为一个 DUO 双人同框中景'
    '（侧面机位、两人面对面），H3 自动按句间停顿分配两条声线；该档必挂双身份板 + 相对站位锚写进'
    '分镜/视频提示词/起始帧三处，镜长 ≥7s。依据：经验库 3.0 节 `[已验证·返工案例]`'
    '（EP001 16 镜 SOLO → 10 镜 DUO，单人漂移/并排/切换过频同时消失）。\n'
)

# (相对路径, [(old, new), ...])
EDITS = {
    r'references\shot-craft.md': [(
        '**`craft_default · SHT-29`**：对白场默认一句一镜，给听者反应，交锋用正反打，先交代再落到中景，特写\n'
        '留给要落地的台词；删掉既无台词也无动作的空镜；插入镜用来调节节奏。\n',
        '**`craft_default · SHT-29`**：对白场默认一句一镜，给听者反应，交锋用正反打，先交代再落到中景，特写\n'
        '留给要落地的台词；删掉既无台词也无动作的空镜；插入镜用来调节节奏。\n\n'
        + NOTE
    )],
    r'references\index.md': [(
        '- [音轨可渲染性](voicetrack-renderability.md)——一镜一句、多说话人怎么办\n',
        '- [音轨可渲染性](voicetrack-renderability.md)——一镜一句、多说话人怎么办'
        '（**单轨 `source`/TTS 档**；H3 `generate` 双声线 DUO 档见 [SKILL.md](../SKILL.md) '
        '镜型规则档位分支与经验库 3.0）\n'
    )],
    r'references\ng-storyboard-export.md': [(
        '| 对白 | 不写 `spoken` | 多说话人按 [音轨可渲染性](voicetrack-renderability.md) 一镜一句 |\n',
        '| 对白 | 不写 `spoken` | 多说话人按 [音轨可渲染性](voicetrack-renderability.md) 一镜一句'
        '（单轨档）；H3 generate 双声线档可 DUO 一镜 2~3 句，见 [SKILL.md](../SKILL.md) 档位分支 |\n'
    ), (
        '| 超过 9 镜 | 只写前 9 个面板 | 按场次拆成多张故事板 |\n\n## 七、自检\n',
        '| 超过 9 镜 | 只写前 9 个面板 | 按场次拆成多张故事板 |\n\n'
        + NOTE + '\n## 七、自检\n'
    )],
    r'references\manual-to-storyboard.md': [(
        '| 台词 | `声音` 里「」原文 + 括号估时；镜型 SOLO/OTS 必标 |\n\n## 第 5 步：过 lint 再定稿\n',
        '| 台词 | `声音` 里「」原文 + 括号估时；镜型 SOLO/OTS 必标 |\n\n'
        + NOTE + '\n## 第 5 步：过 lint 再定稿\n'
    ), (
        'lint 过了才算编译完成，没过按提示回对应步骤。\n',
        'lint 过了才算编译完成，没过按提示回对应步骤。\n'
        '若走 H3 `generate` + 双声线 DUO 档，lint 要显式加 `--audio-mode generate`——'
        '默认 `source` 档的「DUO 不得带台词 / 一镜 ≤2 句 / 同镜单说话人」三条门禁才会按档位豁免'
        '（见 `scripts/storyboard_lint.py` 与经验库 3.0）。\n'
    )],
    r'scripts\storyboard_to_ng.py': [(
        '        # SOLO 镜只摆一个人：视觉依据常把对手也列进来，照单全收会摆出两人同框\n',
        '        # 档位分支（2026-11-22）：SOLO 只摆一人是单轨/source 档语义；\n'
        '        # H3 generate 双声线 DUO 档下对白镜应标 `镜型：DUO` 并保留两人同框\n'
        '        # （见 SKILL.md 镜型规则档位分支、经验库 3.0）。本处逻辑不改，仅提示标镜型。\n'
        '        # SOLO 镜只摆一个人：视觉依据常把对手也列进来，照单全收会摆出两人同框\n'
    )],
    r'scripts\storyboard_lint.py': [
        (
            '检查的是「这一镜交给单轨生成端能不能出声」+「人物互动站位与视角有没有机位语言」，\n'
            '不是文学质量。\n\n'
            '用法\n'
            '  python storyboard_lint.py 分镜.md\n'
            '  python storyboard_lint.py 分镜.md --fps 24 --ctx 22\n'
            '  python storyboard_lint.py 分镜.md --strict      # 缺新字段也算失败（新项目用）\n'
            '  python storyboard_lint.py 分镜.md --csv 分镜.csv # 同时导出机器可读表\n',
            '检查的是「这一镜交给单轨生成端能不能出声」+「人物互动站位与视角有没有机位语言」，\n'
            '不是文学质量。\n\n'
            '档位分支（2026-11-22 补全回灌，见经验库 3.0）：本 lint 的 DUO / 一句一镜 / 单说话人\n'
            '门禁**只针对 `source` + TTS 单轨档**。H3 `generate` + 双声线参考音色档实测可一镜\n'
            '2~3 句 DUO 双人同框，用 `--audio-mode generate` 豁免这三条；默认 `source` 行为不变。\n\n'
            '用法\n'
            '  python storyboard_lint.py 分镜.md\n'
            '  python storyboard_lint.py 分镜.md --fps 24 --ctx 22\n'
            '  python storyboard_lint.py 分镜.md --strict      # 缺新字段也算失败（新项目用）\n'
            '  python storyboard_lint.py 分镜.md --csv 分镜.csv # 同时导出机器可读表\n'
            '  python storyboard_lint.py 分镜.md --audio-mode generate  # H3 双声线 DUO 档\n'
        ),
        (
            '# A6 修复：文档默认「一句一镜最稳」，2 句是单轨能容的硬上限\n'
            'ADVISE_LINES = 1        # >1 句提示拆分（WARN）\n'
            'MAX_LINES = 2           # >2 句硬上限（FAIL，保留原门禁不动）\n',
            '# A6 修复：文档默认「一句一镜最稳」，2 句是单轨能容的硬上限\n'
            '# 档位分支（2026-11-22）：以上限只对 source 单轨档生效；generate 双声线档\n'
            '# 由 --audio-mode 在判定处豁免，经验库 3.0 建议 DUO 一镜 2~3 句。\n'
            'ADVISE_LINES = 1        # >1 句提示拆分（WARN）\n'
            'MAX_LINES = 2           # >2 句硬上限（FAIL，保留原门禁不动）\n'
        ),
        (
            '    ap.add_argument("--csv")\n'
            '    a = ap.parse_args()\n',
            '    ap.add_argument("--csv")\n'
            '    ap.add_argument("--audio-mode", choices=("source", "generate"), default="source",\n'
            '                    help="音轨档位：source=单轨TTS（默认，保留原门禁）；"\n'
            '                         "generate=H3双声线参考音色，豁免 DUO/一句一镜/单说话人门禁（经验库3.0）")\n'
            '    a = ap.parse_args()\n'
        ),
        (
            '        # 2 镜型与台词\n'
            '        if n_lines:\n'
            '            if not kind:\n'
            '                (fails if a.strict else warns).append(\n'
            '                    f"{sid} 有台词但未标 `镜型`（SOLO/OTS），下游无法判是否可渲染")\n'
            '            elif kind == "DUO":\n'
            '                fails.append(f"{sid} 镜型=DUO 却带 {n_lines} 句台词 —— DUO 不得有台词，必须拆镜")\n'
            '            elif kind not in ("SOLO", "OTS"):\n'
            '                fails.append(f"{sid} 镜型 `{kind}` 不是 SOLO/OTS/DUO")\n'
            '            # A6 分级：>1 句提示拆分（WARN），>2 句硬上限（FAIL）\n'
            '            if n_lines > MAX_LINES:\n'
            '                fails.append(f"{sid} 一镜 {n_lines} 句台词（硬上限 {MAX_LINES}）")\n'
            '            elif n_lines > ADVISE_LINES:\n'
            '                warns.append(f"{sid} 一镜 {n_lines} 句台词——文档默认「一句一镜最稳」，"\n'
            '                             f"两句同镜需确认单轨能分别对口型")\n'
            '            if len(uniq) > 1:\n'
            '                fails.append(f"{sid} 同镜出现 {len(uniq)} 个说话人（{\'、\'.join(uniq)}）—— 单轨只能一条音色")\n',
            '        # 2 镜型与台词\n'
            '        # 档位分支（2026-11-22）：generate 双声线档下 DUO 一镜 2~3 句已验证（经验库 3.0），\n'
            '        # 豁免「DUO 不得带台词 / >2 句硬上限 / >1 句提示 / 同镜多说话人」四条单轨档门禁；\n'
            '        # source 档（默认）逐字保持原有行为，其余通用检查（未标镜型、镜型非法、单句字数）不变。\n'
            '        gen = a.audio_mode == "generate"\n'
            '        if n_lines:\n'
            '            if not kind:\n'
            '                (fails if a.strict else warns).append(\n'
            '                    f"{sid} 有台词但未标 `镜型`（SOLO/OTS），下游无法判是否可渲染")\n'
            '            elif kind == "DUO":\n'
            '                if not gen:\n'
            '                    fails.append(f"{sid} 镜型=DUO 却带 {n_lines} 句台词 —— DUO 不得有台词，必须拆镜")\n'
            '            elif kind not in ("SOLO", "OTS"):\n'
            '                fails.append(f"{sid} 镜型 `{kind}` 不是 SOLO/OTS/DUO")\n'
            '            # A6 分级：>1 句提示拆分（WARN），>2 句硬上限（FAIL）\n'
            '            if gen:\n'
            '                if n_lines > 3:\n'
            '                    warns.append(f"{sid} generate 档一镜 {n_lines} 句台词——经验库 3.0 建议 DUO 2~3 句")\n'
            '            else:\n'
            '                if n_lines > MAX_LINES:\n'
            '                    fails.append(f"{sid} 一镜 {n_lines} 句台词（硬上限 {MAX_LINES}）")\n'
            '                elif n_lines > ADVISE_LINES:\n'
            '                    warns.append(f"{sid} 一镜 {n_lines} 句台词——文档默认「一句一镜最稳」，"\n'
            '                                 f"两句同镜需确认单轨能分别对口型")\n'
            '            if len(uniq) > 1 and not gen:\n'
            '                fails.append(f"{sid} 同镜出现 {len(uniq)} 个说话人（{\'、\'.join(uniq)}）—— 单轨只能一条音色")\n'
        ),
        (
            '    print(f"镜头数={len(shots)}  fps={a.fps}  ctx={a.ctx}  有台词镜={sum(1 for r in rows if r[\'台词数\'])}"\n',
            '    if a.audio_mode == "generate":\n'
            '        print("档位=generate(H3双声线DUO) — 已豁免单轨档 DUO/一句一镜/单说话人门禁（经验库3.0）")\n'
            '    print(f"镜头数={len(shots)}  fps={a.fps}  ctx={a.ctx}  有台词镜={sum(1 for r in rows if r[\'台词数\'])}"\n'
        ),
    ],
}


def main():
    # 1) 预检：所有 old 必须存在且唯一
    prepared = {}
    for rel, edits in EDITS.items():
        p = os.path.join(BASE, rel)
        assert os.path.exists(p), '缺文件: ' + p
        t = open(p, encoding='utf-8').read()
        for i, (old, new) in enumerate(edits):
            c = t.count(old)
            assert c == 1, '%s 第%d处 old 命中 %d 次（应为1）' % (rel, i + 1, c)
            t = t.replace(old, new, 1)
        prepared[rel] = t
        print('  [预检 OK] %-45s %d 处替换' % (rel, len(edits)))

    # 2) 备份（统一目录，保留相对结构；不污染 skill 包）
    if os.path.exists(BACKUP):
        print('  [备份已存在] 复用:', BACKUP)
    os.makedirs(BACKUP, exist_ok=True)
    for rel in EDITS:
        src = os.path.join(BASE, rel)
        dst = os.path.join(BACKUP, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

    # 3) 写入
    for rel, t in prepared.items():
        with open(os.path.join(BASE, rel), 'w', encoding='utf-8', newline='') as fh:
            fh.write(t)
        print('  [已写入]', rel)

    # 4) 语法检查
    for rel in ('scripts/storyboard_lint.py', 'scripts/storyboard_to_ng.py'):
        p = os.path.join(BASE, rel)
        py_compile.compile(p, doraise=True)
        print('  [语法 OK]', rel)

    # 5) 注记落位与备份完整性
    print('\n=== 校验 ===')
    for rel in EDITS:
        t = open(os.path.join(BASE, rel), encoding='utf-8').read()
        b = open(os.path.join(BACKUP, rel), encoding='utf-8').read()
        print('  %-45s 注记=%s | 备份=原版(%s) | 变化=%d 字节' % (
            rel, '有' if ('档位分支' in t or 'generate 双声线档' in t) else '【无】',
            '档位分支' not in b or rel.endswith('.py'), len(t) - len(b)))
    print('\n备份目录:', BACKUP)


if __name__ == '__main__':
    main()
