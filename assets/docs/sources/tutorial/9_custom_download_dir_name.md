# 自定义下载文件夹名



## 1. DirRule简介

当你使用download_album下载本子时，本子会以一定的路径规则（DirRule）下载到你的磁盘上。

你可以使用配置文件定制DirRule，例如下面的例子

```yml
dir_rule:
  base_dir: D:/a/b/c/
  # 规则含义: 根目录 / 章节标题 / 图片文件
  rule: Bd_Ptitle # P表示章节，title表示使用章节的title字段
```

如果一个章节的名称（title）是ddd，则最后的下载文件夹结构为：

```
D:/a/b/c/ddd/00001.webp
D:/a/b/c/ddd/00002.webp
D:/a/b/c/ddd/00003.webp
...
```



## 2. 自定义字段名

上述例子使用了title字段，如果你想自定义一个字段，然后在DirRule中使用自定义字段，该怎么做？

基于v2.4.6，你可以使用如下方式



1. 给你的自定义字段取个名

```yml
dir_rule: # 忽略base_dir配置项
  rule: Bd_Amyname # A表示本子，myname表示本子的一个自定义字段
```



2. 在代码中，加入你自定义字段的处理函数

```python
from jmcomic import JmModuleConfig
# 你需要写一个函数，把字段名作为key，函数作为value，加到JmModuleConfig.AFIELD_ADVICE这个字典中
JmModuleConfig.AFIELD_ADVICE['myname'] = lambda album: f'[{album.id}] {album.title}'
```



这样一来，Amyname这个规则就会交由你的函数进行处理，你便可以返回一个自定义的文件夹名





## 3. 更多的使用例子



### 完全使用自己的文件夹名

```python
from jmcomic import JmModuleConfig

dic = {
    '248965': '社团学姐（爆赞韩漫）'
}

# Amyname
JmModuleConfig.AFIELD_ADVICE['myname'] = lambda album: dic[album.id]
download_album(248965)
```



### 文件夹名=作者+标题

```python
from jmcomic import JmModuleConfig
# Amyname
JmModuleConfig.AFIELD_ADVICE['myname'] = lambda album: f'【{album.author}】{album.title}'
# album有一个内置字段 authoroname，效果类似
```



### 文件夹名=禁漫车号+标题

```python
from jmcomic import JmModuleConfig
# Pmyname
JmModuleConfig.PFIELD_ADVICE['myname'] = lambda photo: f'【{photo.id}】{photo.title}'
```



### 文件夹名=第x话+标题

```yml
# 直接使用内置字段 indextitle 即可
dir_rule:
  rule: Bd_Pindextitle
```



