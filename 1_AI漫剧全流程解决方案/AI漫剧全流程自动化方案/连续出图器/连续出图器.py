# -*- coding: utf-8 -*-
"""连续出图器：CSV 驱动的通用分镜静帧生成引擎（漫画式连续出图）。

输入三件套：
  1. 项目配置 JSON   —— 人物肖像 / 场景母版 / 模型 / 提示词模板 / 输出分组
  2. 分镜表 CSV      —— 列: shot|route|base|denoise|seed|refs|group|prompt（竖线分隔）
  3. ComfyUI 8188    —— 提交与轮询

路线：
  A = 场景母版 img2img（base=A/B）或纯 T2I（base=T2I，ECU 等特写）
      模型 Z-Image Turbo，8 步 cfg1 res_multistep，negative ConditioningZeroOut。
  B = QwenEdit-2509 多参考直出：image1=场景母版 + image2/3=人物肖像/脸特写，
      一步合成"把这个人放进这个场景"。20 步 cfg3 euler simple denoise 1.0。

一致性来源（经验库 22/23/24 章）：
  场景 = 母版 img2img；人物 = 肖像参考（B 路线）或后期锁脸（A 路线）；
  构图 = CSV 派生规则（人数/站位/景别写进 prompt）。

用法：
  python 连续出图器.py --config 项目配置_办公室.json              # 体检
  python 连续出图器.py --config 项目配置_办公室.json --only 1 --submit
  python 连续出图器.py --config 项目配置_办公室.json --submit     # 全量
"""
import os, sys, csv, json, time, glob, shutil, socket, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_shots(cfg):
    csv_path = cfg['csv'] if os.path.isabs(cfg['csv']) else os.path.join(BASE, cfg['csv'])
    rows = []
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        for r in csv.reader(f, delimiter='|'):
            if not r or r[0].startswith('#') or r[0].strip() in ('', 'shot'):
                continue
            shot, route, base, den, seed, refs, group, prompt = r[:8]
            refs = [x for x in refs.split('+') if x]
            rows.append({'shot': int(shot), 'route': route.strip().upper(), 'base': base.strip().upper(),
                         'denoise': float(den), 'seed': int(seed), 'refs': refs,
                         'group': group.strip() or 'main', 'prompt': prompt.strip()})
    return rows


def _subst(cfg, text):
    for name, c in cfg['chars'].items():
        text = text.replace('{%s}' % name, c['prompt_desc'])
    return text


# ---------- 路线 A：母版 img2img / 纯 T2I ----------

def build_a(cfg, r):
    m, g = cfg['models'], cfg['groups'][r['group']]
    if r['base'] == 'T2I':
        text = cfg['head']['T2I'] + _subst(cfg, r['prompt']) + cfg['tail']
        latent = ('14', {'class_type': 'EmptySD3LatentImage',
                         'inputs': {'width': 1344, 'height': 768, 'batch_size': 1}})
    else:
        text = cfg['head'][r['base']] + _subst(cfg, r['prompt']) + cfg['tail']
        img = cfg['masters'][r['base']]
        latent = ('13', {'class_type': 'VAEEncode', 'inputs': {
            'pixels': ['12', 0], 'vae': ['5', 0]}})
    api = {
        '2': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['unet'], 'weight_dtype': 'default'}},
        '3': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'shift': 3, 'model': ['2', 0]}},
        '4': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': m['clip'], 'type': 'lumina2', 'device': 'default'}},
        '5': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['vae']}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': text, 'clip': ['4', 0]}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'text': cfg['negative_a'], 'clip': ['4', 0]}},
        '7b': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['7', 0]}},
        latent[0]: latent[1],
        '9': {'class_type': 'KSampler', 'inputs': {
            'seed': r['seed'], 'steps': 8, 'cfg': 1, 'sampler_name': 'res_multistep', 'scheduler': 'simple',
            'denoise': r['denoise'], 'model': ['3', 0], 'positive': ['6', 0],
            'negative': ['7b', 0], 'latent_image': [latent[0], 0]}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['9', 0], 'vae': ['5', 0]}},
        '11': {'class_type': 'SaveImage', 'inputs': {
            'filename_prefix': '%s/SHOT-%03d' % (g['save_prefix'], r['shot']), 'images': ['8', 0]}},
    }
    if r['base'] != 'T2I':
        api['12'] = {'class_type': 'LoadImage', 'inputs': {'image': cfg['masters'][r['base']]}}
    return api


# ---------- 路线 B：QwenEdit-2509 多参考直出 ----------

def build_b(cfg, r):
    m, g = cfg['models'], cfg['groups'][r['group']]
    scene = ('Image 1 is the scene master plate: preserve its composition, camera angle, framing, furniture, '
             'background and lighting COMPLETELY UNCHANGED. ')
    parts = [scene]
    inputs_img = {'image1': ['40', 0]}
    api = {}
    n_imgs = 1
    for i, name in enumerate(r['refs'], start=2):
        c = cfg['chars'][name]
        api[str(30 + i)] = {'class_type': 'LoadImage',
                            'inputs': {'image': c['sheet']}}
        inputs_img['image%d' % i] = [str(30 + i), 0]
        parts.append('Image %d is the full-body character sheet of %s: %s — place/match this person exactly '
                     '(clothing, hairstyle, body), do not output the sheet itself. ' % (i, name, c['prompt_desc']))
        n_imgs += 1
    if len(r['refs']) == 1:
        c = cfg['chars'][r['refs'][0]]
        api['33'] = {'class_type': 'LoadImage', 'inputs': {'image': c['face']}}
        inputs_img['image3'] = ['33', 0]
        parts.append('Image 3 is a clear front-facing close-up of the SAME person — this face is the highest '
                     'priority: match facial features pixel for pixel, do not beautify, do not reshape. ')
        n_imgs += 1
    parts.append(_subst(cfg, r['prompt']))
    text = ''.join(parts)

    api.update({
        '20': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': m['edit_clip'], 'type': 'qwen_image', 'device': 'default'}},
        '21': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['edit_vae']}},
        '22': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['edit_unet'], 'weight_dtype': 'default'}},
        '23': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'shift': 3.0, 'model': ['22', 0]}},
        '30': dict({'class_type': 'TextEncodeQwenImageEditPlus',
                    'inputs': {'clip': ['20', 0], 'vae': ['21', 0], 'prompt': text}}, **inputs_img),
        '31': {'class_type': 'TextEncodeQwenImageEdit',
               'inputs': {'clip': ['20', 0], 'vae': ['21', 0], 'prompt': cfg['negative_b']}},
        '32': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': 1344, 'height': 768, 'batch_size': 1}},
        '34': {'class_type': 'KSampler', 'inputs': {
            'seed': r['seed'], 'steps': 20, 'cfg': 3.0, 'sampler_name': 'euler', 'scheduler': 'simple',
            'denoise': 1.0, 'model': ['23', 0], 'positive': ['30', 0], 'negative': ['31', 0],
            'latent_image': ['32', 0]}},
        '35': {'class_type': 'VAEDecode', 'inputs': {'samples': ['34', 0], 'vae': ['21', 0]}},
        '36': {'class_type': 'SaveImage', 'inputs': {
            'filename_prefix': '%s/SHOT-%03d' % (g['save_prefix'], r['shot']), 'images': ['35', 0]}},
    })
    api['40'] = {'class_type': 'LoadImage', 'inputs': {'image': cfg['masters'][r['base']]}}
    return api, n_imgs


def build(cfg, r):
    return build_a(cfg, r) if r['route'] == 'A' else build_b(cfg, r)


# ---------- 提交 / 轮询 / 归集 ----------

def post(host, path, payload):
    req = urllib.request.Request(host + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get(host, path):
    with urllib.request.urlopen(host + path, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def alive(host):
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect((urllib.parse.urlparse(host).hostname,
                   urllib.parse.urlparse(host).port or 80)); return True
    except Exception:
        return False
    finally:
        s.close()


def collect(cfg, rows):
    n_ok = 0
    for r in rows:
        g = cfg['groups'][r['group']]
        out_dir = os.path.join(cfg['comfy_root_out'], g['save_prefix'])
        cand = sorted(glob.glob(os.path.join(out_dir, 'SHOT-%03d_*.png' % r['shot'])))
        if not cand:
            print('  [缺] G:%s S%03d' % (r['group'], r['shot']))
            continue
        src = cand[-1]
        for dst in (os.path.join(cfg['comfy_root_in'], g['input_subdir'], 'SHOT-%03d.png' % r['shot']),
                    os.path.join(g['project_dir'], 'SHOT-%03d.png' % r['shot'])):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        print('  G:%s S%03d <- %s' % (r['group'], r['shot'], os.path.basename(src)))
        n_ok += 1
    print('归集 %d/%d' % (n_ok, len(rows)))


# ---------- 主流程 ----------

def check(cfg, rows):
    print('=== 连续出图器 体检 ===')
    for r in rows:
        ok = True
        msg = []
        if r['route'] == 'A':
            ok &= r['base'] in ('A', 'B', 'T2I')
            api = build_a(cfg, r)
            txt = api['6']['inputs']['text']
            head = cfg['head']['T2I'] if r['base'] == 'T2I' else cfg['head'][r['base']]
            ok &= txt.startswith(head) and txt.endswith(cfg['tail'].strip())
            ok &= (r['denoise'] <= 1.0 if r['base'] == 'T2I' else 0.30 <= r['denoise'] <= 0.90)
            msg.append('%d节点 文本%d字' % (len(api), len(txt)))
        else:
            ok &= r['base'] in ('A', 'B') and all(x in cfg['chars'] for x in r['refs'])
            api, n = build_b(cfg, r)
            txt = api['30']['inputs']['prompt']
            ok &= n == 1 + len(r['refs']) + (1 if len(r['refs']) == 1 else 0)
            ok &= txt.startswith('Image 1 is the scene master plate') and 1 <= n <= 3
            msg.append('参考图%d张 文本%d字' % (n, len(txt)))
        print('  G:%s S%03d route%s base=%s den=%.2f seed=%d %s %s'
              % (r['group'], r['shot'], r['route'], r['base'], r['denoise'], r['seed'],
                 ' '.join(msg), 'OK' if ok else 'XX'))
        assert ok, 'S%03d 体检失败' % r['shot']
        wf = os.path.join(BASE, '工作流输出', '%s-S%03d-%s.json' % (r['group'], r['shot'], r['route']))
        os.makedirs(os.path.dirname(wf), exist_ok=True)
        with open(wf, 'w', encoding='utf-8') as f:
            json.dump(api, f, ensure_ascii=False, indent=1)


def main():
    args = sys.argv[1:]
    cfg_path = args[args.index('--config') + 1]
    cfg = load_config(cfg_path if os.path.isabs(cfg_path) else os.path.join(BASE, cfg_path))
    rows = load_shots(cfg)
    if '--only' in args:
        only = int(args[args.index('--only') + 1])
        rows = [r for r in rows if r['shot'] == only]
    submit = '--submit' in args
    check(cfg, rows)
    if not submit:
        print('\n[体检模式] ComfyUI: %s' % ('在线' if alive(cfg['host']) else '未监听'))
        return
    assert alive(cfg['host']), 'ComfyUI 未监听: %s' % cfg['host']
    print('\n=== 提交 + 轮询 ===')
    for r in rows:
        api = build(cfg, r)[0] if r['route'] == 'B' else build(cfg, r)
        resp = post(cfg['host'], '/prompt', {'prompt': api, 'client_id': '%s-%s-%02d' % (cfg['name'], r['group'], r['shot'])})
        pid = resp.get('prompt_id')
        if not pid:
            print('  [FAIL] S%03d -> %s' % (r['shot'], json.dumps(resp, ensure_ascii=False)[:400]))
            continue
        print('  G:%s S%03d prompt_id=%s' % (r['group'], r['shot'], pid), flush=True)
        for _ in range(300):
            time.sleep(2)
            try:
                h = get(cfg['host'], '/history/' + pid)
            except Exception:
                continue
            if pid in h:
                print('        %s' % ('完成' if h[pid].get('status', {}).get('completed') else '异常'), flush=True)
                break
        else:
            print('        [超时]', flush=True)
    print('\n=== 归集 ===')
    collect(cfg, rows)


if __name__ == '__main__':
    main()
