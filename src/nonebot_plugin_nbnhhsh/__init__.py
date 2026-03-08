"""
nonebot-plugin-nbnhhsh
~~~~~~~~~~~~~~~~~~~~~~
「能不能好好说话？」拼音首字母缩写翻译 NoneBot2 插件。

原项目：https://github.com/itorr/nbnhhsh
原作者：itorr（Apache-2.0 license）
"""

from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-nbnhhsh",
    description="「能不能好好说话？」拼音首字母缩写翻译 NoneBot2 插件。",
    usage=(
        "/nbnhhsh <缩写>                     翻译缩写\n"
        "/nbnhhsh submit <缩写> <对应文字>    提交补充翻译\n"
    ),
    type="application",  # library
    homepage="https://github.com/ByteColtX/nonebot-plugin-nbnhhsh",
    config=Config,
    # supported_adapters=inherit_supported_adapters(),
    supported_adapters={"~onebot.v11"},  # 仅 onebot
    extra={"author": "ByteColtX", "email": "umk@live.com"},
)


from . import handlers as handlers

__all__ = ["__plugin_meta__"]
