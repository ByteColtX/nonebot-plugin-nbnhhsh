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

from nonebot import CommandGroup, on_message
from nonebot.rule import Rule
from nonebot.params import CommandArg, EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageSegment

from .core import guess, submit, format_result
from .config import plugin_config
from .render import text_to_image


async def _reply(matcher: Matcher, text: str) -> None:
    """根据配置以文字或图片形式发送结果。

    Args:
        matcher: 当前事件对应的 matcher。
        text: 待发送的文本内容。
    """
    if plugin_config.nbnhhsh_text2pic:
        img = await text_to_image(text)
        await matcher.finish(MessageSegment.image(img))
    else:
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


@nbnhhsh_cmd.handle()
async def handle_nbnhhsh(matcher: Matcher, arg: Message = CommandArg()) -> None:
    text = _strip(arg)

    if not text:
        await matcher.finish(
            "用法：\n"
            "  /nbnhhsh <缩写或句子>      翻译缩写\n"
            "  /nbnhhsh submit <缩写> <文字>  提交补充翻译\n\n"
            "示例：\n"
            "  /nbnhhsh yyds\n"
            "  /nbnhhsh gkd"
        )

    try:
        tags = await guess(text)
    except ValueError:
        await matcher.finish("未找到有效缩写（需含 2 个以上连续字母/数字）")
    except Exception as e:
        await matcher.finish(f"查询失败：{e}")

    await _reply(matcher, format_result(tags))


@submit_cmd.handle()
async def handle_submit(matcher: Matcher, arg: Message = CommandArg()) -> None:
    parts = _strip(arg).split(maxsplit=1)

    if len(parts) < 2:
        await matcher.finish(
            "用法：/nbnhhsh submit <缩写> <对应文字>\n"
            "示例：/nbnhhsh submit yyds 永远的神（网络流行语）"
        )

    name, text = parts
    try:
        await submit(name, text, timeout=plugin_config.nbnhhsh_timeout)
    except Exception as e:
        await matcher.finish(f"提交失败：{e}")

    await matcher.finish(
        f"✅ 已提交：「{name}」→「{text}」\n感谢贡献！审核通过后将生效。"
    )


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
        img = await text_to_image(result)
        await matcher.send(MessageSegment.image(img))
    else:
        await matcher.send(result)
