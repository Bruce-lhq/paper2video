#!/usr/bin/env python3
"""mux — paper2video 最终合成：拼接画面 + 音轨 → MP4。

字幕由 manim 直接渲染进画面（make_subtitle 组件），此处只做拼接与音轨合成。

输入（工作目录约定）：
  storyboard.json   分镜
  durations.json    每镜头音频时长（tts_align 输出）
  clips/<sid>.mp4   每场景最终渲染 clip（render_loop final 输出）
  audio/<key>.mp3   每镜头口播

输出：<工作目录>/<论文名>.mp4（1080p30，字幕已烧录在画面中）

用法：
  mux.py <工作目录> [--name 输出文件名（默认论文标题）]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

FFMPEG = "ffmpeg"


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def concat_demuxer(files: list, list_file: Path) -> str:
    list_file.write_text(
        "".join(f"file '{f.resolve()}'\n" for f in files), encoding="utf-8")
    return str(list_file)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="mux", description="paper2video 最终合成：画面+音轨+字幕 → MP4")
    p.add_argument("workdir", help="工作目录")
    p.add_argument("--name", default=None,
                   help="输出文件名（默认论文标题，不含扩展名）")
    args = p.parse_args(argv)

    workdir = Path(args.workdir).resolve()
    sb = json.loads((workdir / "storyboard.json").read_text(encoding="utf-8"))
    durations = json.loads((workdir / "durations.json").read_text(encoding="utf-8"))

    # 1) 收集场景与镜头顺序，计算场景起始时间
    clips, audios, shot_order, scene_starts = [], [], [], {}
    t = 0.0
    for scene in sb["scenes"]:
        sid = scene["id"]
        clip = workdir / "clips" / f"{sid}.mp4"
        if not clip.exists():
            raise SystemExit(f"错误：缺少最终 clip {clip}（先跑 render_loop.py final）")
        clips.append(clip)
        scene_starts[sid] = t
        shot_list = []
        for i, shot in enumerate(scene["shots"], start=1):
            key = f"{sid}-{i}"
            mp3 = workdir / durations[key]["mp3"]
            if not mp3.exists():
                raise SystemExit(f"错误：缺少口播 {mp3}（先跑 tts_align.py）")
            audios.append(mp3)
            shot_list.append((key, shot))
        shot_order.append((sid, shot_list))
        t += probe_duration(clip)

    # 2) 拼接视频与音频（concat demuxer），视频流直接复制（各 clip 参数一致）
    video_list = workdir / "concat_video.txt"
    audio_list = workdir / "concat_audio.txt"
    concat_demuxer(clips, video_list)
    concat_demuxer(audios, audio_list)

    # 3) 合成输出（字幕已渲染进画面，无需滤镜）
    out = workdir / f"{args.name or sb['paper']['title']}.mp4"
    res = subprocess.run([
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(video_list),
        "-f", "concat", "-safe", "0", "-i", str(audio_list),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"错误：ffmpeg 合成失败\n{res.stderr[-2000:]}")
        return 1

    vid_dur = probe_duration(out)
    audio_dur = sum(probe_duration(a) for a in audios)
    if audio_dur > vid_dur + 1.0:
        print(f"警告：音频总长 {audio_dur:.1f}s 超过视频 {vid_dur:.1f}s，"
              f"尾部 {audio_dur - vid_dur:.1f}s 口播被截断——"
              f"场景代码的 wait 需按 durations.json 对齐音频时长")
    print(f"完成：{out}（{vid_dur:.1f}s；音频总长 {audio_dur:.1f}s，"
          f"差 {abs(vid_dur - audio_dur):.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
