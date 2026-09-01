# 复用下载 Runtime

普通下载不需要手动创建 Runtime。同步顶层 API 使用临时 `JmSyncRuntime` 并在返回前显式关闭；裸同步 Downloader 没有 Runtime 时，每次局部调度使用一个临时 `JmSimpleRuntime`。只有当你希望多个下载调用复用同一组线程池，或想明确控制各层并发数时，才需要 `jm_task_context`：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context


runtime = JmSyncRuntime(
    id_workers=2,
    photo_workers=3,
    image_workers=8,
)
try:
    with jm_task_context(runtime=runtime):
        download_album(['123', '456'])
finally:
    runtime.close()
```

这就是分层同步 Runtime 的完整公开用法。`JmSyncRuntime` 负责 `id`、`photo` 和 `image` 三层调度；任务上下文只传播 Runtime，不管理资源，创建 Runtime 的代码负责显式关闭它。

如果只需要直接调度一层独立任务，也可以使用 `JmSimpleRuntime(workers=...)` 或 `JmSimpleRuntime(executor=...)`。它的 `multi_thread_launcher()` 不接收 `level`。不要把同一个单池 Runtime 用于 album 的 photo/image 两层同步嵌套调度，否则外层 worker 等待内层 worker 时可能耗尽线程。

## Runtime 默认容量从哪里来

Runtime 本身不读取 Option，也不保存下载任务状态。它只管理 Executor 的配置、创建、调度和关闭。

如果你没有给某一层配置 `*_workers`，真正发起调度的调用点会把已经解析好的默认值传给 Runtime：`photo` 和 `image` 使用 Option 中的 `download.threading.photo/image`，批量 ID 使用本次 ID 数量，异步阻塞池使用 Downloader 的 `decode_worker`。这样 Runtime 不需要反向依赖 Context 或 Option。

你也可以直接使用公开的 `multi_thread_launcher()`，但普通下载通常不需要这样做。`wait_finish=True` 会等待所有 Future 完成；worker 异常保存在对应 Future 中，由需要结果的调用方通过 `future.result()` 读取：

```python
from jmcomic import JmSyncRuntime, jm_task_context


runtime = JmSyncRuntime(id_workers=2)
try:
    with jm_task_context(runtime=runtime):
        futures = runtime.multi_thread_launcher(
            [123, 456],
            str,
            level='id',
        )
        print([future.result() for future in futures])
finally:
    runtime.close()
```

## 借用已有线程池

如果应用已经管理自己的 `ThreadPoolExecutor`，可以把它交给 Runtime。Runtime 只借用外部 Executor，不会替你关闭：

```python
from concurrent.futures import ThreadPoolExecutor

from jmcomic import JmSyncRuntime, download_album, jm_task_context


with ThreadPoolExecutor(max_workers=2) as id_executor, \
        ThreadPoolExecutor(max_workers=3) as photo_executor, \
        ThreadPoolExecutor(max_workers=8) as image_executor:
    runtime = JmSyncRuntime(
        id_executor=id_executor,
        photo_executor=photo_executor,
        image_executor=image_executor,
    )
    try:
        with jm_task_context(runtime=runtime):
            download_album(['123', '456'])
    finally:
        runtime.close()
```

三个同步层级会互相等待，因此必须使用不同的 Executor。任务上下文需要在线程间传播，所以不支持 `ProcessPoolExecutor`。

## 异步下载

异步网络请求由 event loop 和 Semaphore 并发；图片解密、PIL、写盘和同步 hook 交给 `blocking` Executor：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

from jmcomic import JmAsyncRuntime, download_album_async, jm_task_context


async def main():
    with ThreadPoolExecutor(max_workers=4) as blocking_executor:
        runtime = JmAsyncRuntime(blocking_executor=blocking_executor)
        try:
            with jm_task_context(runtime=runtime):
                await download_album_async('123')
        finally:
            runtime.close()


asyncio.run(main())
```

共享 `blocking` Executor 不会共享 Downloader、网络 Client、Session 或 Semaphore。每个顶层调用仍有自己的 Downloader 和 Manifest。

## Context 中保存什么

项目只有一个 `JM_TASK_CONTEXT`。Runtime 和 Option 直接使用公开字段 `runtime`、`option` 保存，和 `download_type`、`jm_id` 以及调用方附加字段处于同一个 context mapping 中。`get_jm_task_context()` 返回包含所有字段的完整副本。

可以直接从 context 副本读取 `runtime`、`option`，也可以使用便捷方法 `get_jm_runtime()`、`get_current_option()`。`bind_jm_task_context()` 会把完整上下文快照传播到工作线程。默认文本日志不会展开 Runtime 或 Option，但自定义日志处理器可以读取这两个公开字段。

嵌套上下文中的 `runtime=None` 和 `option=None` 表示继承父上下文。同步下载 API 只接受 `JmSyncRuntime`，异步 API 只接受 `JmAsyncRuntime`；同一任务作用域不能替换成另一个 Runtime。`JmSimpleRuntime` 用于独立的单层调度，不作为分层同步下载的共享 context Runtime。
