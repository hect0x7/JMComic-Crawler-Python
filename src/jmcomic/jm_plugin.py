"""
该文件存放的是option插件
"""

from .jm_option import *


class PluginValidationException(Exception):

    def __init__(self, plugin: 'JmOptionPlugin', msg: str):
        self.plugin = plugin
        self.msg = msg


class JmOptionPlugin:
    plugin_key: str

    def __init__(self, option: JmOption):
        self.option = option

    def invoke(self, **kwargs) -> None:
        """
        执行插件的功能
        :param kwargs: 给插件的参数
        """
        raise NotImplementedError

    @classmethod
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        """
        创建插件实例
        :param option: JmOption对象
        """
        return cls(option)

    @classmethod
    def log(cls, msg, topic=None):
        jm_log(
            topic=f'plugin.{cls.plugin_key}' + (f'.{topic}' if topic is not None else ''),
            msg=msg
        )

    def require_true(self, case: Any, msg: str):
        """
        独立于ExceptionTool的一套异常抛出体系
        """
        if case:
            return

        raise PluginValidationException(self, msg)

    def warning_lib_not_install(self, lib: str):
        msg = (f'插件`{self.plugin_key}`依赖库: {lib}，请先安装{lib}再使用。'
               f'安装命令: [pip install {lib}]')
        import warnings
        warnings.warn(msg)


class JmLoginPlugin(JmOptionPlugin):
    """
    功能：登录禁漫，并保存登录后的cookies，让所有client都带上此cookies
    """
    plugin_key = 'login'

    def invoke(self,
               username: str,
               password: str,
               ) -> None:
        self.require_true(username, '用户名不能为空')
        self.require_true(password, '密码不能为空')

        client = self.option.new_jm_client()
        client.login(username, password)

        cookies = dict(client['cookies'])
        self.option.update_cookies(cookies)
        JmModuleConfig.APP_COOKIES = cookies

        self.log('登录成功')


class UsageLogPlugin(JmOptionPlugin):
    plugin_key = 'usage_log'

    def invoke(self, **kwargs) -> None:
        import threading
        t = threading.Thread(
            target=self.monitor_resource_usage,
            kwargs=kwargs,
            daemon=True,
        )
        t.start()

        self.set_thread_as_option_attr(t)

    def set_thread_as_option_attr(self, t):
        """
        线程留痕
        """
        name = f'thread_{self.plugin_key}'

        thread_ls: Optional[list] = getattr(self.option, name, None)
        if thread_ls is None:
            setattr(self.option, name, [t])
        else:
            thread_ls.append(t)

    def monitor_resource_usage(
            self,
            interval=1,
            enable_warning=True,
            warning_cpu_percent=70,
            warning_mem_percent=70,
            warning_thread_count=100,
    ):
        try:
            import psutil
        except ImportError:
            self.warning_lib_not_install('psutil')
            return

        from time import sleep
        from threading import active_count
        # 获取当前进程
        process = psutil.Process()

        cpu_percent = None
        # noinspection PyUnusedLocal
        thread_count = None
        # noinspection PyUnusedLocal
        mem_usage = None

        def warning():
            warning_msg_list = []
            if cpu_percent >= warning_cpu_percent:
                warning_msg_list.append(f'进程占用cpu过高 ({cpu_percent}% >= {warning_cpu_percent}%)')

            mem_percent = psutil.virtual_memory().percent
            if mem_percent >= warning_mem_percent:
                warning_msg_list.append(f'系统内存占用过高 ({mem_percent}% >= {warning_mem_percent}%)')

            if thread_count >= warning_thread_count:
                warning_msg_list.append(f'线程数过多 ({thread_count} >= {warning_thread_count})')

            if len(warning_msg_list) != 0:
                warning_msg_list.insert(0, '硬件占用告警，占用过高可能导致系统卡死！')
                warning_msg_list.append('')
                self.log('\n'.join(warning_msg_list), topic='warning')

        while True:
            # 获取CPU占用率（0~100）
            cpu_percent = process.cpu_percent()
            # 获取内存占用（MB）
            mem_usage = round(process.memory_info().rss / 1024 / 1024, 2)
            thread_count = active_count()
            # 获取网络占用情况
            # network_info = psutil.net_io_counters()
            # network_bytes_sent = network_info.bytes_sent
            # network_bytes_received = network_info.bytes_recv

            # 打印信息
            msg = ', '.join([
                f'线程数: {thread_count}',
                f'CPU占用: {cpu_percent}%',
                f'内存占用: {mem_usage}MB',
                # f"发送的字节数: {network_bytes_sent}",
                # f"接收的字节数: {network_bytes_received}",
            ])
            self.log(msg, topic='log')

            if enable_warning is True:
                # 警告
                warning()

            # 等待一段时间
            sleep(interval)


class FindUpdatePlugin(JmOptionPlugin):
    """
    参考: https://github.com/hect0x7/JMComic-Crawler-Python/issues/95
    """
    plugin_key = 'find_update'

    def invoke(self, **kwargs) -> None:
        self.download_album_with_find_update(kwargs or {})

    def download_album_with_find_update(self, dic):
        from .api import download_album
        from .jm_downloader import JmDownloader

        dic: Dict[str, int]

        # 带入漫画id, 章节id(第x章)，寻找该漫画下第x章节後的所有章节Id
        def find_update(album: JmAlbumDetail):
            if album.album_id not in dic:
                return album

            photo_ls = []
            photo_begin = int(dic[album.album_id])
            is_new_photo = False

            for photo in album:
                if is_new_photo:
                    photo_ls.append(photo)

                if int(photo.photo_id) == photo_begin:
                    is_new_photo = True

            return photo_ls

        class FindUpdateDownloader(JmDownloader):
            def filter_iter_objs(self, detail):
                if not detail.is_album():
                    return detail

                detail: JmAlbumDetail
                return find_update(detail)

        # 调用下载api，指定option和downloader
        download_album(
            jm_album_id=dic.keys(),
            option=self.option,
            downloader=FindUpdateDownloader,
        )


class ZipPlugin(JmOptionPlugin):
    plugin_key = 'zip'

    # noinspection PyAttributeOutsideInit
    def invoke(self,
               album: JmAlbumDetail,
               downloader,
               delete_original_file=False,
               level='photo',
               filename_rule='Ptitle',
               suffix='zip',
               zip_dir='./'
               ) -> None:

        from .jm_downloader import JmDownloader
        downloader: JmDownloader
        self.downloader = downloader
        self.level = level
        self.delete_original_file = delete_original_file

        # 确保压缩文件所在文件夹存在
        zip_dir = JmcomicText.parse_to_abspath(zip_dir)
        mkdir_if_not_exists(zip_dir)

        # 原文件夹 -> zip文件
        dir_zip_dict: Dict[str, Optional[str]] = {}
        photo_dict = downloader.all_downloaded[album]

        if level == 'album':
            zip_path = self.get_zip_path(album, None, filename_rule, suffix, zip_dir)
            dir_path = self.zip_album(album, photo_dict, zip_path)
            if dir_path is not None:
                # 要删除这个album文件夹
                dir_zip_dict[dir_path] = zip_path
                # 也要删除album下的photo文件夹
                for d in files_of_dir(dir_path):
                    dir_zip_dict[d] = None

        elif level == 'photo':
            for photo, image_list in photo_dict.items():
                zip_path = self.get_zip_path(None, photo, filename_rule, suffix, zip_dir)
                dir_path = self.zip_photo(photo, image_list, zip_path)
                if dir_path is not None:
                    dir_zip_dict[dir_path] = zip_path

        else:
            ExceptionTool.raises(f'Not Implemented Zip Level: {level}')

        self.after_zip(dir_zip_dict)

    def zip_photo(self, photo, image_list: list, zip_path: str) -> Optional[str]:
        """
        压缩photo文件夹
        :returns: photo文件夹路径
        """
        photo_dir = self.option.decide_image_save_dir(photo) \
            if len(image_list) == 0 \
            else os.path.dirname(image_list[0][0])

        all_filepath = set(map(lambda t: self.unified_path(t[0]), image_list))

        return self.do_zip(photo_dir,
                           zip_path,
                           all_filepath,
                           f'压缩章节[{photo.photo_id}]成功 → {zip_path}',
                           )

    @staticmethod
    def unified_path(f):
        return fix_filepath(f, os.path.isdir(f))

    def zip_album(self, album, photo_dict: dict, zip_path) -> Optional[str]:
        """
        压缩album文件夹
        :returns: album文件夹路径
        """
        all_filepath: Set[str] = set()

        def addpath(f):
            all_filepath.update(set(f))

        album_dir = self.option.decide_album_dir(album)
        # addpath(self.option.decide_image_save_dir(photo) for photo in photo_dict.keys())
        addpath(path for ls in photo_dict.values() for path, _ in ls)

        return self.do_zip(album_dir,
                           zip_path,
                           all_filepath,
                           msg=f'压缩本子[{album.album_id}]成功 → {zip_path}',
                           )

    def do_zip(self, source_dir, zip_path, all_filepath, msg):
        if len(all_filepath) == 0:
            self.log('无下载文件，无需压缩', 'skip')
            return None

        from common import backup_dir_to_zip
        backup_dir_to_zip(
            source_dir,
            zip_path,
            acceptor=lambda f: os.path.isdir(f) or self.unified_path(f) in all_filepath
        ).close()

        self.log(msg, 'finish')
        return self.unified_path(source_dir)

    def after_zip(self, dir_zip_dict: Dict[str, Optional[str]]):
        # 是否要删除所有原文件
        if self.delete_original_file is True:
            self.delete_all_files_and_empty_dir(
                all_downloaded=self.downloader.all_downloaded,
                dir_list=list(dir_zip_dict.keys())
            )

    # noinspection PyMethodMayBeStatic
    def get_zip_path(self, album, photo, filename_rule, suffix, zip_dir):
        """
        计算zip文件的路径
        """
        filename = DirRule.apply_rule_directly(album, photo, filename_rule)
        from os.path import join
        return join(
            zip_dir,
            filename + fix_suffix(suffix),
        )

    # noinspection PyMethodMayBeStatic
    def delete_all_files_and_empty_dir(self, all_downloaded: dict, dir_list: List[str]):
        """
        删除所有文件和文件夹
        """
        import os
        for photo_dict in all_downloaded.values():
            for image_list in photo_dict.values():
                for f, _ in image_list:
                    # check not exist
                    if file_not_exists(f):
                        continue

                    os.remove(f)
                    self.log(f'删除原文件: {f}', 'remove')

        for d in sorted(dir_list, reverse=True):
            # check exist
            if file_exists(d):
                os.rmdir(d)
                self.log(f'删除文件夹: {d}', 'remove')


class ClientProxyPlugin(JmOptionPlugin):
    plugin_key = 'client_proxy'

    def invoke(self,
               proxy_client_key,
               whitelist=None,
               **kwargs,
               ) -> None:
        if whitelist is not None:
            whitelist = set(whitelist)

        proxy_clazz = JmModuleConfig.client_impl_class(proxy_client_key)
        clazz_init_kwargs = kwargs
        new_jm_client = self.option.new_jm_client

        def hook_new_jm_client(*args, **kwargs):
            client = new_jm_client(*args, **kwargs)
            if whitelist is not None and client.client_key not in whitelist:
                return client

            self.log(f'proxy client {client} with {proxy_clazz}')
            return proxy_clazz(client, **clazz_init_kwargs)

        self.option.new_jm_client = hook_new_jm_client


class ImageSuffixFilterPlugin(JmOptionPlugin):
    plugin_key = 'image_suffix_filter'

    def invoke(self,
               allowed_orig_suffix=None,
               ) -> None:
        if allowed_orig_suffix is None:
            return

        allowed_suffix_set = set(fix_suffix(suffix) for suffix in allowed_orig_suffix)

        option_decide_cache = self.option.decide_download_cache

        def apply_filter_then_decide_cache(image: JmImageDetail):
            if image.img_file_suffix not in allowed_suffix_set:
                self.log(f'跳过下载图片: {image.tag}，'
                         f'因为其后缀\'{image.img_file_suffix}\'不在允许的后缀集合{allowed_suffix_set}内')
                # hook is_exists True to skip download
                image.is_exists = True
                return True

            # let option decide
            return option_decide_cache(image)

        self.option.decide_download_cache = apply_filter_then_decide_cache


class SendQQEmailPlugin(JmOptionPlugin):
    plugin_key = 'send_qq_email'

    def invoke(self,
               msg_from,
               msg_to,
               password,
               title,
               content,
               album=None,
               downloader=None,
               ) -> None:
        self.require_true(msg_from and msg_to and password, '发件人、收件人、授权码都不能为空')

        from common import EmailConfig
        econfig = EmailConfig(msg_from, msg_to, password)
        epostman = econfig.create_email_postman()
        epostman.send(content, title)

        self.log('Email sent successfully')


class LogTopicFilterPlugin(JmOptionPlugin):
    plugin_key = 'log_topic_filter'

    def invoke(self, whitelist) -> None:
        if whitelist is not None:
            whitelist = set(whitelist)

        old_jm_log = JmModuleConfig.log_executor

        def new_jm_log(topic, msg):
            if whitelist is not None and topic not in whitelist:
                return

            old_jm_log(topic, msg)

        JmModuleConfig.log_executor = new_jm_log


class AutoSetBrowserCookiesPlugin(JmOptionPlugin):
    plugin_key = 'auto_set_browser_cookies'

    accepted_cookies_keys = str_to_set('''
    yuo1
    remember_id
    remember
    ''')

    def invoke(self,
               browser: str,
               domain: str,
               ) -> None:
        """
        坑点预警：由于禁漫需要校验同一设备，使用该插件需要配置自己浏览器的headers，例如

        ```yml
        client:
          postman:
            meta_data:
              headers: {
               # 浏览器headers
              }

        # 插件配置如下：
        plugins:
          after_init:
            - plugin: auto_set_browser_cookies
              kwargs:
                browser: chrome
                domain: 18comic.vip
        ```

        :param browser: chrome/edge/...
        :param domain: 18comic.vip/...
        :return: cookies
        """
        cookies, e = get_browser_cookies(browser, domain, safe=True)

        if cookies is None:
            if isinstance(e, ImportError):
                self.warning_lib_not_install('browser_cookie3')
            else:
                self.log('获取浏览器cookies失败，请关闭浏览器重试')
            return

        self.option.update_cookies(
            {k: v for k, v in cookies.items() if k in self.accepted_cookies_keys}
        )
        self.log('获取浏览器cookies成功')
