# 综合使用实例

* 基于v2.2.2+内置插件

## 功能需求

1. 下载id为145504的本子；
2. 只下载章节在290266之后的新章；
3. 最后要把图片转为jpg格式；
4. 要使用登录状态去下载；
5. 压缩文件，按照章节压缩，一个章节一个压缩文件，压缩文件的命名: 章节标题.zip；
6. 自动把下载的文件全部删除，最后只要保留压缩文件。

## 实现方案

#### 1. 写2行python代码
```python
from jmcomic import create_option
create_option('myoption.yml')
```

#### 2. 配置option，调用1的脚本即可
```yaml
dir_rule: # 下载路径规则
  rule: Bd_Aid
  base_dir: D:/jmcomic

download:
  image:
    suffix: .jpg # 转为jpg格式的图片

client:
  domain:
    - 18comic.vip # 指定域名

plugins:
  after_init:
    - plugin: login # 登录插件
      kwargs:
        username: un
        password: pw

    - plugin: find_update # 只下载新章插件
      kwargs:
        145504: 290266 # 下载本子145504的章节290266以后的新章

  after_album:
    - plugin: zip # 压缩文件插件
      kwargs:
        level: photo # 按照章节，一个章节一个压缩文件
        filename_rule: Ptitle # 压缩文件的命名规则
        zip_dir: D:/jmcomic # 压缩文件存放的文件夹
        delete_original_file: true # 压缩成功后，删除所有原文件和文件夹
```
