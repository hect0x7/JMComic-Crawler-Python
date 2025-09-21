# 配置文件指南

## 1. 配置前需知

* option有`默认值`，你配置文件中的配置项会覆盖`默认值`。因此你只需要添加感兴趣的配置项即可。

* 你也可以使用下面的代码来得到option的默认值。你可以删除其中的大部分配置项，只保留你要覆盖的配置项。

```python
from jmcomic import JmOption
JmOption.default().to_file('./option.yml') # 创建默认option，导出为option.yml文件
```

## 2. option常规配置项

```yaml
# 开启jmcomic的日志输出，默认为true
# 对日志有需求的可进一步参考文档 → https://jmcomic.readthedocs.io/en/latest/tutorial/11_log_custom/
log: true

# 配置客户端相关
client:
  # impl: 客户端实现类，不配置默认会使用JmModuleConfig.DEFAULT_CLIENT_IMPL
  # 可配置:
  #  html - 表示网页端
  #  api - 表示APP端
  # APP端不限ip兼容性好，网页端限制ip地区但效率高
  impl: html

  # domain: 禁漫域名配置，一般无需配置，jmcomic会根据上面的impl自动设置相应域名
  # 该配置项需要和上面的impl结合使用，因为禁漫网页端和APP端使用的是不同域名，
  # 所以配置是一个dict结构，key是impl的值，value是域名列表，表示这个impl走这些域名。
  # 域名列表的使用顺序是：先用第一个域名，如果第一个域名重试n次失败，则换下一个域名重试，以此类推。
  # 下面是示例：（注意下面这些域名可能会过时，不一定能用）
  domain:
    html:
      - 18comic.vip
      - 18comic.org
    api:
      - www.jmapiproxyxxx.vip

  # retry_times: 请求失败重试次数，默认为5
  retry_times: 5

  # postman: 请求配置
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
  # 此配置也支持引用环境变量，例如
  # base_dir: ${JM_DIR}/下载文件夹/
  base_dir: D:/a/b/c/

  # rule: 规则dsl。
  # 本项只建议了解编程的朋友定制，实现在这个类: jmcomic.jm_option.DirRule
  # 写法:
  # 1. 以'Bd'开头，表示根目录
  # 2. 文件夹每增加一层，使用 '_' 或者 '/' 区隔
  # 3. 用Pxxx或者Ayyy指代文件夹名，意思是 JmPhotoDetail.xxx / JmAlbumDetail的.yyy。
  # xxx和yyy可以写什么需要看源码，或通过下面代码打印出所有可用的值
  # 
  # ```python
  # import jmcomic
  # properties: dict = jmcomic.JmOption.default().new_jm_client().get_album_detail(本子id).get_properties_dict()
  # print(properties)
  # ```
  # 
  # 下面演示如果要使用禁漫网站的默认下载方式，该怎么写:
  # 规则: 根目录 / 本子id / 章节序号 / 图片文件
  # rule: 'Bd  / Aid   / Pindex'
  # rule: 'Bd_Aid_Pindex'
  # 默认规则是: 根目录 / 章节标题 / 图片文件
  rule: Bd / Ptitle
  # jmcomic v2.5.36 以后，支持使用python的f-string的语法组合文件夹名，下为示例
  # rule: Bd / Aauthor / (JM{Aid}-{Pindex})-{Pname}
  # {}大括号里的内容同样是写 Axxx 或 Pxxx，其他语法自行参考python f-string的语法
  # 另外，rule开头的Bd可忽略不写，因为程序会自动插入Bd
```

## 3. option插件配置项

* **插件配置中的kwargs参数支持引用环境变量，语法为 ${环境变量名}**

```yaml
# 插件的配置示例
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
    - plugin: replace_path_string # 字符串替换插件，直接对下载文件夹的路径进行文本替换
      kwargs:
        replace: 
          # {左边写你要替换的原文}: {右边写替换成什么文本}
          aaa: bbb
          kyockcho: きょくちょ
          
    - plugin: client_proxy # 客户端实现类代理插件，不建议非开发人员使用
      kwargs:
        proxy_client_key: photo_concurrent_fetcher_proxy # 代理类的client_key
        whitelist: [ api, ] # 白名单，当client.impl匹配白名单时才代理

    - plugin: auto_set_browser_cookies # 自动获取浏览器cookies，详见插件类代码→AutoSetBrowserCookiesPlugin
      kwargs:
        browser: chrome
        domain: 18comic.vip
    
    # v2.5.0 引入的插件
    # 可以启动一个服务器，可以在浏览器上查看本子
    # 基于flask框架，需要安装额外库: [pip install plugin_jm_server]
    # 源码：https://github.com/hect0x7/plugin-jm-server
    - plugin: jm_server 
      kwargs:
        password: '3333' # 服务器访问密码
        base_dir: D:/a/b/c/ # 根目录，默认使用dir_rule.base_dir
        
        # 下面是高级配置，不配置也可以
        
        # run下的参数是flask框架的app对象的run方法参数，详见flask文档
        run:
          host: 0.0.0.0 # 默认接收所有ip的请求
          port: 80 # 服务器端口，默认为80
          debug: false # 是否开启debug模式，默认为false
          
        # 支持重写背景图片，可以使用你喜欢的背景图片作为背景
        img_overwrite:
          bg.jpg: D:/浏览器的背景图
          m_bg.jpeg: D:/移动设备浏览器的背景图

    - plugin: subscribe_album_update # 自动订阅本子并下载、发送邮件通知的插件
      kwargs:
        download_if_has_update: true
        email_notify: # 参数说明见下【发送qq邮件插件】
          msg_from: aaa@qq.com
          msg_to: aaa@qq.com
          password: dkjlakdjlkas
          title: album update !!!
          content: album update !!!
        album_photo_dict:
          324930: 424507

  before_album:
    - plugin: download_cover # 额外下载本子封面的插件
      kwargs:
        size: '_3x4' # 可选项，禁漫搜索页的封面图尺寸是 4x3，和详情页不一样，想下搜索页的封面就设置此项
        dir_rule: # 封面图存放路径规则，写法同上
          base_dir: D:/a/b/c/
          rule: '{Atitle}/{Aid}_cover.jpg'
    

  after_album:
    - plugin: zip # 压缩文件插件
      kwargs:
        level: photo # 按照章节，一个章节一个压缩文件
        # level 也可以配成 album，表示一个本子对应一个压缩文件，该压缩文件会包含这个本子的所有章节

        filename_rule: Ptitle # 压缩文件的命名规则
        # 请注意⚠ [https://github.com/hect0x7/JMComic-Crawler-Python/issues/223#issuecomment-2045227527]
        # filename_rule和level有对应关系
        # 如果level=[photo], filename_rule只能写Pxxx
        # 如果level=[album], filename_rule只能写Axxx

        zip_dir: D:/jmcomic/zip/ # 压缩文件存放的文件夹

        suffix: zip #压缩包后缀名，默认值为zip，可以指定为zip或者7z

        # v2.6.0 以后，zip插件也支持dir_rule配置项，可以替代旧版本的zip_dir和filename_rule
        # 请注意⚠ 使用此配置项会使filename_rule，zip_dir，suffix三个配置项无效，与这三个配置项同时存在时仅会使用dir_rule
        # 示例如下:
        # dir_rule: # 新配置项，可取代旧的zip_dir和filename_rule
        #   base_dir: D:/jmcomic-zip
        #   rule: 'Bd / {Atitle} / [{Pid}]-{Ptitle}.zip'  # 设置压缩文件夹规则，中间Atitle表示创建一层文件夹，名称是本子标题。[{Pid}]-{Ptitle}.zip 表示压缩文件的命名规则(需显式写出后缀名)
        # 使用此方法指定压缩包存储路径则无需和level对应

        delete_original_file: true # 压缩成功后，删除所有原文件和文件夹
        
        # 在v2.6.0及以后版本，zip插件还支持设置密码和加密方式，使用encrypt配置项，该配置是可选的，示例如下：
        # 1. 给压缩包设置一个指定密码
        # encrypt:
        #   password: 123456
        # 2. 设置随机生成的密码。该密码会在日志中打印出来，并附着到zip的压缩文件注释里
        # encrypt:
        #   type: random
        # 配置密码时，type和password二选一必填
        
        # 插件还支持使用7z加密，这种方式会加密压缩包文件头，只有输入了密码才能查看压缩包文件列表，隐私性最好。
        # 使用encrypt.impl配置项开启7z格式加密，如果不配置，默认仍使用zip格式。
        # 使用7z格式时记得把压缩包后缀名指定为7z。
        # 示例如下:
        # suffix: 7z
        # encrypt:
        #   impl: 7z
        #   type: random # type和password二选一必填，和上面一样
        # 需要提醒的是，7z没有压缩文件注释，因此如果设置随机密码，密码就只会存在于日志中，请注意及时保存密码。
         
    
    # 删除重复文件插件
    # 参考 → [https://github.com/hect0x7/JMComic-Crawler-Python/issues/244]
    - plugin: delete_duplicated_files
      kwargs:
        # limit: 必填，表示对md5出现次数的限制
        limit: 3
        # 如果文件的md5的出现次数 >= limit，是否要删除
        # 如果delete_original_file不配置，此插件只会打印信息，不会执行其他操作
        # 如果limit=1, delete_original_file=true 效果会是删除所有文件 
        delete_original_file: true

    - plugin: send_qq_email # 发送qq邮件插件
      kwargs:
        msg_from: ${EMAIL} # 发件人
        msg_to: aaa@qq.com # 收件人
        password: dkjlakdjlkas # 发件人的授权码
        title: jmcomic # 标题
        content: jmcomic finished !!! # 内容

  main:
    - plugin: favorite_folder_export # 导出收藏夹插件
      log: false
      kwargs:
        zip_enable: true # 对导出文件进行压缩
        zip_filepath: ${JM_DOWNLOAD_DIR}/export.zip # 压缩文件路径
        zip_password: ${ZIP_PASSWORD} # 压缩密码
  
  before_photo:
    - plugin: skip_photo_with_few_images # 跳过下载章节图片数量过少的章节。一些韩漫的章节是公告，没有实际内容，就可以用该插件来跳过下载这些章节。
      kwargs:
        at_least_image_count: 3 # 至少要有多少张图，才下载此章节

  after_photo:
    # 把章节的所有图片合并为一个pdf的插件
    # 使用前需要安装依赖库: [pip install img2pdf]
    - plugin: img2pdf
      kwargs:
        pdf_dir: D:/pdf/ # pdf存放文件夹
        filename_rule: Pid # pdf命名规则，P代表photo, id代表使用photo.id也就是章节id
        encrypt: # pdf密码，可选配置项
          password: 123 # 密码
  
    # img2pdf也支持合并整个本子，把上方的after_photo改为after_album即可。
    # https://github.com/hect0x7/JMComic-Crawler-Python/discussions/258
    # 配置到after_album时，需要修改filename_rule参数，不能写Pxx只能写Axx示例如下
    - plugin: img2pdf
      kwargs:
        pdf_dir: D:/pdf/ # pdf存放文件夹
        filename_rule: Aname # pdf命名规则，A代表album, name代表使用album.name也就是本子名称
  
    # 插件来源：https://github.com/hect0x7/JMComic-Crawler-Python/pull/294
    # long_img插件是把所有图片合并为一个png长图，效果和img2pdf类似
    - plugin: long_img
      kwargs:
        img_dir: D:/pdf/ # 长图存放文件夹
        filename_rule: Aname # 长图命名规则，同上
  
```
