from .jm_option import *


def download_album(jm_album_id, option=None):
    """
    下载一个本子集，入口api
    @param jm_album_id: 禁漫的本子的id，类型可以是str/int/iterable[str]。
    如果是iterable[str]，则会调用批量下载方法 download_album_batch
    @param option: 下载选项，为空默认是 JmOption.default()
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_album_batch(jm_album_id, option)

    option, jm_client = build_client(option)
    album: JmAlbumDetail = jm_client.get_album_detail(jm_album_id)

    jm_debug('album',
             f'本子获取成功: [{album.id}], '
             f'作者: [{album.author}], '
             f'章节数: [{len(album)}]'
             f'标题: [{album.title}], '
             )

    def download_photo(photo: JmPhotoDetail,
                       debug_topic='photo',
                       ):
        jm_client.ensure_photo_can_use(photo)

        jm_debug(debug_topic,
                 f'开始下载章节: {photo.id} ({photo.album_id}[{photo.index}/{len(album)}]), '
                 f'标题: [{photo.title}], '
                 f'图片数为[{len(photo)}]')

        download_by_photo_detail(photo, option)

        jm_debug(debug_topic, f'章节下载完成: {photo.id} ({photo.album_id}[{photo.index}/{len(album)}])')

    thread_pool_executor(
        iter_objs=album,
        apply_each_obj_func=download_photo,
    )

    jm_debug('album', f'本子下载完成: [{album.id}]')


def download_album_batch(jm_album_id_iter: Union[Iterable, Generator],
                         option=None,
                         wait_finish=True,
                         ) -> List[Thread]:
    """
    批量下载album，每个album一个线程，使用的是同一个option。

    @param jm_album_id_iter: album_id的可迭代对象
    @param option: 下载选项，为空默认是 JmOption.default()
    @param wait_finish: 是否要等待这些下载线程全部完成
    @return 返回值是List[Thread]，里面是每个下载漫画的线程。
    """
    if option is None:
        option = JmOption.default()

    return thread_pool_executor(
        iter_objs=((album_id, option) for album_id in jm_album_id_iter),
        apply_each_obj_func=download_album,
        wait_finish=wait_finish,
    )


def download_photo(jm_photo_id, option=None):
    """
    下载一个本子的一章，入口api
    """
    option, jm_client = build_client(option)
    photo_detail = jm_client.get_photo_detail(jm_photo_id)
    download_by_photo_detail(photo_detail, option)


def download_by_photo_detail(photo_detail: JmPhotoDetail,
                             option=None,
                             ):
    """
    下载一个本子的一章，根据 photo_detail
    @param photo_detail: 本子章节信息
    @param option: 选项
    """
    option, jm_client = build_client(option)

    # 下载准备
    use_cache = option.download_cache
    decode_image = option.download_image_decode
    jm_client.ensure_photo_can_use(photo_detail)

    # 下载每个图片的函数
    def download_image(index, image: JmImageDetail, debug_topic='image'):
        img_save_path = option.decide_image_filepath(photo_detail, index)
        debug_tag = f'{image.aid}/{image.filename} [{index + 1}/{len(photo_detail)}]'

        # 已下载过，缓存命中
        if use_cache is True and file_exists(img_save_path):
            jm_debug(debug_topic,
                     f'图片已存在: {debug_tag} ← [{img_save_path}]')
            return

        # 开始下载
        jm_client.download_by_image_detail(
            image,
            img_save_path,
            decode_image=decode_image,
        )

        jm_debug(debug_topic,
                 f'图片下载完成: {debug_tag}, [{image.img_url}] → [{img_save_path}]')

    length = len(photo_detail)
    # 根据图片数，决定下载策略
    if length <= option.download_threading_batch_count:
        # 如果图片数小的话，直接使用多线程下载，一张图一个线程。
        multi_thread_launcher(
            iter_objs=enumerate(photo_detail),
            apply_each_obj_func=download_image,
        )
    else:
        # 如果图片数多的话，还是分批下载。
        multi_task_launcher_batch(
            iter_objs=enumerate(photo_detail),
            apply_each_obj_func=download_image,
            batch_size=option.download_threading_batch_count
        )


def build_client(option: Optional[JmOption]) -> Tuple[JmOption, JmcomicClient]:
    """
    处理option的判空，并且创建jm_client
    """
    if option is None:
        option = JmOption.default()

    jm_client = option.build_jm_client()
    return option, jm_client


def create_option(filepath: str) -> JmOption:
    option = JmOption.from_file(filepath)
    return option
