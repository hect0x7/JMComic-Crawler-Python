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
                 content=None, redirect_count=0, headers=None):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.redirect_count = redirect_count
        self._json_data = json_data
        self.content = content if content is not None else text.encode()
        self.cookies = {}
        self.headers = headers or {}

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
        option.client.src_dict['domain'] = {'html': ['example.com']}

        for kwargs in (
            {'impl': 'async_html'},
            {'impl': 'html'},
            {'impl': AsyncJmHtmlClient},
        ):
            client = option.new_jm_async_client(**kwargs)
            try:
                self.assertIsInstance(client, AsyncJmHtmlClient)
                self.assertEqual(client.get_domain_list(), ['example.com'])
            finally:
                self.run_async(client.close())

        option.client.src_dict['impl'] = 'html'
        client = option.new_jm_async_client()
        try:
            self.assertIsInstance(client, AsyncJmHtmlClient)
            self.assertEqual(client.get_domain_list(), ['example.com'])
        finally:
            self.run_async(client.close())

        option.client.src_dict['impl'] = 'api'
        option.client.src_dict['async_impl'] = 'async_html'
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

        async def check_lifecycle():
            await client.setup()
            self.assertTrue(client._has_setup)
            await client.close()

        self.run_async(check_lifecycle())
        self.assertFalse(client._has_setup)
        self.assertIsNone(client._session)

    def test_dynamic_domain_resolution_matches_sync(self):
        from jmcomic import ResponseUnexpectedException

        old_domain_html = JmModuleConfig.DOMAIN_HTML
        old_domain_html_list = JmModuleConfig.DOMAIN_HTML_LIST
        try:
            JmModuleConfig.DOMAIN_HTML = None
            JmModuleConfig.DOMAIN_HTML_LIST = None
            option = JmOption.default()
            option.client.src_dict['domain'] = {}
            client = AsyncJmHtmlClient(option)
            self.assertEqual(client.get_domain_list(), [])

            fake_session = _FakeSession()
            fake_session.responses.extend([
                _FakeResponse(status_code=301, headers={'Location': 'https://step1.example/go'}),
                _FakeResponse(status_code=302, headers={'Location': 'https://resolved-html.example/main'}),
            ])
            client._session = fake_session

            self.run_async(client.setup())
            self.assertEqual(JmModuleConfig.DOMAIN_HTML, 'resolved-html.example')
            self.assertEqual(client.get_domain_list(), ['resolved-html.example'])
            self.assertEqual(fake_session.calls[0][1], JmModuleConfig.JM_REDIRECT_URL)
            self.assertFalse(fake_session.calls[0][2]['allow_redirects'])
            self.assertEqual(fake_session.calls[1][1], 'https://step1.example/go')

            JmModuleConfig.DOMAIN_HTML = None
            client_error = AsyncJmHtmlClient(option)
            error_session = _FakeSession()
            error_session.responses.append(_FakeResponse(status_code=500))
            client_error._session = error_session
            with self.assertRaises(ResponseUnexpectedException):
                self.run_async(client_error.setup())
        finally:
            JmModuleConfig.DOMAIN_HTML = old_domain_html
            JmModuleConfig.DOMAIN_HTML_LIST = old_domain_html_list

    def test_search_cache_avoids_second_request(self):
        client = self.new_client()
        client.set_cache_dict({})
        page = object()
        response = _FakeResponse('html')
        with patch.object(client, 'get_jm_html', new=AsyncMock(return_value=response)) as request, \
             patch('jmcomic.jm_async_client.JmPageTool.parse_html_to_search_page', return_value=page):
            first = self.run_async(client.search_site('term'))
            second = self.run_async(client.search_site('term'))

        self.assertIs(first, second)
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
        client['headers'] = {
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
        )

        daily_response = _FakeResponse(json_data={'status': 1, 'msg': 'Jcoin:1'})
        client.post = AsyncMock(return_value=daily_response)
        result = self.run_async(client.daily_checkin('77', old_step=2))
        self.assertEqual(result.code, result.CODE_SUCCESS)
        client.post.assert_awaited_once_with(
            '/ajax/user_daily_sign',
            data={'daily_id': '77', 'oldStep': '2'},
        )

        finished_response = _FakeResponse(json_data={'msg': '', 'error': 'finished'})
        client.post = AsyncMock(return_value=finished_response)
        finished_result = self.run_async(client.daily_checkin('77'))
        self.assertEqual(finished_result.code, finished_result.CODE_ALREADY_CHECKED_IN)

        tw_already_response = _FakeResponse(json_data={'status': 0, 'msg': '今天已經簽到過了'})
        client.post = AsyncMock(return_value=tw_already_response)
        tw_result = self.run_async(client.daily_checkin('77'))
        self.assertEqual(tw_result.code, tw_result.CODE_ALREADY_CHECKED_IN)

    def test_string_proxy_and_allow_redirect_and_domain_fallback(self):
        option = JmOption.default()
        option.client.src_dict['domain'] = {'html': ['bad.example.com', 'good.example.com']}
        option.client.src_dict['retry_times'] = 3
        option.client.postman.src_dict['meta_data']['proxies'] = '127.0.0.1:7890'
        client = AsyncJmHtmlClient(option)

        with patch.dict('sys.modules', {'common': None}), \
             patch('jmcomic.jm_async_client.AsyncSession') as session_cls:
            fake_session = _FakeSession()
            session_cls.return_value = fake_session
            self.run_async(client._ensure_session())
            called_kwargs = session_cls.call_args.kwargs
            self.assertEqual(
                called_kwargs['proxies'],
                {'http': '127.0.0.1:7890', 'https': '127.0.0.1:7890'},
            )

        class FallbackSession(_FakeSession):
            async def get(self, url, **kwargs):
                self.calls.append(('get', url, kwargs))
                if 'bad.example.com' in url:
                    raise OSError('bad domain')
                return _FakeResponse('ok', url=url)

        client._session = FallbackSession()
        client._has_setup = True
        album = SimpleNamespace(album_id='123')
        with patch('jmcomic.jm_async_client.JmcomicText.analyse_jm_album_html', return_value=album):
            detail = self.run_async(client.get_album_detail('123', allow_redirect=False))
            self.run_async(client.get_album_detail('456', allow_redirect=False))
        self.assertEqual(detail.album_id, '123')
        self.assertEqual(len(client._session.calls), 3)
        self.assertEqual(client._session.calls[0][1], 'https://bad.example.com/album/123')
        self.assertEqual(client._session.calls[1][1], 'https://good.example.com/album/123')
        self.assertEqual(client._session.calls[1][2]['headers']['authority'], 'good.example.com')
        # 后续请求因 bad.example.com 失败计数 > 0，直接优先走 good.example.com
        self.assertEqual(client._session.calls[2][1], 'https://good.example.com/album/456')

    def test_search_redirect_to_single_album_and_query_url(self):
        client = self.new_client()
        redirect_resp = _FakeResponse(
            'album-html',
            url='https://example.com/album/438516',
            redirect_count=1,
        )
        client._session.responses.append(redirect_resp)
        fake_album = SimpleNamespace(
            album_id='438516',
            name='test-album',
            author='author',
            tags=['tag1'],
        )
        with patch('jmcomic.jm_async_client.JmcomicText.analyse_jm_album_html', return_value=fake_album):
            page = self.run_async(client.search_site('438516'))
        self.assertTrue(page.is_single_album)
        self.assertEqual(page.single_album.album_id, '438516')
        _, called_url, _ = client._session.calls[0]
        self.assertIn('search_query=438516', called_url)

    def test_login_updates_session_and_client_cookies(self):
        client = self.new_client()
        response = _FakeResponse(json_data={'status': 1, 'msg': 'ok'})
        response.cookies = {'AVS': 'new-avs', 'UID': '12'}
        client.post = AsyncMock(return_value=response)

        result = self.run_async(client.login('alice', 'secret'))

        self.assertIs(result, response)
        self.assertEqual(client._username, 'alice')
        self.assertEqual(client._session.cookies['AVS'], 'new-avs')
        self.assertEqual(client['cookies']['UID'], '12')
        self.assertIsNone(client.option.client.postman.meta_data.src_dict.get('cookies'))

    def test_login_plugin_propagates_to_new_clients_without_polluting_cache(self):
        from jmcomic import JmApiClient, JmHtmlClient, JmLoginPlugin

        option = JmOption.default()
        option.client.src_dict['impl'] = 'api'
        option.client.src_dict['domain'] = {'html': ['example.com'], 'api': ['api.example.com']}

        def fake_html_login(self_client, username, password):
            self_client['cookies'] = {'AVS': 'plugin-avs'}
            self_client._username = username
            self_client._user_id = '9527'

        with patch.object(JmHtmlClient, 'login', fake_html_login), \
             patch.object(JmApiClient, 'after_init', lambda self_client: None):
            JmLoginPlugin.build(option).invoke(username='bob', password='pwd', impl='html')
            cached_default_client = option.build_jm_client()
            new_sync_client = option.new_jm_client(impl='html')
            new_async_client = option.new_jm_async_client(impl='html')

        self.assertIsInstance(cached_default_client, JmApiClient)
        self.assertEqual(cached_default_client['cookies'], {'AVS': 'plugin-avs'})
        self.assertEqual(cached_default_client._username, 'bob')
        self.assertEqual(cached_default_client._user_id, '9527')

        self.assertEqual(new_sync_client['cookies'], {'AVS': 'plugin-avs'})
        self.assertEqual(new_sync_client._username, 'bob')
        self.assertEqual(new_sync_client._user_id, '9527')

        self.assertEqual(new_async_client['cookies'], {'AVS': 'plugin-avs'})
        self.assertEqual(new_async_client._username, 'bob')
        self.assertEqual(new_async_client._user_id, '9527')

    def test_login_plugin_always_forces_login_and_writes_back_auth(self):
        from jmcomic import JmHtmlClient, JmLoginPlugin

        login_calls = []

        def fake_html_login(self_client, username, password):
            login_calls.append((username, password))
            self_client['cookies'] = {'AVS': f'fresh-avs-{len(login_calls)}'}
            self_client._username = username

        option = JmOption.construct({
            'auth': {'username': 'bob', 'password': 'pwd', 'cookies': {'AVS': 'stale-avs'}},
            'client': {'impl': 'html', 'domain': ['example.com']},
        })

        with patch.object(JmHtmlClient, 'login', fake_html_login):
            # auth 已有 cookies 且参数与 auth 相同：仍然发起登录，刷新可能过期的 cookies
            JmLoginPlugin.build(option).invoke(username='bob', password='pwd')
            self.assertEqual(option.auth.src_dict['cookies']['AVS'], 'fresh-avs-1')

            # 不传参数：使用 option.auth 中的账号登录
            JmLoginPlugin.build(option).invoke()

            # 传入新账号：账号与密码一起写回 option.auth
            JmLoginPlugin.build(option).invoke(username='carol', password='pwd2')

        self.assertEqual(login_calls, [('bob', 'pwd'), ('bob', 'pwd'), ('carol', 'pwd2')])
        self.assertEqual(option.auth.src_dict['cookies']['AVS'], 'fresh-avs-3')
        self.assertEqual(option.auth.src_dict['username'], 'carol')
        self.assertEqual(option.auth.src_dict['password'], 'pwd2')
        self.assertEqual(option.new_jm_client()['cookies']['AVS'], 'fresh-avs-3')

    def test_auth_env_placeholder_resolved(self):
        env = {'JM_TEST_AUTH_USER': 'env_user', 'JM_TEST_AUTH_PASS': 'env_pass', 'JM_TEST_AUTH_AVS': 'env_avs'}
        with patch.dict(os.environ, env):
            option = JmOption.construct({
                'auth': {
                    'username': '${JM_TEST_AUTH_USER}',
                    'password': '${JM_TEST_AUTH_PASS}',
                    'cookies': {'AVS': '${JM_TEST_AUTH_AVS}'},
                },
                'client': {'impl': 'html', 'domain': ['example.com']},
            })

        # 创建 option 时替换为环境变量的值
        self.assertEqual(option.auth.username, 'env_user')
        self.assertEqual(option.auth.password, 'env_pass')
        self.assertEqual(option.auth.src_dict['cookies']['AVS'], 'env_avs')
        self.assertEqual(option.new_jm_client()['cookies']['AVS'], 'env_avs')

        # deconstruct 导出解析后的值，并过滤掉运行时字段 cookies / user_id
        auth_dict = option.deconstruct()['auth']
        self.assertEqual(auth_dict['username'], 'env_user')
        self.assertEqual(auth_dict['password'], 'env_pass')
        self.assertEqual(option.copy_option().deconstruct()['auth']['password'], 'env_pass')

        # 字段在运行时被改成别的值后，按新值保存
        option.auth.username = 'other_user'
        self.assertEqual(option.deconstruct()['auth']['username'], 'other_user')

        # 环境变量未设置：直接报错
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('JM_TEST_AUTH_MISSING', None)
            with self.assertRaises(Exception):
                JmOption.construct({'auth': {'username': '${JM_TEST_AUTH_MISSING}'}})

    def test_favorite_folder_export_logs_in_with_auth(self):
        from jmcomic import FavoriteFolderExportPlugin

        option = JmOption.construct({
            'auth': {'username': 'bob', 'password': 'pwd'},
            'client': {'impl': 'html', 'domain': ['example.com']},
        })
        events = []

        def fake_login(*_args, **_kwargs):
            events.append('login')

        class _StopAfterBuild(Exception):
            pass

        def fake_build(*_args, **_kwargs):
            events.append('build_client')
            raise _StopAfterBuild()

        plugin = FavoriteFolderExportPlugin.build(option)
        with patch.object(option, 'login_with_option_auth', fake_login), \
             patch.object(option, 'build_jm_client', fake_build):
            with self.assertRaises(_StopAfterBuild):
                plugin.main()
        self.assertEqual(events, ['login', 'build_client'])

        # 未配置账号密码：不登录
        no_auth = JmOption.construct({'client': {'impl': 'html', 'domain': ['example.com']}})
        events.clear()
        plugin = FavoriteFolderExportPlugin.build(no_auth)
        with patch.object(no_auth, 'login_with_option_auth', fake_login), \
             patch.object(no_auth, 'build_jm_client', fake_build):
            with self.assertRaises(_StopAfterBuild):
                plugin.main()
        self.assertEqual(events, ['build_client'])

    def test_login_preserves_existing_avs_when_response_omits_it(self):
        client = self.new_client()
        client['cookies'] = {'AVS': 'old-avs'}
        response = _FakeResponse(json_data={'status': 1, 'msg': 'ok'})
        client.post = AsyncMock(return_value=response)

        self.run_async(client.login('alice', 'secret'))

        self.assertIsNone(client._username)
        self.assertEqual(client['cookies']['AVS'], 'old-avs')

    def test_cache_and_image_response(self):
        from jmcomic import JmAlbumDetail
        client = self.new_client()
        client.set_cache_dict({})
        album = object.__new__(JmAlbumDetail)
        album.album_id = '123'
        with patch.object(client, 'get_jm_html', new=AsyncMock(return_value=_FakeResponse('html'))), \
             patch('jmcomic.jm_async_client.JmcomicText.analyse_jm_album_html', return_value=album) as parse:
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

        client['headers'] = {
            'authority': 'custom.example',
            'referer': 'https://custom.example',
            'user-agent': 'custom-ua',
        }
        client._session.responses.append(image_response)
        self.run_async(client.get_jm_image(image_response.url))
        custom_headers = client._session.calls[-1][2]['headers']
        self.assertEqual(custom_headers['authority'], 'custom.example')
        self.assertEqual(custom_headers['referer'], 'https://custom.example')
        self.assertEqual(custom_headers['user-agent'], 'custom-ua')

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

    def test_round2_contract_regressions(self):
        import inspect
        from jmcomic import AsyncJmApiClient, JmApiClient

        # 1. @wraps preserves name, docstring and clean signature
        self.assertEqual(AsyncJmHtmlClient.search.__name__, 'search')
        self.assertIsNotNone(AsyncJmApiClient.search.__doc__)
        sig_params = list(inspect.signature(AsyncJmHtmlClient.search).parameters)
        self.assertNotIn('_func', sig_params)
        self.assertNotIn('_name', sig_params)

        # 2. Cross-event-loop lock contention does not raise RuntimeError
        html_client = self.new_client()

        async def contend_locks():
            lock = AsyncJmHtmlClient._get_setup_lock()
            session_lock = html_client._get_session_lock()

            async def worker(lck):
                async with lck:
                    await asyncio.sleep(0.005)

            await asyncio.gather(worker(lock), worker(lock), worker(session_lock), worker(session_lock))

        self.run_async(contend_locks())
        self.run_async(contend_locks())

        # 4. Pre-session __setitem__, close() cookie persistence, and meta_data isolation
        opt = JmOption.default()
        opt.client.src_dict['domain'] = {'html': ['example.com']}
        fresh_client = AsyncJmHtmlClient(opt)
        fresh_client['cookies'] = {'AVS': 'pre-session'}
        self.assertIsNone(opt.client.postman.meta_data.src_dict.get('cookies'))
        self.run_async(fresh_client.setup())
        self.assertEqual(fresh_client._session.cookies.get('AVS'), 'pre-session')
        self.run_async(fresh_client.close())
        self.assertEqual(fresh_client['cookies'], {'AVS': 'pre-session'})
        self.run_async(fresh_client.setup())
        self.assertEqual(fresh_client._session.cookies.get('AVS'), 'pre-session')
        self.run_async(fresh_client.close())

        # 5. new_jm_async_client(True) positional cache parameter compatibility
        cached_client = opt.new_jm_async_client(True, impl='html')
        self.assertIsNotNone(cached_client.get_cache_dict())

        # 6. get_daily, daily_checkin, add/delete_favorite_album signatures aligned across async clients
        for method_name in (
            'get_album_detail',
            'get_photo_detail',
            'search',
            'categories_filter',
            'favorite_folder',
            'add_favorite_album',
            'delete_favorite_album',
            'get_daily',
            'daily_checkin',
            'album_comment',
            'album_pagination',
            'forum_pagination',
        ):
            html_params = list(inspect.signature(getattr(AsyncJmHtmlClient, method_name)).parameters)
            api_params = list(inspect.signature(getattr(AsyncJmApiClient, method_name)).parameters)
            self.assertEqual(html_params, api_params, f'Signature mismatch on {method_name}')
        self.assertIn('daily_id', inspect.signature(JmApiClient.get_daily).parameters)

    def test_top_level_auth_priority_and_login_with_option_auth(self):
        from jmcomic import AsyncJmApiClient, JmApiClient, JmHtmlClient

        # 1. async_impl fallback: non-html/api sync impl falls back to async_api without error
        proxy_opt = JmOption.construct({
            'client': {'impl': 'photo_concurrent_fetcher_proxy'},
        })
        fallback_async_client = proxy_opt.new_jm_async_client()
        self.assertIsInstance(fallback_async_client, AsyncJmApiClient)

        # 1b. Constructing JmOption without auth (or partial auth) works cleanly without KeyError
        base_dict = JmOption.default_dict()
        base_dict.pop('auth', None)
        base_dict.pop('log', None)
        base_dict.pop('version', None)
        direct_opt = JmOption(**base_dict)
        self.assertFalse(bool(direct_opt.auth))
        direct_opt.client.domain = ['example.com']
        direct_opt.client.impl = 'html'
        self.assertIsNotNone(direct_opt.new_jm_client())
        self.assertIsNotNone(direct_opt.new_jm_async_client())
        self.assertFalse(direct_opt._is_auth_logged_in(is_api=False))
        # Setting only username/password via direct_opt.auth.* without cookies/user_id keys does not raise KeyError
        direct_opt.auth.username = 'partial_u'
        direct_opt.auth.password = 'partial_p'
        self.assertIsNotNone(direct_opt.new_jm_client())
        self.assertIsNotNone(direct_opt.new_jm_async_client())
        self.assertFalse(direct_opt._is_auth_logged_in(is_api=False))

        # 2. Priority: explicit kwargs > top-level auth > legacy postman.meta_data
        option = JmOption.construct({
            'auth': {
                'username': 'auth_user',
                'password': 'auth_password',
                'user_id': '888',
                'cookies': {'AVS': 'auth_avs', 'auth_only': '1'},
            },
            'client': {
                'impl': 'html',
                'domain': ['example.com'],
                'postman': {
                    'meta_data': {
                        'cookies': {'AVS': 'legacy_avs', 'legacy_only': '1'},
                    },
                },
            },
        })
        copied = option.copy_option()
        self.assertEqual(copied.auth.username, 'auth_user')
        deconstructed = option.deconstruct()
        self.assertIn('auth', deconstructed)
        # deconstruct strips temporary runtime fields (cookies, user_id)
        self.assertNotIn('cookies', deconstructed['auth'])
        self.assertNotIn('user_id', deconstructed['auth'])
        self.assertEqual(deconstructed['auth']['username'], 'auth_user')

        sync_client = option.new_jm_client()
        self.assertEqual(sync_client._username, 'auth_user')
        self.assertEqual(sync_client._user_id, '888')
        self.assertEqual(sync_client['cookies']['AVS'], 'auth_avs')
        self.assertEqual(sync_client['cookies']['legacy_only'], '1')

        async_client = option.new_jm_async_client()
        self.assertEqual(async_client._username, 'auth_user')
        self.assertEqual(async_client._user_id, '888')
        self.assertEqual(async_client['cookies']['AVS'], 'auth_avs')
        self.assertEqual(async_client['cookies']['legacy_only'], '1')

        explicit_async = option.new_jm_async_client(cookies={'AVS': 'explicit_avs'})
        self.assertEqual(explicit_async['cookies']['AVS'], 'explicit_avs')
        self.assertEqual(explicit_async['cookies']['auth_only'], '1')

        # 3. One-way flow: client manual login(B) is not overwritten by option.auth(A) on close -> setup
        async_client._session = _FakeSession()
        async_client._has_setup = True
        login_b_resp = _FakeResponse(json_data={'status': 1})
        login_b_resp.cookies = {'AVS': 'account_b_avs'}
        async_client._session.responses.append(login_b_resp)
        self.run_async(async_client.login('user_b', 'pass_b'))
        self.assertEqual(async_client['cookies']['AVS'], 'account_b_avs')
        self.assertEqual(async_client._username, 'user_b')
        self.run_async(async_client.close())
        self.run_async(async_client.setup())
        self.assertEqual(async_client._session.cookies.get('AVS'), 'account_b_avs')
        self.assertEqual(async_client._username, 'user_b')
        self.run_async(async_client.close())

        # 4. Sync login_with_option_auth: new_jm_client does not auto-login; login_with_option_auth is idempotent
        sync_login_calls = []

        def fake_sync_api_login(client_self, u, p, *args, **kwargs):
            sync_login_calls.append((u, p))
            client_self['cookies'] = {'AVS': 'sync_auth_avs'}
            client_self._username = u
            client_self._user_id = '9001'

        auth_opt = JmOption.construct({
            'auth': {'username': 'sync_u', 'password': 'sync_p', 'cookies': {'AVS': 'cookie_without_uid'}},
            'client': {'impl': 'api', 'domain': ['example.com']},
        })
        with patch.object(JmApiClient, 'after_init', lambda s: None), \
             patch.object(JmApiClient, 'login', fake_sync_api_login):
            # Pure memory construction: does not trigger network login
            c_before = auth_opt.new_jm_client()
            self.assertEqual(len(sync_login_calls), 0)
            self.assertIsNone(c_before._user_id)

            # Even though cookies exist, API requires user_id as well -> triggers login once
            auth_opt.login_with_option_auth()
            self.assertEqual(len(sync_login_calls), 1)
            self.assertEqual(auth_opt.auth.src_dict['cookies']['AVS'], 'sync_auth_avs')
            self.assertEqual(auth_opt.auth.src_dict['user_id'], '9001')

            # Idempotent second call (both cookies and user_id are now present)
            auth_opt.login_with_option_auth()
            self.assertEqual(len(sync_login_calls), 1)

            # Force=True triggers re-login
            auth_opt.login_with_option_auth(force=True)
            self.assertEqual(len(sync_login_calls), 2)

            c_after = auth_opt.new_jm_client()
            self.assertEqual(c_after['cookies']['AVS'], 'sync_auth_avs')
            self.assertEqual(c_after._user_id, '9001')

        # 5. Async login_with_option_auth_async: idempotent across concurrent calls
        async_login_calls = []

        async def fake_async_html_login(client_self, u, p, *args, **kwargs):
            async_login_calls.append((u, p))
            client_self['cookies'] = {'AVS': 'async_auth_avs'}
            client_self._username = u

        async_auth_opt = JmOption.construct({
            'auth': {'username': 'async_u', 'password': 'async_p'},
            'client': {'impl': 'html', 'domain': ['example.com']},
        })
        with patch.object(AsyncJmHtmlClient, 'login', fake_async_html_login):
            async def run_concurrent_auth():
                await asyncio.gather(
                    async_auth_opt.login_with_option_auth_async(),
                    async_auth_opt.login_with_option_auth_async(),
                )

            self.run_async(run_concurrent_auth())

        self.assertEqual(async_login_calls, [('async_u', 'async_p')])
        ac_after = async_auth_opt.new_jm_async_client()
        self.assertEqual(ac_after['cookies']['AVS'], 'async_auth_avs')
        self.assertEqual(ac_after._username, 'async_u')

        # 6. download_* login parameter (default login=True vs login=False)
        from jmcomic import download_album, download_album_async
        dl_opt = JmOption.construct({
            'auth': {'username': 'dl_u', 'password': 'dl_p'},
            'client': {'impl': 'html', 'domain': ['example.com']},
        })

        class _DummyDler:
            def __init__(self, opt):
                self.option = opt
                self.manifest_dict = {'album_detail': SimpleNamespace(duration=None)}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def add_features(self, extra):
                pass

            def raise_if_has_exception(self):
                pass

            def download_album(self, aid):
                if isinstance(self.option.client.async_impl, str):
                    pass
                return 'album_detail'

        class _DummyAsyncDler(_DummyDler):
            async def download_album(self, aid):
                return 'album_detail'

        with patch.object(dl_opt, 'login_with_option_auth') as mock_sync_login, \
             patch.object(dl_opt, 'login_with_option_auth_async', new_callable=AsyncMock) as mock_async_login:
            download_album('123', dl_opt, downloader=_DummyDler, login=False)
            mock_sync_login.assert_not_called()
            download_album('123', dl_opt, downloader=_DummyDler)
            mock_sync_login.assert_called_once()

            self.run_async(download_album_async('123', dl_opt, downloader=_DummyAsyncDler, login=False))
            mock_async_login.assert_not_awaited()
            self.run_async(download_album_async('123', dl_opt, downloader=_DummyAsyncDler))
            mock_async_login.assert_awaited_once()

    def test_curl_cffi_session_postman_sync_and_async(self):
        from jmcomic import AsyncJmApiClient, AsyncJmHtmlClient, JmApiClient, JmHtmlClient
        from jmcomic.common import CurlCffiSessionPostman

        # 1. Sync client (api & html) with curl_cffi_session preserves existing session cookies on update/login and supports copy()
        opt_api = JmOption.construct({
            'auth': {'username': 'sess_user', 'password': 'sess_pass'},
            'client': {
                'impl': 'api',
                'domain': ['example.com'],
                'postman': {
                    'type': 'curl_cffi_session',
                    'meta_data': {
                        'impersonate': 'chrome',
                        'cookies': {'ipcountry': 'HK', 'ipm5': 'init_ipm5'},
                    },
                },
            },
        })

        with patch.object(JmApiClient, 'after_init', lambda s: None):
            c_api = opt_api.new_jm_client()
            self.assertIsInstance(c_api.postman, CurlCffiSessionPostman)
            # copy() works without AttributeError on meta_data
            copied_postman = c_api.postman.copy()
            self.assertIsInstance(copied_postman, CurlCffiSessionPostman)

            # Updating client['cookies'] merges into session.cookies rather than wiping ipcountry/ipm5
            c_api['cookies'] = {'AVS': 'session_avs_1'}
            cookies_dict = dict(c_api['cookies'])
            self.assertEqual(cookies_dict.get('ipcountry'), 'HK')
            self.assertEqual(cookies_dict.get('ipm5'), 'init_ipm5')
            self.assertEqual(cookies_dict.get('AVS'), 'session_avs_1')

            # Second update overrides AVS while still keeping ipcountry/ipm5
            c_api['cookies'] = {'AVS': 'session_avs_2'}
            cookies_dict_2 = dict(c_api['cookies'])
            self.assertEqual(cookies_dict_2.get('ipcountry'), 'HK')
            self.assertEqual(cookies_dict_2.get('AVS'), 'session_avs_2')

            # login_with_option_auth with curl_cffi_session writes merged cookies & user_id back to option.auth
            def fake_session_api_login(client_self, u, p):
                client_self['cookies'] = {'AVS': 'logged_in_session_avs'}
                client_self._username = u
                client_self._user_id = '7788'

            with patch.object(JmApiClient, 'login', fake_session_api_login):
                opt_api.login_with_option_auth()

            self.assertEqual(opt_api.auth.cookies['AVS'], 'logged_in_session_avs')
            self.assertEqual(opt_api.auth.cookies['ipcountry'], 'HK')
            self.assertEqual(opt_api.auth.user_id, '7788')

            # Subsequent sync and async clients created from opt_api inherit the session cookies & auth state
            c_api_next = opt_api.new_jm_client()
            self.assertEqual(dict(c_api_next['cookies']).get('AVS'), 'logged_in_session_avs')
            self.assertEqual(dict(c_api_next['cookies']).get('ipcountry'), 'HK')
            self.assertEqual(c_api_next._user_id, '7788')

        ac_api = opt_api.new_jm_async_client()
        self.assertIsInstance(ac_api, AsyncJmApiClient)
        self.assertEqual(ac_api['cookies']['AVS'], 'logged_in_session_avs')
        self.assertEqual(ac_api['cookies']['ipcountry'], 'HK')
        self.assertEqual(ac_api._user_id, '7788')

        # 2. Async client login_with_option_auth_async when option is configured with curl_cffi_session
        opt_html = JmOption.construct({
            'auth': {'username': 'html_sess_u', 'password': 'html_sess_p'},
            'client': {
                'impl': 'html',
                'domain': ['example.com'],
                'postman': {
                    'type': 'curl_cffi_session',
                    'meta_data': {
                        'impersonate': 'chrome',
                    },
                },
            },
        })

        async def fake_async_html_login(client_self, u, p, *args, **kwargs):
            client_self['cookies'] = {'AVS': 'async_html_sess_avs', 'ipcountry': 'SG'}
            client_self._username = u

        with patch.object(AsyncJmHtmlClient, 'login', fake_async_html_login):
            self.run_async(opt_html.login_with_option_auth_async())

        self.assertEqual(opt_html.auth.cookies['AVS'], 'async_html_sess_avs')
        self.assertEqual(opt_html.auth.username, 'html_sess_u')

        # Both sync (curl_cffi_session) and async clients created afterward carry the logged-in state
        sync_html = opt_html.new_jm_client()
        self.assertIsInstance(sync_html.postman, CurlCffiSessionPostman)
        self.assertEqual(dict(sync_html['cookies']).get('AVS'), 'async_html_sess_avs')
        self.assertEqual(sync_html._username, 'html_sess_u')

        async_html = opt_html.new_jm_async_client()
        self.assertIsInstance(async_html, AsyncJmHtmlClient)
        self.assertEqual(async_html['cookies']['AVS'], 'async_html_sess_avs')
        self.assertEqual(async_html._username, 'html_sess_u')
        self.run_async(async_html.setup())
        self.assertEqual(async_html._session.cookies.get('AVS'), 'async_html_sess_avs')
        self.run_async(async_html.close())

    @unittest.skipUnless(
        os.environ.get('JM_RUN_REAL_ASYNC_HTML') == '1',
        'set JM_RUN_REAL_ASYNC_HTML=1 for the network smoke test',
    )
    def test_real_actions_html_smoke_with_clash(self):
        """使用 Actions HTML 配置和本地 Clash，在内存中验证网页详情与图片。"""
        from jmcomic import ProxyBuilder, create_option_by_env

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
