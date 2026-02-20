import platform
import unittest

# noinspection PyUnresolvedReferences
import jmcomic
from jmcomic import *

# 设置编码为 utf-8，使用 reconfigure() 而非替换 sys.stdout 对象
# 直接替换会破坏 pytest 的 I/O 捕获机制，导致 "I/O operation on closed file" 错误
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
# 获取项目根目录
project_dir = os.path.abspath(os.path.dirname(__file__) + '/../..')
os.chdir(project_dir)


def ts():
    return time_stamp(False)


skip_time_cost_log = file_exists('./.idea')

cost_time_dict = {}


class JmTestConfigurable(unittest.TestCase):
    option: JmOption = None
    client: JmcomicClient = None
    project_dir: str = project_dir

    def setUp(self) -> None:
        if skip_time_cost_log:
            return
        method_name = self._testMethodName
        cost_time_dict[method_name] = ts()
        print_eye_catching(f' [{format_ts()} | {method_name}] '.center(70, '🚀'))

    def tearDown(self) -> None:
        if skip_time_cost_log:
            return
        method_name = self._testMethodName
        begin = cost_time_dict[method_name]
        end = ts()
        print_eye_catching(f' [cost {end - begin:.02f}s | {self._testMethodName}] '.center(70, '✅'))

    @classmethod
    def setUpClass(cls):
        # 设置 JmOption，JmcomicClient
        option = cls.new_option()
        cls.option = option
        # 设置缓存级别为option，可以减少请求次数
        cls.client = option.build_jm_client(cache='level_option')

        # 跨平台设置
        cls.adapt_os()

        if skip_time_cost_log:
            return
        cost_time_dict[cls.__name__] = ts()

    @classmethod
    def new_option(cls):
        try:
            return create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            return create_option('./assets/option/option_test.yml')

    @classmethod
    def tearDownClass(cls) -> None:
        if skip_time_cost_log:
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
