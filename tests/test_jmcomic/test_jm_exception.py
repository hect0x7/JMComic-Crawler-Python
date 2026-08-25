from test_jmcomic import *
import asyncio


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
        self.assertEqual(['api-one.example', 'api-one.example',
                          'api-two.example', 'api-two.example'],
                         [item['domain'] for item in errors])
        self.assertTrue(all(isinstance(item['error'], TimeoutError) for item in errors))

    def test_async_client_collects_each_failed_request(self):
        class FailingSession:
            async def get(self, url, **kwargs):
                raise ConnectionError(url)

        client = object.__new__(AsyncJmApiClient)
        client._domain_list = ['api-one.example', 'api-two.example']
        client._retry_times = 0
        client._session = FailingSession()

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
