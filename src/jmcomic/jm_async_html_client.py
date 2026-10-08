"""禁漫网页端异步客户端。

网页端的返回值是 HTML 或网页 AJAX JSON。此模块只负责异步请求和会话
生命周期，解析仍复用同步客户端使用的正则解析器，保证两种客户端返回
相同的实体类型。
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Sequence
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests
from curl_cffi.requests import AsyncSession

from .jm_client_impl import JmHtmlClient
from .jm_client_interface import (
    AsyncJmcomicClient,
    JmAlbumCommentResp,
    JmDailyCheckinResp,
    JmImageResp,
    JmJsonResp,
)
from .jm_config import JmMagicConstants, JmModuleConfig, jm_log
from .jm_entity import (
    DetailType,
    JmAlbumCommentPage,
    JmAlbumDetail,
    JmCategoryPage,
    JmFavoritePage,
    JmPhotoDetail,
    JmSearchPage,
)
from .jm_exception import RequestRetryAllFailException
from .jm_exception import JmcomicException
from .jm_option import JmOption
from .jm_toolkit import (
    ExceptionTool,
    JmPageTool,
    JmcomicText,
    PatternTool,
    parse_unicode_escape_text,
)


class AsyncJmHtmlClient(AsyncJmcomicClient):
    """禁漫网页端异步客户端。

    ``domain_list`` 应传入网页域名（例如 ``18comic.ink``）。网页域名不会
    通过移动端 API 的域名更新接口替换；未配置时使用当前项目 Actions 测试
    域名 ``18comic.ink``，调用方也可以随时通过 :meth:`set_domain_list` 修改。
    """

    client_key = 'async_html'
    DEFAULT_DOMAIN = '18comic.ink'

    API_SEARCH = JmHtmlClient.API_SEARCH
    API_CATEGORY = JmHtmlClient.API_CATEGORY
    API_ALBUM_PAGINATION = JmHtmlClient.API_ALBUM_PAGINATION
    API_FORUM = JmHtmlClient.API_FORUM

    _SENTINEL = object()
    _setup_lock = asyncio.Lock()

    def __init__(self,
                 option: JmOption,
                 max_clients=None,
                 domain_list=None,
                 **kwargs):
        if 'domain_retry_strategy' in kwargs:
            raise TypeError('Async client does not support domain_retry_strategy')

        self.option = option
        self._domain_list = self._resolve_domain_list(domain_list)
        retry_times = option.client.get('retry_times')
        self._retry_times = retry_times if retry_times is not None else 5
        self._meta_kwargs = kwargs
        self._timeout = option.client.get('timeout')
        self._max_clients_hint = self._resolve_max_clients(max_clients)
        self._session: AsyncSession | None = None
        self._session_lock = asyncio.Lock()
        self._cache: dict | None = None
        self._username: str | None = None
        self._user_id: str | None = None
        self._has_setup = False

    @staticmethod
    def _normalize_domain_list(domain_list) -> list[str]:
        if isinstance(domain_list, str):
            return [item.strip() for item in domain_list.splitlines() if item.strip()]
        if isinstance(domain_list, Sequence):
            result = []
            for item in domain_list:
                if not isinstance(item, str):
                    raise TypeError(f'domain must be str, got {type(item)}')
                item = item.strip()
                if item:
                    result.append(item)
            return result
        raise TypeError('domain_list must be str, Sequence[str], or None')

    def _resolve_domain_list(self, domain_list=None) -> list[str]:
        if domain_list is not None:
            resolved = self._normalize_domain_list(domain_list)
            if resolved:
                return resolved

        configured = self.option.client.domain
        if isinstance(configured, dict) or hasattr(configured, 'get'):
            configured = configured.get('html', [])
        if configured:
            resolved = self._normalize_domain_list(configured)
            if resolved:
                return resolved

        if JmModuleConfig.DOMAIN_HTML_LIST:
            return list(JmModuleConfig.DOMAIN_HTML_LIST)
        if JmModuleConfig.DOMAIN_HTML:
            return [JmModuleConfig.DOMAIN_HTML]
        return [self.DEFAULT_DOMAIN]

    def _resolve_max_clients(self, max_clients) -> int:
        if max_clients:
            return max(int(max_clients), 1)
        try:
            return max(int(self.option.download.threading.image), 1)
        except (AttributeError, TypeError, ValueError):
            return 10

    def get_domain_list(self) -> list[str]:
        return self._domain_list

    def set_domain_list(self, domain_list: list[str]):
        normalized = self._normalize_domain_list(domain_list)
        self._domain_list = normalized

    def set_cache_dict(self, cache_dict: dict | None):
        self._cache = cache_dict

    def get_cache_dict(self) -> dict | None:
        return self._cache

    def is_given_type(self, ctype) -> bool:
        return isinstance(self, ctype) or self.client_key == ctype.client_key

    @staticmethod
    def _domain_without_protocol(domain: str | None) -> str:
        if not domain:
            return AsyncJmHtmlClient.DEFAULT_DOMAIN
        return domain.removeprefix(JmModuleConfig.PROT).rstrip('/')

    def _build_url(self, path: str, domain: str | None = None) -> str:
        if not path.startswith('/'):
            return path
        domain = domain or self._domain_list[0]
        return JmcomicText.format_url(path, domain)

    def _build_headers(self, domain: str | None, extra_headers=None) -> dict:
        host = self._domain_without_protocol(domain)
        configured = self._session_meta().get('headers')
        if configured:
            headers = dict(configured)
        else:
            headers = JmModuleConfig.new_html_headers(host)

        # 和同步 HTML Client 一样，显式配置的 headers 优先；未配置时才
        # 根据当前重试域名生成 authority/origin/referer。
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _session_meta(self) -> dict:
        postman_conf = deepcopy(self.option.client.get('postman', {}))
        metadata = postman_conf.get('meta_data', {}) or {}
        metadata.update(self._meta_kwargs)
        return metadata

    async def _ensure_session(self):
        if self._session is not None:
            return
        async with self._session_lock:
            if self._session is not None:
                return
            metadata = self._session_meta()
            timeout = self._timeout or metadata.get('timeout') or 30
            session_kwargs = {
                'timeout': timeout,
                'impersonate': metadata.get('impersonate', 'chrome'),
                'max_clients': self._max_clients_hint,
            }
            proxies = metadata.get('proxies')
            if proxies is not None:
                if isinstance(proxies, str):
                    from common import ProxyBuilder
                    proxies = ProxyBuilder.build_by_str(proxies)
                session_kwargs['proxies'] = proxies
            if metadata.get('headers'):
                session_kwargs['headers'] = metadata['headers']
            if metadata.get('cookies'):
                session_kwargs['cookies'] = metadata['cookies']
            self._session = AsyncSession(**session_kwargs)

    async def setup(self):
        if self._has_setup:
            return
        await self._ensure_session()
        async with self.__class__._setup_lock:
            if self._session is None:
                await self._ensure_session()
            self._has_setup = True

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._has_setup = False

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _record_retry(self, error, url, retry, domain=None):
        jm_log('req.error', str(error), error)
        return {
            'domain': domain,
            'url': url,
            'retry': retry,
            'error': error,
        }

    async def _request_with_retry(self,
                                  url: str,
                                  *,
                                  get: bool = True,
                                  headers=None,
                                  is_image: bool = False,
                                  **kwargs):
        if not self._has_setup:
            await self.setup()
        else:
            await self._ensure_session()
        is_path = url.startswith('/')
        domains = self._domain_list if is_path else [None]
        retry_errors = []

        for domain_index, domain in enumerate(domains):
            request_url = self._build_url(url, domain) if is_path else url
            request_headers = self._build_headers(
                domain or urlparse(request_url).netloc,
                headers,
            )
            for retry in range(self._retry_times + 1):
                if domain_index != 0 or retry != 0:
                    jm_log(
                        'req.retry',
                        f'次数: [{retry}/{self._retry_times}], '
                        f'域名: [{domain_index} of {domains}], 路径: [{request_url}]',
                    )
                jm_log(self.client_key, request_url)
                try:
                    if get:
                        response = await self._session.get(
                            request_url,
                            headers=request_headers,
                            **kwargs,
                        )
                    else:
                        response = await self._session.post(
                            request_url,
                            headers=request_headers,
                            **kwargs,
                        )
                    if is_image:
                        wrapped = JmImageResp(response)
                        wrapped.require_success()
                    return response
                except (curl_requests.exceptions.RequestException, OSError, JmcomicException) as error:
                    retry_errors.append(
                        self._record_retry(
                            error,
                            request_url,
                            retry,
                            domain if is_path else None,
                        )
                    )

        msg = f'请求重试全部失败: [{url}], {self._domain_list}'
        jm_log('req.fallback', msg)
        ExceptionTool.raises(
            msg,
            {ExceptionTool.CONTEXT_KEY_RETRY_ERRORS: retry_errors},
            RequestRetryAllFailException,
        )

    async def get(self, url, **kwargs):
        return await self._request_with_retry(url, get=True, **kwargs)

    async def post(self, url, **kwargs):
        return await self._request_with_retry(url, get=False, **kwargs)

    async def get_jm_html(self, url, require_200=True, **kwargs):
        response = await self.get(url, **kwargs)
        if require_200 and response.status_code != 200:
            JmHtmlClient.check_special_http_code(response)
            JmHtmlClient.raise_request_error(response)
        JmHtmlClient.require_resp_success_else_raise(response, url)
        return response

    async def _fetch_detail_entity(self, jmid, prefix: str) -> DetailType:
        jmid = JmcomicText.parse_to_jm_id(jmid)
        cache_key = ('detail', prefix, jmid)
        if self._cache is not None:
            cached = self._cache.get(cache_key, self._SENTINEL)
            if cached is not self._SENTINEL:
                return deepcopy(cached)

        response = await self.get_jm_html(f'/{prefix}/{jmid}')
        if prefix == 'album':
            result = JmcomicText.analyse_jm_album_html(response.text)
        elif prefix == 'photo':
            result = JmcomicText.analyse_jm_photo_html(response.text)
        else:
            raise ValueError(f'不支持的 prefix 类型: {prefix}')

        if self._cache is not None:
            self._cache[cache_key] = deepcopy(result)
        return result

    async def get_album_detail(self, album_id) -> JmAlbumDetail:
        return await self._fetch_detail_entity(album_id, 'album')

    async def get_photo_detail(self,
                               photo_id,
                               fetch_album=True,
                               fetch_scramble_id=True,
                               ) -> JmPhotoDetail:
        photo = await self._fetch_detail_entity(photo_id, 'photo')
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
        cache_key = ('search', search_query, page, main_tag, order_by, time, category, sub_category)
        if self._cache is not None:
            cached = self._cache.get(cache_key, self._SENTINEL)
            if cached is not self._SENTINEL:
                return deepcopy(cached)

        response = await self.get_jm_html(url, params=params, allow_redirects=True)
        redirect_count = getattr(response, 'redirect_count', None)
        if redirect_count is None:
            redirect_count = len(getattr(response, 'history', ()) or ())
        if redirect_count != 0 and '/album/' in str(response.url):
            album = JmcomicText.analyse_jm_album_html(response.text)
            result = JmSearchPage.wrap_single_album(album, page)
            if self._cache is not None:
                self._cache[cache_key] = deepcopy(result)
            return result
        result = JmPageTool.parse_html_to_search_page(response.text, page)
        if self._cache is not None:
            self._cache[cache_key] = deepcopy(result)
        return result

    async def categories_filter(self,
                                page: int,
                                time: str,
                                category: str,
                                order_by: str,
                                sub_category: str | None = None,
                                ) -> JmCategoryPage:
        params = {'page': page, 'o': order_by, 't': time}
        url = JmHtmlClient.build_search_url(self.API_CATEGORY, category, sub_category)
        response = await self.get_jm_html(url, params=params, allow_redirects=True)
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

        original_cookies = self._session_meta().get('cookies') or {}
        new_cookies = dict(getattr(response, 'cookies', {}) or {})
        # 重复登录时网页端可能只返回部分 Cookie，保留已有 AVS。
        if 'AVS' in original_cookies and 'AVS' not in new_cookies:
            return response
        if new_cookies:
            session_cookies = getattr(self._session, 'cookies', None)
            if session_cookies is not None:
                session_cookies.update(new_cookies)
            self.option.update_cookies(new_cookies)
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

    async def add_favorite_album(self, album_id, folder_id='0'):
        response = await self.post(
            '/ajax/favorite_album',
            data={'album_id': str(album_id), 'fid': str(folder_id)},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        result = response.json()
        if result['status'] != 1:
            msg = parse_unicode_escape_text(result['msg'])
            JmHtmlClient.raise_request_error(
                response,
                PatternTool.match_or_default(msg, JmcomicText.pattern_ajax_favorite_msg, msg),
            )
        return response

    async def delete_favorite_album(self, album_id, folder_id='0'):
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
        msg = str(result.get('msg', ''))
        if status == 1:
            code = JmDailyCheckinResp.CODE_SUCCESS
        elif status == 0 and any(keyword in msg for keyword in ('已完成打卡', '今天已经签到', '今日已完成', '已签到', '已打卡')):
            code = JmDailyCheckinResp.CODE_ALREADY_CHECKED_IN
        else:
            JmHtmlClient.raise_request_error(response, f'签到失败：{msg or status}')
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
        response = await self.post('/ajax/album_comment', data=data, **kwargs)
        result = JmAlbumCommentResp(response)
        result.require_success()
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

    async def album_pagination_gen(self,
                                   jm_id: str,
                                   page=1,
                                   series=1,
                                   with_ad_wcm=1,
                                   need_total=True):
        first_page = True
        total = None
        while True:
            page_result = await self.album_pagination(
                jm_id,
                page=page,
                series=series,
                with_ad_wcm=with_ad_wcm,
                need_total=need_total if first_page else False,
            )
            if first_page:
                total = page_result.total
                first_page = False
            else:
                page_result.total = total
            yield page_result

            if page_result.page_count is not None:
                if page >= page_result.page_count:
                    break
            else:
                has_next_page = any(
                    int(match.group(1)) == page + 1
                    for match in JmcomicText.pattern_html_comment_next_page.finditer(page_result.raw_html or '')
                )
                if not has_next_page:
                    break
            page += 1

    async def get_jm_image(self, img_url: str) -> JmImageResp:
        # 图片 CDN 与网页站点可能不是同一域名，Referer/Origin 仍应指向网页域名。
        site_domain = self._domain_list[0] if self._domain_list else self.DEFAULT_DOMAIN
        response = await self._request_with_retry(
            img_url,
            headers=JmModuleConfig.new_html_headers(self._domain_without_protocol(site_domain)),
            is_image=True,
        )
        return JmImageResp(response)
