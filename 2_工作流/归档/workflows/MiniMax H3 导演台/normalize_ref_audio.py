#!/usr/bin/env python
"""参考音色标准化：把一组 wav/mp3 统一成 H3 导演台可用的规格。

为什么需要：插件 `lib/audio_io.load_reference_audio` 按源文件**原生采样率**解码，
只做 `-ac 2`，**不做重采样、不做响度归一、不裁时长**。素材混着 24k/32k/48k、
响度差 20 dB 时，音色克隆的频响基准与「说话力度」都会漂，是发音发虚的变量之一。

处理动作：
  1. 去头尾静音（阈值 -45 dB，留 0.1 s 缓冲）
  2. 从字头截取，最长 8 秒
  3. 响度归一到 -18 LUFS，真峰 -3 dBTP
  4. 重采样到 32 kHz
  5. 输出到 <目录>/normalized/，不覆盖原文件

用法:
    python normalize_ref_audio.py "D:/.../制作成果/audio"
    python normalize_ref_audio.py "D:/.../audio" --sr 32000 --lufs -18 --max-sec 8
    python normalize_ref_audio.py "D:/.../audio" --dry
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

EXTS = (".wav", ".mp3", ".flac", ".m4a", ".ogg")


def find_ffmpeg() -> str | None:
    env = os.environ.get("H3_FFMPEG")
    if env and os.path.isfile(env):
        return env
    hit = glob.glob(
        r"D:/ComfyUI-aki-v3.2/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-*.exe"
    )
    if hit:
        return hit[0]
    return shutil.which("ffmpeg")


def probe(ffmpeg: str, path: str) -> dict | None:
    p = subprocess.run([ffmpeg, "-i", path], capture_output=True)
    txt = (p.stderr or b"").decode("utf-8", "ignore")
    m_sr = re.search(r"(\d+) Hz, ([a-z0-9 ]+)", txt)
    m_du = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", txt)
    if not m_sr or not m_du:
        return None
    dur = int(m_du.group(1)) * 3600 + int(m_du.group(2)) * 60 + float(m_du.group(3))
    return {"sr": int(m_sr.group(1)), "layout": m_sr.group(2).strip(), "dur": dur}


def loudness(ffmpeg: str, path: str) -> tuple[float, float] | None:
    p = subprocess.run(
        [ffmpeg, "-i", path, "-af", "volumedetect", "-f", "null", os.devnull],
        capture_output=True,
    )
    txt = (p.stderr or b"").decode("utf-8", "ignore")
    m1 = re.search(r"mean_volume: (-?\d+\.?\d*) dB", txt)
    m2 = re.search(r"max_volume: (-?\d+\.?\d*) dB", txt)
    if not m1:
        return None
    return float(m1.group(1)), float(m2.group(1)) if m2 else 0.0


def build_filter(lufs: float, tp: float, max_sec: float, sr: int) -> str:
    sil = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1"
    return ",".join(
        [
            sil,                       # 去头静音
            "areverse",
            sil,                       # 反转后去原尾部静音
            "areverse",
            f"atrim=0:{max_sec:.2f}",
            f"loudnorm=I={lufs}:TP={tp}:LRA=11",
            f"aresample={sr}",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--sr", type=int, default=32000)
    ap.add_argument("--lufs", type=float, default=-18.0)
    ap.add_argument("--tp", type=float, default=-3.0)
    ap.add_argument("--max-sec", type=float, default=8.0)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("找不到 ffmpeg：设 H3_FFMPEG 环境变量指向 ffmpeg.exe")
        return 1

    src_dir = os.path.abspath(a.folder)
    out_dir = os.path.join(src_dir, "normalized")
    files = sorted(
        f for f in glob.glob(os.path.join(src_dir, "*")) if f.lower().endswith(EXTS)
    )
    if not files:
        print(f"{src_dir} 下没有音频文件")
        return 1
    if not a.dry:
        os.makedirs(out_dir, exist_ok=True)

    flt = build_filter(a.lufs, a.tp, a.max_sec, a.sr)
    rows, bad = [], []
    for f in files:
        name = os.path.basename(f)
        before = probe(ffmpeg, f)
        vol_b = loudness(ffmpeg, f)
        if not before:
            bad.append((name, "无法探测"))
            continue
        rows.append(
            (
                name,
                before["sr"],
                before["layout"],
                before["dur"],
                vol_b[0] if vol_b else None,
            )
        )

    print(f"{'文件':<24}{'原采样率':>8}{'声道':>8}{'原时长':>9}{'原响度':>9}")
    for name, sr, layout, dur, vol in rows:
        v = f"{vol:.1f} dB" if vol is not None else "-"
        print(f"{name:<24}{sr:>8}{layout:>8}{dur:>8.2f}s{v:>10}")

    if a.dry:
        print("\n--dry：未写文件")
        return 0 if not bad else 1

    print(f"\n输出目录: {out_dir}\n滤镜: {flt}\n")
    ok = 0
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        dst = os.path.join(out_dir, f"{stem}.wav")
        cmd = [
            ffmpeg, "-y", "-v", "error", "-i", f,
            "-af", flt, "-ac", "1", "-ar", str(a.sr),
            "-c:a", "pcm_s16le", dst,
        ]
        r = subprocess.run(cmd)
        if r.returncode != 0 or not os.path.exists(dst):
            bad.append((os.path.basename(f), f"ffmpeg 退出码 {r.returncode}"))
            continue
        after = probe(ffmpeg, dst)
        vol_a = loudness(ffmpeg, dst)
        print(
            f"OK  {os.path.basename(f):<22} → {after['sr']}Hz mono "
            f"{after['dur']:.2f}s  {vol_a[0]:.1f} dB" if after and vol_a else f"OK  {f}"
        )
        if after and after["dur"] < 3.0:
            print(
                f"    WARN: 归一后仅 {after['dur']:.2f}s，音色克隆偏短 —— "
                f"换一段更长的干声（5~8s 纯说话）"
            )
        ok += 1

    print(f"\n完成 {ok}/{len(files)}")
    for n, why in bad:
        print("FAIL:", n, why)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
