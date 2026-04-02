"""真实请求 nbnhhsh 接口并将结果渲染为图片。"""

from pathlib import Path

import pytest
import nonebot

nonebot.init(driver="~none")

from nonebot_plugin_nbnhhsh.core import guess, format_result
from nonebot_plugin_nbnhhsh.render import text_to_image


@pytest.mark.asyncio
async def test_real_request_then_render(tmp_path: Path) -> None:
    tags = await guess("yyds nsdd")
    result_text = format_result(tags)

    assert result_text != "未找到翻译结果。"

    image_bytes = await text_to_image(result_text)

    assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    output_path = tmp_path / "test_real_request_then_render.png"
    output_path.write_bytes(image_bytes)

    assert output_path.exists()
