---
name: paper2video
description: 用 manim 把论文 PDF 自动制作成精讲视频（中文口播 + 中英双语字幕烧录进画面，3b1b 深色风 + 论文原图浮层）。当用户说「讲讲这篇论文」「把这篇文章做成视频」「生成论文讲解视频」并给出 PDF 路径时使用；「对比这几篇」时生成多篇对比视频。管道：pdf2png 提取 → AI 分镜 → edge-tts 口播 → manim 渲染 → ffmpeg 合成。
---

# paper2video — 论文讲解视频生成

把用户给的论文 PDF（一篇或多篇）自动生成 15-30 分钟精讲视频：3b1b 深色风、核心公式逐步推导、关键处浮出论文原图、中文口播 + 中英双语字幕烧录进画面。全自动执行，不打断用户。

## 触发

- 「讲讲这篇论文」「把这篇文章做成视频」+ PDF 路径 → 单篇精讲
- 「对比这三篇」+ 多个 PDF 路径 → 对比模式（mode: compare）
- 输入：本地 PDF 文件路径（多篇用空格分隔）

## 工作目录约定

每篇论文一个独立工作目录：`~/manim_videos/<论文名>/`（论文名 = PDF 文件名去扩展名）。
目录内：`paper.txt`、`pages/`、`figures/`、`storyboard.json`、`audio/`、`durations.json`、`scenes/`、`clips/`、`render_state.json`、最终 `*.mp4`。

## 管线步骤（严格按序执行）

### 第 1 步：提取 PDF

```bash
python3 ~/.claude/skills/paper2video/tools/pdf2png.py extract <pdf> -o <工作目录>
```

- 输出 `paper.txt`（全文文本）+ `pages/`（每页低清预览图）
- 空页占比高时脚本会警告（扫描件需 OCR，目前先提示，视频制作继续）

### 第 2 步：AI 读论文、产出分镜

- 通读 `paper.txt`；用 Read 工具查看 `pages/p-<n>.png` 预览图确认论文结构、图表位置
- 严格按 `prompts/storyboard.md` 的规则与 schema 生成 `storyboard.json`（含每镜头口播文案、动画意图、截图引用、公式）
- 需要新截图时在 `fig_ref` 中给出目标名与页码 bbox 说明

### 第 3 步：按分镜裁剪截图

对 storyboard 中需要的新截图（figures/ 里还不存在的 fig_ref），用 Read 查看对应预览页估算 bbox，然后：

```bash
python3 ~/.claude/skills/paper2video/tools/pdf2png.py crop <pdf> --page <n> --bbox "x0,y0,x1,y1" --name <fig_ref文件名> -o <工作目录>
```

截图后用 Read 检查内容与预期一致（黑边过多/截错区域则调整 bbox 重裁）。

### 第 4 步：生成口播音频（对齐时长）

```bash
python3 ~/.claude/skills/paper2video/tools/tts_align.py <工作目录>
```

- 每镜头中文口播 → `audio/<scene>-<n>.mp3`，时长写入 `durations.json`
- 若有镜头时长越界（<2s 或 >90s），脚本警告：修改 storyboard 重新分镜后重跑本步

### 第 5 步：生成场景代码并渲染

按 storyboard + durations.json 生成 `scenes/scene-<n>.py`（n 按 scenes 顺序，类名固定 `S1`、`S2`…）：

- **只允许组装图元库组件**（`from primitives import ...`，见 `tools/primitives.py`），不裸写动画
- **每个镜头必须调用 `make_subtitle(中文, 英文)`** 加到底部（字幕烧录进画面）；镜头切换时 FadeOut 旧字幕、FadeIn 新字幕
- **动画总时长必须与音频时长对齐**：每镜头动画（含 wait）时长 ≈ durations.json 中对应镜头 mp3 时长 + 0.5s；先读 durations.json 再写 wait
- 公式用 `make_formula_tex`/`animate_formula_derive`（LaTeX 语法）；截图用 `make_figure_card`（配 figure_origin 标注原文位置）
- 每场景可加 `make_progress` 显示章节进度

渲染循环：

```bash
python3 ~/.claude/skills/paper2video/tools/render_loop.py preview <工作目录> --max-retry 3
```

- 失败场景 → `fix_requests/<sid>.txt` 有完整报错 → 修复对应场景代码 → **重跑 preview**（已有 clip 的场景自动跳过）
- 同一场景连续失败超过重试上限 → 自动生成降级静态页（口播+截图+文字），继续其他场景
- 全部通过后：

```bash
python3 ~/.claude/skills/paper2video/tools/render_loop.py final <工作目录>
```

- 高质量渲染（1080p30）到 `clips/<sid>.mp4`；中途可断点续跑（已渲染的跳过）

### 第 6 步：合成最终视频

```bash
python3 ~/.claude/skills/paper2video/tools/mux.py <工作目录>
```

- 拼接各场景 + 音轨合成 → `<工作目录>/<论文标题>.mp4`
- 若警告「音频超过视频」，说明第 5 步 wait 未对齐，修正场景代码后重跑 preview/final/mux

## 对比模式（多篇）

- 每篇论文单独建工作目录，分镜时 `mode: "compare"`，scenes 按「论文A核心 → 论文B核心 → 对比段落」组织（详见 prompts/storyboard.md）
- 对比段落用 `make_flow` 并排对照异同

## 关键约定（不可违反）

1. **字幕**：make_subtitle 每个镜头必加，中文+英文双行，烧录进画面
2. **对齐**：动画时长 = 音频时长（第 5 步先读 durations.json）
3. **图元库**：场景代码只组装 primitives，不裸写动画（避免 manim API 错误导致渲染失败循环）
4. **公式依赖**：MathTex 需要 LaTeX + dvisvgm。本机已配置：`~/.local/bin/dvisvgm` 是 wrapper（brew 版 kpathsea 找不到 BasicTeX 字体树，wrapper 注入 `TEXMFCNF`/`TEXMFROOT` 后转发真二进制）。若 dvisvgm 缺失或配置错误，公式镜头降级为文字说明（在 intent 里注明）
5. **口播语言**：始终中文（edge-tts zh-CN-XiaoxiaoNeural）；英文字幕是论文原句/术语对照

## 交付

完成后向用户报告：视频路径、时长、场景数、哪些场景降级（如有）、耗时。视频在 `~/manim_videos/<论文名>/<论文标题>.mp4`。
