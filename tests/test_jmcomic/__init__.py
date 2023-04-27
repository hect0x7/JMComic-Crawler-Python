import sys
import io
import platform
import unittest

# noinspection PyUnresolvedReferences
import jmcomic
from jmcomic import *

# set encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, 'utf-8')


class JmTestConfigurable(unittest.TestCase):
    option: JmOption = None
    client: JmcomicClient = None

    def setUp(self) -> None:
        print_sep('>')

    def tearDown(self) -> None:
        print_sep('<')

    @classmethod
    def setUpClass(cls):
        # 获取项目根目录
        application_workspace = os.path.abspath(os.path.dirname(__file__) + '/../..')

        # 设置 workspace → assets/
        set_application_workspace(f'{application_workspace}/assets/')
        # 设置 实体类的save_dir → assets/download
        WorkEntity.detail_save_base_dir = workspace("/download/", is_dir=True)

        # 设置 JmOption，JmcomicClient
        option = cls.use_option('option_test.yml')
        cls.option = option
        cls.client = option.build_jm_client()

        # 启用 JmClientClient 缓存
        cls.enable_client_cache()

        # 跨平台设置
        cls.adapt_os()

    @staticmethod
    def use_option(op_filename: str) -> JmOption:
        return create_option(workspace(f"/config/{op_filename}"))

    @staticmethod
    def move_workspace(new_dir: str):
        set_application_workspace(workspace(f"/{new_dir}/", is_dir=True))

    @classmethod
    def adapt_os(cls):
        adapt_func_dict = {
            'Windows': cls.adapt_win,
            'Darwin': cls.adapt_macos,
            'Linux': cls.adapt_linux,
        }

        adapt_func_dict.get(platform.system(), lambda *args, **kwargs: None)()

    @classmethod
    def adapt_win(cls):
        # 尝试更新 cookies
        cookies = ChromePluginCookieParser({'remember', 'comic'}) \
            .apply(when_valid_message="更新jmcomic-option成功！！！！")
        if cookies is not None:
            cls.option.client_config['meta_data']['cookies'] = cookies
            cls.option.save_to_file()

    @classmethod
    def adapt_linux(cls):
        pass

    @classmethod
    def adapt_macos(cls):
        cls.client.domain = JmModuleConfig.domain(cls.client)

    @classmethod
    def enable_client_cache(cls):
        cls.client.enable_cache()
