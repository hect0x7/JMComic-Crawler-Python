# 复用下载 Runtime 与共享线程池

日常使用 JMComic 下载时，通常不需要手动配置 Runtime。顶层下载 API 会自动管理线程资源，并在任务结束后自动释放。

自 `v2.7.6` 起，如果你需要在批量下载时控制并发数，或者希望复用已有程序中的线程池，可以通过 `JmSyncRuntime` 或 `JmAsyncRuntime` 进行定制。

---

## 1. 同步下载的分层并发机制

同步下载漫画时，内部通常是分层调度的：

```text
本子层 (id_executor)       -> 同时下载几个本子 (Album)
  └── 章节层 (photo_executor)  -> 每个本子同时下载几个章节 (Photo)
        └── 图片层 (image_executor)  -> 每个章节同时下载几张图片 (Image)
```

因为外层任务（下载本子）需要等待内层任务（下载章节和图片）完成，所以这三层需要分别使用不同的线程池。如果三层混用同一个线程池，当外层任务占满线程时，内层任务可能无法获得线程执行，导致任务互相等待。

`JmSyncRuntime` 负责集中配置和管理这三层的线程池。

---

## 2. 同步下载：使用 JmSyncRuntime

### 场景 A：自定义各层并发数

通过 `JmSyncRuntime`，可以分别设置每一层的并发线程数，并通过 `jm_task_context` 传给下载方法：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 1. 创建 Runtime，指定本子、章节和图片的并发数
runtime = JmSyncRuntime(
    id_workers=2,       # 同时下载 2 个本子
    photo_workers=3,    # 每个本子同时下载 3 个章节
    image_workers=8,    # 每个章节同时下载 8 张图片
)

try:
    # 2. 绑定到任务上下文并执行下载
    with jm_task_context(runtime=runtime):
        download_album(['123456', '789012'])
finally:
    # 3. 释放 Runtime 创建的线程池
    runtime.close()
```

如果某一层没有指定 `*_workers`，下载器会按 Option 里的默认配置建池。

### 场景 B：复用已有线程池

如果你的程序本身已经维护了 `ThreadPoolExecutor`，可以直接传给 `JmSyncRuntime` 复用：

```python
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmSyncRuntime, download_album, jm_task_context

with ThreadPoolExecutor(max_workers=2) as id_pool, \
     ThreadPoolExecutor(max_workers=3) as photo_pool, \
     ThreadPoolExecutor(max_workers=8) as image_pool:

    runtime = JmSyncRuntime(
        id_executor=id_pool,
        photo_executor=photo_pool,
        image_executor=image_pool,
    )
    try:
        with jm_task_context(runtime=runtime):
            download_album(['123456', '789012'])
    finally:
        runtime.close()
```

关于外部线程池的关闭：
- **不影响外部线程池**：JMComic 遵循“谁创建、谁关闭”的原则，外部传入的线程池仍由外部上下文管理，`runtime.close()` 不会调用外部池的 `shutdown()`；
- **状态注销与防泄漏**：`runtime.close()` 会将 Runtime 标记为已结束；如果部分层级使用了外部池、另一部分是内部自建的，它会自动关闭自建的那部分线程池，避免资源泄漏。

---

## 3. 异步下载：使用 JmAsyncRuntime

异步下载与同步下载的并发分工不同：
- **网络请求**：完全由 Python 的 `asyncio` 事件循环和协程处理，无需占用线程池；
- **图片解密与处理**：禁漫的图片下载后需要进行分块拼接、反混淆解密和写盘，这部分属于 CPU 计算与文件写入，交给后台线程池处理。

`JmAsyncRuntime` 负责管理这层解码线程池：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmAsyncRuntime, download_album_async, jm_task_context

async def main():
    # 方式 1：指定解码线程数（任务完成后 close 释放）
    runtime = JmAsyncRuntime(decode_workers=4)
    try:
        with jm_task_context(runtime=runtime):
            await asyncio.gather(
                download_album_async('123456'),
                download_album_async('789012'),
            )
    finally:
        runtime.close()

    # 方式 2：直接复用外部已有线程池
    with ThreadPoolExecutor(max_workers=4) as my_decode_pool:
        runtime = JmAsyncRuntime(decode_executor=my_decode_pool)
        try:
            with jm_task_context(runtime=runtime):
                await download_album_async('123456')
        finally:
            runtime.close()

asyncio.run(main())
```

---

## 4. 任务上下文统一门面：JTC

在下载过程中，自定义插件（Plugin）、Feature、回调函数或主逻辑常常需要查询当前任务状态。

JMComic 提供了门面类 **`JTC` (Jm Task Context)**，方便统一读取上下文信息：

```python
from jmcomic import JTC, jm_task_context, JmSyncRuntime, JmOption, DownloadControl

runtime = JmSyncRuntime(id_workers=2)
option = JmOption.default()
control = DownloadControl()

with jm_task_context(runtime=runtime, option=option, control=control, custom_tag='v1'):
    # 1. 获取当前生效的 Runtime
    cur_runtime = JTC.get_runtime()

    # 2. 获取当前生效的 Option 配置
    cur_option = JTC.get_option()

    # 3. 获取当前的取消控制器
    cur_control = JTC.get_control()

    # 4. 获取完整任务上下文快照
    ctx_dict = JTC.get_context()
    print('自定义字段:', ctx_dict.get('custom_tag'))
```

在未进入 `jm_task_context` 的代码区域调用 `JTC.get_runtime()` 等方法，会安全返回 `None`。

---

## 5. 核心规则与速查

| 概念 | 核心职责 | 推荐使用方式 |
| :--- | :--- | :--- |
| **`JmSyncRuntime`** | 统一管理同步的 `id`、`photo`、`image` 三层线程池 | 批量下载多本漫画且需控制并发时使用，通过 `try...finally: runtime.close()` 回收 |
| **`JmAsyncRuntime`** | 统一管理异步中的 CPU 解密与文件写入池 (`decode`) | 多个异步任务并发、需要控制解密并发时使用 |
| **`JTC`** | 任务上下文统一访问门面 | 随时读取 `JTC.get_runtime()` / `get_option()` / `get_control()` / `get_context()` |
| **外部 Executor** | 复用已有线程池 | 传入 `*_executor` 参数；Runtime 不会代关，由调用方自行管理生命周期 |
