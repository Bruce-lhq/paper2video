# paper2video · 论文精讲视频生成器

> 把论文 PDF 自动做成 3b1b 深色风精讲视频：核心公式逐步推导、关键处浮出论文原图、中文口播 + 中英双语字幕烧录进画面。时长随论文体量自适应（短文数分钟，长文可达 30 分钟）。全自动执行，不打断用户。

一个 Agent Skill，适用于任何支持 skills 的 AI 编码助手。

## 效果展示

**Attention Is All You Need** 全片精讲（中文口播 + 双语字幕 + 公式推导动画 + 论文原图浮层）：

<video src="https://github.com/user-attachments/assets/f971a857-0f0a-45ef-ac64-d461803fabba" controls muted width="100%"></video>

## 解决什么问题

读论文最耗时的不是"看"，而是"讲清楚"：核心公式的推导链条、符号约定、和前人工作的关系。paper2video 把这个过程产品化——你给一篇 PDF，它产出一条可以直接分享的视频，推导动画对齐口播节奏，关键页面自动浮出原文对照。

## 工作流程

```
PDF ──► pdf2png 提取原文页面
   ──► AI 分镜（storyboard，含公式推导脚本，JSON schema 校验）
   ──► edge-tts 中文口播 + 字幕时间戳对齐
   ──► manim 逐镜渲染（3b1b 深色风、Tex 公式、原图浮层）
   ──► ffmpeg 合成 + 字幕烧录
```

## 安装

**安装 skill：**

```bash
npx skills add Bruce-lhq/paper2video
```

**Python 依赖：**

```bash
pip install -r requirements.txt
```

**系统依赖**：`ffmpeg`、TeX 发行版（含 `dvisvgm`，公式渲染用）、manim 的系统级依赖见 [manim 文档](https://docs.manim.community/en/stable/installation.html)。

## 使用示例

对 AI 编码助手说：

> 帮我把 ~/papers/attention-is-all-you-need.pdf 做成一个精讲视频

或多篇对比：

> 把这两篇论文做成对比讲解视频

## 目录结构

```
SKILL.md            # skill 主文件（流程编排与环境配置）
tools/              # pdf2png / storyboard schema 校验 / tts 对齐 / manim 渲染 / 合成
prompts/            # 分镜生成提示词
docs/               # 设计文档
```

## License

[MIT](LICENSE) © 2026 Haoqi Li
