import inspect
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
    'JmTaskContext',
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
        self._reason: Optional[str] = None

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
    def reason(self) -> Optional[str]:
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
    def get_context_value(cls, key: str, default=None):
        """
        获取当前 JM 任务上下文指定 key 的值，避免全量 dict 拷贝。
        """
        return JM_TASK_CONTEXT.get().get(key, default)

    @classmethod
    def get_runtime(cls) -> Optional[JmRuntime]:
        """
        返回当前任务绑定的 JmRuntime；没有活动 Runtime 时返回 None。
        """
        return cls.get_context_value('runtime')

    @classmethod
    def get_option(cls):
        """
        返回当前任务绑定的 JmOption；没有活动 Option 时返回 None。
        """
        return cls.get_context_value('option')

    @classmethod
    def get_control(cls) -> Optional[DownloadControl]:
        """
        返回当前任务绑定的取消控制器 DownloadControl；未设置时返回 None。
        """
        control = cls.get_context_value('control')
        if control is None:
            return None
        if not isinstance(control, DownloadControl):
            raise TypeError(
                'jm_task_context control must be DownloadControl, '
                f'got {type(control)}'
            )
        return control

    @classmethod
    def is_cancelled(cls) -> bool:
        """
        当前任务是否已被标记取消。
        """
        control = cls.get_control()
        return control is not None and control.is_cancelled

    @classmethod
    def raise_if_cancelled(cls) -> None:
        """
        若当前任务已被标记取消，直接抛出 DownloadCancelledException。
        """
        control = cls.get_control()
        if control is None or not control.is_cancelled:
            return
        from .jm_exception import DownloadCancelledException, ExceptionTool
        raise DownloadCancelledException(
            control.reason,
            {
                ExceptionTool.CONTEXT_KEY_CONTROL: control,
                ExceptionTool.CONTEXT_KEY_REASON: control.reason,
            },
        )


# 兼容已发布的上下文查询入口，内部统一使用 JTC。
get_jm_task_context = JTC.get_context

class JmTaskContext:
    """
    临时绑定任务字段；只传播 Option/Runtime/Control，不管理资源生命周期。

    同时支持同步 with 与异步 async with 上下文管理协议。
    """

    def __init__(self, *, option=None, runtime=None, control=None, **fields):
        self.option = option
        self.runtime = runtime
        self.control = control
        self.fields = fields
        self.token = None

    def __enter__(self):
        context = JTC.get_context()

        if self.runtime is not None and not isinstance(self.runtime, JmRuntime):
            raise TypeError(f'runtime must be JmRuntime or None, got {type(self.runtime)}')

        if self.control is not None and not isinstance(self.control, DownloadControl):
            raise TypeError(f'control must be DownloadControl, got {type(self.control)}')

        context.update(self.fields)
        if self.runtime is not None:
            context['runtime'] = self.runtime
        if self.option is not None:
            context['option'] = self.option
        if self.control is not None:
            context['control'] = self.control

        self.token = JM_TASK_CONTEXT.set(MappingProxyType(context))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            JM_TASK_CONTEXT.reset(self.token)
            self.token = None

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# 保持向下兼容的小写别名
jm_task_context = JmTaskContext


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
