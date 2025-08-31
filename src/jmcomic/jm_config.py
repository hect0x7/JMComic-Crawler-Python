from common import time_stamp, field_cache, ProxyBuilder


def shuffled(lines):
    from random import shuffle
    from common import str_to_list
    ls = str_to_list(lines)
    shuffle(ls)
    return ls


def default_jm_logging(topic: str, msg: str):
    from common import format_ts, current_thread
    print('[{}] [{}]:【{}】{}'.format(format_ts(), current_thread().name, topic, msg))


# 禁漫常量
class JmMagicConstants:
    # 搜索参数-排序
    ORDER_BY_LATEST = 'mr'
    ORDER_BY_VIEW = 'mv'
    ORDER_BY_PICTURE = 'mp'
    ORDER_BY_LIKE = 'tf'

    ORDER_MONTH_RANKING = 'mv_m'
    ORDER_WEEK_RANKING = 'mv_w'
    ORDER_DAY_RANKING = 'mv_t'

    # 搜索参数-时间段
    TIME_TODAY = 't'
    TIME_WEEK = 'w'
    TIME_MONTH = 'm'
    TIME_ALL = 'a'

    # 分类参数API接口的category
    CATEGORY_ALL = '0'  # 全部
    CATEGORY_DOUJIN = 'doujin'  # 同人
    CATEGORY_SINGLE = 'single'  # 单本
    CATEGORY_SHORT = 'short'  # 短篇
    CATEGORY_ANOTHER = 'another'  # 其他
    CATEGORY_HANMAN = 'hanman'  # 韩漫
    CATEGORY_MEIMAN = 'meiman'  # 美漫
    CATEGORY_DOUJIN_COSPLAY = 'doujin_cosplay'  # cosplay
    CATEGORY_3D = '3D'  # 3D
    CATEGORY_ENGLISH_SITE = 'english_site'  # 英文站

    # 副分类
    SUB_CHINESE = 'chinese'  # 汉化，通用副分类
    SUB_JAPANESE = 'japanese'  # 日语，通用副分类

    # 其他类（CATEGORY_ANOTHER）的副分类
    SUB_ANOTHER_OTHER = 'other'  # 其他漫画
    SUB_ANOTHER_3D = '3d'  # 3D
    SUB_ANOTHER_COSPLAY = 'cosplay'  # cosplay

    # 同人（SUB_CHINESE）的副分类
    SUB_DOUJIN_CG = 'CG'  # CG
    SUB_DOUJIN_CHINESE = SUB_CHINESE
    SUB_DOUJIN_JAPANESE = SUB_JAPANESE

    # 短篇（CATEGORY_SHORT）的副分类
    SUB_SHORT_CHINESE = SUB_CHINESE
    SUB_SHORT_JAPANESE = SUB_JAPANESE

    # 单本（CATEGORY_SINGLE）的副分类
    SUB_SINGLE_CHINESE = SUB_CHINESE
    SUB_SINGLE_JAPANESE = SUB_JAPANESE
    SUB_SINGLE_YOUTH = 'youth'

    # 图片分割参数
    SCRAMBLE_220980 = 220980
    SCRAMBLE_268850 = 268850
    SCRAMBLE_421926 = 421926  # 2023-02-08后改了图片切割算法

    # 移动端API密钥
    APP_TOKEN_SECRET = '18comicAPP'
    APP_TOKEN_SECRET_2 = '18comicAPPContent'
    APP_DATA_SECRET = '185Hcomic3PAPP7R'
    API_DOMAIN_SERVER_SECRET = 'diosfjckwpqpdfjkvnqQjsik'
    APP_VERSION = '2.0.6'


# 模块级别共用配置
class JmModuleConfig:
    # 网站相关
    PROT = "https://"
    JM_REDIRECT_URL = f'{PROT}jm365.work/3YeBdF'  # 永久網域，怕走失的小伙伴收藏起来
    JM_PUB_URL = f'{PROT}jmcomic-fb.vip'
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
        500: '500: 禁漫服务器内部异常（可能是服务器过载，可以切换ip或稍后重试）',
        520: '520: Web server is returning an unknown error (禁漫服务器内部报错)',
        524: '524: The origin web server timed out responding to this request. (禁漫服务器处理超时)',
    }

    # 分页大小
    PAGE_SIZE_SEARCH = 80
    PAGE_SIZE_FAVORITE = 20

    # 图片分隔相关
    SCRAMBLE_CACHE = {}

    # 当本子没有作者名字时，顶替作者名字
    DEFAULT_AUTHOR = 'default_author'

    # cookies，目前只在移动端使用，因为移动端请求接口须携带，但不会校验cookies的内容。
    APP_COOKIES = None

    # 移动端图片域名
    DOMAIN_IMAGE_LIST = shuffled('''
    cdn-msp.jmapiproxy1.cc
    cdn-msp.jmapiproxy2.cc
    cdn-msp2.jmapiproxy2.cc
    cdn-msp3.jmapiproxy2.cc
    cdn-msp.jmapinodeudzn.net
    cdn-msp3.jmapinodeudzn.net
    ''')

    # 移动端API域名
    DOMAIN_API_LIST = shuffled('''
    www.cdnaspa.vip
    www.cdnaspa.club
    www.cdnplaystation6.vip
    www.cdnplaystation6.cc
    ''')

    # 获取最新移动端API域名的地址
    API_URL_DOMAIN_SERVER_LIST = shuffled('''
    https://rup4a04-c01.tos-ap-southeast-1.bytepluses.com/newsvr-2025.txt
    https://rup4a04-c02.tos-cn-hongkong.bytepluses.com/newsvr-2025.txt
    ''')

    APP_HEADERS_TEMPLATE = {
        'Accept-Encoding': 'gzip, deflate',
        'user-agent': 'Mozilla/5.0 (Linux; Android 9; V1938CT Build/PQ3A.190705.11211812; wv) AppleWebKit/537.36 (KHTML, '
                      'like Gecko) Version/4.0 Chrome/91.0.4472.114 Safari/537.36',
    }

    APP_HEADERS_IMAGE = {
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'X-Requested-With': 'com.jiaohua_browser',
        'Referer': PROT + DOMAIN_API_LIST[0],
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    # 网页端headers
    HTML_HEADERS_TEMPLATE = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'no-cache',
        'dnt': '1',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': 'https://18comic.vip/',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 '
                      'Safari/537.36',
    }

    # 网页端域名配置
    # 无需配置，默认为None，需要的时候会发起请求获得
    # 使用优先级:
    # 1. DOMAIN_HTML_LIST
    # 2. [DOMAIN_HTML]
    DOMAIN_HTML = None
    DOMAIN_HTML_LIST = None

    # 模块级别的可重写类配置
    CLASS_DOWNLOADER = None
    CLASS_OPTION = None
    CLASS_ALBUM = None
    CLASS_PHOTO = None
    CLASS_IMAGE = None

    # 客户端注册表
    REGISTRY_CLIENT = {}
    # 插件注册表
    REGISTRY_PLUGIN = {}
    # 异常监听器
    # key: 异常类
    # value: 函数，参数只有异常对象，无需返回值
    # 这个异常类（或者这个异常的子类）的实例将要被raise前，你的listener方法会被调用
    REGISTRY_EXCEPTION_LISTENER = {}

    # 执行log的函数
    EXECUTOR_LOG = default_jm_logging

    # 使用固定时间戳
    FLAG_USE_FIX_TIMESTAMP = True
    # 移动端Client初始化cookies
    FLAG_API_CLIENT_REQUIRE_COOKIES = True
    # 自动更新禁漫API域名
    FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = True
    FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN_DONE = None
    # log开关标记
    FLAG_ENABLE_JM_LOG = True
    # log时解码url
    FLAG_DECODE_URL_WHEN_LOGGING = True
    # 当内置的版本号落后时，使用最新的禁漫app版本号
    FLAG_USE_VERSION_NEWER_IF_BEHIND = True

    # 关联dir_rule的自定义字段与对应的处理函数
    # 例如:
    # Amyname -> JmModuleConfig.AFIELD_ADVICE['myname'] = lambda album: "自定义名称"
    AFIELD_ADVICE = dict()
    PFIELD_ADVICE = dict()

    # 当发生 oserror: [Errno 36] File name too long 时，
    # 把文件名限制在指定个字符以内
    VAR_FILE_NAME_LENGTH_LIMIT = 100

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
        clazz_dict = cls.REGISTRY_CLIENT

        clazz = clazz_dict.get(client_key, None)
        if clazz is None:
            from .jm_toolkit import ExceptionTool
            ExceptionTool.raises(f'not found client impl class for key: "{client_key}"')

        return clazz

    @classmethod
    @field_cache("DOMAIN_HTML")
    def get_html_domain(cls, postman=None):
        """
        由于禁漫的域名经常变化，调用此方法可以获取一个当前可用的最新的域名 domain，
        并且设置把 domain 设置为禁漫模块的默认域名。
        这样一来，配置文件也不用配置域名了，一切都在运行时动态获取。
        """
        from .jm_toolkit import JmcomicText
        return JmcomicText.parse_to_jm_domain(cls.get_html_url(postman))

    @classmethod
    def get_html_url(cls, postman=None):
        """
        访问禁漫的永久网域，从而得到一个可用的禁漫网址
        :returns: https://jm-comic2.cc
        """
        postman = postman or cls.new_postman(session=True)

        url = postman.with_redirect_catching().get(cls.JM_REDIRECT_URL)
        cls.jm_log('module.html_url', f'获取禁漫网页URL: [{cls.JM_REDIRECT_URL}] → [{url}]')
        return url

    @classmethod
    @field_cache("DOMAIN_HTML_LIST")
    def get_html_domain_all(cls, postman=None):
        """
        访问禁漫发布页，得到所有的禁漫网页域名

        :returns: ['18comic.vip', ..., 'jm365.xyz/ZNPJam'], 最后一个是【APP軟件下載】
        """
        postman = postman or cls.new_postman(session=True)

        resp = postman.get(cls.JM_PUB_URL)
        if resp.status_code != 200:
            from .jm_toolkit import ExceptionTool
            ExceptionTool.raises_resp(f'请求失败，访问禁漫发布页获取所有域名，HTTP状态码为: {resp.status_code}', resp)

        from .jm_toolkit import JmcomicText
        domain_list = JmcomicText.analyse_jm_pub_html(resp.text)

        cls.jm_log('module.html_domain_all', f'获取禁漫网页全部域名: [{resp.url}] → {domain_list}')
        return domain_list

    @classmethod
    def get_html_domain_all_via_github(cls,
                                       postman=None,
                                       template='https://jmcmomic.github.io/go/{}.html',
                                       index_range=(300, 309)
                                       ):
        """
        通过禁漫官方的github号的repo获取最新的禁漫域名
        https://github.com/jmcmomic/jmcmomic.github.io
        """
        postman = postman or cls.new_postman(headers={
            'authority': 'github.com',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 '
                          'Safari/537.36'
        })
        domain_set = set()

        def fetch_domain(url):
            resp = postman.get(url, allow_redirects=False)
            text = resp.text
            from .jm_toolkit import JmcomicText
            for domain in JmcomicText.analyse_jm_pub_html(text):
                if domain.startswith('jm365'):
                    continue
                domain_set.add(domain)

        from common import multi_thread_launcher

        multi_thread_launcher(
            iter_objs=[template.format(i) for i in range(*index_range)],
            apply_each_obj_func=fetch_domain,
        )

        return domain_set

    @classmethod
    def new_html_headers(cls, domain='18comic.vip'):
        """
        网页端的headers
        """
        headers = cls.HTML_HEADERS_TEMPLATE.copy()
        headers.update({
            'authority': domain,
            'origin': f'https://{domain}',
            'referer': f'https://{domain}',
        })
        return headers

    @classmethod
    @field_cache()
    def get_fix_ts_token_tokenparam(cls):
        ts = time_stamp()
        from .jm_toolkit import JmCryptoTool
        token, tokenparam = JmCryptoTool.token_and_tokenparam(ts)
        return ts, token, tokenparam

    # noinspection PyUnusedLocal
    @classmethod
    def jm_log(cls, topic: str, msg: str):
        if cls.FLAG_ENABLE_JM_LOG is True:
            cls.EXECUTOR_LOG(topic, msg)

    @classmethod
    def disable_jm_log(cls):
        cls.FLAG_ENABLE_JM_LOG = False

    @classmethod
    def new_postman(cls, session=False, **kwargs):
        kwargs.setdefault('impersonate', 'chrome')
        kwargs.setdefault('headers', JmModuleConfig.new_html_headers())
        kwargs.setdefault('proxies', JmModuleConfig.DEFAULT_PROXIES)

        from common import Postmans

        if session is True:
            return Postmans.new_session(**kwargs)

        return Postmans.new_postman(**kwargs)

    # option 相关的默认配置
    # 一般情况下，建议使用option配置文件来定制配置
    # 而如果只想修改几个简单常用的配置，也可以下方的DEFAULT_XXX属性
    JM_OPTION_VER = '2.1'
    DEFAULT_CLIENT_IMPL = 'api'  # 默认Client实现类型为网页端
    DEFAULT_CLIENT_CACHE = None  # 默认关闭Client缓存。缓存的配置详见 CacheRegistry
    DEFAULT_PROXIES = ProxyBuilder.system_proxy()  # 默认使用系统代理

    DEFAULT_OPTION_DICT: dict = {
        'log': None,
        'dir_rule': {'rule': 'Bd_Pname', 'base_dir': None},
        'download': {
            'cache': True,
            'image': {'decode': True, 'suffix': None},
            'threading': {
                'image': 30,
                'photo': None,
            },
        },
        'client': {
            'cache': None,  # see CacheRegistry
            'domain': [],
            'postman': {
                'type': 'curl_cffi',
                'meta_data': {
                    'impersonate': 'chrome',
                    'headers': None,
                    'proxies': None,
                }
            },
            'impl': None,
            'retry_times': 5,
        },
        'plugins': {
            # 如果插件抛出参数校验异常，只log。（全局配置，可以被插件的局部配置覆盖）
            # 可选值：ignore（忽略），log（打印日志），raise（抛异常）。
            'valid': 'log',
        },
    }

    @classmethod
    def option_default_dict(cls) -> dict:
        """
        返回JmOption.default()的默认配置字典。
        这样做是为了支持外界自行覆盖option默认配置字典
        """
        from copy import deepcopy

        option_dict = deepcopy(cls.DEFAULT_OPTION_DICT)

        # log
        if option_dict['log'] is None:
            option_dict['log'] = cls.FLAG_ENABLE_JM_LOG

        # dir_rule.base_dir
        dir_rule = option_dict['dir_rule']
        if dir_rule['base_dir'] is None:
            import os
            dir_rule['base_dir'] = os.getcwd()

        # client cache
        client = option_dict['client']
        if client['cache'] is None:
            client['cache'] = cls.DEFAULT_CLIENT_CACHE

        # client impl
        if client['impl'] is None:
            client['impl'] = cls.DEFAULT_CLIENT_IMPL

        # postman proxies
        meta_data = client['postman']['meta_data']
        if meta_data['proxies'] is None:
            # use system proxy by default
            meta_data['proxies'] = cls.DEFAULT_PROXIES

        # threading photo
        dt = option_dict['download']['threading']
        if dt['photo'] is None:
            import os
            dt['photo'] = os.cpu_count()

        return option_dict

    @classmethod
    def register_plugin(cls, plugin_class):
        from .jm_toolkit import ExceptionTool
        ExceptionTool.require_true(getattr(plugin_class, 'plugin_key', None) is not None,
                                   f'未配置plugin_key, class: {plugin_class}')
        cls.REGISTRY_PLUGIN[plugin_class.plugin_key] = plugin_class

    @classmethod
    def register_client(cls, client_class):
        from .jm_toolkit import ExceptionTool
        ExceptionTool.require_true(getattr(client_class, 'client_key', None) is not None,
                                   f'未配置client_key, class: {client_class}')
        cls.REGISTRY_CLIENT[client_class.client_key] = client_class

    @classmethod
    def register_exception_listener(cls, etype, listener):
        cls.REGISTRY_EXCEPTION_LISTENER[etype] = listener


jm_log = JmModuleConfig.jm_log
disable_jm_log = JmModuleConfig.disable_jm_log
