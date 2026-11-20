"""渲染模块的离线测试：字体固定用 ``tests/assets/test-font.ttf``，不联网。"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from nonebot_plugin_nbnhhsh import render

TEST_FONT = Path(__file__).resolve().parent / "assets" / "test-font.ttf"


@pytest.fixture(autouse=True)
def _use_test_font(monkeypatch: pytest.MonkeyPatch) -> None:
    """把字体固定成测试子集，避免测试去下载 18MB 的完整字体。"""
    monkeypatch.setattr(render, "SYSTEM_FONTS", (str(TEST_FONT),))
    monkeypatch.setattr(render, "_FONT_PATH", None)


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


def test_ellipsize_keeps_short_text() -> None:
    """短文本原样返回。"""
    font = render._font(TEST_FONT, render.TEXT_SIZE)

    assert render._ellipsize("永远的神", font, 10_000) == "永远的神"


def test_ellipsize_truncates_long_text() -> None:
    """超宽文本截断并加省略号，结果不超过给定宽度。"""
    font = render._font(TEST_FONT, render.TEXT_SIZE)
    max_width = int(font.getlength("永远的神")) + 1
    result = render._ellipsize("永远的神永远的神永远的神", font, max_width)

    assert result.endswith("…")
    assert font.getlength(result) <= max_width


def test_missing_font_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """系统没字体、缓存也没有、下载还失败时抛 RuntimeError。"""
    monkeypatch.setattr(render, "SYSTEM_FONTS", ())
    monkeypatch.setattr(render, "_FONT_PATH", None)
    monkeypatch.setattr(render, "_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(render, "_download_font", lambda _target: False)

    with pytest.raises(RuntimeError):
        render.ensure_font()
