from threading import Lock

from .jm_client_interface import *


# 抽象基类，实现了域名管理，发请求，重试机制，log，缓存等功能
class AbstractJmClient(
    JmcomicClient,
    PostmanProxy,
):
    client_key = '__just_for_placeholder_do_not_use_me__'
    func_to_cache = []

    def __init__(self,
                 postman: Postman,
                 domain_list: List[str],
                 retry_times=0,
                 domain_retry_strategy=None,
                 ):
        """
        创建JM客户端

        :param postman: 负责实现HTTP请求的对象，持有cookies、headers、proxies等信息
        :param domain_list: 禁漫域名
        :param retry_times: 重试次数
        """
        super().__init__(postman)
        self.retry_times = retry_times
        self.domain_list = domain_list
        self.domain_retry_strategy = domain_retry_strategy
        self.CLIENT_CACHE = None
        self._username = None  # help for favorite_folder method
        if domain_retry_strategy:
            domain_retry_strategy(self)
        self.enable_cache()
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
        return self.get(img_url, is_image=True, headers=JmModuleConfig.new_html_headers())

    def request_with_retry(self,
                           request,
                           url,
                           domain_index=0,
                           retry_count=0,
                           is_image=False,
                           **kwargs,
                           ):
        """
        支持重试和切换域名的机制

        如果url包含了指定域名，则不会切换域名，例如图片URL。

        如果需要拿到域名进行回调处理，可以重写 self.update_request_with_specify_domain 方法，例如更新headers

        :param request: 请求方法
        :param url: 图片url / path (/album/xxx)
        :param domain_index: 域名下标
        :param retry_count: 重试次数
        :param is_image: 是否是图片请求
        :param kwargs: 请求方法的kwargs
        """
        if self.domain_retry_strategy:
            return self.domain_retry_strategy(self,
                                              request,
                                              url,
                                              is_image,
                                              **kwargs,
                                              )

        if domain_index >= len(self.domain_list):
            return self.fallback(request, url, domain_index, retry_count, is_image, **kwargs)

        url_backup = url

        if url.startswith('/'):
            # path → url
            domain = self.domain_list[domain_index]
            url = self.of_api_url(url, domain)

            self.update_request_with_specify_domain(kwargs, domain, is_image)

            jm_log(self.log_topic(), self.decode(url))
        elif is_image:
            # 图片url
            self.update_request_with_specify_domain(kwargs, None, is_image)

        if domain_index != 0 or retry_count != 0:
            jm_log(f'req.retry',
                   ', '.join([
                       f'次数: [{retry_count}/{self.retry_times}]',
                       f'域名: [{domain_index} of {self.domain_list}]',
                       f'路径: [{url}]',
                       f'参数: [{kwargs if "login" not in url else "#login_form#"}]'
                   ])
                   )

        try:
            resp = request(url, **kwargs)
            # 在最后返回之前，还可以判断resp是否重试
            resp = self.raise_if_resp_should_retry(resp, is_image)
            return resp
        except Exception as e:
            if self.retry_times == 0:
                raise e

            self.before_retry(e, kwargs, retry_count, url)

        if retry_count < self.retry_times:
            return self.request_with_retry(request, url_backup, domain_index, retry_count + 1, is_image, **kwargs)
        else:
            return self.request_with_retry(request, url_backup, domain_index + 1, 0, is_image, **kwargs)

    # noinspection PyMethodMayBeStatic
    def raise_if_resp_should_retry(self, resp, is_image):
        """
        依然是回调，在最后返回之前，还可以判断resp是否重试
        """
        if is_image is True:
            resp = JmImageResp(resp)
            resp.require_success()

        return resp

    def update_request_with_specify_domain(self, kwargs: dict, domain: Optional[str], is_image: bool = False):
        """
        域名自动切换时，用于更新请求参数的回调
        """
        pass

    # noinspection PyMethodMayBeStatic
    def log_topic(self):
        return self.client_key

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def before_retry(self, e, kwargs, retry_count, url):
        jm_log('req.error', str(e))

    def enable_cache(self):
        # noinspection PyDefaultArgument,PyShadowingBuiltins
        def make_key(args, kwds, typed,
                     kwd_mark=(object(),),
                     fasttypes={int, str},
                     tuple=tuple, type=type, len=len):
            key = args
            if kwds:
                key += kwd_mark
                for item in kwds.items():
                    key += item
            if typed:
                key += tuple(type(v) for v in args)
                if kwds:
                    key += tuple(type(v) for v in kwds.values())
            elif len(key) == 1 and type(key[0]) in fasttypes:
                return key[0]
            return hash(key)

        def wrap_func_with_cache(func_name, cache_field_name):
            if hasattr(self, cache_field_name):
                return

            func = getattr(self, func_name)

            def cache_wrapper(*args, **kwargs):
                cache = self.CLIENT_CACHE

                # Equivalent to not enable cache
                if cache is None:
                    return func(*args, **kwargs)

                key = make_key(args, kwargs, False)
                sentinel = object()  # unique object used to signal cache misses

                result = cache.get(key, sentinel)
                if result is not sentinel:
                    return result

                result = func(*args, **kwargs)
                cache[key] = result
                return result

            setattr(self, func_name, cache_wrapper)

        for func_name in self.func_to_cache:
            wrap_func_with_cache(func_name, f'__{func_name}.cache.dict__')

    def set_cache_dict(self, cache_dict: Optional[Dict]):
        self.CLIENT_CACHE = cache_dict

    def get_cache_dict(self):
        return self.CLIENT_CACHE

    def get_domain_list(self):
        return self.domain_list

    def set_domain_list(self, domain_list: List[str]):
        self.domain_list = domain_list

    # noinspection PyUnusedLocal
    def fallback(self, request, url, domain_index, retry_count, is_image, **kwargs):
        msg = f"请求重试全部失败: [{url}], {self.domain_list}"
        jm_log('req.fallback', msg)
        ExceptionTool.raises(msg, {}, RequestRetryAllFailException)

    # noinspection PyMethodMayBeStatic
    def append_params_to_url(self, url, params):
        from urllib.parse import urlencode

        # 将参数字典编码为查询字符串
        query_string = urlencode(params)
        url = f"{url}?{query_string}"
        return url

    # noinspection PyMethodMayBeStatic
    def decode(self, url: str):
        if not JmModuleConfig.FLAG_DECODE_URL_WHEN_LOGGING or '/search/' not in url:
            return url

        from urllib.parse import unquote
        return unquote(url.replace('+', ' '))


# 基于网页实现的JmClient
class JmHtmlClient(AbstractJmClient):
    client_key = 'html'

    func_to_cache = ['search', 'fetch_detail_entity']

    API_SEARCH = '/search/photos'
    API_CATEGORY = '/albums'

    def add_favorite_album(self,
                           album_id,
                           folder_id='0',
                           ):
        data = {
            'album_id': album_id,
            'fid': folder_id,
        }

        resp = self.get_jm_html(
            '/ajax/favorite_album',
            data=data,
        )

        res = resp.json()

        if res['status'] != 1:
            msg = parse_unicode_escape_text(res['msg'])
            error_msg = PatternTool.match_or_default(msg, JmcomicText.pattern_ajax_favorite_msg, msg)
            # 此圖片已經在您最喜愛的清單！

            self.raise_request_error(
                resp,
                error_msg
            )

        return resp

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
        # (had polished by FutureClientProxy)
        if fetch_album is True:
            photo.from_album = self.get_album_detail(photo.album_id)

        return photo

    def fetch_detail_entity(self, jmid, prefix):
        # 参数校验
        jmid = JmcomicText.parse_to_jm_id(jmid)

        # 请求
        resp = self.get_jm_html(f"/{prefix}/{jmid}")

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
               category: str,
               sub_category: Optional[str],
               ) -> JmSearchPage:
        """
        网页搜索API
        """
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
        }

        url = self.build_search_url(self.API_SEARCH, category, sub_category)

        resp = self.get_jm_html(
            self.append_params_to_url(url, params),
            allow_redirects=True,
        )

        # 检查是否发生了重定向
        # 因为如果搜索的是禁漫车号，会直接跳转到本子详情页面
        if resp.redirect_count != 0 and '/album/' in resp.url:
            album = JmcomicText.analyse_jm_album_html(resp.text)
            return JmSearchPage.wrap_single_album(album)
        else:
            return JmPageTool.parse_html_to_search_page(resp.text)

    @classmethod
    def build_search_url(cls, base: str, category: str, sub_category: Optional[str]):
        """
        构建网页搜索/分类的URL

        示例：
        :param base: "/search/photos"
        :param category CATEGORY_DOUJIN
        :param sub_category SUB_DOUJIN_CG
        :return "/search/photos/doujin/sub/CG"
        """
        if category == JmMagicConstants.CATEGORY_ALL:
            return base

        if sub_category is None:
            return f'{base}/{category}'
        else:
            return f'{base}/{category}/sub/{sub_category}'

    def categories_filter(self,
                          page: int,
                          time: str,
                          category: str,
                          order_by: str,
                          sub_category: Optional[str] = None,
                          ) -> JmCategoryPage:
        params = {
            'page': page,
            'o': order_by,
            't': time,
        }

        url = self.build_search_url(self.API_CATEGORY, category, sub_category)

        resp = self.get_jm_html(
            self.append_params_to_url(url, params),
            allow_redirects=True,
        )

        return JmPageTool.parse_html_to_category_page(resp.text)

    # -- 帐号管理 --

    def login(self,
              username,
              password,
              id_remember='on',
              login_remember='on',
              ):
        """
        返回response响应对象
        """

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

        if resp.status_code != 200:
            ExceptionTool.raises_resp(f'登录失败，状态码为{resp.status_code}', resp)

        orig_cookies = self.get_meta_data('cookies') or {}
        new_cookies = dict(resp.cookies)
        # 重复登录下存在bug，AVS会丢失
        if 'AVS' in orig_cookies and 'AVS' not in new_cookies:
            return resp

        self['cookies'] = new_cookies
        self._username = username

        return resp

    def favorite_folder(self,
                        page=1,
                        order_by=JmMagicConstants.ORDER_BY_LATEST,
                        folder_id='0',
                        username='',
                        ) -> JmFavoritePage:
        if username == '':
            ExceptionTool.require_true(self._username is not None, 'favorite_folder方法需要传username参数')
            username = self._username

        resp = self.get_jm_html(
            f'/user/{username}/favorite/albums',
            params={
                'page': page,
                'o': order_by,
                'folder': folder_id,
            }
        )

        return JmPageTool.parse_html_to_favorite_page(resp.text)

    # noinspection PyTypeChecker
    def get_username_from_cookies(self) -> str:
        # cookies = self.get_meta_data('cookies', None)
        # if not cookies:
        #     ExceptionTool.raises('未登录，无法获取到对应的用户名，请给favorite方法传入username参数')
        # 解析cookies，可能需要用到 phpserialize，比较麻烦，暂不实现
        pass

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

    def update_request_with_specify_domain(self, kwargs: dict, domain: Optional[str], is_image=False):
        if is_image:
            return

        latest_headers = kwargs.get('headers', None)
        base_headers = self.get_meta_data('headers', None) or JmModuleConfig.new_html_headers(domain)
        base_headers.update(latest_headers or {})
        kwargs['headers'] = base_headers

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
                      ) -> JmAlbumCommentResp:
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

        jm_log('album.comment',
               f'{video_id}: [{comment}]' +
               (f' to ({comment_id})' if comment_id is not None else '')
               )

        resp = self.post('/ajax/album_comment', data=data)

        ret = JmAlbumCommentResp(resp)
        jm_log('album.comment', f'{video_id}: [{comment}] ← ({ret.model().cid})')

        return ret

    @classmethod
    def require_resp_success_else_raise(cls, resp, url: str):
        """
        :param resp: 响应对象
        :param url: /photo/12412312
        """
        resp_url: str = resp.url

        # 1. 是否是特殊的内容
        cls.check_special_text(resp)

        # 2. 检查响应发送重定向，重定向url是否表示错误网页，即 /error/xxx
        if resp.redirect_count == 0 or '/error/' not in resp_url:
            return

        # 3. 检查错误类型
        def match_case(error_path):
            return resp_url.endswith(error_path) and not url.endswith(error_path)

        # 3.1 album_missing
        if match_case('/error/album_missing'):
            ExceptionTool.raise_missing(resp, JmcomicText.parse_to_jm_id(url))

        # 3.2 user_missing
        if match_case('/error/user_missing'):
            ExceptionTool.raises_resp('此用戶名稱不存在，或者你没有登录，請再次確認使用名稱', resp)

        # 3.3 invalid_module
        if match_case('/error/invalid_module'):
            ExceptionTool.raises_resp('發生了無法預期的錯誤。若問題持續發生，請聯繫客服支援', resp)

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
                f'{reason}({content})'
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
    API_CATEGORIES_FILTER = '/categories/filter'
    API_ALBUM = '/album'
    API_CHAPTER = '/chapter'
    API_SCRAMBLE = '/chapter_view_template'
    API_FAVORITE = '/favorite'

    def search(self,
               search_query: str,
               page: int,
               main_tag: int,
               order_by: str,
               time: str,
               category: str,
               sub_category: Optional[str],
               ) -> JmSearchPage:
        """
        移动端暂不支持 category和sub_category
        """
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
            'page': page,
            'o': order_by,
            't': time,
        }

        resp = self.req_api(self.append_params_to_url(self.API_SEARCH, params))

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

        return JmPageTool.parse_api_to_search_page(data)

    def categories_filter(self,
                          page: int,
                          time: str,
                          category: str,
                          order_by: str,
                          sub_category: Optional[str] = None,
                          ):
        """
        移动端不支持 sub_category
        """
        # o: mv, mv_m, mv_w, mv_t
        o = f'{order_by}_{time}' if time != JmMagicConstants.TIME_ALL else order_by

        params = {
            'page': page,
            'order': '',  # 该参数为空
            'c': category,
            'o': o,
        }

        resp = self.req_api(self.append_params_to_url(self.API_CATEGORIES_FILTER, params))

        return JmPageTool.parse_api_to_search_page(resp.model_data)

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
        带有缓存的fetch_scramble_id，缓存位于 JmModuleConfig.SCRAMBLE_CACHE
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

    def fetch_detail_entity(self, jmid, clazz):
        """
        请求实体类
        """
        jmid = JmcomicText.parse_to_jm_id(jmid)
        url = self.API_ALBUM if issubclass(clazz, JmAlbumDetail) else self.API_CHAPTER
        resp = self.req_api(self.append_params_to_url(
            url,
            {
                'id': jmid
            })
        )

        if resp.res_data.get('name') is None:
            ExceptionTool.raise_missing(resp, jmid)

        return JmApiAdaptTool.parse_entity(resp.res_data, clazz)

    def fetch_scramble_id(self, photo_id):
        """
        请求scramble_id
        """
        photo_id: str = JmcomicText.parse_to_jm_id(photo_id)
        resp = self.req_api(
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

        scramble_id = PatternTool.match_or_default(resp.text,
                                                   JmcomicText.pattern_html_album_scramble_id,
                                                   None,
                                                   )
        if scramble_id is None:
            jm_log('api.scramble', f'未匹配到scramble_id，响应文本：{resp.text}')
            scramble_id = str(JmMagicConstants.SCRAMBLE_220980)

        return scramble_id

    def fetch_photo_additional_field(self, photo: JmPhotoDetail, fetch_album: bool, fetch_scramble_id: bool):
        """
        获取章节的额外信息
        1. scramble_id
        2. album
        如果都需要获取，会排队，效率低

        todo: 改进实现 (had polished by FutureClientProxy)
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
        resp = self.req_api('/setting')

        # 检查禁漫最新的版本号
        setting_ver = str(resp.model_data.version)
        # 禁漫接口的版本 > jmcomic库内置版本
        if setting_ver > JmMagicConstants.APP_VERSION and JmModuleConfig.FLAG_USE_VERSION_NEWER_IF_BEHIND:
            jm_log('api.setting', f'change APP_VERSION from [{JmMagicConstants.APP_VERSION}] to [{setting_ver}]')
            JmMagicConstants.APP_VERSION = setting_ver

        return resp

    def login(self,
              username,
              password,
              ) -> JmApiResp:
        """
        {
          "uid": "123",
          "username": "x",
          "email": "x",
          "emailverified": "yes",
          "photo": "x",
          "fname": "",
          "gender": "x",
          "message": "Welcome x!",
          "coin": 123,
          "album_favorites": 123,
          "s": "x",
          "level_name": "x",
          "level": 1,
          "nextLevelExp": 123,
          "exp": "123",
          "expPercent": 123,
          "badges": [],
          "album_favorites_max": 123
        }

        """
        resp = self.req_api('/login', False, data={
            'username': username,
            'password': password,
        })

        cookies = dict(resp.resp.cookies)
        cookies.update({'AVS': resp.res_data['s']})
        self['cookies'] = cookies

        return resp

    def favorite_folder(self,
                        page=1,
                        order_by=JmMagicConstants.ORDER_BY_LATEST,
                        folder_id='0',
                        username='',
                        ) -> JmFavoritePage:
        resp = self.req_api(
            self.API_FAVORITE,
            params={
                'page': page,
                'folder_id': folder_id,
                'o': order_by,
            }
        )

        return JmPageTool.parse_api_to_favorite_page(resp.model_data)

    def add_favorite_album(self,
                           album_id,
                           folder_id='0',
                           ):
        """
        移动端没有提供folder_id参数
        """
        resp = self.req_api(
            '/favorite',
            data={
                'aid': album_id,
            },
        )

        self.require_resp_status_ok(resp)

        return resp

    # noinspection PyMethodMayBeStatic
    def require_resp_status_ok(self, resp: JmApiResp):
        """
        检查返回数据中的status字段是否为ok
        """
        data = resp.model_data
        if data.status != 'ok':
            ExceptionTool.raises_resp(data.msg, resp)

    def req_api(self, url, get=True, require_success=True, **kwargs) -> JmApiResp:
        ts = self.decide_headers_and_ts(kwargs, url)

        if get:
            resp = self.get(url, **kwargs)
        else:
            resp = self.post(url, **kwargs)

        resp = JmApiResp(resp, ts)

        if require_success:
            self.require_resp_success(resp, url)

        return resp

    def update_request_with_specify_domain(self, kwargs: dict, domain: Optional[str], is_image=False):
        if is_image:
            # 设置APP端的图片请求headers
            kwargs['headers'] = {**JmModuleConfig.APP_HEADERS_TEMPLATE, **JmModuleConfig.APP_HEADERS_IMAGE}

    # noinspection PyMethodMayBeStatic
    def decide_headers_and_ts(self, kwargs, url):
        # 获取时间戳
        if url == self.API_SCRAMBLE:
            # /chapter_view_template
            # 这个接口很特殊，用的密钥 18comicAPPContent 而不是 18comicAPP
            # 如果用后者，则会返回403信息
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(ts, secret=JmMagicConstants.APP_TOKEN_SECRET_2)

        elif JmModuleConfig.FLAG_USE_FIX_TIMESTAMP:
            ts, token, tokenparam = JmModuleConfig.get_fix_ts_token_tokenparam()

        else:
            ts = time_stamp()
            token, tokenparam = JmCryptoTool.token_and_tokenparam(ts)

        # 设置headers
        headers = kwargs.get('headers', None) or JmModuleConfig.APP_HEADERS_TEMPLATE.copy()
        headers.update({
            'token': token,
            'tokenparam': tokenparam,
        })
        kwargs['headers'] = headers

        return ts

    @classmethod
    def require_resp_success(cls, resp: JmApiResp, url: Optional[str] = None):
        """

        :param resp: 响应对象
        :param url: 请求路径，例如 /setting
        """
        resp.require_success()

        # 1. 检查是否 album_missing
        # json: {'code': 200, 'data': []}
        data = resp.model().data
        if isinstance(data, list) and len(data) == 0:
            ExceptionTool.raise_missing(resp, JmcomicText.parse_to_jm_id(url))

        # 2. 是否是特殊的内容
        # 暂无

    def raise_if_resp_should_retry(self, resp, is_image):
        """
        该方法会判断resp返回值是否是json格式，
        如果不是，大概率是禁漫内部异常，需要进行重试

        由于完整的json格式校验会有性能开销，所以只做简单的检查，
        只校验第一个有效字符是不是 '{'，如果不是，就认为异常数据，需要重试
        """
        resp = super().raise_if_resp_should_retry(resp, is_image)

        if isinstance(resp, JmResp):
            # 不对包装过的resp对象做校验，包装者自行校验
            # 例如图片请求
            return resp

        code = resp.status_code
        if code >= 500:
            msg = JmModuleConfig.JM_ERROR_STATUS_CODE.get(code, f'HTTP状态码: {code}')
            ExceptionTool.raises_resp(f"禁漫API异常响应, {msg}", resp)

        url = resp.request.url

        if self.API_SCRAMBLE in url:
            # /chapter_view_template 这个接口不是返回json数据，不做检查
            return resp

        text = resp.text
        for char in text:
            if char not in (' ', '\n', '\t'):
                # 找到第一个有效字符
                ExceptionTool.require_true(
                    char == '{',
                    f'请求不是json格式，强制重试！响应文本: [{JmcomicText.limit_text(text, 200)}]'
                )
                return resp

        ExceptionTool.raises_resp(f'响应无数据！request_url=[{url}]', resp)

    def after_init(self):
        # 自动更新禁漫API域名
        if JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN:
            self.update_api_domain()

        # 保证拥有cookies，因为移动端要求必须携带cookies，否则会直接跳转同一本子【禁漫娘】
        if JmModuleConfig.FLAG_API_CLIENT_REQUIRE_COOKIES:
            self.ensure_have_cookies()

    client_update_domain_lock = Lock()

    def req_api_domain_server(self, url):
        resp = self.postman.get(url)
        text: str = resp.text
        # 去掉开头非ascii字符
        while text and not text[0].isascii():
            text = text[1:]
        res_json = JmCryptoTool.decode_resp_data(text, '', JmMagicConstants.API_DOMAIN_SERVER_SECRET)
        res_data = json_loads(res_json)

        # 检查返回值
        if not res_data.get('Server', None):
            jm_log('api.update_domain.empty',
                   f'获取禁漫最新API域名失败, 返回值: {res_json}')
            return None
        else:
            return res_data['Server']

    def update_api_domain(self):
        if True is JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN_DONE:
            return

        with self.client_update_domain_lock:
            if True is JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN_DONE:
                return
            # 遍历多个域名服务器
            for url in JmModuleConfig.API_URL_DOMAIN_SERVER_LIST:
                try:
                    # 获取域名列表
                    new_server_list = self.req_api_domain_server(url)
                    if new_server_list is None:
                        continue
                    old_server_list = JmModuleConfig.DOMAIN_API_LIST
                    jm_log('api.update_domain.success',
                           f'获取到最新的API域名，替换jmcomic内置域名：(new){new_server_list} ---→ (old){old_server_list}'
                           )
                    # 更新域名
                    if sorted(self.domain_list) == sorted(old_server_list):
                        self.domain_list = new_server_list
                    JmModuleConfig.DOMAIN_API_LIST = new_server_list
                    break
                except Exception as e:
                    jm_log('api.update_domain.error',
                           f'通过[{url}]自动更新API域名失败，仍使用jmcomic内置域名。'
                           f'可通过代码[JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN=False]关闭自动更新API域名. 异常： {e}'
                           )
            # set done finally
            JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN_DONE = True

    client_init_cookies_lock = Lock()

    def ensure_have_cookies(self):
        if self.get_meta_data('cookies'):
            return

        with self.client_init_cookies_lock:
            if self.get_meta_data('cookies'):
                return

            self['cookies'] = self.get_cookies()

    @field_cache("APP_COOKIES", obj=JmModuleConfig)
    def get_cookies(self):
        resp = self.setting()
        cookies = dict(resp.resp.cookies)
        return cookies


class PhotoConcurrentFetcherProxy(JmcomicClient):
    """
    为了解决 JmApiClient.get_photo_detail 方法的排队调用问题，
    即在访问完photo的接口后，需要另外排队访问获取album和scramble_id的接口。

    这三个接口可以并发请求，这样可以提高效率。

    此Proxy代理了get_photo_detail，实现了并发请求这三个接口，然后组装返回值返回photo。

    可通过插件 ClientProxyPlugin 启用本类，配置如下:
    ```yml
    plugins:
      after_init:
        - plugin: client_proxy
          kwargs:
            proxy_client_key: photo_concurrent_fetcher_proxy
    ```
    """
    client_key = 'photo_concurrent_fetcher_proxy'

    class FutureWrapper:
        def __init__(self, future, after_done_callback):
            from concurrent.futures import Future
            future: Future
            self.future = future
            self.done = False
            self._result = None
            self.after_done_callback = after_done_callback

        def result(self):
            if not self.done:
                result = self.future.result()
                self._result = result
                self.done = True
                self.future = None  # help gc
                self.after_done_callback()

            return self._result

    def __init__(self,
                 client: JmcomicClient,
                 max_workers=None,
                 executors=None,
                 ):
        self.client = client
        self.route_notimpl_method_to_internal_client(client)

        if executors is None:
            from concurrent.futures import ThreadPoolExecutor
            executors = ThreadPoolExecutor(max_workers)

        self.executors = executors
        self.future_dict: Dict[str, PhotoConcurrentFetcherProxy.FutureWrapper] = {}
        from threading import Lock
        self.lock = Lock()

    def route_notimpl_method_to_internal_client(self, client):

        proxy_methods = str_to_set('''
        get_album_detail
        get_photo_detail
        ''')

        # 获取对象的所有属性和方法的名称列表
        attributes_and_methods = dir(client)
        # 遍历属性和方法列表，并访问每个方法
        for method in attributes_and_methods:
            # 判断是否为方法（可调用对象）
            if (not method.startswith('_')
                    and callable(getattr(client, method))
                    and method not in proxy_methods
            ):
                setattr(self, method, getattr(client, method))

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        album_id = JmcomicText.parse_to_jm_id(album_id)
        cache_key = f'album_{album_id}'
        future = self.get_future(cache_key, task=lambda: self.client.get_album_detail(album_id))
        return future.result()

    def get_future(self, cache_key, task):
        if cache_key in self.future_dict:
            # cache hit, means that a same task is running
            return self.future_dict[cache_key]

        with self.lock:
            if cache_key in self.future_dict:
                return self.future_dict[cache_key]

            # after future done, remove it from future_dict.
            # cache depends on self.client instead of self.future_dict
            future = self.FutureWrapper(self.executors.submit(task),
                                        after_done_callback=lambda: self.future_dict.pop(cache_key, None)
                                        )

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
