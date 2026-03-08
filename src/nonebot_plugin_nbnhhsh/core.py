"""
nonebot_plugin_nbnhhsh.core
~~~~~~~~~~~~~~~~~~~~~~~~~~~
高层异步接口，整合 API 与解析。
"""

from __future__ import annotations

from .api import api_guess
from .parser import Tag, has_abbr, parse_tags, extract_abbrs


async def guess(text: str) -> list[Tag]:
    """
    翻译文本中包含的所有缩写。

    :param text:  任意含缩写的字符串
    :returns:     词条列表
    :raises ValueError: 文本中不含任何有效缩写
    """
    if not has_abbr(text):
        raise ValueError(f"文本中不包含有效缩写: {text!r}")

    raw = await api_guess(extract_abbrs(text))
    return parse_tags(raw)


def format_result(tags: list[Tag]) -> str:
    """将 Tag 列表渲染为适合发送的多行文本。"""
    if not tags:
        return "未找到翻译结果。"
    return "\n".join(tag.format() for tag in tags)
