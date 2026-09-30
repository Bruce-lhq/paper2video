#!/usr/bin/env python3
"""render_loop — paper2video 场景渲染与修复循环。

约定：
- AI 按 storyboard.json + durations.json 生成场景代码 scenes/scene-<n>.py，
  类名固定为 S1、S2…（对应 storyboard 的 scenes 顺序），import primitives 组装组件
- preview 子命令：-ql 快速渲染，失败写 fix_requests/<sid>.txt 后退出码 1
  （AI 读请求修代码后重跑，最多 max-retry 次；超出自动降级为静态页）
- final 子命令：全部预览通过后 -qh 高质量渲染，断点续跑
- 输出：<workdir>/clips/<sid>.preview.mp4（预览）与 clips/<sid>.mp4（最终）

用法：
  render_loop.py preview <workdir>
  render_loop.py final   <workdir>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import validate, ValidationError

TOOLS_DIR = Path(__file__).parent
MANIM = "/Users/lihaoqi/.master_env/bin/manim"
PYTHON = "/Users/lihaoqi/.master_env/bin/python3"
MAX_RETRY = 3

SCENE_TEMPLATE = '''"""降级静态页（自动生成）：{title}"""
from manim import *
from pathlib import Path
import sys
sys.path.insert(0, {tools_dir!r})
from primitives import *


class {cls}(Scene):
    def construct(self):
        elements = []
        if {fig_ref!r} and Path({fig_ref!r}).exists():
            card = make_figure_card({fig_ref!r}, caption={title!r},
                                    origin_label={origin!r})
            elements.append(card)
        note = make_text_note({fallback_zh!r}, title="本节以图文呈现")
        elements.append(note)
        group = Group(*elements).arrange(DOWN, buff=0.6)
        group.scale_to_fit_height(6.2)
        self.add(group)
        self.wait(8)
'''

FALLBACK_ZH = ("本节动画渲染遇到困难，以口播、截图与文字呈现核心内容。"
               "详细讲解请听配音。")


def shot_has_figure(shot: dict) -> bool:
    return bool(shot.get("fig_ref"))


def scenes_from_storyboard(workdir: Path) -> list:
    sb = json.loads((workdir / "storyboard.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (TOOLS_DIR / "storyboard.schema.json").read_text(encoding="utf-8"))
    validate(sb, schema)
    return sb["scenes"]


def ensure_scene_files(workdir: Path, scenes: list) -> list:
    """检查 scenes/scene-<n>.py 存在，返回 [(n, sid, cls, file)]。"""
    scenes_dir = workdir / "scenes"
    result = []
    for i, sc in enumerate(scenes, start=1):
        cls = f"S{i}"
        f = scenes_dir / f"scene-{i}.py"
        if not f.exists():
            raise SystemExit(f"错误：缺少场景文件 {f}（请先让 AI 生成 {cls}）")
        result.append((i, sc["id"], cls, f))
    return result


def render_one(workdir: Path, n: int, sid: str, cls: str, f: Path,
               quality: str, out_name: str) -> tuple:
    """渲染单个场景，返回 (ok, stderr_tail)。quality: -ql / -qh。"""
    clips = workdir / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    out = clips / f"{out_name}.mp4"
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(TOOLS_DIR) + (":" + env["PYTHONPATH"]
                                          if env.get("PYTHONPATH") else "")
    res = subprocess.run(
        [MANIM, quality, "-o", str(out), str(f), cls],
        capture_output=True, text=True, env=env, cwd=str(workdir),
    )
    ok = res.returncode == 0 and out.exists()
    tail = "\n".join((res.stdout or "").splitlines()[-25:]
                     + (res.stderr or "").splitlines()[-25:])
    return ok, tail


def write_fix_request(workdir: Path, sid: str, err_tail: str, attempt: int) -> None:
    req_dir = workdir / "fix_requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    (req_dir / f"{sid}.txt").write_text(
        f"场景 {sid} 第 {attempt} 次渲染失败。请修复对应 scenes/scene-*.py "
        f"后重跑 render_loop.py preview。\n\n错误输出（尾部）：\n{err_tail}",
        encoding="utf-8")


def write_degraded_scene(workdir: Path, n: int, sid: str, cls: str,
                         scene: dict) -> Path:
    """生成降级静态页场景文件（自动，不依赖 AI）。"""
    first_shot = scene["shots"][0]
    fig_ref = next((s.get("fig_ref") for s in scene["shots"]
                    if shot_has_figure(s)), None)
    origin = next((s.get("figure_origin") for s in scene["shots"]
                   if shot_has_figure(s)), None) or ""
    degraded = workdir / "scenes" / f"scene-{n}-degraded.py"
    degraded.write_text(SCENE_TEMPLATE.format(
        title=scene["title"].replace("'", "\\'"),
        cls=cls, fig_ref=fig_ref or "", origin=origin,
        fallback_zh=FALLBACK_ZH, tools_dir=str(TOOLS_DIR)),
        encoding="utf-8")
    return degraded


STATE_FILE = "render_state.json"
PRIMS = TOOLS_DIR / "primitives.py"


def src_mtime(workdir: Path, n: int) -> float:
    """渲染依赖的源码最新修改时间（primitives + 场景文件）。"""
    t = PRIMS.stat().st_mtime
    scene_f = workdir / "scenes" / f"scene-{n}.py"
    if scene_f.exists():
        t = max(t, scene_f.stat().st_mtime)
    return t


def load_state(workdir: Path) -> dict:
    f = workdir / STATE_FILE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_state(workdir: Path, state: dict) -> None:
    (workdir / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_preview(workdir: Path, max_retry: int) -> int:
    scenes = scenes_from_storyboard(workdir)
    entries = ensure_scene_files(workdir, scenes)
    state = load_state(workdir)
    all_ok = True
    for n, sid, cls, f in entries:
        clip = workdir / "clips" / f"{sid}.preview.mp4"
        cur_mtime = src_mtime(workdir, n)
        rec = state.get(sid)
        stale = rec and rec.get("src_mtime") != cur_mtime
        if clip.exists() and not stale:
            print(f"[跳过] {sid}（已有预览 clip）")
            continue
        if clip.exists() and stale:
            clip.unlink()
            print(f"[重渲染] {sid}（源码已变更）")
        attempts = 0
        src = f
        while attempts < max_retry:
            attempts += 1
            ok, tail = render_one(workdir, n, sid, cls, src, "-ql",
                                  f"{sid}.preview")
            if ok:
                print(f"[OK] {sid}（{src.name}）")
                state[sid] = {"file": src.name, "src_mtime": cur_mtime}
                break
            print(f"[失败] {sid} 第 {attempts} 次（{src.name}）")
            write_fix_request(workdir, sid, tail, attempts)
            if attempts < max_retry:
                print(f"  → 修复请求已写 fix_requests/{sid}.txt，"
                      f"修好后重跑（当前还剩 {max_retry - attempts} 次）")
                save_state(workdir, state)
                return 1
        else:
            print(f"[降级] {sid} {max_retry} 次失败，生成静态页")
            src = write_degraded_scene(workdir, n, sid, cls, scenes[n - 1])
            ok, tail = render_one(workdir, n, sid, cls, src, "-ql",
                                  f"{sid}.preview")
            if not ok:
                print(f"[错误] {sid} 降级页也失败，需人工检查\n{tail}")
                return 1
            state[sid] = {"file": src.name, "src_mtime": cur_mtime}
        all_ok = all_ok and ok
    save_state(workdir, state)
    print(f"预览完成：{'全部通过' if all_ok else '存在未通过场景'}，"
          f"下一步：修复请求处理完后重跑 preview，或直接 render_loop.py final")
    return 0


def cmd_final(workdir: Path) -> int:
    scenes = scenes_from_storyboard(workdir)
    entries = ensure_scene_files(workdir, scenes)
    state = load_state(workdir)
    ok_all = True
    for n, sid, cls, f in entries:
        clip = workdir / "clips" / f"{sid}.mp4"
        preview_clip = workdir / "clips" / f"{sid}.preview.mp4"
        cur_mtime = src_mtime(workdir, n)
        rec = state.get(sid)
        stale = rec and rec.get("src_mtime") != cur_mtime
        # final clip 比最近一次 preview 旧 → 也视为过期（preview 重渲染过）
        if (not stale and clip.exists() and preview_clip.exists()
                and clip.stat().st_mtime < preview_clip.stat().st_mtime):
            stale = True
        if clip.exists() and not stale:
            print(f"[跳过] {sid}（已有最终 clip）")
            continue
        if clip.exists() and stale:
            clip.unlink()
            print(f"[重渲染] {sid}（源码已变更）")
        # 用 preview 实际渲染成功的文件（可能是降级页）
        src = f
        if rec:
            cand = workdir / "scenes" / rec["file"]
            if cand.exists():
                src = cand
        if not (workdir / "clips" / f"{sid}.preview.mp4").exists():
            print(f"[跳过] {sid} 无预览 clip，先跑 preview")
            continue
        ok, tail = render_one(workdir, n, sid, cls, src, "-qh", sid)
        if ok:
            print(f"[OK] {sid}（{src.name}）")
        else:
            ok_all = False
            print(f"[错误] {sid} 最终渲染失败\n{tail}")
    print(f"最终渲染完成：{'全部通过' if ok_all else '存在失败场景'}")
    return 0 if ok_all else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="render_loop",
        description="paper2video 场景渲染与修复循环",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preview", help="-ql 预览渲染，失败写修复请求")
    pp.add_argument("workdir", help="工作目录")
    pp.add_argument("--max-retry", type=int, default=MAX_RETRY,
                    help=f"失败重试上限（默认 {MAX_RETRY}）")
    pf = sub.add_parser("final", help="-qh 高质量渲染")
    pf.add_argument("workdir", help="工作目录")
    args = p.parse_args(argv)
    # 必须绝对路径：manim -o 相对路径会在 mux 阶段找不到文件
    workdir = Path(args.workdir).resolve()
    if args.cmd == "preview":
        return cmd_preview(workdir, args.max_retry)
    return cmd_final(workdir)


if __name__ == "__main__":
    sys.exit(main())
