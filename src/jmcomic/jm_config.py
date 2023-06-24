def default_jm_debug(topic: str, msg: str):
    from common import format_ts
    print(f'{format_ts()}:【{topic}】{msg}')


def default_postman_constructor(session, **kwargs):
    from common import Postmans

    kwargs.setdefault('impersonate', 'chrome110')
    kwargs.setdefault('headers', JmModuleConfig.headers())

    if session is True:
        return Postmans.new_session(**kwargs)

    return Postmans.new_postman(**kwargs)


class JmModuleConfig:
    # 网站相关
    PROT = "https://"
    DOMAIN = None
    JM_REDIRECT_URL = f'{PROT}jm365.work/3YeBdF'  # 永久網域，怕走失的小伙伴收藏起来
    JM_PUB_URL = f'{PROT}jmcomic2.bet'
    JM_CDN_IMAGE_URL_TEMPLATE = PROT + 'cdn-msp.{domain}/media/photos/{photo_id}/{index:05}{suffix}'  # index 从1开始
    JM_IMAGE_SUFFIX = ['.jpg', '.webp', '.png', '.gif']

    # 访问JM可能会遇到的异常网页
    JM_ERROR_RESPONSE_TEXT = {
        "Could not connect to mysql! Please check your database settings!": "禁漫服务器内部报错",
        "Restricted Access!": "禁漫拒绝你所在ip地区的访问，你可以选择: 换域名/换代理",
    }

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

    # 下载时的一些默认值
    default_author = 'default-author'
    default_photo_title = 'default-photo-title'
    default_photo_id = 'default-photo-id'

    # debug
    enable_jm_debug = True
    debug_executor = default_jm_debug
    postman_constructor = default_postman_constructor

    @classmethod
    def domain(cls, postman=None):
        """
        由于禁漫的域名经常变化，调用此方法可以获取一个当前可用的最新的域名 domain，
        并且设置把 domain 设置为禁漫模块的默认域名。
        这样一来，配置文件也不用配置域名了，一切都在运行时动态获取。
        """
        if cls.DOMAIN is None:
            from .jm_toolkit import JmcomicText
            cls.DOMAIN = JmcomicText.parse_to_jm_domain(cls.get_jmcomic_url(postman))

        return cls.DOMAIN  # jmcomic默认域名

    @classmethod
    def headers(cls, authority=None):
        return {
            'authority': authority or '18comic.vip',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'referer': 'https://18comic.vip',
            'pragma': 'no-cache',
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
        return cls.postman_constructor(session, **kwargs)

    @classmethod
    def get_jmcomic_url(cls, postman=None):
        """
        访问禁漫的永久网域，从而得到一个可用的禁漫网址
        @return: https://jm-comic2.cc
        """
        postman = postman or cls.new_postman(session=True)

        resp = postman.get(cls.JM_REDIRECT_URL)
        url = resp.url
        cls.jm_debug('获取禁漫地址', f'[{cls.JM_REDIRECT_URL}] → [{url}]')
        return url

    @classmethod
    def get_jmcomic_domain_all(cls, postman=None):
        """
        访问禁漫发布页，得到所有禁漫的域名
        @return：['18comic.vip', ..., 'jm365.xyz/ZNPJam'], 最后一个是【APP軟件下載】
        """
        postman = postman or cls.new_postman(session=True)

        resp = postman.get(cls.JM_PUB_URL)
        if resp.status_code != 200:
            raise AssertionError(resp.text)

        from .jm_toolkit import JmcomicText
        return JmcomicText.analyse_jm_pub_html(resp.text)


jm_debug = JmModuleConfig.jm_debug
disable_jm_debug = JmModuleConfig.disable_jm_debug
