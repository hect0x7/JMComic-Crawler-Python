# 自定义下载文件夹名

## 0. 最简单直接粗暴有效的方式

使用插件`replace_path_string`：

这个插件可以直接替换下载文件夹路径，配置示例如下（把如下配置放入option配置文件即可）：

```yml
plugins:
  after_init:
    - plugin: replace_path_string
      kwargs:
        replace: 
          # {左边写你要替换的原文}: {右边写替换成什么文本}
          kyockcho: きょくちょ
```
该示例会把文件夹路径中所有`kyockcho`都变为`きょくちょ`，例如：

`D:/a/[kyockcho]本子名称 - kyockcho/` 改为↓

`D:/a/[きょくちょ]本子名称 - きょくちょ/` 

---------------
**_如果上述简单的文本替换无法满足你，或者你需要更多上下文写逻辑代码，那么下面的内容正适合你阅读。_**

## 1. DirRule机制简介


当你使用download_album下载本子时，本子会以一定的路径规则（DirRule）下载到你的磁盘上。

你可以使用配置文件定制DirRule，例如下面的例子：

```yaml
dir_rule:
  # 设定根目录 base_dir
  base_dir: D:/a/b/c/
  rule: Bd / Ptitle # P表示章节，title表示使用章节的title字段
  # 这个规则的含义是，把图片下载到路径 {base_dir}/{Ptitle}/ 下
  # 即：根目录 / 章节标题 / 图片文件
```

例如，假设一个章节的名称（Ptitle）是ddd，则最后的下载文件夹结构为 `D:/a/b/c/ddd/`：

```
D:/a/b/c/ddd/00001.webp
D:/a/b/c/ddd/00002.webp
D:/a/b/c/ddd/00003.webp
...
```

上述的Ptitle，P表示章节，title表示使用章节的title字段。

除了title，你还可以写什么？其实Ptitle表示的是jmcomic里的章节实体类 JmPhotoDetail 的属性。

最终能写什么，取决于JmPhotoDetail有哪些属性，建议使用IDE来获知这些属性，不过这需要你懂一些python基础。

除了Pxxx，你还可以写Axxx，表示这个章节所在的本子的属性xxx，详见本子实体类 JmAlbumDetail。


## 2. 自定义字段名

上述例子使用了title字段，如果你想自定义一个字段，然后在DirRule中使用自定义字段，该怎么做？

基于v2.4.6，你可以使用如下方式



1. 给你的自定义字段取个名

```yaml
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

```yaml
# 直接使用内置字段 indextitle 即可
dir_rule:
  rule: Bd_Pindextitle
```



