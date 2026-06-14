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


class JmAsyncTestConfigurable(JmTestConfigurable):
    """
    异步测试基类。

    设计：
    - 同时持有 sync API client 和 async API client，便于 sync/async diff
    - sync_api_client：sync 版 JmApiClient（用于 diff 对照，与 async 使用同一后端）
    - async_client：AsyncJmApiClient（被测对象）
    - 提供 run_async() / assert_sync_async_* 系列辅助方法
    """
    import asyncio as _asyncio

    sync_api_client = None
    async_client = None
    _loop = None

    @classmethod
    def new_option(cls):
        opt = super().new_option()
        # 强制使用 api impl，避免 HTML 端的 403 封控
        opt.client.src_dict['impl'] = 'api'
        return opt

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._loop = cls._asyncio.new_event_loop()
        cls._asyncio.set_event_loop(cls._loop)

        # 创建 sync API client（用于 diff 对照，与 async 使用同一后端）
        cls.sync_api_client = cls.option.new_jm_client(cache='level_option', impl='api')

        # 创建 async client 并就绪
        async def _create_async_client():
            client = cls.option.new_jm_async_client()
            await client.setup()
            # 为 async client 开启缓存（对齐 sync 的 cache='level_option'）
            client.set_cache_dict({})
            return client
            
        cls.async_client = cls._loop.run_until_complete(_create_async_client())

    @classmethod
    def tearDownClass(cls):
        if cls.async_client:
            cls._loop.run_until_complete(cls.async_client.close())
            cls.async_client = None
        if cls._loop:
            cls._asyncio.set_event_loop(None)
            cls._loop.close()
            cls._loop = None
        super().tearDownClass()

    def run_async(self, coro):
        """在类级 event loop 中运行协程"""
        return self._loop.run_until_complete(coro)

    # ===== sync/async diff 断言辅助 =====

    def assert_sync_async_equal(self, sync_val, async_val, field_name):
        """断言 sync 和 async 值一致，失败时报告差异"""
        self.assertEqual(
            sync_val, async_val,
            f'sync/async 行为偏差 [{field_name}]:\n'
            f'  sync  = {repr(sync_val)}\n'
            f'  async = {repr(async_val)}'
        )

    def assert_album_equal(self, sync_album, async_album):
        """断言两个 JmAlbumDetail 在关键字段上一致"""
        for attr in ['album_id', 'name', 'page_count', 'comment_count']:
            self.assert_sync_async_equal(
                getattr(sync_album, attr),
                getattr(async_album, attr),
                f'album.{attr}',
            )
        # 章节 ID 列表一致
        sync_pids = [p.photo_id for p in sync_album]
        async_pids = [p.photo_id for p in async_album]
        self.assert_sync_async_equal(sync_pids, async_pids, 'album.episode_photo_ids')

    def assert_photo_equal(self, sync_photo, async_photo):
        """断言两个 JmPhotoDetail 在关键字段上一致"""
        for attr in ['photo_id', 'name', 'album_id', 'sort']:
            self.assert_sync_async_equal(
                getattr(sync_photo, attr),
                getattr(async_photo, attr),
                f'photo.{attr}',
            )

    def assert_search_page_equal(self, sync_page, async_page, check_total=True):
        """断言两个搜索结果页在结构上一致"""
        if check_total:
            self.assert_sync_async_equal(sync_page.total, async_page.total, 'page.total')
        # 比较前 5 条结果的 album_id
        sync_ids = [aid for aid, _ in sync_page[:min(5, len(sync_page))]]
        async_ids = [aid for aid, _ in async_page[:min(5, len(async_page))]]
        self.assert_sync_async_equal(sync_ids, async_ids, 'page.top5_ids')
