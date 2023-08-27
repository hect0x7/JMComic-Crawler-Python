from .jm_client_interface import *


# noinspection PyAbstractClass
class AbstractJmClient(
    JmcomicClient,
    PostmanProxy,
):

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

    def get(self, url, **kwargs):
        return self.request_with_retry(self.postman.get, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request_with_retry(self.postman.post, url, **kwargs)

    def of_api_url(self, api_path, domain):
        return JmcomicText.format_url(api_path, domain)

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
            jm_debug(self.debug_topic_request(), url)
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
        return 'html'

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def before_retry(self, e, kwargs, retry_count, url):
        jm_debug('req.err', str(e))

    def enable_cache(self, debug=False):
        def wrap_func_cache(func_name, cache_dict_name):
            import common
            if common.VERSION > '0.4.8':
                if hasattr(self, cache_dict_name):
                    return

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
                if sys.version_info < (3, 9):
                    raise NotImplementedError('不支持启用JmcomicClient缓存。\n'
                                              '请更新python版本到3.9以上，'
                                              '或更新commonX: `pip install commonX --upgrade`')
                import functools
                cache = functools.cache

            # 重载本对象的方法
            func = getattr(self, func_name)
            wrap_func = cache(func)

            setattr(self, func_name, wrap_func)

        for func in {
            'get_photo_detail',
            'get_album_detail',
            'search_album',
        }:
            wrap_func_cache(func, func + '.cache.dict')

        setattr(self, '__enable_cache__', True)

    def is_cache_enabled(self) -> bool:
        return getattr(self, '__enable_cache__', False)

    def get_jmcomic_url(self, postman=None):
        return JmModuleConfig.get_jmcomic_url(postman or self.get_root_postman())

    def get_jmcomic_domain_all(self, postman=None):
        return JmModuleConfig.get_jmcomic_domain_all(postman or self.get_root_postman())

    # noinspection PyUnusedLocal
    def fallback(self, request, url, domain_index, retry_count, **kwargs):
        msg = f"请求重试全部失败: [{url}], {self.domain_list}"
        jm_debug('req.fallback', msg)
        raise JmModuleConfig.exception(msg)


# 基于网页实现的JmClient
class JmHtmlClient(AbstractJmClient):

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

    def search_album(self, search_query, main_tag=0, page=1) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
        }

        resp = self.get_jm_html('/search/photos', params=params, allow_redirects=True)

        # 检查是否发生了重定向
        # 因为如果搜索的是禁漫车号，会直接跳转到本子详情页面
        if resp.redirect_count != 0 and '/album/' in resp.url:
            album = JmcomicText.analyse_jm_album_html(resp.text)
            return JmSearchPage.wrap_single_album(album)
        else:
            return JmSearchSupport.analyse_jm_search_html(resp.text)

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
            raise JmModuleConfig.exception(f'登录失败，状态码为{resp.status_code}')

        if refresh_client_cookies is True:
            self['cookies'] = resp.cookies

        return resp

    def get_jm_html(self, url, require_200=True, **kwargs):
        """
        请求禁漫网页的入口
        """
        resp = self.get(url, **kwargs)

        if require_200 is True and resp.status_code != 200:
            # write_text('./resp.html', resp.text)
            self.check_special_http_code(resp)
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
        raise JmModuleConfig.exception(msg)

    def get_jm_image(self, img_url) -> JmImageResp:

        def get_if_fail_raise(url):
            """
            使用此方法包装 self.get
            """
            resp = JmImageResp(self.get(url))

            if resp.is_success:
                return resp

            self.raise_request_error(
                resp.resp, resp.get_error_msg()
            )

            return resp

        return self.request_with_retry(get_if_fail_raise, img_url)

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
    def require_resp_success_else_raise(cls, resp, req_url):
        # 1. 检查是否 album_missing
        error_album_missing = '/error/album_missing'
        if resp.url.endswith(error_album_missing) and not req_url.endswith(error_album_missing):
            cls.raise_request_error(
                resp,
                f'请求的本子不存在！({req_url})\n'
                '原因可能为:\n'
                '1. id有误，检查你的本子/章节id\n'
                '2. 该漫画只对登录用户可见，请配置你的cookies\n'
            )

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

            write_text('./resp.html', html)
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


class JmApiClient(AbstractJmClient):
    API_SEARCH = '/search'

    def search_album(self, search_query, main_tag=0, page=1) -> JmApiResp:
        """
        model_data: {
          "search_query": "MANA",
          "total": "177",
          "content": [
            {
              "id": "441923",
              "author": "MANA",
              "description": "",
              "name": "[MANA] 神里绫华5",
              "image": "",
              "category": {
                "id": "1",
                "title": "同人"
              },
              "category_sub": {
                "id": "1",
                "title": "同人"
              }
            }
          ]
        }
        """
        return self.get(
            self.API_SEARCH,
            params={
                'search_query': search_query,
                'main_tag': main_tag,
                'page': page,
            }
        )

    def get(self, url, **kwargs) -> JmApiResp:
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


class AsyncSaveImageClient(JmImageClient):

    def __init__(self, workers=None) -> None:
        from concurrent.futures import ThreadPoolExecutor, Future
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.future_list: List[Future] = []

    def save_image_resp(self, *args, **kwargs):
        future = self.executor.submit(lambda: super().save_image_resp(*args, **kwargs))
        self.future_list.append(future)


JmModuleConfig.CLASS_CLIENT_IMPL['html'] = JmHtmlClient
JmModuleConfig.CLASS_CLIENT_IMPL['api'] = JmApiClient
