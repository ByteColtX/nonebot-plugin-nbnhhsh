"""core 与 api 层的参数传递、异常类型回归测试。"""

from __future__ import annotations

import pytest

from nonebot_plugin_nbnhhsh import api, core


async def test_guess_raises_no_abbreviation(monkeypatch: pytest.MonkeyPatch) -> None:
    """无有效缩写时抛专用异常，且不发起请求。"""
    called = False

    async def fake_api_guess(text: str, timeout: int = 10) -> list[dict[str, object]]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(core, "api_guess", fake_api_guess)

    with pytest.raises(core.NoAbbreviationError):
        await core.guess("你好世界")
    assert called is False


async def test_guess_forwards_timeout_and_min_len(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """guess 应把 timeout 与 min_len 一起应用到请求。"""
    seen: dict[str, object] = {}

    async def fake_api_guess(text: str, timeout: int = 10) -> list[dict[str, object]]:
        seen.update(text=text, timeout=timeout)
        return []

    monkeypatch.setattr(core, "api_guess", fake_api_guess)

    await core.guess("abc de", timeout=42, min_len=3)
    assert seen == {"text": "abc", "timeout": 42}


async def test_submit_forwards_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """submit 应把 timeout 传给 api_submit。"""
    seen: dict[str, object] = {}

    async def fake_api_submit(name: str, text: str, timeout: int = 10) -> None:
        seen.update(name=name, text=text, timeout=timeout)

    monkeypatch.setattr(core, "api_submit", fake_api_submit)

    await core.submit("yyds", "永远的神", timeout=42)
    assert seen == {"name": "yyds", "text": "永远的神", "timeout": 42}


async def test_submit_rejects_non_alnum_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """带路径分隔符的缩写应在发请求前被拒绝。"""

    async def fake_api_submit(name: str, text: str, timeout: int = 10) -> None:
        raise AssertionError("不应发起请求")

    monkeypatch.setattr(core, "api_submit", fake_api_submit)

    with pytest.raises(ValueError, match="缩写只能"):
        await core.submit("yy/ds", "永远的神")


def test_translation_url_escapes_name() -> None:
    """提交 URL 中的缩写应作为单个路径段转义。"""
    assert api._translation_url("yyds") == api.API_BASE + "translation/yyds"
    assert api._translation_url("a/b?c#d") == api.API_BASE + "translation/a%2Fb%3Fc%23d"
