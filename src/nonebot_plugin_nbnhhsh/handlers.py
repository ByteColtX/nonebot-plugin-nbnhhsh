"""
nonebot_plugin_nbnhhsh.handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
NoneBot2 事件处理逻辑，包含：
  - /nbnhhsh <缩写>                 主动翻译命令
  - /nbnhhsh submit <缩写> <文字>    提交补充翻译
  - 自然语言问句触发                 「xx是什么」「xx是啥」「xx啥意思」等
  - 自动捕获缩写词条                  需在.env配置 NBNHHSH_AUTO=true
"""

import re
import logging

from nonebot import CommandGroup, get_driver, on_message
from nonebot.rule import Rule, CommandRule
from nonebot.params import CommandArg, EventMessage
from nonebot.matcher import Matcher, matchers
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageSegment

from .core import guess, submit, format_result
from .config import plugin_config
from .render import text_to_image

logger = logging.getLogger("nonebot_plugin_nbnhhsh")


async def _reply(matcher: Matcher, text: str) -> None:
    """根据配置以文字或图片形式发送结果。

    画图失败（没有中文字体、Pillow 缺失等）时退回发文字，不让回复断掉。

    Args:
        matcher: 当前事件对应的 matcher。
        text: 待发送的文本内容。
    """
    if plugin_config.nbnhhsh_text2pic:
        try:
            img = await text_to_image(text)
        except Exception as e:  # 画图失败不能影响回复
            logger.warning(f"[nbnhhsh] 渲染图片失败，改发文字：{e}")
        else:
            await matcher.finish(MessageSegment.image(img))
    await matcher.finish(text)


def _strip(msg: Message) -> str:
    """提取并去除消息文本两端空白。

    Args:
        msg: 输入消息对象。

    Returns:
        处理后的纯文本。
    """
    return msg.extract_plain_text().strip()


nbnhhsh = CommandGroup("nbnhhsh", priority=10, block=True)

nbnhhsh_cmd = nbnhhsh.command((), aliases={"好好说话", "hhsh", "缩写"})
submit_cmd = nbnhhsh.command("submit", aliases={"提交"})

_BASE_CMD = "nbnhhsh"

# 提交子命令的触发词。CommandGroup 的多段命令依赖全局 command_sep，
# 默认值不含空格时 ``/nbnhhsh submit ...`` 只会命中基命令，
# 因此基命令里再按首个词手动分派一次，保证空格分隔也能走提交逻辑。
_SUBMIT_KEYWORDS = {"submit", "提交"}

# 查看帮助的触发词，直接发 /nbnhhsh 也会展示。
_HELP_KEYWORDS = {"help", "帮助", "菜单"}

# 命令说明：主命令 -> 描述，用于帮助列表。
_COMMAND_DESCRIPTIONS: dict[tuple[str, ...], str] = {
    (_BASE_CMD,): "翻译缩写",
    (_BASE_CMD, "submit"): "提交缩写的对应文字",
}

_SUBMIT_USAGE = (
    "用法：/nbnhhsh submit <缩写> <对应文字>\n"
    "示例：/nbnhhsh submit yyds 永远的神（网络流行语）"
)


async def _do_submit(matcher: Matcher, arg: str) -> None:
    """处理提交逻辑，供 ``/nbnhhsh submit`` 与 submit 子命令共用。

    Args:
        matcher: 当前事件对应的 matcher。
        arg: 去掉子命令名后的参数文本（``<缩写> <对应文字>``）。
    """
    parts = arg.split(maxsplit=1)

    if len(parts) < 2:
        await matcher.finish(_SUBMIT_USAGE)

    name, text = parts
    try:
        await submit(name, text, timeout=plugin_config.nbnhhsh_timeout)
    except Exception as e:
        await matcher.finish(f"提交失败：{e}")

    await matcher.finish(
        f"✅ 已提交：「{name}」→「{text}」\n感谢贡献！审核通过后将生效。"
    )


def _format_command(cmd: tuple[str, ...]) -> str:
    """把命令元组渲染成可读文本，如 ``("nbnhhsh", "submit")``。"""
    start = next(iter(get_driver().config.command_start), "")
    return start + " ".join(cmd)


def _iter_plugin_commands() -> list[tuple[tuple[str, ...], list[tuple[str, ...]]]]:
    """枚举本插件注册的命令。

    NoneBot 没有内置的命令清单接口，这里直接遍历已注册的 matcher，
    再从 ``CommandRule`` 里取出命令名（含别名）。

    Returns:
        ``[(主命令, [别名命令, ...]), ...]``，主命令指以 ``nbnhhsh`` 开头的命令。
    """
    commands: list[tuple[tuple[str, ...], list[tuple[str, ...]]]] = []
    seen: set[tuple[str, ...]] = set()
    for group in matchers.values():
        for matcher in group:
            if matcher.plugin_id != __package__:
                continue
            names: list[tuple[str, ...]] = []
            for checker in getattr(matcher.rule, "checkers", ()) or ():
                call = getattr(checker, "call", None)
                if isinstance(call, CommandRule):
                    names.extend(call.cmds)
            primary = next((n for n in names if n and n[0] == _BASE_CMD), None)
            if primary is None or primary in seen:
                continue
            seen.add(primary)
            commands.append((primary, [n for n in names if n != primary]))
    return commands


def _build_help() -> str:
    """生成帮助文本（命令列表）。"""
    lines = ["「能不能好好说话？」指令列表"]
    for primary, aliases in _iter_plugin_commands():
        line = _format_command(primary)
        if desc := _COMMAND_DESCRIPTIONS.get(primary):
            line += f"  {desc}"
        if aliases:
            alias_str = " ".join(_format_command(a) for a in sorted(aliases))
            line += f"（别名：{alias_str}）"
        lines.append(line)
    lines.append("自然语言：xx是什么 / xx是啥 / xx啥意思")
    lines.append("自动划词：NBNHHSH_AUTO=true 时自动翻译消息中的缩写")
    return "\n".join(lines)


@nbnhhsh_cmd.handle()
async def handle_nbnhhsh(matcher: Matcher, arg: Message = CommandArg()) -> None:
    text = _strip(arg)
    parts = text.split(maxsplit=1)

    if not text or parts[0].lower() in _HELP_KEYWORDS:
        await matcher.finish(_build_help())

    if parts[0].lower() in _SUBMIT_KEYWORDS:
        await _do_submit(matcher, parts[1] if len(parts) > 1 else "")
        return

    try:
        tags = await guess(text)
    except ValueError:
        await matcher.finish("未找到有效缩写（需含 2 个以上连续字母/数字）")
    except Exception as e:
        await matcher.finish(f"查询失败：{e}")

    await _reply(matcher, format_result(tags))


@submit_cmd.handle()
async def handle_submit(matcher: Matcher, arg: Message = CommandArg()) -> None:
    await _do_submit(matcher, _strip(arg))


_QUESTION_RE = re.compile(
    r"([a-zA-Z0-9]{2,})\s*是[什啥][么麽]?(?:意思)?"  # xx是什么 / xx是啥 / xx是什么意思
    r"|([a-zA-Z0-9]{2,})\s*[是的]?啥意思"  # xx啥意思 / xx的啥意思
    r"|([a-zA-Z0-9]{2,})\s*什么意思",  # xx什么意思
    re.IGNORECASE,
)


def _question_rule() -> Rule:
    async def _check(msg: Message = EventMessage()) -> bool:
        return bool(_QUESTION_RE.search(msg.extract_plain_text()))

    return Rule(_check)


question_matcher = on_message(rule=_question_rule(), priority=10, block=True)


@question_matcher.handle()
async def handle_question(matcher: Matcher, msg: Message = EventMessage()) -> None:
    text = msg.extract_plain_text()

    # 提取所有命中的缩写（去重保序）
    abbrs: list[str] = []
    seen: set[str] = set()
    for m in _QUESTION_RE.finditer(text):
        word = (m.group(1) or m.group(2) or m.group(3)).lower()
        if word not in seen:
            abbrs.append(word)
            seen.add(word)

    try:
        tags = await guess(",".join(abbrs))
    except Exception as e:
        await matcher.finish(f"查询失败：{e}")

    await _reply(matcher, format_result(tags))


def _auto_rule() -> Rule:
    async def _check(msg: Message = EventMessage()) -> bool:
        if not plugin_config.nbnhhsh_auto:
            return False
        text = msg.extract_plain_text()
        return bool(
            re.search(rf"[a-zA-Z0-9]{{{plugin_config.nbnhhsh_auto_min_len},}}", text)
        )

    return Rule(_check)


auto_matcher = on_message(rule=_auto_rule(), priority=99, block=False)


@auto_matcher.handle()
async def handle_auto(matcher: Matcher, msg: Message = EventMessage()) -> None:
    text = msg.extract_plain_text().strip()
    try:
        tags = await guess(text, timeout=plugin_config.nbnhhsh_timeout)
    except Exception:
        return

    # 过滤暂未录入和空词条，return 静默退出
    visible = [t for t in tags if t.has_translation]
    if not visible:
        return

    result = format_result(visible)
    if plugin_config.nbnhhsh_text2pic:
        try:
            img = await text_to_image(result)
        except Exception as e:  # 画图失败不能影响回复
            logger.warning(f"[nbnhhsh] 渲染图片失败，改发文字：{e}")
        else:
            await matcher.send(MessageSegment.image(img))
            return
    await matcher.send(result)
