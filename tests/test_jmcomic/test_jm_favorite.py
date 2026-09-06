import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from jmcomic import AsyncJmApiClient, JmApiClient


class Test_Favorite(unittest.TestCase):

    def test_api_add_favorite_album_uses_post(self):
        client = object.__new__(JmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok'))
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

    def test_async_api_add_favorite_album_uses_post(self):
        client = object.__new__(AsyncJmApiClient)
        response = SimpleNamespace(model_data=SimpleNamespace(status='ok'))
        client.req_api = AsyncMock(return_value=response)

        result = asyncio.run(AsyncJmApiClient.add_favorite_album(client, 21))

        self.assertIs(result, response)
        client.req_api.assert_awaited_once_with(
            client.API_FAVORITE,
            get=False,
            data={'aid': 21},
        )
