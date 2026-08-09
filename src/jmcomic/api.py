import asyncio
from time import perf_counter

from .jm_downloader import *
from .jm_task_context import bind_jm_task_context, jm_task_context

__DOWNLOAD_API_RET = DownloadResult


def _download_type(download_api) -> str:
    name = getattr(download_api, '__name__', download_api.__class__.__name__)
    if name.endswith('_async'):
        name = name[:-6]
    if name.startswith('download_'):
        name = name[9:]
    return name


def _finish_download_result(detail, dler, task_started_at):
    manifest = dler.manifest_dict[detail]
    manifest.duration = perf_counter() - task_started_at
    return DownloadResult(detail, dler)


def download_batch(download_api,
                   jm_id_iter: Union[Iterable, Generator],
                   option=None,
                   downloader=None,
                   **kwargs,
                   ) -> BatchResult:
    """
    批量下载 album / photo

    一个album/photo，对应一个线程，对应一个option。
    返回 BatchResult(set)，支持 for album, dler in result 遍历。
    失败项收集在 result.failed 中，不会静默丢失。

    :param download_api: 下载api
    :param jm_id_iter: jmid (album_id, photo_id) 的迭代器
    :param option: 下载选项，所有的jmid共用一个option
    :param downloader: 下载器类
    """
    from common import multi_thread_launcher

    if option is None:
        option = JmModuleConfig.option_class().default()

    result = BatchResult()

    download_type = _download_type(download_api)

    def _safe_download(aid):
        """batch 内部的单任务包装：确保异常被收集而非静默丢失"""
        with jm_task_context(download_type=download_type, jm_id=str(aid)):
            try:
                ret = download_api(aid, option, downloader, **kwargs)
                result.add(ret)
            except Exception as e:
                jm_log('batch.failed', f'批量下载失败: [{aid}], 异常: [{e}]', e)
                result.failed[str(aid)] = e

    multi_thread_launcher(
        iter_objs=set(
            JmcomicText.parse_to_jm_id(jmid)
            for jmid in jm_id_iter
        ),
        apply_each_obj_func=bind_jm_task_context(_safe_download),
        wait_finish=True
    )

    return result


def download_album(jm_album_id,
                   option=None,
                   downloader=None,
                   *,
                   check_exception=True,
                   extra=None,
                   ) -> Union[__DOWNLOAD_API_RET, Set[__DOWNLOAD_API_RET]]:
    """
    下载一个本子（album），包含其所有的章节（photo）

    当jm_album_id不是str或int时，视为批量下载，相当于调用 download_batch(download_album, jm_album_id, option, downloader)

    :param jm_album_id: 本子的禁漫车号
    :param option: 下载选项
    :param downloader: 下载器类
    :param check_exception: 仅当 jm_album_id 是单个 ID 时生效。为 True 时检查 downloader 中的部分下载失败，
                            并上抛 PartialDownloadFailedException。多 ID 调用会转交 download_batch，此参数不生效；
                            请检查 BatchResult.failed，或自行封装 download_batch 实现所需的批量异常策略。
    :param extra: 下载特性（Feature），下载时动态挂载的附加行为上下文。会自动根据上下文（如 album/photo 来源）自适应参数行为。支持单个 Feature、FeatureChain、或列表
    :return: 对于的本子实体类，下载器（如果是上述的批量情况，返回值为download_batch的返回值）
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_batch(download_album, jm_album_id, option, downloader, extra=extra)

    task_started_at = perf_counter()
    with jm_task_context(download_type='album', jm_id=str(jm_album_id), task_started_at=task_started_at):
        with new_downloader(option, downloader) as dler:
            # 下载类型已记录在 TaskContext 中，Feature 会据此选择执行钩子
            dler.add_features(extra)
            album = dler.download_album(jm_album_id)

            if check_exception:
                dler.raise_if_has_exception()

        return _finish_download_result(album, dler, task_started_at)


def download_photo(jm_photo_id,
                   option=None,
                   downloader=None,
                   *,
                   check_exception=True,
                   extra=None,
                   ):
    """
    下载一个章节（photo），参数同 download_album。

    check_exception 仅当 jm_photo_id 是单个 ID 时生效。多 ID 场景请检查
    BatchResult.failed，或自行封装 download_batch 处理批量异常。
    """
    if not isinstance(jm_photo_id, (str, int)):
        return download_batch(download_photo, jm_photo_id, option, downloader, extra=extra)

    task_started_at = perf_counter()
    with jm_task_context(download_type='photo', jm_id=str(jm_photo_id), task_started_at=task_started_at):
        with new_downloader(option, downloader) as dler:
            # 下载类型已记录在 TaskContext 中，Feature 会据此选择执行钩子
            dler.add_features(extra)
            photo = dler.download_photo(jm_photo_id)

            if check_exception:
                dler.raise_if_has_exception()

        return _finish_download_result(photo, dler, task_started_at)


def new_downloader(option=None, downloader=None) -> JmDownloader:
    if option is None:
        option = JmModuleConfig.option_class().default()

    if downloader is None:
        downloader = JmModuleConfig.downloader_class()

    return downloader(option)


def create_option_by_file(filepath):
    return JmModuleConfig.option_class().from_file(filepath)


def create_option_by_env(env_name='JM_OPTION_PATH'):
    from .cli import get_env

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


def new_async_downloader(option=None, downloader=None):
    if option is None:
        option = JmModuleConfig.option_class().default()

    if downloader is None:
        downloader = JmModuleConfig.async_downloader_class()

    return downloader(option)


async def download_album_async(jm_album_id,
                               option=None,
                               downloader=None,
                               *,
                               check_exception=True,
                               extra=None,
                               ):
    """
    异步下载一个本子（album），包含其所有的章节（photo）。

    - 支持批量下载（当 jm_album_id 为可迭代对象时）
    - 返回 (album, downloader) 元组，其中 downloader 的网络和线程池资源已关闭，仅用于读取下载结果
    - check_exception 仅当 jm_album_id 是单个 ID 时生效。多 ID 场景请检查 BatchResult.failed，
      或自行封装 download_batch_async 处理批量异常
    """
    if not isinstance(jm_album_id, (str, int)):
        return await download_batch_async(download_album_async,
                                          jm_album_id,
                                          option,
                                          downloader,
                                          extra=extra
                                          )

    task_started_at = perf_counter()
    with jm_task_context(download_type='album', jm_id=str(jm_album_id), task_started_at=task_started_at):
        async with new_async_downloader(option, downloader) as dler:
            dler.add_features(extra)
            album = await dler.download_album(jm_album_id)

            if check_exception:
                dler.raise_if_has_exception()

        return _finish_download_result(album, dler, task_started_at)


async def download_photo_async(jm_photo_id,
                               option=None,
                               downloader=None,
                               *,
                               check_exception=True,
                               extra=None,
                               ):
    """
    异步下载一个章节（photo）。
    返回的 downloader 已关闭网络和线程池资源，仅用于读取下载结果。
    check_exception 仅当 jm_photo_id 是单个 ID 时生效。多 ID 场景请检查
    BatchResult.failed，或自行封装 download_batch_async 处理批量异常。
    """
    if not isinstance(jm_photo_id, (str, int)):
        return await download_batch_async(download_photo_async,
                                          jm_photo_id,
                                          option,
                                          downloader,
                                          extra=extra
                                          )

    task_started_at = perf_counter()
    with jm_task_context(download_type='photo', jm_id=str(jm_photo_id), task_started_at=task_started_at):
        async with new_async_downloader(option, downloader) as dler:
            dler.add_features(extra)
            photo = await dler.download_photo(jm_photo_id)

            if check_exception:
                dler.raise_if_has_exception()

        return _finish_download_result(photo, dler, task_started_at)


async def download_batch_async(download_api,
                               jm_id_iter,
                               option=None,
                               downloader=None,
                               **kwargs,
                               ) -> BatchResult:
    """
    异步批量下载 album / photo。
    - 容错机制：单个 album/photo 失败不会中止整批，也不会丢失其它已完成结果。
    - 返回 BatchResult(set)，失败项收集在 result.failed 中。
    """
    if option is None:
        option = JmModuleConfig.option_class().default()

    jm_ids = list(dict.fromkeys(JmcomicText.parse_to_jm_id(jmid) for jmid in jm_id_iter))
    download_type = _download_type(download_api)

    async def _download_one(jmid):
        with jm_task_context(download_type=download_type, jm_id=str(jmid)):
            return await download_api(jmid, option, downloader, **kwargs)

    results = await asyncio.gather(
        *(_download_one(jmid) for jmid in jm_ids),
        return_exceptions=True,
    )

    # 失败不抛出，但要记录到 result.failed，便于调用者排查
    result = BatchResult()
    for jmid, r in zip(jm_ids, results):
        if isinstance(r, BaseException):
            with jm_task_context(download_type=download_type, jm_id=str(jmid)):
                jm_log('async.batch.failed', f'批量下载失败: [{jmid}], 异常: [{r}]', r)
            result.failed[str(jmid)] = r
        else:
            result.add(r)

    return result
