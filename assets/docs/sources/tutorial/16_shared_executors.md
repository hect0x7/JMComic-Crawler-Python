# 下载并发调优 / 复用线程池

> 日常使用 jmcomic 下载时，不需要关心并发与配置线程池，jmcomic 内部会创建临时线程池来并发下载。
> 
> 但在以下两种场景下，你可能更希望精细控制：
> 
> 1. **大批量下载**：一次性下载几十上百个本子，希望严格限制并发（例如“最多同时下 2 个本子，所有图片最多 8 个线程”），避免把网络或内存卡爆。
> 2. **复用已有的线程池**：你的程序（如 Web 服务、后台调度器）本身已经维护了全局线程池，希望 JMComic 直接复用，避免重复创建和销毁线程。
> 
> 如果你的诉求是这些，那么本教程推荐你往下阅读。
---

## 1、先算一笔账

>  下载本子时有多少线程并发？

jmcomic 对下载分为三层，本子层、章节层、图片层

当你写 `download_album([123, 456])` 时，希望下载两个本子，每层的并发数如下：

* **本子层**：取本子总数
  * 这个场景就是 **2**，两个本子

* **章节层**：取option配置 `threading.photo`，不配默认是当前系统的 CPU 核心数
  * 假设这个场景是跑在8核的cpu上，那就是 **8**

* **图片层**：取option配置 `threading.image`，不配默认固定为 **20** 个线程。
  * 这个场景假设没配，就是 **20**

各层级联调度的真实结构如下：

```text
download_album([123, 456])  ──► 待下载 2 个本子

【本子层】同时跑 2 个本子
  │
  ├─► 本子 123 ── 各自独立创建 Photo 线程池 (默认 8 线程)
  │     ├─► 章节 1 ── 各自独立创建 Image 线程池 (默认 20 线程) ──► 20 线程下载图片
  │     ├─► 章节 2 ── 各自独立创建 Image 线程池 (默认 20 线程) ──► 20 线程下载图片
  │     └─► ... (最多同时跑 8 个章节)
  │
  └─► 本子 456 ── 各自独立创建 Photo 线程池 (默认 8 线程)
        ├─► 章节 1 ── 各自独立创建 Image 线程池 (默认 20 线程) ──► 20 线程下载图片
        ├─► 章节 2 ── 各自独立创建 Image 线程池 (默认 20 线程) ──► 20 线程下载图片
        └─► ... (最多同时跑 8 个章节)
```

如果 123,456这个本子的章节和图片非常多，就有可能拉满全部并发，峰值线程数会达到 $2 \text{ (本子)} \times 8 \text{ (章节)} \times 20 \text{ (图片)} = \mathbf{320}$ **个并发线程！**

这种**乘法级（连乘）级联膨胀**，会导致系统瞬时创建上千个系统线程，引起大量 CPU 上下文切换、内存占用飙升、网络连接数耗尽，甚至直接触发目标服务端的反爬限频或把自己的本地网络打瘫痪。

---

## 2、改配置减少并发

要减少并发，最简单直接的办法，就是把线程数改小一点。

直接在 option 中配置章节层和图片层的并发：

```yaml
# option.yml
download:
  threading:
    photo: 2   # 每个本子同时只下载 2 个章节
    image: 5   # 每个章节同时只下载 5 张图片
```

也可以在 Python 代码里直接修改：

```python
from jmcomic import JmOption, download_album

option = JmOption.default()
option.download.threading.photo = 2
option.download.threading.image = 5

download_album([123, 456], option=option)
```

### 算一笔新账

同样下载 123 和 456 这两个本子，此时的峰值并发变成了：

$$2 \text{ (本子)} \times 2 \text{ (章节)} \times 5 \text{ (图片)} = \mathbf{20} \text{ 个并发线程}$$

从 **320** 骤降到 **20**！

### 减少本子层并发

上面改配置只管住了章节层和图片层。但只要你写的是 `download_album([123, 456])` 传列表，本子层默认依然是同时并发跑的。

如果要减少本子层并发，最直接的做法就是**不要传列表**，而是改成写两行 `download_album`：

```python
from jmcomic import download_album

# 改成两行：本子 123 下载完后，才开始下载本子 456
download_album(123)
download_album(456)
```

这样本子层就完全不并发了（本子并发数直接降为 1）。再配合上面的配置（photo=2, image=5），同一时刻的峰值线程数就只有：

$$1 \text{ (本子)} \times 2 \text{ (章节)} \times 5 \text{ (图片)} = \mathbf{10} \text{ 个并发线程}$$

---

## 3、仅仅改配置不够的场景

通过上面的改配置或者拆分下载，已经能够满足大部分日常需求。

但在以下场景中，你可能需要更精细的并发控制：

##### 场景 1：一次性下载大量本子，希望限制同时下载的本子数（排队下载）

>  如果你有几十个本子要下载，直接传列表 `download_album([1, 2, ...])` 会导致所有本子同时并发跑起来；而如果写成两行或者循环，又只能一个一个完全串行下载。
>
>  如果你希望**同时下载 2 个本子，其余的排队等待**，只改局部配置是无法实现的。

##### 场景 2：希望所有图片下载共用线程池，严格卡死全局线程上限

> 每个章节下载时都会各自创建一套图片线程池。
>
> 如果你希望**不管当前有多少个本子在下载，整个程序全局最多只允许 8 个线程在下载图片，大家共享同一个线程池**，就需要共享图片线程池，而纯配置无法实现。

##### 场景 3：复用外部已有的线程池

>  如果你的项目（例如 Web 服务、定时任务调度器）本身已经维护了全局的 `ThreadPoolExecutor`，希望 jmcomic 直接复用，避免每次下载都重复创建和销毁线程。


## 4、使用 Runtime 精细控制并发

针对上面介绍的场景，jmcomic 提供了 **Runtime** 机制，目的是更加透明精细地控制并发。

你可以把 Runtime 理解为**线程池管家**。它主要为你提供以下能力：

1. **控制【本子层】并发**：指定最多同时下载几个本子，其余本子排队；
2. **让【章节/图片层】共享线程池**：不管下载多少本子，章节和图片的底层线程池固定共享，不再连乘膨胀；
3. **支持复用外部线程池**：可以直接使用你创建的外部线程池 `ThreadPoolExecutor`。

> [!NOTE]
>
> 由于同步下载和异步下载是两套API，因此runtime的使用也有区别，需要挑选对应的实现类：
>
> - **同步下载**：使用 `JmSyncRuntime`。同步下载涉及“本子、章节、图片”三层，用它来统一管理和共享这三层的线程池。
> - **异步下载**：使用 `JmAsyncRuntime`。异步下载的网络请求走的是 `asyncio` 协程，不占线程；只有图片解密与写盘需要线程，因此它只负责管理一个 `decode`（解码）线程池。

---

### 4.1 同步下载：使用 JmSyncRuntime

#### 场景 A：自定义各层并发数（大批量下载防卡死）

创建 `JmSyncRuntime` 并指定每一层的最大线程数：

```python
from jmcomic import JmSyncRuntime, download_album

# 1. 创建 JmSyncRuntime，推荐搭配 with，可以自动关闭runtime创建的线程池资源
with JmSyncRuntime(
    album_workers=2,    # 最多同时下载 2 个本子（其余本子排队）
    photo_workers=3,    # 所有本子合计最多同时处理 3 个章节
    image_workers=8,    # 所有章节合计最多同时下载 8 张图片
):
    # 2. 下载3个本子，这3个本子都受 Runtime 的并发约束
    download_album(['123456', '789012', '345678'])
```

**用了 Runtime 之后，并发线程数从“乘法”变成了“加法”**：
此时系统的总工作线程数恒定为：
$$2 \text{ (本子)} + 3 \text{ (章节)} + 8 \text{ (图片)} = \mathbf{13} \text{ 个线程}$$

无论你一次性传 10 个还是 100 个本子，总线程数都严格卡在 13 个，既不会爆内存，也不会把电脑或网络卡死。

> [!TIP]
> 如果某一层不传参数（例如不传 `photo_workers`），该层会使用系统默认值。

#### 场景 B：复用外部已有的线程池

如果你的程序已经有现成的 `ThreadPoolExecutor`，可以直接传给 Runtime 复用：

```python
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmSyncRuntime, download_album

# 假设程序中已有维护好的线程池
with ThreadPoolExecutor(max_workers=2) as album_pool, \
     ThreadPoolExecutor(max_workers=3) as photo_pool, \
     ThreadPoolExecutor(max_workers=8) as image_pool:

    # 传入外部线程池。遵循“谁创建谁关闭”原则，Runtime 退出时不会关闭外部传入的线程池
    with JmSyncRuntime(
        album_executor=album_pool,
        photo_executor=photo_pool,
        image_executor=image_pool,
    ):
        download_album(['123456', '789012'])
    # 走到这里，album_pool、photo_pool、image_pool 都不会被 runtime 关闭
```

---

### 4.2 异步下载：使用 JmAsyncRuntime

异步下载与同步不同：网络请求由 `asyncio` 协程高效处理，不占线程；<u>**只有图片的解密与保存需要用到后台线程池**。</u>

因此，`JmAsyncRuntime` 只需要管理一个 `decode`（图片解码）线程池，配置非常简单。

#### 场景 A：指定解码并发线程数

```python
import asyncio
from jmcomic import JmAsyncRuntime, download_album_async


async def main():
    # 限制最多同时使用 4 个线程进行图片解密与保存
    with JmAsyncRuntime(decode_workers=4):
        await download_album_async(['123456', '789012'])


asyncio.run(main())
```

#### 场景 B：复用外部已有的解码线程池

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from jmcomic import JmAsyncRuntime, download_album_async


async def main():
    # 借用现成的外部线程池
    with ThreadPoolExecutor(max_workers=4) as my_decode_pool:
        with JmAsyncRuntime(decode_executor=my_decode_pool):
            await download_album_async('123456')


asyncio.run(main())
```

---

## 5、Web 场景示例：全局长效复用 Runtime

在 FastAPI、Django 等常驻 Web 服务或后台常驻进程中，为每个请求频繁创建和销毁线程池会造成不必要的系统开销。

推荐的做法是：**应用启动时创建全局长效 Runtime，每个请求通过 `jm_task_context` 注入当前请求专属的上下文元数据（如 `session_id`、`user_id`）**。

```python
from jmcomic import (
    JmSyncRuntime,
    download_album,
    jm_task_context,
)

# 1. 进程启动时单例初始化全局长效 Runtime，跨请求复用
app_runtime = JmSyncRuntime(
    album_workers=4,
    photo_workers=8,
    image_workers=16,
)

# 2. 单个 Web 请求 / 后台作业处理函数
def handle_download_request(request_id: str, user_id: str, album_ids: list):
    # 将长效 runtime 与链路追踪字段装配入上下文
    with jm_task_context(
        runtime=app_runtime,
        session_id=request_id,
        user_id=user_id,
    ):
        # 内部所有日志、插件、下载任务均透明享有 session_id，并严格受全局并发控制
        download_album(album_ids)
```

---

## 6、Runtime 生命周期与关闭规范

为避免线程泄漏并确保资源安全，JMComic 的 Runtime 严格遵循以下三条生命周期规范：

1. **使用 `with runtime` 上下文管理** → 离开作用域自动关闭
   > 离开 `with` 作用域（无论是正常完成还是发生未捕获异常退出）时，会自动调用 `runtime.close()`，安全关闭 Runtime 自身创建并拥有的底层线程池。

2. **不用 `with`** → 不会自动关闭
   > 若直接创建 `runtime = JmSyncRuntime(...)` 而不搭配 `with`，Runtime 不会自动关闭，需要调用方在适当时机显式调用 `runtime.close()`。

3. **用户外传 Executor** → 遵循“谁创建、谁负责关闭”原则
   > 若在构造 Runtime 时传入了用户自定义的 `*_executor`，Runtime 在 `close()` 时**绝不会**关闭它，其生命周期全权由调用方自行管理。

---

## 7、常见场景速查

| 业务场景 | 推荐代码形态 | 核心优势 |
| :--- | :--- | :--- |
| **平时随手下载** | `download_album(id)` | 零配置，开箱即用 |
| **同步大批量下载限并发** | `with JmSyncRuntime(album_workers=2):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`download_album(ids)` | 自动生效与回收，防止并发膨胀卡死 |
| **异步控制解密并发** | `with JmAsyncRuntime(decode_workers=4):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`await download_album_async(ids)` | 仅限制图片解密写盘线程数，网络仍走协程 |
| **复用外部已有线程池** | 传入 `*_executor=你的线程池` | 严格遵循“谁创建谁关闭”，外部池不被关闭 |
| **Web常驻服务复用** | `with jm_task_context(runtime=app_runtime, session_id=...):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`download_album(ids)` | 进程级长效池跨请求复用，上下文日志透明注入 |

