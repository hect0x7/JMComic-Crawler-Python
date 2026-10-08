# 复用下载 Runtime 与共享线程池

> 日常使用 JMComic 下载时，通常不需要手动配置线程池，顶层下载 API 会自动管理并在任务结束后安全释放。
> 
> 但在以下两种场景下，你可以使用 `Runtime` 来精细控制：
> 
> 1. **批量下载时防卡死**：一次性下载几十上百个本子，希望严格限制并发（例如“最多同时下 2 个本子，所有图片最多 8 个线程”），避免把带宽或电脑卡爆。
> 2. **复用已有的线程池**：你的程序（如 Web 服务、后台调度器）本身已经维护了全局线程池，希望 JMComic 直接复用，避免重复创建和销毁线程。

---

### 算一笔账 ——— 不用 Runtime 可能会“线程爆炸”？

很多用户会好奇：我不配 Runtime，直接传一个列表 `download_album(['1', '2', '3', ...])` 批量下载，程序在底层究竟起了多少线程？

在不使用共享 Runtime 时，JMComic 的三层下载是**各自独立开启局部线程池**的。我们先看系统的真实默认并发口径：
* **本子层 (id)**：默认并发上限为待下载的本子总数 `len(jm_ids)`（全量并发启动）；
* **章节层 (photo)**：默认配置 `threading.photo` 取当前系统的 CPU 核心数 `os.cpu_count()`（常见电脑通常为 8 核）；
* **图片层 (image)**：默认配置 `threading.image` 固定为 **30** 个线程。

各层级联调度的真实结构如下：

```
【本子层 (id)】: 传入 10 个本子 ──► 并发开启 10 个本子线程 (默认 default_workers = 本子总数 10)
  └── 【章节层 (photo)】: 每个本子 ──► 独立开启 Photo 线程池 (默认 os.cpu_count()，如 8 核机器为 8)
        └── 【图片层 (image)】: 每个章节 ──► 独立开启 Image 线程池 (默认配置固定为 30)
```

假设你一次性批量下载 **10 个本子**：
1. **本子层**：10 个本子同时启动调度；
2. **章节层**：每个本子内部各自拉起最多 8 个章节同时处理（合计 $10 \times 8 = 80$ 个并发章节）；
3. **图片层**：每个章节下载图片时，又各自拉起一个最大 30 线程的局部线程池；
4. **总工作线程瞬间爆发**：$10 \text{ (本子)} \times 8 \text{ (章节)} \times 30 \text{ (图片)} = \mathbf{2400}$ **个并发线程！**

这种**乘法级（连乘）级联膨胀**，会导致系统瞬时创建上千个系统线程，引起大量 CPU 上下文切换、内存占用飙升、网络连接数耗尽，甚至直接触发目标服务端的反爬限频或把自己的本地网络打瘫痪。

---

#### 用了 Runtime 之后：从“乘法爆炸”变成“加法控流”

当你使用 `JmSyncRuntime` 统一调度时，线程模型从“各自开池”变成了“**全局水管截流**”：

```
【本子层 (id)】: 全局复用 id 线程池 ──► 严格限制最多 2 个本子在并行 (id_workers=2)
  └── 【章节层 (photo)】: 所有本子共享 photo 线程池 ──► 合计最多同时处理 3 个章节 (photo_workers=3)
        └── 【图片层 (image)】: 所有章节共享 image 线程池 ──► 全局最多同时下载 8 张图片 (image_workers=8)
```

**再算一笔账**：
* 同样面对一次性丢进去的 10 个甚至 100 个本子；
* 配置 `JmSyncRuntime(id_workers=2, photo_workers=3, image_workers=8)`；
* **本子层**：`id_workers=2`，哪怕传了 100 个本子，同时在跑的严格只有 2 个，其余本子在队列排队；
* **章节层**：`photo_workers=3`，正在下载的本子**跨任务共享同一个章节线程池**，合计最多同时处理 3 个章节；
* **图片层**：`image_workers=8`，所有章节里的所有图片**全局共享这 8 个图片下载线程**，绝不超额；
* 系统的总工作线程数恒定为：$2 (\text{本子}) + 3 (\text{章节}) + 8 (\text{图片}) = \mathbf{13}$ **个线程**！

从 **2400 骤降到 13**，不仅彻底避免了爆内存和系统卡顿，而且下载流量平稳有序，还能有效防止触发频繁限制。

---

## 什么是 Runtime？

平时我们直接调用 `download_album('123456')` 时，完全不需要传任何 Runtime 参数。

这是因为 JMComic 已经在后台自动创建了一个默认的 Runtime（下载运行时），负责拉起线程池，并在下载结束后自动释放。

**Runtime 的定位很简单：它就是专门负责管理下载过程中“线程池与并发调度”的管家。**

当你需要**自定义线程数**，或者希望**复用已有线程池**时，就需要显式创建一个 Runtime，并通过 `jm_task_context` 传递给下载任务：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 1. 创建你定制的 Runtime（支持 with 上下文管理，自动安全释放）
with JmSyncRuntime(...) as runtime:
    # 2. 通过 jm_task_context 注入给下载任务
    with jm_task_context(runtime=runtime):
        download_album(...)
```

接下来分别介绍同步与异步的具体用法。

---

## 1. 同步下载：使用 JmSyncRuntime

同步下载时，任务分为三个层级：本子、章节、图片。`JmSyncRuntime` 允许你分别控制这三层的并发线程数。

### 场景 A：自定义各层并发数

通过 `JmSyncRuntime` 指定每一层的最大线程数，并通过 `with` 语法和 `jm_task_context` 传入下载任务：

```python
from jmcomic import JmSyncRuntime, download_album, jm_task_context

# 1. 创建 Runtime，指定各层并发上限（支持 with 上下文管理，退出后自动安全释放）
with JmSyncRuntime(
    id_workers=2,       # 最多同时下载 2 个本子
    photo_workers=3,    # 所有本子合计最多同时处理 3 个章节
    image_workers=8,    # 所有章节合计最多同时下载 8 张图片
) as runtime:
    # 2. 绑定到任务上下文并执行下载
    with jm_task_context(runtime=runtime):
        download_album(['123456', '789012', '345678'])
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

    # 传入外部线程池。遵循“谁创建谁关闭”原则，runtime 退出时不会关闭外部传入的线程池
    with JmSyncRuntime(
        id_executor=id_pool,
        photo_executor=photo_pool,
        image_executor=image_pool,
    ) as runtime:
        with jm_task_context(runtime=runtime):
            download_album(['123456', '789012'])
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
    with JmAsyncRuntime(decode_workers=4) as runtime:
        with jm_task_context(runtime=runtime):
            await download_album_async(['123456', '789012'])


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
        with JmAsyncRuntime(decode_executor=my_decode_pool) as runtime:
            with jm_task_context(runtime=runtime):
                await download_album_async('123456')


asyncio.run(main())
```

---

## 3. 常见问题与速查

| 需求 | 推荐做法 | 说明 |
| :--- | :--- | :--- |
| **同步批量控制并发** | `JmSyncRuntime(id_workers=..., image_workers=...)` | 避免一次性下几十个本子把资源占满 |
| **异步控制解密并发** | `JmAsyncRuntime(decode_workers=...)` | 仅限制图片解密写盘线程数，网络请求仍走协程 |
| **复用已有线程池** | 传入 `*_executor=你的线程池` | 遵循“谁创建谁关闭”，外部线程池不会被自动关闭 |
| **获取当前 Runtime** | `JTC.get_runtime()` | 在插件或上下文内部随时读取当前生效的 Runtime 对象 |
