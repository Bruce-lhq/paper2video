"""primitives — paper2video 图元库：预制 manim 组件。

AI 生成场景代码时组装这些组件，不裸写动画。约定：
- make_*：构造 mobject（纯构造，不进场景）
- animate_*(scene, ...)：在 scene 上播放动画
- 全部 Text 已设置 FONT（macOS PingFang SC），中文直接可用
- 背景默认 manim 深色（#1e1e1e），即 3b1b 风

用法（场景文件）：
    from manim import *
    from primitives import make_title, animate_title, make_formula_tex, ...

    class S1(Scene):
        def construct(self):
            g = make_title("标题", subtitle="副标题")
            animate_title(self, g)
"""
from pathlib import Path

from manim import *  # noqa: F401,F403 — manim 全局符号（Scene/Text/...）

FONT = "PingFang SC"  # macOS 中文字体


# ---------- 1. 标题页 ----------

def make_title(title, subtitle=None, authors=None):
    """论文标题页。subtitle/authors 为可选中英文行。"""
    parts = [Text(title, font=FONT, color=WHITE, font_size=54, weight=BOLD)]
    if subtitle:
        parts.append(Text(subtitle, font=FONT, color=GREY_B, font_size=30))
    if authors:
        parts.append(Text(authors, font=FONT, color=GREY, font_size=24))
    group = VGroup(*parts).arrange(DOWN, buff=0.4)
    return group


def animate_title(scene, group, run_time=2.0):
    scene.play(Write(group), run_time=run_time)


# ---------- 2. 公式逐步推导 ----------

def make_formula_tex(*tex_parts):
    """构造 MathTex。多个 part 按顺序逐步出现（animate_formula_derive 用）。"""
    return MathTex(*tex_parts)


def animate_formula_derive(scene, formula, highlight_color=YELLOW,
                           run_time_per=1.0, buff=0.3):
    """公式逐项出现；可选高亮当前项。"""
    for i, part in enumerate(formula):
        scene.play(Write(part), run_time=run_time_per)
        if i < len(formula) - 1:
            scene.wait(buff)


def animate_formula_highlight(scene, formula, part_index, color=YELLOW):
    """高亮公式第 part_index 项（0 起）。"""
    formula[part_index].set_color(color)
    scene.play(formula[part_index].animate.set_color(color))


# ---------- 3. 论文截图浮层 ----------

def make_figure_card(image_path, caption=None, origin_label=None,
                     max_width=4.5, max_height=2.8):
    """论文原图浮层：白底卡片 + 截图 + 底部原文位置标注。origin_label 如 '§3.2 Fig.3'。"""
    img = ImageMobject(image_path)  # 默认 BICUBIC 重采样，width/height 宽高比正确
    if img.width / img.height > max_width / max_height:
        img.width = max_width
    else:
        img.height = max_height
    card = SurroundingRectangle(img, color=WHITE, buff=0.12,
                                corner_radius=0.05, stroke_width=2)
    group = Group(card, img)  # Group：ImageMobject 非 VMobject，不能进 VGroup
    if caption or origin_label:
        bottom_lines = []
        if caption:
            bottom_lines.append(Text(caption, font=FONT, color=WHITE, font_size=22))
        if origin_label:
            bottom_lines.append(Text(origin_label, font=FONT, color=GREY, font_size=18))
        labels = VGroup(*bottom_lines).arrange(DOWN, buff=0.1).next_to(card, DOWN, buff=0.15)
        group = Group(group, labels)
    return group


def animate_figure_zoom(scene, card, run_time=1.2):
    """截图浮层浮现：放大渐入。"""
    card.scale(0.1)
    scene.play(card.animate.scale(10.0), run_time=run_time)
    scene.wait(0.3)


# ---------- 4. 坐标轴与曲线 ----------

def make_axis(x_range=(-4, 4, 1), y_range=(-3, 3, 1), x_label="x", y_label="y"):
    """数轴。labels 为中文或 LaTeX 字符串。"""
    axes = Axes(x_range=x_range, y_range=y_range,
                axis_config={"include_tip": True, "stroke_width": 2})
    labels = axes.get_axis_labels(x_label, y_label)
    group = VGroup(axes, labels)
    group.scale_to_fit_width(10.0)
    return group


def animate_plot_curve(scene, axes, func, x_range=None, color=YELLOW,
                       run_time=1.5):
    """在 axes 上画函数曲线。func 接收 x 返回 y（numpy 风格）。"""
    if x_range is None:
        x_range = [axes.x_range[0], axes.x_range[1]]
    curve = axes.plot(func, x_range=x_range, color=color, stroke_width=3)
    scene.play(Create(curve), run_time=run_time)


def animate_plot_scatter(scene, axes, points, color=RED, run_time=1.2):
    """在 axes 上画散点。points: [(x, y), ...]（数据坐标）。"""
    dots = VGroup(*[Dot(axes.coords_to_point(x, y), color=color, radius=0.07)
                    for x, y in points])
    scene.play(Create(dots), run_time=run_time)


# ---------- 5. 流程图 / 架构图 ----------

def make_flow(items, direction=RIGHT, box_width=2.2, box_height=0.8):
    """流程/架构图。items: [(标签, 颜色), ...] → 带箭头的框链。"""
    boxes = VGroup()
    for label, color in items:
        box = Rectangle(width=box_width, height=box_height,
                        color=color, stroke_width=2)
        text = Text(label, font=FONT, color=WHITE, font_size=20)
        boxes.add(VGroup(box, text))
    horizontal = direction is RIGHT
    boxes.arrange(direction, buff=0.9)
    arrows = VGroup()
    for a, b in zip(boxes[:-1], boxes[1:]):
        arrow = Arrow(a.get_right() if horizontal else a.get_bottom(),
                      b.get_left() if horizontal else b.get_top(),
                      color=GREY, stroke_width=2)
        arrows.add(arrow)
    return VGroup(boxes, arrows)


def animate_flow(scene, flow, run_time_per=0.6):
    """流程逐个出现。"""
    boxes, arrows = flow[0], flow[1]
    for i, (box, arrow) in enumerate(zip(boxes, [None] + list(arrows))):
        scene.play(Create(box), run_time=run_time_per)
        if arrow:
            scene.play(Create(arrow), run_time=run_time_per * 0.7)


# ---------- 6. 箭头 / 高亮标注 ----------

def make_annotation(target, text, color=YELLOW, direction=UP):
    """指向 target 的箭头 + 说明文字。direction: UP/DOWN/LEFT/RIGHT。"""
    label = Text(text, font=FONT, color=color, font_size=26)
    arrow = Arrow(direction * 1.2, ORIGIN, color=color, stroke_width=3)
    group = VGroup(label, arrow).arrange(direction, buff=0.15)
    group.next_to(target, direction, buff=0.4)
    return group


def animate_annotate(scene, annotation, run_time=0.8):
    scene.play(Write(annotation), run_time=run_time)


# ---------- 7. 章节进度条 ----------

def make_progress(section_label, index, total, width=11.0):
    """底部章节进度条。index/total 从 1 起。"""
    bar = Rectangle(width=width, height=0.05, color=GREY_B, stroke_width=0)
    filled = Rectangle(width=width * index / total, height=0.05,
                       color=YELLOW, stroke_width=0)
    filled.align_to(bar, LEFT).align_to(bar, UP)
    label = Text(section_label, font=FONT, color=GREY, font_size=18)
    label.next_to(bar, DOWN, buff=0.12)
    group = VGroup(bar, filled, label)
    group.to_edge(DOWN, buff=0.35)
    return group


def animate_progress(scene, progress, run_time=0.6):
    scene.play(Create(progress[1]), Write(progress[2]), run_time=run_time)


# ---------- 8. 字幕（烧录进画面） ----------

SUB_MAX_LINE_UNITS = 9.0  # 字幕行最大宽度（画面单位，屏幕宽 14.22，留余量）
CJK_W = 1.0               # 中文/全角字符估算宽（相对中文字宽）
ASCII_W = 0.62            # ASCII 估算宽（实测 0.55 低估导致英文行超屏）


def _char_w(ch: str, unit: float) -> float:
    return unit * (CJK_W if ord(ch) > 0x2E7F else ASCII_W)


def _wrap(text: str, font_size: int) -> str:
    """按估算宽度手动断行（manim 0.20 Text 无自动换行）。
    英文在词边界（空格）断行，不截断单词；中文按字符断。"""
    unit = font_size / 72.0  # 中文字符宽（画面单位，估算偏保守）
    lines, cur, cur_w = [], [], 0.0
    for ch in text:
        w = _char_w(ch, unit)
        if cur and cur_w + w > SUB_MAX_LINE_UNITS:
            line = "".join(cur)
            if ch.isascii() and not ch.isspace():
                last_space = line.rfind(" ")
                if last_space > 0:  # 回退到最近空格，保留完整单词
                    overflow = line[last_space + 1:]
                    lines.append(line[:last_space])
                    cur = list(overflow)
                    cur_w = sum(_char_w(c, unit) for c in overflow)
                    cur.append(ch)
                    cur_w += w
                    continue
            lines.append(line)
            cur, cur_w = [], 0.0
        cur.append(ch)
        cur_w += w
    if cur:
        lines.append("".join(cur))
    return "\n".join(lines)


def _text_layer(text, font_size):
    """单行文字（已断行）：底层黑色放大作描边 + 上层白色（manim 0.20 Text
    stroke 会吞 fill，故双层叠加）。"""
    text = _wrap(text, font_size)
    bg = Text(text, font=FONT, color=BLACK, font_size=font_size).scale(1.06)
    fg = Text(text, font=FONT, color=WHITE, font_size=font_size)
    return VGroup(bg, fg)


def make_subtitle(zh, en=None):
    """底部双语字幕（白字黑描边，双层叠加实现），渲染进画面，任何播放器可见。
    中文 24px / 英文 18px，自动断行（≤9 单位宽），贴在画面底部。
    兜底：个别行实际渲染仍超宽时缩到 9.5 单位（避免顶到屏幕边缘）。
    每个镜头按分镜添加；镜头切换时 FadeOut 旧字幕、FadeIn 新字幕。"""
    rows = [_text_layer(zh, 24)]
    if en:
        rows.append(_text_layer(en, 18))
    group = VGroup(*rows).arrange(DOWN, buff=0.06, aligned_edge=LEFT)
    for row in rows:
        for text_mob in row:
            if text_mob.width > 9.5:
                text_mob.set_max_width(9.5)
    group.to_edge(DOWN, buff=0.25)
    return group


def animate_subtitle(scene, sub, run_time=0.4):
    """字幕淡入淡出：先 fade in，结尾 fade out（供镜头切换用）。"""
    scene.play(FadeIn(sub, shift=UP * 0.05), run_time=run_time)


# ---------- 9. 要点文字卡片 ----------

def make_text_note(text, title=None, width=6.0, color=BLUE):
    """要点卡片：左侧色条 + 标题（可选）+ 正文。"""
    body = Text(text, font=FONT, color=WHITE, font_size=26,
                line_spacing=1.4).set_max_width(width)
    group = VGroup(body)
    if title:
        t = Text(title, font=FONT, color=color, font_size=30, weight=BOLD)
        group = VGroup(t, body).arrange(DOWN, buff=0.3)
    strip = Rectangle(width=0.12, height=group.height + 0.4,
                      color=color, fill_opacity=1.0, stroke_width=0)
    card = VGroup(strip, group).arrange(RIGHT, buff=0.35, aligned_edge=UP)
    return card


def animate_text_note(scene, note, run_time=1.0):
    scene.play(FadeIn(note, shift=UP * 0.2), run_time=run_time)


# ---------- 通用工具 ----------

def fit_card(card, max_width=8.5, max_height=3.2):
    """把任意组件缩放到画面安全区，略上移给底部字幕留空间。"""
    card.scale_to_fit_width(max_width)
    if card.height > max_height:
        card.scale_to_fit_height(max_height)
    return card.move_to(ORIGIN).shift(UP * 0.45)
