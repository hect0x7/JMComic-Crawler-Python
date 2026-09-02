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
      - JTC
      - jm_task_context
      - bind_jm_task_context
      - get_jm_task_context
      - get_current_control
      - get_jm_runtime
      - get_current_option
