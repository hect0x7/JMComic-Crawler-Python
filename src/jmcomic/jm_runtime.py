import concurrent.futures
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from threading import RLock
from typing import Callable, Dict, Optional, Set, Tuple

from common import process_single_arg_to_args_and_kwargs


__all__ = (
    'JmRuntime',
    'JmSimpleRuntime',
    'JmSyncRuntime',
    'JmAsyncRuntime',
)


def validate_jm_workers(name: str, workers: int) -> int:
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError(f'{name} must be a positive integer, got {workers!r}')
    return workers


def validate_jm_executor(name: str, executor: Executor) -> Executor:
    if not isinstance(executor, Executor):
        raise TypeError(f'{name} must be a concurrent.futures.Executor')

    rejected_types = [ProcessPoolExecutor]
    interpreter_pool = getattr(concurrent.futures, 'InterpreterPoolExecutor', None)
    if interpreter_pool is not None:
        rejected_types.append(interpreter_pool)
    if isinstance(executor, tuple(rejected_types)):
        raise TypeError(
            f'{name} must be a same-process thread-based Executor; '
            f'{executor.__class__.__name__} is not supported'
        )
    return executor


def normalize_jm_executor_config(
        name: str,
        workers: Optional[int],
        executor: Optional[Executor],
) -> Tuple[Optional[int], Optional[Executor]]:
    if workers is not None and executor is not None:
        raise ValueError(f'{name}_workers and {name}_executor are mutually exclusive')
    if executor is not None:
        executor = validate_jm_executor(f'{name}_executor', executor)
    if workers is not None:
        workers = validate_jm_workers(f'{name}_workers', workers)
    return workers, executor


class JmRuntime:
    """
    轻量 Runtime：管理 Executor 的配置、创建、调度和关闭。
    """

    _default_level = None

    def __init__(
            self,
            configs: Dict[str, Tuple[Optional[int], Optional[Executor]]],
    ):
        self._workers = {
            level: config[0]
            for level, config in configs.items()
        }
        self._executors = {
            level: config[1]
            for level, config in configs.items()
        }
        self._owned_executors: Set[Executor] = set()
        self._lock = RLock()
        self._closed = False

    def executor(
            self,
            level: Optional[str] = None,
            default_workers: Optional[int] = None,
    ) -> Executor:
        """
        返回指定层级的 Executor；未配置时按调用点给出的默认并发数创建。
        """
        if level is None:
            level = self._default_level
        if level is None:
            raise TypeError('level is required for this Runtime')

        if default_workers is not None:
            default_workers = validate_jm_workers(
                f'{level}_default_workers',
                default_workers,
            )

        with self._lock:
            if self._closed:
                raise RuntimeError('JmRuntime is closed')

            try:
                executor = self._executors[level]
            except KeyError as error:
                raise ValueError(f'unknown runtime level: {level!r}') from error

            if executor is not None:
                return executor

            workers = self._workers[level]
            if workers is None:
                workers = default_workers
                self._workers[level] = workers

            if workers is None:
                executor = ThreadPoolExecutor(thread_name_prefix=f'jm-{level}')
            else:
                executor = ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix=f'jm-{level}',
                )

            self._executors[level] = executor
            self._owned_executors.add(executor)
            return executor

    def multi_thread_launcher(
            self,
            iter_objs,
            apply_each_obj_func: Callable,
            wait_finish=True,
            *,
            level: Optional[str] = None,
            default_workers: Optional[int] = None,
    ):
        """
        使用指定层级的 Executor 批量提交任务，并按需等待完成。
        """
        executor = self.executor(level, default_workers)
        futures = []

        try:
            for obj in iter_objs:
                args, kwargs = process_single_arg_to_args_and_kwargs(obj)
                futures.append(executor.submit(apply_each_obj_func, *args, **kwargs))
        except BaseException:
            if wait_finish:
                concurrent.futures.wait(futures)
            raise

        if wait_finish:
            concurrent.futures.wait(futures)

        return futures

    def close(self) -> None:
        """
        关闭 Runtime 自建的 Executor；调用方传入的 Executor 保持可用。
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            owned_executors = tuple(self._owned_executors)
            self._owned_executors.clear()

        for executor in owned_executors:
            executor.shutdown(wait=True)


class JmSimpleRuntime(JmRuntime):
    """
    单 Executor Runtime：用于一次同步下载中的局部并发。
    """

    _default_level = 'default'

    def __init__(
            self,
            *,
            workers: Optional[int] = None,
            executor: Optional[Executor] = None,
    ):
        if workers is not None and executor is not None:
            raise ValueError('workers and executor are mutually exclusive')
        if workers is not None:
            workers = validate_jm_workers('workers', workers)
        if executor is not None:
            executor = validate_jm_executor('executor', executor)

        super().__init__(
            configs={
                'default': (workers, executor),
            },
        )


class JmSyncRuntime(JmRuntime):
    """
    同步下载 Runtime：分别管理 id、photo、image 三层 Executor。
    """

    def __init__(
            self,
            *,
            id_workers: Optional[int] = None,
            id_executor: Optional[Executor] = None,
            photo_workers: Optional[int] = None,
            photo_executor: Optional[Executor] = None,
            image_workers: Optional[int] = None,
            image_executor: Optional[Executor] = None,
    ):
        external_executors = [
            executor
            for executor in (id_executor, photo_executor, image_executor)
            if executor is not None
        ]
        if len({id(executor) for executor in external_executors}) != len(external_executors):
            raise ValueError(
                'id/photo/image levels must use different executor objects'
            )

        super().__init__(
            configs={
                'id': normalize_jm_executor_config('id', id_workers, id_executor),
                'photo': normalize_jm_executor_config(
                    'photo', photo_workers, photo_executor
                ),
                'image': normalize_jm_executor_config(
                    'image', image_workers, image_executor
                ),
            },
        )


class JmAsyncRuntime(JmRuntime):
    """
    异步下载 Runtime：管理图片解密、处理和同步 hook 的 decode Executor。
    """

    def __init__(
            self,
            *,
            decode_workers: Optional[int] = None,
            decode_executor: Optional[Executor] = None,
    ):
        super().__init__(
            configs={
                'decode': normalize_jm_executor_config(
                    'decode', decode_workers, decode_executor
                ),
            },
        )
