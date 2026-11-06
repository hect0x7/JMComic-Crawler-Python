from test_jmcomic import *
import asyncio
from types import SimpleNamespace


class Test_RequestRetryAllFailException(unittest.TestCase):

    def test_sync_client_collects_each_failed_request(self):
        client = object.__new__(AbstractJmClient)
        client.domain_list = ['api-one.example', 'api-two.example']
        client.retry_times = 1
        client.domain_retry_strategy = None

        def request(url, **kwargs):
            raise TimeoutError(url)

        with self.assertRaises(RequestRetryAllFailException) as cm:
            client.request_with_retry(request, '/search')

        errors = cm.exception.errors
        self.assertEqual(4, len(errors))
        self.assertEqual(['api-one.example', 'api-two.example',
                          'api-one.example', 'api-two.example'],
                         [item['domain'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], TimeoutError) for item in errors))

    def test_sync_client_sorts_domains_by_fail_count(self):
        client = object.__new__(AbstractJmClient)
        client.domain_list = ['bad.example', 'good.example']
        client.retry_times = 1
        client.domain_retry_strategy = None

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

    def test_sync_and_advanced_retry_do_not_multiply_absolute_image_url_by_domains(self):
        client = object.__new__(AbstractJmClient)
        client.domain_list = ['d1.example', 'd2.example', 'd3.example', 'd4.example']
        client.retry_times = 2
        client.domain_retry_strategy = None

        img_url = 'https://cdn-msp.example/media/photos/123/00001.webp'
        calls = []

        def failing_img_request(url, **kwargs):
            calls.append(url)
            raise ConnectionError(url)

        with self.assertRaises(RequestRetryAllFailException) as cm:
            client.request_with_retry(failing_img_request, img_url, is_image=True)

        self.assertEqual(3, len(calls))
        self.assertEqual(3, len(cm.exception.errors))
        self.assertEqual([None, None, None], [item['domain'] for item in cm.exception.errors])
        self.assertEqual({}, getattr(client, '_domain_fail_count', {}))

        calls.clear()
        plugin = object.__new__(AdvancedRetryPlugin)
        plugin.retry_config = {
            'retry_rounds': 2,
            'retry_domain_max_times': 5,
        }
        plugin(client)

        with self.assertRaises(RequestRetryAllFailException) as plugin_cm:
            plugin(client, failing_img_request, img_url, True)

        self.assertEqual(2, len(calls))
        self.assertEqual([None, None], [item['domain'] for item in plugin_cm.exception.errors])

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

        client = object.__new__(AsyncJmApiClient)
        client._domain_list = ['api-one.example', 'api-two.example']
        client._retry_times = 0
        client._session = FailingSession()
        client._domain_fail_count = {}

        async def request():
            return await client._request_with_retry('/search', {})

        with self.assertRaises(RequestRetryAllFailException) as cm:
            asyncio.run(request())

        errors = cm.exception.errors
        self.assertEqual(2, len(errors))
        self.assertEqual(['api-one.example', 'api-two.example'],
                         [item['domain'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], ConnectionError) for item in errors))

    def test_advanced_retry_collects_each_failed_request(self):
        client = object.__new__(AbstractJmClient)
        client.domain_list = ['api-one.example', 'api-two.example']
        client.retry_times = 1
        client.domain_retry_strategy = None

        plugin = object.__new__(AdvancedRetryPlugin)
        plugin.retry_config = {
            'retry_rounds': 1,
            'retry_domain_max_times': 1,
        }
        plugin(client)

        def request(url, **kwargs):
            raise OSError(url)

        with self.assertRaises(RequestRetryAllFailException) as cm:
            plugin(client, request, '/search', False)

        errors = cm.exception.errors
        self.assertEqual(2, len(errors))
        self.assertEqual(['api-one.example', 'api-two.example'],
                         [item['domain'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], OSError) for item in errors))

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
