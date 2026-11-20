"""
nonebot_plugin_nbnhhsh.config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
插件配置项，通过 NoneBot2 配置系统注入。

在 .env 中可设置：

    NBNHHSH_AUTO=False          # 开启自动划词翻译（默认关闭）
    NBNHHSH_AUTO_MIN_LEN=2      # 自动划词触发的最短缩写长度（默认 2）
    NBNHHSH_TIMEOUT=10          # HTTP 请求超时秒数（默认 10）
    NBNHHSH_TEXT2PIC=True       # 以图片形式发送结果，防止风控（默认开启）
"""

from nonebot import get_plugin_config
from pydantic import Field, BaseModel


class Config(BaseModel):
    """插件配置模型。"""

    nbnhhsh_auto: bool = False
    nbnhhsh_auto_min_len: int = Field(default=2, ge=2)
    nbnhhsh_timeout: int = Field(default=10, gt=0)
    nbnhhsh_text2pic: bool = True


plugin_config: Config = get_plugin_config(Config)
