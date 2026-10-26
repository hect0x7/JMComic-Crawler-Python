"""
异步 jmcomic 客户端模块

对标同步端的 jm_client_impl.py，统一提供：
- AbstractAsyncJmClient：异步客户端公共抽象基类
- AsyncJmHtmlClient：禁漫网页端异步客户端
- AsyncJmApiClient：禁漫移动端异步 API 客户端
"""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from functools import wraps
from typing import Sequence
from urllib.parse import urlencode

from curl_cffi import requests as curl_requests
from curl_cffi.requests import AsyncSession

from .jm_client_impl import JmHtmlClient
from .jm_client_interface import (
    JmResp, JmJsonResp, JmApiResp, JmImageResp,
    JmAlbumCommentResp, JmDailyCheckinResp, AsyncJmcomicClient,
)
from .jm_entity import (
    DetailEntity, JmAlbumDetail, JmPhotoDetail, JmSearchPage, JmCategoryPage,
    JmFavoritePage, DetailType, JmAlbumCommentPage,
)
from .jm_config import JmModuleConfig, JmMagicConstants, time_stamp, jm_log
from .jm_toolkit import (
    JmcomicText, JmCryptoTool, JmApiAdaptTool, JmPageTool,
    ExceptionTool, PatternTool, parse_unicode_escape_text,
)
from .jm_exception import JmcomicException, RequestRetryAllFailException
from .jm_option import JmOption


class AbstractAsyncJmClient(AsyncJmcomicClient):
    """
    异步客户端公共抽象基类，对标同步端的 AbstractJmClient。
    """

    client_key = '__just_for_placeholder_do_not_use_me__'
    domain_config_key: str = ''
    func_to_cache: list[str] = []
    option: JmOption | None = None
    _username: str | None = None
    _user_id: str | None = None
    _setup_lock: asyncio.Lock | None = None
    _setup_lock_loop: asyncio.AbstractEventLoop | None = None

    @staticmethod
    def _wrap_cache_method(func):
        @wraps(func)
        async def cache_wrapper(self, *args, **kwds):
            cache = self._cache
            if cache is None:
                return await func(self, *args, **kwds)

            key = (args, tuple(kwds.items())) if kwds else args
            sentinel = object()
            result = cache.get(key, sentinel)
            if result is not sentinel:
                return deepcopy(result) if isinstance(result, DetailEntity) else result

            result = await func(self, *args, **kwds)
            cache[key] = deepcopy(result) if isinstance(result, DetailEntity) else result
            return result

        return cache_wrapper

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._setup_lock = None
        cls._setup_lock_loop = None
        for func_name in cls.func_to_cache:
            func = cls.__dict__.get(func_name)
            if func is not None:
                setattr(cls, func_name, cls._wrap_cache_method(func))

    def __init__(self, option: JmOption, max_clients=None, domain_list=None, **kwargs):
        if 'domain_retry_strategy' in kwargs:
            raise TypeError('Async client does not support domain_retry_strategy')

        self.option = option
        self.meta_data: dict = deepcopy(option.client.postman.meta_data.src_dict)
        if kwargs:
            self.meta_data.update(kwargs)
        merged_cookies = option.resolve_auth_cookies(kwargs.get('cookies'))
        if merged_cookies is not None:
            self.meta_data['cookies'] = merged_cookies
        self._domain_list = self._resolve_domain_list(domain_list)
        self._retry_times = option.client.retry_times if option.client.retry_times is not None else 5
        self._timeout = option.client.get('timeout', 30) or 30
        if max_clients:
            self._max_clients_hint = int(max_clients)
        else:
            self._max_clients_hint = int(option.download.threading.image or 10)

        self._session: AsyncSession | None = None
        self._session_lock: asyncio.Lock | None = None
        self._session_lock_loop: asyncio.AbstractEventLoop | None = None
        self._cache: dict | None = None
        self._domain_fail_count: dict[str, int] = {}
        self._username: str | None = option.auth.username if option.auth else None
        self._user_id: str | None = option.auth.user_id if option.auth else None
        self._has_setup = False

    @classmethod
    def _get_setup_lock(cls) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if cls._setup_lock is None or cls._setup_lock_loop is not loop:
            cls._setup_lock = asyncio.Lock()
            cls._setup_lock_loop = loop
        return cls._setup_lock

    def _get_session_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._session_lock is None or self._session_lock_loop is not loop:
            self._session_lock = asyncio.Lock()
            self._session_lock_loop = loop
        return self._session_lock

    # ======================================================================
    # 域名管理
    # ======================================================================

    @staticmethod
    def _normalize_domain_list(domain_list) -> list[str]:
        if isinstance(domain_list, str):
            return [domain.strip() for domain in domain_list.splitlines() if domain.strip()]

        if isinstance(domain_list, Sequence):
            result = []
            for domain in domain_list:
                if not isinstance(domain, str):
                    raise TypeError(f'domain must be str, got {type(domain)}')
                domain = domain.strip()
                if domain:
                    result.append(domain)
            return result

        raise TypeError('domain_list must be str, Sequence[str], or None')

    def _default_domain_list(self) -> list[str]:
        raise NotImplementedError

    def _resolve_domain_list(self, domain_list=None) -> list[str]:
        if domain_list is None:
            domain = self.option.client.domain
            domain_list = domain.get(self.domain_config_key, []) if hasattr(domain, 'get') else domain

        if domain_list is not None:
            resolved = self._normalize_domain_list(domain_list)
            if resolved:
                return resolved

        return self._default_domain_list()

    def get_domain_list(self) -> list[str]:
        return self._domain_list

    def set_domain_list(self, domain_list: list[str]):
        self._domain_list = self._normalize_domain_list(domain_list)

    # ======================================================================
    # 缓存
    # ======================================================================

    def set_cache_dict(self, cache_dict: dict | None):
        self._cache = cache_dict

    def get_cache_dict(self) -> dict | None:
        return self._cache

    # ======================================================================
    # Session 与生命周期管理
    # ======================================================================

    def get_meta_data(self, key=None, dv=None):
        if key is None:
            return self.meta_data
        return self.meta_data.get(key, dv)

    def __getitem__(self, item):
        return self.get_meta_data(item)

    def __setitem__(self, key, value):
        if key == 'cookies':
            cookies = dict(self.meta_data.get('cookies') or {})
            if value:
                cookies.update(value)
            self.meta_data['cookies'] = cookies
            if self._session is not None and value:
                self._session.cookies.update(value)
            return
        self.meta_data[key] = value

    async def _ensure_session(self):
        """懒加载 AsyncSession，确保在 event loop 中初始化"""
        if self._session is not None:
            return
        async with self._get_session_lock():
            if self._session is not None:
                return

            meta_data = self.get_meta_data()
            kwargs = {
                'timeout': meta_data.get('timeout') or self._timeout,
                'impersonate': meta_data.get('impersonate', 'chrome'),
                'max_clients': max(self._max_clients_hint, 1),
            }

            proxies = meta_data.get('proxies', None)
            if proxies is not None:
                if isinstance(proxies, str):
                    from .common import ProxyBuilder
                    proxies = ProxyBuilder.build_by_str(proxies)
                kwargs['proxies'] = proxies

            if meta_data.get('headers'):
                kwargs['headers'] = meta_data['headers']

            if meta_data.get('cookies'):
                kwargs['cookies'] = meta_data['cookies']

            # noinspection PyArgumentList
            self._session = AsyncSession(**kwargs)

    async def setup(self):
        if self._has_setup:
            return
        await self._ensure_session()
        self._has_setup = True

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._has_setup = False

    # ======================================================================
    # 核心请求基础设施（对齐 AbstractJmClient）
    # ======================================================================

    # noinspection PyMethodMayBeStatic
    def of_api_url(self, api_path: str, domain: str) -> str:
        return JmcomicText.format_url(api_path, domain)

    @staticmethod
    def append_params_to_url(url: str, params: dict) -> str:
        return f'{url}?{urlencode(params)}'

    # noinspection PyMethodMayBeStatic
    def decode(self, url: str) -> str:
        if not JmModuleConfig.FLAG_DECODE_URL_WHEN_LOGGING or '/search/' not in url:
            return url
        from urllib.parse import unquote
        return unquote(url.replace('+', ' '))

    def log_topic(self) -> str:
        return self.client_key

    def update_request_with_specify_domain(self, kwargs: dict, domain: str | None, is_image: bool = False):
        pass

    # noinspection PyMethodMayBeStatic
    def raise_if_resp_should_retry(self, resp, is_image: bool = False):
        if is_image:
            resp = JmImageResp(resp)
            resp.require_success()
        return resp

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def before_retry(self, e, kwargs, retry_count, url):
        jm_log('req.error', str(e), e)

    # noinspection PyUnusedLocal
    def fallback(self, url, domain_index, retry_count, is_image, retry_errors=None, **kwargs):
        msg = f"请求重试全部失败: [{url}], {self._domain_list}"
        jm_log('req.fallback', msg)
        ExceptionTool.raises(
            msg,
            {ExceptionTool.CONTEXT_KEY_RETRY_ERRORS: retry_errors or []},
            RequestRetryAllFailException,
        )

    async def _request_with_retry(self,
                                  url_path: str,
                                  headers: dict | None = None,
                                  get: bool = True,
                                  is_image: bool = False,
                                  **kwargs,
                                  ):
        await self._ensure_session()
        if headers is not None:
            kwargs['headers'] = headers
        params = kwargs.pop('params', None)
        if params:
            url_path = self.append_params_to_url(url_path, params)

        is_path = url_path.startswith('/')
        if is_path and not self._domain_list:
            ExceptionTool.raises(f'无可用 {self.client_key} 域名列表')

        retry_errors = []
        for retry in range(self._retry_times + 1):
            domains = (
                sorted(self._domain_list, key=lambda d: self._domain_fail_count.get(d, 0))
                if is_path
                else [None]
            )
            for domain_index, domain in enumerate(domains):
                req_url = self.of_api_url(url_path, domain) if is_path else url_path
                req_kwargs = dict(kwargs)
                self.update_request_with_specify_domain(req_kwargs, domain, is_image=is_image)

                if is_path:
                    jm_log(self.log_topic(), self.decode(req_url))

                if domain_index != 0 or retry != 0:
                    jm_log('req.retry',
                           ', '.join([
                               f'次数: [{retry}/{self._retry_times}]',
                               f'域名: [{domain_index} of {domains}]',
                               f'路径: [{req_url}]',
                               f'参数: [{req_kwargs if "login" not in req_url else "#login_form#"}]',
                           ]))

                try:
                    if get:
                        # noinspection PyUnresolvedReferences
                        resp = await self._session.get(req_url, **req_kwargs)
                    else:
                        # noinspection PyUnresolvedReferences
                        resp = await self._session.post(req_url, **req_kwargs)

                    return self.raise_if_resp_should_retry(resp, is_image=is_image)
                except (curl_requests.exceptions.RequestException, OSError, JmcomicException) as e:
                    if is_path:
                        self._domain_fail_count[domain] = self._domain_fail_count.get(domain, 0) + 1
                    self.before_retry(e, req_kwargs, retry, req_url)
                    retry_errors.append({
                        'domain': domain if is_path else None,
                        'url': req_url,
                        'retry': retry,
                        'error': e,
                    })

        return self.fallback(url_path, len(self._domain_list) if is_path else 1, self._retry_times, is_image,
                             retry_errors=retry_errors, **kwargs)

    async def get(self, url, **kwargs):
        await self.setup()
        return await self._request_with_retry(url, get=True, **kwargs)

    async def post(self, url, **kwargs):
        await self.setup()
        return await self._request_with_retry(url, get=False, **kwargs)

    async def get_jm_image(self, img_url: str) -> JmImageResp:
        return await self.get(img_url, is_image=True)


class AsyncJmHtmlClient(AbstractAsyncJmClient):
    """禁漫网页端异步客户端，对标同步端 JmHtmlClient。"""

    client_key = 'async_html'
    domain_config_key = 'html'
    func_to_cache = ['search', 'fetch_detail_entity']

    API_SEARCH = JmHtmlClient.API_SEARCH
    API_CATEGORY = JmHtmlClient.API_CATEGORY
    API_ALBUM_PAGINATION = JmHtmlClient.API_ALBUM_PAGINATION
    API_FORUM = JmHtmlClient.API_FORUM

    def _default_domain_list(self) -> list[str]:
        if JmModuleConfig.DOMAIN_HTML_LIST:
            return list(JmModuleConfig.DOMAIN_HTML_LIST)
        if JmModuleConfig.DOMAIN_HTML:
            return [JmModuleConfig.DOMAIN_HTML]
        return []

    async def get_html_url(self) -> str:
        """访问禁漫永久网域，得到可用的禁漫网址（对标 JmModuleConfig.get_html_url）"""
        await self._ensure_session()
        url = JmModuleConfig.JM_REDIRECT_URL
        while True:
            # noinspection PyUnresolvedReferences
            resp = await self._session.get(
                url,
                headers=JmModuleConfig.new_html_headers(),
                allow_redirects=False,
            )
            if resp.status_code == 301:
                url = resp.headers['Location']
                continue
            if resp.status_code == 302:
                url = resp.headers['Location']
                break
            ExceptionTool.raises_resp(f'请求失败，访问禁漫永久网域获取可用网址，HTTP状态码为: {resp.status_code}', resp)

        jm_log('module.html_url', f'获取禁漫网页URL: [{JmModuleConfig.JM_REDIRECT_URL}] → [{url}]')
        return url

    async def get_html_domain(self) -> str:
        """动态获取并缓存禁漫网页域名（对标 JmModuleConfig.get_html_domain）"""
        if JmModuleConfig.DOMAIN_HTML is None:
            JmModuleConfig.DOMAIN_HTML = JmcomicText.parse_to_jm_domain(await self.get_html_url())
        return JmModuleConfig.DOMAIN_HTML

    async def get_html_domain_all(self) -> list[str]:
        """访问禁漫发布页，得到所有的禁漫网页域名（对标 JmModuleConfig.get_html_domain_all）"""
        if JmModuleConfig.DOMAIN_HTML_LIST is not None:
            return JmModuleConfig.DOMAIN_HTML_LIST
        await self._ensure_session()
        # noinspection PyUnresolvedReferences
        resp = await self._session.get(
            JmModuleConfig.JM_PUB_URL,
            headers=JmModuleConfig.new_html_headers(),
        )
        if resp.status_code != 200:
            ExceptionTool.raises_resp(f'请求失败，访问禁漫发布页获取所有域名，HTTP状态码为: {resp.status_code}', resp)
        domain_list = JmcomicText.analyse_jm_pub_html(resp.text)
        jm_log('module.html_domain_all', f'获取禁漫网页全部域名: [{resp.url}] → {domain_list}')
        JmModuleConfig.DOMAIN_HTML_LIST = domain_list
        return domain_list

    async def setup(self):
        if self._has_setup:
            return

        await self._ensure_session()

        if not self._domain_list:
            async with self._get_setup_lock():
                if not self._domain_list:
                    self._domain_list = [await self.get_html_domain()]

        self._has_setup = True

    def update_request_with_specify_domain(self, kwargs: dict, domain: str | None, is_image: bool = False):
        if is_image:
            domain = self._domain_list[0] if self._domain_list else None
        latest_headers = kwargs.get('headers')
        base_headers = dict(
            self.get_meta_data('headers')
            or (JmModuleConfig.new_html_headers(domain) if domain else JmModuleConfig.new_html_headers())
        )
        if latest_headers:
            base_headers.update(latest_headers)
        kwargs['headers'] = base_headers

    async def get_jm_html(self, url, require_200=True, **kwargs):
        response = await self.get(url, **kwargs)
        if require_200 and response.status_code != 200:
            JmHtmlClient.check_special_http_code(response)
            JmHtmlClient.raise_request_error(response)
        JmHtmlClient.require_resp_success_else_raise(response, url)
        return response

    async def fetch_detail_entity(self, jmid, prefix: str) -> DetailType:
        jmid = JmcomicText.parse_to_jm_id(jmid)
        response = await self.get_jm_html(f'/{prefix}/{jmid}')
        if prefix == 'album':
            return JmcomicText.analyse_jm_album_html(response.text)
        if prefix == 'photo':
            return JmcomicText.analyse_jm_photo_html(response.text)
        raise ValueError(f'不支持的 prefix 类型: {prefix}')

    async def get_album_detail(self, album_id, allow_redirect=True) -> JmAlbumDetail:
        return await self.fetch_detail_entity(album_id, 'album')

    async def get_photo_detail(self,
                               photo_id,
                               fetch_album=True,
                               fetch_scramble_id=True,
                               ) -> JmPhotoDetail:
        photo = await self.fetch_detail_entity(photo_id, 'photo')
        if fetch_album:
            photo.from_album = await self.get_album_detail(photo.album_id)
        return photo

    async def search(self,
                     search_query: str,
                     page: int,
                     main_tag: int,
                     order_by: str,
                     time: str,
                     category: str,
                     sub_category: str | None,
                     ) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
        }
        url = JmHtmlClient.build_search_url(self.API_SEARCH, category, sub_category)
        response = await self.get_jm_html(
            self.append_params_to_url(url, params),
            allow_redirects=True,
        )
        if response.redirect_count != 0 and '/album/' in str(response.url):
            album = JmcomicText.analyse_jm_album_html(response.text)
            return JmSearchPage.wrap_single_album(album, page)
        return JmPageTool.parse_html_to_search_page(response.text, page)

    async def categories_filter(self,
                                page: int,
                                time: str,
                                category: str,
                                order_by: str,
                                sub_category: str | None = None,
                                ) -> JmCategoryPage:
        params = {'page': page, 'o': order_by, 't': time}
        url = JmHtmlClient.build_search_url(self.API_CATEGORY, category, sub_category)
        response = await self.get_jm_html(
            self.append_params_to_url(url, params),
            allow_redirects=True,
        )
        return JmPageTool.parse_html_to_category_page(response.text, page)

    async def login(self, username, password, id_remember='on', login_remember='on'):
        response = await self.post(
            '/login',
            data={
                'username': username,
                'password': password,
                'id_remember': id_remember,
                'login_remember': login_remember,
                'submit_login': '',
            },
            allow_redirects=False,
        )
        if response.status_code != 200:
            JmHtmlClient.raise_request_error(response, f'登录失败，状态码为{response.status_code}')
        result = response.json()
        if result.get('status') != 1:
            errors = result.get('errors') or [result.get('msg', '登录失败')]
            JmHtmlClient.raise_request_error(response, f'登录失败：{errors[0]}')

        original_cookies = self.get_meta_data('cookies') or {}
        new_cookies = dict(response.cookies)
        if 'AVS' in original_cookies and 'AVS' not in new_cookies:
            return response
        if new_cookies:
            self['cookies'] = new_cookies
        self._username = username
        return response

    async def favorite_folder(self,
                              page=1,
                              order_by=JmMagicConstants.ORDER_FF_FAVORITE_TIME,
                              folder_id='0',
                              username='',
                              ) -> JmFavoritePage:
        if username == '':
            ExceptionTool.require_true(self._username is not None, 'favorite_folder方法需要传username参数')
            username = self._username
        response = await self.get_jm_html(
            f'/user/{username}/favorite/albums',
            params={'page': page, 'o': order_by, 'folder': folder_id},
        )
        return JmPageTool.parse_html_to_favorite_page(response.text, page)

    async def add_favorite_album(self, album_id, folder_id='0', rollback_when_mismatch: bool = True):
        response = await self.post(
            '/ajax/favorite_album',
            data={'album_id': str(album_id), 'fid': str(folder_id)},
        )
        result = response.json()
        if result['status'] != 1:
            msg = parse_unicode_escape_text(result['msg'])
            JmHtmlClient.raise_request_error(
                response,
                PatternTool.match_or_default(msg, JmcomicText.pattern_ajax_favorite_msg, msg),
            )
        return response

    async def delete_favorite_album(self, album_id, folder_id='0', rollback_when_mismatch: bool = True):
        response = await self.post('/ajax/delete_favorite_album', data={'album_id': str(album_id)})
        result = response.json()
        if result['status'] != 1:
            msg = parse_unicode_escape_text(result['msg'])
            JmHtmlClient.raise_request_error(
                response,
                PatternTool.match_or_default(msg, JmcomicText.pattern_ajax_favorite_msg, msg),
            )
        return response

    async def get_or_fetch_daily_id(self, daily_id=None) -> str:
        if daily_id is None:
            response = await self.get_jm_html('/')
            daily_id = JmcomicText.parse_daily_id(response.text)
            ExceptionTool.require_true(bool(daily_id), '未能从首页获取到 daily_id，请手动传入 daily_id 参数')
        return str(daily_id)

    async def get_daily(self, user_id: str | None = None, daily_id: str | None = None) -> JmJsonResp:
        daily_id = await self.get_or_fetch_daily_id(daily_id)
        response = await self.get('/ajax/user_daily_event', params={'daily_id': daily_id})
        result = JmJsonResp(response)
        result.require_success()
        return result

    async def daily_checkin(self,
                            daily_id: str | None = None,
                            user_id: str | None = None,
                            old_step: int = 1) -> JmDailyCheckinResp:
        daily_id = await self.get_or_fetch_daily_id(daily_id)
        response = await self.post(
            '/ajax/user_daily_sign',
            data={'daily_id': daily_id, 'oldStep': str(old_step)},
        )
        if response.status_code != 200:
            JmHtmlClient.raise_request_error(response, f'签到请求失败，HTTP状态码: {response.status_code}')
        result = response.json()
        status = result.get('status')
        error = result.get('error')
        msg = str(result.get('msg', ''))
        if status == 1:
            code = JmDailyCheckinResp.CODE_SUCCESS
        elif error == 'finished' or (
                status == 0 and any(kw in msg for kw in self.DAILY_ALREADY_CHECKED_IN_KEYWORDS)
        ):
            code = JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN
        else:
            JmHtmlClient.raise_request_error(response, f'签到失败：{msg or error or status}')
        return JmDailyCheckinResp(response, code, msg, result)

    async def album_comment(self,
                            video_id,
                            comment,
                            originator='',
                            status='true',
                            comment_id=None,
                            **kwargs) -> JmAlbumCommentResp:
        data = {
            'video_id': video_id,
            'comment': comment,
            'originator': originator,
            'status': status,
        }
        if comment_id is not None:
            data.pop('status')
            data.update({'comment_id': comment_id, 'is_reply': 1, 'forum_subject': 1})
        jm_log(
            'album.comment',
            f'{video_id}: [{comment}]' + (f' to ({comment_id})' if comment_id is not None else ''),
        )
        response = await self.post('/ajax/album_comment', data=data, **kwargs)
        result = JmAlbumCommentResp(response)
        result.require_success()
        jm_log('album.comment', f'{video_id}: [{comment}] ← ({result.model().cid})')
        return result

    async def album_pagination(self,
                               jm_id: str,
                               page=1,
                               series=1,
                               with_ad_wcm=1,
                               need_total=True) -> JmAlbumCommentPage:
        response = await self.post(
            self.API_ALBUM_PAGINATION,
            data={
                'video_id': JmcomicText.parse_to_jm_id(jm_id),
                'page': page,
                'series': series,
                'with_ad_wcm': with_ad_wcm,
            },
        )
        result = JmJsonResp(response)
        result.require_success()
        page_result = JmPageTool.parse_html_to_album_comment_page(result.model(), page)
        if need_total:
            album = await self.get_album_detail(jm_id)
            page_result.total = album.comment_count
        return page_result

    async def forum_pagination(self, page=1, with_ad_wcm=1) -> JmAlbumCommentPage:
        response = await self.post(
            self.API_FORUM,
            data={'page': page, 'with_ad_wcm': with_ad_wcm},
        )
        result = JmJsonResp(response)
        result.require_success()
        return JmPageTool.parse_html_to_album_comment_page(result.model(), page)


class AsyncJmApiClient(AbstractAsyncJmClient):
    """
    禁漫移动端异步 API 客户端，对标同步端 JmApiClient。
    """

    client_key = 'async_api'
    domain_config_key = 'api'
    func_to_cache = ['search', 'fetch_detail_entity']

    # 核心 API 路径定义
    API_SEARCH = '/search'
    API_CATEGORIES_FILTER = '/categories/filter'
    API_ALBUM = '/album'
    API_CHAPTER = '/chapter'
    API_SCRAMBLE = '/chapter_view_template'
    API_FAVORITE = '/favorite'
    API_FORUM = '/forum'
    API_DAILY = '/daily'
    API_DAILY_CHK = '/daily_chk'

    # 类级别初始化标记，防止并发重复更新域名
    _has_setup_domain = False

    def _default_domain_list(self) -> list[str]:
        return list(JmModuleConfig.DOMAIN_API_LIST)

    def update_old_api_domain(self, new_server_list: list[str]):
        if not new_server_list:
            return

        if sorted(self._domain_list) != sorted(JmModuleConfig.DOMAIN_API_LIST):
            return

        old_server_list = self._domain_list
        self._domain_list = list(new_server_list)
        jm_log(
            'api.update_domain.replace',
            f'替换异步客户端的内置API域名：(old){old_server_list} ---→ (new){self._domain_list}',
        )

    def update_request_with_specify_domain(self, kwargs: dict, domain: str | None, is_image: bool = False):
        if is_image:
            kwargs['headers'] = {**JmModuleConfig.APP_HEADERS_TEMPLATE, **JmModuleConfig.APP_HEADERS_IMAGE}

    def decide_headers_and_ts(self, kwargs: dict, url: str) -> int:
        if url == self.API_SCRAMBLE:
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(
                ts, secret=JmMagicConstants.APP_TOKEN_SECRET_2
            )
        elif JmModuleConfig.FLAG_USE_FIX_TIMESTAMP:
            ts, token, tokenparam = JmModuleConfig.get_fix_ts_token_tokenparam()
        else:
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(ts)

        headers = dict(JmModuleConfig.APP_HEADERS_TEMPLATE)
        ext_headers = kwargs.pop('headers', None)
        if ext_headers:
            headers.update(ext_headers)
        headers['token'] = token
        headers['tokenparam'] = tokenparam
        kwargs['headers'] = headers
        return ts

    def raise_if_resp_should_retry(self, resp, is_image: bool = False):
        """校验 API 响应报文内容，若存在异常格式或 5xx 状态码则抛出异常以触发重试"""
        resp = super().raise_if_resp_should_retry(resp, is_image=is_image)
        if isinstance(resp, JmResp):
            return resp

        code = resp.status_code
        if code >= 500:
            msg = JmModuleConfig.JM_ERROR_STATUS_CODE.get(code, f'HTTP状态码: {code}')
            ExceptionTool.raises_resp(f"禁漫API异常响应, {msg}", resp)

        if self.API_SCRAMBLE in str(resp.url):
            return resp

        try:
            JmcomicText.try_parse_json_object(resp.text)
            return resp
        except Exception:
            ExceptionTool.raises_resp(
                f'请求不是json格式，强制重试！响应文本: [{JmcomicText.limit_text(resp.text, 200)}]',
                resp,
            )

    @classmethod
    def require_resp_success(cls, resp: JmApiResp, url: str | None = None):
        resp.require_success()

    # noinspection PyMethodMayBeStatic
    def require_resp_status_ok(self, resp: JmApiResp):
        data = resp.model_data
        if data.status != 'ok':
            ExceptionTool.raises_resp(data.msg, resp)

    async def req_api(self,
                      url: str,
                      get: bool = True,
                      require_success: bool = True,
                      params: dict | None = None,
                      **kwargs,
                      ) -> JmApiResp:
        """
        核心的 API 请求封装方法。
        """
        # /setting 是 setup() 内部初始化调用的接口，跳过 setup 防止 asyncio.Lock 不可重入死锁
        if url != '/setting':
            await self.setup()
        else:
            await self._ensure_session()

        ts = self.decide_headers_and_ts(kwargs, url)
        url_path = self.append_params_to_url(url, params) if params else url
        resp = await self._request_with_retry(url_path, get=get, **kwargs)

        api_resp = JmApiResp(resp, ts)
        if require_success:
            self.require_resp_success(api_resp, url)

        return api_resp

    # ======================================================================
    # 详情数据接口获取方法
    # ======================================================================

    async def fetch_detail_entity(self, jmid, clazz: type[DetailType]) -> DetailType:
        """发起详情页数据请求并解析为指定的实体类型"""
        jmid = JmcomicText.parse_to_jm_id(jmid)
        url = self.API_ALBUM if issubclass(clazz, JmAlbumDetail) else self.API_CHAPTER
        resp = await self.req_api(url, params={'id': jmid})

        if not resp.encoded_data or resp.res_data.get('name') is None:
            ExceptionTool.raise_missing(resp, jmid)

        return JmApiAdaptTool.parse_entity(resp.res_data, clazz)

    async def get_album_detail(self, album_id, allow_redirect=True) -> JmAlbumDetail:
        """获取本子详情信息"""
        album: JmAlbumDetail = await self.fetch_detail_entity(album_id, JmModuleConfig.album_class())
        if allow_redirect and album.series_id not in ('0', '', album.album_id):
            jm_log('api.album_redirect',
                   f'请求本子详情传入的ID[{album.album_id}]实为章节ID，自动重定向到所属本子ID[{album.series_id}]')
            return await self.get_album_detail(album.series_id, allow_redirect=False)
        return album

    async def get_photo_detail(self,
                               photo_id,
                               fetch_album=True,
                               fetch_scramble_id=True,
                               ) -> JmPhotoDetail:
        """获取指定图片的详细数据及其前置依赖关联信息"""
        photo = await self.fetch_detail_entity(photo_id, JmModuleConfig.photo_class())
        if fetch_album or fetch_scramble_id:
            await self.fetch_photo_additional_field(photo, fetch_album, fetch_scramble_id)
        return photo

    async def fetch_photo_additional_field(self, photo: JmPhotoDetail,
                                           fetch_album: bool,
                                           fetch_scramble_id: bool):
        """并发获取图片从属的本子信息与 scramble_id 加解密参数。"""
        tasks = {}
        if fetch_album:
            tasks['album'] = self.get_album_detail(photo.album_id)
        if fetch_scramble_id:
            tasks['scramble'] = self.get_scramble_id(photo.photo_id, photo.album_id)

        if not tasks:
            return

        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values())
        result_map = dict(zip(keys, results))

        if 'album' in result_map:
            photo.from_album = result_map['album']
        if 'scramble' in result_map:
            photo.scramble_id = result_map['scramble']

    # ======================================================================
    # 图片解码参数 Scramble ID 获取接口
    # ======================================================================

    async def get_scramble_id(self, photo_id, album_id=None) -> str:
        """获取指定图片的 scramble_id（支持内存级缓存）"""
        cache = JmModuleConfig.SCRAMBLE_CACHE
        if photo_id in cache:
            return cache[photo_id]
        if album_id is not None and album_id in cache:
            return cache[album_id]

        scramble_id = await self.fetch_scramble_id(photo_id)
        cache[photo_id] = scramble_id
        if album_id is not None:
            cache[album_id] = scramble_id
        return scramble_id

    async def fetch_scramble_id(self, photo_id) -> str:
        """向服务端发起实时请求，提取指定图片的 scramble_id 解析参数"""
        photo_id = JmcomicText.parse_to_jm_id(photo_id)
        resp = await self.req_api(
            self.API_SCRAMBLE,
            params={
                'id': photo_id,
                'mode': 'vertical',
                'page': '0',
                'app_img_shunt': '1',
                'express': 'off',
                'v': time_stamp(),
            },
            require_success=False,
        )

        scramble_id = PatternTool.match_or_default(
            resp.text, JmcomicText.pattern_html_album_scramble_id, None
        )
        if scramble_id is None:
            jm_log('api.scramble', f'未匹配到scramble_id，响应文本：{resp.text}')
            scramble_id = str(JmMagicConstants.SCRAMBLE_220980)

        return scramble_id

    # ======================================================================
    # 环境配置与认证管理
    # ======================================================================

    async def ensure_have_cookies(self):
        """初始化基础 Cookies 信息，当不存在时从服务端的 setting 接口拉取"""
        if self.get_meta_data('cookies'):
            return
        if JmModuleConfig.APP_COOKIES is None:
            resp = await self.setting()
            JmModuleConfig.APP_COOKIES = dict(resp.resp.cookies)
        self['cookies'] = JmModuleConfig.APP_COOKIES

    async def setting(self) -> JmApiResp:
        """获取服务端的环境配置（包含应用版本等参数）"""
        resp = await self.req_api('/setting')

        setting_ver = str(resp.model_data.jm3_version)
        if (
                JmModuleConfig.FLAG_USE_VERSION_NEWER_IF_BEHIND
                and JmcomicText.compare_versions(setting_ver, JmMagicConstants.APP_VERSION) == 1
        ):
            jm_log('api.setting',
                   f'change APP_VERSION from [{JmMagicConstants.APP_VERSION}] to [{setting_ver}]')
            JmMagicConstants.APP_VERSION = setting_ver

        return resp

    # ======================================================================
    # 搜索与分类接口
    # ======================================================================

    async def search(self,
                     search_query: str,
                     page: int,
                     main_tag: int,
                     order_by: str,
                     time: str,
                     category: str,
                     sub_category: str | None,
                     ) -> JmSearchPage:
        """
        发起全局搜索请求，提取并包装为搜索结果分页对象。
        注意：移动端暂不支持 category 和 sub_category。
        """
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
        }
        resp = await self.req_api(self.API_SEARCH, params=params)

        data = resp.model_data
        if data.get('redirect_aid', None) is not None:
            aid = data.redirect_aid
            return JmSearchPage.wrap_single_album(await self.get_album_detail(aid), page)

        return JmPageTool.parse_api_to_search_page(data, page)

    async def categories_filter(self,
                                page: int,
                                time: str,
                                category: str,
                                order_by: str,
                                sub_category: str | None = None,
                                ) -> JmCategoryPage:
        """
        获取指定分类下的本子列表数据。
        注意：移动端不支持 sub_category。
        """
        o = f'{order_by}_{time}' if time != JmMagicConstants.TIME_ALL else order_by
        params = {
            'page': page,
            'order': '',
            'c': category,
            'o': o,
        }
        resp = await self.req_api(self.API_CATEGORIES_FILTER, params=params)
        return JmPageTool.parse_api_to_search_page(resp.model_data, page)

    # ======================================================================
    # 用户资产与登录接口
    # ======================================================================

    async def login(self, username: str, password: str) -> JmApiResp:
        """使用账户密码执行系统登录"""
        resp = await self.req_api('/login', False, data={
            'username': username,
            'password': password,
        })
        res_data = resp.res_data
        cookies = dict(resp.resp.cookies)
        cookies.update({'AVS': res_data['s']})
        self['cookies'] = cookies
        self._username = username
        self._user_id = str(res_data['uid']) if 'uid' in res_data else None
        return resp

    async def favorite_folder(self,
                              page=1,
                              order_by=JmMagicConstants.ORDER_FF_FAVORITE_TIME,
                              folder_id='0',
                              username='',
                              ) -> JmFavoritePage:
        """获取收藏夹内特定目录的本子数据分页。"""
        resp = await self.req_api(
            self.API_FAVORITE,
            params={
                'page': page,
                'folder_id': folder_id,
                'o': order_by,
            }
        )
        return JmPageTool.parse_api_to_favorite_page(resp.model_data, page)

    async def album_pagination(self,
                               jm_id: str,
                               page=1,
                               series=1,
                               with_ad_wcm=1,
                               need_total=True,
                               ) -> JmAlbumCommentPage:
        """获取本子评论分页，返回评论分页对象。"""
        resp = await self.req_api(
            self.API_FORUM,
            params={
                'mode': 'all',
                'page': page,
                'aid': JmcomicText.parse_to_jm_id(jm_id),
            },
        )
        return JmPageTool.parse_api_to_album_comment_page(resp.model_data, page)

    async def forum_pagination(self,
                               page=1,
                               with_ad_wcm=1,
                               ) -> JmAlbumCommentPage:
        """获取全站评论分页。"""
        resp = await self.req_api(
            self.API_FORUM,
            params={
                'mode': 'all',
                'page': page,
            },
        )
        return JmPageTool.parse_api_to_album_comment_page(resp.model_data, page)

    async def toggle_favorite_album(self,
                                    album_id,
                                    folder_id='0',
                                    expected_type: str | None = None,
                                    rollback_when_mismatch: bool = True,
                                    ):
        """
        切换本子的收藏状态（移动端接口底层为 Toggle 逻辑）。
        """
        resp = await self.req_api(
            self.API_FAVORITE,
            get=False,
            data={'aid': album_id},
        )
        self.require_resp_status_ok(resp)
        data = resp.model_data

        if expected_type is None or data.type == expected_type:
            return resp

        actual_type = data.type
        if not (rollback_when_mismatch and actual_type in ('add', 'remove')):
            ExceptionTool.raises_resp(
                f'收藏操作不符合预期，期望 [{expected_type}]，实际为 [{actual_type}]: {data.msg}',
                resp
            )

        rollback_resp = await self.req_api(
            self.API_FAVORITE,
            get=False,
            data={'aid': album_id},
        )
        rollback_data = rollback_resp.model_data
        expected_rollback_type = 'remove' if actual_type == 'add' else 'add'
        if rollback_data.status != 'ok' or rollback_data.type != expected_rollback_type:
            ExceptionTool.raises_resp(
                f'收藏操作不符合预期（期望 [{expected_type}]，实际为 [{actual_type}]），'
                f'且自动回滚失败（期望回滚为 [{expected_rollback_type}]，'
                f'实际 status=[{rollback_data.status}], type=[{rollback_data.type}]）: {rollback_data.msg}',
                rollback_resp,
            )

        ExceptionTool.raises_resp(
            f'收藏操作不符合预期，期望 [{expected_type}]，实际为 [{actual_type}]（已自动回滚还原收藏状态）: {data.msg}',
            resp
        )

    async def add_favorite_album(self, album_id, folder_id='0', rollback_when_mismatch: bool = True):
        return await self.toggle_favorite_album(album_id, folder_id, expected_type='add',
                                                rollback_when_mismatch=rollback_when_mismatch)

    async def delete_favorite_album(self, album_id, folder_id='0', rollback_when_mismatch: bool = True):
        return await self.toggle_favorite_album(album_id, folder_id, expected_type='remove',
                                                rollback_when_mismatch=rollback_when_mismatch)

    async def get_daily(self, user_id: str | None = None, daily_id: str | None = None) -> JmApiResp:
        if user_id is None:
            ExceptionTool.require_true(self._user_id is not None, '签到需要传入 user_id 参数，或者先调用 login 方法')
            user_id = self._user_id

        return await self.req_api(self.API_DAILY, params={'user_id': user_id})

    async def daily_checkin(self,
                            daily_id: str | None = None,
                            user_id: str | None = None,
                            old_step: int = 1) -> JmDailyCheckinResp:
        if user_id is None:
            ExceptionTool.require_true(self._user_id is not None, '签到需要传入 user_id 参数，或者先调用 login 方法')
            user_id = self._user_id

        if daily_id is None:
            daily_resp = await self.get_daily(user_id)
            if 'daily_id' not in daily_resp.res_data:
                ExceptionTool.raises_resp('签到失败：签到信息缺少 daily_id', daily_resp)
            daily_id = daily_resp.res_data['daily_id']

        resp: JmApiResp = await self.req_api(
            self.API_DAILY_CHK,
            get=False,
            data={
                'user_id': user_id,
                'daily_id': daily_id,
            },
        )

        res_data = resp.res_data
        msg = str(res_data.get('msg', ''))

        if any(kw in msg for kw in self.DAILY_ALREADY_CHECKED_IN_KEYWORDS):
            code = JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN
        elif 'Jcoin' in msg or 'EXP' in msg or res_data.get('status') == 'ok' or '成功' in msg:
            code = JmDailyCheckinResp.CODE_SUCCESS
        else:
            ExceptionTool.raises_resp(f'签到失败：{msg or res_data}', resp)

        return JmDailyCheckinResp(resp.resp, code, msg, res_data)

    async def album_comment(self,
                            video_id,
                            comment,
                            originator='',
                            status='true',
                            comment_id=None,
                            **kwargs,
                            ) -> JmAlbumCommentResp:
        raise NotImplementedError('移动端 API 不支持评论功能，请使用网页端 JmHtmlClient / AsyncJmHtmlClient')

    # ======================================================================
    # 域名与状态自动刷新
    # ======================================================================

    async def auto_update_domain(self):
        """通过查询中心服务器下发的配置动态刷新本地的接口可用域名列表"""
        if not JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN:
            return

        if JmModuleConfig.DOMAIN_API_UPDATED_LIST is not None:
            self.update_old_api_domain(JmModuleConfig.DOMAIN_API_UPDATED_LIST)
            return

        await self._ensure_session()
        for url in JmModuleConfig.API_URL_DOMAIN_SERVER_LIST:
            try:
                # noinspection PyUnresolvedReferences
                resp = await self._session.get(url, timeout=10)
                text = resp.text
                while text and not text[0].isascii():
                    text = text[1:]
                res_json = JmCryptoTool.decode_resp_data(
                    text, '', JmMagicConstants.API_DOMAIN_SERVER_SECRET
                )
                res_data = json.loads(res_json)
                new_server_list = res_data.get('Server', None)
                if not new_server_list:
                    continue

                jm_log('api.update_domain.success',
                       f'获取到最新的API域名: {new_server_list}')
                JmModuleConfig.DOMAIN_API_UPDATED_LIST = new_server_list
                self.update_old_api_domain(new_server_list)
                return
            except Exception as e:
                jm_log('api.update_domain.error', f'通过[{url}]自动更新API域名失败: {e}')
                continue

        JmModuleConfig.DOMAIN_API_UPDATED_LIST = []

    async def setup(self):
        if self._has_setup:
            return

        await self._ensure_session()

        cls = self.__class__
        async with cls._get_setup_lock():
            if self._has_setup:
                return

            if not cls._has_setup_domain:
                await self.auto_update_domain()
                cls._has_setup_domain = True
            elif JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN:
                self.update_old_api_domain(JmModuleConfig.DOMAIN_API_UPDATED_LIST)

            if JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES:
                await self.ensure_have_cookies()

            self._has_setup = True
