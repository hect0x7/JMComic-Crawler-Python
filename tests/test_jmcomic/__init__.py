import io
import platform
import unittest

# noinspection PyUnresolvedReferences
import jmcomic
from jmcomic import *

# set encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, 'utf-8')
# 获取项目根目录
project_dir = os.path.abspath(os.path.dirname(__file__) + '/../..')
os.chdir(project_dir)


def ts():
    return time_stamp(False)


skip_time_cost_debug = file_exists('./.idea')

cost_time_dict = {}


class JmTestConfigurable(unittest.TestCase):
    option: JmOption = None
    client: JmcomicClient = None
    project_dir: str = project_dir

    def setUp(self) -> None:
        if skip_time_cost_debug:
            return
        method_name = self._testMethodName
        cost_time_dict[method_name] = ts()
        print_eye_catching(f' [{format_ts()} | {method_name}] '.center(70, '🚀'))

    def tearDown(self) -> None:
        if skip_time_cost_debug:
            return
        method_name = self._testMethodName
        begin = cost_time_dict[method_name]
        end = ts()
        print_eye_catching(f' [cost {end - begin:.02f}s | {self._testMethodName}] '.center(70, '✅'))

    @classmethod
    def setUpClass(cls):
        # 设置 JmOption，JmcomicClient
        try:
            option = create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            option = create_option('./assets/option/option_test.yml')

        cls.option = option
        cls.client = option.build_jm_client()

        # 跨平台设置
        cls.adapt_os()

        if skip_time_cost_debug:
            return
        cost_time_dict[cls.__name__] = ts()

    @classmethod
    def tearDownClass(cls) -> None:
        if skip_time_cost_debug:
            return
        begin = cost_time_dict[cls.__name__]
        end = ts()
        print_eye_catching(f' [total cost {end - begin:.02f}s | {cls.__name__}] '.center(60, '-'))

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
