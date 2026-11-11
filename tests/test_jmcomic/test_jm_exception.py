from test_jmcomic import *
import asyncio
from types import SimpleNamespace


class Test_RequestRetryAllFailException(unittest.TestCase):

    @staticmethod
    def _new_sync_client(domain_list, retry_times=1):
        return AbstractJmClient(
            postman=SimpleNamespace(),
            domain_list=domain_list,
            retry_times=retry_times,
        )

    @staticmethod
    def _new_async_client(session, domain_list, retry_times=0):
        client = AsyncJmApiClient(JmOption.default(), domain_list=domain_list)
        client._retry_times = retry_times
        client._session = session
        client._has_setup = True
        return client

    def test_sync_client_collects_each_failed_request(self):
        client = self._new_sync_client(['api-one.example', 'api-two.example'], retry_times=2)

        def request(url, **kwargs):
            raise TimeoutError(url)

        with self.assertRaises(RequestRetryAllFailException) as cm:
            client.request_with_retry(request, '/search')

        errors = cm.exception.errors
        self.assertEqual(3, len(errors))
        self.assertEqual(['api-one.example', 'api-two.example', 'api-one.example'],
                         [item['domain'] for item in errors])
        self.assertEqual([0, 1, 2], [item['retry'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], TimeoutError) for item in errors))

        # retry_times=0 时仅发 1 次请求，失败立即返回不重试
        zero_client = self._new_sync_client(['api-one.example', 'api-two.example'], retry_times=0)
        with self.assertRaises(RequestRetryAllFailException) as zero_cm:
            zero_client.request_with_retry(request, '/search')
        self.assertEqual(['api-one.example'], [item['domain'] for item in zero_cm.exception.errors])

    def test_sync_client_sorts_domains_by_fail_count(self):
        client = self._new_sync_client(['bad.example', 'good.example'], retry_times=1)

        seen_urls = []

        def request(url, **kwargs):
            seen_urls.append(url)
            if 'bad.example' in url:
                raise TimeoutError(url)
            return SimpleNamespace(status_code=200, url=url, text='ok')

        resp1 = client.request_with_retry(request, '/album')
        self.assertEqual('https://good.example/album', resp1.url)

        seen_urls.clear()
        resp2 = client.request_with_retry(request, '/chapter')
        self.assertEqual('https://good.example/chapter', resp2.url)
        self.assertEqual(['https://good.example/chapter'], seen_urls)

    def test_sync_client_does_not_multiply_absolute_image_url_by_domains(self):
        client = self._new_sync_client(['d1.example', 'd2.example', 'd3.example', 'd4.example'], retry_times=2)

        img_url = 'https://cdn-msp.example/media/photos/123/00001.webp'
        calls = []

        def failing_img_request(url, **kwargs):
            calls.append(url)
            raise ConnectionError(url)

        with unittest.mock.patch.object(JmModuleConfig, 'DOMAIN_IMAGE_LIST', ['img1.example', 'img2.example', 'img3.example']):
            with self.assertRaises(RequestRetryAllFailException) as cm:
                client.request_with_retry(failing_img_request, img_url, is_image=True)

        # 总尝试次数严格等于 1 + retry_times = 3，不会乘以域名数放大，且每次重试自动切下一个图床节点
        self.assertEqual(3, len(calls))
        self.assertEqual([
            'https://cdn-msp.example/media/photos/123/00001.webp',
            'https://img1.example/media/photos/123/00001.webp',
            'https://img2.example/media/photos/123/00001.webp',
        ], calls)
        self.assertEqual(3, len(cm.exception.errors))
        self.assertEqual(['cdn-msp.example', 'img1.example', 'img2.example'],
                         [item['domain'] for item in cm.exception.errors])
        self.assertEqual({}, client._domain_fail_count)
        self.assertEqual({'cdn-msp.example': 1, 'img1.example': 1, 'img2.example': 1},
                         client._image_domain_fail_count)

        # 非禁漫 /media/ 路径的普通外链图片不改写域名
        calls.clear()
        ext_url = 'https://other.example/custom/pic.webp'
        with self.assertRaises(RequestRetryAllFailException) as ext_cm:
            client.request_with_retry(failing_img_request, ext_url, is_image=True)
        self.assertEqual([ext_url, ext_url, ext_url], calls)
        self.assertEqual([None, None, None], [item['domain'] for item in ext_cm.exception.errors])

    def test_advanced_retry_invoke_logs_deprecation_without_hooking_new_jm_client(self):
        from unittest.mock import patch

        logged = []
        with patch('jmcomic.jm_plugin.jm_log', side_effect=lambda topic, msg, *a, **kw: logged.append((topic, msg))):
            option = JmOption.construct({
                'plugins': {
                    'after_init': [
                        {
                            'plugin': 'advanced_retry',
                            'kwargs': {
                                'retry_config': {
                                    'retry_rounds': 2,
                                    'retry_domain_max_times': 3,
                                }
                            }
                        }
                    ]
                }
            })

        self.assertTrue(
            any(topic == 'plugin.advanced_retry.deprecated' and '不再需要配置 advanced_retry' in msg
                for topic, msg in logged),
            f'未捕获到 advanced_retry 废弃提示日志: {logged}',
        )
        self.assertNotIn('new_jm_client', option.__dict__)

    def test_async_client_collects_each_failed_request(self):
        class FailingSession:
            async def get(self, url, **kwargs):
                raise ConnectionError(url)

        client = self._new_async_client(FailingSession(), ['api-one.example', 'api-two.example'], retry_times=2)

        async def request():
            return await client._request_with_retry('/search', {})

        with self.assertRaises(RequestRetryAllFailException) as cm:
            asyncio.run(request())

        errors = cm.exception.errors
        self.assertEqual(3, len(errors))
        self.assertEqual(['api-one.example', 'api-two.example', 'api-one.example'],
                         [item['domain'] for item in errors])
        self.assertEqual([0, 1, 2], [item['retry'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], ConnectionError) for item in errors))

        zero_client = self._new_async_client(FailingSession(), ['api-one.example', 'api-two.example'], retry_times=0)
        with self.assertRaises(RequestRetryAllFailException) as zero_cm:
            asyncio.run(zero_client._request_with_retry('/search', {}))
        self.assertEqual(['api-one.example'], [item['domain'] for item in zero_cm.exception.errors])

    def test_preserves_and_formats_retry_errors(self):
        error_500 = ResponseUnexpectedException('禁漫API异常响应, 500', {})
        error_timeout = TimeoutError('connection timed out')
        errors = [
            {
                'domain': 'api-one.example',
                'url': 'https://api-one.example/search',
                'retry': 0,
                'error': error_500,
            },
            {
                'domain': 'api-two.example',
                'url': 'https://api-two.example/search',
                'retry': 1,
                'error': error_timeout,
            },
        ]
        exception = RequestRetryAllFailException(
            '请求重试全部失败',
            {ExceptionTool.CONTEXT_KEY_RETRY_ERRORS: errors},
        )

        self.assertIs(exception.errors[0]['error'], error_500)
        self.assertIs(exception.errors[1]['error'], error_timeout)
        text = str(exception)
        self.assertIn('ResponseUnexpectedException: 禁漫API异常响应, 500', text)
        self.assertIn('TimeoutError: connection timed out', text)
        self.assertIn('https://api-one.example/search, retry=0', text)

    def test_sync_and_async_image_cdn_failover_and_promotion(self):
        from unittest.mock import patch

        with patch.object(JmModuleConfig, 'DOMAIN_IMAGE_LIST', ['img-bad.example', 'img-good.example']):
            # 1) 同步客户端：原图床失败 -> 切换备用图床并保留 query 参数 -> 下一张图直接走健康图床
            sync_client = self._new_sync_client(['html.example'], retry_times=2)
            sync_seen = []

            def fake_sync_req(url, **kwargs):
                sync_seen.append(url)
                if 'orig-html.example' in url or 'img-bad.example' in url:
                    return SimpleNamespace(status_code=200, url=url, content=b'', text='')
                return SimpleNamespace(status_code=200, url=url, content=b'webp-bytes', text='ok')

            resp1 = sync_client.request_with_retry(
                fake_sync_req,
                'https://orig-html.example/media/photos/438516/00001.webp?v=99',
                is_image=True,
            )
            self.assertEqual(b'webp-bytes', resp1.content)
            self.assertEqual([
                'https://orig-html.example/media/photos/438516/00001.webp?v=99',
                'https://img-bad.example/media/photos/438516/00001.webp?v=99',
                'https://img-good.example/media/photos/438516/00001.webp?v=99',
            ], sync_seen)

            sync_seen.clear()
            resp2 = sync_client.request_with_retry(
                fake_sync_req,
                'https://img-bad.example/media/photos/438516/00002.webp?v=99',
                is_image=True,
            )
            self.assertEqual(b'webp-bytes', resp2.content)
            self.assertEqual(['https://img-good.example/media/photos/438516/00002.webp?v=99'], sync_seen)

            # 2) 异步客户端：同样在 1 + retry_times 预算内切换并后置失败图床
            async_seen = []

            class ImageSwitchSession:
                async def get(self, url, **kwargs):
                    async_seen.append(url)
                    if 'orig-html.example' in url or 'img-bad.example' in url:
                        raise TimeoutError(url)
                    return SimpleNamespace(status_code=200, url=url, content=b'async-webp', text='ok')

            async_client = self._new_async_client(ImageSwitchSession(), ['api.example'], retry_times=2)

            aresp1 = asyncio.run(async_client.get_jm_image('https://orig-html.example/media/photos/438516/00001.webp'))
            self.assertEqual(b'async-webp', aresp1.content)
            self.assertEqual([
                'https://orig-html.example/media/photos/438516/00001.webp',
                'https://img-bad.example/media/photos/438516/00001.webp',
                'https://img-good.example/media/photos/438516/00001.webp',
            ], async_seen)

            async_seen.clear()
            aresp2 = asyncio.run(async_client.get_jm_image('https://img-bad.example/media/photos/438516/00002.webp'))
            self.assertEqual(b'async-webp', aresp2.content)
            self.assertEqual(['https://img-good.example/media/photos/438516/00002.webp'], async_seen)

    def test_register_image_domain_and_setting_integration(self):
        from unittest.mock import AsyncMock, Mock, patch

        orig_list = list(JmModuleConfig.DOMAIN_IMAGE_LIST)
        orig_flag = JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN
        try:
            JmModuleConfig.DOMAIN_IMAGE_LIST = ['cdn-a.example', 'cdn-b.example']
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = True

            # 动态收录去重前置，保留原有兜底域名
            added = JmModuleConfig.register_image_domain('https://cdn-new.example/')
            self.assertEqual('cdn-new.example', added)
            self.assertEqual(['cdn-new.example', 'cdn-a.example', 'cdn-b.example'], JmModuleConfig.DOMAIN_IMAGE_LIST)

            # 已有节点移至首位且不重复膨胀
            JmModuleConfig.register_image_domain('cdn-b.example')
            self.assertEqual(['cdn-b.example', 'cdn-new.example', 'cdn-a.example'], JmModuleConfig.DOMAIN_IMAGE_LIST)

            # http 开头裸域名与 http:// 协议头均正常解析
            self.assertEqual('httpcdn.example.com', JmcomicText.parse_to_jm_domain('httpcdn.example.com/'))
            self.assertEqual('cdn-http.example.com', JmcomicText.parse_to_jm_domain('http://cdn-http.example.com/'))

            # 验证同步与异步 setting() 受 FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN 控制并自动收录 img_host
            JmModuleConfig.DOMAIN_IMAGE_LIST = ['cdn-base.example']

            with patch.object(JmModuleConfig, 'FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN', False), \
                    patch.object(JmModuleConfig, 'FLAG_API_CLIENT_REQUIRE_COOKIES', False):
                sync_api = JmApiClient(SimpleNamespace(), ['api.example'], retry_times=0)
            fake_setting_resp = SimpleNamespace(
                model_data=AdvancedDict({'jm3_version': '2.1.12', 'img_host': 'https://cdn-sync-setting.example'})
            )
            sync_api.req_api = Mock(return_value=fake_setting_resp)
            with patch.object(JmModuleConfig, 'FLAG_USE_VERSION_NEWER_IF_BEHIND', False):
                JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = False
                sync_api.setting()
                self.assertEqual(['cdn-base.example'], JmModuleConfig.DOMAIN_IMAGE_LIST)

                JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = True
                sync_api.setting()
            self.assertEqual('cdn-sync-setting.example', JmModuleConfig.DOMAIN_IMAGE_LIST[0])

            async_api = AsyncJmApiClient(JmOption.default(), domain_list=['api.example'])
            fake_async_resp = SimpleNamespace(
                model_data=AdvancedDict({'jm3_version': '2.1.12', 'img_host': 'https://cdn-async-setting.example'})
            )
            async_api.req_api = AsyncMock(return_value=fake_async_resp)
            with patch.object(JmModuleConfig, 'FLAG_USE_VERSION_NEWER_IF_BEHIND', False):
                asyncio.run(async_api.setting())
            self.assertEqual('cdn-async-setting.example', JmModuleConfig.DOMAIN_IMAGE_LIST[0])
            self.assertIn('cdn-sync-setting.example', JmModuleConfig.DOMAIN_IMAGE_LIST)
        finally:
            JmModuleConfig.DOMAIN_IMAGE_LIST = orig_list
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = orig_flag

    def test_new_postman_normalizes_string_proxies(self):
        expected = ProxyBuilder.build_by_str('127.0.0.1:7890')
        self.assertIsInstance(expected, dict)
        pm = JmModuleConfig.new_postman(proxies='127.0.0.1:7890')
        self.assertEqual(expected, pm.get_meta_data('proxies'))
        spm = JmModuleConfig.new_postman(session=True, proxies='127.0.0.1:7890')
        self.assertEqual(expected, spm.get_meta_data('proxies'))

    def test_system_proxy_preserves_scheme_and_supports_socks(self):
        from unittest.mock import patch

        with patch('urllib.request.getproxies', return_value={}):
            self.assertEqual({}, ProxyBuilder.system_proxy())

        with patch('urllib.request.getproxies', return_value={'http': 'http://127.0.0.1:7890'}):
            self.assertEqual(
                {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'},
                ProxyBuilder.system_proxy(),
            )

        with patch('urllib.request.getproxies', return_value={'https': 'https://proxy.example:8443'}):
            self.assertEqual(
                {'http': 'https://proxy.example:8443', 'https': 'https://proxy.example:8443'},
                ProxyBuilder.system_proxy(),
            )

        with patch('urllib.request.getproxies', return_value={'socks': 'socks5://127.0.0.1:1080'}):
            self.assertEqual(
                {'http': 'socks5://127.0.0.1:1080', 'https': 'socks5://127.0.0.1:1080'},
                ProxyBuilder.system_proxy(),
            )

        with patch('urllib.request.getproxies', return_value={'all': 'socks4://127.0.0.1:1081'}):
            self.assertEqual(
                {'http': 'socks4://127.0.0.1:1081', 'https': 'socks4://127.0.0.1:1081'},
                ProxyBuilder.system_proxy(),
            )
