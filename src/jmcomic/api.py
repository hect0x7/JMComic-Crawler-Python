import asyncio
from time import perf_counter

from .jm_downloader import *
from .jm_exception import DownloadCancelledException, ExceptionTool
from .jm_runtime import (
    JmAsyncRuntime,
    JmRuntime,
    JmSyncRuntime,
    JmTempRuntime,
)
from .jm_task_context import (
    bind_jm_task_context,
    JTC,
    jm_task_context,
)

__DOWNLOAD_API_RET = DownloadResult


def _finish_download_result(detail, dler, task_started_at):
    manifest = dler.manifest_dict[detail]
    manifest.duration = perf_counter() - task_started_at
    return DownloadResult(detail, dler)


def _ensure_option(option):
    return JmModuleConfig.option_class().default() if option is None else option


def _raise_if_cancelled_chain(cause_exc: BaseException):
    """在当前任务已被取消时，将底层异常转换为 DownloadCancelledException 并保留原始异常链。"""
    control = JTC.get_control()
    if control is not None and control.is_cancelled:
        reason = control.reason
        raise DownloadCancelledException(
            reason,
            {
                ExceptionTool.CONTEXT_KEY_CONTROL: control,
                ExceptionTool.CONTEXT_KEY_REASON: reason,
            },
        ) from cause_exc
    raise cause_exc


def _execute_sync_download(
        action,
        download_type: str,
        jm_id,
        option,
        downloader,
        extra,
        check_exception: bool,
        control=None,
):
    option = _ensure_option(option)
    task_started_at = perf_counter()

    with jm_task_context(
            option=option,
            download_type=download_type,
            jm_id=str(jm_id),
            task_started_at=task_started_at,
            control=control,
    ):
        with new_downloader(option, downloader) as dler:
            dler.add_features(extra)
            try:
                detail = action(dler)
                if check_exception:
                    dler.raise_if_has_exception()
            except DownloadCancelledException:
                raise
            except Exception as e:
                _raise_if_cancelled_chain(e)

    return _finish_download_result(detail, dler, task_started_at)


async def _execute_async_download(
        action,
        download_type: str,
        jm_id,
        option,
        downloader,
        extra,
        check_exception: bool,
        control=None,
):
    option = _ensure_option(option)
    task_started_at = perf_counter()

    async with jm_task_context(
            option=option,
            download_type=download_type,
            jm_id=str(jm_id),
            task_started_at=task_started_at,
            control=control,
    ), new_async_downloader(option, downloader) as dler:
        dler.add_features(extra)
        try:
            detail = await action(dler)
            if check_exception:
                dler.raise_if_has_exception()
        except DownloadCancelledException:
            raise
        except Exception as e:
            _raise_if_cancelled_chain(e)

    return _finish_download_result(detail, dler, task_started_at)


def download_batch(
        download_api,
        jm_id_iter: Union[Iterable, Generator],
        option=None,
        downloader=None,
        download_type='batch',
        control=None,
        **kwargs,
) -> BatchResult:
    """
    批量下载 album / photo

    一个album/photo，对应一个线程，对应一个option。
    返回 BatchResult，保持 FIFO 顺序，支持 for album, dler in result 遍历与按车号检索。
    失败项收集在 result.failed 中，不会静默丢失。

    :param download_api: 下载api
    :param jm_id_iter: jmid (album_id, photo_id) 的迭代器
    :param option: 下载选项，所有的jmid共用一个option
    :param downloader: 下载器类
    :param download_type: 下载类型 ('album', 'photo' 等)，默认 'batch'
    :param control: 可选的取消控制器 (DownloadControl)，用于外部协作式中断下载任务
    """
    option = _ensure_option(option)
    # 1. 保序去重 ID 列表
    jm_ids = list(dict.fromkeys(
        JmcomicText.parse_to_jm_id(jmid)
        for jmid in jm_id_iter
    ))
    result = BatchResult()
    if len(jm_ids) == 0:
        return result

    with jm_task_context(option=option, control=control):
        # 2. 单项下载执行闭包：在专属任务上下文中执行，并将异常封装为三元组返回，避免打断批处理调度
        def _download_one(aid):
            with jm_task_context(download_type=download_type, jm_id=str(aid)):
                try:
                    item = download_api(aid, option, downloader, **kwargs)
                    return aid, item, None
                except Exception as error:
                    return aid, None, error

        runtime = JTC.get_runtime()
        if runtime is not None and not isinstance(runtime, JmSyncRuntime):
            raise TypeError('sync batch API requires JmSyncRuntime')

        cancellation_error = None
        worker = bind_jm_task_context(_download_one)

        # 3. 调度本子层并发：外部 JmSyncRuntime 显式配置了 album 层则复用；未配置则使用独立 JmTempRuntime，避免将首批数量固化为常驻池容量
        if runtime is not None and runtime.has_executor(JmRuntime.LEVEL_ALBUM):
            futures = runtime.multi_thread_launcher(
                iter_objs=jm_ids,
                apply_each_obj_func=worker,
                wait_finish=True,
                level=JmRuntime.LEVEL_ALBUM,
            )
        else:
            with JmTempRuntime(workers=len(jm_ids)) as launcher:
                futures = launcher.multi_thread_launcher(
                    iter_objs=jm_ids,
                    apply_each_obj_func=worker,
                    wait_finish=True,
                )

        # 4. 收集 Future 执行结果：记录成功成果与失败异常
        completed_results = []
        succeeded_ids = set()

        for future in futures:
            aid, item, error = future.result()
            if error is None:
                result.add(item)
                if item is not None:
                    completed_results.append(item)
                    succeeded_ids.add(str(aid))
                continue

            # 取消属于主动中断，不当成下载失败记录进 failed 字典
            if isinstance(error, DownloadCancelledException):
                if cancellation_error is None:
                    cancellation_error = error
                continue

            # 记录失败日志并存入 failed
            with jm_task_context(download_type=download_type, jm_id=str(aid)):
                jm_log(
                    'batch.failed',
                    f'批量下载失败: [{aid}], 异常: [{error}]',
                    error,
                )
            result.failed[str(aid)] = error

        # 5. 收尾判断：若发生取消，补全已完成成果与未完成 ID 后再抛出
        if cancellation_error is not None:
            cancellation_error.context[ExceptionTool.CONTEXT_KEY_COMPLETED_RESULTS] = completed_results
            cancellation_error.context[ExceptionTool.CONTEXT_KEY_UNFINISHED_IDS] = [
                str(aid) for aid in jm_ids if str(aid) not in succeeded_ids
            ]
            raise cancellation_error
        return result


def download_album(jm_album_id,
                   option=None,
                   downloader=None,
                   *,
                   check_exception=True,
                   extra=None,
                   control=None,
                   ) -> Union[__DOWNLOAD_API_RET, Set[__DOWNLOAD_API_RET]]:
    """
    下载一个本子（album），包含其所有的章节（photo）

    当jm_album_id不是str或int时，视为批量下载，相当于调用 download_batch(download_album, jm_album_id, option, downloader, control=control)

    :param jm_album_id: 本子的禁漫车号
    :param option: 下载选项
    :param downloader: 下载器类
    :param check_exception: 仅当 jm_album_id 是单个 ID 时生效。为 True 时检查 downloader 中的部分下载失败，
                            并上抛 PartialDownloadFailedException。多 ID 调用会转交 download_batch，此参数不生效；
                            请检查 BatchResult.failed，或自行封装 download_batch 实现所需的批量异常策略。
    :param extra: 下载特性（Feature），下载时动态挂载的附加行为上下文。会自动根据上下文（如 album/photo 来源）自适应参数行为。支持单个 Feature、FeatureChain、或列表
    :param control: 可选的取消控制器 (DownloadControl)，用于外部协作式中断下载任务
    :return: 对于的本子实体类，下载器（如果是上述的批量情况，返回值为download_batch的返回值）
    """

    if not isinstance(jm_album_id, (str, int)):
        return download_batch(
            download_album,
            jm_album_id,
            option,
            downloader,
            download_type='album',
            extra=extra,
            control=control,
        )

    return _execute_sync_download(
        lambda dler: dler.download_album(jm_album_id),
        'album',
        jm_album_id,
        option,
        downloader,
        extra,
        check_exception,
        control=control,
    )


def download_photo(jm_photo_id,
                   option=None,
                   downloader=None,
                   *,
                   check_exception=True,
                   extra=None,
                   control=None,
                   ):
    """
    下载一个章节（photo），参数同 download_album。

    check_exception 仅当 jm_photo_id 是单个 ID 时生效。多 ID 场景请检查
    BatchResult.failed，或自行封装 download_batch 处理批量异常。
    """
    if not isinstance(jm_photo_id, (str, int)):
        return download_batch(
            download_photo,
            jm_photo_id,
            option,
            downloader,
            download_type='photo',
            extra=extra,
            control=control,
        )

    return _execute_sync_download(
        lambda dler: dler.download_photo(jm_photo_id),
        'photo',
        jm_photo_id,
        option,
        downloader,
        extra,
        check_exception,
        control=control,
    )


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
                               control=None,
                               ):
    """异步下载一个本子及其全部章节。

    当 ``jm_album_id`` 是可迭代对象时使用批量 API。单个 ID 返回
    ``DownloadResult``；其中 Downloader 的网络 client 已关闭，阻塞工作也已
    收敛。通过 ``jm_task_context(runtime=JmAsyncRuntime(...))`` 提供的 decode
    执行器由调用方负责关闭。

    ``check_exception`` 只对单个 ID 生效。批量场景应检查
    ``BatchResult.failed``，或按需封装 ``download_batch_async``。
    """
    if not isinstance(jm_album_id, (str, int)):
        return await download_batch_async(download_album_async,
                                          jm_album_id,
                                          option,
                                          downloader,
                                          download_type='album',
                                          extra=extra,
                                          control=control,
                                          )

    return await _execute_async_download(
        lambda dler: dler.download_album(jm_album_id),
        'album',
        jm_album_id,
        option,
        downloader,
        extra,
        check_exception,
        control=control,
    )


async def download_photo_async(jm_photo_id,
                               option=None,
                               downloader=None,
                               *,
                               check_exception=True,
                               extra=None,
                               control=None,
                               ):
    """异步下载一个章节。

    返回的 Downloader 已关闭网络 client，阻塞工作也已收敛。通过
    ``jm_task_context(runtime=JmAsyncRuntime(...))`` 提供的 decode 执行器由调用方负责关闭。

    ``check_exception`` 只对单个 ID 生效。批量场景应检查
    ``BatchResult.failed``，或按需封装 ``download_batch_async``。
    """
    if not isinstance(jm_photo_id, (str, int)):
        return await download_batch_async(download_photo_async,
                                          jm_photo_id,
                                          option,
                                          downloader,
                                          download_type='photo',
                                          extra=extra,
                                          control=control,
                                          )

    return await _execute_async_download(
        lambda dler: dler.download_photo(jm_photo_id),
        'photo',
        jm_photo_id,
        option,
        downloader,
        extra,
        check_exception,
        control=control,
    )


async def download_batch_async(
        download_api,
        jm_id_iter,
        option=None,
        downloader=None,
        download_type='batch',
        control=None,
        **kwargs,
) -> BatchResult:
    """
    异步批量下载 album / photo。
    - 容错机制：单个 album/photo 失败不会中止整批，也不会丢失其它已完成结果。
    - 返回 BatchResult，保持 FIFO 顺序，支持按车号检索，失败项收集在 result.failed 中。
    :param control: 可选的取消控制器 (DownloadControl)，用于外部协作式中断下载任务
    """
    option = _ensure_option(option)
    jm_ids = list(dict.fromkeys(JmcomicText.parse_to_jm_id(jmid) for jmid in jm_id_iter))
    result = BatchResult()
    if len(jm_ids) == 0:
        return result

    async def _download_one(jmid):
        with jm_task_context(download_type=download_type, jm_id=str(jmid)):
            return await download_api(jmid, option, downloader, **kwargs)

    runtime = JTC.get_runtime()
    if runtime is not None and not isinstance(runtime, JmAsyncRuntime):
        raise TypeError('async batch API requires JmAsyncRuntime')

    with jm_task_context(option=option, control=control):
        tasks = [asyncio.create_task(_download_one(jmid)) for jmid in jm_ids]
        # 等待所有异步任务执行完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查是否有任务被取消
        cancellation_error = None
        for item in results:
            if isinstance(item, DownloadCancelledException):
                cancellation_error = item
                break

        # 若发生取消，收集已完成成果与未完成 ID 后抛出，不当成下载失败记录进 failed
        if cancellation_error is not None:
            succeeded_ids = {
                str(jmid)
                for jmid, item in zip(jm_ids, results)
                if not isinstance(item, BaseException) and item is not None
            }
            cancellation_error.context[ExceptionTool.CONTEXT_KEY_COMPLETED_RESULTS] = [
                item for item in results
                if not isinstance(item, BaseException) and item is not None
            ]
            cancellation_error.context[ExceptionTool.CONTEXT_KEY_UNFINISHED_IDS] = [
                str(jmid) for jmid in jm_ids
                if str(jmid) not in succeeded_ids
            ]
            raise cancellation_error

        # 外部协程取消信号
        for item in results:
            if isinstance(item, asyncio.CancelledError):
                raise item

        # 记录失败项并收集成功结果
        for jmid, item in zip(jm_ids, results):
            if isinstance(item, BaseException):
                with jm_task_context(download_type=download_type, jm_id=str(jmid)):
                    jm_log(
                        'async.batch.failed',
                        f'批量下载失败: [{jmid}], 异常: [{item}]',
                        item,
                    )
                result.failed[str(jmid)] = item
            else:
                result.add(item)

        return result
