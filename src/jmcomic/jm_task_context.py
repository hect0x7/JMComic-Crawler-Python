import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Event, Lock
from types import MappingProxyType
from typing import Callable, Mapping, Optional

from .jm_runtime import JmRuntime


__all__ = (
    'JM_TASK_CONTEXT',
    'DownloadControl',
    'JTC',
    'get_jm_task_context',
    'jm_task_context',
    'bind_jm_task_context',
)


_EMPTY_TASK_CONTEXT = MappingProxyType({})
JM_TASK_CONTEXT: ContextVar[Mapping] = ContextVar(
    'jm_task_context',
    default=_EMPTY_TASK_CONTEXT,
)


class DownloadControl:
    """
    在线程间共享、线程安全且幂等的下载取消信号。
    """

    def __init__(self):
        self._event = Event()
        self._lock = Lock()
        self._reason = 'download cancelled'

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self, reason: str = 'download cancelled') -> bool:
        normalized_reason = str(reason or 'download cancelled')
        with self._lock:
            if self._event.is_set():
                return False
            self._reason = normalized_reason
            self._event.set()
            return True

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason


class JTC:
    """
    JMComic 任务上下文统一门面 (Jm Task Context)。
    """

    @classmethod
    def get_context(cls) -> dict:
        """
        返回当前 JM 任务上下文的可变快照。
        """
        return dict(JM_TASK_CONTEXT.get())

    @classmethod
    def get_runtime(cls) -> Optional[JmRuntime]:
        """
        返回当前任务绑定的 JmRuntime；没有活动 Runtime 时返回 None。
        """
        return cls.get_context().get('runtime')

    @classmethod
    def get_option(cls):
        """
        返回当前任务绑定的 JmOption；没有活动 Option 时返回 None。
        """
        return cls.get_context().get('option')

    @classmethod
    def get_control(cls) -> Optional[DownloadControl]:
        """
        返回当前任务绑定的取消控制器 DownloadControl；未设置时返回 None。
        """
        control = cls.get_context().get('control')
        if control is None:
            return None
        if not isinstance(control, DownloadControl):
            raise TypeError(
                'jm_task_context control must be DownloadControl, '
                f'got {type(control)}'
            )
        return control


# 兼容已发布的上下文查询入口，内部统一使用 JTC。
get_jm_task_context = JTC.get_context


@contextmanager
def jm_task_context(*, option=None, runtime=None, **fields):
    """
    临时绑定任务字段；只传播 Option/Runtime，不管理资源生命周期。
    """
    context = JTC.get_context()
    parent_runtime = context.get('runtime')

    if runtime is not None and not isinstance(runtime, JmRuntime):
        raise TypeError('runtime must be JmSyncRuntime, JmAsyncRuntime, or None')
    if (
            runtime is not None
            and parent_runtime is not None
            and runtime is not parent_runtime
    ):
        raise RuntimeError('another JmRuntime is already active in this task context')

    context.update(fields)
    if runtime is not None:
        context['runtime'] = runtime
    if option is not None:
        context['option'] = option

    token = JM_TASK_CONTEXT.set(MappingProxyType(context))
    try:
        yield
    finally:
        JM_TASK_CONTEXT.reset(token)


def bind_jm_task_context(func: Callable, context: Optional[Mapping] = None) -> Callable:
    """
    把完整任务上下文快照绑定到同步可调用对象。
    """
    if (
            inspect.iscoroutinefunction(func)
            or inspect.iscoroutinefunction(getattr(func, '__call__', None))
    ):
        raise TypeError('bind_jm_task_context only supports synchronous callables')

    snapshot = MappingProxyType(dict(
        JTC.get_context() if context is None else context
    ))

    @wraps(func)
    def wrapped(*args, **kwargs):
        token = JM_TASK_CONTEXT.set(snapshot)
        try:
            return func(*args, **kwargs)
        finally:
            JM_TASK_CONTEXT.reset(token)

    return wrapped
