"""
Async 自定义 Client 注册对称性测试 —— 对标 test_jm_custom.py

验证 REGISTRY_ASYNC_CLIENT 注册、域名回退、异常行为与 sync 一致。
"""
from test_jmcomic import *
from jmcomic.jm_async_client import AsyncJmApiClient
from jmcomic.jm_async_downloader import JmAsyncDownloader
from jmcomic.jm_client_interface import AsyncJmcomicClient
import asyncio


class Test_Async_Custom(JmAsyncTestConfigurable):
    """异步自定义 client 注册对称性测试"""

    def test_async_extends_api_client(self):
        """对标 test_extends_api_client：自定义 async client 注册到 REGISTRY_ASYNC_CLIENT"""

        class MyAsyncClient(AsyncJmApiClient):
            client_key = 'my_async_test'

        JmModuleConfig.register_async_client(MyAsyncClient)

        # 通过 option 创建自定义 client
        opt = self.new_option()
        opt.client.src_dict['async_impl'] = 'my_async_test'
        loop = asyncio.new_event_loop()
        client = None
        try:
            client = opt.new_jm_async_client()
            self.assertIsInstance(client, MyAsyncClient)
            # setup 前应回退到默认 API 域名列表（与 sync 构造行为一致）
            expected = JmModuleConfig.DOMAIN_API_LIST
            self.assertListEqual(client.get_domain_list(), list(expected))
        finally:
            if client is not None:
                loop.run_until_complete(client.close())
            loop.close()

    def test_async_client_key_missing(self):
        """对标 test_client_key_missing：注册时无 client_key → 异常"""

        class BadAsyncClient(AsyncJmcomicClient):
            pass

        self.assertRaises(
            JmcomicException,
            JmModuleConfig.register_async_client,
            BadAsyncClient,
        )

    def test_async_custom_client_empty_domain(self):
        """对标 test_custom_client_empty_domain：自定义 client 空域名 → 异常"""

        class MinimalAsyncClient(AsyncJmcomicClient):
            client_key = 'minimal_async_test'

            def __init__(self, option, **kwargs):
                self._domain_list = []

            def get_domain_list(self):
                return self._domain_list

            def set_domain_list(self, domain_list):
                self._domain_list = domain_list

            def set_cache_dict(self, cache_dict):
                pass

            def get_cache_dict(self):
                return None

            async def setup(self):
                pass

            async def close(self):
                pass

        JmModuleConfig.register_async_client(MinimalAsyncClient)

        opt = self.new_option()
        opt.client.src_dict['async_impl'] = 'minimal_async_test'
        loop = asyncio.new_event_loop()
        client = None
        try:
            client = opt.new_jm_async_client()
            # 域名列表应为空
            self.assertEqual(len(client.get_domain_list()), 0)
        finally:
            if client is not None:
                loop.run_until_complete(client.close())
            loop.close()

    def test_async_client_empty_domain_fallback(self):
        """对标 test_client_empty_domain：继承 AsyncJmApiClient 空域名时的回退"""

        class MyAsyncFallback(AsyncJmApiClient):
            client_key = 'async_fallback_test'

        JmModuleConfig.register_async_client(MyAsyncFallback)

        opt = self.new_option()
        opt.client.src_dict['async_impl'] = 'async_fallback_test'
        loop = asyncio.new_event_loop()
        client = None
        try:
            client = opt.new_jm_async_client()
            # setup 前应回退到默认 API 域名列表（与 sync 构造行为一致）
            expected = JmModuleConfig.DOMAIN_API_LIST
            self.assertListEqual(client.get_domain_list(), list(expected))
        finally:
            if client is not None:
                loop.run_until_complete(client.close())
            loop.close()

    def test_async_explicit_domain_list(self):
        """setup 仅替换内置域名，保留显式参数和 Option 自定义域名"""
        old_auto_update = JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN
        old_require_cookies = JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES
        old_updated_domains = JmModuleConfig.DOMAIN_API_UPDATED_LIST
        old_setup_domain = AsyncJmApiClient._has_setup_domain

        expected = ['domain-a.example', 'domain-b.example']
        updated = ['updated-domain.example']
        clients = []
        default_client = None
        loop = asyncio.new_event_loop()
        try:
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = True
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = False
            JmModuleConfig.DOMAIN_API_UPDATED_LIST = updated
            AsyncJmApiClient._has_setup_domain = False

            opt = self.new_option()
            configured_opt = self.new_option()
            configured_opt.client.src_dict['domain'] = {'api': list(expected)}
            default_opt = self.new_option()
            default_opt.client.src_dict['domain'] = {'api': list(JmModuleConfig.DOMAIN_API_LIST)}

            clients = [
                opt.new_jm_async_client(domain_list=expected),
                opt.new_jm_async_client(domain_list=tuple(expected)),
                opt.new_jm_async_client(domain_list='domain-a.example\ndomain-b.example'),
                configured_opt.new_jm_async_client(),
            ]
            default_client = default_opt.new_jm_async_client()

            for client in clients:
                loop.run_until_complete(client.setup())
                self.assertListEqual(client.get_domain_list(), expected)

            loop.run_until_complete(default_client.setup())
            self.assertListEqual(default_client.get_domain_list(), updated)
        finally:
            for client in clients:
                loop.run_until_complete(client.close())
            if default_client is not None:
                loop.run_until_complete(default_client.close())
            loop.close()
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = old_auto_update
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = old_require_cookies
            JmModuleConfig.DOMAIN_API_UPDATED_LIST = old_updated_domains
            AsyncJmApiClient._has_setup_domain = old_setup_domain

        self.assertRaises(
            TypeError,
            opt.new_jm_async_client,
            domain_list=['domain.example', 1],
        )
        self.assertRaises(
            TypeError,
            opt.new_jm_async_client,
            domain_retry_strategy=lambda client: client,
        )

    def test_async_setup_checks_cookies_for_each_session(self):
        """首个 client 自带 Cookie 时，后续 client 仍应独立初始化 Cookie"""
        old_auto_update = JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN
        old_require_cookies = JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES
        old_app_cookies = JmModuleConfig.APP_COOKIES
        old_setup_domain = AsyncJmApiClient._has_setup_domain

        first = None
        second = None
        loop = asyncio.new_event_loop()
        try:
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = False
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = True
            JmModuleConfig.APP_COOKIES = {'cached': 'cookie'}
            AsyncJmApiClient._has_setup_domain = False

            first_option = self.new_option()
            first_option.client.postman.meta_data.src_dict['cookies'] = {'custom': 'cookie'}
            second_option = self.new_option()
            second_option.client.postman.meta_data.src_dict.pop('cookies', None)

            first = first_option.new_jm_async_client()
            second = second_option.new_jm_async_client()
            loop.run_until_complete(first.setup())
            loop.run_until_complete(second.setup())

            self.assertEqual(first._session.cookies.get('custom'), 'cookie')
            self.assertEqual(second._session.cookies.get('cached'), 'cookie')
        finally:
            if first is not None:
                loop.run_until_complete(first.close())
            if second is not None:
                loop.run_until_complete(second.close())
            loop.close()
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = old_auto_update
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = old_require_cookies
            JmModuleConfig.APP_COOKIES = old_app_cookies
            AsyncJmApiClient._has_setup_domain = old_setup_domain

    def test_async_downloader_cleanup_when_setup_fails(self):
        """真实 AsyncSession 初始化失败时，downloader 应回收 client 和线程池"""
        old_auto_update = JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN
        old_require_cookies = JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES
        old_app_cookies = JmModuleConfig.APP_COOKIES
        old_updated_domains = JmModuleConfig.DOMAIN_API_UPDATED_LIST
        old_setup_domain = AsyncJmApiClient._has_setup_domain

        loop = asyncio.new_event_loop()
        downloader = None
        try:
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = False
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = True
            JmModuleConfig.APP_COOKIES = None
            JmModuleConfig.DOMAIN_API_UPDATED_LIST = []
            AsyncJmApiClient._has_setup_domain = False

            option = JmOption.default()
            option.client.src_dict['domain'] = {'api': ['127.0.0.1:1']}
            option.client.src_dict['retry_times'] = 0
            option.client.src_dict['timeout'] = 1
            option.client.postman.meta_data.src_dict['proxies'] = None

            downloader = JmAsyncDownloader(
                option,
                image_concurrency=1,
                photo_concurrency=1,
                decode_worker=1,
            )
            with self.assertRaises(RequestRetryAllFailException):
                loop.run_until_complete(downloader.__aenter__())

            self.assertIsNone(downloader.client)
            self.assertTrue(downloader._decode_pool._shutdown)
        finally:
            if downloader is not None and not downloader._decode_pool._shutdown:
                downloader.shutdown()
            loop.close()
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = old_auto_update
            JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES = old_require_cookies
            JmModuleConfig.APP_COOKIES = old_app_cookies
            JmModuleConfig.DOMAIN_API_UPDATED_LIST = old_updated_domains
            AsyncJmApiClient._has_setup_domain = old_setup_domain
