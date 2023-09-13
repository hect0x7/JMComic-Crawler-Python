from .jm_toolkit import *

"""

Response Entity

"""

DictModel = AdvancedEasyAccessDict

class JmResp(CommonResp):

    @property
    def is_success(self) -> bool:
        return self.http_code == 200 and len(self.content) != 0

    def json(self, **kwargs) -> Dict:
        raise NotImplementedError

    def model(self) -> DictModel:
        return DictModel(self.json())

    def require_success(self):
        if self.is_not_success:
            raise JmModuleConfig.exception(self.resp.text)

class JmImageResp(JmResp):

    def json(self, **kwargs) -> Dict:
        raise NotImplementedError

    def require_success(self):
        if self.is_success:
            return

        raise JmModuleConfig.exception(self.get_error_msg())

    def get_error_msg(self):
        msg = f'禁漫图片获取失败: [{self.url}]'
        if self.http_code != 200:
            msg += f'，http状态码={self.http_code}'
        if len(self.content) == 0:
            msg += f'，响应数据为空'
        return msg

    def transfer_to(self,
                    path,
                    scramble_id,
                    decode_image=True,
                    img_url=None,
                    ):
        img_url = img_url or self.url

        if decode_image is False:
            # 不解密图片，直接保存文件
            JmImageSupport.save_resp_img(
                self,
                path,
                need_convert=suffix_not_equal(img_url, path),
            )
        else:
            # 解密图片并保存文件
            JmImageSupport.decode_and_save(
                JmImageSupport.get_num_by_url(scramble_id, img_url),
                JmImageSupport.open_Image(self.content),
                path,
            )


class JmApiResp(JmResp):

    @classmethod
    def wrap(cls, resp, key_ts):
        if isinstance(resp, JmApiResp):
            raise JmModuleConfig.exception('重复包装')

        return cls(resp, key_ts)

    def __init__(self, resp, key_ts):
        super().__init__(resp)
        self.key_ts = key_ts
        self.cache_decode_data = None

    @staticmethod
    def parse_data(text, time) -> str:
        # 1. base64解码
        import base64
        data = base64.b64decode(text)

        # 2. AES-ECB解密
        # key = 时间戳拼接 '18comicAPPContent' 的md5
        import hashlib
        key = hashlib.md5(f"{time}18comicAPPContent".encode("utf-8")).hexdigest().encode("utf-8")
        from Crypto.Cipher import AES
        data = AES.new(key, AES.MODE_ECB).decrypt(data)

        # 3. 移除末尾的一些特殊字符
        data = data[:-data[-1]]

        # 4. 解码为字符串 (json)
        res = data.decode('utf-8')
        return res

    @property
    def decoded_data(self) -> str:
        if self.cache_decode_data is None:
            self.cache_decode_data = self.parse_data(self.encoded_data, self.key_ts)

        return self.cache_decode_data

    @property
    def encoded_data(self) -> str:
        return self.json()['data']

    @property
    def res_data(self) -> Any:
        self.require_success()
        from json import loads
        return loads(self.decoded_data)

    def json(self, **kwargs) -> Dict:
        return self.resp.json()

    @property
    def model_data(self) -> DictModel:
        self.require_success()
        return DictModel(self.res_data)


# album-comment
class JmAcResp(JmResp):

    def is_success(self) -> bool:
        return super().is_success and self.json()['err'] is False

    def json(self, **kwargs) -> Dict:
        return self.resp.json()

    def model(self) -> DictModel:
        return DictModel(self.json())


"""

Client Interface

"""


class JmDetailClient:

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        raise NotImplementedError

    def get_photo_detail(self, photo_id, fetch_album=True) -> JmPhotoDetail:
        raise NotImplementedError

    def of_api_url(self, api_path, domain):
        raise NotImplementedError

    def enable_cache(self, debug=False):
        raise NotImplementedError

    def is_cache_enabled(self) -> bool:
        raise NotImplementedError

    def check_photo(self, photo: JmPhotoDetail):
        """
        photo来源有两种:
        1. album[?]
        2. client.get_photo_detail(?)

        其中，只有[2]是可以包含下载图片的url信息的。
        本方法会检查photo是不是[1]，
        如果是[1]，通过请求获取[2]，然后把2中的一些重要字段更新到1中

        @param photo: 被检查的JmPhotoDetail对象
        """
        # 检查 from_album
        if photo.from_album is None:
            photo.from_album = self.get_album_detail(photo.album_id)

        # 检查 page_arr 和 data_original_domain
        if photo.page_arr is None or photo.data_original_domain is None:
            new = self.get_photo_detail(photo.photo_id, False)
            new.from_album = photo.from_album
            photo.__dict__.update(new.__dict__)


class JmUserClient:

    def login(self,
              username,
              password,
              refresh_client_cookies=True,
              id_remember='on',
              login_remember='on',
              ):
        raise NotImplementedError

    def album_comment(self,
                      video_id,
                      comment,
                      originator='',
                      status='true',
                      comment_id=None,
                      **kwargs,
                      ) -> JmAcResp:
        """
        评论漫画/评论回复
        @param video_id: album_id/photo_id
        @param comment: 评论内容
        @param status: 是否 "有劇透"
        @param comment_id: 被回复评论的id
        @param originator:
        @return: JmAcResp 对象
        """
        raise NotImplementedError


class JmImageClient:

    # -- 下载图片 --

    def download_image(self,
                       img_url: str,
                       img_save_path: str,
                       scramble_id: Optional[int] = None,
                       decode_image=True,
                       ):
        """
        下载JM的图片
        @param img_url: 图片url
        @param img_save_path: 图片保存位置
        @param scramble_id: 图片所在photo的scramble_id
        @param decode_image: 要保存的是解密后的图还是原图
        """
        if scramble_id is None:
            scramble_id = JmModuleConfig.SCRAMBLE_0

        # 请求图片
        resp = self.get_jm_image(img_url)

        resp.require_success()

        return self.save_image_resp(decode_image, img_save_path, img_url, resp, scramble_id)

    def save_image_resp(self, decode_image, img_save_path, img_url, resp, scramble_id):
        # gif图无需加解密，需要最先判断
        if self.img_is_not_need_to_decode(img_url, resp):
            # 相当于调用save_directly，但使用save_resp_img可以统一调用入口
            JmImageSupport.save_resp_img(resp, img_save_path, False)
        else:
            resp.transfer_to(img_save_path, scramble_id, decode_image, img_url)

    def download_by_image_detail(self,
                                 image: JmImageDetail,
                                 img_save_path,
                                 decode_image=True,
                                 ):
        return self.download_image(
            image.download_url,
            img_save_path,
            int(image.scramble_id),
            decode_image=decode_image,
        )

    def get_jm_image(self, img_url) -> JmImageResp:
        raise NotImplementedError

    @classmethod
    def img_is_not_need_to_decode(cls, data_original: str, _resp):
        return data_original.endswith('.gif')


class JmSearchAlbumClient:
    """
    搜尋的最佳姿勢？
    【包含搜尋】
    搜尋[+]全彩[空格][+]人妻,僅顯示全彩且是人妻的本本
    範例:+全彩 +人妻

    【排除搜尋】
    搜尋全彩[空格][-]人妻,顯示全彩並排除人妻的本本
    範例:全彩 -人妻

    【我都要搜尋】
    搜尋全彩[空格]人妻,會顯示所有包含全彩及人妻的本本
    範例:全彩 人妻
    """

    ORDER_BY_LATEST = 'mr'
    ORDER_BY_VIEW = 'mv'
    ORDER_BY_PICTURE = 'mp'
    ORDER_BY_LIKE = 'tf'

    TIME_TODAY = 't'
    TIME_WEEK = 'w'
    TIME_MONTH = 'm'
    TIME_ALL = 'a'

    def search(self,
               search_query: str,
               page: int,
               main_tag: int,
               order_by: str,
               time: str,
               ) -> JmSearchPage:
        """
        搜索【成人A漫】
        """
        raise NotImplementedError

    def search_site(self,
                    search_query: str,
                    page: int = 1,
                    order_by: str = ORDER_BY_LATEST,
                    time: str = TIME_ALL,
                    ):
        """
        对应禁漫的站内搜索
        """
        return self.search(search_query, page, 0, order_by, time)

    def search_work(self,
                    search_query: str,
                    page: int = 1,
                    order_by: str = ORDER_BY_LATEST,
                    time: str = TIME_ALL,
                    ):
        """
        搜索album的作品 work
        """
        return self.search(search_query, page, 1, order_by, time)

    def search_author(self,
                      search_query: str,
                      page: int = 1,
                      order_by: str = ORDER_BY_LATEST,
                      time: str = TIME_ALL,
                      ):
        """
        搜索album的作者 author
        """
        return self.search(search_query, page, 2, order_by, time)

    def search_tag(self,
                   search_query: str,
                   page: int = 1,
                   order_by: str = ORDER_BY_LATEST,
                   time: str = TIME_ALL,
                   ):
        """
        搜索album的标签 tag
        """
        return self.search(search_query, page, 3, order_by, time)

    def search_actor(self,
                     search_query: str,
                     page: int = 1,
                     order_by: str = ORDER_BY_LATEST,
                     time: str = TIME_ALL,
                     ):
        """
        搜索album的登场角色 actor
        """
        return self.search(search_query, page, 4, order_by, time)


# noinspection PyAbstractClass
class JmcomicClient(
    JmImageClient,
    JmDetailClient,
    JmUserClient,
    JmSearchAlbumClient,
    Postman,
):
    def get_jmcomic_url(self):
        return JmModuleConfig.get_jmcomic_url()

    def get_jmcomic_domain_all(self):
        return JmModuleConfig.get_jmcomic_domain_all()

    def get_domain_list(self) -> List[str]:
        raise NotImplementedError

    def set_domain_list(self, domain_list: List[str]):
        raise NotImplementedError
