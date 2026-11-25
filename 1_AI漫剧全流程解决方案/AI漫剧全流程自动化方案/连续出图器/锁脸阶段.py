# -*- coding: utf-8 -*-
"""锁脸阶段：对连续出图器路线 A 的静帧跑 QwenEdit v3 温和锁脸（保构图只换脸）。

- 单人镜：image1=帧, image2=人物肖像板, image3=脸特写，单段完成。
- 双人镜（S001/S005/S008/S014）：两段式——先锁男主（PASS1 中间帧），再在结果上锁女主。
- 输入：ComfyUI input/办公室/frames_gen/SHOT-NNN.png（连续出图器归集产物）
- 输出：ComfyUI output/办公室/LOCKED-G/SHOT-NNN → 归集到项目 连续出图/frames_locked

用法：
  python 锁脸阶段.py --config 项目配置_办公室.json              # 体检
  python 锁脸阶段.py --config ... --only 3 --submit
  python 锁脸阶段.py --config ... --submit                     # 全量
"""
import os, sys, json, time, glob, shutil, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))

DUAL = (1, 5, 8, 14)          # 双人镜：单段直接锁女主（男主前景背影脸不可见）
MALE_SHOTS = (3, 7, 9, 10, 12, 15)
# 其余 = 女主单人镜 (2,4,6,11,13)

RETRY_SEED_OFFSET = 30000     # 失败重跑时换种子（拼贴/劣化是种子相关随机失败）
RETRY_SHOTS = {3}             # 本轮拼贴失败，换种子重跑

CFG_PATH = '项目配置_办公室.json'
IN_SUB = '办公室/frames_gen'
OUT_PREFIX = '办公室/LOCKED-G'
LOCKED_IN = '办公室/frames_locked'
PROJECT_DIR = os.environ.get('PROJECT_DIR', '')  # 跨机：由环境变量指定项目根，勿硬编码盘符

POS_TMPL = (
    "Image 1 is the original film still that must be preserved exactly. Image 2 is the target person's full-body "
    "character sheet. Image 3 is a clear front-facing close-up of the SAME target person — this face is the highest "
    "priority. Output ONE edited image: keep image 1's composition, camera angle, framing, number of people, each "
    "person's position, pose, gesture, body proportions, clothing, hairstyle, the night-office background, furniture "
    "and lighting COMPLETELY UNCHANGED. The ONLY change is to replace the face of the target person in image 1 with "
    "the face in image 3 — {desc}. Match facial features, eye shape, brows, nose, lips, face shape and skin tone to "
    "image 3 pixel for pixel; do not beautify, do not reshape the face, do not youngify. Keep the hair natural dark "
    "brown / black, never reddish. Do not let image 3's hair color transfer to the result. Do not output image 2 or "
    "image 3, do not output a character sheet, do not change panel layout, do not add or remove people, do not "
    "change clothes or hair. Photorealistic, real photo, natural skin texture, high detail."
)
NEG = ("text, watermark, extra people, third person, changed pose, changed clothes, changed hairstyle, "
       "red hair, auburn hair, copper hair, reddish brown hair, different face, beautified face, deformed, "
       "blurry, oversaturated, character sheet, collage, split screen")


def spec(cfg, char_name, image1, seed, out_prefix):
    c = cfg['chars'][char_name]
    m = cfg['models']
    return {
        '10': {'class_type': 'LoadImage', 'inputs': {'image': image1}},
        '11': {'class_type': 'LoadImage', 'inputs': {'image': c['sheet']}},
        '12': {'class_type': 'LoadImage', 'inputs': {'image': c['face']}},
        '20': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': m['edit_clip'], 'type': 'qwen_image', 'device': 'default'}},
        '21': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['edit_vae']}},
        '22': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['edit_unet'], 'weight_dtype': 'default'}},
        '23': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'shift': 3.0, 'model': ['22', 0]}},
        '30': {'class_type': 'TextEncodeQwenImageEditPlus',
               'inputs': {'clip': ['20', 0], 'vae': ['21', 0], 'prompt': POS_TMPL.format(desc=c['prompt_desc']),
                          'image1': ['10', 0], 'image2': ['11', 0], 'image3': ['12', 0]}},
        '31': {'class_type': 'TextEncodeQwenImageEdit',
               'inputs': {'clip': ['20', 0], 'vae': ['21', 0], 'prompt': NEG}},
        '32': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': 1344, 'height': 768, 'batch_size': 1}},
        '33': {'class_type': 'KSampler', 'inputs': {
            'seed': seed, 'steps': 20, 'cfg': 3.0, 'sampler_name': 'euler', 'scheduler': 'simple',
            'denoise': 1.0, 'model': ['23', 0], 'positive': ['30', 0], 'negative': ['31', 0],
            'latent_image': ['32', 0]}},
        '34': {'class_type': 'VAEDecode', 'inputs': {'samples': ['33', 0], 'vae': ['21', 0]}},
        '35': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': out_prefix, 'images': ['34', 0]}},
    }


def jobs(cfg, only=None):
    """返回 [(shot, pass_idx, char, input_image, seed, out_prefix)]"""
    out = []
    for s in range(1, 16):
        if only and s != only:
            continue
        base_img = '%s/SHOT-%03d.png' % (IN_SUB, s)
        if s in MALE_SHOTS:
            seed = 70000 + s + (RETRY_SEED_OFFSET if s in RETRY_SHOTS else 0)
            out.append((s, 1, '陆沉', base_img, seed, '%s/SHOT-%03d' % (OUT_PREFIX, s)))
        elif s in DUAL:
            # 双人镜男主均为前景背影（脸不可见），无需锁男主——单段直接锁女主。
            # 两段式实测：pass1 良好，pass2 二次重绘必劣化（色彩崩/拼贴），废弃。
            out.append((s, 1, '苏晚', base_img, 72000 + s, '%s/SHOT-%03d' % (OUT_PREFIX, s)))
        else:
            out.append((s, 1, '苏晚', base_img, 70000 + s, '%s/SHOT-%03d' % (OUT_PREFIX, s)))
    return out


def wait_file(comfy_out, prefix, timeout=600):
    pat = os.path.join(comfy_out, prefix.replace('/', os.sep) + '_*.png')
    end = time.time() + timeout
    while time.time() < end:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
        time.sleep(3)
    return None


def main():
    if not PROJECT_DIR:
        raise SystemExit('请先设置环境变量 PROJECT_DIR 指向本项目的连续出图目录（勿在脚本里写死盘符，见 路径约定.md）')
    args = sys.argv[1:]
    p = args[args.index('--config') + 1] if '--config' in args else CFG_PATH
    cfg = importlib.import_module('连续出图器').load_config(p if os.path.isabs(p) else os.path.join(HERE, p))
    # 复用连续出图器的 post/get/alive
    eng = importlib.import_module('连续出图器')
    only = int(args[args.index('--only') + 1]) if '--only' in args else None
    submit = '--submit' in args
    list_jobs = jobs(cfg, only)

    print('=== 锁脸阶段 体检 ===')
    comfy_out = os.path.join(cfg['comfy_root_out'], '办公室', 'LOCKED-G')
    for s, pi, ch, img, seed, prefix in list_jobs:
        api = spec(cfg, ch, img, seed, prefix)
        ok = (len(api) == 13 and api['30']['inputs']['image1'][0] == '10'
              and len(api['30']['inputs']['prompt']) > 400
              and api['12']['inputs']['image'] == cfg['chars'][ch]['face'])
        print('  S%03d pass%d %s seed=%d %s' % (s, pi, ch, seed, 'OK' if ok else 'XX'))
        assert ok
    if not submit:
        print('\n[体检模式] ComfyUI: %s' % ('在线' if eng.alive(cfg['host']) else '未监听'))
        return
    assert eng.alive(cfg['host']), 'ComfyUI 未监听'
    print('\n=== 提交（串行，两段式依赖中间帧）===')
    for s, pi, ch, img, seed, prefix in list_jobs:
        # 两段式 pass2 依赖 pass1 输出文件
        if pi == 2:
            src = wait_file(comfy_out, prefix.rsplit('/', 1)[-1] if False else 'PASS1-SHOT-%03d' % s)
            assert src, 'S%03d PASS1 未产出' % s
            dst = os.path.join(cfg['comfy_root_in'], '办公室', 'frames_gen', 'PASS1-SHOT-%03d.png' % s)
            shutil.copy2(src, dst)
            img = '%s/frames_gen/PASS1-SHOT-%03d.png' % ('办公室', s)
        api = spec(cfg, ch, img, seed, prefix)
        resp = eng.post(cfg['host'], '/prompt', {'prompt': api, 'client_id': 'lockface-S%03d-p%d' % (s, pi)})
        pid = resp.get('prompt_id')
        if not pid:
            print('  [FAIL] S%03d p%d -> %s' % (s, pi, json.dumps(resp, ensure_ascii=False)[:300]))
            continue
        print('  S%03d pass%d %s prompt_id=%s' % (s, pi, ch, pid), flush=True)
        for _ in range(300):
            time.sleep(2)
            try:
                h = eng.get(cfg['host'], '/history/' + pid)
            except Exception:
                continue
            if pid in h:
                st = h[pid].get('status', {})
                print('        %s' % ('完成' if st.get('completed') else '异常'), flush=True)
                break
        else:
            print('        [超时]', flush=True)
    print('\n=== 归集 ===')
    os.makedirs(PROJECT_DIR, exist_ok=True)
    os.makedirs(os.path.join(cfg['comfy_root_in'], LOCKED_IN), exist_ok=True)
    ok = 0
    for s in range(1, 16):
        if only and s != only:
            continue
        cand = sorted(glob.glob(os.path.join(comfy_out, 'SHOT-%03d_*.png' % s)))
        if not cand:
            print('  [缺] S%03d' % s)
            continue
        src = cand[-1]
        for dst in (os.path.join(cfg['comfy_root_in'], LOCKED_IN, 'SHOT-%03d.png' % s),
                    os.path.join(PROJECT_DIR, 'SHOT-%03d.png' % s)):
            shutil.copy2(src, dst)
        print('  S%03d <- %s' % (s, os.path.basename(src)))
        ok += 1
    print('归集 %d -> %s' % (ok, PROJECT_DIR))


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()
