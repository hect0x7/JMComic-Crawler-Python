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
    album_detail: JmAlbumDetail = jm_client.get_album_detail(jm_album_id)

    jm_debug('download_album',
             f'获得album_detail成功，准备下载。'
             f'本子作者是【{album_detail.author}】，一共有{len(album_detail)}集本子')

    def download_photo(index: int,
                       photo_detail: JmPhotoDetail,
                       debug_topic='download_album_photo',
                       ):
        jm_client.ensure_photo_can_use(photo_detail)

        jm_debug(debug_topic,
                 f"下载第[{index + 1}]集: "
                 f"图片数为[{len(photo_detail)}]，"
                 f"标题为：({photo_detail.title}) "
                 f"-- photo {photo_detail.photo_id}")

        download_by_photo_detail(
            photo_detail,
            option,
        )

        jm_debug(debug_topic,
                 f"下载完成：({photo_detail.title}) "
                 f"-- photo {photo_detail.photo_id}")

    thread_pool_executor(
        iter_objs=enumerate(album_detail),
        apply_each_obj_func=download_photo,
    )


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
    use_cache = option.download_use_disk_cache
    decode_image = option.download_image_then_decode
    jm_client.ensure_photo_can_use(photo_detail)

    # 下载每个图片的函数
    def download_image(index, img_detail, debug_topic='download_images_of_photo'):
        img_save_path = option.decide_image_filepath(photo_detail, index)

        # 已下载过，缓存命中
        if use_cache is True and file_exists(img_save_path):
            jm_debug(debug_topic, f'photo-{img_detail.aid}: '
                                  f'图片{img_detail.filename}已下载过，'
                                  f'命中磁盘缓存（{img_save_path}）')
            return

        # 开始下载
        jm_client.download_by_image_detail(
            img_detail,
            img_save_path,
            decode_image=decode_image,
        )

        jm_debug(debug_topic, f'photo-{img_detail.aid}: '
                              f'图片{img_detail.filename}下载完成：'
                              f'[{img_detail.img_url}] → [{img_save_path}]')

    length = len(photo_detail)
    # 根据图片数，决定下载策略
    if length <= option.download_multi_thread_photo_len_limit:
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
            batch_size=option.download_multi_thread_photo_batch_count
        )


def renew_jm_default_domain():
    """
    由于禁漫的域名经常变化，调用此方法可以获取一个当前可用的最新的域名 domain，
    并且设置把 domain 设置为禁漫模块的默认域名。
    这样一来，配置文件也不用配置域名了，一切都在运行时动态获取。
    """
    domain = JmcomicText.parse_to_jm_domain(JmModuleConfig.get_jmcomic_url())
    JmModuleConfig.DOMAIN = domain
    return domain


def build_client(option: Optional[JmOption]) -> Tuple[JmOption, JmcomicClient]:
    """
    处理option的判空，并且创建jm_client
    """
    if option is None:
        option = JmOption.default()
        option.client_config['domain'] = renew_jm_default_domain()
    jm_client = option.build_jm_client()
    return option, jm_client


def create_option(filepath: str) -> JmOption:
    """
    创建 JmOption，同时检查域名是否配置，未配置则补上配置
    @param filepath:
    @return:
    """
    option = JmOption.create_from_file(filepath)
    client_config = option.client_config
    key = 'domain'
    if client_config.get(key, None) is None or client_config[key] is None:
        client_config[key] = renew_jm_default_domain()
    return option
