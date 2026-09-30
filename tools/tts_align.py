#!/usr/bin/env python3
"""tts_align — paper2video 口播生成与时长对齐。

按 storyboard.json 为每个镜头生成中文口播 mp3（edge-tts），
输出 durations.json（每镜头音频时长），供渲染阶段对齐动画时长。

用法：
  tts_align.py <工作目录> [--voice zh-CN-XiaoxiaoNeural] [--rate +0%]

工作目录结构约定：
  <dir>/storyboard.json   分镜（输入）
  <dir>/audio/            口播 mp3（输出，<scene_id>-<n>.mp3）
  <dir>/durations.json    时长（输出）
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

EDGE_TTS = "/Users/lihaoqi/.master_env/bin/edge-tts"
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
MIN_SHOT_SEC, MAX_SHOT_SEC = 2.0, 90.0
MAX_TTS_RETRY = 2
RETRY_DELAY = 2.0


def shot_key(scene_id: str, index: int) -> str:
    return f"{scene_id}-{index}"


def mp3_duration(mp3: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp3)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"错误：ffprobe 读取时长失败 {mp3}：{out.stderr.strip()}")
    return float(out.stdout.strip())


def tts_one(text: str, mp3: Path, voice: str, rate: str) -> None:
    last_err = None
    for _ in range(MAX_TTS_RETRY + 1):
        res = subprocess.run(
            [EDGE_TTS, "-t", text, "-v", voice, "--rate", rate,
             "--write-media", str(mp3)],
            capture_output=True, text=True,
        )
        if res.returncode == 0 and mp3.exists() and mp3.stat().st_size > 0:
            return
        last_err = res.stderr.strip() or res.stdout.strip()
        time.sleep(RETRY_DELAY)
    raise SystemExit(f"错误：edge-tts 生成失败（{MAX_TTS_RETRY + 1} 次）：{last_err}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        prog="tts_align",
        description="为 storyboard 每个镜头生成中文口播并输出时长",
    )
    p.add_argument("workdir", help="工作目录（含 storyboard.json）")
    p.add_argument("--voice", default=DEFAULT_VOICE,
                   help=f"edge-tts 语音（默认 {DEFAULT_VOICE}）")
    p.add_argument("--rate", default="+0%", help="语速（默认 +0%）")
    args = p.parse_args(argv)

    workdir = Path(args.workdir)
    sb = json.loads((workdir / "storyboard.json").read_text(encoding="utf-8"))
    audio_dir = workdir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    durations = {}
    bad = []
    for scene in sb["scenes"]:
        sid = scene["id"]
        for i, shot in enumerate(scene["shots"], start=1):
            key = shot_key(sid, i)
            mp3 = audio_dir / f"{key}.mp3"
            tts_one(shot["narration_zh"], mp3, args.voice, args.rate)
            dur = mp3_duration(mp3)
            durations[key] = {"mp3": str(mp3.relative_to(workdir)),
                              "duration": dur}
            if not MIN_SHOT_SEC <= dur <= MAX_SHOT_SEC:
                bad.append((key, round(dur, 1)))
            print(f"  {key}: {dur:.1f}s")

    (workdir / "durations.json").write_text(
        json.dumps(durations, ensure_ascii=False, indent=2), encoding="utf-8")

    if bad:
        detail = "，".join(f"{k}({d}s)" for k, d in bad)
        print(f"警告：以下镜头口播时长越界（要求 15-60s，允许 2-90s）：{detail}")
        print("建议：让 AI 重新分镜后再跑 tts_align")
        return 1
    print(f"完成：{len(durations)} 段口播 → {audio_dir}/，时长 → durations.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
