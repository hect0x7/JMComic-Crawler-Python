# jmcomic 常用类和方法演示

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

```python
from jmcomic import *

# 1. 创建option对象，推荐使用配置文件的方式
# 你可以配置很多东西，比如代理、cookies、下载规则等等
# 配置文件的语法参考: https://jmcomic.readthedocs.io/en/latest/option_file_syntax/
option = create_option_by_file('op.yml')  # 通过配置文件来创建option对象

# 2. 调用下载api，把option作为参数传递 
download_album(123, option)
# 也可以使用下面这种面向对象的方式，是一样的
option.download_album(123)
```

## 获取实体类

```python
from jmcomic import *

# 客户端
client = JmOption.default().new_jm_client()

# 本子实体类
album: JmAlbumDetail = client.get_album_detail('427413')


def fetch(photo: JmPhotoDetail):
    # 章节实体类
    photo = client.get_photo_detail(photo.photo_id, False)

    # 图片实体类
    image: JmImageDetail
    for image in photo:
        print(image.img_url)

# 多线程发起请求
multi_thread_launcher(
    iter_objs=album,
    apply_each_obj_func=fetch
)
```

## 搜索本子

```python
from jmcomic import *

client = JmOption.default().new_jm_client()

# 分页查询，search_site就是禁漫网页上的【站内搜索】
page: JmSearchPage = client.search_site(search_query='+MANA +无修正', page=1)
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
