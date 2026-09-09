# 复用下载 Runtime 与共享线程池

> 日常使用 JMComic 下载时，通常不需要手动配置线程池，顶层下载 API 会自动管理并在任务结束后安全释放。
> 
> 但在以下两种场景下，你可以使用 `Runtime` 来精细控制：
> 
> 1. **批量下载时防卡死**：一次性下载几十上百个本子，希望严格限制并发（例如“最多同时下 2 个本子，所有图片最多 8 个线程”），避免把带宽或电脑卡爆。
> 2. **复用已有的线程池**：你的程序（如 Web 服务、后台调度器）本身已经维护了全局线程池，希望 JMComic 直接复用，避免重复创建和销毁线程。

---

## 什么是 Runtime？

平时我们直接调用 `download_album('123456')` 时，完全不需要传任何 Runtime 参数。

这是因为 JMComic 已经在后台自动创建了一个默认的 Runtime（下载运行时），负责拉起线程池，并在下载结束后自动释放。

**Runtime 的定位很简单：它就是专门负责管理下载过程中“线程池与并发调度”的管家。**

当你需要**自定义线程数**，或者希望**复用已有线程池**时，就需要显式创建一个 Runtime，并通过 `jm_task_context` 传递给下载任务：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 1. 创建你定制的 Runtime
runtime = JmSyncRuntime(...)

# 2. 通过 jm_task_context 注入给下载任务
with jm_task_context(runtime=runtime):
    download_album(...)
```

接下来分别介绍同步与异步的具体用法。

---

## 1. 同步下载：使用 JmSyncRuntime

同步下载时，任务分为三个层级：本子、章节、图片。`JmSyncRuntime` 允许你分别控制这三层的并发线程数。

### 场景 A：自定义各层并发数

通过 `JmSyncRuntime` 指定每一层的最大线程数，并通过 `jm_task_context` 传入下载任务：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 1. 创建 Runtime，指定各层并发上限
runtime = JmSyncRuntime(
    id_workers=2,       # 最多同时下载 2 个本子
    photo_workers=3,    # 所有本子合计最多同时处理 3 个章节
    image_workers=8,    # 所有章节合计最多同时下载 8 张图片
)

try:
    # 2. 绑定到任务上下文并执行下载
    with jm_task_context(runtime=runtime):
        download_album(['123456', '789012', '345678'])
finally:
    # 3. 任务完成后释放线程池
    runtime.close()
```

> [!TIP]
> 如果某一层不传参数（例如不传 `photo_workers`），该层会使用系统默认值。

### 场景 B：复用外部已有的线程池

如果你的程序已经有现成的 `ThreadPoolExecutor`，可以直接传给 Runtime 复用：

```python
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 假设项目中已有维护好的线程池
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
        # 释放 Runtime。遵循“谁创建谁关闭”原则，外部传入的线程池不会被关闭
        runtime.close()
```

---

## 2. 异步下载：使用 JmAsyncRuntime

异步下载与同步不同：网络请求完全由 `asyncio` 协程高效处理，不占线程；**只有图片的解密、反混淆拼接与写盘（CPU 计算与文件 I/O）需要用到后台线程池**。

因此，`JmAsyncRuntime` 只需要管理一个 `decode`（图片解码）线程池，配置更加简单。

### 场景 A：指定解码并发线程数

```python
import asyncio
from jmcomic import JmAsyncRuntime, download_album_async, jm_task_context


async def main():
    # 限制最多同时使用 4 个线程进行图片解密与保存
    runtime = JmAsyncRuntime(decode_workers=4)
    try:
        with jm_task_context(runtime=runtime):
            await download_album_async(['123456', '789012'])
    finally:
        runtime.close()


asyncio.run(main())
```

### 场景 B：复用外部已有的解码线程池

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmAsyncRuntime, download_album_async, jm_task_context


async def main():
    # 借用现成的外部线程池
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

## 3. 常见问题与速查

| 需求 | 推荐做法 | 说明 |
| :--- | :--- | :--- |
| **同步批量控制并发** | `JmSyncRuntime(id_workers=..., image_workers=...)` | 避免一次性下几十个本子把资源占满 |
| **异步控制解密并发** | `JmAsyncRuntime(decode_workers=...)` | 仅限制图片解密写盘线程数，网络请求仍走协程 |
| **复用已有线程池** | 传入 `*_executor=你的线程池` | 遵循“谁创建谁关闭”，`runtime.close()` 不会关闭外部线程池 |
| **自省当前 Runtime** | `JTC.get_runtime()` | 在插件或上下文内部随时自省当前生效的 Runtime 对象 |
