def field_cache(*args, **kwargs):
    from common import field_cache
    return field_cache(*args, **kwargs)


def default_jm_debug(topic: str, msg: str):
    from common import format_ts
    print(f'{format_ts()}:【{topic}】{msg}')


def default_postman_constructor(session, **kwargs):
    from common import Postmans

    if session is True:
        return Postmans.new_session(**kwargs)

    return Postmans.new_postman(**kwargs)


def default_raise_regex_error(msg, *_args, **_kwargs):
    raise JmModuleConfig.exception(msg)


class JmcomicException(Exception):
    pass


class JmModuleConfig:
    # 网站相关
    PROT = "https://"
    JM_REDIRECT_URL = f'{PROT}jm365.work/3YeBdF'  # 永久網域，怕走失的小伙伴收藏起来
    JM_PUB_URL = f'{PROT}jmcomic.ltd'
    JM_CDN_IMAGE_URL_TEMPLATE = PROT + 'cdn-msp.{domain}/media/photos/{photo_id}/{index:05}{suffix}'  # index 从1开始
    JM_IMAGE_SUFFIX = ['.jpg', '.webp', '.png', '.gif']

    # JM的异常网页内容
    JM_ERROR_RESPONSE_TEXT = {
        "Could not connect to mysql! Please check your database settings!": "禁漫服务器内部报错",
        "Restricted Access!": "禁漫拒绝你所在ip地区的访问，你可以选择: 换域名/换代理",
    }

    # JM的异常网页code
    JM_ERROR_STATUS_CODE = {
        403: 'ip地区禁止访问/爬虫被识别',
        520: '520: Web server is returning an unknown error (禁漫服务器内部报错)',
        524: '524: The origin web server timed out responding to this request. (禁漫服务器处理超时)',
    }

    # 图片分隔相关
    SCRAMBLE_0 = 220980
    SCRAMBLE_10 = 268850
    SCRAMBLE_NUM_8 = 421926  # 2023-02-08后改了图片切割算法

    # API的相关配置
    MAGIC_18COMICAPPCONTENT = '18comicAPPContent'

    # 下载时的一些默认值配置
    default_author = 'default-author'

    # 模块级别的可重写配置
    DOMAIN = None
    DOMAIN_LIST = None
    CLASS_DOWNLOADER = None
    CLASS_OPTION = None
    CLASS_ALBUM = None
    CLASS_PHOTO = None
    CLASS_IMAGE = None
    CLASS_CLIENT_IMPL = {}
    CLASS_EXCEPTION = None

    # 执行debug的函数
    debug_executor = default_jm_debug
    # postman构造函数
    postman_constructor = default_postman_constructor
    # 网页正则表达式解析失败时，执行抛出异常的函数，可以替换掉用于debug
    raise_regex_error_executor = default_raise_regex_error

    # debug开关标记
    enable_jm_debug = True

    @classmethod
    def downloader_class(cls):
        if cls.CLASS_DOWNLOADER is not None:
            return cls.CLASS_DOWNLOADER

        from .jm_downloader import JmDownloader
        return JmDownloader

    @classmethod
    def option_class(cls):
        if cls.CLASS_OPTION is not None:
            return cls.CLASS_OPTION

        from .jm_option import JmOption
        return JmOption

    @classmethod
    def album_class(cls):
        if cls.CLASS_ALBUM is not None:
            return cls.CLASS_ALBUM

        from .jm_entity import JmAlbumDetail
        return JmAlbumDetail

    @classmethod
    def photo_class(cls):
        if cls.CLASS_PHOTO is not None:
            return cls.CLASS_PHOTO

        from .jm_entity import JmPhotoDetail
        return JmPhotoDetail

    @classmethod
    def image_class(cls):
        if cls.CLASS_IMAGE is not None:
            return cls.CLASS_IMAGE

        from .jm_entity import JmImageDetail
        return JmImageDetail

    @classmethod
    def client_impl_class(cls, client_key: str):
        client_impl_dict = cls.CLASS_CLIENT_IMPL

        impl_class = client_impl_dict.get(client_key, None)
        if impl_class is None:
            raise NotImplementedError(f'not found client impl class for key: "{client_key}"')

        return impl_class

    @classmethod
    def exception(cls, msg: str):
        if cls.CLASS_EXCEPTION is not None:
            return cls.CLASS_EXCEPTION(msg)

        return JmcomicException(msg)

    @classmethod
    @field_cache("DOMAIN")
    def domain(cls, postman=None):
        """
        由于禁漫的域名经常变化，调用此方法可以获取一个当前可用的最新的域名 domain，
        并且设置把 domain 设置为禁漫模块的默认域名。
        这样一来，配置文件也不用配置域名了，一切都在运行时动态获取。
        """
        from .jm_toolkit import JmcomicText
        return JmcomicText.parse_to_jm_domain(cls.get_jmcomic_url(postman))

    @classmethod
    def get_jmcomic_url(cls, postman=None):
        """
        访问禁漫的永久网域，从而得到一个可用的禁漫网址
        @return: https://jm-comic2.cc
        """
        postman = postman or cls.new_postman(session=True)

        url = postman.with_redirect_catching().get(cls.JM_REDIRECT_URL)
        cls.jm_debug('获取禁漫URL', f'[{cls.JM_REDIRECT_URL}] → [{url}]')
        return url

    @classmethod
    @field_cache("DOMAIN_LIST")
    def get_jmcomic_domain_all(cls, postman=None):
        """
        访问禁漫发布页，得到所有禁漫的域名

        @return: ['18comic.vip', ..., 'jm365.xyz/ZNPJam'], 最后一个是【APP軟件下載】
        """
        postman = postman or cls.new_postman(session=True)

        resp = postman.get(cls.JM_PUB_URL)
        if resp.status_code != 200:
            raise JmModuleConfig.exception(resp.text)

        from .jm_toolkit import JmcomicText
        domain_list = JmcomicText.analyse_jm_pub_html(resp.text)

        cls.jm_debug('获取禁漫全部域名', f'[{resp.url}] → {domain_list}')
        return domain_list

    @classmethod
    def headers(cls, domain='18comic.vip'):
        return {
            'authority': domain,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'referer': f'https://{domain}',
            'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 '
                          'Safari/537.36',
        }

    # noinspection PyUnusedLocal
    @classmethod
    def jm_debug(cls, topic: str, msg: str):
        if cls.enable_jm_debug is True:
            cls.debug_executor(topic, msg)

    @classmethod
    def disable_jm_debug(cls):
        cls.enable_jm_debug = False

    @classmethod
    def new_postman(cls, session=False, **kwargs):
        kwargs.setdefault('impersonate', 'chrome110')
        kwargs.setdefault('headers', JmModuleConfig.headers())
        return cls.postman_constructor(session, **kwargs)

    album_comment_headers = {
        'authority': '18comic.vip',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://18comic.vip',
        'pragma': 'no-cache',
        'referer': 'https://18comic.vip/album/248965/',
        'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/114.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    # option 默认配置字典
    default_option_dict: dict = {
        'version': '2.0',
        'debug': None,
        'dir_rule': {'rule': 'Bd_Ptitle', 'base_dir': None},
        'download': {
            'cache': True,
            'image': {'decode': True, 'suffix': None},
            'threading': {'batch_count': 30},
        },
        'client': {
            'cache': None,
            'domain': [],
            'postman': {
                'type': 'cffi',
                'meta_data': {
                    'impersonate': 'chrome110',
                    'headers': None,
                }
            },
            'impl': 'html',
            'retry_times': 5
        }
    }

    @classmethod
    def option_default_dict(cls) -> dict:
        """
        返回JmOption.default()的默认配置字典。
        这样做是为了支持外界自行覆盖option默认配置字典
        """
        option_dict = cls.default_option_dict.copy()

        # debug
        if option_dict['debug'] is None:
            option_dict['debug'] = cls.enable_jm_debug

        # dir_rule.base_dir
        dir_rule = option_dict['dir_rule']
        if dir_rule['base_dir'] is None:
            import os
            dir_rule['base_dir'] = os.getcwd()

        # client cache
        client = option_dict['client']
        if client['cache'] is None:
            client['cache'] = True

        # headers
        meta_data = client['postman']['meta_data']
        if meta_data['headers'] is None:
            meta_data['headers'] = cls.headers()

        return option_dict


jm_debug = JmModuleConfig.jm_debug
disable_jm_debug = JmModuleConfig.disable_jm_debug
