class JmModuleConfig:
    # 网站相关
    PROT = "https://"
    _DOMAIN = None
    JM_REDIRECT_URL = f'{PROT}jm365.xyz/3YeBdF'  # 永久網域，怕走失的小伙伴收藏起来
    JM_PUB_URL = f'{PROT}jmcomic1.bet'
    JM_CDN_IMAGE_URL_TEMPLATE = PROT + 'cdn-msp.{domain}/media/photos/{photo_id}/{index:05}{suffix}'  # index 从1开始
    JM_IMAGE_SUFFIX = ['.jpg', '.webp', '.png', '.gif']

    # 访问JM可能会遇到的异常网页
    JM_ERROR_RESPONSE_HTML = {
        "Could not connect to mysql! Please check your database settings!": "禁漫服务器内部报错",
        "Restricted Access!": "禁漫拒绝你所在ip地区的访问，你可以选择: 换域名/换代理",
    }

    # 图片分隔相关
    SCRAMBLE_0 = 220980
    SCRAMBLE_10 = 268850
    SCRAMBLE_NUM_8 = 421926  # 2023-02-08后改了图片切割算法

    # 下载时的一些默认值
    default_author = 'default-author'
    default_photo_title = 'default-photo-title'
    default_photo_id = 'default-photo-id'

    # debug
    enable_jm_debug = True
    debug_printer = print

    # 缓存
    jm_client_caches = {}

    @classmethod
    def domain(cls, postman=None):
        """
        由于禁漫的域名经常变化，调用此方法可以获取一个当前可用的最新的域名 domain，
        并且设置把 domain 设置为禁漫模块的默认域名。
        这样一来，配置文件也不用配置域名了，一切都在运行时动态获取。
        """
        if cls._DOMAIN is None:
            cls._DOMAIN = cls.get_jmcomic_url(postman).replace(cls.PROT, '')

        return cls._DOMAIN  # jmcomic默认域名

    @classmethod
    def headers(cls, authority=None):
        return {
            'authority': authority or cls.domain(),
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 '
                          'Safari/537.36',
        }

    # noinspection PyUnusedLocal
    @classmethod
    def jm_debug(cls, topic: str, msg: str, from_class=None):
        if cls.enable_jm_debug is True:
            cls.debug_printer(f'【{topic}】{msg}')

    @classmethod
    def disable_jm_debug(cls):
        cls.enable_jm_debug = False

    @classmethod
    def get_jmcomic_url(cls, postman=None):
        """
        访问禁漫的永久网域，从而得到一个可用的禁漫网址，
        """
        if postman is None:
            from common import Postmans
            postman = Postmans \
                .get_impl_clazz('cffi') \
                .create(headers=cls.headers(cls.JM_REDIRECT_URL))

        domain = postman.with_redirect_catching().get(cls.JM_REDIRECT_URL)
        cls.jm_debug('获取禁漫地址', f'[{cls.JM_REDIRECT_URL}] → [{domain}]')
        return domain

    @classmethod
    def check_html(cls, html: str, url=None):
        html = html.strip()
        error_msg = cls.JM_ERROR_RESPONSE_HTML.get(html, None)
        if error_msg is None:
            return

        raise AssertionError(f'{error_msg}' + f': {url}' if url is not None else '')


jm_debug = JmModuleConfig.jm_debug
disable_jm_debug = JmModuleConfig.disable_jm_debug
