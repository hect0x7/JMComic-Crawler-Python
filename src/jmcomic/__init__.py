# 模块依赖关系如下:
# 被依赖方 <--- 使用方
# config <--- entity <--- toolkit <--- client <--- option <--- downloader

__version__ = '2.7.2'

from .api import *
from .jm_plugin import *
from .jm_feature import *
from .jm_async_client import AsyncJmApiClient
from .jm_async_downloader import JmAsyncDownloader
from .jm_client_interface import AsyncJmcomicClient
from .api import download_album_async, download_photo_async, download_batch_async

# 下面进行注册组件（客户端、插件）
gb = dict(filter(lambda pair: isinstance(pair[1], type), globals().items()))


def register_jmcomic_component(variables: Dict[str, Any], method, valid_interface: type):
    for v in variables.values():
        if v != valid_interface and issubclass(v, valid_interface):
            method(v)


# 注册 sync 客户端
register_jmcomic_component(gb,
                           JmModuleConfig.register_client,
                           JmcomicClient,
                           )
# 注册 async 客户端
register_jmcomic_component(gb,
                           JmModuleConfig.register_async_client,
                           AsyncJmcomicClient,
                           )
# 注册插件
register_jmcomic_component(gb,
                           JmModuleConfig.register_plugin,
                           JmOptionPlugin,
                           )
