import asyncio
import base64
import hashlib
import json
import threading
import unittest
from types import SimpleNamespace

from Crypto.Cipher import AES

from jmcomic.jm_async_client import AsyncJmApiClient
from jmcomic.jm_client_impl import JmApiClient
from jmcomic.jm_config import JmMagicConstants, JmModuleConfig
from jmcomic.jm_entity import JmPhotoDetail
from jmcomic.jm_exception import RequestRetryAllFailException


def _encrypt_api_data(payload: dict, ts: int) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    pad = 16 - (len(raw) % 16)
    raw += bytes([pad]) * pad
    key = hashlib.md5(f'{ts}{JmMagicConstants.APP_DATA_SECRET}'.encode('utf-8')).hexdigest().encode('utf-8')
    return base64.b64encode(AES.new(key, AES.MODE_ECB).encrypt(raw)).decode('ascii')


def _fake_http_resp(url: str, payload: dict, ts: int, status_code: int = 200):
    body = json.dumps({'code': 200, 'data': _encrypt_api_data(payload, ts)})
    return SimpleNamespace(
        url=url,
        status_code=status_code,
        text=body,
        content=body.encode('utf-8'),
        request=SimpleNamespace(url=url),
        json=lambda: json.loads(body),
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

    def test_sync_chapter_empty_images_reuses_retry_and_recovers(self):
        called_urls = []

        class FakePostman:
            def get(self, url, **kwargs):
                called_urls.append(url)
                ts = int(kwargs['headers']['tokenparam'].split(',')[0])
                if 'bad.example' in url:
                    return _fake_http_resp(
                        url,
                        {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
                        ts,
                    )
                return _fake_http_resp(
                    url,
                    {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': ['00001.webp', '00002.webp']},
                    ts,
                )

        client = object.__new__(JmApiClient)
        client.postman = FakePostman()
        client.domain_list = ['bad.example', 'good.example']
        client.retry_times = 2
        client.domain_retry_strategy = None
        client._domain_fail_lock = threading.Lock()
        client._domain_fail_count = {}
        client._image_domain_fail_count = {}

        photo = client.fetch_detail_entity('438516', JmPhotoDetail)
        self.assertEqual(
            ['https://bad.example/chapter?id=438516', 'https://good.example/chapter?id=438516'],
            called_urls,
        )
        self.assertEqual(['00001.webp', '00002.webp'], photo.page_arr)
        self.assertEqual(1, client._domain_fail_count.get('bad.example', 0))

    def test_sync_chapter_all_empty_images_raises_retry_all_fail(self):
        called_urls = []

        class FakePostman:
            def get(self, url, **kwargs):
                called_urls.append(url)
                ts = int(kwargs['headers']['tokenparam'].split(',')[0])
                return _fake_http_resp(
                    url,
                    {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
                    ts,
                )

        client = object.__new__(JmApiClient)
        client.postman = FakePostman()
        client.domain_list = ['d1.example', 'd2.example']
        client.retry_times = 1
        client.domain_retry_strategy = None
        client._domain_fail_lock = threading.Lock()
        client._domain_fail_count = {}
        client._image_domain_fail_count = {}

        with self.assertRaises(RequestRetryAllFailException):
            client.fetch_detail_entity('438516', JmPhotoDetail)
        self.assertEqual(
            ['https://d1.example/chapter?id=438516', 'https://d2.example/chapter?id=438516'],
            called_urls,
        )

    def test_async_chapter_empty_images_reuses_retry_and_recovers(self):
        called_urls = []

        class FakeSession:
            async def get(self, url, **kwargs):
                called_urls.append(url)
                ts = int(kwargs['headers']['tokenparam'].split(',')[0])
                if 'bad.example' in url:
                    return _fake_http_resp(
                        url,
                        {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': []},
                        ts,
                    )
                return _fake_http_resp(
                    url,
                    {'id': 438516, 'name': 'demo', 'series_id': '0', 'series': [], 'tags': '', 'images': ['00001.webp']},
                    ts,
                )

        client = object.__new__(AsyncJmApiClient)
        client._session = FakeSession()
        client._domain_list = ['bad.example', 'good.example']
        client._retry_times = 2
        client._domain_fail_count = {}
        client._image_domain_fail_count = {}
        client._meta_data = {}
        client._cache = None

        async def noop_setup():
            return None

        client.setup = noop_setup
        client._ensure_session = noop_setup

        photo = asyncio.run(client.fetch_detail_entity('438516', JmPhotoDetail))
        self.assertEqual(
            ['https://bad.example/chapter?id=438516', 'https://good.example/chapter?id=438516'],
            called_urls,
        )
        self.assertEqual(['00001.webp'], photo.page_arr)
        self.assertEqual(1, client._domain_fail_count.get('bad.example', 0))


if __name__ == '__main__':
    unittest.main()
