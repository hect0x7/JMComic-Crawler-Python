import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from jmcomic import (
    AsyncJmApiClient,
    JmApiClient,
    JmHtmlClient,
    JmcomicText,
    JmDailyCheckinResp,
)
from jmcomic.jm_exception import JmcomicException


class Test_CheckIn(unittest.TestCase):

    def test_html_client_get_daily(self):
        client = object.__new__(JmHtmlClient)
        client.get_jm_html = Mock(return_value=SimpleNamespace(
            text='<div id="bouns-popup" data-dailyid="99">'
        ))
        text = '{"dateArray": [5], "oldStep": 1}'
        mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
        mock_raw_resp.json = Mock(return_value={"dateArray": [5], "oldStep": 1})
        client.get = Mock(return_value=mock_raw_resp)

        resp = JmHtmlClient.get_daily(client)
        client.get_jm_html.assert_called_once_with('/')
        client.get.assert_called_once_with(
            '/ajax/user_daily_event',
            params={'daily_id': '99'},
        )
        self.assertEqual(resp.json()['dateArray'], [5])
        self.assertEqual(resp.model().oldStep, 1)

    def test_html_client_daily_checkin_success(self):
        client = object.__new__(JmHtmlClient)
        text = '{"status": 1, "msg": "打卡成功！獲得經驗: 50 金幣: 50"}'
        mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
        mock_raw_resp.json = Mock(return_value={"status": 1, "msg": "打卡成功！獲得經驗: 50 金幣: 50"})
        client.post = Mock(return_value=mock_raw_resp)

        resp = JmHtmlClient.daily_checkin(client, daily_id='72', old_step=2)
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.msg, '打卡成功！獲得經驗: 50 金幣: 50')
        client.post.assert_called_once_with(
            '/ajax/user_daily_sign',
            data={'daily_id': '72', 'oldStep': '2'},
        )

    def test_html_client_daily_checkin_already_checked_in(self):
        client = object.__new__(JmHtmlClient)
        text = '{"status": 0, "msg": "您今日已完成打卡"}'
        mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
        mock_raw_resp.json = Mock(return_value={"status": 0, "msg": "您今日已完成打卡"})
        client.post = Mock(return_value=mock_raw_resp)

        resp = JmHtmlClient.daily_checkin(client, daily_id='72')
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
        self.assertEqual(resp.status, 1)
        self.assertEqual(resp.msg, '您今日已完成打卡')

    def test_html_client_daily_checkin_other_status_raises(self):
        client = object.__new__(JmHtmlClient)
        text = '{"status": 0, "msg": "请先登录"}'
        mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
        mock_raw_resp.json = Mock(return_value={"status": 0, "msg": "请先登录"})
        client.post = Mock(return_value=mock_raw_resp)
        client.raise_request_error = Mock(side_effect=JmcomicException('请先登录', {}))

        with self.assertRaises(JmcomicException):
            JmHtmlClient.daily_checkin(client, daily_id='72')

    def test_html_client_daily_checkin_http_error_raises(self):
        client = object.__new__(JmHtmlClient)
        mock_raw_resp = Mock(status_code=500, text='Server Error', content=b'Server Error')
        client.post = Mock(return_value=mock_raw_resp)
        client.raise_request_error = Mock(side_effect=JmcomicException('HTTP 500', {}))

        with self.assertRaises(JmcomicException):
            JmHtmlClient.daily_checkin(client, daily_id='72')

    def test_html_client_daily_checkin_auto_fetch_daily_id(self):
        client = object.__new__(JmHtmlClient)
        client.get_jm_html = Mock(return_value=SimpleNamespace(
            text='<div id="bouns-popup" data-dailyid="88">'
        ))
        text = '{"status": 1, "msg": "打卡成功"}'
        mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
        mock_raw_resp.json = Mock(return_value={"status": 1, "msg": "打卡成功"})
        client.post = Mock(return_value=mock_raw_resp)

        resp = JmHtmlClient.daily_checkin(client)
        client.get_jm_html.assert_called_once_with('/')
        client.post.assert_called_once_with(
            '/ajax/user_daily_sign',
            data={'daily_id': '88', 'oldStep': '1'},
        )
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.msg, '打卡成功')

    def test_html_client_daily_checkin_missing_daily_id_raises(self):
        client = object.__new__(JmHtmlClient)
        client.get_jm_html = Mock(return_value=SimpleNamespace(text='<html>no daily id</html>'))
        with self.assertRaises(JmcomicException):
            JmHtmlClient.daily_checkin(client)

    def test_parse_daily_id(self):
        html = '<div id="bouns-popup" class="modal fade" data-dailyid="72" tabindex="-1">'
        self.assertEqual(JmcomicText.parse_daily_id(html), '72')
        self.assertEqual(JmcomicText.parse_html_daily_id(html), '72')
        self.assertIsNone(JmcomicText.parse_daily_id('<html>no daily id</html>'))
        self.assertEqual(JmcomicText.parse_daily_id('<html>no daily id</html>', default='default_id'), 'default_id')


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

    def test_api_check_in_success(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        chk_resp = SimpleNamespace(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
        client.req_api = Mock(return_value=chk_resp)

        resp = JmApiClient.daily_checkin(client, daily_id='999')
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.msg, 'Jcoin:100 EXP:50')
        client.req_api.assert_called_once_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '123456', 'daily_id': '999'},
        )

    def test_api_check_in_already_checked_in(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        chk_resp = SimpleNamespace(res_data={'msg': '今天已經簽到過了'})
        client.req_api = Mock(return_value=chk_resp)

        resp = JmApiClient.daily_checkin(client, daily_id='999')
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
        self.assertEqual(resp.status, 1)
        self.assertEqual(resp.msg, '今天已經簽到過了')

    def test_api_check_in_unexpected_msg_raises(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        chk_resp = SimpleNamespace(res_data={'msg': '账号异常'})
        client.req_api = Mock(return_value=chk_resp)

        with self.assertRaises(JmcomicException):
            JmApiClient.daily_checkin(client, daily_id='999')

    def test_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'

        def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return SimpleNamespace(res_data={'daily_id': '88', 'signed': False})
            if url == client.API_DAILY_CHK:
                return SimpleNamespace(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
            raise AssertionError(f'unexpected url: {url}')

        client.req_api = Mock(side_effect=mock_req)

        resp = JmApiClient.daily_checkin(client)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.msg, 'Jcoin:100 EXP:50')
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

        with self.assertRaises(KeyError):
            JmApiClient.daily_checkin(client)

    def test_api_check_in_without_user_id_raises(self):
        client = object.__new__(JmApiClient)
        client._user_id = None
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

    def test_async_api_check_in_success(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        chk_resp = SimpleNamespace(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
        client.req_api = AsyncMock(return_value=chk_resp)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.msg, 'Jcoin:100 EXP:50')
        client.req_api.assert_awaited_once_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '654321', 'daily_id': '77'},
        )

    def test_async_api_check_in_already_checked_in(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        chk_resp = SimpleNamespace(res_data={'msg': '今天已經簽到過了'})
        client.req_api = AsyncMock(return_value=chk_resp)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))
        self.assertIsInstance(resp, JmDailyCheckinResp)
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
        self.assertEqual(resp.status, 1)
        self.assertEqual(resp.msg, '今天已經簽到過了')

    def test_async_api_check_in_unexpected_msg_raises(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        chk_resp = SimpleNamespace(res_data={'msg': '系统异常'})
        client.req_api = AsyncMock(return_value=chk_resp)

        with self.assertRaises(JmcomicException):
            asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))

    def test_async_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'

        async def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return SimpleNamespace(res_data={'daily_id': '99', 'signed': False})
            if url == client.API_DAILY_CHK:
                return SimpleNamespace(res_data={'status': 'ok', 'msg': 'Jcoin:40 EXP:40'})
            raise AssertionError(f'unexpected url: {url}')

        client.req_api = AsyncMock(side_effect=mock_req)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client))
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_SUCCESS)
        self.assertEqual(resp.msg, 'Jcoin:40 EXP:40')
        self.assertEqual(client.req_api.await_count, 2)
        client.req_api.assert_awaited_with(
            client.API_DAILY_CHK,
            get=False,
            data={'user_id': '654321', 'daily_id': '99'},
        )

    def test_async_api_check_in_missing_daily_id_raises(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        daily_resp = SimpleNamespace(res_data={}, text='{}')
        client.req_api = AsyncMock(return_value=daily_resp)

        with self.assertRaises(KeyError):
            asyncio.run(AsyncJmApiClient.daily_checkin(client))

    def test_async_api_check_in_without_user_id_raises(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = None
        with self.assertRaises(JmcomicException):
            asyncio.run(AsyncJmApiClient.daily_checkin(client))
