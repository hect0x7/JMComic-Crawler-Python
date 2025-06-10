from .jm_downloader import *

__DOWNLOAD_API_RET = Tuple[JmAlbumDetail, JmDownloader]


def download_batch(download_api,
                   jm_id_iter: Union[Iterable, Generator],
                   option=None,
                   downloader=None,
                   ) -> Set[__DOWNLOAD_API_RET]:
    """
    批量下载 album / photo

    一个album/photo，对应一个线程，对应一个option

    :param download_api: 下载api
    :param jm_id_iter: jmid (album_id, photo_id) 的迭代器
    :param option: 下载选项，所有的jmid共用一个option
    :param downloader: 下载器类
    """
    from common import multi_thread_launcher

    if option is None:
        option = JmModuleConfig.option_class().default()

    result = set()

    def callback(*ret):
        result.add(ret)

    multi_thread_launcher(
        iter_objs=set(
            JmcomicText.parse_to_jm_id(jmid)
            for jmid in jm_id_iter
        ),
        apply_each_obj_func=lambda aid: download_api(aid,
                                                     option,
                                                     downloader,
                                                     callback=callback,
                                                     ),
        wait_finish=True
    )

    return result


def download_album(jm_album_id,
                   option=None,
                   downloader=None,
                   callback=None,
                   check_exception=True,
                   ) -> Union[__DOWNLOAD_API_RET, Set[__DOWNLOAD_API_RET]]:
    """
    下载一个本子（album），包含其所有的章节（photo）

    当jm_album_id不是str或int时，视为批量下载，相当于调用 download_batch(download_album, jm_album_id, option, downloader)

    :param jm_album_id: 本子的禁漫车号
    :param option: 下载选项
    :param downloader: 下载器类
    :param callback: 返回值回调函数，可以拿到 album 和 downloader
    :param check_exception: 是否检查异常, 如果为True，会检查downloader是否有下载异常，并上抛PartialDownloadFailedException
    :return: 对于的本子实体类，下载器（如果是上述的批量情况，返回值为download_batch的返回值）
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_batch(download_album, jm_album_id, option, downloader)

    with new_downloader(option, downloader) as dler:
        album = dler.download_album(jm_album_id)

        if callback is not None:
            callback(album, dler)
        if check_exception:
            dler.raise_if_has_exception()
        return album, dler


def download_photo(jm_photo_id,
                   option=None,
                   downloader=None,
                   callback=None,
                   check_exception=True,
                   ):
    """
    下载一个章节（photo），参数同 download_album
    """
    if not isinstance(jm_photo_id, (str, int)):
        return download_batch(download_photo, jm_photo_id, option)

    with new_downloader(option, downloader) as dler:
        photo = dler.download_photo(jm_photo_id)

        if callback is not None:
            callback(photo, dler)
        if check_exception:
            dler.raise_if_has_exception()
        return photo, dler


def new_downloader(option=None, downloader=None) -> JmDownloader:
    if option is None:
        option = JmModuleConfig.option_class().default()

    if downloader is None:
        downloader = JmModuleConfig.downloader_class()

    return downloader(option)


def create_option_by_file(filepath):
    return JmModuleConfig.option_class().from_file(filepath)


def create_option_by_env(env_name='JM_OPTION_PATH'):
    from .cl import get_env

    filepath = get_env(env_name, None)
    ExceptionTool.require_true(filepath is not None,
                               f'未配置环境变量: {env_name}，请配置为option的文件路径')
    return create_option_by_file(filepath)


def create_option_by_str(text: str, mode=None):
    if mode is None:
        mode = PackerUtil.mode_yml
    data = PackerUtil.unpack_by_str(text, mode)[0]
    return JmModuleConfig.option_class().construct(data)


create_option = create_option_by_file
