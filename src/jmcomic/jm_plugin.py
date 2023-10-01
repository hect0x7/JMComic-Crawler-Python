"""
该文件存放的是option扩展功能类
"""

from .jm_option import *


class JmOptionPlugin:
    plugin_key: str

    def __init__(self, option: JmOption):
        self.option = option

    def invoke(self, **kwargs) -> None:
        """
        执行插件的功能
        @param kwargs: 给插件的参数
        """
        raise NotImplementedError

    @classmethod
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        """
        创建插件实例
        @param option: JmOption对象
        """
        return cls(option)


class JmLoginPlugin(JmOptionPlugin):
    """
    功能：登录禁漫，并保存登录后的cookies，让所有client都带上此cookies
    """
    plugin_key = 'login'

    def invoke(self, username, password) -> None:
        assert isinstance(username, str), '用户名必须是str'
        assert isinstance(password, str), '密码必须是str'

        client = self.option.new_jm_client()
        client.login(username, password)
        cookies = client['cookies']

        postman: dict = self.option.client.postman.src_dict
        meta_data = postman.get('meta_data', {})
        meta_data['cookies'] = cookies
        postman['meta_data'] = meta_data
        jm_debug('plugin.login', '登录成功')


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
            msg = (f'插件`{self.plugin_key}`依赖psutil库，请先安装psutil再使用。'
                   f'安装命令: [pip install psutil]')
            import warnings
            warnings.warn(msg)
            # import sys
            # print(msg, file=sys.stderr)
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
                jm_debug('plugin.psutil.warning', '\n'.join(warning_msg_list))

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
            jm_debug('plugin.psutil.log', msg)

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
            def filter_iter_objs(self, iter_objs):
                if not isinstance(iter_objs, JmAlbumDetail):
                    return iter_objs

                return find_update(iter_objs)

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
        dir_zip_dict = {}
        photo_dict = downloader.all_downloaded[album]

        if level == 'album':
            zip_path = self.get_zip_path(album, None, filename_rule, suffix, zip_dir)
            dir_path = self.zip_album(album, photo_dict, zip_path)
            dir_zip_dict[dir_path] = zip_path

        elif level == 'photo':
            for photo, image_list in photo_dict.items():
                zip_path = self.get_zip_path(None, photo, filename_rule, suffix, zip_dir)
                dir_path = self.zip_photo(photo, image_list, zip_path)
                dir_zip_dict[dir_path] = zip_path

        else:
            ExceptionTool.raises(f'Not Implemented Zip Level: {level}')

        self.after_zip(dir_zip_dict)

    def zip_photo(self, photo, image_list: list, zip_path: str):
        """
        压缩photo文件夹
        @return: photo文件夹路径
        """
        photo_dir = self.option.decide_image_save_dir(photo) \
            if len(image_list) == 0 \
            else os.path.dirname(image_list[0][0])

        all_filepath = set(map(lambda t: t[0], image_list))

        if len(all_filepath) == 0:
            jm_debug('plugin.zip.skip', '无下载文件，无需压缩')
            return

        from common import backup_dir_to_zip
        backup_dir_to_zip(photo_dir, zip_path, acceptor=lambda f: f in all_filepath)
        jm_debug('plugin.zip.finish', f'压缩章节[{photo.photo_id}]成功 → {zip_path}')
        return photo_dir

    def zip_album(self, album, photo_dict: dict, zip_path):
        """
        压缩album文件夹
        @return: album文件夹路径
        """
        album_dir = self.option.decide_album_dir(album)
        all_filepath: Set[str] = set()

        for image_list in photo_dict.values():
            image_list: List[Tuple[str, JmImageDetail]]
            for path, _ in image_list:
                all_filepath.add(path)

        if len(all_filepath) == 0:
            jm_debug('plugin.zip.skip', '无下载文件，无需压缩')
            return

        from common import backup_dir_to_zip
        backup_dir_to_zip(
            album_dir,
            zip_path,
            acceptor=lambda f: f in all_filepath
        )

        jm_debug('plugin.zip.finish', f'压缩本子[{album.album_id}]成功 → {zip_path}')
        return album_dir

    def after_zip(self, dir_zip_dict: Dict[str, str]):
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
        for album, photo_dict in all_downloaded.items():
            for photo, image_list in photo_dict.items():
                for f, image in image_list:
                    os.remove(f)
                    jm_debug('plugin.zip.remove', f'删除原文件: {f}')

        for d in dir_list:
            if len(os.listdir(d)) == 0:
                os.removedirs(d)
                jm_debug('plugin.zip.remove', f'删除文件夹: {d}')


JmModuleConfig.register_plugin(JmLoginPlugin)
JmModuleConfig.register_plugin(UsageLogPlugin)
JmModuleConfig.register_plugin(FindUpdatePlugin)
JmModuleConfig.register_plugin(ZipPlugin)
