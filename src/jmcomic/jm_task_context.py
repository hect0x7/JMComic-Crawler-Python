import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from types import MappingProxyType
from typing import Callable, Mapping, Optional


__all__ = (
    'JM_TASK_CONTEXT',
    'jm_task_context',
    'get_jm_task_context',
    'bind_jm_task_context',
)


_EMPTY_TASK_CONTEXT = MappingProxyType({})
JM_TASK_CONTEXT: ContextVar[Mapping] = ContextVar(
    'jm_task_context',
    default=_EMPTY_TASK_CONTEXT,
)


def get_jm_task_context() -> dict:
    """Return a mutable snapshot of the current JM task context."""
    return dict(JM_TASK_CONTEXT.get())


@contextmanager
def jm_task_context(**fields):
    """Temporarily add fields to the current JM task context."""
    context = get_jm_task_context()
    context.update(fields)
    token = JM_TASK_CONTEXT.set(MappingProxyType(context))
    try:
        yield
    finally:
        JM_TASK_CONTEXT.reset(token)


def bind_jm_task_context(func: Callable, context: Optional[Mapping] = None) -> Callable:
    """Bind a synchronous callable to a snapshot of the current task context."""
    if (inspect.iscoroutinefunction(func)
            or inspect.iscoroutinefunction(getattr(func, '__call__', None))):
        raise TypeError('bind_jm_task_context only supports synchronous callables')

    snapshot = MappingProxyType(dict(
        get_jm_task_context() if context is None else context
    ))

    @wraps(func)
    def wrapped(*args, **kwargs):
        token = JM_TASK_CONTEXT.set(snapshot)
        try:
            return func(*args, **kwargs)
        finally:
            JM_TASK_CONTEXT.reset(token)

    return wrapped
