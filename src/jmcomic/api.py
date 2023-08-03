from .jm_downloader import *


def download_album_batch(jm_album_id_iter: Union[Iterable, Generator],
                         option=None,
                         ):
    """
    批量下载album.
    一个album，对应一个线程，对应一个option

    @param jm_album_id_iter: album_id的迭代器
    @param option: 下载选项，为空默认是 JmOption.default()
    """
    from common import multi_thread_launcher

    return multi_thread_launcher(
        iter_objs=set(
            JmcomicText.parse_to_album_id(album_id)
            for album_id in jm_album_id_iter
        ),
        apply_each_obj_func=lambda aid: download_album(aid, option),
    )


def download_album(jm_album_id, option=None):
    """
    下载一个本子
    @param jm_album_id: 禁漫的本子的id，类型可以是str/int/iterable[str]。
    如果是iterable[str]，则会调用 download_album_batch
    @param option: 下载选项，为空默认是 JmOption.default()
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_album_batch(jm_album_id, option)

    with new_downloader(option) as dler:
        dler.download_album(jm_album_id)


def download_photo(jm_photo_id, option=None):
    """
    下载一个章节
    """
    with new_downloader(option) as dler:
        dler.download_photo(jm_photo_id)


def new_downloader(option=None):
    if option is None:
        option = JmModuleConfig.option_class().default()

    return JmModuleConfig.downloader_class()(option)


def create_option(filepath):
    return JmModuleConfig.option_class().from_file(filepath)
