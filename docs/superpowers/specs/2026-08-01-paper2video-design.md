# paper2video Skill 设计文档

日期：2026-08-01
状态：已确认（2026-08-01，brainstorming 会话）

## 1. 概述

本地运行的 Claude Code skill：用户提供论文 PDF（一篇或多篇），skill 自动将其转化为「精讲式」manim 讲解视频，帮助用户无痛理解论文。成品为带中文配音与中英双语字幕的 MP4。

## 2. 已确认需求（用户决策）

| 维度 | 决策 |
|---|---|
| 讲解深度 | 精讲式推导：15-30 分钟，核心公式逐步推导，方法细节深入可视化（3b1b 式） |
| 画面风格 | 3b1b 深色风为主（manim 默认质感），关键处浮出论文原图截图，标注原文位置（如 Fig.1 / §3.2） |
| 流程 | 全自动一条龙：用户发论文 → 直接产出视频，不打断用户 |
| 声音 | 默认中文口播（edge-tts），音轨合成进 MP4 |
| 字幕 | 中英双语烧录字幕，双行显示（中文主字幕 + 英文对照）；英文论文取原句/术语，中文论文译成英文 |
| 多篇 | 默认逐篇独立成片；用户明确要求（如「对比这三篇」）时生成对比视频 |
| 触发方式 | 用户说「讲讲这篇论文」等 + 给 PDF 路径 → skill 自动接管 |
| 输出规格 | 1080p30、16:9、MP4，字幕烧录（任何播放器打开即看）；附 storyboard.json 供回看/重渲染 |

## 3. 架构

固定管线，中间产物为 storyboard.json（分镜 JSON）。绿色=脚本自动，蓝色=AI 完成，橙色=修复循环。

```
① pdf2png.py ──► ② AI 读论文产出 storyboard.json ──► ③ tts_align.py（口播+音频时长）
      │                                                       │
      │                                                       ▼
      │                                              ④ AI 按分镜+图元库写 manim 场景代码
      │                                                       │
      └─────────────── 文本+截图 ◄───────── ③/④/⑤ 反复使用  ▼
                                                   ⑤ render_loop.py（-ql 预览→修复循环→高质量渲染）
                                                       │
                                                       ▼
                                                   ⑥ mux.py（画面+音轨+字幕 → MP4）
```

### skill 目录结构

```
~/.claude/skills/paper2video/
├── SKILL.md                 # 指令：触发条件、管线步骤、脚本调用方式
├── tools/
│   ├── pdf2png.py           # PDF → 文本 + 页面 PNG + bbox 裁剪截图
│   ├── tts_align.py         # edge-tts 口播 → mp3 + 音频时长 JSON
│   ├── render_loop.py       # 逐片渲染 + 失败自动修复循环
│   ├── mux.py               # ffmpeg 合成 → 最终 MP4
│   └── primitives/          # 图元库：预制 manim 组件模板
└── prompts/
    └── storyboard.md        # 分镜生成系统提示词（含 schema 与示例）
```

## 4. 组件规格

### 4.1 pdf2png.py（PDF 提取）

输入：PDF 路径；输出到论文工作目录 `~/manim_videos/<论文名>/` 下：

- `paper.txt`：全文文本（AI 阅读用）。扫描件走 OCR 兜底（与 pdf2zh_next 的 babeldoc/doclayout 思路一致，但实现从简：先 PyMuPDF 文本抽取，失败/空页再启用 OCR）
- `pages/p-<n>.png`：每页低清渲染（预览版，AI 选图用）
- `figures/`：按 bbox 高清裁剪的截图（AI 在分镜中给出 bbox 引用，脚本渲染高清版）

依赖：PyMuPDF（fitz）。装进 `~/.master_env`（复用现有环境；如冲突则独立 venv，待实现时验证）。

### 4.2 storyboard.json（分镜 schema）

```json
{
  "paper": {"title": "…", "authors": "…", "lang": "en"},
  "mode": "single | compare",
  "scenes": [
    {
      "id": "s1-title",
      "title": "开场",
      "type": "title",
      "narration_zh": "口播文案（同时作为中文字幕）",
      "subtitle_en": "英文对照字幕",
      "shots": [
        {
          "kind": "formula | figure_zoom | axis | diagram | text | transition",
          "intent": "动画意图描述（AI 生成场景代码的依据）",
          "primitives": ["标题页", "截图浮层"],
          "fig_ref": "figures/fig-3-2.png | null",
          "figure_origin": "§3.2 Fig.3 | null",
          "formulas": ["e^{i\\pi}+1=0"]
        }
      ]
    }
  ]
}
```

约束：每镜头口播 15-60 秒；AI 分镜时保证（过长/过短由 tts_align 检出并报错要求重分段）。

对比模式（mode: "compare"）分镜组织约定：scenes 按「论文 A 核心 → 论文 B 核心 → 对比段落（异同/演进关系）」编排，schema 其余字段复用；对比段落的具体镜头模板（并排对比图、差异高亮）在实现计划中细化。

### 4.3 tts_align.py（口播）

- 每镜头 narration_zh → edge-tts（`~/.master_env/bin/edge-tts`）→ `audio/<scene>-<shot>.mp3`
- 输出 `durations.json`：每镜头音频时长
- 时长校验：<2s 或 >90s → 报错列出，AI 重新分段后重跑
- 动画时长对齐规则：镜头动画总时长 = 音频时长 + 0.5s 余量；动画本身长于音频时压缩 wait，短于时补 `Wait`

### 4.4 图元库 primitives/（关键可靠性设计）

预制 manim 组件模板（函数/类），AI 组装而非裸写：

| 组件 | 用途 |
|---|---|
| `title_page` | 标题页：论文标题 + 作者 + 场景标题 |
| `formula_derive` | 公式逐步推导（逐项 Write/Transform） |
| `figure_zoom` | 论文截图浮层：白卡片 + 原文位置标注（Fig.1 / §3.2） |
| `axis_plot` | 坐标轴 + 函数曲线/散点（实验数据展示） |
| `diagram_flow` | 流程图/架构图（方法讲解） |
| `highlight_annotation` | 箭头/高亮标注 |
| `progress_bar` | 底部进度条（章节指示） |
| `text_note` | 要点文字卡片 |
| `make_subtitle` | 底部双语字幕（中文+英文双行，烧录进画面；每个镜头必加） |

每个组件：输入（标题、内容、位置等参数）+ 对应 manim 代码模板 + 渲染一帧的验证脚本。

### 4.5 render_loop.py（渲染 + 修复循环）

- 每场景一个 Scene 文件（`scenes/scene-<n>.py`），分片渲染、失败隔离
- 流程：`-ql` 预览渲染 → 失败 → 收集报错 + 代码片段 → AI 修复（最多 3 次）→ 重试；3 次失败 → 该片降级为「口播 + 论文截图 + 字幕」静态页，不阻塞整片
- 预览全部通过 → 高质量渲染（默认 1080p30）
- 断点续跑：检查已有 clip 跳过已完成场景

### 4.6 mux.py（合成）

- 各场景 clip + 对应 mp3 → ffmpeg 拼接（concat demuxer）+ 音轨合成（aac）
- 视频流 `-c:v copy`（各 clip 参数一致），音频转 aac
- 输出：`~/manim_videos/<论文名>/<论文名>.mp4`
- 音频总长 > 视频时打印警告（提示场景 wait 未对齐音频）

> **实现时发现并调整**：字幕不由 mux 烧录，而是由 **manim 直接渲染进画面**（图元库 `make_subtitle`，白字黑描边双层叠加——manim 0.20 的 Text stroke 会吞掉 fill，故用底层黑字放大 1.06 作描边）。原因：本机 brew ffmpeg 8.1.1 未编译 libass 且无 drawtext 滤镜，`subtitles=` 滤镜不可用。字幕渲染进画面同时天然满足「任何播放器打开即看」。AI 生成场景代码时**必须**为每个镜头添加 `make_subtitle`（中文+英文双行），镜头切换时 FadeOut/FadeIn。

## 5. 数据流要点

1. TTS 在渲染之前：动画时长由音频时长驱动，预览即终稿
2. 文本提取 + 截图只做一次，分镜阶段不再重复读 PDF
3. 每篇论文独立工作目录，中途可续跑

## 6. 错误处理汇总

| 场景 | 处理 |
|---|---|
| manim 渲染失败 | 修复循环 ≤3 次 → 降级静态页 |
| 口播过长/过短 | tts_align 检出 → AI 重分段 |
| 截图裁剪失败/区域空 | 回退全页截图 → 回退纯动画无图 |
| 扫描件无文本 | OCR 兜底 |
| 长视频渲染时间 | 分片渲染 + 中途发现问题；-ql 预览先行 |

## 7. 测试与验收

1. 图元库组件逐个渲染单帧验证
2. 脚本单测：截图 bbox、音频时长对齐、合成时长一致性
3. 端到端：用户指定一篇熟悉论文跑通全流程，产出 1080p30 MP4，验证：口播对齐、双语字幕、论文截图浮层正确
4. 修复循环：故意注入一个渲染错误，验证自动修复与降级路径

## 8. 边界（YAGNI，不做）

- 不做 URL 输入（仅本地 PDF）
- 不做多语言配音（仅中文口播 + 英文字幕对照）
- 不做视频剪辑软件导出格式
- 不做在线分享
- 不做对比模式之外的联合分析

## 9. 依赖清单

- `~/.master_env`：manim（已装 0.20.1）、PyMuPDF（已装 1.27）、edge-tts（已装 7.2.8）、jsonschema（已装）
- 系统：ffmpeg（已装 8.1.1，**无 libass/drawtext 滤镜**——字幕因此由 manim 渲染进画面）、LaTeX（BasicTeX 2026，`tlmgr install standalone` 已补）、dvisvgm（brew 3.6 + `~/.local/bin/dvisvgm` wrapper 注入 `TEXMFCNF`/`TEXMFROOT` 指向 BasicTeX，否则 kpathsea 找不到字体树）
- uv：仅用 `uv pip`（CLAUDE.md 规定）
