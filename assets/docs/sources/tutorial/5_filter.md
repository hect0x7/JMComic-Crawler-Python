# Filter - 下载过滤器

filter(过滤器)是v2.1.12新引入的机制，
利用filter，你可以实现下载时过滤本子/章节/图片，完全控制你要下载的内容。

使用filter的步骤如下：

```
1. 自定义class，继承JmDownloader，重写do_filter方法，即:
   class MyDownloader(JmDownloader):
       def do_filter(self, detail):
           # 如何重写？参考JmDownloader.do_filter和下面的示例
           ...

2. 让你的class生效，使用如下代码：
   JmModuleConfig.CLASS_DOWNLOADER = MyDownloader

3. 照常使用下载api:
   download_album(xxx, option)
```

* 下面的示例只演示步骤1



## 示例1：只下载章节的前三张图

```python
from jmcomic import *

class First3ImageDownloader(JmDownloader):

    def do_filter(self, detail):
        if detail.is_photo():
            photo: JmPhotoDetail = detail
            # 支持[start,end,step]
            return photo[:3]

        return detail
```



## 示例2：只下载本子的特定章节以后的章节

```python
from jmcomic import *

# 参考：https://github.com/hect0x7/JMComic-Crawler-Python/issues/95
class FindUpdateDownloader(JmDownloader):
    album_after_photo = {
        'xxx': 'yyy'
    }

    def do_filter(self, detail):
        if not detail.is_album():
            return detail

        return self.find_update(detail)

    # 带入漫画id, 章节id(第x章)，寻找该漫画下第x章节後的所有章节Id
    def find_update(self, album: JmAlbumDetail):
        if album.album_id not in self.album_after_photo:
            return album

        photo_ls = []
        photo_begin = self.album_after_photo[album.album_id]
        is_new_photo = False

        for photo in album:
            if is_new_photo:
                photo_ls.append(photo)

            if photo.photo_id == photo_begin:
                is_new_photo = True

        return photo_ls
```