"""
nonebot_plugin_nbnhhsh.render
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
把翻译结果绘制成一张图片。

直接使用 Pillow 绘制结果图片，渲染只需要 Pillow 和一份中文字体。

字体优先级：系统里已有的中文字体 → 缓存目录里下载过的 → 从内置镜像下载。
全都拿不到时抛 :class:`RuntimeError`，由调用方决定怎么兜底。

绘制是同步阻塞的 CPU 活，调用方必须走 :func:`text_to_image`（内部放进线程池），
否则会卡住事件循环。
"""

from __future__ import annotations

import io
import re
import asyncio
import logging
import threading
from typing import Any
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger("nonebot_plugin_nbnhhsh.render")

# ── 版面参数 ────────────────────────────────────────────────────────────────
# 数值沿用原布局的 CSS 像素，输出图宽度与旧版一致（720px）。
# 内部按 SUPERSAMPLE 倍绘制再缩回来，文字边缘比直接按 1 倍画干净。

SUPERSAMPLE = 2
PAGE_WIDTH = 720
PAGE_PADDING = 24
PANEL_PADDING = 18
PANEL_RADIUS = 20
PANEL_BORDER = 2
PANEL_SHADOW_BLUR = 12
PANEL_SHADOW_OFFSET = 10
PANEL_SHADOW_ALPHA = 26

HEADING_SIZE = 22
HEADING_WEIGHT = 800
HEADING_GAP = 6
DESC_SIZE = 12
DESC_WEIGHT = 500
DESC_GAP = 14
ABBR_SIZE = 26
ABBR_WEIGHT = 800
ABBR_GAP = 12
MEANING_SIZE = 16
MEANING_WEIGHT = 500
MEANING_PAD_X = 16
MEANING_PAD_Y = 10
MEANING_GAP = 10
MEANING_TOP_GAP = 16
TEXT_SIZE = 16
TEXT_WEIGHT = 500
TEXT_LINE_HEIGHT = 1.6
TEXT_GAP = 12
NORMAL_LINE_HEIGHT = 1.2

PAGE_BG = (255, 248, 241)  # #fff8f1
PANEL_BG = (255, 253, 249)  # #fffdf9
PANEL_EDGE = (255, 215, 168)  # #ffd7a8
SHADOW_RGB = (180, 118, 33)
HEADING_FG = (180, 83, 9)  # #b45309
DESC_FG = (146, 64, 14)  # #92400e
ABBR_FG = (194, 65, 12)  # #c2410c
TEXT_FG = (43, 43, 43)  # #2b2b2b

HEADING_TEXT = "能不能好好说话？"
DESC_TEXT = "数据源： 神奇的海螺"

# 中文字体候选：系统里已有的直接用，省一次下载。
SYSTEM_FONTS: tuple[str, ...] = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)

# 下载地址（按顺序尝试），要的是带中文的字体。
FONT_URLS: tuple[str, ...] = (
    "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosanssc/"
    "NotoSansSC%5Bwght%5D.ttf",
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/"
    "NotoSansSC%5Bwght%5D.ttf",
    "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
)

FONT_FILENAME = "NotoSansSC.ttf"
FONT_MIN_BYTES = 1_000_000

# ``[缩写] 释义1、释义2`` 形式的行，其余行按普通文本画。
_ABBR_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s*(?P<rest>.*)$")
# 折行的最小单元：连续字母数字算一个词，其余（含中文）逐字处理。
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|\s+|.", re.DOTALL)

# 运行时找到的字体文件（系统字体或下载缓存）。
_FONT_PATH: Path | None = None
_FONT_LOCK = threading.Lock()


def _cache_dir() -> Path:
    """返回字体缓存目录。

    Returns:
        用户缓存目录下的插件专属目录；platformdirs 缺失时退回 ``~/.cache``。
    """
    try:
        from platformdirs import user_cache_dir
    except ImportError:  # pragma: no cover - platformdirs 是硬依赖，防御性分支
        return Path.home() / ".cache" / "nonebot-plugin-nbnhhsh"
    return Path(user_cache_dir("nonebot-plugin-nbnhhsh"))


def _is_font_file(path: Path) -> bool:
    """检查缓存文件是否能被 Pillow 打开。"""
    try:
        from PIL import ImageFont

        ImageFont.truetype(str(path), 16)
    except (ImportError, OSError, ValueError):
        return False
    return True


def _download_font(target: Path) -> bool:
    """从内置镜像下载字体到 ``target``。

    Args:
        target: 目标文件路径。

    Returns:
        下载成功（文件大小合理）时为 ``True``。
    """
    import httpx

    for url in FONT_URLS:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with httpx.stream("GET", url, timeout=120, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    continue
                tmp = target.with_suffix(".part")
                with tmp.open("wb") as handle:
                    for chunk in resp.iter_bytes(1 << 16):
                        handle.write(chunk)
            if tmp.stat().st_size < FONT_MIN_BYTES:
                tmp.unlink(missing_ok=True)
                continue
            tmp.replace(target)
        except Exception as exc:
            logger.warning(f"[nbnhhsh] 字体下载失败 {url}: {exc}")
            continue
        logger.info(f"[nbnhhsh] 字体已下载 {target}")
        return True
    return False


def ensure_font() -> Path:
    """确保有一份可用的中文字体。

    顺序：系统字体 → 缓存目录里已下载的 → 现场下载。

    Returns:
        字体文件路径。

    Raises:
        RuntimeError: 三种途径都没拿到字体。
    """
    global _FONT_PATH
    if _FONT_PATH is not None and _is_font_file(_FONT_PATH):
        return _FONT_PATH

    # 多个事件同时首次触发图片渲染时，只允许一个线程下载字体。
    with _FONT_LOCK:
        if _FONT_PATH is not None and _is_font_file(_FONT_PATH):
            return _FONT_PATH

        for candidate in SYSTEM_FONTS:
            candidate_path = Path(candidate)
            if candidate_path.is_file() and _is_font_file(candidate_path):
                logger.info(f"[nbnhhsh] 使用系统字体 {candidate}")
                _FONT_PATH = candidate_path
                return _FONT_PATH

        cached = _cache_dir() / FONT_FILENAME
        if cached.is_file() and _is_font_file(cached):
            _FONT_PATH = cached
            return cached

        if _download_font(cached):
            _FONT_PATH = cached
            return cached

    raise RuntimeError(
        "没有可用的中文字体：系统里没有，下载也失败了。"
        "装一个中文字体（如 fonts-noto-cjk），或让缓存目录可写后重试。"
    )


@lru_cache(maxsize=32)
def _font(size: int, weight: int = 400) -> Any:
    """按字号和字重取字体对象（带缓存）。

    Args:
        size: 字号（像素）。
        weight: 字重，可变字体支持 100-900。

    Returns:
        Pillow 的字体对象。
    """
    from PIL import ImageFont

    font = ImageFont.truetype(str(ensure_font()), size)
    try:
        font.set_variation_by_axes([weight])
    except Exception:
        pass
    return font


def _line_height(font: Any) -> int:
    """取字体的行高。

    Args:
        font: 字体对象。

    Returns:
        上升部与下降部之和。
    """
    ascent, descent = font.getmetrics()
    return ascent + descent


def _text_top(font: Any, line_h: int) -> int:
    """算出让文字在行盒里垂直居中的偏移。

    Args:
        font: 字体对象。
        line_h: 行盒高度。

    Returns:
        相对行盒顶部的绘制偏移。
    """
    ascent, descent = font.getmetrics()
    return max(0, (line_h - ascent - descent) // 2)


def wrap(text: str, font: Any, max_width: int) -> list[str]:
    """按宽度折行：中文逐字断，英文单词整体挪到下一行。

    Args:
        text: 原始文本（不含换行）。
        font: 字体对象。
        max_width: 每行最大像素宽度。

    Returns:
        折行后的文本列表；空文本返回空列表。
    """
    lines: list[str] = []
    current = ""
    for token in _TOKEN_RE.findall(text):
        if font.getlength(current + token) <= max_width:
            current += token
            continue
        if current.strip():
            lines.append(current.rstrip())
        current = ""
        if token.isspace():
            continue
        if font.getlength(token) <= max_width:
            current = token
            continue
        # 单个词就超过一行宽度：只能按字符硬切
        piece = ""
        for char in token:
            if font.getlength(piece + char) <= max_width:
                piece += char
            else:
                lines.append(piece)
                piece = char
        current = piece
    if current.strip():
        lines.append(current.rstrip())
    return lines


def _parse(text: str) -> list[tuple[str, str, list[str]]]:
    """把 ``format_result`` 的输出拆成绘制块。

    Args:
        text: 多行文本，形如 ``[yyds] 永远的神、永远单身``。

    Returns:
        ``(kind, 内容, 释义列表)`` 列表；``kind`` 取 ``abbr`` 或 ``text``。
    """
    blocks: list[tuple[str, str, list[str]]] = []
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        matched = _ABBR_RE.match(line)
        if matched:
            meanings = [
                item.strip()
                for item in matched.group("rest").split("、")
                if item.strip()
            ]
            blocks.append(("abbr", matched.group("name"), meanings))
        else:
            blocks.append(("text", line, []))
    return blocks


def _pack_meanings(
    meanings: list[str],
    font: Any,
    max_width: int,
    *,
    scale: int = 1,
) -> list[list[tuple[str, int]]]:
    """把释义条目排成若干行（对应原 CSS 的 flex-wrap）。

    Args:
        meanings: 释义文本列表。
        font: 释义字体。
        max_width: 面板内容区宽度。
        scale: 当前绘制使用的超采样倍数。

    Returns:
        每行是 ``(文本, 宽度)`` 列表；宽度含条目自身的左右内边距。
    """
    rows: list[list[tuple[str, int]]] = []
    row: list[tuple[str, int]] = []
    used = 0
    horizontal_padding = MEANING_PAD_X * 2 * scale
    gap = MEANING_GAP * scale
    text_width = max(1, max_width - horizontal_padding)
    for meaning in meanings:
        lines = wrap(meaning, font, text_width)
        measured_width = max(
            (int(font.getlength(line)) for line in lines),
            default=0,
        )
        width = min(max_width, measured_width + horizontal_padding)
        if row and used + gap + width > max_width:
            rows.append(row)
            row, used = [], 0
        if row:
            used += gap
        row.append((meaning, width))
        used += width
    if row:
        rows.append(row)
    return rows


def _meaning_row_height(
    row: list[tuple[str, int]],
    font: Any,
    max_width: int,
    line_height: int,
    scale: int,
) -> int:
    """返回一行释义条目所需的高度。"""
    text_width = max(1, max_width - MEANING_PAD_X * 2 * scale)
    padding = MEANING_PAD_Y * 2 * scale
    return max(
        (
            len(wrap(meaning, font, text_width)) * line_height + padding
            for meaning, _width in row
        ),
        default=line_height + padding,
    )


def _render(text: str) -> bytes:
    """把文本画成 PNG（同步阻塞，调用方放线程池）。

    Args:
        text: ``core.format_result`` 的输出。

    Returns:
        PNG 字节。

    Raises:
        RuntimeError: 没有可用的中文字体。
    """
    from PIL import Image, ImageDraw, ImageFilter

    scale = SUPERSAMPLE
    heading_font = _font(HEADING_SIZE * scale, HEADING_WEIGHT)
    desc_font = _font(DESC_SIZE * scale, DESC_WEIGHT)
    abbr_font = _font(ABBR_SIZE * scale, ABBR_WEIGHT)
    meaning_font = _font(MEANING_SIZE * scale, MEANING_WEIGHT)
    text_font = _font(TEXT_SIZE * scale, TEXT_WEIGHT)

    page_pad = PAGE_PADDING * scale
    panel_pad = PANEL_PADDING * scale
    border = PANEL_BORDER * scale
    panel_width = PAGE_WIDTH * scale - page_pad * 2
    inner_width = panel_width - (panel_pad + border) * 2

    # CSS 的 ``normal`` 行高约为字号的 1.2 倍；直接使用 Pillow 的
    # ascent + descent 会把面板撑得比原布局高一截。
    heading_h = round(HEADING_SIZE * NORMAL_LINE_HEIGHT) * scale
    desc_h = round(DESC_SIZE * NORMAL_LINE_HEIGHT) * scale
    abbr_h = round(ABBR_SIZE * NORMAL_LINE_HEIGHT) * scale
    meaning_h = round(MEANING_SIZE * NORMAL_LINE_HEIGHT) * scale
    meaning_row_gap = MEANING_GAP * scale
    text_line_h = round(TEXT_SIZE * TEXT_LINE_HEIGHT) * scale

    # 第一遍：量出每块高度，算出面板总高
    laid: list[tuple[str, Any, int]] = []
    height = heading_h + HEADING_GAP * scale + desc_h + DESC_GAP * scale
    for kind, content, meanings in _parse(text):
        if kind == "abbr":
            abbr_lines = wrap(content, abbr_font, inner_width)
            rows = _pack_meanings(
                meanings,
                meaning_font,
                inner_width,
                scale=scale,
            )
            laid.append(("abbr", (abbr_lines, rows), 0))
            height += len(abbr_lines) * abbr_h
            if rows:
                height += MEANING_TOP_GAP * scale
                height += sum(
                    _meaning_row_height(
                        row,
                        meaning_font,
                        inner_width,
                        meaning_h,
                        scale,
                    )
                    for row in rows
                )
                height += (len(rows) - 1) * meaning_row_gap
            height += ABBR_GAP * scale
        else:
            lines = wrap(content, text_font, inner_width)
            laid.append(("text", lines, 0))
            height += len(lines) * text_line_h + TEXT_GAP * scale

    panel_h = height + panel_pad * 2
    image_w = PAGE_WIDTH * scale
    image_h = panel_h + page_pad * 2

    canvas = Image.new("RGBA", (image_w, image_h), (*PAGE_BG, 255))

    # 面板阴影：单独画一层再模糊，比直接描边自然
    shadow = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (
            page_pad,
            page_pad + PANEL_SHADOW_OFFSET * scale,
            page_pad + panel_width,
            page_pad + panel_h + PANEL_SHADOW_OFFSET * scale,
        ),
        radius=PANEL_RADIUS * scale,
        fill=(*SHADOW_RGB, PANEL_SHADOW_ALPHA),
    )
    canvas.alpha_composite(
        shadow.filter(ImageFilter.GaussianBlur(PANEL_SHADOW_BLUR * scale))
    )

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (page_pad, page_pad, page_pad + panel_width, page_pad + panel_h),
        radius=PANEL_RADIUS * scale,
        fill=(*PANEL_BG, 255),
        outline=(*PANEL_EDGE, 255),
        width=border,
    )

    left = page_pad + panel_pad + border
    y = page_pad + panel_pad

    draw.text(
        (left, y + _text_top(heading_font, heading_h)),
        HEADING_TEXT,
        font=heading_font,
        fill=HEADING_FG,
    )
    y += heading_h + HEADING_GAP * scale
    draw.text(
        (left, y + _text_top(desc_font, desc_h)),
        DESC_TEXT,
        font=desc_font,
        fill=DESC_FG,
    )
    y += desc_h + DESC_GAP * scale

    for kind, payload, _unused in laid:
        if kind == "abbr":
            abbr_lines, rows = payload
            for line in abbr_lines:
                draw.text(
                    (left, y + _text_top(abbr_font, abbr_h)),
                    line,
                    font=abbr_font,
                    fill=ABBR_FG,
                )
                y += abbr_h
            if rows:
                y += MEANING_TOP_GAP * scale
                for row in rows:
                    x = left
                    row_height = _meaning_row_height(
                        row,
                        meaning_font,
                        inner_width,
                        meaning_h,
                        scale,
                    )
                    for meaning, width in row:
                        lines = wrap(
                            meaning,
                            meaning_font,
                            max(1, inner_width - MEANING_PAD_X * 2 * scale),
                        )
                        for line_index, line in enumerate(lines):
                            draw.text(
                                (
                                    x + MEANING_PAD_X * scale,
                                    y
                                    + MEANING_PAD_Y * scale
                                    + line_index * meaning_h
                                    + _text_top(meaning_font, meaning_h),
                                ),
                                line,
                                font=meaning_font,
                                fill=DESC_FG,
                            )
                        x += width + MEANING_GAP * scale
                    y += row_height + meaning_row_gap
                y -= meaning_row_gap
            y += ABBR_GAP * scale
        else:
            for line in payload:
                draw.text(
                    (left, y + _text_top(text_font, text_line_h)),
                    line,
                    font=text_font,
                    fill=TEXT_FG,
                )
                y += text_line_h
            y += TEXT_GAP * scale

    final = canvas.convert("RGB").resize(
        (PAGE_WIDTH, image_h // scale), Image.Resampling.LANCZOS
    )
    buffer = io.BytesIO()
    final.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


async def text_to_image(text: str) -> bytes:
    """将文本渲染为 PNG 图片。

    Args:
        text: 要渲染的文本，通常来自 ``core.format_result``。

    Returns:
        PNG 格式的图片字节。

    Raises:
        RuntimeError: 没有可用的中文字体。
    """
    return await asyncio.to_thread(_render, text)
