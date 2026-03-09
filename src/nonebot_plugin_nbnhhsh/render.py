"""
nonebot_plugin_nbnhhsh.render
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
使用 nonebot-plugin-htmlkit 将文字渲染为图片。
"""

from __future__ import annotations

from nonebot import require

require("nonebot_plugin_htmlkit")

from nonebot_plugin_htmlkit import text_to_pic


async def text_to_image(text: str) -> bytes:
    """
    将文本渲染为 PNG 图片，返回字节数据。

    :param text: 要渲染的文本
    :returns:    PNG 格式的图片字节
    """
    return await text_to_pic(text)
