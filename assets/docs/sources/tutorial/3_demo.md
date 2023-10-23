# 使用jmcomic实现简单功能

## 下载本子

```python
from jmcomic import *

ls = str_to_list('''
438696
https://18comic.vip/album/497896/
''')

download_album(ls)
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