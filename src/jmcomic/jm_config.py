class JmModuleConfig:
    # 网站相关
    HTTP = "https://"
    DOMAIN = "jmcomic1.group"  # jmcomic默认域名
    JM_REDIRECT_URL = f'{HTTP}jm365.xyz/3YeBdF'  # 永久網域，怕走失的小伙伴收藏起来↓
    JM_PUB_URL = f'{HTTP}jmcomic1.bet'
    JM_CDN_IMAGE_URL_TEMPLATE = HTTP + 'cdn-msp.{domain}/media/photos/{photo_id}/{index:05}{suffix}'  # index 从1开始
    JM_SERVER_ERROR_HTML = "Could not connect to mysql! Please check your database settings!"
    JM_IMAGE_SUFFIX = ['.jpg', '.webp', '.png', '.gif']

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
    def default_headers(cls):
        return {
            'authority': cls.DOMAIN,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 '
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
    def get_jmcomic_url(cls):
        """
        访问禁漫的永久网域，从而得到一个可用的禁漫网址，
        """
        from common import Postmans

        domain = Postmans \
            .get_impl_clazz('cffi') \
            .create(headers=cls.default_headers()) \
            .with_wrap_resp() \
            .get(cls.JM_REDIRECT_URL, allow_redirects=False) \
            .redirect_url

        cls.jm_debug('获取禁漫地址', f'获取成功，最新可用的禁漫地址: {domain}')
        return domain


jm_debug = JmModuleConfig.jm_debug
disable_jm_debug = JmModuleConfig.disable_jm_debug
