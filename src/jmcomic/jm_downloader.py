from .jm_option import *


def catch_exception(func):
    from functools import wraps

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self: JmDownloader
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            detail: JmBaseEntity = args[0]
            if detail.is_image():
                detail: JmImageDetail
                jm_log('image.failed', f'图片下载失败: [{detail.download_url}], 异常: [{e}]')
                self.download_failed_image.append((detail, e))

            elif detail.is_photo():
                detail: JmPhotoDetail
                jm_log('photo.failed', f'章节下载失败: [{detail.id}], 异常: [{e}]')
                self.download_failed_photo.append((detail, e))

            raise e

    return wrapper


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
        if image.exists:
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
        self.client = option.build_jm_client()
        # 下载成功的记录dict
        self.download_success_dict: Dict[JmAlbumDetail, Dict[JmPhotoDetail, List[Tuple[str, JmImageDetail]]]] = {}
        # 下载失败的记录list
        self.download_failed_image: List[Tuple[JmImageDetail, BaseException]] = []
        self.download_failed_photo: List[Tuple[JmPhotoDetail, BaseException]] = []

    def download_album(self, album_id):
        album = self.client.get_album_detail(album_id)
        self.download_by_album_detail(album)
        return album

    def download_by_album_detail(self, album: JmAlbumDetail):
        self.before_album(album)
        if album.skip:
            return
        self.execute_on_condition(
            iter_objs=album,
            apply=self.download_by_photo_detail,
            count_batch=self.option.decide_photo_batch_count(album)
        )
        self.after_album(album)

    def download_photo(self, photo_id):
        photo = self.client.get_photo_detail(photo_id)
        self.download_by_photo_detail(photo)
        return photo

    @catch_exception
    def download_by_photo_detail(self, photo: JmPhotoDetail):
        self.client.check_photo(photo)

        self.before_photo(photo)
        if photo.skip:
            return
        self.execute_on_condition(
            iter_objs=photo,
            apply=self.download_by_image_detail,
            count_batch=self.option.decide_image_batch_count(photo)
        )
        self.after_photo(photo)

    @catch_exception
    def download_by_image_detail(self, image: JmImageDetail):
        img_save_path = self.option.decide_image_filepath(image)

        image.save_path = img_save_path
        image.exists = file_exists(img_save_path)

        self.before_image(image, img_save_path)

        if image.skip:
            return

        # let option decide use_cache and decode_image
        use_cache = self.option.decide_download_cache(image)
        decode_image = self.option.decide_download_image_decode(image)

        # skip download
        if use_cache is True and image.exists:
            return

        self.client.download_by_image_detail(
            image,
            img_save_path,
            decode_image=decode_image,
        )

        self.after_image(image, img_save_path)

    def execute_on_condition(self,
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

    @property
    def all_success(self) -> bool:
        """
        是否成功下载了全部图片

        该属性需要等到downloader的全部download_xxx方法完成后才有意义。

        注意！如果使用了filter机制，例如通过filter只下载3张图片，那么all_success也会为False
        """
        if self.has_download_failures:
            return False

        for album, photo_dict in self.download_success_dict.items():
            if len(album) != len(photo_dict):
                return False

            for photo, image_list in photo_dict.items():
                if len(photo) != len(image_list):
                    return False

        return True

    @property
    def has_download_failures(self):
        return len(self.download_failed_image) != 0 or len(self.download_failed_photo) != 0

    # 下面是回调方法

    def before_album(self, album: JmAlbumDetail):
        super().before_album(album)
        self.download_success_dict.setdefault(album, {})
        self.option.call_all_plugin(
            'before_album',
            album=album,
            downloader=self,
        )

    def after_album(self, album: JmAlbumDetail):
        super().after_album(album)
        self.option.call_all_plugin(
            'after_album',
            album=album,
            downloader=self,
        )

    def before_photo(self, photo: JmPhotoDetail):
        super().before_photo(photo)
        self.download_success_dict.setdefault(photo.from_album, {})
        self.download_success_dict[photo.from_album].setdefault(photo, [])
        self.option.call_all_plugin(
            'before_photo',
            photo=photo,
            downloader=self,
        )

    def after_photo(self, photo: JmPhotoDetail):
        super().after_photo(photo)
        self.option.call_all_plugin(
            'after_photo',
            photo=photo,
            downloader=self,
        )

    def before_image(self, image: JmImageDetail, img_save_path):
        super().before_image(image, img_save_path)
        self.option.call_all_plugin(
            'before_image',
            image=image,
            downloader=self,
        )

    def after_image(self, image: JmImageDetail, img_save_path):
        super().after_image(image, img_save_path)
        photo = image.from_photo
        album = photo.from_album

        self.download_success_dict.get(album).get(photo).append((img_save_path, image))
        self.option.call_all_plugin(
            'after_image',
            image=image,
            downloader=self,
        )

    def raise_if_has_exception(self):
        if not self.has_download_failures:
            return
        msg_ls = ['部分下载失败', '', '']

        if len(self.download_failed_photo) != 0:
            msg_ls[1] = f'共{len(self.download_failed_photo)}个章节下载失败: {self.download_failed_photo}'

        if len(self.download_failed_image) != 0:
            msg_ls[2] = f'共{len(self.download_failed_image)}个图片下载失败: {self.download_failed_image}'

        ExceptionTool.raises(
            '\n'.join(msg_ls),
            {'downloader': self},
            PartialDownloadFailedException,
        )

    # 下面是对with语法的支持

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            jm_log('dler.exception',
                   f'{self.__class__.__name__} Exit with exception: {exc_type, str(exc_val)}'
                   )

    @classmethod
    def use(cls, *args, **kwargs):
        """
        让本类替换JmModuleConfig.CLASS_DOWNLOADER
        """
        JmModuleConfig.CLASS_DOWNLOADER = cls


class DoNotDownloadImage(JmDownloader):
    """
    不会下载任何图片的Downloader，用作测试
    """

    def download_by_image_detail(self, image: JmImageDetail):
        # ensure make dir
        self.option.decide_image_filepath(image)


class JustDownloadSpecificCountImage(JmDownloader):
    """
    只下载特定数量图片的Downloader，用作测试
    """
    from threading import Lock

    count_lock = Lock()
    count = 0

    @catch_exception
    def download_by_image_detail(self, image: JmImageDetail):
        # ensure make dir
        self.option.decide_image_filepath(image)

        if self.try_countdown():
            return super().download_by_image_detail(image)

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
