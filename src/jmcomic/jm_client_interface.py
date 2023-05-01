from .jm_toolkit import *

"""

Response Entity

"""


class JmResp(CommonResp):

    @property
    def is_success(self) -> bool:
        return self.http_code == 200 and len(self.content) != 0


class JmImageResp(JmResp):

    def require_success(self):
        if self.is_success:
            return

        msg = f'禁漫图片获取失败: [{self.url}]'
        if self.http_code != 200:
            msg += f'，http状态码={self.http_code}'
        if len(self.content) == 0:
            msg += f'，响应数据为空'

        raise AssertionError(msg)

    def transfer(self,
                 path,
                 scramble_id,
                 decode_image=True,
                 img_url=None,
                 ):
        img_url = img_url or self.url

        if decode_image is False:
            # 不解密图片，直接返回
            JmImageSupport.save_resp_img(
                self,
                path,
                need_convert=suffix_not_equal(img_url, path),
            )
        else:
            # 解密图片，需要 photo_id、scramble_id
            JmImageSupport.decode_and_save(
                JmImageSupport.get_num_by_url(scramble_id, img_url),
                JmImageSupport.open_Image(self.content),
                path,
            )


class JmTextResp(JmResp):
    pass


"""

Client Interface

"""


class JmDetailClient:

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        raise NotImplementedError

    def get_photo_detail(self, photo_id: str, album=True) -> JmPhotoDetail:
        raise NotImplementedError

    def ensure_photo_can_use(self, photo_detail: JmPhotoDetail):
        raise NotImplementedError

    def search_album(self, search_query, main_tag=0) -> JmSearchPage:
        raise NotImplementedError

    def of_api_url(self, api_path):
        raise NotImplementedError

    def enable_cache(self, debug=False):
        raise NotImplementedError


class JmUserClient:

    def login(self,
              username,
              password,
              refresh_client_cookies=True,
              id_remember='on',
              login_remember='on',
              ):
        raise NotImplementedError


class JmImageClient:

    # -- 下载图片 --

    def download_image(self,
                       img_url: str,
                       img_save_path: str,
                       scramble_id: str,
                       decode_image=True,
                       ):
        """
        下载JM的图片
        @param img_url: 图片url
        @param img_save_path: 图片保存位置
        @param scramble_id: 图片所在photo的scramble_id
        @param decode_image: 要保存的是解密后的图还是原图
        """
        # 请求图片
        resp = self.get_jm_image(img_url)

        resp.require_success()

        # gif图无需加解密，需要最先判断

        if self.img_is_not_need_to_decode(img_url, resp):
            JmImageSupport.save_resp_img(resp, img_save_path, False)
        else:
            resp.transfer(img_save_path, scramble_id, decode_image, img_url)

    def download_by_image_detail(self,
                                 img_detail: JmImageDetail,
                                 img_save_path,
                                 decode_image=True,
                                 ):
        self.download_image(
            img_detail.img_url,
            img_save_path,
            img_detail.scramble_id,
            decode_image=decode_image,
        )

    def get_jm_image(self, img_url) -> JmImageResp:
        raise NotImplementedError

    @classmethod
    def img_is_not_need_to_decode(cls, data_original: str, _resp):
        return data_original.endswith('.gif')


class JmcomicClient(
    JmImageClient,
    JmDetailClient,
    JmUserClient,
):
    pass
