"""HTML 域名发现仅作用于当前客户端，全局列表只用于显式配置。"""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from jmcomic import AsyncJmHtmlClient, JmModuleConfig, JmOption, JmcomicText


class TestHtmlDomains(unittest.TestCase):
    def test_sync_queries_always_fetch_and_preserve_user_config(self):
        configured = ['configured.example']
        response = SimpleNamespace(status_code=200, text='page', url='https://publish.example')
        postman = SimpleNamespace(get=Mock(return_value=response))
        with patch.object(JmModuleConfig, 'DOMAIN_HTML_LIST', configured), \
                patch.object(JmModuleConfig, 'get_html_url', return_value='https://fresh.example') as redirect, \
                patch.object(JmcomicText, 'analyse_jm_pub_html', return_value=['fresh.example']):
            for _ in range(2):
                self.assertEqual('fresh.example', JmModuleConfig.get_html_domain(postman))
                self.assertEqual(['fresh.example'], JmModuleConfig.get_html_domain_all(postman))
            self.assertEqual(2, redirect.call_count)
            self.assertEqual(2, postman.get.call_count)
            self.assertIs(configured, JmModuleConfig.DOMAIN_HTML_LIST)
            self.assertEqual(['configured.example'], configured)

    def test_sync_client_reuse_and_empty_configuration(self):
        for configured in (None, []):
            with self.subTest(configured=configured), \
                    patch.object(JmModuleConfig, 'DOMAIN_HTML_LIST', configured), \
                    patch.object(JmModuleConfig, 'get_html_domain', return_value='fresh.example') as discover:
                option = JmOption.construct({'client': {'impl': 'html'}})
                client = option.build_jm_client()
                self.assertIs(client, option.build_jm_client())
                self.assertEqual(['fresh.example'], client.get_domain_list())
                self.assertEqual(1, discover.call_count)
                other = option.new_jm_client()
                self.assertIsNot(client, other)
                self.assertEqual(2, discover.call_count)
                self.assertIs(configured, JmModuleConfig.DOMAIN_HTML_LIST)

    def test_configured_domains_skip_discovery(self):
        configured = ['configured.example']
        with patch.object(JmModuleConfig, 'DOMAIN_HTML_LIST', configured), \
                patch.object(JmModuleConfig, 'get_html_domain', side_effect=AssertionError('unexpected discovery')):
            option = JmOption.construct({'client': {'impl': 'html'}})
            sync = option.build_jm_client()
            async_client = option.new_jm_async_client()
            self.assertEqual(configured, sync.get_domain_list())
            self.assertEqual(configured, async_client.get_domain_list())
            sync.get_domain_list().append('local.example')
            self.assertEqual(['configured.example'], configured)

    def test_async_queries_always_fetch_and_preserve_user_config(self):
        async def run():
            configured = ['configured.example']
            with patch.object(JmModuleConfig, 'DOMAIN_HTML_LIST', configured), \
                    patch.object(JmcomicText, 'analyse_jm_pub_html', return_value=['fresh.example']):
                client = AsyncJmHtmlClient(JmOption.default())
                client.get_html_url = AsyncMock(return_value='https://fresh.example')
                response = SimpleNamespace(status_code=200, text='page', url='https://publish.example')
                client._session = SimpleNamespace(get=AsyncMock(return_value=response))
                for _ in range(2):
                    self.assertEqual('fresh.example', await client.get_html_domain())
                    self.assertEqual(['fresh.example'], await client.get_html_domain_all())
                self.assertEqual(2, client.get_html_url.await_count)
                self.assertEqual(2, client._session.get.await_count)
                self.assertIs(configured, JmModuleConfig.DOMAIN_HTML_LIST)
                self.assertEqual(['configured.example'], configured)
        asyncio.run(run())

    def test_async_discovery_is_per_client(self):
        async def run(configured):
            with patch.object(JmModuleConfig, 'DOMAIN_HTML_LIST', configured):
                option = JmOption.construct({'client': {'impl': 'html'}})
                for _ in range(2):
                    client = option.new_jm_async_client()
                    client._ensure_session = AsyncMock()
                    client.get_html_domain = AsyncMock(return_value='fresh.example')
                    await asyncio.gather(client.setup(), client.setup())
                    self.assertEqual(1, client.get_html_domain.await_count)
                    self.assertEqual(['fresh.example'], client.get_domain_list())
                self.assertIs(configured, JmModuleConfig.DOMAIN_HTML_LIST)
        for configured in (None, []):
            with self.subTest(configured=configured):
                asyncio.run(run(configured))
