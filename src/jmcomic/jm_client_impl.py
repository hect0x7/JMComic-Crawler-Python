from .jm_client_interface import *


# 抽象基类，实现了域名管理，发请求，重试机制，debug，缓存等功能
class AbstractJmClient(
    JmcomicClient,
    PostmanProxy,
):
    client_key = None

    def __init__(self,
                 postman: Postman,
                 retry_times: int,
                 domain=None,
                 fallback_domain_list=None,
                 ):
        super().__init__(postman)
        self.retry_times = retry_times

        if fallback_domain_list is None:
            fallback_domain_list = []

        if domain is not None:
            fallback_domain_list.insert(0, domain)

        self.domain_list = fallback_domain_list
        self.after_init()

    def after_init(self):
        pass

    def get(self, url, **kwargs):
        return self.request_with_retry(self.postman.get, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request_with_retry(self.postman.post, url, **kwargs)

    def of_api_url(self, api_path, domain):
        return JmcomicText.format_url(api_path, domain)

    def get_jm_image(self, img_url) -> JmImageResp:

        def get_if_fail_raise(url):
            """
            使用此方法包装 self.get，使得图片数据为空时，判定为请求失败时，走重试逻辑
            """
            resp = JmImageResp(self.get(url))
            resp.require_success()
            return resp

        return self.request_with_retry(get_if_fail_raise, img_url)

    def request_with_retry(self,
                           request,
                           url,
                           domain_index=0,
                           retry_count=0,
                           **kwargs,
                           ):
        """
        统一请求，支持重试
        @param request: 请求方法
        @param url: 图片url / path (/album/xxx)
        @param domain_index: 域名下标
        @param retry_count: 重试次数
        @param kwargs: 请求方法的kwargs
        """
        if domain_index >= len(self.domain_list):
            self.fallback(request, url, domain_index, retry_count, **kwargs)

        if url.startswith('/'):
            # path → url
            url = self.of_api_url(
                api_path=url,
                domain=self.domain_list[domain_index],
            )
            jm_debug(self.debug_topic_request(), self.decode(url))
        else:
            # 图片url
            pass

        if domain_index != 0 or retry_count != 0:
            jm_debug(f'req.retry',
                     ', '.join([
                         f'次数: [{retry_count}/{self.retry_times}]',
                         f'域名: [{domain_index} of {self.domain_list}]',
                         f'路径: [{url}]',
                         f'参数: [{kwargs if "login" not in url else "#login_form#"}]'
                     ])
                     )

        try:
            return request(url, **kwargs)
        except Exception as e:
            self.before_retry(e, kwargs, retry_count, url)

        if retry_count < self.retry_times:
            return self.request_with_retry(request, url, domain_index, retry_count + 1, **kwargs)
        else:
            return self.request_with_retry(request, url, domain_index + 1, 0, **kwargs)

    # noinspection PyMethodMayBeStatic
    def debug_topic_request(self):
        return self.client_key

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def before_retry(self, e, kwargs, retry_count, url):
        jm_debug('req.error', str(e))

    def enable_cache(self, debug=False):
        if self.is_cache_enabled():
            return

        def wrap_func_cache(func_name, cache_dict_name):
            if hasattr(self, cache_dict_name):
                return

            if sys.version_info > (3, 9):
                import functools
                cache = functools.cache
            else:
                import common
                if common.VERSION > '0.4.8':
                    cache = common.cache
                    cache_dict = {}
                    cache_hit_msg = (f'【缓存命中】{cache_dict_name} ' + '→ [{}]') if debug is True else None
                    cache_miss_msg = (f'【缓存缺失】{cache_dict_name} ' + '← [{}]') if debug is True else None
                    cache = cache(
                        cache_dict=cache_dict,
                        cache_hit_msg=cache_hit_msg,
                        cache_miss_msg=cache_miss_msg,
                    )
                    setattr(self, cache_dict_name, cache_dict)
                else:
                    ExceptionTool.raises('不支持启用JmcomicClient缓存。\n'
                                         '请更新python版本到3.9以上，'
                                         '或更新commonX: `pip install commonX --upgrade`')
                    return

            func = getattr(self, func_name)
            wrap_func = cache(func)

            setattr(self, func_name, wrap_func)

        for func in {
            'get_photo_detail',
            'get_album_detail',
            'search',
        }:
            wrap_func_cache(func, func + '.cache.dict')

        setattr(self, '__enable_cache__', True)

    def is_cache_enabled(self) -> bool:
        return getattr(self, '__enable_cache__', False)

    def get_html_domain(self, postman=None):
        return JmModuleConfig.get_html_domain(postman or self.get_root_postman())

    def get_html_domain_all(self, postman=None):
        return JmModuleConfig.get_html_domain_all(postman or self.get_root_postman())

    def get_domain_list(self):
        return self.domain_list

    def set_domain_list(self, domain_list: List[str]):
        self.domain_list = domain_list

    # noinspection PyUnusedLocal
    def fallback(self, request, url, domain_index, retry_count, **kwargs):
        msg = f"请求重试全部失败: [{url}], {self.domain_list}"
        jm_debug('req.fallback', msg)
        ExceptionTool.raises(msg)

    # noinspection PyMethodMayBeStatic
    def append_params_to_url(self, url, params):
        from urllib.parse import urlencode

        # 将参数字典编码为查询字符串
        query_string = urlencode(params)
        url = f"{url}?{query_string}"
        return url

    # noinspection PyMethodMayBeStatic
    def decode(self, url: str):
        if not JmModuleConfig.decode_url_when_debug or '/search/' not in url:
            return url

        from urllib.parse import unquote
        return unquote(url.replace('+', ' '))


# 基于网页实现的JmClient
class JmHtmlClient(AbstractJmClient):
    client_key = 'html'

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        # 参数校验
        album_id = JmcomicText.parse_to_photo_id(album_id)

        # 请求
        resp = self.get_jm_html(f"/album/{album_id}")

        # 用 JmcomicText 解析 html，返回实体类
        return JmcomicText.analyse_jm_album_html(resp.text)

    def get_photo_detail(self, photo_id, fetch_album=True) -> JmPhotoDetail:
        # 参数校验
        photo_id = JmcomicText.parse_to_photo_id(photo_id)

        # 请求
        resp = self.get_jm_html(f"/photo/{photo_id}")

        # 用 JmcomicText 解析 html，返回实体类
        photo = JmcomicText.analyse_jm_photo_html(resp.text)

        # 一并获取该章节的所处本子
        if fetch_album is True:
            photo.from_album = self.get_album_detail(photo.album_id)

        return photo

    def search(self,
               search_query: str,
               page: int,
               main_tag: int,
               order_by: str,
               date: str,
               ) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': date,
        }

        resp = self.get_jm_html(
            self.append_params_to_url('/search/photos', params),
            allow_redirects=True,
        )

        # 检查是否发生了重定向
        # 因为如果搜索的是禁漫车号，会直接跳转到本子详情页面
        if resp.redirect_count != 0 and '/album/' in resp.url:
            album = JmcomicText.analyse_jm_album_html(resp.text)
            return JmSearchPage.wrap_single_album(album)
        else:
            return JmcomicText.analyse_jm_search_html(resp.text)

    # -- 帐号管理 --

    def login(self,
              username,
              password,
              refresh_client_cookies=True,
              id_remember='on',
              login_remember='on',
              ):

        data = {
            'username': username,
            'password': password,
            'id_remember': id_remember,
            'login_remember': login_remember,
            'submit_login': '',
        }

        resp = self.post('/login',
                         data=data,
                         allow_redirects=False,
                         )

        if resp.status_code != 301:
            ExceptionTool.raises_resp(f'登录失败，状态码为{resp.status_code}', resp)

        if refresh_client_cookies is True:
            self['cookies'] = resp.cookies

        return resp

    def get_jm_html(self, url, require_200=True, **kwargs):
        """
        请求禁漫网页的入口
        """
        resp = self.get(url, **kwargs)

        if require_200 is True and resp.status_code != 200:
            # 检查是否是特殊的状态码（JmModuleConfig.JM_ERROR_STATUS_CODE）
            # 如果是，直接抛出异常
            self.check_special_http_code(resp)
            # 运行到这里说明上一步没有抛异常，说明是未知状态码，抛异常兜底处理
            self.raise_request_error(resp)

        # 检查请求是否成功
        self.require_resp_success_else_raise(resp, url)

        return resp

    @classmethod
    def raise_request_error(cls, resp, msg: Optional[str] = None):
        """
        请求如果失败，统一由该方法抛出异常
        """
        if msg is None:
            msg = f"请求失败，" \
                  f"响应状态码为{resp.status_code}，" \
                  f"URL=[{resp.url}]，" \
                  + (f"响应文本=[{resp.text}]" if len(resp.text) < 200 else
                     f'响应文本过长(len={len(resp.text)})，不打印'
                     )

        ExceptionTool.raises_resp(msg, resp)

    def album_comment(self,
                      video_id,
                      comment,
                      originator='',
                      status='true',
                      comment_id=None,
                      **kwargs,
                      ) -> JmAcResp:
        data = {
            'video_id': video_id,
            'comment': comment,
            'originator': originator,
            'status': status,
        }

        # 处理回复评论
        if comment_id is not None:
            data.pop('status')
            data['comment_id'] = comment_id
            data['is_reply'] = 1
            data['forum_subject'] = 1

        jm_debug('album.comment',
                 f'{video_id}: [{comment}]' +
                 (f' to ({comment_id})' if comment_id is not None else '')
                 )

        resp = self.post('https://18comic.vip/ajax/album_comment',
                         headers=JmModuleConfig.album_comment_headers,
                         data=data,
                         )

        ret = JmAcResp(resp)
        jm_debug('album.comment', f'{video_id}: [{comment}] ← ({ret.model().cid})')

        return ret

    @classmethod
    def require_resp_success_else_raise(cls, resp, org_req_url: str):
        """
        @param resp: 响应对象
        @param org_req_url: /photo/12412312
        """
        # 1. 检查是否 album_missing
        error_album_missing = '/error/album_missing'
        if resp.url.endswith(error_album_missing) and not org_req_url.endswith(error_album_missing):
            ExceptionTool.raise_missing(resp, org_req_url)

        # 2. 是否是特殊的内容
        cls.check_special_text(resp)

    @classmethod
    def check_special_text(cls, resp):
        html = resp.text
        url = resp.url

        if len(html) > 500:
            return

        for content, reason in JmModuleConfig.JM_ERROR_RESPONSE_TEXT.items():
            if content not in html:
                continue

            cls.raise_request_error(
                resp,
                f'{reason}'
                + (f': {url}' if url is not None else '')
            )

    @classmethod
    def check_special_http_code(cls, resp):
        code = resp.status_code
        url = resp.url

        error_msg = JmModuleConfig.JM_ERROR_STATUS_CODE.get(int(code), None)
        if error_msg is None:
            return

        cls.raise_request_error(
            resp,
            f"请求失败，"
            f"响应状态码为{code}，"
            f'原因为: [{error_msg}], '
            + (f'URL=[{url}]' if url is not None else '')
        )


# 基于禁漫移动端（APP）实现的JmClient
class JmApiClient(AbstractJmClient):
    client_key = 'api'
    API_SEARCH = '/search'
    API_ALBUM = '/album'
    API_CHAPTER = '/chapter'
    API_SCRAMBLE = '/chapter_view_template'

    def search(self,
               search_query: str,
               page: int,
               main_tag: int,
               order_by: str,
               time: str,
               ) -> JmSearchPage:
        resp = self.get_decode(
            self.API_SEARCH,
            params={
                'search_query': search_query,
                'main_tag': main_tag,
                'page': page,
                'o': order_by,
                't': time,
            }
        )

        # 直接搜索禁漫车号，发生重定向的响应数据 resp.model_data
        # {
        #   "search_query": "310311",
        #   "total": 1,
        #   "redirect_aid": "310311",
        #   "content": []
        # }
        data = resp.model_data
        if data.get('redirect_aid', None) is not None:
            aid = data.redirect_aid
            return JmSearchPage.wrap_single_album(self.get_album_detail(aid))

        return JmcomicSearchTool.parse_api_resp_to_page(data)

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        return self.fetch_detail_entity(album_id,
                                        JmModuleConfig.album_class(),
                                        )

    def get_photo_detail(self, photo_id, fetch_album=True) -> JmPhotoDetail:
        photo: JmPhotoDetail = self.fetch_detail_entity(photo_id,
                                                        JmModuleConfig.photo_class(),
                                                        )
        self.fetch_photo_additional_field(photo, fetch_album)
        return photo

    def get_scramble_id(self, photo_id):
        """
        带有缓存的fetch_scramble_id，缓存位于JmModuleConfig.SCRAMBLE_CACHE
        """
        cache = JmModuleConfig.SCRAMBLE_CACHE
        if photo_id in cache:
            return cache[photo_id]

        scramble_id = self.fetch_scramble_id(photo_id)
        cache[photo_id] = scramble_id
        return scramble_id

    def fetch_detail_entity(self, apid, clazz, **kwargs):
        """
        请求实体类
        """
        apid = JmcomicText.parse_to_album_id(apid)
        url = self.API_ALBUM if issubclass(clazz, JmAlbumDetail) else self.API_CHAPTER
        resp = self.get_decode(
            url,
            params={
                'id': apid,
                **kwargs,
            }
        )

        self.require_resp_success(resp, url)

        return JmApiAdaptTool.parse_entity(resp.res_data, clazz)

    def fetch_scramble_id(self, photo_id):
        """
        请求scramble_id
        """
        photo_id: str = JmcomicText.parse_to_photo_id(photo_id)
        resp = self.get_decode(
            self.API_SCRAMBLE,
            params={
                "id": photo_id,
                "mode": "vertical",
                "page": "0",
                "app_img_shunt": "NaN",
            }
        )

        match = JmcomicText.pattern_html_album_scramble_id.search(resp.text)

        if match is not None:
            scramble_id = match[1]
        else:
            jm_debug('api.scramble', '未从响应中匹配到scramble_id，返回默认值220980')
            scramble_id = '220980'

        return scramble_id

    def fetch_photo_additional_field(self, photo: JmPhotoDetail, fetch_album: bool):
        """
        获取章节的额外信息
        1. scramble_id
        2. album

        这里的难点是，是否要采用异步的方式并发请求。
        """
        aid = photo.album_id
        pid = photo.photo_id
        scramble_cache = JmModuleConfig.SCRAMBLE_CACHE

        if fetch_album is False and pid in scramble_cache:
            # 不用发请求，直接返回
            photo.scramble_id = scramble_cache[pid]
            return

        if fetch_album is True and pid not in scramble_cache:
            # 要发起两个请求，这里实现很简易，直接排队请求
            # todo: 改进实现
            # 1. 直接开两个线程跑
            # 2. 开两个线程，但是开之前检查重复性
            # 3. 线程池，也要检查重复性
            # 23做法要改不止一处地方
            photo.from_album = self.get_scramble_id(pid)
            photo.scramble_id = self.get_album_detail(aid)
            return

        if fetch_album is True:
            photo.from_album = self.get_album_detail(aid)
        else:
            photo.scramble_id = self.get_scramble_id(pid)

    def get_decode(self, url, **kwargs) -> JmApiResp:
        # set headers
        headers, key_ts = self.headers_key_ts
        kwargs.setdefault('headers', headers)

        resp = super().get(url, **kwargs)
        return JmApiResp.wrap(resp, key_ts)

    @property
    def headers_key_ts(self):
        key_ts = time_stamp()
        import hashlib
        token = hashlib.md5(f"{key_ts}{JmModuleConfig.MAGIC_18COMICAPPCONTENT}".encode()).hexdigest()
        return {
            "token": token,
            "tokenparam": f"{key_ts},1.5.2",
            "user-agent": "okhttp/3.12.1",
            "accept-encoding": "gzip",
        }, key_ts

    def debug_topic_request(self):
        return 'api'

    @classmethod
    def require_resp_success(cls, resp: JmApiResp, org_req_url: str):
        resp.require_success()

        # 1. 检查是否 album_missing
        # json: {'code': 200, 'data': []}
        data = resp.model().data
        if isinstance(data, list) and len(data) == 0:
            ExceptionTool.raise_missing(resp, org_req_url)

        # 2. 是否是特殊的内容
        # 暂无


JmModuleConfig.register_client(JmHtmlClient)
JmModuleConfig.register_client(JmApiClient)
