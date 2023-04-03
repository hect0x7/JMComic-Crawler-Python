from .jm_client import *


class CdnConfig:

    def __init__(self,
                 cdn_domain: str,
                 cdn_image_suffix: str,
                 fetch_strategy: Type[FetchStrategy],
                 use_cache,
                 decode_image,
                 ):
        self.cdn_domain = cdn_domain
        self.cdn_image_suffix = cdn_image_suffix
        self.fetch_strategy = fetch_strategy
        self.use_cache = use_cache
        self.decode_image = decode_image

    def get_cdn_image_url(self, photo_id: str, index: int) -> str:
        return JmModuleConfig.JM_CDN_IMAGE_URL_TEMPLATE.format(
            domain=self.cdn_domain,
            photo_id=photo_id,
            index=index,
            suffix=self.cdn_image_suffix
        )

    def check_request_is_valid(self, req: CdnRequest):
        from common import is_function

        if req.photo_len is not None and not isinstance(req.photo_len, int):
            raise AssertionError('传参错误，photo_len要么给整数，要么给None')
        if not is_function(req.save_path_provider):
            raise AssertionError('传参错误，save_path_provider应该是函数')
        if self.decode_image is True and req.scramble_id is None:
            raise AssertionError('传参缺失，指定decode_image=True，就必须提供scramble_id')
        if req.from_index <= 0:
            raise AssertionError(f'传参错误，from_index必须大于1: {req.from_index} < 1')

    @classmethod
    def create(cls,
               cdn_domain,
               fetch_strategy,
               cdn_image_suffix=None,
               use_cache=False,
               decode_image=True,
               ):

        return CdnConfig(
            cdn_domain,
            cdn_image_suffix or '.webp',
            fetch_strategy,
            use_cache,
            decode_image,
        )


class InOrderFetch(FetchStrategy):

    def do_fetch(self):
        index, photo_len, resp_getter, resp_consumer = self.args()

        while True:
            if photo_len is not None and index > photo_len:
                break

            resp_info = resp_getter(index)
            if resp_info[0] is None:
                break
            resp_consumer(resp_info, index)
            index += 1


class MultiThreadFetch(FetchStrategy):
    fetch_batch_count = 5

    def do_fetch(self):
        from common import multi_thread_launcher
        begin, photo_len, resp_getter, resp_consumer = self.args()

        if photo_len is not None:
            # 确定要爬多少页

            def accpet_index(index):
                resp_info = resp_getter(index)
                if resp_info[0] is None:
                    return
                resp_consumer(resp_info, index)

            multi_thread_launcher(
                iter_objs=range(begin, photo_len + 1),
                apply_each_obj_func=accpet_index,
                wait_finish=True,
            )
        else:
            # 不确定要爬多少页

            # 批量单位
            batch_count = self.fetch_batch_count
            # 标记位
            fetch_suffer_none_resp = False

            def accpet_index(index):
                resp_info = resp_getter(index)
                if resp_info is None:
                    nonlocal fetch_suffer_none_resp
                    fetch_suffer_none_resp = True
                    return
                resp_consumer(resp_info, index)

            while True:
                # 5次5次爬，每5次中，但凡有1次出现了失败，就停止

                multi_thread_launcher(
                    iter_objs=range(begin, begin + batch_count),
                    apply_each_obj_func=accpet_index,
                    wait_finish=True
                )

                # 检查标记
                if fetch_suffer_none_resp is False:
                    begin += batch_count
                else:
                    break


class CdnFetchService:

    def __init__(self,
                 config: CdnConfig,
                 client: 'JmcomicClient',
                 ):
        self.client = client
        self.config = config

    def download_photo_from_cdn_directly(self,
                                         req: CdnRequest,
                                         ):
        # 校验参数
        self.config.check_request_is_valid(req)

        # 基本信息
        photo_id = req.photo_id
        scramble_id = req.scramble_id
        use_cache = self.config.use_cache
        decode_image = self.config.decode_image

        # 获得响应
        def get_resp(index: int) -> Tuple[Optional[Any], str, str]:
            url = self.config.get_cdn_image_url(photo_id, index)
            suffix = self.config.cdn_image_suffix
            pre_try_save_path = req.save_path_provider(url, suffix, index, decode_image)

            # 判断是否命中缓存（预先尝试）
            if use_cache is True and file_exists(pre_try_save_path):
                # 命中，返回特殊值
                return None, suffix, pre_try_save_path
            else:
                return self.try_get_cdn_image_resp(
                    self.client,
                    url,
                    suffix,
                    photo_id,
                    index,
                )

        # 保存响应
        def save_resp(resp_info: Tuple[Optional[Any], str, str], index: int):
            resp, suffix, img_url = resp_info

            # 1. 判断是不是特殊值
            if resp_info[0] is None:
                # 是，表示命中缓存，直接返回
                save_path = resp_info[2]
                jm_debug('图片下载成功',
                         f'photo-{photo_id}: {index}{suffix}命中磁盘缓存 ({save_path})')
                return

            # 2. 判断是否命中缓存
            save_path = req.save_path_provider(img_url, suffix, index, decode_image)
            if use_cache is True and file_exists(save_path):
                # 命中，直接返回
                jm_debug('图片下载成功',
                         f'photo-{photo_id}: {index}{suffix}命中磁盘缓存 ({save_path})')
                return

            # 3. 保存图片
            if decode_image is False:
                JmImageSupport.save_resp_img(resp, save_path)
            else:
                JmImageSupport.save_resp_decoded_img(
                    resp,
                    JmImageDetail.of(photo_id, scramble_id, data_original=img_url),
                    save_path,
                )

            # 4. debug 消息
            jm_debug('图片下载成功',
                     f'photo-{photo_id}: {index}{suffix}下载完成 ('
                     + ('已解码' if decode_image is True else '未解码') +
                     f') [{img_url}] → [{save_path}]')

        # 调用爬虫策略
        self.config.fetch_strategy(
            req.from_index,
            req.photo_len,
            resp_getter=get_resp,
            resp_consumer=save_resp,
        ).do_fetch()

    # 准备提供给爬虫策略的函数
    @staticmethod
    def try_get_cdn_image_resp(client: JmcomicClient,
                               url: str,
                               suffix: str,
                               photo_id,
                               index,
                               ) -> Optional[Tuple[Any, str, str]]:
        resp = client.jm_get(url, False, False)

        # 第一次校验，不空则直接返回
        if not client.is_empty_image(resp):
            return resp, suffix, url

        # 下面进行重试
        jm_debug(
            '图片获取重试',
            f'photo-{photo_id}，图片序号为{index}，url=[{url}]'
        )

        # 重试点1：是否文件后缀名不对？
        for alter_suffix in JmModuleConfig.JM_IMAGE_SUFFIX:
            url = change_file_suffix(url, alter_suffix)
            resp = client.jm_get(url, False, False)
            if not client.is_empty_image(resp):
                jm_debug(
                    '图片获取重试 → 成功√',
                    f'更改请求后缀（{suffix} -> {alter_suffix}），url={url}'
                )
                return resp, alter_suffix, url

        # 结论：可能是图片到头了
        jm_debug(
            '图片获取重试 ← 失败×',
            f'更换后缀名不成功，停止爬取。'
            f'(推断本子长度<={index - 1}。当前图片序号为{index}，已经到达尽头，'
            f'photo-{photo_id})'
        )
