from .jm_toolkit import *

"""

Response Entity

"""


class JmResp:

    def __init__(self, resp):
        ExceptionTool.require_true(not isinstance(resp, JmResp), f'重复包装: {resp}')
        self.resp = resp

    @property
    def is_success(self) -> bool:
        return self.http_code == 200 and len(self.content) != 0

    @property
    def is_not_success(self) -> bool:
        return not self.is_success

    @property
    def content(self):
        return self.resp.content

    @property
    def http_code(self):
        return self.resp.status_code

    @property
    def text(self) -> str:
        return self.resp.text

    @property
    def url(self) -> str:
        return self.resp.url

    def require_success(self):
        if self.is_not_success:
            ExceptionTool.raises_resp(self.error_msg(), self)

    def error_msg(self):
        return self.text


class JmImageResp(JmResp):

    def error_msg(self):
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
        index = img_url.find("?")
        if index != -1:
            img_url = img_url[0:index]

        if decode_image is False or scramble_id is None:
            # 不解密图片，直接保存文件
            JmImageTool.save_resp_img(
                self,
                path,
                need_convert=suffix_not_equal(img_url, path),
            )
        else:
            # 解密图片并保存文件
            JmImageTool.decode_and_save(
                JmImageTool.get_num_by_url(scramble_id, img_url),
                JmImageTool.open_image(self.content),
                path,
            )


class JmJsonResp(JmResp):

    @field_cache()
    def json(self) -> Dict:
        try:
            return self.resp.json()
        except Exception as e:
            ExceptionTool.raises_resp(f'json解析失败: {e}', self, JsonResolveFailException)

    def model(self) -> AdvancedDict:
        return AdvancedDict(self.json())


class JmApiResp(JmJsonResp):

    def __init__(self, resp, ts: str):
        super().__init__(resp)
        self.ts = ts

    # 重写json()方法，可以忽略一些非json格式的脏数据
    @field_cache()
    def json(self) -> Dict:
        try:
            return JmcomicText.try_parse_json_object(self.resp.text)
        except Exception as e:
            ExceptionTool.raises_resp(f'json解析失败: {e}', self, JsonResolveFailException)

    @property
    def is_success(self) -> bool:
        return super().is_success and self.json()['code'] == 200

    @property
    @field_cache()
    def decoded_data(self) -> str:
        return JmCryptoTool.decode_resp_data(self.encoded_data, self.ts)

    @property
    def encoded_data(self) -> str:
        return self.json()['data']

    @property
    def res_data(self) -> Any:
        self.require_success()
        from json import loads
        return loads(self.decoded_data)

    @property
    def model_data(self) -> AdvancedDict:
        self.require_success()
        return AdvancedDict(self.res_data)


# album-comment
class JmAlbumCommentResp(JmJsonResp):

    def is_success(self) -> bool:
        return super().is_success and self.json()['err'] is False


"""

Client Interface

"""


class JmDetailClient:

    def get_album_detail(self, album_id) -> JmAlbumDetail:
        raise NotImplementedError

    def get_photo_detail(self,
                         photo_id,
                         fetch_album=True,
                         fetch_scramble_id=True,
                         ) -> JmPhotoDetail:
        raise NotImplementedError

    def check_photo(self, photo: JmPhotoDetail):
        """
        photo来源有两种:
        1. album[?]
        2. client.get_photo_detail(?)

        其中，只有[2]是可以包含下载图片的url信息的。
        本方法会检查photo是不是[1]，
        如果是[1]，通过请求获取[2]，然后把2中的一些重要字段更新到1中

        :param photo: 被检查的JmPhotoDetail对象
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
              username: str,
              password: str,
              ):
        """
        1. 返回response响应对象
        2. 保证当前client拥有登录cookies
        """
        raise NotImplementedError

    def album_comment(self,
                      video_id,
                      comment,
                      originator='',
                      status='true',
                      comment_id=None,
                      **kwargs,
                      ) -> JmAlbumCommentResp:
        """
        评论漫画/评论回复
        :param video_id: album_id/photo_id
        :param comment: 评论内容
        :param status: 是否 "有劇透"
        :param comment_id: 被回复评论的id
        :param originator:
        :returns: JmAcResp 对象
        """
        raise NotImplementedError

    def favorite_folder(self,
                        page=1,
                        order_by=JmMagicConstants.ORDER_BY_LATEST,
                        folder_id='0',
                        username='',
                        ) -> JmFavoritePage:
        """
        获取收藏了的漫画，文件夹默认是全部
        :param folder_id: 文件夹id
        :param page: 分页
        :param order_by: 排序
        :param username: 用户名
        """
        raise NotImplementedError

    def add_favorite_album(self,
                           album_id,
                           folder_id='0',
                           ):
        """
        把漫画加入收藏夹
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
        :param img_url: 图片url
        :param img_save_path: 图片保存位置
        :param scramble_id: 图片所在photo的scramble_id
        :param decode_image: 要保存的是解密后的图还是原图
        """
        # 请求图片
        resp = self.get_jm_image(img_url)

        resp.require_success()

        return self.save_image_resp(decode_image, img_save_path, img_url, resp, scramble_id)

    # noinspection PyMethodMayBeStatic
    def save_image_resp(self, decode_image, img_save_path, img_url, resp, scramble_id):
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
    def img_is_not_need_to_decode(cls, data_original: str, _resp) -> bool:
        # https://cdn-msp2.18comic.vip/media/photos/498976/00027.gif?v=1697541064
        query_params_index = data_original.find('?')

        if query_params_index != -1:
            data_original = data_original[:query_params_index]

        # https://cdn-msp2.18comic.vip/media/photos/498976/00027.gif
        return data_original.endswith('.gif')

    def download_album_cover(self, album_id, save_path: str, size: str = ''):
        self.download_image(
            img_url=JmcomicText.get_album_cover_url(album_id, size=size),
            img_save_path=save_path,
            scramble_id=None,
            decode_image=False,
        )


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
        搜索【成人A漫】
        网页端与移动端的搜索有差别：

        - 移动端不支持 category, sub_category参数，网页端支持全部参数
        """
        raise NotImplementedError

    def search_site(self,
                    search_query: str,
                    page: int = 1,
                    order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                    time: str = JmMagicConstants.TIME_ALL,
                    category: str = JmMagicConstants.CATEGORY_ALL,
                    sub_category: Optional[str] = None,
                    ):
        """
        对应禁漫的站内搜索
        """
        return self.search(search_query, page, 0, order_by, time, category, sub_category)

    def search_work(self,
                    search_query: str,
                    page: int = 1,
                    order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                    time: str = JmMagicConstants.TIME_ALL,
                    category: str = JmMagicConstants.CATEGORY_ALL,
                    sub_category: Optional[str] = None,
                    ):
        """
        搜索album的作品 work
        """
        return self.search(search_query, page, 1, order_by, time, category, sub_category)

    def search_author(self,
                      search_query: str,
                      page: int = 1,
                      order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                      time: str = JmMagicConstants.TIME_ALL,
                      category: str = JmMagicConstants.CATEGORY_ALL,
                      sub_category: Optional[str] = None,
                      ):
        """
        搜索album的作者 author
        """
        return self.search(search_query, page, 2, order_by, time, category, sub_category)

    def search_tag(self,
                   search_query: str,
                   page: int = 1,
                   order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                   time: str = JmMagicConstants.TIME_ALL,
                   category: str = JmMagicConstants.CATEGORY_ALL,
                   sub_category: Optional[str] = None,
                   ):
        """
        搜索album的标签 tag
        """
        return self.search(search_query, page, 3, order_by, time, category, sub_category)

    def search_actor(self,
                     search_query: str,
                     page: int = 1,
                     order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                     time: str = JmMagicConstants.TIME_ALL,
                     category: str = JmMagicConstants.CATEGORY_ALL,
                     sub_category: Optional[str] = None,
                     ):
        """
        搜索album的登场角色 actor
        """
        return self.search(search_query, page, 4, order_by, time, category, sub_category)


class JmCategoryClient:
    """
    该接口可以看作是对全体禁漫本子的排行，热门排行的功能也派生于此

    月排行 = 分类【时间=月，排序=观看】
    周排行 = 分类【时间=周，排序=观看】
    日排行 = 分类【时间=周，排序=观看】
    """

    def categories_filter(self,
                          page: int,
                          time: str,
                          category: str,
                          order_by: str,
                          sub_category: Optional[str] = None,
                          ) -> JmCategoryPage:
        """
        分类

        :param page: 页码
        :param time: 时间范围，默认是全部时间
        :param category: 类别，默认是最新，即显示最新的禁漫本子
        :param sub_category: 副分类，仅网页端有这功能
        :param order_by: 排序方式，默认是观看数
        """
        raise NotImplementedError

    def month_ranking(self,
                      page: int,
                      category: str = JmMagicConstants.CATEGORY_ALL,
                      ):
        """
        月排行 = 分类【时间=月，排序=观看】
        """
        return self.categories_filter(page,
                                      JmMagicConstants.TIME_MONTH,
                                      category,
                                      JmMagicConstants.ORDER_BY_VIEW,
                                      )

    def week_ranking(self,
                     page: int,
                     category: str = JmMagicConstants.CATEGORY_ALL,
                     ):
        """
        周排行 = 分类【时间=周，排序=观看】
        """
        return self.categories_filter(page,
                                      JmMagicConstants.TIME_WEEK,
                                      category,
                                      JmMagicConstants.ORDER_BY_VIEW,
                                      )

    def day_ranking(self,
                    page: int,
                    category: str = JmMagicConstants.CATEGORY_ALL,
                    ):
        """
        日排行 = 分类【时间=日，排序=观看】
        """
        return self.categories_filter(page,
                                      JmMagicConstants.TIME_TODAY,
                                      category,
                                      JmMagicConstants.ORDER_BY_VIEW,
                                      )


# noinspection PyAbstractClass
class JmcomicClient(
    JmImageClient,
    JmDetailClient,
    JmUserClient,
    JmSearchAlbumClient,
    JmCategoryClient,
    Postman,
):
    client_key: None

    def get_domain_list(self) -> List[str]:
        """
        获取当前client的域名配置
        """
        raise NotImplementedError

    def set_domain_list(self, domain_list: List[str]):
        """
        设置当前client的域名配置
        """
        raise NotImplementedError

    def set_cache_dict(self, cache_dict: Optional[Dict]):
        raise NotImplementedError

    def get_cache_dict(self) -> Optional[Dict]:
        raise NotImplementedError

    def of_api_url(self, api_path, domain):
        raise NotImplementedError

    def get_html_domain(self):
        return JmModuleConfig.get_html_domain(self.get_root_postman())

    def get_html_domain_all(self):
        return JmModuleConfig.get_html_domain_all(self.get_root_postman())

    def get_html_domain_all_via_github(self):
        return JmModuleConfig.get_html_domain_all_via_github(self.get_root_postman())

    # noinspection PyMethodMayBeStatic
    def do_page_iter(self, params: dict, page: int, get_page_method):
        from math import inf

        def update(value: Optional[Dict], page: int, page_content: JmPageContent):
            if value is None:
                return page + 1, page_content.page_count

            ExceptionTool.require_true(isinstance(value, dict), 'require dict params')

            # 根据外界传递的参数，更新params和page
            page = value.get('page', page)
            params.update(value)

            return page, inf

        total = inf
        while page <= total:
            params['page'] = page
            page_content = get_page_method(**params)
            value = yield page_content
            page, total = update(value, page, page_content)

    def favorite_folder_gen(self,
                            page=1,
                            order_by=JmMagicConstants.ORDER_BY_LATEST,
                            folder_id='0',
                            username='',
                            ) -> Generator[JmFavoritePage, Dict, None]:
        """
        见 search_gen
        """
        params = {
            'order_by': order_by,
            'folder_id': folder_id,
            'username': username,
        }

        yield from self.do_page_iter(params, page, self.favorite_folder)

    def search_gen(self,
                   search_query: str,
                   main_tag=0,
                   page: int = 1,
                   order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                   time: str = JmMagicConstants.TIME_ALL,
                   category: str = JmMagicConstants.CATEGORY_ALL,
                   sub_category: Optional[str] = None,
                   ) -> Generator[JmSearchPage, Dict, None]:
        """
        搜索结果的生成器，支持下面这种调用方式：

        ```
        for page in self.search_gen('无修正'):
            # 每次循环，page为新页的结果
            pass
        ```

        同时支持外界send参数，可以改变搜索的设定，例如：

        ```
        gen = client.search_gen('MANA')
        for i, page in enumerate(gen):
            print(page.page_count)
            page = gen.send({
                'search_query': '+MANA +无修正',
                'page': 1
            })
            print(page.page_count)
            break
        ```

        """
        params = {
            'search_query': search_query,
            'main_tag': main_tag,
            'order_by': order_by,
            'time': time,
            'category': category,
            'sub_category': sub_category,
        }

        yield from self.do_page_iter(params, page, self.search)

    def categories_filter_gen(self,
                              page: int = 1,
                              time: str = JmMagicConstants.TIME_ALL,
                              category: str = JmMagicConstants.CATEGORY_ALL,
                              order_by: str = JmMagicConstants.ORDER_BY_LATEST,
                              sub_category: Optional[str] = None,
                              ) -> Generator[JmCategoryPage, Dict, None]:
        """
        见 search_gen
        """
        params = {
            'time': time,
            'category': category,
            'order_by': order_by,
            'sub_category': sub_category,
        }

        yield from self.do_page_iter(params, page, self.categories_filter)

    def is_given_type(self, ctype: Type['JmcomicClient']) -> bool:
        """
        Client代理的此方法会被路由到内部client的方法
        即：ClientProxy(AClient()).is_given_type(AClient) is True
        但是: ClientProxy(AClient()).client_key != AClient.client_key
        """
        if isinstance(self, ctype):
            return True
        if self.client_key == ctype.client_key:
            return True
        return False
