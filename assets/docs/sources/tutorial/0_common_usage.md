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
# 配置文件的语法参考: https://jmcomic.readthedocs.io/en/latest/option_file_syntax/
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
# 该参数主要用于主动检查部分下载失败的情况，
# 因为非当前线程抛出的异常（比如下载章节的线程和下载图片的线程），这些线程如果抛出异常，
# 当前线程是感知不到的，try-catch下载方法download_album不能捕获到其他线程发生的异常。
try:
    album, downloader = download_album(123, check_exception=True)
except PartialDownloadFailedException as e:
    downloader: JmDownloader = e.downloader
    print(f'下载出现部分失败, 下载失败的章节: {downloader.download_failed_photo}, 下载失败的图片: {downloader.download_failed_image}')
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

## 获取收藏夹

可参考discussions: https://github.com/hect0x7/JMComic-Crawler-Python/discussions/235

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
for page in cl.categories_filter_gen(page=1, # 起始页码
                                     # 下面是分类参数
                                     time=JmMagicConstants.TIME_WEEK,
                                     category=JmMagicConstants.CATEGORY_ALL,
                                     order_by=JmMagicConstants.ORDER_BY_VIEW,
                                     ):
    for aid, atitle in page:
        print(aid, atitle)

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
