import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


# nonebug 要求在 collect 前初始化，使用 pytest 插件机制
def pytest_configure(config):
    nonebot.init(driver="~none")
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    nonebot.load_plugin("nonebot_plugin_nbnhhsh")
