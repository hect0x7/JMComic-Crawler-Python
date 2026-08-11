# 常用类和方法

## 下载本子/章节

```python
from jmcomic import *

# 下载id为438696的本子 (https://18comic.vip/album/438696)
download_album(438696)

# 下载章节 (https://18comic.vip/photo/438696)
download_photo(438696)

# 同时下载多个本子
download_album([123, 456, 789])

# 查看本子/章节下载位置和耗时
result: DownloadResult = download_album(123)
album: JmAlbumDetail = result.detail # detail是实体类，download_album 返回 album，download_photo 返回 photo
print(f'本子-JM{album.id}，下载保存文件夹: {album.save_path}, 下载耗时: {result.duration:.3f}秒')
# DownloadResult 里还包含大量字段，更多用法请查阅下方章节【下载返回值】
```

## 使用option定制化下载本子

如果你在下载本子时有一些定制化需求，

例如指定禁漫域名，使用代理，登录禁漫，图片格式转换等等，

那么，你可以试试看jmcomic提供的option机制

```python
from jmcomic import *

# 1. 在调用下载api前，通过创建和使用option对象，可以定制化下载行为。
# 推荐使用配置文件的方式来创建option对象，
# 你可以配置很多东西，比如代理、cookies、下载规则等等。
# 配置文件的语法参考: https://jmcomic.readthedocs.io/zh-cn/latest/option_file_syntax/
option = create_option_by_file('op.yml')  # 通过配置文件来创建option对象

# 2. 调用下载api，把option作为参数传递 
download_album(123, option)
# 也可以使用下面这种面向对象的方式，是一样的
option.download_album(123)
```

## 获取本子/章节/图片的实体类，下载图片/封面图

```python
from jmcomic import *

# 客户端
client = JmOption.default().new_jm_client()

# 本子实体类
album: JmAlbumDetail = client.get_album_detail('427413')

# 下载本子封面图，保存为 cover.png （图片后缀可指定为jpg、webp等）
client.download_album_cover('427413', './cover.png')


def fetch(photo: JmPhotoDetail):
    # 章节实体类
    photo = client.get_photo_detail(photo.photo_id, False)
    print(f'章节id: {photo.photo_id}')

    # 图片实体类
    image: JmImageDetail
    for image in photo:
        print(f'图片url: {image.img_url}')

    # 下载单个图片
    client.download_by_image_detail(image, './a.jpg')
    # 如果是已知未混淆的图片，也可以直接使用url来下载
    random_image_domain = JmModuleConfig.DOMAIN_IMAGE_LIST[0]
    client.download_image(f'https://{random_image_domain}/media/albums/416130.jpg', './a.jpg')


# 多线程发起请求
multi_thread_launcher(
    iter_objs=album,
    apply_each_obj_func=fetch
)
```

## jmcomic异常处理示例

```python
from jmcomic import *

# 客户端
client = JmOption.default().new_jm_client()

# 捕获获取本子/章节详情时可能出现的异常
try:
    # 请求本子实体类
    album: JmAlbumDetail = client.get_album_detail('427413')
except MissingAlbumPhotoException as e:
    print(f'id={e.error_jmid}的本子不存在')

except JsonResolveFailException as e:
    print(f'解析json失败')
    # 响应对象
    resp = e.resp
    print(f'resp.text: {resp.text}, resp.status_code: {resp.status_code}')

except RequestRetryAllFailException as e:
    print(f'请求失败，重试次数耗尽')

except JmcomicException as e:
    # 捕获所有异常，用作兜底
    print(f'jmcomic遇到异常: {e}')

# 多线程下载时，可能出现非当前线程下载失败，抛出异常，
# 而JmDownloader有对应字段记录了这些线程发生的异常
# 使用check_exception=True参数可以使downloader主动检查是否存在下载异常
# 如果有，则当前线程会主动上抛一个PartialDownloadFailedException异常
# 该参数主要用于主动检查部分下载失败的情况，（仅对单个本子/章节 ID 生效，传入多个 ID 时不生效。多个 ID 的场景见下）
# 因为非当前线程抛出的异常（比如下载章节的线程和下载图片的线程），这些线程如果抛出异常，
# 当前线程是感知不到的，try-catch下载方法download_album不能捕获到其他线程发生的异常。
try:
    album, downloader = download_album(123, check_exception=True)
except PartialDownloadFailedException as e:
    downloader: JmDownloader = e.downloader
    print(f'下载出现部分失败, 下载失败的章节: {downloader.download_failed_photo}, 下载失败的图片: {downloader.download_failed_image}')

# 多 ID 下载不会因为某一项失败而中断，请检查 BatchResult.failed。
# 如果需要在批量失败时抛异常、重试或拿到更详细信息，建议自行封装一个批量下载方法。
result = download_album([123, 456, 789])
for album_id, error in result.failed.items():
    print(f'本子 {album_id} 下载失败: {error}')
```


## 搜索本子

```python
from jmcomic import *

client = JmOption.default().new_jm_client()

# 分页查询，search_site就是禁漫网页上的【站内搜索】
page: JmSearchPage = client.search_site(search_query='+MANA +无修正', page=1)
print(f'结果总数: {page.total}, 分页大小: {page.page_size}，页数: {page.page_count}')

# page默认的迭代方式是page.iter_id_title()，每次迭代返回 albun_id, title
for album_id, title in page:
    print(f'[{album_id}]: {title}')

# 直接搜索禁漫车号
page = client.search_site(search_query='427413')
album: JmAlbumDetail = page.single_album
print(album.tags)
```

## 搜索并下载本子

```python
from jmcomic import *

option = JmOption.default()
client = option.new_jm_client()

tag = '無修正'
# 搜索标签，可以使用search_tag。
# 搜索第一页。
page: JmSearchPage = client.search_tag(tag, page=1)

aid_list = []

for aid, atitle, tag_list in page.iter_id_title_tag():  # 使用page的iter_id_title_tag迭代器
    if tag in tag_list:
        print(f'[标签/{tag}] 发现目标: [{aid}]: [{atitle}]')
        aid_list.append(aid)

download_album(aid_list, option)
```

## 获取评论

目前支持获取两种评论：

| 评论类型 | 说明 | 获取一页的方法 | 自动翻页的方法 |
| --- | --- | --- | --- |
| 本子评论 | 获取指定本子下的评论和回评 | `album_pagination` | `album_pagination_gen` |
| 全站评论 | 获取全站最新发布的评论，可通过 `comment.album_id` 知道评论来自哪个本子 | `forum_pagination` | `forum_pagination_gen` |

评论页可以直接遍历，评论对象也可以直接打印，格式为 `[评论ID] 用户（剧透）: 内容`。

### 获取本子评论

`album_pagination` 获取指定本子的一页评论。

```python
from jmcomic import JmOption, JmAlbumComment

client = JmOption.default().new_jm_client(impl='api')
page = client.album_pagination('123456')

print(f'第 {page.page_number}/{page.page_count} 页，当前页一共 {len(page)} 条主评论，整本一共 {page.total} 条主评论')
for comment in page:
    comment: JmAlbumComment # 评论是实体类
    print(
        f'评论ID: {comment.comment_id} | 用户ID: {comment.user_id} | 用户: {comment.nickname or comment.username} | '
        f'是否剧透: {comment.is_spoiler} | 点赞数: {comment.likes} | 发布时间: {comment.created_at}\n内容: {comment.content}'
    )
    for reply in comment.replies:
        reply: JmAlbumComment # 回评也是相同的实体类
        print('  └─', reply)

# 需要连续获取分页时，使用生成器：
for page in client.album_pagination_gen('123456'):
    print(f'\n第 {page.page_number} 页')
    for comment in page:
        print(comment)
```

### 获取全站评论

`forum_pagination` 获取一页全站评论。

> [!NOTE]
> html 端不提供 `total`（全部分页的主评论总数）和 `page_count`（总页数），这两个字段都为 `None`，api端则有值。

```python
page = client.forum_pagination(page=1)

print(f'第 {page.page_number}/{page.page_count} 页，当前页一共 {len(page)} 条主评论，全站一共 {page.total} 条主评论')
for comment in page:
    print(f'本子 {comment.album_id} | {comment}')

# 全站评论同样支持生成器
for page in client.forum_pagination_gen(page=1):
    print(f'\n第 {page.page_number} 页')
    for comment in page:
        print(f'本子 {comment.album_id} | {comment}')
```

## 获取收藏夹

可参考discussions: https://github.com/hect0x7/JMComic-Crawler-Python/discussions/235

### 一键导出全部收藏夹

下面的代码不会下载图片，只会把帐号中的全部收藏夹导出为 CSV，并生成 `favorites.zip`：

```python
from jmcomic import JmOption, FavoriteFolderExportPlugin

USERNAME = '你的禁漫帐号'
PASSWORD = '你的禁漫密码'

option = JmOption.default()
option.build_jm_client().login(USERNAME, PASSWORD)

FavoriteFolderExportPlugin(option).invoke(
    save_dir='./',
    zip_enable=True,
    zip_filepath='./favorites.zip',
)
```

### 获取并遍历收藏夹

```python
from jmcomic import *

option = JmOption.default()
client = option.new_jm_client()
client.login('用户名', '密码')  # 也可以使用login插件/配置cookies

# 遍历全部收藏的所有页
for page in client.favorite_folder_gen():  # 如果你只想获取特定收藏夹，需要添加folder_id参数
    # 遍历每页结果
    for aid, atitle in page.iter_id_title():
        # aid: 本子的album_id
        # atitle: 本子的名称
        print(aid)
    # 打印当前帐号的所有收藏夹信息
    for folder_id, folder_name in page.iter_folder_id_name():
        print(f'收藏夹id: {folder_id}, 收藏夹名称: {folder_name}')

# 获取特定收藏夹的单页，使用favorite_folder方法
page = client.favorite_folder(page=1,
                              order_by=JmMagicConstants.ORDER_BY_LATEST,
                              folder_id='0'  # 收藏夹id
                              )
```

## 分类 / 排行榜

禁漫的分类是一个和搜索有些类似的功能。

搜索是按某一条件进行过滤。

分类没有过滤，就是把某一类别（category）下的本子全都调出来。

禁漫的排行榜就是分类的一种形式

下面演示调用分类api

```python
from jmcomic import *

# 创建客户端
op = JmOption.default()
cl = op.new_jm_client()

# 调用分类接口
# 根据下面的参数，这个调用的意义就是：
# 在全部分类下，选择所有时间范围，按观看数排序后，获取第一页的本子
page: JmCategoryPage = cl.categories_filter(
    page=1,
    time=JmMagicConstants.TIME_ALL,  # 时间选择全部，具体可以写什么请见JmMagicConstants
    category=JmMagicConstants.CATEGORY_ALL,  # 分类选择全部，具体可以写什么请见JmMagicConstants
    order_by=JmMagicConstants.ORDER_BY_VIEW,  # 按照观看数排序，具体可以写什么请见JmMagicConstants
)

# 月排行，底层实现也是调的categories_filter
page: JmCategoryPage = cl.month_ranking(1)
# 周排行
page: JmCategoryPage = cl.week_ranking(1)

# 循环获取分页，使用 cl.categories_filter_gen
# 基础用法：简单的 for 循环
for page in cl.categories_filter_gen(page=1, # 起始页码
                                     # 下面是分类参数
                                     time=JmMagicConstants.TIME_WEEK,
                                     category=JmMagicConstants.CATEGORY_ALL,
                                     order_by=JmMagicConstants.ORDER_BY_VIEW,
                                     ):
    for aid, atitle in page:
        print(aid, atitle)

# 高级用法：使用 generator 的 send() 方法在遍历中途动态修改查询条件
# 注意：必须用 while 循环手动接收 send() 的返回值，避免在 for 循环内调用 send() 跳过分页
generator = cl.categories_filter_gen(page=1, time=JmMagicConstants.TIME_WEEK)
try:
    page = next(generator)  # 预先启动生成器
    while True:
        # 打印第一页
        for aid, atitle in page:
            print(aid, atitle)
        
        # 假设我们只想看前一页，下一页想换一个排序方式
        # 调用 send 传入包含新参数的 dict 即可覆盖原来的查询条件
        page = generator.send({"order_by": JmMagicConstants.ORDER_BY_LATEST})
except StopIteration:
    pass

```

## 高级搜索（分类/副分类）

禁漫网页端的搜索除了常规条件，还支持【分类】和【副分类】的搜索。

在任一搜索页面，你会看到本子图的右上方有两个标签。左边的是【分类】，右边的是【副分类】。

下面演示代码如何编写。

* **注意！！禁漫移动端没有提供如下功能，以下代码仅对网页端生效。**

```python
# 在编写代码前，建议先熟悉禁漫网页的搜本功能，下面的代码都是对照网页编写的。
# 网页搜索示例：https://18comic.vip/search/photos/doujin/sub/CG?main_tag=0&search_query=mana&page=1&o=mr&t=a

from jmcomic import *

op = create_option_by_file('op.yml')
# 创建网页端client
html_cl = op.new_jm_client(impl='html')

# 使用站内搜索，指定【分类】和【副分类】
# 分类 = JmMagicConstants.CATEGORY_DOUJIN = 同人本
# 副分类 = JmMagicConstants.SUB_DOUJIN_CG = CG本
# 实际URL：https://18comic.vip/search/photos/doujin/sub/CG?main_tag=0&search_query=mana&page=1&o=mr&t=a
page = html_cl.search_site(search_query='mana',
                           category=JmMagicConstants.CATEGORY_DOUJIN,
                           sub_category=JmMagicConstants.SUB_DOUJIN_CG,
                           page=1,
                           )
# 打印page内容
for aid, atitle in page.iter_id_title():
    print(aid, atitle)

# 循环获取分页
for page in html_cl.search_gen(search_query='mana',
                               category=JmMagicConstants.CATEGORY_DOUJIN,
                               sub_category=JmMagicConstants.SUB_DOUJIN_CG,
                               page=1,  # 起始页码
                               ):
    # 打印page内容
    for aid, atitle in page.iter_id_title():
        print(aid, atitle)

# 高级用法：使用 generator 的 send() 方法进行手动翻页或修改查询条件
generator = html_cl.search_gen('mana')
try:
    page = next(generator)
    while True:
        for aid, atitle in page.iter_id_title():
            print(aid, atitle)
        
        # 可直接动态传参改变搜索条件，例如下一页换成搜索 'nana'
        page = generator.send({"search_query": 'nana'})
except StopIteration:
    pass
```


## 手动创建Client

```python
# 默认的使用方式是先创建option，option封装了所有配置，然后由option.new_jm_client() 创建客户端client，使用client可以访问禁漫接口

# 下面演示直接构造client的方式
from jmcomic import *

"""
创建JM客户端

:param postman: 负责实现HTTP请求的对象，持有cookies、headers、proxies等信息
:param domain_list: 禁漫域名
:param retry_times: 重试次数
"""

# 网页端
cl = JmHtmlClient(
    postman=JmModuleConfig.new_postman(),
    domain_list=['18comic.vip'],
    retry_times=1
)

# API端（APP）
cl = JmApiClient(
    postman=JmModuleConfig.new_postman(),
    domain_list=JmModuleConfig.DOMAIN_API_LIST,
    retry_times=1
)
```


## 下载返回值

`download_album` 和 `download_photo` 下载完成后，单个 ID 返回 `DownloadResult`，多个 ID 返回 `BatchResult`。

从 `result.detail` 可以取得下载的本子/章节的实体类：

```python
from jmcomic import download_album, download_photo

# 下载本子；result.detail 是本子实体
result = download_album('123')
album = result.detail
print(f'本子实体: {album}')

# 下载章节；result.detail 是章节实体
result = download_photo('456')
photo = result.detail
print(f'章节实体: {photo}')
```

### 获取保存路径和耗时

下载完成后，你通常会关心两件事：文件保存在哪里，以及哪一步比较慢。下表介绍获取方法。

| 对象 | `save_path` | `duration`（单位-秒）                                |
| --- | --- |------------------------------------------------------|
| 下载结果 `result` | 通过 `result.detail.save_path` 查看 | 从调用下载方法到返回，你总共等了多久                 |
| 本子 `album` | 本子根目录 | 下载这个本子花了多久。包含获取详情、下载章节和插件   |
| 章节 `photo` | 章节图片目录 | 下载这个章节花了多久。包含获取详情、下载图片和插件   |
| 图片 `image` | 图片文件路径 | 下载这张图片花了多久。包含检查缓存、下载、保存和插件 |

> [!NOTE]
> 一次本子下载可能同时处理多个章节，一个章节也可能同时处理多张图片。因此，把所有章节或图片的耗时相加，不会得到本子的耗时，这是正常现象。


<details markdown="1">
<summary>完整示例：查看路径、耗时和缓存状态</summary>

```python
from jmcomic import download_album

result = download_album('123')
album = result.detail

# result.duration 是调用下载方法后总共等待的时间
print(f'本子目录: {album.save_path}，总共等待: {result.duration:.2f} 秒')
print(f'下载本子用了: {album.duration:.2f} 秒')

for photo in album:
    # 查看每个章节的保存目录和处理耗时
    print(f'章节 {photo.id} 目录: {photo.save_path}，耗时: {photo.duration:.2f} 秒')

    for image in photo:
        # exists 和 cache 都为 True，表示满足缓存复用条件
        not_download = image.exists and image.cache
        print(
            f'图片 {image.filename} 路径: {image.save_path}，'
            f'耗时: {image.duration:.2f} 秒，是否因存在而跳过下载: {not_download}'
        )
```

`not_download` 为 `True`，表示目标图片原本存在并且允许使用缓存。

</details>

### 使用 `manifest` 获取结果文件

相比于遍历实体类， `manifest` 提供了更直接的写法，适合场景：直接取得全部图片路径，以及取得**额外产物**（由插件/Feature产出的 PDF、ZIP、长图）

| 想要什么                                   | 推荐写法 |
|--------------------------------------------| --- |
| 查看某张图片的路径、耗时和缓存状态         | 遍历实体，读取 `image.save_path` 等字段 |
| 直接获取所有图片路径（包含命中缓存的图片） | 用`manifest`，`result.manifest.image_filepath_list` |
| 额外产物（PDF、ZIP 或长图）                | 用`manifest`，`result.manifest.get_export_filepath_list('文件后缀')` |

<details markdown="1">
<summary>完整示例：获取图片和导出文件</summary>

```python
from jmcomic import Feature, download_album

# 下载本子，并使用内置 Feature 导出 PDF、ZIP 和长图
result = download_album(
    '123',
    extra=Feature.export_pdf + Feature.export_zip + Feature.export_long_img,
)

# 本次成功下载或直接复用的图片路径
print('图片文件:', result.manifest.image_filepath_list)

# 插件导出的文件按后缀查询，后缀前面的点可以省略
pdf_filepath_list = result.manifest.get_export_filepath_list('pdf')
zip_filepath_list = result.manifest.get_export_filepath_list('.zip')
png_filepath_list = result.manifest.get_export_filepath_list('png')

print('PDF 文件:', pdf_filepath_list)
print('ZIP 文件:', zip_filepath_list)
print('长图导出文件:', png_filepath_list)
```

</details>

### 批量下载的返回值

传入多个 ID 时，返回值是 `BatchResult`。每一项成功下载对应一个 `DownloadResult`，失败任务则记录在 `failed` 中：

<details markdown="1">
<summary>完整示例：处理批量下载结果</summary>

```python
from jmcomic import download_album

# 同时下载多个本子
batch_result = download_album(['123', '456', '789'])

# BatchResult 继承 set，成功结果没有输入顺序保证
for result in batch_result:
    album = result.detail
    # 通过实体 ID 识别当前结果，不要用遍历位置对应输入列表
    print(f'JM{album.id} 下载到: {album.save_path}')

# failed 的键是下载失败的 ID，值是记录失败原因的异常对象
for album_id, error in batch_result.failed.items():
    print(f'JM{album_id} 下载失败: {error}')

# total 是实际处理的不同 ID 数量，重复 ID 不会重复下载
print('任务总数:', batch_result.total)
print('是否全部成功:', batch_result.all_succeeded)
```

</details>

下载单个 ID 时，请求本子失败会直接抛出异常；如果只有部分章节或图片失败，会在任务结束后汇总抛出 `PartialDownloadFailedException`，此时不会返回 `DownloadResult`。批量下载则继续执行其他任务，并把失败项集中放进 `batch_result.failed`。

### 速查表

| 你的需求 | 推荐写法 |
| --- | --- |
| 查看本子或章节信息 | `result.detail` |
| 查看本子或章节目录 | `result.detail.save_path` |
| 查看单张图片路径和状态 | 遍历实体后读取 `image.save_path` 等字段 |
| 查看图片或章节失败原因 | 捕获 `PartialDownloadFailedException` 后，读取 `e.downloader.download_failed_image` / `download_failed_photo`；列表元素为 `(实体, 异常)` |
| 获取本次成功图片路径列表 | `result.manifest.image_filepath_list` |
| 获取已登记的导出文件路径 | `result.manifest.get_export_filepath_list('后缀')` |
| 查看单个 ID 下载的完整时间 | `result.duration` |
| 定位本子、章节或图片的内部处理慢点 | 对应实体的 `duration` |
| 检查批量下载失败项 | `batch_result.failed` |

<details markdown="1">
<summary>兼容旧版本的返回值解包写法</summary>

旧代码可能会把返回值直接解包成两个变量，这种写法仍然可以继续使用：

```python
from jmcomic import download_album

result = download_album('123')

# 旧写法：第一个变量是本子实体，第二个变量是下载器
album, downloader = result

# 新代码更推荐直接通过 result.detail 读取本子实体
assert album is result.detail
```

</details>
