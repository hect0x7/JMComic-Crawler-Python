import unittest

# noinspection PyUnresolvedReferences
import jmcomic
from jmcomic import *


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

        # 更新
        cls.try_update_jm_cookies()

    @staticmethod
    def use_option(op_filename: str) -> JmOption:
        return create_option(workspace(f"/config/{op_filename}"))

    @staticmethod
    def move_workspace(new_dir: str):
        set_application_workspace(workspace(f"/{new_dir}/", is_dir=True))

    @classmethod
    def try_update_jm_cookies(cls):
        import platform
        if platform.system() != 'Windows':
            return

        # 尝试更新 cookies
        cookies = ChromePluginCookieParser({'remember', 'comic'}) \
            .apply(when_valid_message="更新jmcomic-option成功！！！！")
        if cookies is not None:
            cls.option.client_config['meta_data']['cookies'] = cookies
            cls.option.save_to_file()
