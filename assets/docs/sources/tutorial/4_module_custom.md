# 模块自定义



下方所有函数都省略了如下的导包和准备代码

```python
from jmcomic import *
option = JmOption.default()
client: JmcomicClient = option.build_jm_client()
```



## 自定义下载前后的回调函数

```python
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
    
    # 最后，让你的自定义类生效
    JmModuleConfig.CLASS_DOWNLOADER = MyDownloader
```



## 自定义option类


```python
def custom_option_class():
    """
    该函数演示自定义option类
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
```


## 自定义client类

```python
def custom_client_class():
    """
    该文件演示自定义client类
    """

    # 默认情况下，JmOption使用client类是根据配置项 `client.impl` 决定的
    # JmOption会根据`client.impl`到 JmModuleConfig.CLASS_CLIENT_IMPL 中查找
    
    # 自定义client的步骤如下
    
    # 1. 自定义Client类
    class MyClient(JmHtmlClient):
        client_key = 'myclient'
        pass
    
    # 2. 让MyClient生效
    JmModuleConfig.register_client(MyClient)
    
    # 3. 在配置文件中使用你定义的client.impl，后续使用这个option即可
    """
    client:
        impl: myclient
    """
```


## 自定义实体类（本子/章节/图片）

```python
def custom_album_photo_image_detail_class():
    """
    该函数演示自定义实体类（本子/章节/图片）

    在使用路径规则 DirRule 时，可能会遇到需要自定义实体类属性的情况，例如：
    dir_rule:
        base_dir: ${workspace}
        rule: Bd_Acustom_Pcustom
    
    上面的Acustom，Pcustom都是自定义字段
    如果你想要使用这种自定义字段，你就需要替换默认的实体类，方式如下
    """
    
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
    
    """
    v2.3.3: 支持更灵活的自定义方式，可以使用函数，效果同上，示例见下
    """
    
    class MyAlbum2(JmAlbumDetail):
    
        def get_dirname(self, ref: str) -> str:
            if ref == 'custom':
                return f'custom_{self.name}'
    
            return super().get_dirname(ref)
    
    # 最后，替换默认实体类来让你的自定义类生效
    JmModuleConfig.CLASS_ALBUM = MyAlbum
    JmModuleConfig.CLASS_PHOTO = MyPhoto
```



## 自定义log

```python
def custom_jm_log():
    """
    该函数演示自定义log
    """

    # jmcomic模块在运行过程中会使用 jm_log() 这个函数进行打印信息
    # jm_log() 这个函数 最后会调用 JmModuleConfig.log_executor 函数
    # 你可以写一个自己的函数，替换 JmModuleConfig.log_executor，实现自定义log
    
    # 1. 自定义log函数
    def my_log(topic: str, msg: str):
        """
        这个log函数的参数列表必须包含两个参数，topic和msg
        @param topic: log主题，例如 'album.before', 'req.error', 'plugin.error'
        @param msg: 具体log的信息
        """
        pass
    
    # 2. 让my_log生效
    JmModuleConfig.log_executor = my_log
```



## 自定义异常监听器/回调

```python
def custom_exception_listener():
    """
    该函数演示jmcomic的异常监听器机制
    """
    
    # 1. 选一个可能会发生的、你感兴趣的异常
    etype = ResponseUnexpectedException
    
    
    def listener(e):
        """
        你的监听器方法
        该方法无需返回值
        :param e: 异常实例
        """
        print(f'my exception listener invoke !!! exception happened: {e}')
    
    
    # 注册监听器/回调
    # 这个异常类（或者这个异常的子类）的实例将要被raise前，你的listener方法会被调用
    JmModuleConfig.register_exception_listener(etype, listener)
```