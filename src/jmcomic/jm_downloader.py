from .jm_option import *


class JmDownloadException(Exception):
    pass


# noinspection PyMethodMayBeStatic
class DownloadCallback:

    def before_album(self, album: JmAlbumDetail):
        jm_debug('album-before',
                 f'本子获取成功: [{album.id}], '
                 f'作者: [{album.author}], '
                 f'章节数: [{len(album)}], '
                 f'标题: [{album.title}], '
                 )

    def after_album(self, album: JmAlbumDetail):
        jm_debug('album-after', f'本子下载完成: [{album.id}]')

    def before_photo(self, photo: JmPhotoDetail):
        jm_debug('photo-before',
                 f'开始下载章节: {photo.id} ({photo.album_id}[{photo.index}/{len(photo.from_album)}]), '
                 f'标题: [{photo.title}], '
                 f'图片数为[{len(photo)}]'
                 )

    def after_photo(self, photo: JmPhotoDetail):
        jm_debug('photo-after',
                 f'章节下载完成: {photo.id} ({photo.album_id}[{photo.index}/{len(photo.from_album)}])')

    def before_image(self, image: JmImageDetail, img_save_path):
        if image.is_exists:
            jm_debug('image-before',
                     f'图片已存在: {image.tag} ← [{img_save_path}]'
                     )
        else:
            jm_debug('image-before',
                     f'图片准备下载: {image.tag}, [{image.img_url}] → [{img_save_path}]'
                     )

    def after_image(self, image: JmImageDetail, img_save_path):
        jm_debug('image-after',
                 f'图片下载完成: {image.tag}, [{image.img_url}] → [{img_save_path}]')


class JmDownloader(DownloadCallback):
    """
    JmDownloader = JmOption + 调度逻辑
    """

    def __init__(self, option) -> None:
        self.option = option
        self.use_cache = self.option.download_cache
        self.decode_image = self.option.download_image_decode

    def download_album(self, album_id):
        client = self.client_for_album(album_id)
        album = client.get_album_detail(album_id)

        self.before_album(album)
        self.download_by_album_detail(album, client)
        self.after_album(album)

    def download_by_album_detail(self, album: JmAlbumDetail, client: JmcomicClient):
        self.execute_by_condition(
            iter_objs=album,
            apply=lambda photo: self.download_by_photo_detail(photo, client),
            count_batch=self.option.decide_photo_batch_count(album)
        )

    def download_photo(self, photo_id):
        client = self.client_for_photo(photo_id)
        photo = client.get_photo_detail(photo_id)

        self.before_photo(photo)
        self.download_by_photo_detail(photo, client)
        self.after_photo(photo)

    def download_by_photo_detail(self, photo: JmPhotoDetail, client: JmcomicClient):
        client.check_photo(photo)

        self.execute_by_condition(
            iter_objs=photo,
            apply=lambda image: self.download_by_image_detail(image, client),
            count_batch=self.option.decide_image_batch_count(photo)
        )

    def download_by_image_detail(self, image: JmImageDetail, client: JmcomicClient):
        img_save_path = self.option.decide_image_filepath(image)
        image.is_exists = file_exists(img_save_path)

        self.before_image(image, img_save_path)
        if self.use_cache is True and image.is_exists:
            return
        client.download_by_image_detail(
            image,
            img_save_path,
            decode_image=self.decode_image,
        )
        self.after_image(image, img_save_path)

    # noinspection PyMethodMayBeStatic
    def execute_by_condition(self, iter_objs, apply: Callable, count_batch: int):
        """
        章节/图片的下载调度逻辑
        """
        count_real = len(iter_objs)

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

    # noinspection PyUnusedLocal
    def client_for_album(self, jm_album_id):
        """
        默认情况下，每次调用JmDownloader的download_album或download_photo,
        都会使用一个新的 JmcomicClient
        """
        return self.option.new_jm_client()

    # noinspection PyUnusedLocal
    def client_for_photo(self, jm_photo_id):
        """
        默认情况下，每次调用JmDownloader的download_album或download_photo,
        都会使用一个新的 JmcomicClient
        """
        return self.option.new_jm_client()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            jm_debug('exception',
                     f'{self.__class__.__name__} Exit with exception: {exc_type, exc_val}'
                     )
