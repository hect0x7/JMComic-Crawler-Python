"""
该文件存放的是option插件
"""
import os.path

from .jm_option import *


class PluginValidationException(Exception):

    def __init__(self, plugin: 'JmOptionPlugin', msg: str):
        self.plugin = plugin
        self.msg = msg


class JmOptionPlugin:
    plugin_key: str

    def __init__(self, option: JmOption):
        self.option = option
        self.log_enable = True
        self.delete_original_file = False

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

    def log(self, msg, topic=None):
        if self.log_enable is not True:
            return

        jm_log(
            topic=f'plugin.{self.plugin_key}' + (f'.{topic}' if topic is not None else ''),
            msg=msg
        )

    def require_param(self, case: Any, msg: str):
        """
        专门用于校验参数的方法，会抛出特定异常，由option拦截根据策略进行处理

        :param case: 条件
        :param msg: 报错信息
        """
        if case:
            return

        raise PluginValidationException(self, msg)

    def warning_lib_not_install(self, lib: str):
        msg = (f'插件`{self.plugin_key}`依赖库: {lib}，请先安装{lib}再使用。'
               f'安装命令: [pip install {lib}]')
        import warnings
        warnings.warn(msg)

    def execute_deletion(self, paths: List[str]):
        """
        删除文件和文件夹
        :param paths: 路径列表
        """
        if self.delete_original_file is not True:
            return

        for p in paths:
            if file_not_exists(p):
                continue

            if os.path.isdir(p):
                os.rmdir(p)
                self.log(f'删除文件夹: {p}', 'remove')
            else:
                os.remove(p)
                self.log(f'删除原文件: {p}', 'remove')

    # noinspection PyMethodMayBeStatic
    def execute_cmd(self, cmd):
        """
        执行shell命令，这里采用简单的实现
        :param cmd: shell命令
        """
        return os.system(cmd)

    # noinspection PyMethodMayBeStatic
    def execute_multi_line_cmd(self, cmd: str):
        import subprocess
        subprocess.run(cmd, shell=True, check=True)

    def enter_wait_list(self):
        self.option.need_wait_plugins.append(self)

    def leave_wait_list(self):
        self.option.need_wait_plugins.remove(self)

    def wait_until_finish(self):
        pass


class JmLoginPlugin(JmOptionPlugin):
    """
    功能：登录禁漫，并保存登录后的cookies，让所有client都带上此cookies
    """
    plugin_key = 'login'

    def invoke(self,
               username: str,
               password: str,
               impl=None,
               ) -> None:
        self.require_param(username, '用户名不能为空')
        self.require_param(password, '密码不能为空')

        client = self.option.build_jm_client(impl=impl)
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

    def download_album_with_find_update(self, dic: Dict[str, int]):
        from .api import download_album
        from .jm_downloader import JmDownloader

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
            def do_filter(self, detail):
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
               downloader,
               album: JmAlbumDetail = None,
               photo: JmPhotoDetail = None,
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

        path_to_delete = []
        photo_dict = self.get_downloaded_photo(downloader, album, photo)

        if level == 'album':
            zip_path = self.get_zip_path(album, None, filename_rule, suffix, zip_dir)
            self.zip_album(album, photo_dict, zip_path, path_to_delete)

        elif level == 'photo':
            for photo, image_list in photo_dict.items():
                zip_path = self.get_zip_path(None, photo, filename_rule, suffix, zip_dir)
                self.zip_photo(photo, image_list, zip_path, path_to_delete)

        else:
            ExceptionTool.raises(f'Not Implemented Zip Level: {level}')

        self.after_zip(path_to_delete)

    def get_downloaded_photo(self, downloader, album, photo):
        return (
            downloader.download_success_dict[album]
            if album is not None  # after_album
            else downloader.download_success_dict[photo.from_album]  # after_photo
        )

    def zip_photo(self, photo, image_list: list, zip_path: str, path_to_delete):
        """
        压缩photo文件夹
        """
        photo_dir = self.option.decide_image_save_dir(photo) \
            if len(image_list) == 0 \
            else os.path.dirname(image_list[0][0])

        from common import backup_dir_to_zip
        backup_dir_to_zip(photo_dir, zip_path)

        self.log(f'压缩章节[{photo.photo_id}]成功 → {zip_path}', 'finish')
        path_to_delete.append(self.unified_path(photo_dir))

    @staticmethod
    def unified_path(f):
        return fix_filepath(f, os.path.isdir(f))

    def zip_album(self, album, photo_dict: dict, zip_path, path_to_delete):
        """
        压缩album文件夹
        """

        album_dir = self.option.dir_rule.decide_album_root_dir(album)
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as f:
            for photo in photo_dict.keys():
                # 定位到章节所在文件夹
                photo_dir = self.unified_path(self.option.decide_image_save_dir(photo))
                # 章节文件夹标记为删除
                path_to_delete.append(photo_dir)
                for file in files_of_dir(photo_dir):
                    abspath = os.path.join(photo_dir, file)
                    relpath = os.path.relpath(abspath, album_dir)
                    f.write(abspath, relpath)
        self.log(f'压缩本子[{album.album_id}]成功 → {zip_path}', 'finish')

    def after_zip(self, path_to_delete: List[str]):
        # 删除所有原文件
        dirs = sorted(path_to_delete, reverse=True)
        image_paths = [
            path
            for photo_dict in self.downloader.download_success_dict.values()
            for image_list in photo_dict.values()
            for path, image in image_list
        ]
        self.execute_deletion(image_paths)
        self.execute_deletion(dirs)

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


class ClientProxyPlugin(JmOptionPlugin):
    plugin_key = 'client_proxy'

    def invoke(self,
               proxy_client_key,
               whitelist=None,
               **clazz_init_kwargs,
               ) -> None:
        if whitelist is not None:
            whitelist = set(whitelist)

        proxy_clazz = JmModuleConfig.client_impl_class(proxy_client_key)
        new_jm_client: Callable = self.option.new_jm_client

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
                image.skip = True

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
        self.require_param(msg_from and msg_to and password, '发件人、收件人、授权码都不能为空')

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

        old_jm_log = JmModuleConfig.EXECUTOR_LOG

        def new_jm_log(topic, msg):
            if whitelist is not None and topic not in whitelist:
                return

            old_jm_log(topic, msg)

        JmModuleConfig.EXECUTOR_LOG = new_jm_log


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


# noinspection PyMethodMayBeStatic
class FavoriteFolderExportPlugin(JmOptionPlugin):
    plugin_key = 'favorite_folder_export'

    # noinspection PyAttributeOutsideInit
    def invoke(self,
               save_dir=None,
               zip_enable=False,
               zip_filepath=None,
               zip_password=None,
               delete_original_file=False,
               ):
        self.save_dir = os.path.abspath(save_dir if save_dir is not None else (os.getcwd() + '/export/'))
        self.zip_enable = zip_enable
        self.zip_filepath = os.path.abspath(zip_filepath)
        self.zip_password = zip_password
        self.delete_original_file = delete_original_file
        self.files = []

        mkdir_if_not_exists(self.save_dir)
        mkdir_if_not_exists(of_dir_path(self.zip_filepath))

        self.main()

    def main(self):
        cl = self.option.build_jm_client()
        # noinspection PyAttributeOutsideInit
        self.cl = cl
        page = cl.favorite_folder()

        # 获取所有的收藏夹
        folders = {fid: fname for fid, fname in page.iter_folder_id_name()}
        # 加上特殊收藏栏【全部】
        folders.setdefault('0', '全部')

        # 一个收藏夹一个线程，导出收藏夹数据到文件
        multi_thread_launcher(
            iter_objs=folders.items(),
            apply_each_obj_func=self.handle_folder,
        )

        if not self.zip_enable:
            return

        # 压缩导出的文件
        self.require_param(self.zip_filepath, '如果开启zip，请指定zip_filepath参数（压缩文件保存路径）')

        if self.zip_password is None:
            self.zip_folder_without_password(self.files, self.zip_filepath)
        else:
            self.zip_with_password()

        self.execute_deletion(self.files)

    def handle_folder(self, fid: str, fname: str):
        self.log(f'【收藏夹: {fname}, fid: {fid}】开始获取数据')

        # 获取收藏夹数据
        page_data = self.fetch_folder_page_data(fid)

        # 序列化到文件
        filepath = self.save_folder_page_data_to_file(page_data, fid, fname)

        if filepath is None:
            self.log(f'【收藏夹: {fname}, fid: {fid}】收藏夹无数据')
            return

        self.log(f'【收藏夹: {fname}, fid: {fid}】保存文件成功 → [{filepath}]')
        self.files.append(filepath)

    def fetch_folder_page_data(self, fid):
        # 一页一页获取，不使用并行
        page_data = list(self.cl.favorite_folder_gen(folder_id=fid))
        return page_data

    def save_folder_page_data_to_file(self, page_data: List[JmFavoritePage], fid: str, fname: str):
        from os import path
        filepath = path.abspath(path.join(self.save_dir, fix_windir_name(f'【{fid}】{fname}.csv')))

        data = []
        for page in page_data:
            for aid, extra in page.content:
                data.append(
                    (aid, extra.get('author', '') or JmModuleConfig.DEFAULT_AUTHOR, extra['name'])
                )

        if len(data) == 0:
            return

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('id,author,name\n')
            for item in data:
                f.write(','.join(item) + '\n')

        return filepath

    def zip_folder_without_password(self, files, zip_path):
        """
        压缩文件夹中的文件并设置密码

        :param files: 要压缩的文件的绝对路径的列表
        :param zip_path: 压缩文件的保存路径
        """
        import zipfile

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 获取文件夹中的文件列表并将其添加到 ZIP 文件中
            for file in files:
                zipf.write(file, arcname=of_file_name(file))

    def zip_with_password(self):
        # 构造shell命令
        cmd_list = f'''
        cd {self.save_dir}
        7z a "{self.zip_filepath}" "./" -p{self.zip_password} -mhe=on > "../7z_output.txt"
        
        '''
        self.log(f'运行命令: {cmd_list}')

        # 执行
        self.execute_multi_line_cmd(cmd_list)


class ConvertJpgToPdfPlugin(JmOptionPlugin):
    plugin_key = 'j2p'

    def check_image_suffix_is_valid(self, std_suffix):
        """
        检查option配置的图片后缀转换，目前限制使用Magick时只能搭配jpg
        暂不探究Magick是否支持更多图片格式
        """
        cur_suffix: Optional[str] = self.option.download.image.suffix

        ExceptionTool.require_true(
            cur_suffix is not None and cur_suffix.endswith(std_suffix),
            '请把图片的后缀转换配置为jpg，不然无法使用Magick！'
            f'（当前配置是[{cur_suffix}]）\n'
            f'配置模板如下: \n'
            f'```\n'
            f'download:\n'
            f'  image:\n'
            f'    suffix: {std_suffix} # 当前配置是{cur_suffix}\n'
            f'```'
        )

    def invoke(self,
               photo: JmPhotoDetail,
               downloader=None,
               pdf_dir=None,
               filename_rule='Pid',
               quality=100,
               delete_original_file=False,
               override_cmd=None,
               override_jpg=None,
               **kwargs,
               ):
        self.delete_original_file = delete_original_file

        # 检查图片后缀配置
        suffix = override_jpg or '.jpg'
        self.check_image_suffix_is_valid(suffix)

        # 处理文件夹配置
        filename = DirRule.apply_rule_directly(None, photo, filename_rule)
        photo_dir = self.option.decide_image_save_dir(photo)

        # 处理生成的pdf文件的路径
        if pdf_dir is None:
            pdf_dir = photo_dir
        else:
            pdf_dir = fix_filepath(pdf_dir, True)
            mkdir_if_not_exists(pdf_dir)

        pdf_filepath = os.path.join(pdf_dir, f'{filename}.pdf')

        # 生成命令
        def generate_cmd():
            return (
                    override_cmd or
                    'magick convert -quality {quality} "{photo_dir}*{suffix}" "{pdf_filepath}"'
            ).format(
                quality=quality,
                photo_dir=photo_dir,
                suffix=suffix,
                pdf_filepath=pdf_filepath,
            )

        cmd = generate_cmd()
        self.log(f'Execute Command: [{cmd}]')
        code = self.execute_cmd(cmd)

        ExceptionTool.require_true(
            code == 0,
            'jpg图片合并为pdf失败！'
            '请确认你是否安装了magick，安装网站: [https://www.imagemagick.org/]',
        )

        self.log(f'Convert Successfully: JM{photo.id} → {pdf_filepath}')

        if downloader is not None:
            from .jm_downloader import JmDownloader
            downloader: JmDownloader

            paths = [
                path
                for path, image in downloader.download_success_dict[photo.from_album][photo]
            ]

            paths.append(self.option.decide_image_save_dir(photo, ensure_exists=False))
            self.execute_deletion(paths)


class Img2pdfPlugin(JmOptionPlugin):
    plugin_key = 'img2pdf'

    def invoke(self,
               photo: JmPhotoDetail = None,
               album: JmAlbumDetail = None,
               downloader=None,
               pdf_dir=None,
               filename_rule='Pid',
               delete_original_file=False,
               **kwargs,
               ):
        if photo is None and album is None:
            jm_log('wrong_usage', 'img2pdf必须运行在after_photo或after_album时')

        try:
            import img2pdf
        except ImportError:
            self.warning_lib_not_install('img2pdf')
            return

        self.delete_original_file = delete_original_file

        # 处理生成的pdf文件的路径
        pdf_dir = self.ensure_make_pdf_dir(pdf_dir)

        # 处理pdf文件名
        filename = DirRule.apply_rule_directly(album, photo, filename_rule)

        # pdf路径
        pdf_filepath = os.path.join(pdf_dir, f'{filename}.pdf')

        # 调用 img2pdf 把 photo_dir 下的所有图片转为pdf
        img_path_ls, img_dir_ls = self.write_img_2_pdf(pdf_filepath, album, photo)
        self.log(f'Convert Successfully: JM{album or photo} → {pdf_filepath}')

        # 执行删除
        img_path_ls += img_dir_ls
        self.execute_deletion(img_path_ls)

    def write_img_2_pdf(self, pdf_filepath, album: JmAlbumDetail, photo: JmPhotoDetail):
        import img2pdf

        if album is None:
            img_dir_ls = [self.option.decide_image_save_dir(photo)]
        else:
            img_dir_ls = [self.option.decide_image_save_dir(photo) for photo in album]

        img_path_ls = []

        for img_dir in img_dir_ls:
            imgs = files_of_dir(img_dir)
            if not imgs:
                continue
            img_path_ls += imgs

        with open(pdf_filepath, 'wb') as f:
            f.write(img2pdf.convert(img_path_ls))

        return img_path_ls, img_dir_ls

    @staticmethod
    def ensure_make_pdf_dir(pdf_dir: str):
        pdf_dir = pdf_dir or os.getcwd()
        pdf_dir = fix_filepath(pdf_dir, True)
        mkdir_if_not_exists(pdf_dir)
        return pdf_dir


class LongImgPlugin(JmOptionPlugin):
    plugin_key = 'long_img'

    def invoke(self,
               photo: JmPhotoDetail = None,
               album: JmAlbumDetail = None,
               downloader=None,
               img_dir=None,
               filename_rule='Pid',
               delete_original_file=False,
               **kwargs,
               ):
        if photo is None and album is None:
            jm_log('wrong_usage', 'long_img必须运行在after_photo或after_album时')

        try:
            from PIL import Image
        except ImportError:
            self.warning_lib_not_install('PIL')
            return

        self.delete_original_file = delete_original_file

        # 处理文件夹配置
        img_dir = self.get_img_dir(img_dir)

        # 处理生成的长图文件的路径
        filename = DirRule.apply_rule_directly(album, photo, filename_rule)

        # 长图路径
        long_img_path = os.path.join(img_dir, f'{filename}.png')

        # 调用 PIL 把 photo_dir 下的所有图片合并为长图
        img_path_ls = self.write_img_2_long_img(long_img_path, album, photo)
        self.log(f'Convert Successfully: JM{album or photo} → {long_img_path}')

        # 执行删除
        self.execute_deletion(img_path_ls)

    def write_img_2_long_img(self, long_img_path, album: JmAlbumDetail, photo: JmPhotoDetail) -> List[str]:
        import itertools
        from PIL import Image

        if album is None:
            img_dir_items = [self.option.decide_image_save_dir(photo)]
        else:
            img_dir_items = [self.option.decide_image_save_dir(photo) for photo in album]

        img_paths = itertools.chain(*map(files_of_dir, img_dir_items))
        img_paths = filter(lambda x: not x.startswith('.'), img_paths)  # 过滤系统文件

        images = self.open_images(img_paths)

        try:
            resample_method = Image.Resampling.LANCZOS
        except AttributeError:
            resample_method = Image.LANCZOS

        min_img_width = min(img.width for img in images)
        total_height = 0
        for i, img in enumerate(images):
            if img.width > min_img_width:
                images[i] = img.resize((min_img_width, int(img.height * min_img_width / img.width)),
                                       resample=resample_method)
            total_height += images[i].height

        long_img = Image.new('RGB', (min_img_width, total_height))
        y_offset = 0
        for img in images:
            long_img.paste(img, (0, y_offset))
            y_offset += img.height

        long_img.save(long_img_path)
        for img in images:
            img.close()

        return img_paths

    def open_images(self, img_paths: List[str]):
        images = []
        for img_path in img_paths:
            try:
                img = Image.open(img_path)
                images.append(img)
            except IOError as e:
                self.log(f"Failed to open image {img_path}: {e}", 'error')
        return images

    @staticmethod
    def get_img_dir(img_dir: Optional[str]) -> str:
        img_dir = fix_filepath(img_dir or os.getcwd())
        mkdir_if_not_exists(img_dir)
        return img_dir


class JmServerPlugin(JmOptionPlugin):
    plugin_key = 'jm_server'

    default_run_kwargs = {
        'host': '0.0.0.0',
        'port': '80',
        'debug': False,
    }

    from threading import Lock
    single_instance_lock = Lock()

    def __init__(self, option: JmOption):
        super().__init__(option)
        self.run_server_lock = Lock()
        self.running = False
        self.server_thread: Optional[Thread] = None

    def invoke(self,
               password='',
               base_dir=None,
               album=None,
               photo=None,
               downloader=None,
               run=None,
               **kwargs
               ):
        """

        :param password: 密码
        :param base_dir: 初始访问服务器的根路径
        :param album: 为了支持 after_album 这种调用时机
        :param photo: 为了支持 after_album 这种调用时机
        :param downloader: 为了支持 after_album 这种调用时机
        :param run: 用于启动服务器: app.run(**run_kwargs)
        :param kwargs: 用于JmServer构造函数: JmServer(base_dir, password, **kwargs)
        """

        if base_dir is None:
            base_dir = self.option.dir_rule.base_dir

        if run is None:
            run = self.default_run_kwargs
        else:
            base_run_kwargs = self.default_run_kwargs.copy()
            base_run_kwargs.update(run)
            run = base_run_kwargs

        if self.running is True:
            return

        with self.run_server_lock:
            if self.running is True:
                return

            # 服务器的代码位于一个独立库：plugin_jm_server，需要独立安装
            # 源代码仓库：https://github.com/hect0x7/plugin-jm-server
            try:
                import plugin_jm_server
                self.log(f'当前使用plugin_jm_server版本: {plugin_jm_server.__version__}')
            except ImportError:
                self.warning_lib_not_install('plugin_jm_server')
                return

            # 核心函数，启动服务器，会阻塞当前线程
            def blocking_run_server():
                self.server_thread = current_thread()
                self.enter_wait_list()
                server = plugin_jm_server.JmServer(base_dir, password, **kwargs)
                # run方法会阻塞当前线程直到flask退出
                server.run(**run)

            # 对于debug模式，特殊处理
            if run['debug'] is True:
                run.setdefault('use_reloader', False)

                # debug模式只能在主线程启动，判断当前线程是不是主线程
                if current_thread() is not threading.main_thread():
                    # 不是主线程，return
                    return self.warning_wrong_usage_of_debug()
                else:
                    self.running = True
                    # 是主线程，启动服务器
                    blocking_run_server()

            else:
                # 非debug模式，开新线程启动
                threading.Thread(target=blocking_run_server, daemon=True).start()
                atexit_register(self.wait_server_stop)
                self.running = True

    def warning_wrong_usage_of_debug(self):
        self.log('注意！当配置debug=True时，请确保当前插件是在主线程中被调用。\n'
                 '因为如果本插件配置在 [after_album/after_photo] 这种时机调用，\n'
                 '会使得flask框架不在主线程debug运行，\n'
                 '导致报错（ValueError: signal only works in main thread of the main interpreter）。\n',
                 '【基于上述原因，当前线程非主线程，不启动服务器】'
                 'warning'
                 )

    def wait_server_stop(self, proactive=False):
        st = self.server_thread
        if (
                st is None
                or st == current_thread()
                or not st.is_alive()
        ):
            return

        if proactive:
            msg = f'[{self.plugin_key}]的服务器线程仍运行中，可按下ctrl+c结束程序'
        else:
            msg = f'主线程执行完毕，但插件[{self.plugin_key}]的服务器线程仍运行中，可按下ctrl+c结束程序'

        self.log(msg, 'wait')

        while st.is_alive():
            try:
                st.join(timeout=0.5)
            except KeyboardInterrupt:
                self.log('收到ctrl+c，结束程序', 'wait')
                return

    def wait_until_finish(self):
        self.wait_server_stop(proactive=True)

    @classmethod
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        """
        单例模式
        """
        field_name = 'single_instance'

        instance = getattr(cls, field_name, None)
        if instance is not None:
            return instance

        with cls.single_instance_lock:
            instance = getattr(cls, field_name, None)
            if instance is not None:
                return instance
            instance = JmServerPlugin(option)
            setattr(cls, field_name, instance)
            return instance


class SubscribeAlbumUpdatePlugin(JmOptionPlugin):
    plugin_key = 'subscribe_album_update'

    def invoke(self,
               album_photo_dict=None,
               email_notify=None,
               download_if_has_update=True,
               auto_update_after_download=True,
               ) -> None:
        if album_photo_dict is None:
            return

        album_photo_dict: Dict
        for album_id, photo_id in album_photo_dict.copy().items():
            # check update
            try:
                has_update, photo_new_list = self.check_photo_update(album_id, photo_id)
            except JmcomicException as e:
                self.log('Exception happened: ' + str(e), 'check_update.error')
                continue

            if has_update is False:
                continue

            self.log(f'album={album_id}，发现新章节: {photo_new_list}，准备开始下载')

            # send email
            try:
                if email_notify:
                    SendQQEmailPlugin.build(self.option).invoke(**email_notify)
            except PluginValidationException:
                # ignore
                pass

            # download new photo
            if has_update and download_if_has_update:
                self.option.download_photo(photo_new_list)

            if auto_update_after_download:
                album_photo_dict[album_id] = photo_new_list[-1]
                self.option.to_file()

    def check_photo_update(self, album_id: str, photo_id: str):
        client = self.option.new_jm_client()
        album = client.get_album_detail(album_id)

        photo_new_list = []
        is_new_photo = False
        sentinel = int(photo_id)

        for photo in album:
            if is_new_photo:
                photo_new_list.append(photo.photo_id)

            if int(photo.photo_id) == sentinel:
                is_new_photo = True

        return len(photo_new_list) != 0, photo_new_list


class SkipPhotoWithFewImagesPlugin(JmOptionPlugin):
    plugin_key = 'skip_photo_with_few_images'

    def invoke(self,
               at_least_image_count: int,
               photo: Optional[JmPhotoDetail] = None,
               image: Optional[JmImageDetail] = None,
               album: Optional[JmAlbumDetail] = None,
               **kwargs
               ):
        self.try_mark_photo_skip_and_log(photo, at_least_image_count)
        if image is not None:
            self.try_mark_photo_skip_and_log(image.from_photo, at_least_image_count)

    def try_mark_photo_skip_and_log(self, photo: JmPhotoDetail, at_least_image_count: int):
        if photo is None:
            return

        if len(photo) >= at_least_image_count:
            return

        self.log(f'跳过下载章节: {photo.id} ({photo.album_id}[{photo.index}/{len(photo.from_album)}])，'
                 f'因为其图片数: {len(photo)} < {at_least_image_count} (at_least_image_count)')
        photo.skip = True

    @classmethod
    @field_cache()  # 单例
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        return super().build(option)


class DeleteDuplicatedFilesPlugin(JmOptionPlugin):
    """
    https://github.com/hect0x7/JMComic-Crawler-Python/issues/244
    """
    plugin_key = 'delete_duplicated_files'

    @classmethod
    def calculate_md5(cls, file_path):
        import hashlib

        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @classmethod
    def find_duplicate_files(cls, root_folder):
        """递归读取文件夹下所有文件并计算MD5出现次数"""
        import os
        from collections import defaultdict
        md5_dict = defaultdict(list)

        for root, _, files in os.walk(root_folder):
            for file in files:
                file_path = os.path.join(root, file)
                file_md5 = cls.calculate_md5(file_path)
                md5_dict[file_md5].append(file_path)

        return md5_dict

    def invoke(self,
               limit,
               album=None,
               downloader=None,
               delete_original_file=True,
               **kwargs,
               ) -> None:
        if album is None:
            return

        self.delete_original_file = delete_original_file
        # 获取到下载本子所在根目录
        root_folder = self.option.dir_rule.decide_album_root_dir(album)
        self.find_duplicated_files_and_delete(limit, root_folder, album)

    def find_duplicated_files_and_delete(self, limit: int, root_folder: str, album: Optional[JmAlbumDetail] = None):
        md5_dict = self.find_duplicate_files(root_folder)
        # 打印MD5出现次数大于等于limit的文件
        for md5, paths in md5_dict.items():
            if len(paths) >= limit:
                prefix = '' if album is None else f'({album.album_id}) '
                message = [prefix + f'MD5: {md5} 出现次数: {len(paths)}'] + \
                          [f'  {path}' for path in paths]
                self.log('\n'.join(message))
                self.execute_deletion(paths)


class ReplacePathStringPlugin(JmOptionPlugin):
    plugin_key = 'replace_path_string'

    def invoke(self,
               replace: Dict[str, str],
               ):
        if not replace:
            return

        old_decide_dir = self.option.decide_image_save_dir

        def new_decide_dir(photo, ensure_exists=True) -> str:
            original_path: str = old_decide_dir(photo, False)
            for k, v in replace.items():
                original_path = original_path.replace(k, v)

            if ensure_exists:
                JmcomicText.try_mkdir(original_path)

            return original_path

        self.option.decide_image_save_dir = new_decide_dir
