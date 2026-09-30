#!/usr/bin/env python3
"""pdf2png — paper2video 的 PDF 输入提取。

子命令：
  extract <pdf> -o <dir>     抽取全文文本 + 渲染页面预览图
     → <dir>/paper.txt       全文文本（AI 阅读用；扫描件会警告并尽量保留图片页说明）
     → <dir>/pages/p-<n>.png 每页低清预览图（AI 选图用）

  crop <pdf> --page N --bbox x0,y0,x1,y1 --name <n>
     -o <dir>                按 bbox（PDF 点坐标）高清裁剪页面区域
     → <dir>/figures/<n>.png （manim 截图浮层用）

用法示例：
  pdf2png.py extract paper.pdf -o out/
  pdf2png.py crop paper.pdf --page 3 --bbox "100,150,500,400" --name fig-3-1 -o out/
"""
import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

EMPTY_PAGE_CHARS = 20     # 文本少于该字符数视为空页（可能含图）
SCAN_WARN_RATIO = 0.3     # 空页占比超过该值提示可能是扫描件
PREVIEW_ZOOM = 2.0        # 页面预览图渲染倍率（72dpi 点 → 像素）
CROP_ZOOM = 3.0           # 截图渲染倍率（约 1785px 宽，适配 1080p 画面）


def paper_name(pdf_path: Path) -> str:
    return pdf_path.stem.strip()


def extract(pdf_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    texts, empty_pages = [], []
    for n, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        texts.append(text)
        if len(text) < EMPTY_PAGE_CHARS:
            empty_pages.append(n)
        pix = page.get_pixmap(matrix=fitz.Matrix(PREVIEW_ZOOM, PREVIEW_ZOOM))
        pix.save(pages_dir / f"p-{n}.png")

    (out_dir / "paper.txt").write_text(
        f"# {pdf_path.name}（共 {len(texts)} 页）\n\n"
        + "\n\n".join(f"## 第 {n} 页\n{t}" for n, t in enumerate(texts, start=1)),
        encoding="utf-8",
    )

    if empty_pages:
        ratio = len(empty_pages) / len(texts)
        mark = "（可能是扫描件，需 OCR）" if ratio >= SCAN_WARN_RATIO else ""
        print(f"警告：空页 {empty_pages}{mark}")

    print(f"完成：{len(texts)} 页文本 → {out_dir / 'paper.txt'}，"
          f"预览图 → {pages_dir}/")
    doc.close()


def crop(pdf_path: Path, page_no: int, bbox: tuple, name: str,
         out_dir: Path, zoom: float) -> None:
    doc = fitz.open(pdf_path)
    if not 1 <= page_no <= doc.page_count:
        raise SystemExit(f"错误：页码 {page_no} 超出范围（1-{doc.page_count}）")
    page = doc[page_no - 1]
    x0, y0, x1, y1 = bbox
    rect = fitz.Rect(x0, y0, x1, y1)
    if not (rect & page.rect).get_area() > 0:
        raise SystemExit(f"错误：bbox {bbox} 超出页面范围 {page.rect}")
    if rect.width <= 0 or rect.height <= 0:
        raise SystemExit(f"错误：bbox 宽高必须为正（{bbox}）")

    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect)
    out_path = figures_dir / f"{name}.png"
    pix.save(out_path)
    print(f"完成：{out_path}（{pix.width}x{pix.height}px）")
    doc.close()


def parse_bbox(raw: str) -> tuple:
    try:
        x0, y0, x1, y1 = (float(v) for v in raw.split(","))
    except ValueError:
        raise SystemExit(f"错误：无效 bbox '{raw}'（应为 x0,y0,x1,y1 四值逗号分隔）")
    return (x0, y0, x1, y1)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        prog="pdf2png",
        description="paper2video 的 PDF 输入提取：文本 + 页面预览图 + bbox 截图",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="抽取全文文本 + 渲染页面预览图")
    pe.add_argument("pdf", help="PDF 文件路径")
    pe.add_argument("-o", "--output", default=".",
                    help="输出目录（默认当前目录，输出到 <dir>/ 下）")

    pc = sub.add_parser("crop", help="按 bbox 裁剪页面区域为高清截图")
    pc.add_argument("pdf", help="PDF 文件路径")
    pc.add_argument("--page", type=int, required=True, help="页码（从 1 开始）")
    pc.add_argument("--bbox", required=True,
                    help="裁剪区域 'x0,y0,x1,y1'（PDF 点坐标）")
    pc.add_argument("--name", required=True, help="输出截图名（不含扩展名）")
    pc.add_argument("-o", "--output", default=".",
                    help="输出目录（截图写到 <dir>/figures/）")
    pc.add_argument("--zoom", type=float, default=CROP_ZOOM,
                    help=f"渲染倍率（默认 {CROP_ZOOM:g}）")

    args = p.parse_args(argv)
    if args.cmd == "extract":
        extract(Path(args.pdf), Path(args.output))
    else:
        crop(Path(args.pdf), args.page, parse_bbox(args.bbox), args.name,
             Path(args.output), args.zoom)


if __name__ == "__main__":
    sys.exit(main())
