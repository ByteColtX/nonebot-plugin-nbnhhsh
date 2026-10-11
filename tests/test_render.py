"""渲染模块的离线测试：字体固定用 ``tests/assets/test-font.ttf``，不联网。"""

from __future__ import annotations

import struct
from pathlib import Path
from collections.abc import Iterator

import pytest

from nonebot_plugin_nbnhhsh import render

TEST_FONT = Path(__file__).resolve().parent / "assets" / "test-font.ttf"


@pytest.fixture(autouse=True)
def _use_test_font(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """把字体固定成测试子集，避免测试去下载 18MB 的完整字体。"""
    monkeypatch.setattr(render, "SYSTEM_FONTS", (str(TEST_FONT),))
    monkeypatch.setattr(render, "_FONT_PATH", None)
    render._font.cache_clear()
    yield
    render._font.cache_clear()


def _size(png: bytes) -> tuple[int, int]:
    """从 PNG 头部读出宽高。"""
    return struct.unpack(">II", png[16:24])


async def test_text_to_image_returns_png() -> None:
    """正常词条能画成 720 宽的 PNG。"""
    png = await render.text_to_image("[yyds] 永远的神、永远单身")

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = _size(png)
    assert width == render.PAGE_WIDTH
    assert height > 100


async def test_text_to_image_handles_fallback_text() -> None:
    """「暂未录入」这种两行文本也能画出来。"""
    png = await render.text_to_image("[zzzz] 暂未录入\n可能是：z z z z")

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert _size(png)[0] == render.PAGE_WIDTH


async def test_more_meanings_make_a_taller_image() -> None:
    """释义条目多到换行时，图会变高。"""
    many_meanings = "、".join(["永远的神"] * 12)
    one = _size(await render.text_to_image("[yyds] 永远的神"))[1]
    many = _size(await render.text_to_image(f"[yyds] {many_meanings}"))[1]

    assert many > one


def test_wrap_breaks_chinese_by_char() -> None:
    """中文按字断行，每行都不超过给定宽度。"""
    font = render._font(render.TEXT_SIZE)
    lines = render.wrap("能不能好好说话能不能好好说话能不能好好说话", font, 200)

    assert len(lines) > 1
    assert all(font.getlength(line) <= 200 for line in lines)
    assert "".join(lines) == "能不能好好说话能不能好好说话能不能好好说话"


def test_wrap_keeps_latin_words_whole() -> None:
    """英文单词整体挪到下一行，不从中间劈开。"""
    font = render._font(render.TEXT_SIZE)
    width = int(font.getlength("world")) + 1
    lines = render.wrap("hello world", font, width)

    assert lines == ["hello", "world"]


def test_missing_font_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """系统没字体、缓存也没有、下载还失败时抛 RuntimeError。"""
    monkeypatch.setattr(render, "SYSTEM_FONTS", ())
    monkeypatch.setattr(render, "_FONT_PATH", None)
    monkeypatch.setattr(render, "_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(render, "_download_font", lambda _target: False)

    with pytest.raises(RuntimeError):
        render.ensure_font()
