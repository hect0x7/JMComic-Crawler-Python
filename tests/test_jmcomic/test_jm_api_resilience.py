import asyncio
import threading
import unittest
from types import SimpleNamespace

from jmcomic.jm_async_client import AsyncJmApiClient
from jmcomic.jm_client_impl import JmApiClient
from jmcomic.jm_config import JmMagicConstants, JmModuleConfig
from jmcomic.jm_entity import JmPhotoDetail


def _fake_api_resp(url: str, data: dict):
    return SimpleNamespace(
        url=url,
        encoded_data='dummy',
        res_data=data,
    )


class TestApiResilience(unittest.TestCase):

    def test_fix_tokenparam_refreshes_when_app_version_changes(self):
        orig_ver = JmMagicConstants.APP_VERSION
        cache_attr = '__cache_get_fix_ts_token_tokenparam__'
        orig_cache = getattr(JmModuleConfig, cache_attr, None)
        try:
            if hasattr(JmModuleConfig, cache_attr):
                delattr(JmModuleConfig, cache_attr)

            JmMagicConstants.APP_VERSION = '2.1.13'
            first = JmModuleConfig.get_fix_ts_token_tokenparam()
            second = JmModuleConfig.get_fix_ts_token_tokenparam()
            self.assertEqual(first, second)
            self.assertTrue(first[2].endswith(',2.1.13'))

            JmMagicConstants.APP_VERSION = '2.1.14'
            refreshed = JmModuleConfig.get_fix_ts_token_tokenparam()
            self.assertTrue(refreshed[2].endswith(',2.1.14'))
            self.assertEqual(refreshed, JmModuleConfig.get_fix_ts_token_tokenparam())
        finally:
            JmMagicConstants.APP_VERSION = orig_ver
            if orig_cache is None:
                if hasattr(JmModuleConfig, cache_attr):
                    delattr(JmModuleConfig, cache_attr)
            else:
                setattr(JmModuleConfig, cache_attr, orig_cache)

    def test_sync_chapter_empty_images_switches_domain_and_recovers(self):
        client = object.__new__(JmApiClient)
        client.domain_list = ['bad.example', 'good.example']
        client._domain_fail_lock = threading.Lock()
        client._domain_fail_count = {}
        client._image_domain_fail_count = {}

        called_domains = []

        def fake_req_api(url, **kwargs):
            domain = client._pick_domain(client.domain_list, False)
            called_domains.append(domain)
            if domain == 'bad.example':
                return _fake_api_resp(
                    f'https://{domain}{url}',
                    {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
                )
            return _fake_api_resp(
                f'https://{domain}{url}',
                {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': ['00001.webp', '00002.webp']},
            )

        client.req_api = fake_req_api
        photo = client.fetch_detail_entity('438516', JmPhotoDetail)
        self.assertEqual(['bad.example', 'good.example'], called_domains)
        self.assertEqual(['00001.webp', '00002.webp'], photo.page_arr)
        self.assertEqual(1, client._domain_fail_count.get('bad.example', 0))

    def test_sync_chapter_all_empty_images_returns_gracefully(self):
        client = object.__new__(JmApiClient)
        client.domain_list = ['d1.example', 'd2.example']
        client._domain_fail_lock = threading.Lock()
        client._domain_fail_count = {}
        client._image_domain_fail_count = {}

        called_domains = []

        def fake_req_api(url, **kwargs):
            domain = client._pick_domain(client.domain_list, False)
            called_domains.append(domain)
            return _fake_api_resp(
                f'https://{domain}{url}',
                {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
            )

        client.req_api = fake_req_api
        photo = client.fetch_detail_entity('438516', JmPhotoDetail)
        self.assertEqual(['d1.example', 'd2.example'], called_domains)
        self.assertEqual([], photo.page_arr)

    def test_async_chapter_empty_images_switches_domain_and_recovers(self):
        client = object.__new__(AsyncJmApiClient)
        client._domain_list = ['bad.example', 'good.example']
        client._domain_fail_count = {}
        client._cache = None

        called_domains = []

        async def fake_req_api(url, params=None, **kwargs):
            domain = min(client._domain_list, key=lambda d: client._domain_fail_count.get(d, 0))
            called_domains.append(domain)
            if domain == 'bad.example':
                return _fake_api_resp(
                    f'https://{domain}{url}?id=438516',
                    {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
                )
            return _fake_api_resp(
                f'https://{domain}{url}?id=438516',
                {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': ['00001.webp']},
            )

        client.req_api = fake_req_api
        photo = asyncio.run(client.fetch_detail_entity('438516', JmPhotoDetail))
        self.assertEqual(['bad.example', 'good.example'], called_domains)
        self.assertEqual(['00001.webp'], photo.page_arr)
        self.assertEqual(1, client._domain_fail_count.get('bad.example', 0))


if __name__ == '__main__':
    unittest.main()
