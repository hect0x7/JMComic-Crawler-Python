import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from jmcomic import (
    AsyncJmApiClient,
    JmApiClient,
    JmApiResp,
    JmHtmlClient,
    JmModuleConfig,
    JmUserClient,
    JmcomicText,
    JmDailyCheckinResp,
)
from jmcomic.jm_exception import JmcomicException


class _CheckinApiResp(JmApiResp):
    """保留真实响应继承链，仅替换与本测试无关的解密数据。"""

    def __init__(self, res_data):
        super().__init__(
            SimpleNamespace(status_code=200, content=b'{"code": 200, "data": "1"}', text='{"code": 200, "data": "1"}'),
            '0')
        self._data = res_data

    @property
    def res_data(self):
        return self._data


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
        for payload in (
            {"status": 0, "msg": "您今日已完成打卡"},
            {"msg": "", "error": "finished"},
        ):
            with self.subTest(payload=payload):
                client = object.__new__(JmHtmlClient)
                text = str(payload)
                mock_raw_resp = Mock(status_code=200, text=text, content=text.encode('utf-8'))
                mock_raw_resp.json = Mock(return_value=payload)
                client.post = Mock(return_value=mock_raw_resp)

                resp = JmHtmlClient.daily_checkin(client, daily_id='72')
                self.assertIsInstance(resp, JmDailyCheckinResp)
                self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
                self.assertEqual(resp.status, 1)

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
        daily_resp = _CheckinApiResp(res_data={'daily_id': '88', 'signed': False})
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
        chk_resp = _CheckinApiResp(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
        client.req_api = Mock(return_value=chk_resp)

        resp = JmApiClient.daily_checkin(client, daily_id='999')
        self.assertIs(resp.resp, chk_resp.resp)
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
        for msg_text in ('今天已經簽到過了', '今天已经签到过了'):
            with self.subTest(msg=msg_text):
                client = object.__new__(JmApiClient)
                client._user_id = '123456'
                chk_resp = _CheckinApiResp(res_data={'msg': msg_text})
                client.req_api = Mock(return_value=chk_resp)

                resp = JmApiClient.daily_checkin(client, daily_id='999')
                self.assertIs(resp.resp, chk_resp.resp)
                self.assertIsInstance(resp, JmDailyCheckinResp)
                self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
                self.assertEqual(resp.status, 1)
                self.assertEqual(resp.msg, msg_text)

    def test_api_check_in_unexpected_msg_raises(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        chk_resp = _CheckinApiResp(res_data={'msg': '账号异常'})
        client.req_api = Mock(return_value=chk_resp)

        with self.assertRaises(JmcomicException):
            JmApiClient.daily_checkin(client, daily_id='999')

    def test_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(JmApiClient)
        client._user_id = '123456'

        def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return _CheckinApiResp(res_data={'daily_id': '88', 'signed': False})
            if url == client.API_DAILY_CHK:
                return _CheckinApiResp(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
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
        daily_resp = _CheckinApiResp(res_data={})
        client.req_api = Mock(return_value=daily_resp)

        with self.assertRaisesRegex(JmcomicException, '签到信息缺少 daily_id'):
            JmApiClient.daily_checkin(client)
        client.req_api.assert_called_once_with(client.API_DAILY, params={'user_id': '123456'})

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
        daily_resp = _CheckinApiResp(res_data={'daily_id': '77', 'signed': True})
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
        chk_resp = _CheckinApiResp(res_data={'status': 'ok', 'msg': 'Jcoin:100 EXP:50'})
        client.req_api = AsyncMock(return_value=chk_resp)

        resp = asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))
        self.assertIs(resp.resp, chk_resp.resp)
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
        for msg_text in ('今天已經簽到過了', '今天已经签到过了'):
            with self.subTest(msg=msg_text):
                client = object.__new__(AsyncJmApiClient)
                client._user_id = '654321'
                chk_resp = _CheckinApiResp(res_data={'msg': msg_text})
                client.req_api = AsyncMock(return_value=chk_resp)

                resp = asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))
                self.assertIs(resp.resp, chk_resp.resp)
                self.assertIsInstance(resp, JmDailyCheckinResp)
                self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)
                self.assertEqual(resp.status, 1)
                self.assertEqual(resp.msg, msg_text)

    def test_api_favorite_mismatch_rolls_back(self):
        client = object.__new__(JmApiClient)
        mismatch_resp = _CheckinApiResp(res_data={'status': 'ok', 'type': 'remove', 'msg': '已取消收藏'})
        rollback_resp = _CheckinApiResp(res_data={'status': 'ok', 'type': 'add', 'msg': '已加入收藏'})
        client.req_api = Mock(side_effect=[mismatch_resp, rollback_resp])

        with self.assertRaisesRegex(JmcomicException, '已自动回滚还原收藏状态'):
            JmApiClient.add_favorite_album(client, '12345')

        self.assertEqual(client.req_api.call_count, 2)

        # rollback_when_mismatch=False 时不触发二次回滚请求
        client.req_api = Mock(return_value=mismatch_resp)
        with self.assertRaisesRegex(JmcomicException, '收藏操作不符合预期'):
            JmApiClient.add_favorite_album(client, '12345', rollback_when_mismatch=False)
        self.assertEqual(client.req_api.call_count, 1)

        # 回滚响应本身 status != 'ok' 或 type 未反转时，异常信息包含回滚失败详情
        bad_rollback_resp = _CheckinApiResp(res_data={'status': 'ok', 'type': 'remove', 'msg': '仍为移除'})
        client.req_api = Mock(side_effect=[mismatch_resp, bad_rollback_resp])
        with self.assertRaisesRegex(JmcomicException, '且自动回滚失败'):
            JmApiClient.add_favorite_album(client, '12345')

    def test_async_api_favorite_mismatch_rolls_back(self):
        client = object.__new__(AsyncJmApiClient)
        mismatch_resp = _CheckinApiResp(res_data={'status': 'ok', 'type': 'remove', 'msg': '已取消收藏'})
        rollback_resp = _CheckinApiResp(res_data={'status': 'ok', 'type': 'add', 'msg': '已加入收藏'})
        client.req_api = AsyncMock(side_effect=[mismatch_resp, rollback_resp])

        with self.assertRaisesRegex(JmcomicException, '已自动回滚还原收藏状态'):
            asyncio.run(AsyncJmApiClient.add_favorite_album(client, '12345'))

        self.assertEqual(client.req_api.await_count, 2)

        # rollback_when_mismatch=False 时不触发二次回滚请求
        client.req_api = AsyncMock(return_value=mismatch_resp)
        with self.assertRaisesRegex(JmcomicException, '收藏操作不符合预期'):
            asyncio.run(AsyncJmApiClient.add_favorite_album(client, '12345', rollback_when_mismatch=False))
        self.assertEqual(client.req_api.await_count, 1)

        # 回滚响应本身 status != 'ok' 或 type 未反转时，异常信息包含回滚失败详情
        bad_rollback_resp = _CheckinApiResp(res_data={'status': 'error', 'type': '', 'msg': '服务异常'})
        client.req_api = AsyncMock(side_effect=[mismatch_resp, bad_rollback_resp])
        with self.assertRaisesRegex(JmcomicException, '且自动回滚失败'):
            asyncio.run(AsyncJmApiClient.add_favorite_album(client, '12345'))

    def test_custom_daily_already_checked_in_keywords(self):
        self.assertIs(JmApiClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS, JmUserClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS)
        self.assertIs(JmHtmlClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS, JmUserClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS)
        self.assertIs(AsyncJmApiClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS,
                      JmUserClient.DAILY_ALREADY_CHECKED_IN_KEYWORDS)

        client = object.__new__(JmApiClient)
        client._user_id = '123456'
        client.DAILY_ALREADY_CHECKED_IN_KEYWORDS = ('自定义已打卡文案',)
        chk_resp = _CheckinApiResp(res_data={'msg': '提示：自定义已打卡文案！'})
        client.req_api = Mock(return_value=chk_resp)

        resp = JmApiClient.daily_checkin(client, daily_id='999')
        self.assertEqual(resp.code, JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN)

    @staticmethod
    def _build_album_api_data(album_id: int, series_id: str, name: str, author=None, tags=None, series=None):
        return {
            'id': album_id,
            'name': name,
            'author': author if author is not None else ['作者A'],
            'images': ['00001.webp'],
            'description': 'desc',
            'total_views': '100',
            'total_photos': 10,
            'addtime': '1700000000',
            'likes': '10',
            'series': series if series is not None else [],
            'series_id': series_id,
            'comment_total': '2',
            'tags': tags if tags is not None else ['标签1'],
            'works': [],
            'actors': [],
            'related_list': [],
            'liked': False,
            'is_favorite': False,
        }

    def test_api_fetch_album_redirects_when_given_chapter_id(self):
        client = object.__new__(JmApiClient)
        series_list = [
            {'id': '1228973', 'name': '第1话', 'sort': '1'},
            {'id': '1236387', 'name': '第2话', 'sort': '2'},
        ]
        chapter_as_album = _CheckinApiResp(res_data=self._build_album_api_data(
            album_id=1236387,
            series_id='1228973',
            name='恰如舌咬 2',
            author=[],
            tags=[],
            series=series_list,
        ))
        parent_album = _CheckinApiResp(res_data=self._build_album_api_data(
            album_id=1228973,
            series_id='1228973',
            name='恰如舌咬',
            author=['博'],
            tags=['青年漫', '劇情向'],
            series=series_list,
        ))
        single_album = _CheckinApiResp(res_data=self._build_album_api_data(
            album_id=438516,
            series_id='0',
            name='单章本子',
        ))

        def mock_req(url, **kwargs):
            if 'id=1236387' in url:
                return chapter_as_album
            if 'id=1228973' in url:
                return parent_album
            if 'id=438516' in url:
                return single_album
            raise AssertionError(f'unexpected url: {url}')

        client.req_api = Mock(side_effect=mock_req)

        logs = []
        orig_log = JmModuleConfig.EXECUTOR_LOG
        orig_flag = JmModuleConfig.FLAG_ENABLE_JM_LOG
        JmModuleConfig.FLAG_ENABLE_JM_LOG = True
        JmModuleConfig.EXECUTOR_LOG = lambda topic, msg: logs.append((topic, msg))
        try:
            # 1. 子章节 ID -> 自动重定向到父本子 ID 并打印日志
            album = JmApiClient.get_album_detail(client, '1236387')
            self.assertEqual(album.album_id, '1228973')
            self.assertEqual(album.name, '恰如舌咬')
            self.assertEqual(album.authors, ['博'])
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0][0], 'api.album_redirect')
            self.assertIn('1236387', logs[0][1])
            self.assertIn('1228973', logs[0][1])

            # 2. 多章父本子 ID (series_id == id) -> 不触发重定向
            logs.clear()
            album_parent = JmApiClient.get_album_detail(client, '1228973')
            self.assertEqual(album_parent.album_id, '1228973')
            self.assertEqual(len(logs), 0)

            # 3. 单章本子 ID (series_id == '0') -> 不触发重定向
            album_single = JmApiClient.get_album_detail(client, '438516')
            self.assertEqual(album_single.album_id, '438516')
            self.assertEqual(len(logs), 0)

            # 4. allow_redirect=False -> 不触发重定向，保留章节原始返回及 series_id
            album_no_redirect = JmApiClient.get_album_detail(client, '1236387', allow_redirect=False)
            self.assertEqual(album_no_redirect.album_id, '1236387')
            self.assertEqual(album_no_redirect.series_id, '1228973')
            self.assertEqual(len(logs), 0)
        finally:
            JmModuleConfig.EXECUTOR_LOG = orig_log
            JmModuleConfig.FLAG_ENABLE_JM_LOG = orig_flag

    def test_async_api_fetch_album_redirects_and_caches(self):
        client = object.__new__(AsyncJmApiClient)
        client._cache = {}
        series_list = [
            {'id': '43164', 'name': '1', 'sort': '1'},
            {'id': '275013', 'name': '90', 'sort': '31'},
        ]
        chapter_as_album = _CheckinApiResp(res_data=self._build_album_api_data(
            album_id=275013,
            series_id='43164',
            name='奈奈与薰的SM日记_第90话.zip',
            author=['filename'],
            tags=['filename'],
            series=series_list,
        ))
        parent_album = _CheckinApiResp(res_data=self._build_album_api_data(
            album_id=43164,
            series_id='43164',
            name='奈奈与薰的SM日记',
            author=['甘詰留太'],
            tags=['青年漫'],
            series=series_list,
        ))

        async def mock_req(url, params=None, **kwargs):
            aid = str((params or {}).get('id'))
            if aid == '275013':
                return chapter_as_album
            if aid == '43164':
                return parent_album
            raise AssertionError(f'unexpected params: {params}')

        client.req_api = AsyncMock(side_effect=mock_req)

        logs = []
        orig_log = JmModuleConfig.EXECUTOR_LOG
        orig_flag = JmModuleConfig.FLAG_ENABLE_JM_LOG
        JmModuleConfig.FLAG_ENABLE_JM_LOG = True
        JmModuleConfig.EXECUTOR_LOG = lambda topic, msg: logs.append((topic, msg))
        try:
            album = asyncio.run(AsyncJmApiClient.get_album_detail(client, '275013'))
            self.assertEqual(album.album_id, '43164')
            self.assertEqual(album.authors, ['甘詰留太'])
            self.assertEqual(client.req_api.await_count, 2)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0][0], 'api.album_redirect')

            # 再次请求子章节 ID 或父本子 ID 均直接命中缓存，不再发网络请求
            album_cached_1 = asyncio.run(AsyncJmApiClient.get_album_detail(client, '275013'))
            album_cached_2 = asyncio.run(AsyncJmApiClient.get_album_detail(client, '43164'))
            self.assertEqual(album_cached_1.album_id, '43164')
            self.assertEqual(album_cached_2.album_id, '43164')
            self.assertEqual(client.req_api.await_count, 2)

            # allow_redirect=False 时直接返回子章节对应实体，不重定向
            logs.clear()
            album_no_redirect = asyncio.run(AsyncJmApiClient.get_album_detail(client, '275013', allow_redirect=False))
            self.assertEqual(album_no_redirect.album_id, '275013')
            self.assertEqual(album_no_redirect.series_id, '43164')
            self.assertEqual(len(logs), 0)
        finally:
            JmModuleConfig.EXECUTOR_LOG = orig_log
            JmModuleConfig.FLAG_ENABLE_JM_LOG = orig_flag

    def test_async_api_check_in_unexpected_msg_raises(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'
        chk_resp = _CheckinApiResp(res_data={'msg': '系统异常'})
        client.req_api = AsyncMock(return_value=chk_resp)

        with self.assertRaises(JmcomicException):
            asyncio.run(AsyncJmApiClient.daily_checkin(client, daily_id='77'))

    def test_async_api_check_in_auto_fetch_daily_id(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = '654321'

        async def mock_req(url, get=True, **kwargs):
            if url == client.API_DAILY:
                return _CheckinApiResp(res_data={'daily_id': '99', 'signed': False})
            if url == client.API_DAILY_CHK:
                return _CheckinApiResp(res_data={'status': 'ok', 'msg': 'Jcoin:40 EXP:40'})
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
        daily_resp = _CheckinApiResp(res_data={})
        client.req_api = AsyncMock(return_value=daily_resp)

        with self.assertRaisesRegex(JmcomicException, '签到信息缺少 daily_id'):
            asyncio.run(AsyncJmApiClient.daily_checkin(client))
        client.req_api.assert_awaited_once_with(client.API_DAILY, params={'user_id': '654321'})

    def test_async_api_check_in_without_user_id_raises(self):
        client = object.__new__(AsyncJmApiClient)
        client._user_id = None
        with self.assertRaises(JmcomicException):
            asyncio.run(AsyncJmApiClient.daily_checkin(client))
