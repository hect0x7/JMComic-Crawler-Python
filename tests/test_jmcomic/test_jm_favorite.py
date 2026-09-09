import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from jmcomic import AsyncJmApiClient, JmApiClient, JmHtmlClient


class Test_Favorite(unittest.TestCase):

    def test_html_delete_favorite_album_uses_ajax_form_post(self):
        client = object.__new__(JmHtmlClient)
        response = SimpleNamespace(
            status_code=200,
            url='https://example.com/ajax/delete_favorite_album',
            redirect_count=0,
            text='{"status": 1, "msg": "<div class=\\"alert\\"><button>×</button>漫畫刪除成功</div>"}',
            json=lambda: {'status': 1, 'msg': '<div class="alert"><button>×</button>漫畫刪除成功</div>'},
        )
        client.post = Mock(return_value=response)

        result = JmHtmlClient.delete_favorite_album(client, 21)

        self.assertIs(result, response)
        client.post.assert_called_once_with(
            '/ajax/delete_favorite_album',
            data={
                'album_id': '21',
            },
        )

    def test_api_add_favorite_album_uses_post(self):
        client = object.__new__(JmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok', type='add', msg='ok'))
        client.req_api = Mock(return_value=response)
        client.require_resp_status_ok = Mock()

        result = JmApiClient.add_favorite_album(client, 21)

        self.assertIs(result, response)
        client.req_api.assert_called_once_with(
            client.API_FAVORITE,
            get=False,
            data={'aid': 21},
        )
        client.require_resp_status_ok.assert_called_once_with(response)

    def test_api_delete_favorite_album_uses_post(self):
        client = object.__new__(JmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok', type='remove', msg='ok'))
        client.req_api = Mock(return_value=response)
        client.require_resp_status_ok = Mock()

        result = JmApiClient.delete_favorite_album(client, 21)

        self.assertIs(result, response)
        client.req_api.assert_called_once_with(
            client.API_FAVORITE,
            get=False,
            data={'aid': 21},
        )
        client.require_resp_status_ok.assert_called_once_with(response)

    def test_api_favorite_album_raises_on_unexpected_type(self):
        client = object.__new__(JmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok', type='remove', msg='已移除收藏'))
        client.req_api = Mock(return_value=response)
        client.require_resp_status_ok = Mock()

        with self.assertRaises(Exception):
            JmApiClient.add_favorite_album(client, 21)

    def test_async_api_add_favorite_album_uses_post(self):
        client = object.__new__(AsyncJmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok', type='add', msg='ok'))
        client.req_api = AsyncMock(return_value=response)

        result = asyncio.run(AsyncJmApiClient.add_favorite_album(client, 21))

        self.assertIs(result, response)
        client.req_api.assert_awaited_once_with(
            client.API_FAVORITE,
            get=False,
            data={'aid': 21},
        )

    def test_async_api_delete_favorite_album_uses_post(self):
        client = object.__new__(AsyncJmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok', type='remove', msg='ok'))
        client.req_api = AsyncMock(return_value=response)

        result = asyncio.run(AsyncJmApiClient.delete_favorite_album(client, 21))

        self.assertIs(result, response)
        client.req_api.assert_awaited_once_with(
            client.API_FAVORITE,
            get=False,
            data={'aid': 21},
        )


    def test_html_delete_favorite_album_raises_on_failure(self):
        client = object.__new__(JmHtmlClient)
        response = SimpleNamespace(
            status_code=200,
            url='https://example.com/ajax/delete_favorite_album',
            redirect_count=0,
            text='{"status": 0, "msg": "failed"}',
            json=lambda: {'status': 0, 'msg': 'failed'},
        )
        client.post = Mock(return_value=response)
        client.raise_request_error = Mock(side_effect=Exception('failed'))

        with self.assertRaises(Exception):
            JmHtmlClient.delete_favorite_album(client, 21)


