from .jm_option import *


# noinspection PyMethodMayBeStatic
class DownloadCallback:

    def before_album(self, album: JmAlbumDetail):
        jm_log('album.before',
               f'本子获取成功: [{album.id}], '
               f'作者: [{album.author}], '
               f'章节数: [{len(album)}], '
               f'总页数: [{album.page_count}], '
               f'标题: [{album.name}], '
               f'关键词: {album.tags}'
               )

    def after_album(self, album: JmAlbumDetail):
        jm_log('album.after', f'本子下载完成: [{album.id}]')

    def before_photo(self, photo: JmPhotoDetail):
        jm_log('photo.before',
               f'开始下载章节: {photo.id} ({photo.album_id}[{photo.index}/{len(photo.from_album)}]), '
               f'标题: [{photo.name}], '
               f'图片数为[{len(photo)}]'
               )

    def after_photo(self, photo: JmPhotoDetail):
        jm_log('photo.after',
               f'章节下载完成: [{photo.id}] ({photo.album_id}[{photo.index}/{len(photo.from_album)}])')

    def before_image(self, image: JmImageDetail, img_save_path):
        if image.is_exists:
            jm_log('image.before',
                   f'图片已存在: {image.tag} ← [{img_save_path}]'
                   )
        else:
            jm_log('image.before',
                   f'图片准备下载: {image.tag}, [{image.img_url}] → [{img_save_path}]'
                   )

    def after_image(self, image: JmImageDetail, img_save_path):
        jm_log('image.after',
               f'图片下载完成: {image.tag}, [{image.img_url}] → [{img_save_path}]')


class JmDownloader(DownloadCallback):
    """
    JmDownloader = JmOption + 调度逻辑
    """

    def __init__(self, option: JmOption) -> None:
        self.option = option
        # 收集所有下载的image，为plugin提供数据
        self.all_downloaded: Dict[JmAlbumDetail, Dict[JmPhotoDetail, List[Tuple[str, JmImageDetail]]]] = {}

    def download_album(self, album_id):
        client = self.client_for_album(album_id)
        album = client.get_album_detail(album_id)
        self.download_by_album_detail(album, client)

    def download_by_album_detail(self, album: JmAlbumDetail, client: JmcomicClient):
        self.before_album(album)
        self.execute_by_condition(
            iter_objs=album,
            apply=lambda photo: self.download_by_photo_detail(photo, client),
            count_batch=self.option.decide_photo_batch_count(album)
        )
        self.after_album(album)

    def download_photo(self, photo_id):
        client = self.client_for_photo(photo_id)
        photo = client.get_photo_detail(photo_id)
        self.download_by_photo_detail(photo, client)

    def download_by_photo_detail(self, photo: JmPhotoDetail, client: JmcomicClient):
        client.check_photo(photo)

        self.before_photo(photo)
        self.execute_by_condition(
            iter_objs=photo,
            apply=lambda image: self.download_by_image_detail(image, client),
            count_batch=self.option.decide_image_batch_count(photo)
        )
        self.after_photo(photo)

    def download_by_image_detail(self, image: JmImageDetail, client: JmcomicClient):
        img_save_path = self.option.decide_image_filepath(image)

        image.save_path = img_save_path
        image.is_exists = file_exists(img_save_path)

        self.before_image(image, img_save_path)

        # let option decide use_cache and decode_image
        use_cache = self.option.decide_download_cache(image)
        decode_image = self.option.decide_download_image_decode(image)

        # skip download
        if use_cache is True and image.is_exists:
            return

        client.download_by_image_detail(
            image,
            img_save_path,
            decode_image=decode_image,
        )
        self.after_image(image, img_save_path)

    # noinspection PyMethodMayBeStatic
    def execute_by_condition(self,
                             iter_objs: DetailEntity,
                             apply: Callable,
                             count_batch: int,
                             ):
        """
        调度本子/章节的下载
        """
        iter_objs = self.do_filter(iter_objs)
        count_real = len(iter_objs)

        if count_real == 0:
            return

        if count_batch >= count_real:
            # 一个图/章节 对应 一个线程
            multi_thread_launcher(
                iter_objs=iter_objs,
                apply_each_obj_func=apply,
            )
        else:
            # 创建batch个线程的线程池
            thread_pool_executor(
                iter_objs=iter_objs,
                apply_each_obj_func=apply,
                max_workers=count_batch,
            )

    # noinspection PyMethodMayBeStatic
    def do_filter(self, detail: DetailEntity):
        """
        该方法可用于过滤本子/章节，默认不会做过滤。
        例如:
        只想下载 本子的最新一章，返回 [album[-1]]
        只想下载 章节的前10张图片，返回 [photo[:10]]

        :param detail: 可能是本子或者章节，需要自行使用 isinstance / detail.is_xxx 判断
        :returns: 只想要下载的 本子的章节 或 章节的图片
        """
        return detail

    # noinspection PyUnusedLocal
    def client_for_album(self, jm_album_id) -> JmcomicClient:
        """
        默认情况下，所有的JmDownloader共用一个JmcomicClient
        """
        return self.option.build_jm_client()

    # noinspection PyUnusedLocal
    def client_for_photo(self, jm_photo_id) -> JmcomicClient:
        """
        默认情况下，所有的JmDownloader共用一个JmcomicClient
        """
        return self.option.build_jm_client()

    # 下面是回调方法

    def before_album(self, album: JmAlbumDetail):
        super().before_album(album)
        self.all_downloaded.setdefault(album, {})

    def before_photo(self, photo: JmPhotoDetail):
        super().before_photo(photo)
        self.all_downloaded.setdefault(photo.from_album, {})
        self.all_downloaded[photo.from_album].setdefault(photo, [])

    def after_album(self, album: JmAlbumDetail):
        super().after_album(album)
        self.option.call_all_plugin(
            'after_album',
            album=album,
            downloader=self,
        )

    def after_photo(self, photo: JmPhotoDetail):
        super().after_photo(photo)
        self.option.call_all_plugin(
            'after_photo',
            photo=photo,
            downloader=self,
        )

    def after_image(self, image: JmImageDetail, img_save_path):
        super().after_image(image, img_save_path)
        photo = image.from_photo
        album = photo.from_album

        self.all_downloaded.get(album).get(photo).append((img_save_path, image))

    # 下面是对with语法的支持

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            jm_log('dler.exception',
                   f'{self.__class__.__name__} Exit with exception: {exc_type, exc_val}'
                   )

    @classmethod
    def use(cls, *args, **kwargs):
        """
        让本类替换JmModuleConfig.CLASS_DOWNLOADER
        """
        JmModuleConfig.CLASS_DOWNLOADER = cls


class DoNotDownloadImage(JmDownloader):
    """
    本类仅用于测试

    用法：

    JmModuleConfig.CLASS_DOWNLOADER = DoNotDownloadImage
    """

    def download_by_image_detail(self, image: JmImageDetail, client: JmcomicClient):
        # ensure make dir
        self.option.decide_image_filepath(image)
        pass


class JustDownloadSpecificCountImage(JmDownloader):
    from threading import Lock

    count_lock = Lock()
    count = 0

    def __init__(self, option: JmOption) -> None:
        super().__init__(option)

    def download_by_image_detail(self, image: JmImageDetail, client: JmcomicClient):
        # ensure make dir
        self.option.decide_image_filepath(image)

        if self.try_countdown():
            return super().download_by_image_detail(image, client)

    def try_countdown(self):
        if self.count < 0:
            return False

        with self.count_lock:
            if self.count < 0:
                return False

            self.count -= 1

            return self.count >= 0

    @classmethod
    def use(cls, count):
        cls.count = count
        super().use()
