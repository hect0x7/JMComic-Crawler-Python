from .jm_downloader import *


def download_batch(download_api,
                   jm_id_iter: Union[Iterable, Generator],
                   option=None,
                   ):
    """
    批量下载 album / photo
    一个album/photo，对应一个线程，对应一个option

    @param download_api: 下载api
    @param jm_id_iter: jmid (album_id, photo_id) 的迭代器
    @param option: 下载选项，对所有的jmid使用同一个，默认是 JmOption.default()
    """
    from common import multi_thread_launcher

    if option is None:
        option = JmOption.default()

    return multi_thread_launcher(
        iter_objs=set(
            JmcomicText.parse_to_album_id(jmid)
            for jmid in jm_id_iter
        ),
        apply_each_obj_func=lambda aid: download_api(aid, option),
    )


def download_album(jm_album_id, option=None):
    """
    下载一个本子
    @param jm_album_id: 禁漫的本子的id，类型可以是str/int/iterable[str]。
    如果是iterable[str]，则会调用 download_album_batch
    @param option: 下载选项，为空默认是 JmOption.default()
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_batch(download_album, jm_album_id, option)

    with new_downloader(option) as dler:
        dler.download_album(jm_album_id)


def download_photo(jm_photo_id, option=None):
    """
    下载一个章节
    """
    if not isinstance(jm_photo_id, (str, int)):
        return download_batch(download_photo, jm_photo_id, option)

    with new_downloader(option) as dler:
        dler.download_photo(jm_photo_id)


def new_downloader(option=None):
    if option is None:
        option = JmModuleConfig.option_class().default()

    return JmModuleConfig.downloader_class()(option)


def create_option(filepath):
    return JmModuleConfig.option_class().from_file(filepath)
