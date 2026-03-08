"""
nonebot_plugin_nbnhhsh.handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
NoneBot2 事件处理逻辑，包含：
  - /nbnhhsh <缩写>    主动翻译命令
  - /nbnhhsh submit <缩写> <文字>  提交补充翻译
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg


def _strip(msg: Message) -> str:
    return msg.extract_plain_text().strip()


nbnhhsh_cmd = on_command(
    "nbnhhsh",
    aliases={"好好说话", "hhsh", "缩写"},
    priority=10,
    block=True,
)

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

    await matcher.finish("test_nbnhhsh: " + text)
