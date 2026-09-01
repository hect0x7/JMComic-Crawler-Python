# download

::: jmcomic.api
    options:
      members:
      - download_album
      - download_photo
      - create_option
      - create_option_by_env
      - create_option_by_file
      - create_option_by_str
      - download_album_async
      - download_photo_async
      - download_batch_async

::: jmcomic.jm_async_downloader
    options:
      members:
      - JmAsyncDownloader

::: jmcomic.jm_downloader
    options:
      members:
      - BaseDownloader
      - JmDownloader

## 下载 Runtime 与取消控制

::: jmcomic.jm_runtime
    options:
      members:
      - JmRuntime
      - JmSimpleRuntime
      - JmSyncRuntime
      - JmAsyncRuntime

::: jmcomic.jm_exception
    options:
      members:
      - DownloadCancelledException

::: jmcomic.jm_task_context
    options:
      members:
      - DownloadControl
      - jm_task_context
      - bind_jm_task_context
      - get_jm_task_context
      - get_current_control
      - get_jm_runtime
      - get_current_option

同步顶层 API 默认创建 `JmSyncRuntime`，并在调用结束时显式关闭。需要让多个顶层调用复用线程池时，先创建 `JmSyncRuntime`，通过 `jm_task_context(runtime=runtime)` 传播，并在任务完成后显式调用 `runtime.close()`；异步调用改用 `JmAsyncRuntime`。裸同步 Downloader 没有 Runtime 时，会为每次局部调度创建并关闭只有一个线程池的 `JmSimpleRuntime`。完整示例见[复用下载 Runtime](../tutorial/16_shared_executors.md)。

Runtime 只负责 Executor 的配置、调度和生命周期。`JmSimpleRuntime.multi_thread_launcher()` 不要求下载层级；`JmSyncRuntime` 的 launcher 使用 `id/photo/image` 层级。未显式配置容量时，由下载调用点把 Option 或 Downloader 已解析出的默认 worker 数传给 Runtime。

使用 `get_jm_runtime()` 可以读取当前任务激活的 Runtime；没有激活 Runtime 时返回 `None`。

Runtime 和 Option 以公开字段 `runtime`、`option` 直接保存在 `JM_TASK_CONTEXT` 中。`get_jm_task_context()` 返回包含这两个字段的完整副本；`get_jm_runtime()` 和 `get_current_option()` 是读取它们的便捷方法。自定义日志处理器也可以从 LogRecord 的任务上下文中访问这两个公开字段，默认文本日志不会展开对象内容。

`jm_task_context` 只负责字段传播与作用域恢复，不会关闭 Runtime。谁创建 Runtime，谁显式调用 `runtime.close()`；Runtime 只会关闭自身创建的 Executor，不会关闭调用方注入的 Executor。

取消检查统一由 `BaseDownloader.raise_if_cancelled()` 这个 `classmethod` 执行。自定义 Downloader 可以重写它来调整检查策略；Client 和顶层 API 不直接读取取消状态。
