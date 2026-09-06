# 复用下载 Runtime 与共享线程池

日常使用 JMComic 下载时，通常不需要手动配置 Runtime。顶层下载 API 会自动管理线程资源，并在任务结束后自动释放。

自 `v2.7.6` 起，如果你需要在批量下载时控制并发数，或者希望复用已有程序中的线程池，可以通过 `JmSyncRuntime` 或 `JmAsyncRuntime` 进行定制。

---

## 1. 同步下载的分层并发机制

同步下载漫画时，内部通常是分层调度的：

```text
本子层 (id_executor)       -> 共享此 Runtime 的本子任务并发上限
  └── 章节层 (photo_executor)  -> 这些本子的章节任务共用一个并发上限
        └── 图片层 (image_executor)  -> 这些章节的图片任务共用一个并发上限
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
    id_workers=2,       # 整个 Runtime 最多同时处理 2 个本子任务
    photo_workers=3,    # 所有本子合计最多同时处理 3 个章节任务
    image_workers=8,    # 所有章节合计最多同时处理 8 个图片任务
)

try:
    # 2. 绑定到任务上下文并执行下载
    with jm_task_context(runtime=runtime):
        download_album(['123456', '789012'])
finally:
    # 3. 释放 Runtime 创建的线程池
    runtime.close()
```

> 上例中的两个本子共用 3 个章节线程，所有章节共用 8 个图片线程。不会因为增加本子或章节数量，就为每个本子、每个章节分别创建一套线程池。

如果某一层没有指定 `*_workers`，下载器会在首次使用该层时按调用点传入的默认并发数建池，后续任务复用该池；章节、图片层的默认值来自 Option。

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
            results = await download_album_async(['123456', '789012'])
            for album_id, error in results.failed.items():
                print(f'本子 {album_id} 下载任务失败: {error}')
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

> 批量 API 会等两个本子的任务都结束，再返回 `BatchResult`。普通任务异常收集在 `results.failed` 中，取消仍会向调用方抛出，因此需要检查失败项。不要直接用默认的 `asyncio.gather` 包住两个单本下载后立即关闭 Runtime：一个任务报错时，另一个任务可能还在使用解码池。

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

## Runtime 与 Control 架构图

```text
下载调用
  |
  +-- jm_task_context：为任务绑定 Runtime 和 Control
  |     |
  |     +-- Runtime：管理下载使用的线程池
  |     `-- Control：保存取消信号和原因
  |
  `-- 下载 API -> Downloader（下载器）
        |
        +-- 同步：JmSyncRuntime
        |     ID 池（批量时）-> 章节池 -> 图片池
        |                                 `-- 请求、解码、保存
        |
        +-- 异步：JmAsyncRuntime
        |     协程 + 信号量 -> 网络请求
        |     解码池       -> 图片解码、保存、同步回调
        |
        `-- 取消检查点 <--- Control.cancel() <--- 用户点击停止
              已取消 -> 当前图片工作收尾，保留已保存文件
                        抛出 DownloadCancelledException

资源关闭
  API 自动创建的 Runtime -> API 在任务结束后关闭
  调用方提供的 Runtime   -> 调用方等待所有任务结束后关闭
  外部传入的线程池       -> 由外部管理，Runtime 不代为关闭
```
