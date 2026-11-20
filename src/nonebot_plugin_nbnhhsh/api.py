"""
nonebot_plugin_nbnhhsh.api
~~~~~~~~~~~~~~~~~~~~~~~~~~
与 lab.magiconch.com 后端通信的异步 HTTP 封装。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

API_BASE = "https://lab.magiconch.com/api/nbnhhsh/"


def _translation_url(name: str) -> str:
    """构造提交接口 URL，缩写按路径段转义，防止斜杠、问号等改变路由。"""
    return f"{API_BASE}translation/{quote(name, safe='')}"


async def api_guess(text: str, timeout: int = 10) -> list[dict[str, Any]]:
    """查询缩写翻译。

    Args:
        text: 用逗号分隔的缩写串，如 ``"yyds,nb"``。
        timeout: HTTP 请求超时时间，单位为秒。

    Returns:
        API 返回的词条列表。若响应不是列表，则返回空列表。
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            API_BASE + "guess",
            json={"text": text},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


async def api_submit(name: str, text: str, timeout: int = 10) -> None:
    """提交补充翻译。

    Args:
        name: 缩写，如 ``"yyds"``。
        text: 对应文字，末尾可括号注明来源，如
            ``"永远的神（网络流行语）"``。
        timeout: HTTP 请求超时时间，单位为秒。
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            _translation_url(name),
            json={"text": text},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
