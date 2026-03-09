"""
nonebot_plugin_nbnhhsh.config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
插件配置项，通过 NoneBot2 配置系统注入。

在 .env 中可设置：

    NBNHHSH_AUTO=true      # 开启自动划词翻译（默认关闭）
    NBNHHSH_AUTO_MIN_LEN=2 # 自动划词触发的最短缩写长度（默认 2）
    NBNHHSH_TIMEOUT=10     # HTTP 请求超时秒数（默认 10）
"""

from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    nbnhhsh_auto: bool = False
    nbnhhsh_auto_min_len: int = 2
    nbnhhsh_timeout: int = 10


plugin_config: Config = get_plugin_config(Config)
