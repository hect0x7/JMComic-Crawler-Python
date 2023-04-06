from .jm_toolkit import *


class JmcomicClient(PostmanProxy):
    retry_postman_type = RetryPostman

    def __init__(self, postman: Postman, domain, retry_times=None):
        super().__init__(postman.with_retry(retry_times or 5, self.retry_postman_type))
        self.domain = domain

    def download_image(self,
                       data_original: str,
                       img_save_path: str,
                       scramble_id: str,
                       photo_id: str = None,
                       decode_image=True,
                       ):
        """
        下载JM的图片
        @param data_original: 图片url
        @param img_save_path: 图片保存位置
        @param scramble_id: 图片所在photo的scramble_id
        @param photo_id: 图片所在photo的photo_id，可为空
        @param decode_image: 要保存的是解密后的图还是原图
        """
        # 请求图片
        resp = self.jm_get(data_original, is_api=False)

        if self.is_empty_image(resp):
            raise AssertionError(f'接收到的图片数据为空: {resp.url}')

        # gif图无需加解密，需要最先判断
        if self.img_is_not_need_to_decode(data_original, resp):
            JmImageSupport.save_resp_img(resp, img_save_path, False)
            return

        # 不解密图片，直接返回
        if decode_image is False:
            # 保存图片
            JmImageSupport.save_resp_img(
                resp,
                img_save_path,
                need_convert=suffix_not_equal(data_original, img_save_path),
            )

        JmImageSupport.save_resp_decoded_img(
            resp=resp,
            img_detail=JmImageDetail.of(
                photo_id or JmcomicText.parse_to_photo_id(data_original),
                scramble_id,
                data_original,
            ),
            filepath=img_save_path
        )

    def download_by_image_detail(self,
                                 img_detail: JmImageDetail,
                                 img_save_path,
                                 decode_image=True,
                                 ):
        self.download_image(
            img_detail.img_url,
            img_save_path,
            img_detail.scramble_id,
            photo_id=img_detail.aid,
            decode_image=decode_image,
        )

    # -- get detail（返回值是实体类） --

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        # 参数校验
        album_id = JmcomicText.parse_to_photo_id(album_id)

        # 请求
        resp = self.jm_get(f"/album/{album_id}")

        # 用 JmcomicText 解析 html，返回实体类
        return JmcomicText.analyse_jm_album_html(resp.text)

    def get_photo_detail(self, photo_id: str, album=True) -> JmPhotoDetail:
        # 参数校验
        photo_id = JmcomicText.parse_to_photo_id(photo_id)

        # 请求
        resp = self.jm_get(f"/photo/{photo_id}")

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
            photo_detail.page_arr = new.page_arr
            photo_detail.data_original_domain = new.data_original_domain

    # -- search --

    def search_album(self, search_query, main_tag=0) -> JmSearchPage:
        params = {
            'main_tag': main_tag,
            'search_query': search_query,
        }

        resp = self.jm_get('/search/photos', params=params)

        return JmSearchSupport.analyse_jm_search_html(resp.text)

    # -- 对象方法 --

    def of_api_url(self, api_path):
        return f"{JmModuleConfig.HTTP}{self.domain}{api_path}"

    def jm_get(self, url, is_api=True, require_200=True, **kwargs):
        """
        向禁漫发请求的统一入口
        """
        url = self.of_api_url(url) if is_api is True else url
        if is_api is True:
            jm_debug("api", url)

        resp = self.get(url, **kwargs)

        if require_200 is True and resp.status_code != 200:
            write_text('./resp.html', resp.text)
            raise AssertionError(f"请求失败，"
                                 f"响应状态码为{resp.status_code}，"
                                 f"URL=[{resp.url}]，"
                                 +
                                 (f"响应文本=[{resp.text}]" if len(resp.text) < 50 else
                                  f'响应文本过长(len={len(resp.text)})，不打印')
                                 )

        if is_api is True and resp.text.strip() == JmModuleConfig.JM_SERVER_ERROR_HTML:
            raise AssertionError("【JM异常】Could not connect to mysql! Please check your database settings!")

        return resp

    # -- 类方法 --

    @classmethod
    def is_empty_image(cls, resp):
        return resp.status_code != 200 or len(resp.content) == 0

    @classmethod
    def img_is_not_need_to_decode(cls, data_original: str, _resp):
        return data_original.endswith('.gif')


# 爬取策略
class FetchStrategy:

    def __init__(self,
                 from_index,
                 photo_len,
                 resp_getter,
                 resp_consumer,
                 ):
        self.from_index = from_index
        self.photo_len = photo_len
        self.resp_getter = resp_getter
        self.resp_consumer = resp_consumer

    def do_fetch(self):
        raise NotImplementedError

    def args(self):
        return (self.from_index,
                self.photo_len,
                self.resp_getter,
                self.resp_consumer,
                )
