# Option File Syntax

## 1. 配置前需知

* option有`默认值`，当你使用配置文件来创建option时，你配置文件中的值会覆盖`默认值`。

  因此，在配置option时，不需要配置全部的值，只需要配置特定部分即可。

* 你可以使用下面的代码来得到option的默认值，你可以删除其中的大部分配置项，只保留你要覆盖的配置项

```python
from jmcomic import JmOption
JmOption.default().to_file('./option.yml') # 创建默认option，导出为option.yml文件
```

## 2. option常用配置项

```yml
# 配置客户端相关
client:
  # impl: 客户端实现类，不配默认是html，表示网页端
  impl: html

  # domain: 域名配置，默认是 []，表示运行时自动获取域名。
  # 可配置特定域名，如下：
  # 程序会先用第一个域名，如果第一个域名重试n次失败，则换下一个域名重试，以此类推。
  domain:
    - jm-comic.org
    - jm-comic2.cc
    - 18comic.vip
    - 18comic.org

  postman:
    meta_data:
      # proxies: 代理配置，默认是 system，表示使用系统代理。
      # 以下的写法都可以:
      # proxies: null # 不使用代理
      # proxies: clash
      # proxies: v2ray
      # proxies: 127.0.0.1:7890
      # proxies:
      #   http: 127.0.0.1:7890
      #   https: 127.0.0.1:7890
      proxies: system

      # cookies: 帐号配置，默认是 null，表示未登录状态访问JM。
      # 禁漫的大部分本子，下载是不需要登录的；少部分敏感题材需要登录才能看。
      # 如果你希望以登录状态下载本子，最简单的方式是配置一下浏览器的cookies，
      # 不用全部cookies，只要那个叫 AVS 就行。
      # 特别注意！！！(https://github.com/hect0x7/JMComic-Crawler-Python/issues/104)
      # cookies是区分域名的：
      # 假如你要访问的是 `18comic.vip`，那么你配置的cookies也要来自于 `18comic.vip`，不能配置来自于 `jm-comic.club` 的cookies。
      # 如果你发现配置了cookies还是没有效果，大概率就是你配置的cookies和代码访问的域名不一致。
      cookies:
        AVS: qkwehjjasdowqeq # 这个值是乱打的，不能用

# 下载配置
download:
  cache: true # 如果要下载的文件在磁盘上已存在，不用再下一遍了吧？默认为true
  image:
    decode: true # JM的原图是混淆过的，要不要还原？默认为true
    suffix: .jpg # 把图片都转为.jpg格式，默认为null，表示不转换。
  threading:
    # image: 同时下载的图片数，默认是30张图
    # 数值大，下得快，配置要求高，对禁漫压力大
    # 数值小，下得慢，配置要求低，对禁漫压力小
    # PS: 禁漫网页一次最多请求50张图
    image: 30
    # photo: 同时下载的章节数，不配置默认是cpu的线程数。例如8核16线程的cpu → 16.
    photo: 16



# 文件夹规则配置，决定图片文件存放在你的电脑上的哪个文件夹
dir_rule:
  # base_dir: 根目录。
  base_dir: D:/a/b/c/

  # rule: 规则dsl。
  # 本项只建议了解编程的朋友定制，实现在这个类: jmcomic.jm_option.DirRule
  # 写法:
  # 1. 以'Bd'开头，表示根目录
  # 2. 文件夹每增加一层，使用'_'区隔
  # 3. 文件夹名字表示为 Pxxx/Ayyy，意思是 JmPhotoDetail.xxx / JmAlbumDetail的.yyy。xxx和yyy可以写什么需要看源码。
  # 下面是示例，表示使用禁漫网站的默认下载方式 [根目录 / 本子id / 章节序号 / 图片文件]
  # rule: Bd_Aid_Pindex

  # 默认规则是: 根目录 / 章节标题 / 图片文件
  rule: Bd_Ptitle
```


## 3. option插件配置项
```yml
# 插件的配置示例
# 当kwargs的值为字符串类型时，支持使用环境变量，语法为 ${环境变量名}
plugins:
  after_init:
    - plugin: usage_log # 实时打印硬件占用率的插件
      kwargs:
        interval: 0.5 # 间隔时间
        enable_warning: true # 占用过大时发出预警

    - plugin: login # 登录插件
      kwargs:
        username: un # 用户名
        password: pw # 密码

    - plugin: find_update # 只下载新章插件
      kwargs:
        145504: 290266 # 下载本子145504的章节290266以后的新章
        
    - plugin: image_suffix_filter # 图片后缀过滤器插件，可以控制只下载哪些后缀的图片
      kwargs:
        allowed_orig_suffix: # 后缀列表，表示只想下载以.gif结尾的图片
          - .gif 

    - plugin: client_proxy # 客户端实现类代理插件，不建议非开发人员使用
      kwargs:
        proxy_client_key: cl_proxy_future # 代理类的client_key
        whitelist: [ api, ] # 白名单，当client.impl匹配白名单时才代理

    - plugin: auto_set_browser_cookies # 自动获取浏览器cookies，详见插件类
      kwargs:
        browser: chrome
        domain: 18comic.vip

  after_album:
    - plugin: zip # 压缩文件插件
      kwargs:
        level: photo # 按照章节，一个章节一个压缩文件
        filename_rule: Ptitle # 压缩文件的命名规则
        zip_dir: D:/jmcomic/zip/ # 压缩文件存放的文件夹
        delete_original_file: true # 压缩成功后，删除所有原文件和文件夹

    - plugin: send_qq_email # 发送qq邮件插件
      kwargs:
        msg_from: ${EMAIL} # 发件人
        msg_to: aaa@qq.com # 收件人
        password: dkjlakdjlkas # 发件人的授权码
        title: jmcomic # 标题
        content: jmcomic finished !!! # 内容

```