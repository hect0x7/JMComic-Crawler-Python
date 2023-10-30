from .jm_client_interface import *


# 抽象基类，实现了域名管理，发请求，重试机制，debug，缓存等功能
class AbstractJmClient(
    JmcomicClient,
    PostmanProxy,
):
    client_key = '__just_for_placeholder_do_not_use_me__'
    func_to_cache = []

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

        def judge(resp):
            """
            使用此方法包装 self.get，使得图片数据为空时，判定为请求失败时，走重试逻辑
            """
            resp = JmImageResp(resp)
            resp.require_success()
            return resp

        return self.get(img_url, judge=judge)

    def request_with_retry(self,
                           request,
                           url,
                           domain_index=0,
                           retry_count=0,
                           judge=lambda resp: resp,
                           **kwargs,
                           ):
        """
        统一请求，支持重试
        :param request: 请求方法
        :param url: 图片url / path (/album/xxx)
        :param domain_index: 域名下标
        :param retry_count: 重试次数
        :param judge: 判定响应是否成功
        :param kwargs: 请求方法的kwargs
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
            resp = request(url, **kwargs)
            return judge(resp)
        except Exception as e:
            self.before_retry(e, kwargs, retry_count, url)

        if retry_count < self.retry_times:
            return self.request_with_retry(request, url, domain_index, retry_count + 1, judge, **kwargs)
        else:
            return self.request_with_retry(request, url, domain_index + 1, 0, judge, **kwargs)

    # noinspection PyMethodMayBeStatic
    def debug_topic_request(self):
        return self.client_key

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def before_retry(self, e, kwargs, retry_count, url):
        jm_debug('req.error', str(e))

    def enable_cache(self, debug=False):
        if self.is_cache_enabled():
            return

        def wrap_func_with_cache(func_name, cache_field_name):
            if hasattr(self, cache_field_name):
                return

            if sys.version_info > (3, 9):
                import functools
                cache = functools.cache
            else:
                from functools import lru_cache
                cache = lru_cache()

            func = getattr(self, func_name)
            setattr(self, func_name, cache(func))

        for func_name in self.func_to_cache:
            wrap_func_with_cache(func_name, f'__{func_name}.cache.dict__')

        setattr(self, '__enable_cache__', True)

    def is_cache_enabled(self) -> bool:
        return getattr(self, '__enable_cache__', False)

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

    func_to_cache = ['search', 'fetch_detail_entity']

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        return self.fetch_detail_entity(album_id, 'album')

    def get_photo_detail(self,
                         photo_id,
                         fetch_album=True,
                         fetch_scramble_id=True,
                         ) -> JmPhotoDetail:
        photo = self.fetch_detail_entity(photo_id, 'photo')

        # 一并获取该章节的所处本子
        # todo: 可优化，获取章节所在本子，其实不需要等待章节获取完毕后。
        #  可以直接调用 self.get_album_detail(photo_id)，会重定向返回本子的HTML
        if fetch_album is True:
            photo.from_album = self.get_album_detail(photo.album_id)

        return photo

    def fetch_detail_entity(self, apid, prefix):
        # 参数校验
        apid = JmcomicText.parse_to_jm_id(apid)

        # 请求
        resp = self.get_jm_html(f"/{prefix}/{apid}")

        # 用 JmcomicText 解析 html，返回实体类
        if prefix == 'album':
            return JmcomicText.analyse_jm_album_html(resp.text)

        if prefix == 'photo':
            return JmcomicText.analyse_jm_photo_html(resp.text)

    def search(self,
               search_query: str,
               page: int,
               main_tag: int,
               order_by: str,
               time: str,
               ) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
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

        resp = self.post('/ajax/album_comment',
                         headers=JmModuleConfig.album_comment_headers,
                         data=data,
                         )

        ret = JmAcResp(resp)
        jm_debug('album.comment', f'{video_id}: [{comment}] ← ({ret.model().cid})')

        return ret

    @classmethod
    def require_resp_success_else_raise(cls, resp, orig_req_url: str):
        """
        :param resp: 响应对象
        :param orig_req_url: /photo/12412312
        """
        # 1. 检查是否 album_missing
        error_album_missing = '/error/album_missing'
        if resp.url.endswith(error_album_missing) and not orig_req_url.endswith(error_album_missing):
            ExceptionTool.raise_missing(resp, orig_req_url)

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
    func_to_cache = ['search', 'fetch_detail_entity']

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
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
        }

        resp = self.get_decode(self.append_params_to_url(self.API_SEARCH, params))

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

        return JmSearchTool.parse_api_resp_to_page(data)

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        return self.fetch_detail_entity(album_id,
                                        JmModuleConfig.album_class(),
                                        )

    def get_photo_detail(self,
                         photo_id,
                         fetch_album=True,
                         fetch_scramble_id=True,
                         ) -> JmPhotoDetail:
        photo: JmPhotoDetail = self.fetch_detail_entity(photo_id,
                                                        JmModuleConfig.photo_class(),
                                                        )
        if fetch_album or fetch_scramble_id:
            self.fetch_photo_additional_field(photo, fetch_album, fetch_scramble_id)

        return photo

    def get_scramble_id(self, photo_id, album_id=None):
        """
        带有缓存的fetch_scramble_id，缓存位于JmModuleConfig.SCRAMBLE_CACHE
        """
        cache = JmModuleConfig.SCRAMBLE_CACHE
        if photo_id in cache:
            return cache[photo_id]

        if album_id is not None and album_id in cache:
            return cache[album_id]

        scramble_id = self.fetch_scramble_id(photo_id)
        cache[photo_id] = scramble_id
        if album_id is not None:
            cache[album_id] = scramble_id

        return scramble_id

    def fetch_detail_entity(self, apid, clazz):
        """
        请求实体类
        """
        apid = JmcomicText.parse_to_jm_id(apid)
        url = self.API_ALBUM if issubclass(clazz, JmAlbumDetail) else self.API_CHAPTER
        resp = self.get_decode(
            url,
            params={
                'id': apid,
            }
        )

        self.require_resp_success(resp, url)

        return JmApiAdaptTool.parse_entity(resp.res_data, clazz)

    def fetch_scramble_id(self, photo_id):
        """
        请求scramble_id
        """
        photo_id: str = JmcomicText.parse_to_jm_id(photo_id)
        resp = self.get_decode(
            self.API_SCRAMBLE,
            params={
                "id": photo_id,
                "mode": "vertical",
                "page": "0",
                "app_img_shunt": "1",
            }
        )

        match = JmcomicText.pattern_html_album_scramble_id.search(resp.text)

        if match is not None:
            scramble_id = match[1]
        else:
            jm_debug('api.scramble', '未从响应中匹配到scramble_id，返回默认值220980')
            scramble_id = '220980'

        return scramble_id

    def fetch_photo_additional_field(self, photo: JmPhotoDetail, fetch_album: bool, fetch_scramble_id: bool):
        """
        获取章节的额外信息
        1. scramble_id
        2. album
        如果都需要获取，会排队，效率低

        todo: 改进实现
        1. 直接开两个线程跑
        2. 开两个线程，但是开之前检查重复性
        3. 线程池，也要检查重复性
        23做法要改不止一处地方
        """
        if fetch_album:
            photo.from_album = self.get_album_detail(photo.album_id)

        if fetch_scramble_id:
            # 同album的scramble_id相同
            photo.scramble_id = self.get_scramble_id(photo.photo_id, photo.album_id)

    def setting(self) -> JmApiResp:
        """
        禁漫app的setting请求，返回如下内容（resp.res_data）
        {
          "logo_path": "https://cdn-msp.jmapiproxy1.monster/media/logo/new_logo.png",
          "main_web_host": "18-comic.work",
          "img_host": "https://cdn-msp.jmapiproxy1.monster",
          "base_url": "https://www.jmapinode.biz",
          "is_cn": 0,
          "cn_base_url": "https://www.jmapinode.biz",
          "version": "1.6.0",
          "test_version": "1.6.1",
          "store_link": "https://play.google.com/store/apps/details?id=com.jiaohua_browser",
          "ios_version": "1.6.0",
          "ios_test_version": "1.6.1",
          "ios_store_link": "https://18comic.vip/stray/",
          "ad_cache_version": 1698140798,
          "bundle_url": "https://18-comic.work/static/apk/patches1.6.0.zip",
          "is_hot_update": true,
          "api_banner_path": "https://cdn-msp.jmapiproxy1.monster/media/logo/channel_log.png?v=",
          "version_info": "\nAPP & IOS更新\nV1.6.0\n#禁漫 APK 更新拉!!\n更新調整以下項目\n1. 系統優化\n\nV1.5.9\n1. 跳錯誤新增 重試 網頁 按鈕\n2. 圖片讀取優化\n3.
          線路調整優化\n\n無法順利更新或是系統題是有風險請使用下方\n下載點2\n有問題可以到DC群反饋\nhttps://discord.gg/V74p7HM\n",
          "app_shunts": [
            {
              "title": "圖源1",
              "key": 1
            },
            {
              "title": "圖源2",
              "key": 2
            },
            {
              "title": "圖源3",
              "key": 3
            },
            {
              "title": "圖源4",
              "key": 4
            }
          ],
          "download_url": "https://18-comic.work/static/apk/1.6.0.apk",
          "app_landing_page": "https://jm365.work/pXYbfA",
          "float_ad": true
        }
        """
        resp = self.get_decode('/setting')
        return resp

    def login(self,
              username,
              password,
              refresh_client_cookies=True,
              id_remember='on',
              login_remember='on',
              ):
        jm_debug('api.login', '禁漫移动端无需登录，调用login不会做任何操作')
        pass

    def get_decode(self, url, **kwargs) -> JmApiResp:
        # set headers
        headers, key_ts = self.headers_key_ts
        kwargs['headers'] = headers

        resp = self.get(url, **kwargs)
        return JmApiResp.wrap(resp, key_ts)

    @property
    def headers_key_ts(self):
        key_ts = time_stamp()
        return JmModuleConfig.new_api_headers(key_ts), key_ts

    def debug_topic_request(self):
        return 'api'

    @classmethod
    def require_resp_success(cls, resp: JmApiResp, orig_req_url: str):
        resp.require_success()

        # 1. 检查是否 album_missing
        # json: {'code': 200, 'data': []}
        data = resp.model().data
        if isinstance(data, list) and len(data) == 0:
            ExceptionTool.raise_missing(resp, orig_req_url)

        # 2. 是否是特殊的内容
        # 暂无

    @classmethod
    @field_cache('__init_cookies__')
    def fetch_init_cookies(cls, client: 'JmApiClient'):
        resp = client.setting()
        return dict(resp.resp.cookies)

    def after_init(self):
        cookies = self.__class__.fetch_init_cookies(self)
        self.get_root_postman().get_meta_data()['cookies'] = cookies


class FutureClientProxy(JmcomicClient):
    """
    在Client上做了一层线程池封装来实现异步，对外仍然暴露JmcomicClient的接口，可以看作Client的代理。
    除了使用线程池做异步，还通过加锁和缓存结果，实现同一个请求不会被多个线程发出，减少开销

    可通过插件 ClientProxyPlugin 启用本类，配置如下:
    ```yml
    plugins:
      after_init:
        - plugin: client_proxy
          kwargs:
            proxy_client_key: cl_proxy_future
    ```
    """
    client_key = 'cl_proxy_future'
    proxy_methods = ['album_comment', 'enable_cache', 'get_domain_list',
                     'get_html_domain', 'get_html_domain_all', 'get_jm_image',
                     'is_cache_enabled', 'set_domain_list', ]

    class FutureWrapper:
        def __init__(self, future):
            from concurrent.futures import Future
            future: Future
            self.future = future
            self.done = False
            self._result = None

        def result(self):
            if not self.done:
                result = self.future.result()
                self._result = result
                self.done = True
                self.future = None  # help gc

            return self._result

    def __init__(self,
                 client: JmcomicClient,
                 max_workers=None,
                 executors=None,
                 ):
        self.client = client
        for method in self.proxy_methods:
            setattr(self, method, getattr(client, method))

        if executors is None:
            from concurrent.futures import ThreadPoolExecutor
            executors = ThreadPoolExecutor(max_workers)

        self.executors = executors
        self.future_dict: Dict[str, FutureClientProxy.FutureWrapper] = {}
        from threading import Lock
        self.lock = Lock()

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        album_id = JmcomicText.parse_to_jm_id(album_id)
        cache_key = f'album_{album_id}'
        future = self.get_future(cache_key, task=lambda: self.client.get_album_detail(album_id))
        return future.result()

    def get_future(self, cache_key, task):
        if cache_key in self.future_dict:
            return self.future_dict[cache_key]

        with self.lock:
            if cache_key in self.future_dict:
                return self.future_dict[cache_key]

            future = self.FutureWrapper(self.executors.submit(task))
            self.future_dict[cache_key] = future
            return future

    def get_photo_detail(self, photo_id, fetch_album=True, fetch_scramble_id=True) -> JmPhotoDetail:
        photo_id = JmcomicText.parse_to_jm_id(photo_id)
        client: JmcomicClient = self.client
        futures = [None, None, None]
        results = [None, None, None]

        # photo_detail
        photo_future = self.get_future(f'photo_{photo_id}',
                                       lambda: client.get_photo_detail(photo_id,
                                                                       False,
                                                                       False)
                                       )
        futures[0] = photo_future

        # fetch_album
        if fetch_album:
            album_future = self.get_future(f'album_{photo_id}',
                                           lambda: client.get_album_detail(photo_id))
            futures[1] = album_future
        else:
            results[1] = None

        # fetch_scramble_id
        if fetch_scramble_id and isinstance(client, JmApiClient):
            client: JmApiClient
            scramble_future = self.get_future(f'scramble_id_{photo_id}',
                                              lambda: client.get_scramble_id(photo_id))
            futures[2] = scramble_future
        else:
            results[2] = ''

        # wait finish
        for i, f in enumerate(futures):
            if f is None:
                continue
            results[i] = f.result()

        # compose
        photo: JmPhotoDetail = results[0]
        album = results[1]
        scramble_id = results[2]

        if album is not None:
            photo.from_album = album
        if scramble_id != '':
            photo.scramble_id = scramble_id

        return photo

    def search(self, search_query: str, page: int, main_tag: int, order_by: str, time: str) -> JmSearchPage:
        cache_key = f'search_query_{search_query}_page_{page}_main_tag_{main_tag}_order_by_{order_by}_time_{time}'
        future = self.get_future(cache_key, task=lambda: self.client.search(search_query, page, main_tag, order_by, time))
        return future.result()
