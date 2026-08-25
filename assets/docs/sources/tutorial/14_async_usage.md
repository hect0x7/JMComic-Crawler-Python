# 异步使用指南

> [!TIP]
> 关于`async`和`sync`版本的性能对比可以查看 → [actions-benchmark](https://github.com/hect0x7/JMComic-Crawler-Python/actions/workflows/benchmark.yml)
>
> 简单来说，下载场景`async`**快10%↑**，纯查询无下载场景`async`**快30%↑**

本章节介绍项目中提供的异步接口。章节结构与 `0_common_usage.md` 基本对应，可作为从同步迁移到异步代码的对照参考。

---

## 1. 异步下载本子/章节

你可以直接使用以下方法来进行异步下载：

```python
import asyncio
import jmcomic

async def main():
    # 异步下载单个本子
    album, downloader = await jmcomic.download_album_async('438696')

    # 返回的 downloader 已释放网络连接和线程池，只用于读取下载结果
    print(downloader.download_failed_image)
    
    # 异步下载单章节
    await jmcomic.download_photo_async('438696')
    
    # 批量异步下载（直接传递包含 ID 的列表或迭代器即可，内部会自动同时下载）
    await jmcomic.download_album_async(['123', '456'])

if __name__ == '__main__':
    asyncio.run(main())
```

## 2. 使用 Option 定制化异步下载

和同步版本一样，你可以配合 `option` 对象来定制网络请求、代理、下载路径等：

```python
import asyncio
from jmcomic import create_option_by_file, download_album_async

async def main():
    # 通过配置文件来创建option对象
    option = create_option_by_file('op.yml')
    
    # 调用异步下载 api，把 option 作为参数传递 
    await download_album_async(123, option)

asyncio.run(main())
```

## 3. 异步获取实体类，并发请求

### 💡 关于 async with 和自动初始化

当你使用异步client时，推荐直接搭配 `async with` 上下文管理器来使用：

```python
# 推荐用法，离开代码块时会自动清理并断开连接
async with JmOption.default().new_jm_async_client() as cl:
    album = await cl.get_album_detail(123)

# 另外一种用法，单独使用client
cl = JmOption.default().new_jm_async_client()
try:
    album = await cl.get_album_detail(123)
finally:
    await cl.close()
```

`async with` 和单独使用client都会自动初始化，区别主要在初始化时机和生命周期管理：

| 对比项 | 使用 `async with` | 单独使用client                            |
| --- | --- |-------------------------------------------|
| 初始化时机 | 进入 `async with` 作用域时自动初始化 | 第一次发起真实请求前自动初始化            |
| 初始化内容 | 自动完成域名解析、联通性检查等必要工作 | 同左                                      |
| 初始化次数 | 只初始化一次 | 同左                                      |
| 连接清理 | 离开作用域时自动安全释放连接 | 使用完成后必须显式调用 `await cl.close()` |
| 推荐场景 | 推荐用于一般请求和下载任务 | 需要自行控制客户端生命周期时使用          |

两种写法都不需要手动调用初始化方法；如果单独使用客户端，请通过 `try/finally` 确保连接一定会被关闭。


---

### 并发请求示例

使用 `asyncio.gather` 可以并发执行网络请求：

```python
import asyncio
from jmcomic import JmOption, AsyncJmApiClient

async def main():
    op = JmOption.default()
    
    # 同步获取客户端对象，并通过上下文管理器自动管理生命周期
    async with op.new_jm_async_client() as cl:
        # 示例：使用 async 并发获取本子详情
        album_id_list = [123, 456]
        album_list = await asyncio.gather(
            *(cl.get_album_detail(aid) for aid in album_id_list)
        )
        
        # 打印结果
        for aid, album in zip(album_id_list, album_list):
            print(f'[JM{aid}] 本子详情: {album}')

asyncio.run(main())
```

## 4. 异步异常处理示例

异步调用的异常机制与同步完全一致，同样可以通过捕获 `JmcomicException` 及各类派生异常进行处理：

```python
import asyncio
from jmcomic import JmOption, MissingAlbumPhotoException, JsonResolveFailException, RequestRetryAllFailException, JmcomicException

async def main():
    async with JmOption.default().new_jm_async_client() as cl:
        try:
            album = await cl.get_album_detail('99999999')
        except MissingAlbumPhotoException as e:
            print(f'id={e.error_jmid}的本子不存在')
        except JsonResolveFailException as e:
            print(f'解析json失败: {e.resp.status_code}')
        except RequestRetryAllFailException:
            print(f'请求失败，重试次数耗尽')
        except JmcomicException as e:
            print(f'遇到异常: {e}')

asyncio.run(main())
```

## 5. 异步搜索本子

由于搜索结果通常有多页，推荐使用 `search_gen` 异步生成器。配合 `async for`，客户端会自动处理翻页逻辑并逐页获取数据：

```python
import asyncio
from jmcomic import JmOption

async def main():
    async with JmOption.default().new_jm_async_client() as cl:
        # async for 会帮你自动加载下一页，一页一页往下搜
        async for page in cl.search_gen('+MANA +无修正'):
            print(f'当前获取到了第 {page.page_number} 页，本页数据量: {len(page)}，总数量: {page.total}')
            
            for album_id, title in page.iter_id_title():
                print(f'[{album_id}]: {title}')

asyncio.run(main())
```

如果只需要第一页的数据，依然可以直接调用基础的 `await cl.search(...)` 方法。

## 6. 异步获取收藏夹

获取收藏夹的用法和搜索非常像，同样支持使用异步生成器 `favorite_folder_gen` 自动翻页获取整个收藏夹的内容：

```python
import asyncio
from jmcomic import JmOption

async def main():
    async with JmOption.default().new_jm_async_client() as cl:
        # 先登录
        await cl.login('你的用户名', '你的密码')

        # 使用 async for 遍历整个收藏夹的所有页
        async for page in cl.favorite_folder_gen(folder_id='0'):
            # 遍历本页的所有本子
            for aid, atitle in page.iter_id_title():
                print(aid, atitle)
                
            # 同时支持获取当前账号下的所有收藏夹目录信息
            for folder_id, folder_name in page.iter_folder_id_name():
                print(f'收藏夹id: {folder_id}, 名称: {folder_name}')

asyncio.run(main())
```

## 7. 异步分类 / 排行榜

分类和排行榜本质上都是过滤请求，可以使用 `categories_filter` 获取单页，或使用
`categories_filter_gen` 异步生成器自动翻页。

```python
import asyncio
from jmcomic import JmMagicConstants, JmOption

async def main():
    async with JmOption.default().new_jm_async_client() as cl:
        # 获取全部时间、全部分类下，按观看数排序的第一页本子
        page = await cl.categories_filter(
            page=1,
            time=JmMagicConstants.TIME_ALL,
            category=JmMagicConstants.CATEGORY_ALL,
            order_by=JmMagicConstants.ORDER_BY_VIEW,
        )
        
        for aid, atitle in page:
            print(aid, atitle)

        async for page in cl.categories_filter_gen(
            time=JmMagicConstants.TIME_ALL,
            category=JmMagicConstants.CATEGORY_ALL,
            order_by=JmMagicConstants.ORDER_BY_VIEW,
        ):
            print(f'当前获取到了第 {page.page_number} 页，本页数据量: {len(page)}')

asyncio.run(main())
```

## 8. 关于 `async_impl` 配置

注意：仅仅在 `option.yml` 中增加配置**并不能**让代码自动变成异步，你必须要在代码中改为调用 `_async` 相关方法（如上文所示）。

`async_impl`目前可以不配置，因为配置的作用仅仅是指定底层使用哪种API实现。目前的唯一实现是 `async_api`：

```yaml
# myoption.yml
client:
  impl: html
  # 指定异步客户端的底层实现类 (目前仅有: async_api)
  async_impl: async_api
```

## 9. 查看下载耗时

异步下载完成后，可以直接查看自己总共等了多久，也可以继续查看具体是哪个本子、章节或图片比较慢。所有 `duration` 的单位都是秒。

```python
import asyncio
import jmcomic


async def main():
    result = await jmcomic.download_album_async('438696')
    album = result.detail

    # 从调用 download_album_async 到返回，总共等了多久
    print(f'总共等待: {result.duration:.3f} 秒')

    # 如果下载比较慢，可以继续查看具体慢在哪里
    print(f'下载本子用了: {album.duration:.3f} 秒')
    for photo in album:
        print(f'下载章节 {photo.id} 用了: {photo.duration:.3f} 秒')
        for image in photo:
            print(f'处理图片 {image.img_file_name} 用了: {image.duration:.3f} 秒')


asyncio.run(main())
```

| 字段 | 它告诉你什么 |
| --- | --- |
| `result.duration` | 从调用异步下载方法到返回，你总共等了多久 |
| `album.duration` | 下载这个本子花了多久，包含获取本子信息和整理下载结果 |
| `photo.duration` | 下载这个章节花了多久，包含获取或补全章节信息 |
| `image.duration` | 处理这张图片花了多久，包含检查缓存、下载、解密和保存 |

下载器可能同时处理多个章节或多张图片，所以把它们的耗时全部相加，不会得到本子的耗时，这是正常现象。同步下载中的这些字段含义相同。
