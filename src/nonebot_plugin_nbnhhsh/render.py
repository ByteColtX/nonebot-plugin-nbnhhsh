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
PAGE_PADDING_X = 48
PAGE_PADDING_TOP = 42
PAGE_PADDING_BOTTOM = 48

HEADER_ICON_SIZE = 52
HEADER_ICON_INSET = 7
HEADER_ICON_GAP = 14
HEADING_SIZE = 23
HEADING_WEIGHT = 650
HEADING_GAP = 5
DESC_SIZE = 12
DESC_WEIGHT = 400
DESC_GAP = 26
ABBR_SIZE = 22
ABBR_WEIGHT = 600
ABBR_META_SIZE = 11
ABBR_META_WEIGHT = 400
MEANING_SIZE = 15
MEANING_WEIGHT = 400
MEANING_LINE_HEIGHT = 1.35
MEANING_ROW_GAP = 7
MEANING_COLUMN_GAP = 20
MEANING_BULLET_SIZE = 5
MEANING_BULLET_GAP = 9
TEXT_SIZE = 16
TEXT_WEIGHT = 400
TEXT_LINE_HEIGHT = 1.55
ENTRY_TOP_PAD = 12
ENTRY_BOTTOM_PAD = 15
ENTRY_TITLE_GAP = 10
ENTRY_ACCENT_WIDTH = 4
ENTRY_ACCENT_RADIUS = 2
ENTRY_GAP = 19
ENTRY_DIVIDER_GAP = 15
NORMAL_LINE_HEIGHT = 1.2

PAGE_BG = (246, 247, 250)  # #f6f7fa
DIVIDER = (224, 227, 234)  # #e0e3ea
HEADING_FG = (29, 31, 38)  # #1d1f26
DESC_FG = (112, 116, 126)  # #70747e
ABBR_FG = (35, 38, 48)  # #232630
TEXT_FG = (57, 61, 72)  # #393d48
ICON_HALO = (255, 255, 255)
ICON_HALO_EDGE = (232, 235, 242)
RAINBOW_ACCENTS: tuple[tuple[int, int, int], ...] = (
    (235, 103, 158),  # pink
    (244, 165, 76),  # orange
    (67, 177, 157),  # green
    (86, 133, 224),  # blue
    (157, 105, 210),  # purple
)
SINGLE_ACCENT = RAINBOW_ACCENTS[0]

HEADING_TEXT = "能不能好好说话？"
DESC_TEXT = "数据源：神奇的海螺"

ICON_PATH = Path(__file__).with_name("assets") / "magiconch-favicon.ico"

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



def _ellipsize(text: str, font: Any, max_width: int) -> str:
    """在单行内截短文本，保证释义永远不会被折行。"""
    text = " ".join(text.replace("\n", " ").split())
    if max_width <= 0:
        return ""
    if font.getlength(text) <= max_width:
        return text

    ellipsis = "…"
    ellipsis_width = font.getlength(ellipsis)
    if ellipsis_width > max_width:
        return ellipsis

    left, right = 0, len(text)
    while left < right:
        middle = (left + right + 1) // 2
        candidate = text[:middle].rstrip() + ellipsis
        if font.getlength(candidate) <= max_width:
            left = middle
        else:
            right = middle - 1
    return text[:left].rstrip() + ellipsis


def _pack_meanings(
    meanings: list[str],
    font: Any,
    max_width: int,
    *,
    scale: int = 1,
) -> dict[str, Any]:
    """按宽度从短到长横向装行，并锁定等距栏位的起点。

    每个词条最多使用 5 个等宽栏位。短释义占一栏，长释义横跨多栏；
    下一条释义总是从下一个固定栏位开始，所以不同高度的行也能对齐。
    """
    if not meanings:
        meanings = ["暂无释义"]

    gap = MEANING_COLUMN_GAP * scale
    bullet_width = MEANING_BULLET_SIZE * scale + MEANING_BULLET_GAP * scale
    ordered = sorted(
        (" ".join(item.replace("\n", " ").split()) for item in meanings),
        key=lambda item: (font.getlength(item), item),
    )
    columns = min(5, len(ordered))
    slot_width = max(1.0, (max_width - gap * (columns - 1)) / columns)
    full_width = slot_width * columns + gap * (columns - 1)

    rows: list[list[tuple[str, int]]] = []
    row: list[tuple[str, int]] = []
    used_columns = 0
    for meaning in ordered:
        measured_width = font.getlength(meaning) + bullet_width
        span = columns
        for candidate in range(1, columns + 1):
            candidate_width = slot_width * candidate + gap * (candidate - 1)
            if measured_width <= candidate_width + 0.5:
                span = candidate
                break

        if measured_width > full_width + 0.5:
            display = _ellipsize(meaning, font, int(full_width - bullet_width))
            span = columns
        else:
            display = meaning

        if row and used_columns + span > columns:
            rows.append(row)
            row = []
            used_columns = 0
        item_width = round(slot_width * span + gap * (span - 1))
        row.append((display, item_width))
        used_columns += span

    if row:
        rows.append(row)
    return {"rows": rows}


def _accent_for(index: int, count: int) -> tuple[int, int, int]:
    """单词条用粉色，多词条沿彩虹顺序取色。"""
    if count <= 1:
        return SINGLE_ACCENT
    return RAINBOW_ACCENTS[index % len(RAINBOW_ACCENTS)]


@lru_cache(maxsize=4)
def _header_icon(size: int) -> Any:
    """读取并放大指定的 magiconch favicon。"""
    from PIL import Image

    try:
        with Image.open(ICON_PATH) as source:
            icon = source.convert("RGBA")
            return icon.resize((size, size), Image.Resampling.NEAREST)
    except (FileNotFoundError, OSError):
        return None


def _background(image_w: int, image_h: int, scale: int) -> Any:
    """绘制极浅的渐变光斑，给留白增加一点层次。"""
    from PIL import Image, ImageDraw, ImageFilter

    canvas = Image.new("RGBA", (image_w, image_h), (*PAGE_BG, 255))
    glow = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse(
        (-180 * scale, -130 * scale, 250 * scale, 250 * scale),
        fill=(210, 219, 255, 48),
    )
    draw.ellipse(
        (image_w - 250 * scale, -145 * scale, image_w + 80 * scale, 200 * scale),
        fill=(255, 221, 235, 42),
    )
    draw.ellipse(
        (
            image_w - 180 * scale,
            image_h - 170 * scale,
            image_w + 120 * scale,
            image_h + 100 * scale,
        ),
        fill=(209, 245, 235, 34),
    )
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(58 * scale)))

    # 两条几乎不可见的弧线只负责平衡右上和左下的空白，不形成边框。
    lines = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
    line_draw = ImageDraw.Draw(lines)
    line_draw.arc(
        (image_w - 180 * scale, -70 * scale, image_w + 90 * scale, 200 * scale),
        70,
        205,
        fill=(255, 255, 255, 72),
        width=max(1, scale),
    )
    line_draw.arc(
        (-125 * scale, image_h - 185 * scale, 110 * scale, image_h + 50 * scale),
        250,
        35,
        fill=(255, 255, 255, 54),
        width=max(1, scale),
    )
    canvas.alpha_composite(lines)
    return canvas


def _draw_icon_halo(canvas: Any, x: int, y: int, size: int, scale: int) -> None:
    """在标题处放置用户指定的 favicon。"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(canvas)
    draw.ellipse(
        (x, y, x + size, y + size),
        fill=(*ICON_HALO, 238),
        outline=(*ICON_HALO_EDGE, 220),
        width=max(1, scale),
    )
    icon = _header_icon(max(1, size - HEADER_ICON_INSET * 2 * scale))
    if icon is not None:
        canvas.alpha_composite(
            icon,
            (x + HEADER_ICON_INSET * scale, y + HEADER_ICON_INSET * scale),
        )


def _render(text: str) -> bytes:
    """把文本画成 PNG（同步阻塞，调用方放线程池）。"""
    from PIL import Image, ImageDraw

    scale = SUPERSAMPLE
    heading_font = _font(HEADING_SIZE * scale, HEADING_WEIGHT)
    desc_font = _font(DESC_SIZE * scale, DESC_WEIGHT)
    abbr_font = _font(ABBR_SIZE * scale, ABBR_WEIGHT)
    abbr_meta_font = _font(ABBR_META_SIZE * scale, ABBR_META_WEIGHT)
    meaning_font = _font(MEANING_SIZE * scale, MEANING_WEIGHT)
    text_font = _font(TEXT_SIZE * scale, TEXT_WEIGHT)

    page_left = PAGE_PADDING_X * scale
    page_top = PAGE_PADDING_TOP * scale
    content_width = PAGE_WIDTH * scale - page_left * 2
    header_icon_size = HEADER_ICON_SIZE * scale
    heading_h = round(HEADING_SIZE * NORMAL_LINE_HEIGHT) * scale
    desc_h = round(DESC_SIZE * NORMAL_LINE_HEIGHT) * scale
    abbr_h = round(ABBR_SIZE * NORMAL_LINE_HEIGHT) * scale
    abbr_meta_h = round(ABBR_META_SIZE * NORMAL_LINE_HEIGHT) * scale
    meaning_h = round(MEANING_SIZE * MEANING_LINE_HEIGHT) * scale
    text_line_h = round(TEXT_SIZE * TEXT_LINE_HEIGHT) * scale
    header_text_h = heading_h + HEADING_GAP * scale + desc_h
    header_h = max(header_icon_size, header_text_h)

    blocks = _parse(text)
    block_count = sum(kind == "abbr" for kind, _content, _meanings in blocks)
    if block_count == 0:
        block_count = len(blocks)

    laid: list[tuple[str, dict[str, Any]]] = []
    content_y = header_h + DESC_GAP * scale
    total_height = content_y
    for block_index, (kind, content, meanings) in enumerate(blocks):
        if block_index:
            total_height += ENTRY_GAP * scale

        if kind == "abbr":
            grid_width = content_width - (ENTRY_ACCENT_WIDTH + 18) * scale
            grid = _pack_meanings(meanings, meaning_font, grid_width, scale=scale)
            entry_title_h = abbr_h + 2 * scale + abbr_meta_h
            row_count = len(grid["rows"])
            grid_h = row_count * meaning_h + max(
                0, row_count - 1
            ) * MEANING_ROW_GAP * scale
            entry_height = (
                ENTRY_TOP_PAD * scale
                + entry_title_h
                + ENTRY_TITLE_GAP * scale
                + grid_h
                + ENTRY_BOTTOM_PAD * scale
            )
            laid.append(
                (
                    "abbr",
                    {
                        "name": content,
                        "grid": grid,
                        "height": entry_height,
                        "title_height": entry_title_h,
                    },
                )
            )
        else:
            line = " ".join(content.replace("\n", " ").split())
            display = _ellipsize(line, text_font, content_width - 20 * scale)
            entry_height = (
                ENTRY_TOP_PAD * scale + text_line_h + ENTRY_BOTTOM_PAD * scale
            )
            laid.append(("text", {"text": display, "height": entry_height}))
        total_height += entry_height

    if not laid:
        # 让异常输入仍然得到一张可读图片。
        laid.append(
            ("text", {"text": "未找到翻译结果。", "height": text_line_h + 27 * scale})
        )
        total_height += text_line_h + 27 * scale

    image_h = page_top + total_height + PAGE_PADDING_BOTTOM * scale
    canvas = _background(PAGE_WIDTH * scale, image_h, scale)
    draw = ImageDraw.Draw(canvas)

    # 标题使用单个柔和圆形作为背景，内容区保持平面留白。
    icon_x = page_left
    icon_y = page_top
    _draw_icon_halo(canvas, icon_x, icon_y, header_icon_size, scale)
    title_x = icon_x + header_icon_size + HEADER_ICON_GAP * scale
    draw.text(
        (title_x, page_top + _text_top(heading_font, heading_h)),
        HEADING_TEXT,
        font=heading_font,
        fill=HEADING_FG,
    )
    desc_y = page_top + heading_h + HEADING_GAP * scale
    draw.text(
        (title_x, desc_y + _text_top(desc_font, desc_h)),
        DESC_TEXT,
        font=desc_font,
        fill=DESC_FG,
    )

    y = page_top + content_y
    draw.line(
        (
            page_left,
            y - ENTRY_DIVIDER_GAP * scale,
            page_left + content_width,
            y - ENTRY_DIVIDER_GAP * scale,
        ),
        fill=(*DIVIDER, 255),
        width=max(1, scale),
    )

    entry_index = 0
    for laid_index, (kind, payload) in enumerate(laid):
        entry_top = y
        entry_height = payload["height"]
        accent = _accent_for(entry_index, block_count)
        accent_x = page_left
        draw.rounded_rectangle(
            (
                accent_x,
                entry_top + ENTRY_TOP_PAD * scale,
                accent_x + ENTRY_ACCENT_WIDTH * scale,
                entry_top + entry_height - ENTRY_BOTTOM_PAD * scale,
            ),
            radius=ENTRY_ACCENT_RADIUS * scale,
            fill=(*accent, 255),
        )

        if kind == "abbr":
            name = payload["name"]
            title_x = page_left + 18 * scale
            title_y = entry_top + ENTRY_TOP_PAD * scale
            name_display = _ellipsize(name, abbr_font, content_width - 18 * scale)
            draw.text(
                (title_x, title_y + _text_top(abbr_font, abbr_h)),
                name_display,
                font=abbr_font,
                fill=ABBR_FG,
            )
            grid = payload["grid"]
            # The count is kept separate from the list so no decorative dot is
            # needed between the abbreviation and its metadata.
            meaning_count = sum(len(row) for row in grid["rows"])
            meta = f"共 {meaning_count} 条释义"
            meta_y = title_y + abbr_h + 2 * scale
            draw.text(
                (title_x, meta_y + _text_top(abbr_meta_font, abbr_meta_h)),
                meta,
                font=abbr_meta_font,
                fill=DESC_FG,
            )

            grid_x = title_x
            grid_y = title_y + payload["title_height"] + ENTRY_TITLE_GAP * scale
            for row_index, row in enumerate(grid["rows"]):
                x = grid_x
                for display, item_width in row:
                    bullet_y = grid_y + meaning_h // 2
                    bullet_r = MEANING_BULLET_SIZE * scale // 2
                    bullet_x = x + bullet_r
                    draw.ellipse(
                        (
                            bullet_x - bullet_r,
                            bullet_y - bullet_r,
                            bullet_x + bullet_r,
                            bullet_y + bullet_r,
                        ),
                        fill=(*accent, 255),
                    )
                    draw.text(
                        (
                            x + (MEANING_BULLET_SIZE + MEANING_BULLET_GAP) * scale,
                            grid_y + _text_top(meaning_font, meaning_h),
                        ),
                        display,
                        font=meaning_font,
                        fill=TEXT_FG,
                    )
                    x += item_width + MEANING_COLUMN_GAP * scale
                grid_y += meaning_h
                if row_index < len(grid["rows"]) - 1:
                    grid_y += MEANING_ROW_GAP * scale
            entry_index += 1
        else:
            text_x = page_left + 18 * scale
            text_y = entry_top + ENTRY_TOP_PAD * scale
            draw.text(
                (text_x, text_y + _text_top(text_font, text_line_h)),
                payload["text"],
                font=text_font,
                fill=TEXT_FG,
            )

        y = entry_top + entry_height
        if laid_index < len(laid) - 1:
            divider_y = y + ENTRY_GAP * scale // 2
            draw.line(
                (
                    page_left + 18 * scale,
                    divider_y,
                    page_left + content_width,
                    divider_y,
                ),
                fill=(*DIVIDER, 255),
                width=max(1, scale),
            )
            y += ENTRY_GAP * scale

    final = canvas.convert("RGB").resize(
        (PAGE_WIDTH, image_h // scale), Image.Resampling.LANCZOS
    )
    buffer = io.BytesIO()
    final.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


async def text_to_image(text: str) -> bytes:
    """将文本渲染为 PNG 图片。"""
    return await asyncio.to_thread(_render, text)
