# 异步使用指南

本章节介绍项目中提供的异步接口。章节结构与 `0_common_usage.md` 基本对应，可作为从同步迁移到异步代码的对照参考。

---

## 1. 异步下载本子/章节

你可以直接使用最高层的封装方法来进行异步下载：

```python
import asyncio
import jmcomic

async def main():
    # 异步下载本子
    await jmcomic.download_album_async('438696')
    
    # 异步下载单章节
    await jmcomic.download_photo_async('438696')
    
    # 批量异步下载（替代同步版传递 list）
    await jmcomic.download_batch_async(['123', '456'])

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

使用 `asyncio.gather` 可以极大地加速网络请求：

```python
import asyncio
from jmcomic import JmOption, AsyncJmApiClient

async def main():
    op = JmOption.default()
    
    # 异步获取客户端对象
    cl: AsyncJmApiClient = await op.new_jm_async_client()
    
    # 示例：使用async并发获取本子详情
    album_id_list = [123, 456]
    album_list = await asyncio.gather(
        *(cl.get_album_detail(aid) for aid in album_id_list)
    )
    
    # 打印结果
    for aid, album in zip(album_id_list, album_list):
        print(f'[JM{aid}] 本子详情: {album}')
        
    # 获取章节实体类
    photo = await cl.get_photo_detail('212214')
    print(photo.name)

asyncio.run(main())
```

## 4. 异步异常处理示例

异步调用的异常机制与同步完全一致，同样可以通过捕获 `JmcomicException` 及各类派生异常进行兜底：

```python
import asyncio
from jmcomic import JmOption, MissingAlbumPhotoException, JsonResolveFailException, RequestRetryAllFailException, JmcomicException

async def main():
    cl = await JmOption.default().new_jm_async_client()

    try:
        album = await cl.get_album_detail('99999999')
    except MissingAlbumPhotoException as e:
        print(f'id={e.error_jmid}的本子不存在')
    except JsonResolveFailException as e:
        print(f'解析json失败: {e.resp.status_code}')
    except RequestRetryAllFailException:
        print(f'请求失败，重试次数耗尽')
    except JmcomicException as e:
        print(f'遇到兜底异常: {e}')

asyncio.run(main())
```

## 5. 异步搜索本子

使用 `search` 方法获取搜索分页数据。注意，异步方法目前未提供 `_gen` 生成器封装，需要手动管理页码遍历。

```python
import asyncio
from jmcomic import JmOption, JmSearchPage

async def main():
    cl = await JmOption.default().new_jm_async_client()

    # 查询，类似于网页上的【站内搜索】
    page: JmSearchPage = await cl.search(
        search_query='+MANA +无修正', 
        page=1, 
        main_tag=0, 
        order_by='mr', 
        time='a', 
        category='doujin', 
        sub_category=None
    )
    
    print(f'结果总数: {page.total}, 分页大小: {page.page_size}，页数: {page.page_count}')

    for album_id, title in page.iter_id_title():
        print(f'[{album_id}]: {title}')

asyncio.run(main())
```

## 6. 异步获取收藏夹

获取收藏夹同样支持分页，可以传入指定的 `folder_id`。

```python
import asyncio
from jmcomic import JmOption

async def main():
    cl = await JmOption.default().new_jm_async_client()
    # 异步登录
    await cl.login('用户名', '密码')

    # 获取特定收藏夹的单页
    page = await cl.favorite_folder(
        page=1,
        order_by='mr', # JmMagicConstants.ORDER_BY_LATEST
        folder_id='0'  # 收藏夹id
    )
    
    # 遍历本页结果
    for aid, atitle in page.iter_id_title():
        print(aid, atitle)
        
    # 打印当前帐号的所有收藏夹信息
    for folder_id, folder_name in page.iter_folder_id_name():
        print(f'收藏夹id: {folder_id}, 收藏夹名称: {folder_name}')

asyncio.run(main())
```

## 7. 异步分类 / 排行榜

分类和排行榜本质上都是过滤请求，可以使用 `categories_filter` 异步方法获取分页。

```python
import asyncio
from jmcomic import JmOption

async def main():
    cl = await JmOption.default().new_jm_async_client()

    # 获取全部时间、全部分类下，按观看数排序的第一页本子
    page = await cl.categories_filter(
        page=1,
        time='a',        # JmMagicConstants.TIME_ALL
        category='all',  # JmMagicConstants.CATEGORY_ALL
        order_by='mv',   # JmMagicConstants.ORDER_BY_VIEW
    )
    
    for aid, atitle in page:
        print(aid, atitle)

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
