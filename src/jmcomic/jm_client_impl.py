from .jm_client_interface import *


class AbstractJmClient(
    JmcomicClient,
    RetryPostman,
):

    def __init__(self,
                 postman: Postman,
                 retry_times: int,
                 ):
        super().__init__(postman, retry_times)

    def with_retry(self, retry_times, clazz=None):
        self.retry_times = retry_times
        return self

    def fallback(self, url, kwargs):
        raise RuntimeError(f"禁漫请求失败（重试了{self.retry_times}次）: {url}")

    def tip_retrying(self, time, _request, url, kwargs):
        jm_debug('请求重试',
                 f'进入重试{time + 1}/{self.retry_times}: {url}'
                 f'，携带参数: {kwargs if "login" not in url else "#login_form#"}')

    def get_jmcomic_url(self, postman=None):
        return JmModuleConfig.get_jmcomic_url(postman or self)

    def get_jmcomic_url_all(self, postman=None):
        return JmModuleConfig.get_jmcomic_url_all(postman or self)

    def enable_cache(self, debug=False):
        def wrap_func_cache(func_name, cache_dict_name):
            if hasattr(self, cache_dict_name):
                return

            cache_dict = {}
            setattr(self, cache_dict_name, cache_dict)

            # 重载本对象的方法
            func = getattr(self, func_name)

            cache_hit_msg = f'【缓存命中】{cache_dict_name} ' + '→ [{}]' if debug is True else None
            cache_miss_msg = f'【缓存缺失】{cache_dict_name} ' + '← [{}]' if debug is True else None

            wrap_func = enable_cache(
                cache_dict=cache_dict,
                cache_hit_msg=cache_hit_msg,
                cache_miss_msg=cache_miss_msg,
            )(func)

            setattr(self, func_name, wrap_func)

        wrap_func_cache('get_photo_detail', 'album_cache_dict')
        wrap_func_cache('get_album_detail', 'photo_cache_dict')
        wrap_func_cache('search_album', 'search_album_cache_dict')


# 基于网页实现的JmClient
class JmHtmlClient(AbstractJmClient):
    retry_postman_type = RetryPostman

    def __init__(self,
                 domain,
                 postman: Postman,
                 retry_times=None,
                 ):
        super().__init__(postman, retry_times)
        self.domain = domain

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        # 参数校验
        album_id = JmcomicText.parse_to_photo_id(album_id)

        # 请求
        resp = self.get_jm_html(f"/album/{album_id}")

        # 用 JmcomicText 解析 html，返回实体类
        return JmcomicText.analyse_jm_album_html(resp.text)

    def get_photo_detail(self, photo_id: str, album=True) -> JmPhotoDetail:
        # 参数校验
        photo_id = JmcomicText.parse_to_photo_id(photo_id)

        # 请求
        resp = self.get_jm_html(f"/photo/{photo_id}")

        # 用 JmcomicText 解析 html，返回实体类
        photo_detail = JmcomicText.analyse_jm_photo_html(resp.text)

        # 一并获取该章节的所处本子
        if album is True:
            photo_detail.from_album = self.get_album_detail(photo_detail.album_id)

        return photo_detail

    def ensure_photo_can_use(self, photo_detail: JmPhotoDetail):
        # 检查 from_album
        if photo_detail.from_album is None:
            photo_detail.from_album = self.get_album_detail(photo_detail.album_id)

        # 检查 page_arr 和 data_original_domain
        if photo_detail.page_arr is None or photo_detail.data_original_domain is None:
            new = self.get_photo_detail(photo_detail.photo_id, False)
            new.from_album = photo_detail.from_album
            photo_detail.__dict__.update(new.__dict__)

    def search_album(self, search_query, main_tag=0) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
        }

        resp = self.get_jm_html('/search/photos', params=params)

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

        resp = self.post(self.of_api_url('/login'),
                         data=data,
                         allow_redirects=False,
                         )

        if resp.status_code != 301:
            raise AssertionError(f'登录失败，状态码为{resp.status_code}')

        if refresh_client_cookies is True:
            self['cookies'] = resp.cookies

        return resp

    def of_api_url(self, api_path):
        return f"{JmModuleConfig.PROT}{self.domain}{api_path}"

    def get_jm_html(self, url, require_200=True, **kwargs):
        """
        向禁漫发请求的统一入口
        """
        url = self.of_api_url(url)
        jm_debug("api", url)

        resp = self.get(url, **kwargs)

        if require_200 is True and resp.status_code != 200:
            write_text('./resp.html', resp.text)
            self.check_special_http_code(resp.status_code, url)
            raise AssertionError(f"请求失败，"
                                 f"响应状态码为{resp.status_code}，"
                                 f"URL=[{resp.url}]，"
                                 + (f"响应文本=[{resp.text}]" if len(resp.text) < 50 else
                                    f'响应文本过长(len={len(resp.text)})，不打印')
                                 )
        # 检查请求是否成功
        self.require_resp_success_else_raise(resp, url)

        return resp

    def get_jm_image(self, img_url) -> JmImageResp:
        return JmImageResp(self.get(img_url))

    @classmethod
    def require_resp_success_else_raise(cls, resp, url):
        # 1. 是否 album_missing
        if resp.url.endswith('/error/album_missing'):
            raise AssertionError(f'请求的本子不存在！({url})\n'
                                 '原因可能为:\n'
                                 '1. id有误，检查你的本子/章节id\n'
                                 '2. 该漫画只对登录用户可见，请配置你的cookies\n')

        # 2. 是否是错误html页
        cls.check_error_html(resp.text.strip(), url)

    @classmethod
    def check_error_html(cls, html: str, url=None):
        html = html.strip()
        error_msg = JmModuleConfig.JM_ERROR_RESPONSE_HTML.get(html, None)
        if error_msg is None:
            return

        raise AssertionError(f'{error_msg}'
                             + (f': {url}' if url is not None else ''))

    @classmethod
    def check_special_http_code(cls, code, url=None):
        error_msg = JmModuleConfig.JM_ERROR_STATUS_CODE.get(int(code), None)
        if error_msg is None:
            return

        raise AssertionError(f"请求失败，"
                             f"响应状态码为{code}，"
                             f'原因为: [{error_msg}], '
                             + (f'URL=[{url}]' if url is not None else '')
                             )


class JmApiClient(AbstractJmClient):
    API_SEARCH = '/search'

    def __init__(self,
                 base_url,
                 postman: Postman,
                 retry_times=5,
                 ):
        super().__init__(postman, retry_times)
        self.base_url: str = base_url

    def search_album(self, search_query: str, main_tag=0) -> JmApiResp:
        return self.get(
            self.API_SEARCH,
            params={
                'search_query': search_query,
            }
        )

    def get(self, url, concat_domain=True, **kwargs) -> JmApiResp:
        api_url = self.of_api_url(url) if concat_domain else url

        # set headers
        headers, key_ts = self.headers_key_ts
        kwargs.setdefault('headers', headers)

        resp = super().get(api_url, **kwargs)
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

    def of_api_url(self, api_path):
        return self.base_url + api_path
