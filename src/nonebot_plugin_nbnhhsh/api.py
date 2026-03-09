"""
nonebot_plugin_nbnhhsh.api
~~~~~~~~~~~~~~~~~~~~~~~~~~
与 lab.magiconch.com 后端通信的异步 HTTP 封装。
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "https://lab.magiconch.com/api/nbnhhsh/"


async def api_guess(text: str, timeout: int = 10) -> list[dict[str, Any]]:
    """
    POST /guess — 查询缩写翻译。

    :param text: 用逗号分隔的缩写串，如 ``"yyds,nb"``
    :returns: 词条列表 `[{"name": "<缩写>", "trans": "<翻译>"}]`
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
    """
    POST /translation/<n> - 提交补充翻译

    :param name: 缩写，如 ``"yyds"``
    :param text: 对应文字，末尾可括号注明来源，如 ``"永远的神（网络流行语）"``
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            API_BASE + f"translation/{name}",
            json={"text": text},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
