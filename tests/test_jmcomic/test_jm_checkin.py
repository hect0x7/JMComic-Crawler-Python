import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from jmcomic import (
    AsyncJmApiClient,
    JmApiClient,
    JmHtmlClient,
)
from jmcomic.jm_exception import JmcomicException


class Test_CheckIn(unittest.TestCase):

    def test_html_client_raises_not_implemented(self):
        client = object.__new__(JmHtmlClient)
        with self.assertRaises(NotImplementedError):
            client.get_daily()
        with self.assertRaises(NotImplementedError):
            client.daily_checkin()

    def test_api_login_records_user_id(self):
        client = object.__new__(JmApiClient)
        client.postman = {}
        resp_obj = SimpleNamespace(
            resp=SimpleNamespace(cookies={'session': '1'}),
            res_data={'uid': 123456, 's': 'token_s'},
        )
        client.req_api = Mock(return_value=resp_obj)

        resp = JmApiClient.login(client, 'user_a', 'pass_b')
        self.assertIs(resp, resp_obj)
        self.assertEqual(client._user_id, '123456')
        self.assertEqual(client._username, 'user_a')

    def test_api_get_daily_without_user_id_raises(self):
        client = object.__new__(JmApiClient)
        client._user_id = None
        with self.assertRaises(JmcomicException):
            JmApiClient.get_daily(client)

    def test_api_get_daily_success(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        daily_resp = SimpleNamespace(res_data={'daily_id': '88', 'signed': False})
        client.req_api = Mock(return_value=daily_resp)

        resp = JmApiClient.get_daily(client)
        self.assertIs(resp, daily_resp)
        client.req_api.assert_called_once_with(
            client.API_DAILY,
            params={'user_id': '123456'},
        )

    def test_api_check_in_with_explicit_daily_id(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        chk_resp = SimpleNamespace(res_data={'status': 'ok', 'msg': '签到成功'})
        client.req_api = Mock(return_value=chk_resp)

        resp = JmApiClient.daily_checkin(client, daily_id='999')
        self.assertIs(resp, chk_resp)
        client.req_api.assert_called_once_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '123456', 'daily_id': '999'},
        )

    def test_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'

        def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return SimpleNamespace(res_data={'daily_id': '88', 'signed': False})
            if url == client.API_DAILY_CHK:
                return SimpleNamespace(res_data={'status': 'ok', 'msg': '打卡成功'})
            raise AssertionError(f'unexpected url: {url}')

        client.req_api = Mock(side_effect=mock_req)

        resp = JmApiClient.daily_checkin(client)
        self.assertEqual(resp.res_data['status'], 'ok')
        self.assertEqual(client.req_api.call_count, 2)
        client.req_api.assert_called_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '123456', 'daily_id': '88'},
        )

    def test_api_check_in_missing_daily_id_raises(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        daily_resp = SimpleNamespace(res_data={}, text='{}')
        client.req_api = Mock(return_value=daily_resp)

        with self.assertRaises(JmcomicException):
            JmApiClient.daily_checkin(client)

    def test_async_api_login_records_user_id(self):
        client = object.__new__(AsyncJmApiClient)
        client._session = SimpleNamespace(cookies=SimpleNamespace(update=Mock()))
        client.option = SimpleNamespace(update_cookies=Mock())
        resp_obj = SimpleNamespace(
            resp=SimpleNamespace(cookies={'session': '1'}),
            res_data={'uid': 654321, 's': 'token_s'},
        )
        client.req_api = AsyncMock(return_value=resp_obj)

        resp = asyncio.run(AsyncJmApiClient.login(client, 'async_user', 'async_pass'))
        self.assertIs(resp, resp_obj)
        self.assertEqual(client._user_id, '654321')
        self.assertEqual(client._username, 'async_user')

    def test_async_api_get_daily_success(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        daily_resp = SimpleNamespace(res_data={'daily_id': '77', 'signed': True})
        client.req_api = AsyncMock(return_value=daily_resp)

        resp = asyncio.run(AsyncJmApiClient.get_daily(client))
        self.assertIs(resp, daily_resp)
        client.req_api.assert_awaited_once_with(
            client.API_DAILY,
            params={'user_id': '654321'},
        )

    def test_async_api_check_in_with_explicit_daily_id(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        chk_resp = SimpleNamespace(res_data={'status': 'ok', 'msg': '签到完成'})
        client.req_api = AsyncMock(return_value=chk_resp)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))
        self.assertIs(resp, chk_resp)
        client.req_api.assert_awaited_once_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '654321', 'daily_id': '77'},
        )

    def test_async_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'

        async def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return SimpleNamespace(res_data={'daily_id': '99', 'signed': False})
            if url == client.API_DAILY_CHK:
                return SimpleNamespace(res_data={'status': 'ok', 'msg': '签到完成'})
            raise AssertionError(f'unexpected url: {url}')

        client.req_api = AsyncMock(side_effect=mock_req)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client))
        self.assertEqual(resp.res_data['status'], 'ok')
        self.assertEqual(client.req_api.await_count, 2)
        client.req_api.assert_awaited_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '654321', 'daily_id': '99'},
        )
