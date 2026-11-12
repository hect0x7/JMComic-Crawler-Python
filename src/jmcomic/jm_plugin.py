"""
该文件存放的是option插件
"""

import atexit
import threading
from collections import deque
from threading import RLock, Thread, current_thread

from .jm_async_downloader import JmAsyncDownloader
from .jm_downloader import JmDownloader
from .jm_option import *
from .jm_runtime import JmTempRuntime
from .jm_task_context import bind_jm_task_context, JTC


class PluginValidationException(Exception):

    def __init__(self, plugin: 'JmOptionPlugin', msg: str):
        self.plugin = plugin
        self.msg = msg


class JmOptionPlugin:
    plugin_key: str
    # 插件运行所需的依赖库。
    # 元素可以是 import 模块名（如 'psutil'），或者元组 (import_name, pip_pkg_name)。
    plugin_dependencies: tuple = ()

    @classmethod
    def required_dependencies_for(cls, kwargs: dict) -> tuple:
        """
        返回该插件在给定 kwargs 配置下实际需要的依赖库，供依赖策略校验使用。

        默认返回类声明的 plugin_dependencies。
        插件可按配置重写此方法，避免对合法配置误报
        （如未加密的 zip 用标准库 zipfile 即可，无需 pyzipper/py7zr）。
        """
        return cls.plugin_dependencies

    @classmethod
    def parse_dependency_spec(cls, dep: Union[str, Tuple[str, str]]) -> Tuple[str, str]:
        """
        解析依赖规格，返回 (import_name, pip_pkg_name)。
        """
        if isinstance(dep, tuple):
            return dep[0], dep[1]
        return dep, dep

    @classmethod
    def check_plugin_dependency(cls, kwargs: dict, strategy: str = 'failed-fast') -> None:
        """
        检查当前插件在给定配置下所需的依赖库是否已安装，并按全局策略处理缺失情况。

        该方法由 JmOption 初始化（__init__）阶段在执行 after_init 之前统一触发，
        确保依赖问题在任务启动伊始即被捕获或解决。

        :param kwargs: 当前插件在 option 中配置的参数字典，用于动态推断依赖
        :param strategy: 依赖处理策略，对应配置 plugins.dependencies_strategy：
            - 'failed-fast': 快速失败（默认），抛出异常并提示具体的解决方案；
            - 'auto-install': 自动通过 pip 安装缺失的依赖包，安装失败严格报错；
            - 'ignore-only-log': 仅输出 warning 日志，不阻断运行。
        """
        import importlib.util

        # 1. 获取当前插件在特定配置下实际需要的可选依赖列表（如未加密 zip 无需额外库）
        req_deps = cls.required_dependencies_for(kwargs)
        if not req_deps:
            return

        # 2. 逐项检查依赖模块是否可用，收集所有缺失项 (import_name, pip_pkg_name)
        missing: List[Tuple[str, str]] = []
        for dep in req_deps:
            import_name, pip_name = cls.parse_dependency_spec(dep)
            if importlib.util.find_spec(import_name) is None:
                missing.append((import_name, pip_name))

        # 全部依赖已就绪，无需后续处理
        if not missing:
            return

        # 3. 整理缺失模块名与 pip 安装包名，拼接命令与提示文案
        missing_import_names = [m[0] for m in missing]
        missing_pip_names = [m[1] for m in missing]
        import_names_str = ', '.join(missing_import_names)
        pip_install_cmd = 'pip install ' + ' '.join(missing_pip_names)

        # 4. 根据策略分发处理：
        if strategy == 'auto-install':
            # 策略一：自动安装。以插件为单位排队调用 pip 安装缺失包
            cls.install_missing_dependencies(missing_pip_names)
        elif strategy == 'ignore-only-log':
            # 策略二：仅打日志。记录警告信息，不抛出异常，保持最大容错
            jm_log(
                topic=f'plugin.{cls.plugin_key}.dependency',
                msg=f'插件 [{cls.plugin_key}] 缺少依赖库 [{import_names_str}]，'
                    f'可能会影响该插件执行。安装命令: [{pip_install_cmd}]'
            )
        else:
            # 策略三：failed-fast（默认）。阻断执行并输出包含3种方案的用户指引
            error_msg = (
                f"插件 [{cls.plugin_key}] 缺少依赖库 [{import_names_str}]，无法执行插件。有3种解决方案需要你选择一种手动执行：\n"
                f"1. 仅安装该库，手动执行: {pip_install_cmd}\n"
                f"2. 一键安装jmcomic插件依赖全家桶，手动执行: pip install jmcomic[plugins]\n"
                f"3. 修改option，让jmcomic自动安装或不要报错\n"
                f"plugins:\n"
                f"    dependencies_strategy: failed-fast # 👈当前默认配置，可配置为以下值\n"
                f"    # auto-install  # 缺失时自动安装依赖\n"
                f"    # ignore-only-log # 缺失时仅打印失败日志不报错"
            )
            ExceptionTool.raises(error_msg)

    @classmethod
    def install_missing_dependencies(cls, pip_packages: List[str]) -> None:
        """
        通过 pip 自动安装缺失的依赖包。如果安装失败则严格抛出异常。
        """
        import sys
        import subprocess
        import importlib

        cmd = [sys.executable, '-m', 'pip', 'install'] + pip_packages
        jm_log(
            topic=f'plugin.{cls.plugin_key}.dependency',
            msg=f'检测到插件 [{cls.plugin_key}] 缺少依赖，auto-install 策略正在自动安装: {" ".join(cmd)}'
        )

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if res.stdout:
                jm_log(topic=f'plugin.{cls.plugin_key}.dependency', msg=res.stdout.strip())
            # 刷新导入缓存，保证后续 import 能够正常找到新装的包
            importlib.invalidate_caches()
            jm_log(
                topic=f'plugin.{cls.plugin_key}.dependency',
                msg=f'插件 [{cls.plugin_key}] 依赖安装成功: {" ".join(pip_packages)}'
            )
        except Exception as e:
            err_output = getattr(e, 'stderr', '') or str(e)
            ExceptionTool.raises(
                f'插件 [{cls.plugin_key}] 自动安装依赖 [{" ".join(pip_packages)}] 失败。\n'
                f'执行命令: {" ".join(cmd)}\n'
                f'错误详情: {err_output}\n'
                f'请排查网络/权限问题，或手动执行: pip install {" ".join(pip_packages)}'
            )

    def __init__(self, option: JmOption):
        self.option = option
        self.log_enable = True
        self.delete_original_file = False
        self.downloader = None

    @staticmethod
    def default_export_filename_rule(is_album: bool) -> str:
        return '[JM{Aid}]{Atitle}' if is_album else '[JM{Pid}]{Ptitle}'

    def collect_export_images(self,
                              album: Optional[JmAlbumDetail],
                              photo: Optional[JmPhotoDetail],
                              ) -> Tuple[List[str], List[str], List[str]]:
        """
        统一收集纯图片合成插件（img2pdf / long_img）的输入图片路径与关联章节目录：
        1. 若存在 downloader 且 download_success_dict 记录了本次已完成（含命中缓存）的图片，
           优先按章节序号与图片页码有序提取，不扫描章节外的无关文件；
        2. 若脱离下载器手动调用插件（无记录），回退按章节目录扫描普通文件。
        """
        if self.downloader is not None and hasattr(self.downloader, 'download_success_dict'):
            if album is not None:
                photo_dict = self.downloader.download_success_dict.get(album, {})
                photo_groups = sorted(photo_dict.items(), key=lambda item: getattr(item[0], 'index', 0))
            else:
                img_tuples = self.downloader.download_success_dict.get(photo.from_album, {}).get(photo, [])
                photo_groups = [(photo, img_tuples)] if img_tuples else []

            recorded_paths = []
            recorded_dirs = []
            seen_paths = set()
            for p, img_list in photo_groups:
                p_dir = self.option.decide_image_save_dir(p, ensure_exists=False)
                if os.path.isdir(p_dir):
                    recorded_dirs.append(p_dir)
                sorted_imgs = sorted(
                    img_list,
                    key=lambda item: (item[1].index, item[1].save_path),
                )
                for _, image in sorted_imgs:
                    path = image.save_path
                    if os.path.isfile(path) and path not in seen_paths:
                        seen_paths.add(path)
                        recorded_paths.append(path)
                        parent = os.path.dirname(path)
                        if parent and os.path.isdir(parent):
                            recorded_dirs.append(parent)

            if recorded_paths:
                unique_dirs = list(dict.fromkeys(recorded_dirs))
                return recorded_paths, unique_dirs, unique_dirs

        if album is None:
            raw_dirs = [self.option.decide_image_save_dir(photo, ensure_exists=False)]
        else:
            raw_dirs = [self.option.decide_image_save_dir(p, ensure_exists=False) for p in album]

        img_dir_ls = [d for d in dict.fromkeys(raw_dirs) if os.path.isdir(d)]
        img_path_ls = []
        seen_paths = set()
        for img_dir in img_dir_ls:
            for p in files_of_dir(img_dir):
                if os.path.isfile(p) and not os.path.basename(p).startswith('.') and p not in seen_paths:
                    seen_paths.add(p)
                    img_path_ls.append(p)

        return img_path_ls, img_dir_ls, raw_dirs

    def invoke(self, **kwargs) -> None:
        """
        执行插件的功能
        :param kwargs: 给插件的参数
        """
        raise NotImplementedError

    @property
    def jm_task_context(self) -> dict:
        """Return the current invocation's isolated task-context snapshot."""
        return JTC.get_context()

    async def async_invoke(self, **kwargs) -> None:
        import asyncio
        await asyncio.to_thread(self.invoke, **kwargs)

    @classmethod
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        """
        创建插件实例
        :param option: JmOption对象
        """
        return cls(option)

    def log(self, msg, topic=None):
        if not self.log_enable:
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
        """
        依赖库未安装时发出警告并抛出 PluginValidationException，由 option 按 plugins.valid 策略处理
        """
        msg = (f'插件`{self.plugin_key}`依赖库: {lib}，请先安装{lib}再使用。'
               f'安装命令: [pip install {lib}]')
        import warnings
        warnings.warn(msg)
        raise PluginValidationException(self, msg)

    def execute_deletion(self, paths: List[str]):
        """
        删除文件和文件夹
        :param paths: 路径列表
        """
        if not self.delete_original_file:
            return

        for p in paths:
            if not os.path.exists(p):
                continue

            if os.path.isdir(p):
                if os.listdir(p):
                    self.log(f'文件夹中存在非本次下载的文件，请手动删除文件夹内的文件: {p}', 'remove.ignore')
                    continue
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

    # noinspection PyMethodMayBeStatic
    def decide_filepath(self,
                        album: Optional[JmAlbumDetail],
                        photo: Optional[JmPhotoDetail],
                        filename_rule: Optional[str], suffix: Optional[str], base_dir: Optional[str],
                        dir_rule_dict: Optional[dict]
                        ):
        """
        根据规则计算一个文件的全路径

        参数 dir_rule_dict 优先级最高，
        如果 dir_rule_dict 不为空，优先用 dir_rule_dict
        否则使用 base_dir + filename_rule + suffix

        当album为空时，自动复制为photo.from_album，防止底层dir_rule的dsl包含Axx报错
        """
        if album is None:
            album = photo.from_album
        filepath: str
        base_dir: str
        if dir_rule_dict is not None:
            dir_rule = DirRule(**dir_rule_dict)
            filepath = dir_rule.apply_rule_to_path(album, photo)
            base_dir = os.path.dirname(filepath)
        else:
            base_dir = base_dir or os.getcwd()
            filepath = os.path.join(base_dir,
                                    DirRule.apply_rule_to_filename(album, photo, filename_rule) + fix_suffix(suffix))

        mkdir_if_not_exists(base_dir)
        return fix_filepath(filepath)

    @classmethod
    def check_encrypt_param(cls, encrypt):
        """
        校验 encrypt 配置的类型与必填密码，返回配置（未配置时返回 None）。
        固定密码必须显式提供 password，随机密码使用 type: random。

        配置用法（YAML）：
        | 配置 | 行为 |
        | 未配置 encrypt / encrypt: null | 不加密 |
        | encrypt: {} | 报错，缺少密码 |
        | encrypt: {password: null} | 报错，null 视为未填写 |
        | encrypt: {password: ""} | 允许传给底层，由加密框架决定是否支持 |
        | encrypt: {password: abc} | 使用指定密码 |
        | encrypt: {type: random} | 生成随机密码 |
        | encrypt: {type: random, password: abc} | 随机密码优先，忽略 password |

        只有 type: random 可以免填 password；其他 type 仍需提供非 null 的 password。

        encrypt 必须是映射（如 {type: random} 或 {password: xxx}），
        写成真值标量（encrypt: enabled）时后续的 encrypt.get(...) 会抛
        AttributeError，绕过了配置校验机制、报错也难以理解，这里统一拦掉。
        """
        if encrypt is None:
            return None
        if not isinstance(encrypt, dict):
            plugin_name = getattr(cls, 'plugin_key', cls.__name__)
            ExceptionTool.raises(
                f'{plugin_name}插件的encrypt参数类型有误，预期为映射（如 {{type: random}} 或 {{password: xxx}}），'
                f'实际类型为{type(encrypt)}'
            )
        # 必须显式配置 password；允许为空字符串，是否可用由底层加密库决定
        if encrypt.get('type') != 'random' and encrypt.get('password') is None:
            ExceptionTool.raises(f'{cls.plugin_key}插件的encrypt参数缺少password，请配置password或使用 type: random')
        return encrypt

    @classmethod
    def encrypt_dependencies(cls, encrypt: dict) -> tuple:
        """
        返回当前加密实现所需的依赖库，由子类按配置重写。
        初始化阶段的依赖预检与 decide_password 共用此声明。
        """
        raise NotImplementedError

    @classmethod
    def generate_random_str(cls, random_length) -> str:
        """
        自动生成随机字符密码，长度由randomlength指定
        """
        import random

        random_str = ''
        base_str = r'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
        base_length = len(base_str) - 1
        for _ in range(random_length):
            random_str += base_str[random.randint(0, base_length)]
        return random_str

    def decide_password(self,
                        encrypt_dict: Optional[dict],
                        filepath: str,
                        ) -> Tuple[Optional[str], bool]:
        """
        统一校验加密配置、检查加密依赖并决定密码。
        未配置加密时返回 (None, False)，否则返回 (密码, 是否为随机密码)。
        每个输出文件调用一次，下层写入方法直接使用返回的密码。
        """
        if encrypt_dict is None:
            return None, False

        # 直接调用插件时也校验配置，不依赖 option 初始化阶段的预检
        self.check_encrypt_param(encrypt_dict)

        # 写出文件之前确认加密依赖可用
        for dependency in self.encrypt_dependencies(encrypt_dict):
            import_name, pip_name = self.parse_dependency_spec(dependency)
            try:
                __import__(import_name)
            except ImportError:
                # 抛出 PluginValidationException，由 option 按插件异常策略处理
                self.warning_lib_not_install(pip_name)

        encrypt_type = encrypt_dict.get('type', '')
        is_random = False

        if encrypt_type == 'random':
            is_random = True
            password = self.generate_random_str(48)
            self.log(f'生成随机密码: [{password}] → [{filepath}]', 'encrypt')
        else:
            password = str(encrypt_dict['password'])
            self.log(f'使用指定密码: [{password}] → [{filepath}]', 'encrypt')

        return password, is_random


class JmLoginPlugin(JmOptionPlugin):
    """
    功能：立即登录禁漫，并把登录态（cookies、user_id）写回 option.auth，让后续创建的 client 都带上登录态。

    - 传入 username/password 时，会先写入 option.auth（保证 auth 中账号与密码成对）；不传则使用 option.auth 中已有的账号。
    - 每次调用都会强制登录，不复用 option.auth 中可能已过期的 cookies。
    """
    plugin_key = 'login'

    def invoke(self,
               username: Optional[str] = None,
               password: Optional[str] = None,
               impl=None,
               ) -> None:
        if username is not None:
            self.option.auth.username = username
        if password is not None:
            self.option.auth.password = password
        self.require_param(self.option.auth.get('username'), '用户名不能为空')
        self.require_param(self.option.auth.get('password'), '密码不能为空')

        self.option.login_with_option_auth(impl=impl, force=True)
        self.log('登录成功')


class UsageLogPlugin(JmOptionPlugin):
    plugin_key = 'usage_log'
    plugin_dependencies = ('psutil',)

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

            if enable_warning:
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
    """
    感谢zip加密功能的贡献者:
        - AXIS5 a.k.a AXIS5Hacker (https://github.com/hect0x7/JMComic-Crawler-Python/pull/375)
    """

    plugin_key = 'zip'
    # zip 依赖取决于加密配置：未加密用标准库 zipfile，加密 zip 用 pyzipper，7z 用 py7zr
    plugin_dependencies = ()

    @classmethod
    def required_dependencies_for(cls, kwargs: dict) -> tuple:
        encrypt = cls.check_encrypt_param(kwargs.get('encrypt'))
        if encrypt is None:
            return ()
        return cls.encrypt_dependencies(encrypt)

    @classmethod
    def encrypt_dependencies(cls, encrypt: dict) -> tuple:
        if encrypt.get('impl', '') == '7z':
            return ('py7zr',)
        return ('pyzipper',)

    # noinspection PyAttributeOutsideInit
    def invoke(self,
               downloader,
               album: JmAlbumDetail = None,
               photo: JmPhotoDetail = None,
               delete_original_file=False,
               level=None,
               filename_rule=None,
               suffix='zip',
               zip_dir='./',
               dir_rule=None,
               encrypt=None,
               ) -> None:

        from .jm_downloader import JmDownloader
        downloader: JmDownloader
        self.downloader = downloader
        # level 自动推导：有 album 则合并打包，只有 photo 则单章打包
        if level is None:
            level = 'album' if album is not None else 'photo'
        if filename_rule is None:
            filename_rule = self.default_export_filename_rule(level == 'album')
        self.level = level
        self.delete_original_file = delete_original_file

        # 确保压缩文件所在文件夹存在
        zip_dir = JmcomicText.parse_to_abspath(zip_dir)
        mkdir_if_not_exists(zip_dir)

        path_to_delete = []
        photo_dict = self.get_downloaded_photo(downloader, album, photo)

        if level == 'album':
            zip_path = self.decide_filepath(album, None, filename_rule, suffix, zip_dir, dir_rule)
            password, is_random = self.decide_password(encrypt, zip_path)
            with self.open_zip_file(zip_path, encrypt, password, is_random) as f:
                self.zip_album(album, photo_dict, path_to_delete, f)

            # 归档关闭成功后打印结果
            self.log(f'{album.alias_cn()}压缩成功！'
                     f'[{album}] → [{zip_path}]', 'finish')
            downloader.record_export_filepath(album, zip_path)

        elif level == 'photo':
            for photo, image_list in photo_dict.items():
                zip_path = self.decide_filepath(photo.from_album, photo, filename_rule, suffix, zip_dir, dir_rule)
                password, is_random = self.decide_password(encrypt, zip_path)
                with self.open_zip_file(zip_path, encrypt, password, is_random) as f:
                    self.zip_photo(image_list, path_to_delete, f)

                # 归档关闭成功后打印结果
                self.log(f'{photo.alias_cn()}压缩成功！'
                         f'[{photo}] → [{zip_path}]', 'finish')
                downloader.record_export_filepath(photo, zip_path)

        else:
            ExceptionTool.raises(f'Not Implemented Zip Level: {level}')

        self.after_zip(path_to_delete, photo_dict)

    # noinspection PyMethodMayBeStatic
    def get_downloaded_photo(self, downloader, album, photo):
        if album is not None:  # after_album
            return downloader.download_success_dict[album]

        # after_photo 只处理当前章节，其他章节可能仍在下载
        return {photo: downloader.download_success_dict[photo.from_album][photo]}

    def zip_photo(self, image_list: list, path_to_delete, f):
        """
        压缩photo已下载的图片，使用 after_image 处理后的当前路径。
        """
        for _, image in image_list:
            path = image.save_path
            f.write(path, os.path.basename(path))
            path_to_delete.append(self.unified_path(os.path.dirname(path)))

    @staticmethod
    def unified_path(f):
        return fix_filepath(f, os.path.isdir(f))

    def zip_album(self, album, photo_dict: dict, path_to_delete, f):
        """
        压缩album已下载的图片，保留包内的章节目录层级。
        """
        album_dir = self.option.dir_rule.decide_album_root_dir(album)
        for photo, image_list in photo_dict.items():
            # 定位包内章节目录，不创建可能已被图片插件移走的原目录
            photo_dir = self.unified_path(self.option.decide_image_save_dir(photo, ensure_exists=False))
            relative_dir = os.path.relpath(photo_dir, album_dir)
            for _, image in image_list:
                path = image.save_path
                relpath = os.path.join(relative_dir, os.path.basename(path))
                f.write(path, relpath)
                # 当前图片所在的目录标记为删除，仅清理空目录
                path_to_delete.append(self.unified_path(os.path.dirname(path)))

    def after_zip(self, path_to_delete: List[str], photo_dict: dict):
        # 归档写入和关闭成功后，删除已压缩的原文件，再清理空目录
        dirs = sorted(set(path_to_delete), reverse=True)
        image_paths = [
            image.save_path
            for image_list in photo_dict.values()
            for _, image in image_list
        ]
        self.execute_deletion(image_paths)
        self.execute_deletion(dirs)

    def open_zip_file(self,
                      zip_path: str,
                      encrypt_dict: Optional[dict],
                      password,
                      is_random,
                      ):
        """
        按配置创建归档对象；加密依赖和密码已由 decide_password 处理。
        """
        if password is None:
            import zipfile
            return zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)

        if encrypt_dict.get('impl', '') == '7z':
            # noinspection PyUnresolvedReferences
            import py7zr
            filters = [{'id': py7zr.FILTER_COPY}]
            return py7zr.SevenZipFile(zip_path, mode='w', password=password, filters=filters, header_encryption=True)

        # noinspection PyUnresolvedReferences
        import pyzipper

        aes_zip_file = pyzipper.AESZipFile(zip_path, "w", pyzipper.ZIP_DEFLATED)
        aes_zip_file.setencryption(pyzipper.WZ_AES, nbits=128)
        password_bytes = str.encode(password)
        aes_zip_file.setpassword(password_bytes)
        # 随机密码同时写入 ZIP 注释，保留现有的密码找回方式
        if is_random:
            aes_zip_file.comment = password_bytes
        return aes_zip_file


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

        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg.attach(MIMEText(content))
        msg['Subject'] = title or content[:10]
        msg['From'] = msg_from
        msg['To'] = msg_to

        with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
            s.login(msg_from, password)
            s.sendmail(msg_from, msg_to, msg.as_string())

        self.log('Email sent successfully')


class LogTopicFilterPlugin(JmOptionPlugin):
    plugin_key = 'log_topic_filter'

    import logging

    class TopicFilter(logging.Filter):
        def __init__(self, whitelist):
            super().__init__()
            self.whitelist = whitelist

        def filter(self, record):
            topic = getattr(record, 'topic', None)
            if self.whitelist is not None and topic is not None and topic not in self.whitelist:
                return False
            return True

    def invoke(self, whitelist) -> None:
        if whitelist is not None:
            whitelist = set(whitelist)

        from jmcomic import jm_logger

        # 删除旧的同类 filter 避免重复
        jm_logger.filters = [f for f in jm_logger.filters if not isinstance(f, LogTopicFilterPlugin.TopicFilter)]
        jm_logger.addFilter(LogTopicFilterPlugin.TopicFilter(whitelist))


# noinspection attribute-outside-init
class ProgressDownloader(JmDownloader):
    progress_console = None
    progress_log_lines = deque(maxlen=6)
    active_progresses = set()
    displayed_progresses = []
    progress_live = None
    progress_ui_lock = RLock()

    def __init__(self, option):
        super().__init__(option)
        self.progress = None

    @staticmethod
    def display_id(entity_id):
        entity_id = str(entity_id)
        return entity_id if entity_id.upper().startswith('JM') else f'JM{entity_id}'

    @classmethod
    def get_progress_console(cls):
        with cls.progress_ui_lock:
            if cls.progress_console is None:
                from rich.console import Console
                cls.progress_console = Console()
            return cls.progress_console

    @classmethod
    def reset_progress_logs(cls):
        with cls.progress_ui_lock:
            cls.progress_log_lines.clear()

    @classmethod
    def configure_progress_log_lines(cls, max_lines):
        with cls.progress_ui_lock:
            cls.progress_log_lines = deque(maxlen=max_lines)

    @classmethod
    def append_progress_log(cls, message):
        with cls.progress_ui_lock:
            cls.progress_log_lines.append(message)
            cls.refresh_progress_ui()

    @classmethod
    def refresh_progress_ui(cls):
        from rich.console import Group

        with cls.progress_ui_lock:
            if cls.progress_live is not None:
                cls.progress_live.update(
                    Group(cls.build_log_panel(), *cls.displayed_progresses),
                    refresh=True,
                )

    @classmethod
    def register_progress(cls, progress):
        if progress.console.is_interactive:
            from rich.live import Live

            with cls.progress_ui_lock:
                if progress in cls.active_progresses:
                    return
                cls.active_progresses.add(progress)
                cls.displayed_progresses.append(progress)
                live_created = cls.progress_live is None
                try:
                    if live_created:
                        # 所有下载器只提供进度内容，终端刷新由唯一的 Live 管理。
                        cls.progress_live = Live(console=progress.console, auto_refresh=False)
                        cls.progress_live.start()
                    cls.refresh_progress_ui()
                except BaseException:
                    # 启动或首帧渲染失败时撤销注册，让后续下载能重新建立界面。
                    cls.active_progresses.discard(progress)
                    cls.displayed_progresses.remove(progress)
                    if live_created and cls.progress_live is not None:
                        try:
                            cls.progress_live.stop()
                        finally:
                            cls.progress_live = None
                    raise

    @classmethod
    def unregister_progress(cls, progress):
        with cls.progress_ui_lock:
            cls.active_progresses.discard(progress)
            if cls.progress_live is not None and not cls.active_progresses:
                try:
                    # 已结束任务保留到最后一个下载器退出，再统一留下最终画面。
                    cls.refresh_progress_ui()
                finally:
                    try:
                        cls.progress_live.stop()
                    finally:
                        cls.progress_live = None
                        cls.displayed_progresses.clear()

    @classmethod
    def build_log_panel(cls):
        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text

        with cls.progress_ui_lock:
            lines = list(cls.progress_log_lines)
            max_lines = cls.progress_log_lines.maxlen

        render_lines = [
            Text(line, overflow='ellipsis', no_wrap=True)
            for line in lines
        ]
        render_lines.extend(Text('') for _ in range(max_lines - len(render_lines)))
        return Panel(
            Group(*render_lines),
            title='[bold cyan]JMComic Logs[/bold cyan]',
            border_style='cyan',
            height=max_lines + 2,
        )

    @classmethod
    def new_rich_progress(cls, console):
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        return Progress(
            SpinnerColumn(style='bright_cyan'),
            TextColumn('{task.description}'),
            BarColumn(
                bar_width=28,
                style='grey37',
                complete_style='bright_cyan',
                finished_style='bright_green',
            ),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            auto_refresh=False,
            disable=not console.is_interactive,
        )

    def refresh_progress(self):
        if self.progress.console.is_interactive:
            ProgressDownloader.refresh_progress_ui()

    def print_non_interactive_summary(self, photo_id=None):
        if self.progress.console.is_interactive:
            return

        if photo_id is not None:
            done = self.chapter_done[photo_id]
            total = self.chapter_total[photo_id]
            succeeded = done == total
            icon = '✓' if succeeded else '⚠'
            status = '下载完成' if succeeded else '下载结束'
            chapter_name = f'章节-{ProgressDownloader.display_id(photo_id)}'
            self.progress.console.print(
                f'{icon} {status}：{chapter_name}，图片 {done}/{total}'
            )
            return

        image_done = sum(self.chapter_done.values())
        image_total = sum(self.chapter_total.values())
        succeeded = self.album_done == self.album_total and image_done == image_total
        icon = '✓' if succeeded else '⚠'
        status = '下载完成' if succeeded else '下载结束'
        album_name = f'本子-{ProgressDownloader.display_id(self.album_id)}'
        self.progress.console.print(
            f'{icon} {status}：{album_name}，章节 {self.album_done}/{self.album_total}，'
            f'图片 {image_done}/{image_total}'
        )

    def before_album(self, album):
        super().before_album(album)
        self.start_progress(len(album), album.id)

    def start_progress(self, album_total=None, album_id=None):
        from threading import Lock

        self.progress_lock = Lock()
        self.album_total = album_total
        self.album_id = album_id
        self.album_done = 0
        self.chapter_done = {}
        self.chapter_total = {}
        self.chapter_tasks = {}
        console = ProgressDownloader.get_progress_console()
        self.progress = self.new_rich_progress(console)
        ProgressDownloader.register_progress(self.progress)
        self.album_task = None
        if album_total is not None:
            self.album_task = self.progress.add_task(
                f'[bold magenta]本子-{self.display_id(album_id)}[/bold magenta]',
                total=album_total,
            )
        self.refresh_progress()

    def before_photo(self, photo):
        super().before_photo(photo)
        if self.progress is None:
            self.start_progress()
        with self.progress_lock:
            self.chapter_done[photo.id] = 0
            self.chapter_total[photo.id] = len(photo)
            self.chapter_tasks[photo.id] = self.progress.add_task(
                f'[cyan]章节-{self.display_id(photo.id)}[/cyan]',
                total=len(photo),
            )
            self.refresh_progress()

    def after_image(self, image, img_save_path):
        super().after_image(image, img_save_path)
        photo_id = image.from_photo.id
        with self.progress_lock:
            self.chapter_done[photo_id] += 1
            self.progress.advance(self.chapter_tasks[photo_id])
            self.refresh_progress()

    def after_photo(self, photo):
        super().after_photo(photo)
        with self.progress_lock:
            done = self.chapter_done[photo.id]
            succeeded = done == len(photo)
            color = 'bold green' if succeeded else 'bold yellow'
            icon = '✓' if succeeded else '⚠'
            self.progress.update(
                self.chapter_tasks[photo.id],
                description=f'[{color}]{icon} 章节-{self.display_id(photo.id)}[/{color}]',
            )
            if succeeded:
                self.album_done += 1
                if self.album_task is not None:
                    self.progress.advance(self.album_task)
            self.refresh_progress()
            if self.album_total is None:
                self.print_non_interactive_summary(photo.id)

    def after_album(self, album):
        super().after_album(album)
        with self.progress_lock:
            succeeded = self.album_done == len(album)
            color = 'bold green' if succeeded else 'bold yellow'
            icon = '✓' if succeeded else '⚠'
            self.progress.update(
                self.album_task,
                description=f'[{color}]{icon} 本子-{self.display_id(self.album_id)}[/{color}]',
            )
            self.refresh_progress()
            self.print_non_interactive_summary()
        self.stop_progress()

    def stop_progress(self):
        if self.progress is None:
            return
        progress = self.progress
        try:
            ProgressDownloader.unregister_progress(progress)
        finally:
            self.progress = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.stop_progress()
        finally:
            super().__exit__(exc_type, exc_val, exc_tb)


# noinspection attribute-outside-init
class AsyncProgressDownloader(JmAsyncDownloader):

    def __init__(self, option, *args, **kwargs):
        super().__init__(option, *args, **kwargs)
        self.progress = None

    def start_progress(self, album_total=None, album_id=None):
        from threading import Lock

        self.progress_lock = Lock()
        self.album_total = album_total
        self.album_id = album_id
        self.album_done = 0
        self.chapter_done = {}
        self.chapter_total = {}
        self.chapter_tasks = {}
        console = ProgressDownloader.get_progress_console()
        self.progress = ProgressDownloader.new_rich_progress(console)
        ProgressDownloader.register_progress(self.progress)
        self.album_task = None
        if album_total is not None:
            self.album_task = self.progress.add_task(
                f'[bold magenta]本子-{ProgressDownloader.display_id(album_id)}[/bold magenta]',
                total=album_total,
            )
        ProgressDownloader.refresh_progress(self)

    async def before_album(self, album):
        await super().before_album(album)
        self.start_progress(len(album), album.id)

    async def before_photo(self, photo):
        await super().before_photo(photo)
        if self.progress is None:
            self.start_progress()
        with self.progress_lock:
            self.chapter_done[photo.id] = 0
            self.chapter_total[photo.id] = len(photo)
            self.chapter_tasks[photo.id] = self.progress.add_task(
                f'[cyan]章节-{ProgressDownloader.display_id(photo.id)}[/cyan]',
                total=len(photo),
            )
            ProgressDownloader.refresh_progress(self)

    async def after_image(self, image, img_save_path):
        await super().after_image(image, img_save_path)
        photo_id = image.from_photo.id
        with self.progress_lock:
            self.chapter_done[photo_id] += 1
            self.progress.advance(self.chapter_tasks[photo_id])
            ProgressDownloader.refresh_progress(self)

    async def after_photo(self, photo):
        await super().after_photo(photo)
        with self.progress_lock:
            done = self.chapter_done[photo.id]
            succeeded = done == len(photo)
            color = 'bold green' if succeeded else 'bold yellow'
            icon = '✓' if succeeded else '⚠'
            self.progress.update(
                self.chapter_tasks[photo.id],
                description=f'[{color}]{icon} 章节-{ProgressDownloader.display_id(photo.id)}[/{color}]',
            )
            if succeeded:
                self.album_done += 1
                if self.album_task is not None:
                    self.progress.advance(self.album_task)
            ProgressDownloader.refresh_progress(self)
            if self.album_total is None:
                ProgressDownloader.print_non_interactive_summary(self, photo.id)

    async def after_album(self, album):
        await super().after_album(album)
        with self.progress_lock:
            succeeded = self.album_done == len(album)
            color = 'bold green' if succeeded else 'bold yellow'
            icon = '✓' if succeeded else '⚠'
            self.progress.update(
                self.album_task,
                description=f'[{color}]{icon} 本子-{ProgressDownloader.display_id(self.album_id)}[/{color}]',
            )
            ProgressDownloader.refresh_progress(self)
            ProgressDownloader.print_non_interactive_summary(self)
        self.stop_progress()

    def stop_progress(self):
        if self.progress is None:
            return
        progress = self.progress
        try:
            ProgressDownloader.unregister_progress(progress)
        finally:
            self.progress = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            self.stop_progress()
        finally:
            await super().__aexit__(exc_type, exc_val, exc_tb)


class DownloadProgressPlugin(JmOptionPlugin):
    plugin_key = 'download_progress'
    plugin_dependencies = ('rich',)
    log_file = 'jmcomic-download.log'

    @staticmethod
    def preview(album_ids, photo_ids):
        """使用模拟任务预览真实进度界面，不创建 Client、Option 或文件。"""
        from datetime import datetime
        from random import Random
        from time import sleep

        random = Random()

        def log(topic, message, worker):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ProgressDownloader.append_progress_log(
                f'{timestamp} [mock-worker-{worker}] [{topic}] {message}'
            )

        if not album_ids and not photo_ids:
            album_ids = ['100001', '100002']
        console = ProgressDownloader.get_progress_console()
        console.print('模拟下载：不请求网络、不写入图片或日志文件，也不加载 --option 配置。')
        previews = []
        ProgressDownloader.reset_progress_logs()
        try:
            for kind, ids in (('本子', album_ids), ('章节', photo_ids)):
                for entity_id in ids:
                    progress = ProgressDownloader.new_rich_progress(console)
                    name = f'{kind}-{ProgressDownloader.display_id(entity_id)}'
                    album_task = progress.add_task(name, total=2) if kind == '本子' else None
                    chapters = []
                    for index in range(2 if album_task is not None else 1):
                        chapter_name = f'章节-JM{entity_id}{index + 1:02}' if album_task is not None else name
                        total = random.randint(12, 32)
                        task_id = progress.add_task(
                            f'  {chapter_name}' if album_task is not None else chapter_name,
                            total=total, start=False,
                        )
                        chapters.append({
                            'task_id': task_id, 'name': chapter_name,
                            'next_tick': random.randint(0, 8),
                            'interval': random.randint(1, 3),
                            'started': False, 'retried': False,
                        })
                    worker = len(previews) + 1
                    previews.append((progress, album_task, chapters, name, worker))
                    ProgressDownloader.register_progress(progress)
                    if album_task is not None:
                        log('album.before', f'本子获取成功: [{entity_id}], 章节数: [2], 标题: [模拟本子]', worker)

            tick = 0
            while any(not task.finished for progress, _, _, _, _ in previews for task in progress.tasks):
                if console.is_interactive:
                    sleep(random.uniform(0.08, 0.16))
                for progress, album_task, chapters, name, worker in previews:
                    tasks = {task.id: task for task in progress.tasks}
                    for chapter in chapters:
                        task = tasks[chapter['task_id']]
                        if task.finished or tick < chapter['next_tick']:
                            continue
                        chapter_name = chapter['name']
                        if not chapter['started']:
                            progress.start_task(task.id)
                            chapter['started'] = True
                            log('photo.before', f'开始下载章节: {chapter_name}, 图片数为[{int(task.total)}]', worker)
                        elif not chapter['retried'] and random.random() < 0.08:
                            chapter['retried'] = True
                            chapter['next_tick'] = tick + random.randint(3, 6)
                            log('image.retry',
                                f'{chapter_name} 图片 {int(task.completed) + 1:05}.jpg 请求超时，准备重试', worker)
                            continue
                        advance = min(random.randint(1, 3), int(task.total - task.completed))
                        for page in range(int(task.completed) + 1, int(task.completed) + advance + 1):
                            progress.advance(task.id)
                            log('image.after', f'图片下载完成: {chapter_name}/{page:05}.jpg [{page}/{int(task.total)}]',
                                worker)
                        chapter['next_tick'] = tick + chapter['interval'] + random.randint(0, 1)
                        if task.finished:
                            progress.update(task.id, description=f'✓ {task.description}')
                            log('photo.after',
                                f'章节下载完成: [{chapter_name}], 图片 {int(task.total)}/{int(task.total)}',
                                worker)
                    if album_task is not None:
                        was_finished = tasks[album_task].finished
                        done = sum(tasks[chapter['task_id']].finished for chapter in chapters)
                        progress.update(album_task, completed=done)
                        if done == len(chapters) and not was_finished:
                            progress.update(album_task, description=f'✓ {name}')
                            log('album.after', f'本子下载完成: [{name}], 章节 {done}/{len(chapters)}', worker)
                    ProgressDownloader.refresh_progress_ui()
                tick += 1

            if not console.is_interactive:
                for progress, album_task, chapters, name, worker in previews:
                    console.print(f'模拟完成：{name}')
        finally:
            for progress, album_task, chapters, name, worker in previews:
                ProgressDownloader.unregister_progress(progress)
            ProgressDownloader.reset_progress_logs()
        console.print('模拟结束，未下载任何文件。')

    @staticmethod
    def cli_no_progress_notice():
        if not JTC.get_context_value('cli_no_progress'):
            return ''

        return (
            '\n[bold yellow]⚠ 检测到命令行参数 --no-progress，'
            '但是当前 Option 已配置 download_progress 插件，因此未关闭进度条。[/bold yellow]'
        )

    @classmethod
    def build(cls, option):
        plugin = cls(option)
        try:
            import rich
        except ImportError:
            plugin.warning_lib_not_install('rich')
        return plugin

    def redirect_log_to_file(self, log_file=None):
        import logging
        from pathlib import Path
        from .jm_config import jm_logger

        class ProgressLogHandler(logging.Handler):
            def emit(self, record):
                try:
                    ProgressDownloader.append_progress_log(self.format(record))
                except Exception:
                    self.handleError(record)

        log_path = Path(log_file or self.log_file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            '%(asctime)s [%(threadName)s] [%(topic)s] '
            '%(message)s'
        )
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)

        for old_handler in jm_logger.handlers[:]:
            jm_logger.removeHandler(old_handler)

        ProgressDownloader.reset_progress_logs()
        jm_logger.addHandler(file_handler)
        if ProgressDownloader.get_progress_console().is_interactive:
            progress_handler = ProgressLogHandler()
            progress_handler.setFormatter(formatter)
            jm_logger.addHandler(progress_handler)
        jm_logger.setLevel(logging.INFO)
        jm_logger.propagate = False
        return log_path

    @staticmethod
    def print_non_interactive_notice(console, log_path):
        from rich.panel import Panel

        console.print(Panel.fit(
            '[bold green]✓ 下载进度插件已启用[/bold green]'
            f'{DownloadProgressPlugin.cli_no_progress_notice()}\n\n'
            '[cyan]显示模式[/cyan]：完成后汇总\n'
            '[cyan]动态进度[/cyan]：请在 Terminal / PowerShell 中运行\n\n'
            '[yellow]详细日志[/yellow]\n'
            f'{log_path}',
            title='[bold magenta]JMComic Progress[/bold magenta]',
            border_style='bright_blue',
        ))

    def invoke(self,
               log_file='jmcomic-download.log',
               terminal_log_lines=6,
               ):
        from rich.panel import Panel

        self.require_param(
            isinstance(terminal_log_lines, int)
            and not isinstance(terminal_log_lines, bool)
            and terminal_log_lines > 0,
            'terminal_log_lines 必须是大于 0 的整数',
        )
        ProgressDownloader.configure_progress_log_lines(terminal_log_lines)
        self.log_path = self.redirect_log_to_file(log_file)
        ProgressDownloader.use()
        AsyncProgressDownloader.use()
        self.log('已将默认 Downloader 替换为 ProgressDownloader')
        self.log('已将默认 Async Downloader 替换为 AsyncProgressDownloader')
        self.log(f'普通日志只写入文件: {self.log_path}')
        console = ProgressDownloader.get_progress_console()
        if console.is_interactive:
            self.log('当前为交互终端，显示本子、章节两级彩色动态进度')
            console.print(Panel.fit(
                '[bold green]✓ 彩色下载进度插件已启用[/bold green]'
                f'{self.cli_no_progress_notice()}\n'
                '[cyan]Sync[/cyan]：ProgressDownloader\n'
                '[cyan]Async[/cyan]：AsyncProgressDownloader\n'
                f'[yellow]详细日志[/yellow]：{self.log_path}\n'
                '[dim]终端只显示进度，普通日志不会刷屏[/dim]',
                title='[bold magenta]JMComic Progress[/bold magenta]',
                border_style='bright_blue',
            ))
        else:
            self.log('当前不是交互终端，关闭动态进度，只在下载结束后输出汇总')
            self.print_non_interactive_notice(console, self.log_path)


class AutoSetBrowserCookiesPlugin(JmOptionPlugin):
    plugin_key = 'auto_set_browser_cookies'
    plugin_dependencies = ('browser_cookie3',)

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
        if not browser:
            raise ValueError('browser参数不能为空')

        try:
            import browser_cookie3
            cookie_jar = getattr(browser_cookie3, browser)(domain_name=domain)
            cookies = {c.name: c.value for c in cookie_jar}
            e = None
        except BaseException as err:
            cookies, e = None, err

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
               max_retry=2,
               ):
        self.save_dir = os.path.abspath(save_dir if save_dir is not None else (os.getcwd() + '/export/'))
        self.zip_enable = zip_enable
        self.zip_filepath = os.path.abspath(zip_filepath)
        self.zip_password = zip_password
        self.delete_original_file = delete_original_file
        # max_retry 表示「首次失败后的重试次数」，所以总尝试次数是 max_retry + 1。
        # 允许配 0 表示不重试（只尝试一次），不要把它强行抬成 1。
        self.max_retry = max(0, int(max_retry))
        self.files = []
        self.failed_folders = []

        mkdir_if_not_exists(self.save_dir)
        mkdir_if_not_exists(os.path.dirname(self.zip_filepath))

        self.main()

    def main(self):
        # 收藏夹需要登录：auth 配置了账号密码时先确保已登录（已登录则跳过），规则与下载接口一致
        if self.option.auth.get('username') and self.option.auth.get('password'):
            self.option.login_with_option_auth()

        cl = self.option.build_jm_client()
        # noinspection PyAttributeOutsideInit
        self.cl = cl
        page = cl.favorite_folder()

        # 获取所有的收藏夹
        folders = {fid: fname for fid, fname in page.iter_folder_id_name()}
        # 加上特殊收藏栏【全部】
        folders.setdefault('0', '全部')

        # 一个收藏夹一个线程，导出收藏夹数据到文件
        with JmTempRuntime(workers=len(folders)) as launcher:
            launcher.multi_thread_launcher(
                iter_objs=folders.items(),
                apply_each_obj_func=bind_jm_task_context(self.handle_folder),
            )

        # 压缩导出的文件（放在失败检查之前：即便有收藏夹失败，
        # 已经成功抓下来的那部分也应该照常打包，不能因为一个收藏夹失败就丢掉整批数据）
        if self.zip_enable:
            self.require_param(self.zip_filepath, '如果开启zip，请指定zip_filepath参数（压缩文件保存路径）')

            if self.zip_password is None:
                self.zip_folder_without_password(self.files, self.zip_filepath)
            else:
                self.zip_with_password(self.files, self.zip_filepath)

            self.execute_deletion(self.files)

        # 汇总导出失败的收藏夹，避免数据静默缺失
        self.raise_if_failed_folders()

    def handle_folder(self, fid: str, fname: str):
        self.log(f'【收藏夹: {fname}, fid: {fid}】开始获取数据')

        # 第 0 次是首次尝试，之后每次都是重试；总共 1 + max_retry 次
        for attempt in range(self.max_retry + 1):
            try:
                # 获取收藏夹数据
                page_data = self.fetch_folder_page_data(fid)

                # 序列化到文件
                filepath = self.save_folder_page_data_to_file(page_data, fid, fname)
            except Exception as e:
                # 单个收藏夹失败不应该中断其他收藏夹，
                # 但也不能无声无息地丢掉这份数据，这里记录并在结束后统一汇报
                self.log(f'【收藏夹: {fname}, fid: {fid}】第 {attempt + 1}/{self.max_retry + 1} 次获取失败: [{e}]')

                if attempt >= self.max_retry:
                    self.failed_folders.append((fid, fname, e))
                    return

                self.retry_backoff(attempt + 1)
                continue

            if filepath is None:
                self.log(f'【收藏夹: {fname}, fid: {fid}】收藏夹无数据')
                return

            self.log(f'【收藏夹: {fname}, fid: {fid}】保存文件成功 → [{filepath}]')
            self.files.append(filepath)
            return

    # noinspection PyMethodMayBeStatic
    def retry_backoff(self, attempt: int):
        """
        重试前的等待，避免短时间内反复请求加剧服务端限流。

        :param attempt: 当前是第几次尝试（从 1 开始）
        """
        import time

        # attempt 从 1 开始，首次重试等 2s，之后 4s、8s，上限 10s
        time.sleep(min(2 ** attempt, 10))

    def raise_if_failed_folders(self):
        """
        导出结束后统一检查失败的收藏夹。

        收藏夹数据量大、耗时长时，登录态可能在服务端被提前过期，
        导致个别收藏夹抓取失败；这类失败此前会被静默吞掉，导出的结果看起来
        是成功的、实际却缺了数据。这里抛出运行时异常，交由 option 的 safe
        策略决定记录后继续或向外抛出，不走参数校验的 valid 策略。
        """
        if not self.failed_folders:
            return

        detail = '、'.join(f'【{fname}】(fid={fid})' for fid, fname, _ in self.failed_folders)
        msg = (f'以下 {len(self.failed_folders)} 个收藏夹导出失败（已重试 {self.max_retry} 次）: {detail}。'
               f'可稍后重新执行导出以补全这部分数据。')
        self.log(msg)
        ExceptionTool.raises(msg)

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

    def zip_with_password(self, files, zip_path):
        """
        用 7z 打包指定文件并加密。

        只打包传入的 files，不打包整个 save_dir：否则会连上一轮遗留的旧导出、
        以及失败收藏夹写了一半的 csv 一起塞进包里，而这些文件并不在
        execute_deletion 的删除范围内，等于往产物里混入无关数据。

        :param files: 要压缩的文件的绝对路径的列表
        :param zip_path: 压缩文件的保存路径
        """
        # 未指定输入文件时，7z 会默认打包整个目录。
        if not files:
            return

        import shlex

        # 在 save_dir 中逐个列举本次成功导出的文件。
        file_args = ' '.join(
            shlex.quote(of_file_name(f)) for f in files
        )

        cmd_list = f'''
        cd {self.save_dir}
        7z a "{zip_path}" {file_args} -p{self.zip_password} -mhe=on > "../7z_output.txt"
        
        '''
        self.log(f'运行命令: {cmd_list}')

        # 执行
        self.execute_multi_line_cmd(cmd_list)


class Img2pdfPlugin(JmOptionPlugin):
    plugin_key = 'img2pdf'
    # img2pdf 总是需要；pikepdf 仅在加密 pdf 时需要
    plugin_dependencies = ('img2pdf',)

    @classmethod
    def required_dependencies_for(cls, kwargs: dict) -> tuple:
        encrypt = cls.check_encrypt_param(kwargs.get('encrypt'))
        if encrypt is None:
            return cls.plugin_dependencies
        return cls.plugin_dependencies + cls.encrypt_dependencies(encrypt)

    @classmethod
    def encrypt_dependencies(cls, encrypt: dict) -> tuple:
        return ('pikepdf',)

    def invoke(self,
               photo: JmPhotoDetail = None,
               album: JmAlbumDetail = None,
               downloader=None,
               pdf_dir=None,
               filename_rule=None,
               dir_rule=None,
               delete_original_file=False,
               encrypt=None,
               **kwargs,
               ):
        if photo is None and album is None:
            jm_log('wrong_usage', 'img2pdf必须运行在after_photo或after_album时')

        if filename_rule is None:
            filename_rule = self.default_export_filename_rule(album is not None)

        try:
            import img2pdf
        except ImportError:
            self.warning_lib_not_install('img2pdf')
            return

        self.downloader = downloader
        self.delete_original_file = delete_original_file

        # 处理生成的pdf文件的路径
        pdf_filepath = self.decide_filepath(album, photo, filename_rule, 'pdf', pdf_dir, dir_rule)

        # 配置了加密时，在生成 pdf 之前确认加密依赖与密码，避免写出 pdf 后才失败而留下未加密文件
        password, _ = self.decide_password(encrypt, pdf_filepath)

        # 调用 img2pdf 把目标图片转为 pdf
        result = self.write_img_2_pdf(pdf_filepath, album, photo, password)
        if not result:
            return
        img_path_ls, img_dir_ls = result

        # noinspection PyTypeChecker
        detail: DetailEntity = album or photo
        if downloader is not None:
            downloader.record_export_filepath(detail, pdf_filepath)

        # 打印结果
        self.log(f'{detail.alias_cn()}合并PDF成功！'
                 f'[{detail}] → [{pdf_filepath}]', 'finish')

        # 执行删除
        img_path_ls += sorted(img_dir_ls, key=lambda d: len(os.path.abspath(d)), reverse=True)
        self.execute_deletion(img_path_ls)

    def write_img_2_pdf(self, pdf_filepath, album: JmAlbumDetail, photo: JmPhotoDetail, password):
        import img2pdf

        img_path_ls, img_dir_ls, raw_dirs = self.collect_export_images(album, photo)
        if len(img_path_ls) == 0:
            self.log(f'所有文件夹都不存在图片，无法生成pdf：{raw_dirs}', 'error')
            return

        try:
            pdf_bytes = img2pdf.convert(img_path_ls)
            valid_img_paths = img_path_ls
        except Exception:
            valid_img_paths = []
            for p in img_path_ls:
                try:
                    img2pdf.convert([p])
                    valid_img_paths.append(p)
                except Exception as item_err:
                    self.log(f'Failed to convert image {p}: {item_err}', 'error')
            if not valid_img_paths:
                return
            pdf_bytes = img2pdf.convert(valid_img_paths)

        with open(pdf_filepath, 'wb') as f:
            f.write(pdf_bytes)

        if password is not None:
            self.encrypt_pdf(pdf_filepath, password)

        return valid_img_paths, img_dir_ls

    def encrypt_pdf(self, pdf_filepath: str, password: str):
        import pikepdf

        with pikepdf.open(pdf_filepath, allow_overwriting_input=True) as pdf:
            pdf.save(pdf_filepath, encryption=pikepdf.Encryption(user=password, owner=password))


class LongImgPlugin(JmOptionPlugin):
    plugin_key = 'long_img'

    def invoke(self,
               photo: JmPhotoDetail = None,
               album: JmAlbumDetail = None,
               downloader=None,
               img_dir=None,
               filename_rule=None,
               delete_original_file=False,
               dir_rule=None,
               **kwargs,
               ):
        if photo is None and album is None:
            jm_log('wrong_usage', 'long_img必须运行在after_photo或after_album时')

        if filename_rule is None:
            filename_rule = self.default_export_filename_rule(album is not None)

        try:
            from PIL import Image
        except ImportError:
            self.warning_lib_not_install('PIL')
            return

        self.downloader = downloader
        self.delete_original_file = delete_original_file

        # 处理生成的长图文件的路径
        long_img_path = self.decide_filepath(album, photo, filename_rule, 'png', img_dir, dir_rule)

        # 调用 PIL 把目标图片合并为长图
        img_path_ls = self.write_img_2_long_img(long_img_path, album, photo)
        if not img_path_ls:
            return
        # noinspection PyTypeChecker
        detail: DetailEntity = album or photo
        if downloader is not None:
            downloader.record_export_filepath(detail, long_img_path)

        # 打印结果
        self.log(f'{detail.alias_cn()}合并长图成功！'
                 f'[{detail}] → [{long_img_path}]', 'finish')

        # 执行删除
        self.execute_deletion(img_path_ls)

    def write_img_2_long_img(self, long_img_path, album: JmAlbumDetail, photo: JmPhotoDetail) -> Optional[List[str]]:
        from PIL import Image

        img_paths, img_dir_ls, raw_dirs = self.collect_export_images(album, photo)
        if not img_paths:
            self.log(f'所有文件夹都不存在图片，无法生成long_img：{raw_dirs}', 'error')
            return

        images, valid_img_paths = self.open_images_with_paths(img_paths)
        if not images:
            return

        resample_method = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS')
        try:
            min_img_width = min(img.width for img in images)
            total_height = 0
            for i, img in enumerate(images):
                if img.width > min_img_width:
                    resized = img.resize((min_img_width, int(img.height * min_img_width / img.width)),
                                         resample=resample_method)
                    img.close()
                    images[i] = resized
                total_height += images[i].height

            long_img = Image.new('RGB', (min_img_width, total_height))
            y_offset = 0
            for img in images:
                long_img.paste(img, (0, y_offset))
                y_offset += img.height

            long_img.save(long_img_path)
        finally:
            for img in images:
                img.close()

        sorted_dirs = sorted(img_dir_ls, key=lambda d: len(os.path.abspath(d)), reverse=True)
        return valid_img_paths + sorted_dirs

    def open_images_with_paths(self, img_paths: List[str]) -> Tuple[List[Any], List[str]]:
        from PIL import Image

        images = []
        valid_paths = []
        for img_path in img_paths:
            try:
                img = Image.open(img_path)
                images.append(img)
                valid_paths.append(img_path)
            except Exception as e:
                self.log(f"Failed to open image {img_path}: {e}", 'error')
        return images, valid_paths

    def open_images(self, img_paths: List[str]):
        images, _ = self.open_images_with_paths(img_paths)
        return images


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

        if self.running:
            return

        with self.run_server_lock:
            if self.running:
                return

            # 服务器的代码位于独立库 jm-view-server，需要独立安装
            # 源代码仓库：https://github.com/hect0x7/jm-view-server
            try:
                # noinspection PyUnresolvedReferences
                import jm_view_server as jm_server_lib
            except ModuleNotFoundError as e:
                if e.name != 'jm_view_server':
                    raise

                try:
                    # 兼容尚未迁移的 plugin_jm_server <= 0.2.3
                    # noinspection PyUnresolvedReferences
                    import plugin_jm_server as jm_server_lib
                except ModuleNotFoundError as legacy_error:
                    if legacy_error.name != 'plugin_jm_server':
                        raise
                    self.warning_lib_not_install('jm-view-server')
                    return

                self.log('检测到旧包 plugin_jm_server，建议升级到 jm-view-server', 'warning')

            self.log(f'当前使用 jm-view-server 版本: {jm_server_lib.__version__}')

            # 核心函数，启动服务器，会阻塞当前线程
            def blocking_run_server():
                self.server_thread = current_thread()
                self.enter_wait_list()
                server = jm_server_lib.JmServer(base_dir, password, **kwargs)
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
                atexit.register(self.wait_server_stop)
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

            if not has_update:
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


class AdvancedRetryPlugin(JmOptionPlugin):
    plugin_key = 'advanced_retry'

    def invoke(self, **kwargs):
        self.log(
            '客户端现已内置域名轮询与失败后置重试机制，不再需要配置 advanced_retry 插件，你可以直接删除该配置',
            'deprecated',
        )


class DownloadCoverPlugin(JmOptionPlugin):
    plugin_key = 'download_cover'

    def invoke(self,
               dir_rule: dict,
               size='',
               photo: JmPhotoDetail = None,
               album: JmAlbumDetail = None,
               downloader=None,
               **kwargs) -> None:
        album_id = album.id if album else photo.album_id
        save_path = self.decide_filepath(
            album, photo,
            None, None, None,
            dir_rule
        )
        if self.option.download.cache and os.path.exists(save_path):
            self.log(f'album-{album_id}的封面已存在，跳过下载: [{save_path}]', 'skip')
            return
        downloader.client.download_album_cover(album_id, save_path, size)

    async def async_invoke(self,
                           dir_rule: dict,
                           size='',
                           photo: JmPhotoDetail = None,
                           album: JmAlbumDetail = None,
                           downloader=None,
                           **kwargs) -> None:
        album_id = album.id if album else photo.album_id
        save_path = self.decide_filepath(
            album, photo,
            None, None, None,
            dir_rule
        )
        if self.option.download.cache and os.path.exists(save_path):
            self.log(f'album-{album_id}的封面已存在，跳过下载: [{save_path}]', 'skip')
            return
        decode_executor = downloader.get_decode_executor() if isinstance(downloader, JmAsyncDownloader) else None
        await downloader.client.download_album_cover(album_id, save_path, size, decode_executor=decode_executor)


class CalibreMetadataPlugin(JmOptionPlugin):
    """
    功能：为本子生成 Calibre 可识别的元数据文件 metadata.opf。

    通常挂在 after_album 上，每个本子在其目录下生成一份 metadata.opf，
    Calibre 导入（从 OPF 读元数据）时可以自动带上书名、作者、标签、简介和封面。

    OPF 的生成逻辑由 jmcomic-calibre 提供，
    避免同一份 XML 拼接逻辑在两处各维护一份。

    配置示例：

    ```yml
    plugins:
      after_album:
        - plugin: calibre_metadata
          kwargs:
            dir_rule:
              rule: "Bd / Aid / metadata.opf"
              base_dir: "./"
            include_cover: true
            fields: # 追加静态字段
              language: "zh"
    ```

    说明：
    - identifier 固定写为 jmcomic:{album_id}，可在 Calibre 中反查回禁漫的 album_id
    - fields 中的 title/author 可覆盖默认取值，其余键值对须为 Dublin Core 元素名（如 language/publisher/date），按 dc:{key} 写入，不支持的键会忽略并告警
    - include_cover 依赖 downloader（after_album 阶段自动传入）
    """
    plugin_key = 'calibre_metadata'
    plugin_dependencies = (('jmcomic_calibre', 'jmcomic-calibre'),)

    def invoke(self,
               dir_rule: dict,
               album: JmAlbumDetail = None,
               photo: JmPhotoDetail = None,
               downloader=None,
               include_cover=False,
               fields=None,
               **kwargs) -> None:
        prepared = self._prepare_opf_export(dir_rule, album, photo)
        if prepared is None:
            return
        jmcomic_calibre, opf_path = prepared

        # 处理封面下载
        if include_cover:
            cover_path = self._decide_cover_path(opf_path)
            self.download_cover_if_needed(album.id, cover_path, downloader)

        self._export_opf(jmcomic_calibre, album, opf_path, fields, include_cover)

    async def async_invoke(self,
                           dir_rule: dict,
                           album: JmAlbumDetail = None,
                           photo: JmPhotoDetail = None,
                           downloader=None,
                           include_cover=False,
                           fields=None,
                           **kwargs) -> None:
        prepared = self._prepare_opf_export(dir_rule, album, photo)
        if prepared is None:
            return
        jmcomic_calibre, opf_path = prepared

        # 处理封面下载
        if include_cover:
            cover_path = self._decide_cover_path(opf_path)
            await self.download_cover_if_needed_async(album.id, cover_path, downloader)

        import asyncio
        await asyncio.to_thread(
            self._export_opf,
            jmcomic_calibre,
            album,
            opf_path,
            fields,
            include_cover,
        )

    def _prepare_opf_export(self, dir_rule: dict, album: JmAlbumDetail, photo: JmPhotoDetail):
        self.require_param(album, '本插件需在after_album阶段使用，需要album参数')

        try:
            import jmcomic_calibre
        except ImportError:
            self.warning_lib_not_install('jmcomic-calibre')
            return None

        opf_path = self.decide_filepath(album, photo, None, None, None, dir_rule)
        return jmcomic_calibre, opf_path

    @staticmethod
    def _decide_cover_path(opf_path: str) -> str:
        return os.path.join(os.path.dirname(opf_path), 'cover.jpg')

    def _prepare_cover_download(self, album_id: str, cover_path: str, downloader) -> bool:
        if self.option.download.cache and os.path.exists(cover_path):
            self.log(f'album-{album_id}的封面已存在，跳过下载: [{cover_path}]', 'skip')
            return False
        self.require_param(downloader, 'include_cover=true时需要downloader参数（after_album阶段会自动传入）')
        return True

    def download_cover_if_needed(self, album_id: str, cover_path: str, downloader):
        if not self._prepare_cover_download(album_id, cover_path, downloader):
            return
        downloader.client.download_album_cover(album_id, cover_path, '')

    async def download_cover_if_needed_async(self, album_id: str, cover_path: str, downloader):
        if not self._prepare_cover_download(album_id, cover_path, downloader):
            return
        decode_executor = downloader.get_decode_executor() if isinstance(downloader, JmAsyncDownloader) else None
        await downloader.client.download_album_cover(album_id, cover_path, '', decode_executor=decode_executor)

    def _export_opf(self, jmcomic_calibre, album: JmAlbumDetail, opf_path: str, fields, include_cover: bool):
        jmcomic_calibre.export_opf(
            album=album,
            opf_path=opf_path,
            fields=fields,
            include_cover=include_cover,
            on_ignored=lambda key, allowed: self.log(
                f'calibre_metadata: 忽略不支持的fields字段 [{key}]，'
                f'仅支持Dublin Core元素: {", ".join(sorted(allowed))}', 'warning'),
        )
        self.log(f'已生成Calibre元数据文件 → [{opf_path}]')
