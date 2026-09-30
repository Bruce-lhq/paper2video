"""verify_primitives — 图元库单帧验证：每个组件渲染一帧 PNG。

用法：
  manim -ql -s verify_primitives.py All
（Tex 公式场景需 dvisvgm 就绪；未就绪时单独验证场景会失败，其余不受影响）
"""
import sys
from pathlib import Path

from manim import *  # noqa: F401,F403

sys.path.insert(0, str(Path(__file__).parent))
from primitives import *  # noqa: F401,F403,E402

TEST_IMG = Path(__file__).parent / "verify_assets" / "fig-test.png"


class V1_Title(Scene):
    def construct(self):
        g = make_title("深度卷积神经网络在计算机视觉中的应用研究综述",
                       subtitle="A Survey of Deep CNNs in Computer Vision",
                       authors="张三 等 · 2016")
        animate_title(self, g)


class V2_Formula(Scene):
    def construct(self):
        f = make_formula_tex(r"e^{i\pi}", r" + 1", r" = 0")
        animate_formula_derive(self, f)


class V3_Figure(Scene):
    def construct(self):
        if not TEST_IMG.exists():
            self.wait(0.1)
            return
        card = make_figure_card(str(TEST_IMG), caption="卷积网络结构示意",
                                origin_label="§2.2 Fig.3")
        animate_figure_zoom(self, fit_card(card))


class V4_Axis(Scene):
    def construct(self):
        axes = make_axis()
        animate_plot_curve(self, axes, lambda x: x ** 2)
        animate_plot_scatter(self, axes, [(-2, 4), (1, 1), (2, 4)])


class V5_Flow(Scene):
    def construct(self):
        flow = make_flow([("输入图像", BLUE), ("卷积层", GREEN),
                          ("池化层", GREEN), ("全连接", ORANGE), ("输出", RED)])
        animate_flow(self, fit_card(flow))


class V6_Annotation(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        self.play(Create(circle))
        ann = make_annotation(circle, "这就是卷积核", color=YELLOW, direction=UP)
        animate_annotate(self, ann)


class V7_Progress(Scene):
    def construct(self):
        p = make_progress("§3 方法", 3, 5)
        animate_progress(self, p)


class V8_Note(Scene):
    def construct(self):
        note = make_text_note("卷积核共享参数，大幅减少参数量",
                              title="核心思想", color=GREEN)
        animate_text_note(self, fit_card(note))
