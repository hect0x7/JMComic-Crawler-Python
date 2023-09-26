"""
本文件演示对jmcomic模块进行自定义功能的方式，下面的每个函数都是一个独立的演示单元。
本文件不演示【自定义配置】，有关配置的教程文档请见 ``
"""
from jmcomic import *

option = JmOption.default()
client: JmcomicClient = option.build_jm_client()


def custom_download_callback():
    """
    该函数演示自定义下载时的回调函数
    """

    # jmcomic的下载功能由 JmModuleConfig.CLASS_DOWNLOADER 这个类来负责执行
    # 这个类默认是 JmDownloader，继承了DownloadCallback
    # 你可以写一个自定义类，继承JmDownloader，覆盖属于DownloadCallback的方法，来实现自定义回调
    class MyDownloader(JmDownloader):
        # 覆盖 album 下载完成后的回调
        def after_album(self, album: JmAlbumDetail):
            print(f'album下载完毕: {album}')
            pass

    # 同样的，最后要让你的自定义类生效
    JmModuleConfig.CLASS_DOWNLOADER = MyDownloader


def custom_option_class():
    """
    该函数演示自定义option
    """

    # jmcomic模块支持自定义Option类，
    # 你可以写一个自己的类，继承JmOption，然后覆盖其中的一些方法。
    class MyOption(JmOption):

        def __init__(self, *args, **kwargs):
            print('MyOption 初始化开始')
            super().__init__(*args, **kwargs)

        @classmethod
        def default(cls):
            print('调用了MyOption.default()')
            return super().default()

    # 最后，替换默认Option类即可
    JmModuleConfig.CLASS_OPTION = MyOption


def custom_client_class():
    """
    该文件演示自定义client类
    """

    # 默认情况下，JmOption使用client类是根据配置项 `client.impl` 决定的
    # JmOption会根据`client.impl`到 JmModuleConfig.CLASS_CLIENT_IMPL 中查找

    # 你可以自定义一个`client.impl`，例如 'my-client'，
    # 或者使用jmcomic内置 'html' 和 'api'，
    # 然后把你的`client.impl`和类一起配置到JmModuleConfig中

    # 1. 自定义Client类
    class MyClient(JmHtmlClient):
        pass

    # 2. 让你的配置类生效
    JmModuleConfig.CLASS_CLIENT_IMPL['my-client'] = MyClient

    # 3. 在配置文件中使用你定义的client.impl，后续使用这个option即可
    """
    client:
        impl: 'my-client'
    """


def custom_album_photo_image_detail_class():
    """
    该函数演示替换实体类（本子/章节/图片）
    """

    # 在使用路径规则 DirRule 时，可能会遇到需要自定义实体类属性的情况，例如：
    """
    dir_rule:
        base_dir: ${workspace}
        rule: Bd_Acustom_Pcustom
    """

    # 上面的Acustom，Pcustom都是自定义字段
    # 如果你想要使用这种自定义字段，你就需要替换默认的实体类，例如

    # 自定义本子实体类
    class MyAlbum(JmAlbumDetail):
        # 自定义 custom 属性
        @property
        def custom(self):
            return f'custom_{self.title}'

    # 自定义章节实体类
    class MyPhoto(JmPhotoDetail):
        # 自定义 custom 属性
        @property
        def custom(self):
            return f'custom_{self.title}'

    # 自定义图片实体类
    class MyImage(JmImageDetail):
        pass

    # 最后，替换默认实体类来让你的自定义类生效
    JmModuleConfig.CLASS_ALBUM = MyAlbum
    JmModuleConfig.CLASS_PHOTO = MyPhoto
    JmModuleConfig.CLASS_IMAGE = MyImage


def custom_jm_debug():
    """
    该函数演示自定义debug
    """

    # jmcomic模块在运行过程中会使用 jm_debug() 这个函数进行打印信息
    # jm_debug() 这个函数 最后会调用 JmModuleConfig.debug_executor 函数
    # 你可以写一个自己的函数，替换 JmModuleConfig.debug_executor，实现自定义debug

    # 1. 自定义debug函数
    def my_debug(topic: str, msg: str):
        """
        这个debug函数的参数列表必须包含两个参数，topic和msg
        @param topic: debug主题，例如 'album.before', 'req.error', 'plugin.error'
        @param msg: 具体debug的信息
        """
        pass

    # 2. 让my_debug生效
    JmModuleConfig.debug_executor = my_debug
