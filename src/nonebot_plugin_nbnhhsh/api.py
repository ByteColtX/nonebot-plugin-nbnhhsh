"""
nonebot_plugin_nbnhhsh.api
~~~~~~~~~~~~~~~~~~~~~~~~~~
与 lab.magiconch.com 后端通信的异步 HTTP 封装。
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "https://lab.magiconch.com/api/nbnhhsh/"


async def api_guess(text: str) -> list[dict[str, Any]]:
    """
    POST /guess — 查询缩写翻译。

    :param text: 用逗号分隔的缩写串，如 ``"yyds,nb"``
    :returns: 词条列表 `[{"name": "<缩写>", "trans": "<翻译>"}]`
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            API_BASE + "guess",
            json={"text": text},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
