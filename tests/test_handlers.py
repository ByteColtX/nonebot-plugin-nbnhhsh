"""命令路由回归测试。

确保 ``/nbnhhsh submit <缩写> <文字>``（空格分隔）能进入提交逻辑，而不是被
当成普通查询。此前 submit 子命令依赖全局 ``COMMAND_SEP`` 含空格，默认配置下
``/nbnhhsh submit ...`` 只会命中基命令并触发查询。
"""

from __future__ import annotations

from typing import Any

import pytest
from nonebug import App
from nonebot.adapters.onebot.v11 import Message

from tests.fake import fake_group_message_event_v11


def _patch_io(monkeypatch: pytest.MonkeyPatch, handlers: Any) -> dict[str, list[Any]]:
    """拦截网络与渲染，记录 guess/submit 的调用参数。"""
    calls: dict[str, list[Any]] = {"guess": [], "submit": []}

    async def fake_guess(text: str, timeout: int = 10) -> list[Any]:
        calls["guess"].append(text)
        return []

    async def fake_submit(name: str, text: str, timeout: int = 10) -> None:
        calls["submit"].append((name, text))

    monkeypatch.setattr(handlers, "guess", fake_guess)
    monkeypatch.setattr(handlers, "submit", fake_submit)
    monkeypatch.setattr(handlers.plugin_config, "nbnhhsh_text2pic", False)
    return calls


async def test_submit_space_separated(
    app: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/nbnhhsh submit agent AI Agent（AI 智能体）应走提交逻辑。"""
    from nonebot_plugin_nbnhhsh import handlers

    calls = _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(
            message=Message("/nbnhhsh submit agent AI Agent（AI 智能体）")
        )
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            "✅ 已提交：「agent」→「AI Agent（AI 智能体）」\n"
            "感谢贡献！审核通过后将生效。",
            True,
        )
        ctx.should_finished(handlers.nbnhhsh_cmd)

    assert calls["submit"] == [("agent", "AI Agent（AI 智能体）")]
    assert calls["guess"] == []


async def test_submit_cn_alias_space_separated(
    app: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/nbnhhsh 提交 <缩写> <文字> 同样应走提交逻辑。"""
    from nonebot_plugin_nbnhhsh import handlers

    calls = _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(
            message=Message("/nbnhhsh 提交 yyds 永远的神")
        )
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            "✅ 已提交：「yyds」→「永远的神」\n感谢贡献！审核通过后将生效。",
            True,
        )
        ctx.should_finished(handlers.nbnhhsh_cmd)

    assert calls["submit"] == [("yyds", "永远的神")]


async def test_submit_missing_args(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """/nbnhhsh submit 缺参数时给出用法提示，不发起提交。"""
    from nonebot_plugin_nbnhhsh import handlers

    calls = _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(message=Message("/nbnhhsh submit"))
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, handlers._SUBMIT_USAGE, True)
        ctx.should_finished(handlers.nbnhhsh_cmd)

    assert calls["submit"] == []


async def test_plain_query_still_works(
    app: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/nbnhhsh yyds 仍走查询逻辑。"""
    from nonebot_plugin_nbnhhsh import handlers

    calls = _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(message=Message("/nbnhhsh yyds"))
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "未找到翻译结果。", True)
        ctx.should_finished(handlers.nbnhhsh_cmd)

    assert calls["guess"] == ["yyds"]
    assert calls["submit"] == []


async def test_no_args_shows_help(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """/nbnhhsh 无参数时展示帮助（命令列表）。"""
    from nonebot_plugin_nbnhhsh import handlers

    _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(message=Message("/nbnhhsh"))
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, handlers._build_help(), True)
        ctx.should_finished(handlers.nbnhhsh_cmd)


async def test_help_keyword(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    """/nbnhhsh help 也展示帮助。"""
    from nonebot_plugin_nbnhhsh import handlers

    _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.nbnhhsh_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(message=Message("/nbnhhsh help"))
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, handlers._build_help(), True)
        ctx.should_finished(handlers.nbnhhsh_cmd)


def test_build_help_lists_commands() -> None:
    """帮助文本应列出主命令、子命令与别名。"""
    from nonebot_plugin_nbnhhsh import handlers

    text = handlers._build_help()
    assert "/nbnhhsh" in text
    assert "/nbnhhsh submit" in text
    assert "/好好说话" in text
    assert "/提交" in text


async def test_submit_dot_form_still_works(
    app: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/nbnhhsh.submit（默认 command_sep）仍由 submit 子命令处理。"""
    from nonebot_plugin_nbnhhsh import handlers

    calls = _patch_io(monkeypatch, handlers)

    async with app.test_matcher(handlers.submit_cmd) as ctx:
        bot = ctx.create_bot()
        event = fake_group_message_event_v11(
            message=Message("/nbnhhsh.submit yyds 永远的神")
        )
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            "✅ 已提交：「yyds」→「永远的神」\n感谢贡献！审核通过后将生效。",
            True,
        )
        ctx.should_finished(handlers.submit_cmd)

    assert calls["submit"] == [("yyds", "永远的神")]
