"""
nonebot_plugin_nbnhhsh.core
~~~~~~~~~~~~~~~~~~~~~~~~~~~
高层异步接口，整合 API 与解析。
"""

from __future__ import annotations

import re

from .api import api_guess, api_submit
from .parser import Tag, has_abbr, parse_tags, extract_abbrs

# 与 parser 的缩写定义一致：仅字母数字。
_ABBR_NAME_RE = re.compile(r"[a-zA-Z0-9]+")


class NoAbbreviationError(ValueError):
    """文本中不含任何满足长度要求的缩写。"""


async def guess(text: str, timeout: int = 10, min_len: int = 2) -> list[Tag]:
    """翻译文本中包含的所有缩写。

    Args:
        text: 任意含缩写的字符串。
        timeout: HTTP 请求超时时间，单位为秒。
        min_len: 缩写的最小长度。

    Returns:
        解析后的词条列表。

    Raises:
        NoAbbreviationError: 文本中不含任何有效缩写。
    """
    if not has_abbr(text, min_len):
        raise NoAbbreviationError(f"文本中不包含有效缩写: {text!r}")

    raw = await api_guess(extract_abbrs(text, min_len), timeout=timeout)
    return parse_tags(raw)


def format_result(tags: list[Tag]) -> str:
    """将词条列表渲染为适合发送的多行文本。

    Args:
        tags: 待渲染的词条列表。

    Returns:
        渲染后的多行文本。若没有可展示的词条，则返回兜底提示。
    """
    visible = [t for t in tags if t.has_translation or t.inputting]
    if not visible:
        return "未找到翻译结果。"
    return "\n".join(tag.format() for tag in visible)


async def submit(name: str, text: str, timeout: int = 10) -> None:
    """提交补充翻译。

    Args:
        name: 缩写，如 ``"yyds"``。
        text: 对应文字，末尾可括号注明来源，如
            ``"永远的神（网络流行语）"``。
        timeout: HTTP 请求超时时间，单位为秒。

    Raises:
        ValueError: 提交内容为空，或缩写包含非字母数字字符。
    """
    name = name.strip()
    text = text.strip()
    if not text:
        raise ValueError("提交内容不能为空")
    if not _ABBR_NAME_RE.fullmatch(name):
        raise ValueError("缩写只能由字母和数字组成")
    await api_submit(name, text, timeout=timeout)
