"""
异步 jmcomic API 客户端模块

提供禁漫移动端接口的异步访问能力，基于 curl_cffi 与 asyncio 构建高性能网络通信层。
"""
from __future__ import annotations

import asyncio
import json
from typing import Sequence
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession

from .jm_client_interface import (
    JmApiResp, JmImageResp, JmAlbumCommentResp,
    AsyncJmcomicClient,
)
from .jm_entity import (
    JmAlbumDetail, JmPhotoDetail, JmSearchPage, JmCategoryPage,
    JmFavoritePage, DetailType
)
from .jm_config import JmModuleConfig, JmMagicConstants, time_stamp, jm_log
from .jm_toolkit import (
    JmcomicText, JmCryptoTool, JmApiAdaptTool, JmPageTool,
    ExceptionTool, PatternTool,
)
from .jm_exception import RequestRetryAllFailException
from .jm_option import JmOption


class AsyncJmApiClient(AsyncJmcomicClient):
    """
    禁漫移动端异步 API 客户端。

    继承 AsyncJmcomicClient 接口，提供全面的异步网络通信能力，
    涵盖图集、章节、搜索、登录与收藏夹等功能模块。
    通过异步会话管理与并发请求调度，显著提升网络 I/O 的处理性能与吞吐量。
    """

    client_key = 'async_api'

    # 核心 API 路径定义
    API_SEARCH = '/search'
    API_CATEGORIES_FILTER = '/categories/filter'
    API_ALBUM = '/album'
    API_CHAPTER = '/chapter'
    API_SCRAMBLE = '/chapter_view_template'
    API_FAVORITE = '/favorite'

    # 缓存未命中标记
    _SENTINEL = object()

    # 类级别初始化标记与锁，防止并发更新域名
    _has_setup_domain = False
    _setup_lock = asyncio.Lock()

    def __init__(self, option: JmOption, max_clients=None, domain_list=None, **kwargs):
        if 'domain_retry_strategy' in kwargs:
            raise TypeError('Async client does not support domain_retry_strategy')

        self.option = option
        self._domain_list = self._resolve_domain_list(domain_list)
        retry_times = option.client.get('retry_times')
        self._retry_times = retry_times if retry_times is not None else 5
        self._timeout = option.client.get('timeout', 30) or 30
        # AsyncSession 句柄池大小：优先用调用方（下载器）传入的实际图片并发，
        # 否则回退到 option 配置；避免因默认限制导致真实并发被隐式压低。
        if max_clients:
            self._max_clients_hint = int(max_clients)
        else:
            try:
                self._max_clients_hint = int(option.download.threading.image) or 10
            except Exception:
                self._max_clients_hint = 10

        self._session: AsyncSession | None = None
        self._session_lock = asyncio.Lock()
        # 缓存默认关闭，由外部配置决定是否启用。
        self._cache: dict | None = None
        self._username: str | None = None

        # 接收并保存额外的会话级元数据参数
        self._meta_kwargs = kwargs
        self._has_setup = False

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

    def _resolve_domain_list(self, domain_list=None) -> list[str]:
        """解析并返回可用的 API 域名列表"""
        if domain_list is not None:
            resolved = self._normalize_domain_list(domain_list)
            if resolved:
                return resolved

        domain = self.option.client.domain
        if hasattr(domain, 'get'):
            domain_list = domain.get('api', [])
        else:
            domain_list = domain

        if domain_list is not None:
            resolved = self._normalize_domain_list(domain_list)
            if resolved:
                return resolved

        return list(JmModuleConfig.DOMAIN_API_LIST)

    def get_domain_list(self) -> list[str]:
        return self._domain_list

    def set_domain_list(self, domain_list: list[str]):
        self._domain_list = domain_list

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

    # ======================================================================
    # 缓存
    # ======================================================================

    def set_cache_dict(self, cache_dict: dict | None):
        self._cache = cache_dict

    def get_cache_dict(self) -> dict | None:
        return self._cache

    def _cache_get(self, key):
        """从缓存获取，未命中返回 sentinel"""
        if self._cache is None:
            return self._SENTINEL
        return self._cache.get(key, self._SENTINEL)

    def _cache_set(self, key, value):
        """写入缓存"""
        if self._cache is not None:
            self._cache[key] = value

    # 说明：异步缓存不采用动态方法包裹（Monkey Patching）的方式，避免缓存协程对象引发复用异常。
    # 而是直接在 _fetch_detail_entity / search 内部通过 _cache_get/_cache_set 进行结果级缓存操作。
    # 启停状态由 self._cache 对象驱动。

    # ======================================================================
    # Session 管理
    # ======================================================================

    async def _ensure_session(self):
        """懒加载 AsyncSession，确保在 event loop 中初始化"""
        if self._session is not None:
            return
        async with self._session_lock:
            if self._session is not None:
                return

            # 提取应用配置中预设的网络通信元数据信息（如代理配置与全局 Headers）
            from copy import deepcopy
            postman_conf = deepcopy(self.option.client.get('postman', {}))
            meta_data = postman_conf.get('meta_data', {})
            if self._meta_kwargs:
                meta_data.update(self._meta_kwargs)

            kwargs = {
                'timeout': self._timeout,
                'impersonate': meta_data.get('impersonate', 'chrome'),
                # 让 AsyncSession 的句柄池大小与本下载器的图片并发对齐，
                # 避免因默认限制导致真实并发被隐式压低。
                'max_clients': max(self._max_clients_hint, 1),
            }

            proxies = meta_data.get('proxies', None)
            if proxies is not None:
                # 字符串形式的代理需经 ProxyBuilder 转 dict
                if isinstance(proxies, str):
                    from common import ProxyBuilder
                    proxies = ProxyBuilder.build_by_str(proxies)
                kwargs['proxies'] = proxies

            if meta_data.get('headers'):
                kwargs['headers'] = meta_data['headers']

            # 加载预配置或已持久化的历史会话 Cookies
            if meta_data.get('cookies'):
                kwargs['cookies'] = meta_data['cookies']

            # noinspection PyArgumentList
            self._session = AsyncSession(**kwargs)

    # ======================================================================
    # 核心请求基础设施
    # ======================================================================

    def _build_api_url(self, path: str, domain: str) -> str:
        prot = JmModuleConfig.PROT
        if domain.startswith(prot):
            return f'{domain}{path}'
        return f'{prot}{domain}{path}'

    def _build_api_headers(self, path: str) -> tuple:
        """构建对应接口所需的 API 请求头部信息与时间戳"""
        headers = dict(JmModuleConfig.APP_HEADERS_TEMPLATE)

        if path == self.API_SCRAMBLE:
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(
                ts, secret=JmMagicConstants.APP_TOKEN_SECRET_2
            )
        elif JmModuleConfig.FLAG_USE_FIX_TIMESTAMP:
            ts, token, tokenparam = JmModuleConfig.get_fix_ts_token_tokenparam()
        else:
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(ts)

        headers['token'] = token
        headers['tokenparam'] = tokenparam
        return headers, ts

    async def _request_with_retry(self,
                                  url_path: str,
                                  headers: dict,
                                  get: bool = True,
                                  is_api: bool = True,
                                  **kwargs,
                                  ):
        """
        带域名切换机制的请求重试策略。
        机制：在当前域名下重试指定的次数，如全数失败则切换至备选域名，直至遍历完所有可用域名。
        """
        domain_list = self._domain_list
        if not domain_list:
            ExceptionTool.raises("无可用 API 域名列表")

        for domain_index, domain in enumerate(domain_list):
            url = self._build_api_url(url_path, domain)

            for retry in range(self._retry_times + 1):
                # 记录重试信息
                if domain_index != 0 or retry != 0:
                    jm_log('req.retry',
                           f'次数: [{retry}/{self._retry_times}], '
                           f'域名: [{domain_index} of {domain_list}], '
                           f'路径: [{url}]')

                # 记录请求日志
                jm_log(self.client_key, self._decode_url_for_log(url))

                try:
                    if get:
                        # noinspection PyUnresolvedReferences
                        resp = await self._session.get(url, headers=headers, **kwargs)
                    else:
                        # noinspection PyUnresolvedReferences
                        resp = await self._session.post(url, headers=headers, **kwargs)

                    # 校验 API 响应的有效性并决定是否触发重试
                    if is_api:
                        self._raise_if_resp_should_retry(resp)

                    return resp
                except Exception as e:
                    self.before_retry(e, url, retry, domain_index)

        # 所有域名都失败
        msg = f"请求重试全部失败: [{url_path}], {domain_list}"
        jm_log('req.fallback', msg)
        ExceptionTool.raises(msg, {}, RequestRetryAllFailException)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def before_retry(self, e, url, retry, domain_index):
        """
        每次请求失败且即将进入重试前的拦截回调，子类可重写以加入自定义的副作用逻辑（例如告警或统计）。
        """
        jm_log('req.error', str(e), e)

    def _decode_url_for_log(self, url: str) -> str:
        """将 URL 转换为适合在日志中显示的解码格式"""
        if not JmModuleConfig.FLAG_DECODE_URL_WHEN_LOGGING or '/search/' not in url:
            return url

        from urllib.parse import unquote
        return unquote(url.replace('+', ' '))

    @staticmethod
    def _raise_if_resp_should_retry(resp):
        """内部校验 API 响应报文内容，若存在异常格式或无法处理的数据则抛出异常以触发重试"""
        code = resp.status_code
        if code >= 500:
            msg = JmModuleConfig.JM_ERROR_STATUS_CODE.get(code, f'HTTP状态码: {code}')
            ExceptionTool.raises_resp(f"禁漫API异常响应, {msg}", resp)

        url = getattr(resp, 'url', '')
        if AsyncJmApiClient.API_SCRAMBLE in str(url):
            # /chapter_view_template 这个接口不是返回json数据，不做检查
            return

        # 检查响应的第一个有效字符是否为 '{'（JSON 格式）
        text = resp.text
        for char in text:
            if char not in (' ', '\n', '\t'):
                ExceptionTool.require_true(
                    char == '{',
                    f'请求不是json格式，强制重试！响应文本: [{JmcomicText.limit_text(text, 200)}]'
                )
                return
        ExceptionTool.raises_resp(f'响应无数据！', resp)

    @staticmethod
    def _require_resp_success(resp: JmApiResp):
        """断言响应状态必须为成功"""
        resp.require_success()

    async def req_api(self,
                      url: str,
                      get: bool = True,
                      require_success: bool = True,
                      params: dict | None = None,
                      **kwargs,
                      ) -> JmApiResp:
        """
        核心的 API 请求封装方法。
        处理参数拼装、请求发送与重试，并返回统一的 JmApiResp 响应对象。
        """
        # /setting 是 setup() 内部初始化调用的接口，跳过 setup 防止 asyncio.Lock 不可重入死锁
        if url != '/setting':
            await self.setup()
        else:
            await self._ensure_session()

        # 构建 headers 和时间戳
        headers, ts = self._build_api_headers(url)
        # 合并外部传入的 headers
        ext_headers = kwargs.pop('headers', None)
        if ext_headers:
            headers.update(ext_headers)

        # 构建 URL 路径
        url_path = url
        if params:
            url_path = f'{url}?{urlencode(params)}'

        # 带域名重试的请求（不硬编码 timeout，使用 session 级别的配置）
        resp = await self._request_with_retry(
            url_path, headers, get=get, is_api=True, **kwargs,
        )

        # 封装为 JmApiResp，复用完整的校验链
        api_resp = JmApiResp(resp, ts)
        if require_success:
            self._require_resp_success(api_resp)

        return api_resp

    # ======================================================================
    # 详情数据接口获取方法
    # ======================================================================

    async def _fetch_detail_entity(self, jmid, clazz: type[DetailType]) -> DetailType:
        """发起详情页数据请求并解析为指定的实体类型"""
        jmid = JmcomicText.parse_to_jm_id(jmid)

        # 缓存检查
        cache_key = ('detail', jmid, clazz)
        cached = self._cache_get(cache_key)
        if cached is not self._SENTINEL:
            # noinspection PyTypeChecker
            return cached

        url = self.API_ALBUM if issubclass(clazz, JmAlbumDetail) else self.API_CHAPTER
        resp = await self.req_api(url, params={'id': jmid})

        if not resp.encoded_data or resp.res_data.get('name') is None:
            ExceptionTool.raise_missing(resp, jmid)

        result = JmApiAdaptTool.parse_entity(resp.res_data, clazz)
        self._cache_set(cache_key, result)
        return result

    async def get_album_detail(self, album_id) -> JmAlbumDetail:
        """获取图集详情信息"""
        return await self._fetch_detail_entity(album_id, JmModuleConfig.album_class())

    async def get_photo_detail(self,
                               photo_id,
                               fetch_album=True,
                               fetch_scramble_id=True,
                               ) -> JmPhotoDetail:
        """获取指定图片的详细数据及其前置依赖关联信息"""
        photo = await self._fetch_detail_entity(photo_id, JmModuleConfig.photo_class())
        if fetch_album or fetch_scramble_id:
            await self._fetch_photo_additional_field(photo, fetch_album, fetch_scramble_id)
        return photo

    async def _fetch_photo_additional_field(self, photo: JmPhotoDetail,
                                            fetch_album: bool,
                                            fetch_scramble_id: bool):
        """并发获取图片从属的图集信息与 scramble_id 加解密参数。"""
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

    # check_photo 继承自 AsyncJmcomicClient 基类

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
        # noinspection PyUnresolvedReferences
        if self._session and self._session.cookies:
            return
        # 复用全局缓存
        if JmModuleConfig.APP_COOKIES is not None:
            await self._ensure_session()
            # noinspection PyUnresolvedReferences
            self._session.cookies.update(JmModuleConfig.APP_COOKIES)
            return
        resp = await self.setting()
        cookies = dict(resp.resp.cookies)
        JmModuleConfig.APP_COOKIES = cookies
        # noinspection PyUnresolvedReferences,PyTypeChecker
        self._session.cookies.update(cookies)

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
        # 缓存检查
        cache_key = ('search', search_query, page, main_tag, order_by, time)
        # noinspection PyTypeChecker
        cached: JmSearchPage = self._cache_get(cache_key)
        if cached is not self._SENTINEL:
            return cached

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
            result = JmSearchPage.wrap_single_album(await self.get_album_detail(aid))
        else:
            result = JmPageTool.parse_api_to_search_page(data)

        self._cache_set(cache_key, result)
        return result

    # search_site / search_work / search_author / search_tag / search_actor
    # 继承自 AsyncJmcomicClient 基类，默认值由基类便捷方法提供

    # ======================================================================
    # 分类过滤接口
    # ======================================================================

    async def categories_filter(self,
                                page: int,
                                time: str,
                                category: str,
                                order_by: str,
                                sub_category: str | None = None,
                                ) -> JmCategoryPage:
        """
        获取指定分类下的图集列表数据。
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
        return JmPageTool.parse_api_to_search_page(resp.model_data)

    # month_ranking / week_ranking / day_ranking
    # 继承自 AsyncJmcomicClient 基类

    # ======================================================================
    # 用户资产与登录接口
    # ======================================================================

    async def login(self, username: str, password: str) -> JmApiResp:
        """使用账户密码执行系统登录"""
        resp = await self.req_api('/login', False, data={
            'username': username,
            'password': password,
        })
        cookies = dict(resp.resp.cookies)
        cookies.update({'AVS': resp.res_data['s']})
        # noinspection PyUnresolvedReferences,PyTypeChecker
        self._session.cookies.update(cookies)
        # 同步到 Option 配置，确保 cookies 持久化
        self.option.update_cookies(cookies)
        self._username = username
        return resp

    async def favorite_folder(self,
                              page=1,
                              order_by=JmMagicConstants.ORDER_BY_LATEST,
                              folder_id='0',
                              username='',
                              ) -> JmFavoritePage:
        """获取收藏夹内特定目录的图集数据分页。"""
        resp = await self.req_api(
            self.API_FAVORITE,
            params={
                'page': page,
                'folder_id': folder_id,
                'o': order_by,
            }
        )
        return JmPageTool.parse_api_to_favorite_page(resp.model_data)

    async def add_favorite_album(self, album_id, folder_id='0'):
        """
        将指定图集加入用户的收藏夹。
        注意：移动端没有提供 folder_id 参数。
        """
        # 服务端实现上使用带 body 的 GET 请求方式
        resp = await self.req_api('/favorite', data={'aid': album_id})
        data = resp.model_data
        if data.status != 'ok':
            ExceptionTool.raises_resp(data.msg, resp)
        return resp

    async def album_comment(self,
                            video_id,
                            comment,
                            originator='',
                            status='true',
                            comment_id=None,
                            **kwargs,
                            ) -> JmAlbumCommentResp:
        """提交图集评论内容"""
        # 移动端 API 没有评论接口，此方法仅为接口完整性保留
        raise NotImplementedError('移动端 API 不支持评论功能，请使用网页端 JmHtmlClient')

    # ======================================================================
    # 图片下载
    # ======================================================================

    async def get_jm_image(self, img_url: str) -> JmImageResp:
        """
        异步下载指定 URL 的图片原始字节数据。
        """
        await self.setup()
        headers = {**JmModuleConfig.APP_HEADERS_TEMPLATE, **JmModuleConfig.APP_HEADERS_IMAGE}

        last_error = None
        for retry in range(self._retry_times + 1):
            try:
                # noinspection PyUnresolvedReferences
                resp = await self._session.get(img_url, headers=headers, timeout=self._timeout)
                # 对图片资源的数据进行基础有效性校验
                img_resp = JmImageResp(resp)
                if resp.status_code != 200 or len(resp.content) == 0:
                    img_resp.require_success()  # 会抛出描述性异常
                return img_resp
            except Exception as e:
                last_error = e
                jm_log('req.error',
                       f'图片下载失败: [{img_url}], Retry=[{retry}/{self._retry_times}], Error=[{e}]')
                if retry < self._retry_times:
                    await asyncio.sleep(0.3)

        raise ExceptionTool.raises(f'图片下载重试全部失败: {last_error}', {}, RequestRetryAllFailException)

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

        # 尝试从域名服务器获取最新域名
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

    # ======================================================================
    # 资源生命周期控制
    # ======================================================================

    async def setup(self):
        """
        异步初始化入口，应在使用前调用。
        __aenter__ 会自动调用此方法。
        """
        if self._has_setup:
            return

        await self._ensure_session()

        cls = self.__class__
        async with cls._setup_lock:
            if self._has_setup:
                return

            if not cls._has_setup_domain:
                await self.auto_update_domain()
                cls._has_setup_domain = True
            else:
                # 即使已经初始化过域名，也需要将已保存的全局 DOMAIN 赋值到当前 client
                if JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN:
                    self.update_old_api_domain(JmModuleConfig.DOMAIN_API_UPDATED_LIST)

            # Cookie 属于 session 状态，每个 client 都需要独立确认。
            if JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES:
                await self.ensure_have_cookies()

            self._has_setup = True

    # ======================================================================
    # 生命周期
    # ======================================================================

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
