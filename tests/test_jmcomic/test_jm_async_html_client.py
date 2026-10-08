"""异步 HTML Client 的本地契约测试。"""

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from jmcomic import (
    AsyncJmHtmlClient,
    JmAlbumComment,
    JmAlbumCommentPage,
    JmModuleConfig,
    JmOption,
)


class _FakeResponse:
    def __init__(self, text='', status_code=200, url='https://example.com/', json_data=None,
                 content=None, redirect_count=0):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.redirect_count = redirect_count
        self._json_data = json_data
        self.content = content if content is not None else text.encode()
        self.cookies = {}

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self):
        self.calls = []
        self.responses = []
        self.cookies = {}

    async def get(self, url, **kwargs):
        self.calls.append(('get', url, kwargs))
        return self.responses.pop(0)

    async def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        return self.responses.pop(0)

    async def close(self):
        return None


class Test_Async_Html_Client(unittest.TestCase):

    def new_client(self):
        option = JmOption.default()
        option.client.src_dict['retry_times'] = 0
        option.client.src_dict['domain'] = {'html': ['example.com']}
        client = AsyncJmHtmlClient(option)
        client._session = _FakeSession()
        client._has_setup = True
        return client

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_registered_and_factory_selects_html(self):
        self.assertIs(
            JmModuleConfig.async_client_impl_class('async_html'),
            AsyncJmHtmlClient,
        )
        option = JmOption.default()
        option.client.src_dict['async_impl'] = 'async_html'
        option.client.src_dict['domain'] = {'html': ['example.com']}
        client = option.new_jm_async_client()
        try:
            self.assertIsInstance(client, AsyncJmHtmlClient)
            self.assertEqual(client.get_domain_list(), ['example.com'])
        finally:
            self.run_async(client.close())

    def test_domain_validation_and_lifecycle(self):
        option = JmOption.default()
        option.client.src_dict['domain'] = {'html': ['example.com']}
        option.client.src_dict['async_impl'] = 'async_html'

        with self.assertRaises(TypeError):
            AsyncJmHtmlClient(option, domain_list=['example.com', 1])
        with self.assertRaises(TypeError):
            option.new_jm_async_client(domain_list=['example.com', 1])
        with self.assertRaises(TypeError):
            option.new_jm_async_client(domain_retry_strategy=lambda client: client)

        client = AsyncJmHtmlClient(option)
        try:
            self.run_async(client.setup())
            self.assertTrue(client._has_setup)
        finally:
            self.run_async(client.close())
        self.assertFalse(client._has_setup)
        self.assertIsNone(client._session)

    def test_search_cache_avoids_second_request(self):
        client = self.new_client()
        client.set_cache_dict({})
        page = object()
        response = _FakeResponse('html')
        with patch.object(client, 'get_jm_html', new=AsyncMock(return_value=response)) as request, \
             patch('jmcomic.jm_async_html_client.JmPageTool.parse_html_to_search_page', return_value=page):
            first = self.run_async(client.search_site('term'))
            second = self.run_async(client.search_site('term'))

        self.assertIsNot(first, second)
        self.assertEqual(request.await_count, 1)

    def test_html_request_uses_domain_headers_and_path(self):
        client = self.new_client()
        client._session.responses.append(_FakeResponse('ok'))

        response = self.run_async(client.get_jm_html('/album/123'))

        self.assertEqual(response.text, 'ok')
        method, url, kwargs = client._session.calls[0]
        self.assertEqual(method, 'get')
        self.assertEqual(url, 'https://example.com/album/123')
        self.assertEqual(kwargs['headers']['authority'], 'example.com')
        self.assertEqual(kwargs['headers']['origin'], 'https://example.com')
        self.assertEqual(kwargs['headers']['referer'], 'https://example.com')

    def test_configured_headers_keep_explicit_site_headers(self):
        client = self.new_client()
        client.option.client.postman.src_dict['meta_data']['headers'] = {
            'authority': 'custom.example',
            'origin': 'https://custom.example',
            'referer': 'https://custom.example',
            'x-test': 'configured',
        }
        client._session.responses.append(_FakeResponse('ok'))

        self.run_async(client.get_jm_html('/album/123'))

        headers = client._session.calls[0][2]['headers']
        self.assertEqual(headers['authority'], 'custom.example')
        self.assertEqual(headers['origin'], 'https://custom.example')
        self.assertEqual(headers['referer'], 'https://custom.example')
        self.assertEqual(headers['x-test'], 'configured')

    def test_request_retries_transient_network_error(self):
        client = self.new_client()
        client._retry_times = 1

        class FailOnceSession(_FakeSession):
            async def get(self, url, **kwargs):
                self.calls.append(('get', url, kwargs))
                if len(self.calls) == 1:
                    raise OSError('temporary failure')
                return _FakeResponse('ok')

        client._session = FailOnceSession()
        response = self.run_async(client.get_jm_html('/search/photos'))
        self.assertEqual(response.text, 'ok')
        self.assertEqual(len(client._session.calls), 2)

    def test_favorite_and_daily_methods_match_html_contract(self):
        client = self.new_client()
        favorite_response = _FakeResponse(json_data={'status': 1})
        client.post = AsyncMock(return_value=favorite_response)
        self.assertIs(self.run_async(client.add_favorite_album(21, 123)), favorite_response)
        client.post.assert_awaited_once_with(
            '/ajax/favorite_album',
            data={'album_id': '21', 'fid': '123'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )

        daily_response = _FakeResponse(json_data={'status': 1, 'msg': 'Jcoin:1'})
        client.post = AsyncMock(return_value=daily_response)
        result = self.run_async(client.daily_checkin('77', old_step=2))
        self.assertEqual(result.code, result.CODE_SUCCESS)
        client.post.assert_awaited_once_with(
            '/ajax/user_daily_sign',
            data={'daily_id': '77', 'oldStep': '2'},
        )

    def test_login_updates_session_and_option_cookies(self):
        client = self.new_client()
        response = _FakeResponse(json_data={'status': 1, 'msg': 'ok'})
        response.cookies = {'AVS': 'new-avs', 'UID': '12'}
        client.post = AsyncMock(return_value=response)

        result = self.run_async(client.login('alice', 'secret'))

        self.assertIs(result, response)
        self.assertEqual(client._username, 'alice')
        self.assertEqual(client._session.cookies['AVS'], 'new-avs')
        self.assertEqual(client.option.client.postman.meta_data.cookies['UID'], '12')

    def test_login_preserves_existing_avs_when_response_omits_it(self):
        client = self.new_client()
        client.option.client.postman.src_dict['meta_data']['cookies'] = {'AVS': 'old-avs'}
        response = _FakeResponse(json_data={'status': 1, 'msg': 'ok'})
        client.post = AsyncMock(return_value=response)

        self.run_async(client.login('alice', 'secret'))

        self.assertIsNone(client._username)
        self.assertEqual(client.option.client.postman.meta_data.cookies['AVS'], 'old-avs')

    def test_cache_and_image_response(self):
        client = self.new_client()
        client.set_cache_dict({})
        album = SimpleNamespace(album_id='123')
        with patch.object(client, 'get_jm_html', new=AsyncMock(return_value=_FakeResponse('html'))), \
             patch('jmcomic.jm_async_html_client.JmcomicText.analyse_jm_album_html', return_value=album) as parse:
            first = self.run_async(client.get_album_detail('123'))
            second = self.run_async(client.get_album_detail('123'))
        self.assertIsNot(first, second)
        parse.assert_called_once_with('html')

        image_response = _FakeResponse(content=b'raw-image', url='https://cdn.example.com/a.jpg')
        client._session.responses.append(image_response)
        image = self.run_async(client.get_jm_image(image_response.url))
        self.assertEqual(image.content, b'raw-image')
        headers = client._session.calls[-1][2]['headers']
        self.assertEqual(headers['authority'], 'example.com')
        self.assertEqual(headers['referer'], 'https://example.com')

    def test_album_pagination_generator_stops_without_next_link(self):
        client = self.new_client()
        pages = [
            JmAlbumCommentPage(
                [JmAlbumComment({'CID': '1'})],
                page_number=1,
                raw_html='<div id="p_album_comments_1_2"></div>',
            ),
            JmAlbumCommentPage(
                [JmAlbumComment({'CID': '2'})],
                page_number=2,
                raw_html='<div id="p_album_comments_1_2"></div>',
            ),
        ]
        client.album_pagination = AsyncMock(side_effect=pages)

        async def collect():
            return [page async for page in client.album_pagination_gen('123', need_total=False)]

        result = self.run_async(collect())
        self.assertEqual([page.page_number for page in result], [1, 2])
        self.assertEqual(client.album_pagination.await_count, 2)

    @unittest.skipUnless(
        os.environ.get('JM_RUN_REAL_ASYNC_HTML') == '1',
        'set JM_RUN_REAL_ASYNC_HTML=1 for the network smoke test',
    )
    def test_real_actions_html_smoke_with_clash(self):
        """使用 Actions HTML 配置和本地 Clash，在内存中验证网页详情与图片。"""
        from common import ProxyBuilder
        from jmcomic import create_option_by_env

        option = create_option_by_env('JM_OPTION_PATH_TEST')
        option.client.src_dict['async_impl'] = 'async_html'
        self.assertIn('18comic.ink', option.client.domain.get('html', []))
        option.client.postman.meta_data.src_dict['proxies'] = ProxyBuilder.clash_proxy()
        client = option.new_jm_async_client()

        async def run():
            async with client:
                page = await client.search_site('438516', page=1)
                self.assertGreater(len(page), 0)
                album = await client.get_album_detail('438516')
                self.assertEqual(str(album.album_id), '438516')
                self.assertTrue(len(album) > 0)
                photo = await client.get_photo_detail(album[0].photo_id, fetch_album=False)
                image = await client.get_jm_image(photo[0].download_url)
                self.assertGreater(len(image.content), 1000)

        try:
            self.run_async(run())
        finally:
            self.run_async(client.close())


if __name__ == '__main__':
    unittest.main()
