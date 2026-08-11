import os
import inspect
from functools import wraps
from typing import NamedTuple
from time import perf_counter

from .jm_option import *
from .jm_task_context import bind_jm_task_context, get_jm_task_context, jm_task_context


def record_download_duration(context_key: str, clock=None):
    def decorator(func):
        # 装饰时只解析一次参数名，关键字调用无需在每次执行时重复 inspect。
        entity_param = tuple(inspect.signature(func).parameters)[1]

        def get_time():
            return perf_counter() if clock is None else clock()

        def get_entity(args, kwargs):
            # 常规位置参数走快路径；只有关键字调用才按参数名取值。
            if len(args) > 1:
                return args[1]
            return kwargs[entity_param]

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                entity = get_entity(args, kwargs)
                detail_call = isinstance(entity, Downloadable)
                # 顶层 ID 下载负责完整耗时，内部 detail 调用复用同一个计时上下文。
                if detail_call and get_jm_task_context().get(context_key) is not None:
                    return await func(*args, **kwargs)

                started_at = get_time()
                with jm_task_context(**{context_key: started_at}):
                    result = await func(*args, **kwargs)
                    # detail 入口直接记录传入实体；ID 入口记录下载后返回的实体。
                    detail = entity if detail_call else result
                    detail.duration = get_time() - started_at
                    return result

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            entity = get_entity(args, kwargs)
            detail_call = isinstance(entity, Downloadable)
            # 顶层 ID 下载负责完整耗时，内部 detail 调用复用同一个计时上下文。
            if detail_call and get_jm_task_context().get(context_key) is not None:
                return func(*args, **kwargs)

            started_at = get_time()
            with jm_task_context(**{context_key: started_at}):
                result = func(*args, **kwargs)
                # detail 入口直接记录传入实体；ID 入口记录下载后返回的实体。
                detail = entity if detail_call else result
                detail.duration = get_time() - started_at
                return result

        return wrapper

    return decorator


class DownloadManifest:
    """一次顶层下载产生的聚合文件清单。"""

    def __init__(self):
        self.image_filepath_list: List[str] = []
        self.export_filepath_dict: Dict[str, List[str]] = {}
        self.duration: Optional[float] = None  # 顶层任务完整耗时（秒）

    def get_export_filepath_list(self, suffix: str) -> List[str]:
        normalized_suffix = str(suffix).lower().lstrip('.')
        return self.export_filepath_dict.get(normalized_suffix, [])


def catch_exception(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self: JmDownloader
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            detail: JmBaseEntity = args[0]
            if detail.is_image():
                detail: JmImageDetail
                jm_log('image.failed', f'图片下载失败: [{detail.download_url}], 异常: [{e}]', e)
                self.download_failed_image.append((detail, e))

            elif detail.is_photo():
                detail: JmPhotoDetail
                jm_log('photo.failed', f'章节下载失败: [{detail.id}], 异常: [{e}]', e)
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
        if image.exists and image.cache:
            jm_log('image.before',
                   f'图片已存在: {image.tag} ← [{img_save_path}]'
                   )
            return
        jm_log('image.before',
               f'图片准备下载: {image.tag}, [{image.img_url}] → [{img_save_path}]'
               )

    def after_image(self, image: JmImageDetail, img_save_path):
        jm_log('image.after',
               f'图片下载完成: {image.tag}, [{image.img_url}] → [{img_save_path}]')


class BaseDownloader(DownloadCallback):
    """
    不含 I/O 调度的公共基类，负责回调、钩子、Features 注册等无 I/O 通用逻辑。
    """

    def __init__(self, option: JmOption):
        self.option = option
        self.client = None
        # 下载成功的记录dict
        self.download_success_dict: Dict[JmAlbumDetail, Dict[JmPhotoDetail, List[Tuple[str, JmImageDetail]]]] = {}
        # 下载失败的记录list
        self.download_failed_image: List[Tuple[JmImageDetail, BaseException]] = []
        self.download_failed_photo: List[Tuple[JmPhotoDetail, BaseException]] = []
        # 每次顶层下载对应的聚合清单
        self.manifest_dict: Dict[DetailEntity, DownloadManifest] = {}
        # 当前顶层下载注册的 Feature 列表
        self._feature_list: List = []

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
        # 触发匹配 after_album 的 Feature
        self._invoke_features_for('after_album', album=album, downloader=self)

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
        # 触发匹配 after_photo 的 Feature
        self._invoke_features_for('after_photo', photo=photo, downloader=self)

    def before_image(self, image: JmImageDetail, img_save_path):
        super().before_image(image, img_save_path)
        self.option.call_all_plugin(
            'before_image',
            image=image,
            downloader=self,
        )

    def after_image(self, image: JmImageDetail, img_save_path):
        super().after_image(image, img_save_path)
        self.option.call_all_plugin(
            'after_image',
            image=image,
            downloader=self,
        )
        photo = image.from_photo
        album = photo.from_album
        self.download_success_dict.get(album).get(photo).append((image.save_path, image))

    def begin_manifest(self, detail: DetailEntity) -> DownloadManifest:
        manifest = DownloadManifest()
        self.manifest_dict[detail] = manifest
        return manifest

    def resolve_manifest_detail(self, detail: DetailEntity) -> Optional[DetailEntity]:
        if detail in self.manifest_dict:
            return detail

        if detail.is_photo() and detail.from_album in self.manifest_dict:
            return detail.from_album

        return None

    def record_export_filepath(self, detail: DetailEntity, filepath: str) -> None:
        manifest_detail = self.resolve_manifest_detail(detail)
        if manifest_detail is None:
            from .jm_toolkit import ExceptionTool
            ExceptionTool.raises(f'当前实体没有活动的下载清单: {detail}')

        suffix = os.path.splitext(filepath)[1].lower().lstrip('.')
        if suffix == '':
            return

        manifest = self.manifest_dict[manifest_detail]
        manifest.export_filepath_dict.setdefault(suffix, []).append(filepath)

    def finish_manifest(self, detail: DetailEntity) -> DownloadManifest:
        manifest = self.manifest_dict[detail]
        if detail.is_album():
            success_dict = self.download_success_dict.get(detail, {})
            success_groups = [
                success_list
                for _, success_list in sorted(
                    success_dict.items(),
                    key=lambda item: item[0].index,
                )
            ]
        else:
            success_groups = [
                self.download_success_dict.get(detail.from_album, {}).get(detail, [])
            ]

        manifest.image_filepath_list = [
            image.save_path
            for success_list in success_groups
            for _, image in sorted(success_list, key=lambda item: item[1].index)
        ]
        return manifest

    @staticmethod
    def _require_feature_context() -> str:
        from .jm_toolkit import ExceptionTool

        download_type = get_jm_task_context().get('download_type')
        ExceptionTool.require_true(
            download_type in ('album', 'photo'),
            'Feature 注册与执行必须位于下载任务上下文中，请使用 '
            "jm_task_context(download_type='album') 或 "
            "jm_task_context(download_type='photo') 进行包裹",
        )
        return download_type

    def add_features(self, features):
        """
        为当前顶层下载注册 Feature。

        :param features: Feature / FeatureChain / list / None
        """
        if features is None:
            return

        from .jm_feature import FeatureChain, Feature
        from .jm_toolkit import ExceptionTool
        self._require_feature_context()

        if isinstance(features, list):
            for f in features:
                self.add_features(f)
        elif isinstance(features, FeatureChain):
            for f in features.to_list():
                self._feature_list.append(f)
        elif isinstance(features, Feature):
            self._feature_list.append(features)
        else:
            ExceptionTool.raises(f'不支持的 extra 类型: {type(features)}，请传入 Feature / FeatureChain / list / None')

    def _invoke_features_for(self, when: str, **kwargs):
        """
        在指定钩子(when)中触发匹配的 Feature。

        :param when: 当前钩子名，如 'after_album', 'after_photo'
        :param kwargs: album, photo, downloader 等上下文
        """
        if len(self._feature_list) == 0:
            return

        download_type = self._require_feature_context()
        for feature in self._feature_list:
            if feature.should_invoke(when):
                try:
                    feature.invoke(self.option, when=when, **kwargs)
                except Exception as e:
                    jm_log('downloader.feature.exception', f'Feature执行失败: [{feature}], 下载类型: [{download_type}], 异常: [{e}]',
                           e)

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


class DownloadResult(NamedTuple):
    """单个下载结果。

    支持解包：album, dler = download_album(id)
    也支持属性访问：result.detail, result.downloader
    NamedTuple 是 tuple 子类，isinstance(result, tuple) 为 True。
    """
    detail: DetailEntity
    downloader: BaseDownloader

    @property
    def manifest(self) -> DownloadManifest:
        return self.downloader.manifest_dict[self.detail]

    @property
    def duration(self) -> Optional[float]:
        """顶层下载耗时，单位：秒。"""
        return self.manifest.duration


class BatchResult(set):
    """批量下载结果集。

    继承 set，完全兼容旧写法 for album, dler in result。
    新增 .failed 属性，记录失败的 jm_id 和对应异常。
    """

    def __init__(self):
        super().__init__()
        self.failed: Dict[str, BaseException] = {}

    @property
    def all_succeeded(self) -> bool:
        return len(self.failed) == 0

    @property
    def total(self) -> int:
        """预期总数（成功 + 失败）"""
        return len(self) + len(self.failed)


class JmDownloader(BaseDownloader):
    """
    JmDownloader = BaseDownloader + 同步 I/O 调度逻辑
    """

    def __init__(self, option: JmOption):
        super().__init__(option)
        self.client = self.create_client()

    def create_client(self):
        """
        创建该downloader使用的client。
        """
        return self.option.build_jm_client()

    @record_download_duration('album_started_at')
    def download_album(self, album_id):
        album = self.client.get_album_detail(album_id)
        self.begin_manifest(album)
        try:
            self.download_by_album_detail(album)
        finally:
            self.finish_manifest(album)
        return album

    @record_download_duration('album_started_at')
    def download_by_album_detail(self, album: JmAlbumDetail):
        album.save_path = self.option.dir_rule.decide_album_root_dir(album)
        self.before_album(album)
        if album.skip:
            return
        self.execute_on_condition(
            iter_objs=album,
            apply=self.download_by_photo_detail,
            count_batch=self.option.decide_photo_batch_count(album)
        )
        self.after_album(album)

    @record_download_duration('photo_started_at')
    def download_photo(self, photo_id):
        photo = self.client.get_photo_detail(photo_id)
        self.begin_manifest(photo)
        try:
            self.download_by_photo_detail(photo)
        finally:
            self.finish_manifest(photo)
        return photo

    @catch_exception
    @record_download_duration('photo_started_at')
    def download_by_photo_detail(self, photo: JmPhotoDetail):
        photo.save_path = self.option.decide_image_save_dir(photo)
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
    @record_download_duration('image_started_at')
    def download_by_image_detail(self, image: JmImageDetail):
        img_save_path = self.option.decide_image_filepath(image)
        image.save_path = img_save_path
        image.exists = file_exists(img_save_path)
        image.cache = self.option.decide_download_cache(image)

        self.before_image(image, img_save_path)
        if image.skip:
            return

        if image.cache and image.exists:
            self.after_image(image, img_save_path)
            return

        decode_image = self.option.decide_download_image_decode(image)
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

        apply = bind_jm_task_context(apply)

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
        before_class = JmModuleConfig.downloader_class()
        JmModuleConfig.CLASS_DOWNLOADER = cls
        after_class = JmModuleConfig.downloader_class()
        jm_log(
            'downloader.use',
            f'替换 Downloader class: '
            f'[{before_class.__module__}.{before_class.__qualname__}] -> '
            f'[{after_class.__module__}.{after_class.__qualname__}]'
        )


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
