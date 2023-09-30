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
    project_dir: str = None

    def setUp(self) -> None:
        print_eye_catching(f' [{self._testMethodName}] '.center(40, '🚀'))

    def tearDown(self) -> None:
        print_eye_catching(f' [{self._testMethodName}] '.center(40, '✅'))

    @classmethod
    def setUpClass(cls):
        # 获取项目根目录
        cls.project_dir = os.path.abspath(os.path.dirname(__file__) + '/../..')
        os.chdir(cls.project_dir)

        # 设置 JmOption，JmcomicClient
        try:
            option = create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            option = create_option('./assets/config/option_test.yml')

        cls.option = option
        cls.client = option.build_jm_client()

        # 跨平台设置
        cls.adapt_os()

    @classmethod
    def use_option(cls, op_filename: str) -> JmOption:
        return create_option(f'./assets/config/{op_filename}')

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
        pass

    @classmethod
    def adapt_linux(cls):
        pass

    @classmethod
    def adapt_macos(cls):
        pass
