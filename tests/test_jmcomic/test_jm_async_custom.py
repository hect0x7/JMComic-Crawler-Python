"""
Async 自定义 Client 注册对称性测试 —— 对标 test_jm_custom.py

验证 REGISTRY_ASYNC_CLIENT 注册、域名回退、异常行为与 sync 一致。
"""
from test_jmcomic import *
from jmcomic.jm_async_client import AsyncJmApiClient
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
            # 域名应回退到默认 API 域名列表（与 sync 行为一致）
            expected = JmModuleConfig.DOMAIN_API_UPDATED_LIST or JmModuleConfig.DOMAIN_API_LIST
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
            # 应回退到 DOMAIN_API_UPDATED_LIST 或 DOMAIN_API_LIST（与 sync 行为一致）
            expected = JmModuleConfig.DOMAIN_API_UPDATED_LIST or JmModuleConfig.DOMAIN_API_LIST
            self.assertListEqual(client.get_domain_list(), list(expected))
        finally:
            if client is not None:
                loop.run_until_complete(client.close())
            loop.close()
