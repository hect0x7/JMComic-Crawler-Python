"""
jmcomic综合使用实例，基于v2.2.2+内置插件

功能需求：
1. 下载id为145504的本子；
2. 只下载章节在290266之后的新章；
3. 最后要把图片转为jpg格式；
4. 要使用登录状态去下载；
5. 压缩文件，按照章节压缩，一个章节一个压缩文件，压缩文件的命名: 章节标题.zip；
6. 自动把下载的文件全部删除，最后只要保留压缩文件。


实现方案：
1. 写2行python代码
2. 配置option，调用1的脚本即可

"""

# 1. 写2行python代码
from jmcomic import create_option
create_option('myoption.yml')

# 2. 配置option，调用1的脚本即可
"""
dir_rule: # 下载路径规则
  rule: Bd_Aid
  base_dir: D:/jmcomic

download:
  image:
    suffix: .jpg # 转为jpg格式的图片

client:
  domain:
    - 18comic.vip # 指定域名

plugin:
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
        zip_dir: D:/GitProject/dev/pip/jmcomic/ # 压缩文件存放的文件夹
        delete_original_file: true # 压缩成功后，删除所有原文件和文件夹
"""


# 到此，程序已开始运行，最后会完成所有需求，并打印出如下日志。
# 你可以详细查看以下日志，运行时所有关键节点都有日志打印。
"""
2023-08-01 02:23:57:【plugin.invoke】调用插件: [login]
2023-08-01 02:23:57:【html】https://18comic.vip/login
2023-08-01 02:23:58:【plugin.login】登录成功
2023-08-01 02:23:58:【plugin.kwargs】插件参数类型转换: 145504 (<class 'int'>) -> 145504 (<class 'str'>)
2023-08-01 02:23:58:【plugin.invoke】调用插件: [find_update]
2023-08-01 02:23:58:【html】https://18comic.vip/album/145504
2023-08-01 02:23:59:【album.before】本子获取成功: [145504], 作者: [G.HO], 章节数: [104], 总页数: [3598], 标题: [健身教练 / もしも、幼馴染を抱いたなら / Fitness], 关键词: [['完結', '韩漫', '上柱香再走', '以晨：我爹呢', '你妈真香', '連載中', '肌肉豪名不虚传']], 2023-08-01 02:23:59:【html】https://18comic.vip/photo/291640
2023-08-01 02:24:00:【photo.before】开始下载章节: 291640 (145504[104/104]), 标题: [健身教练 完結], 图片数为[41]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00001.webp [1/41], [https://cdn-msp.18comic.vip/media/photos/291640/00001.webp] → [D:/jmcomic/145504/00001.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00004.webp [4/41], [https://cdn-msp.18comic.vip/media/photos/291640/00004.webp] → [D:/jmcomic/145504/00004.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00003.webp [3/41], [https://cdn-msp.18comic.vip/media/photos/291640/00003.webp] → [D:/jmcomic/145504/00003.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00007.webp [7/41], [https://cdn-msp.18comic.vip/media/photos/291640/00007.webp] → [D:/jmcomic/145504/00007.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00005.webp [5/41], [https://cdn-msp.18comic.vip/media/photos/291640/00005.webp] → [D:/jmcomic/145504/00005.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00002.webp [2/41], [https://cdn-msp.18comic.vip/media/photos/291640/00002.webp] → [D:/jmcomic/145504/00002.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00008.webp [8/41], [https://cdn-msp.18comic.vip/media/photos/291640/00008.webp] → [D:/jmcomic/145504/00008.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00006.webp [6/41], [https://cdn-msp.18comic.vip/media/photos/291640/00006.webp] → [D:/jmcomic/145504/00006.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00009.webp [9/41], [https://cdn-msp.18comic.vip/media/photos/291640/00009.webp] → [D:/jmcomic/145504/00009.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00010.webp [10/41], [https://cdn-msp.18comic.vip/media/photos/291640/00010.webp] → [D:/jmcomic/145504/00010.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00011.webp [11/41], [https://cdn-msp.18comic.vip/media/photos/291640/00011.webp] → [D:/jmcomic/145504/00011.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00012.webp [12/41], [https://cdn-msp.18comic.vip/media/photos/291640/00012.webp] → [D:/jmcomic/145504/00012.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00013.webp [13/41], [https://cdn-msp.18comic.vip/media/photos/291640/00013.webp] → [D:/jmcomic/145504/00013.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00014.webp [14/41], [https://cdn-msp.18comic.vip/media/photos/291640/00014.webp] → [D:/jmcomic/145504/00014.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00015.webp [15/41], [https://cdn-msp.18comic.vip/media/photos/291640/00015.webp] → [D:/jmcomic/145504/00015.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00016.webp [16/41], [https://cdn-msp.18comic.vip/media/photos/291640/00016.webp] → [D:/jmcomic/145504/00016.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00017.webp [17/41], [https://cdn-msp.18comic.vip/media/photos/291640/00017.webp] → [D:/jmcomic/145504/00017.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00018.webp [18/41], [https://cdn-msp.18comic.vip/media/photos/291640/00018.webp] → [D:/jmcomic/145504/00018.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00019.webp [19/41], [https://cdn-msp.18comic.vip/media/photos/291640/00019.webp] → [D:/jmcomic/145504/00019.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00020.webp [20/41], [https://cdn-msp.18comic.vip/media/photos/291640/00020.webp] → [D:/jmcomic/145504/00020.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00021.webp [21/41], [https://cdn-msp.18comic.vip/media/photos/291640/00021.webp] → [D:/jmcomic/145504/00021.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00023.webp [23/41], [https://cdn-msp.18comic.vip/media/photos/291640/00023.webp] → [D:/jmcomic/145504/00023.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00022.webp [22/41], [https://cdn-msp.18comic.vip/media/photos/291640/00022.webp] → [D:/jmcomic/145504/00022.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00024.webp [24/41], [https://cdn-msp.18comic.vip/media/photos/291640/00024.webp] → [D:/jmcomic/145504/00024.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00025.webp [25/41], [https://cdn-msp.18comic.vip/media/photos/291640/00025.webp] → [D:/jmcomic/145504/00025.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00027.webp [27/41], [https://cdn-msp.18comic.vip/media/photos/291640/00027.webp] → [D:/jmcomic/145504/00027.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00026.webp [26/41], [https://cdn-msp.18comic.vip/media/photos/291640/00026.webp] → [D:/jmcomic/145504/00026.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00028.webp [28/41], [https://cdn-msp.18comic.vip/media/photos/291640/00028.webp] → [D:/jmcomic/145504/00028.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00029.webp [29/41], [https://cdn-msp.18comic.vip/media/photos/291640/00029.webp] → [D:/jmcomic/145504/00029.jpg]
2023-08-01 02:24:00:【image.before】图片准备下载: 291640/00030.webp [30/41], [https://cdn-msp.18comic.vip/media/photos/291640/00030.webp] → [D:/jmcomic/145504/00030.jpg]
2023-08-01 02:24:01:【image.after】图片下载完成: 291640/00017.webp [17/41], [https://cdn-msp.18comic.vip/media/photos/291640/00017.webp] → [D:/jmcomic/145504/00017.jpg]
2023-08-01 02:24:01:【image.before】图片准备下载: 291640/00031.webp [31/41], [https://cdn-msp.18comic.vip/media/photos/291640/00031.webp] → [D:/jmcomic/145504/00031.jpg]
2023-08-01 02:24:01:【image.after】图片下载完成: 291640/00007.webp [7/41], [https://cdn-msp.18comic.vip/media/photos/291640/00007.webp] → [D:/jmcomic/145504/00007.jpg]
2023-08-01 02:24:01:【image.before】图片准备下载: 291640/00032.webp [32/41], [https://cdn-msp.18comic.vip/media/photos/291640/00032.webp] → [D:/jmcomic/145504/00032.jpg]
2023-08-01 02:24:01:【image.after】图片下载完成: 291640/00021.webp [21/41], [https://cdn-msp.18comic.vip/media/photos/291640/00021.webp] → [D:/jmcomic/145504/00021.jpg]
2023-08-01 02:24:01:【image.before】图片准备下载: 291640/00033.webp [33/41], [https://cdn-msp.18comic.vip/media/photos/291640/00033.webp] → [D:/jmcomic/145504/00033.jpg]
2023-08-01 02:24:02:【image.after】图片下载完成: 291640/00003.webp [3/41], [https://cdn-msp.18comic.vip/media/photos/291640/00003.webp] → [D:/jmcomic/145504/00003.jpg]
2023-08-01 02:24:02:【image.before】图片准备下载: 291640/00034.webp [34/41], [https://cdn-msp.18comic.vip/media/photos/291640/00034.webp] → [D:/jmcomic/145504/00034.jpg]
2023-08-01 02:24:03:【image.after】图片下载完成: 291640/00008.webp [8/41], [https://cdn-msp.18comic.vip/media/photos/291640/00008.webp] → [D:/jmcomic/145504/00008.jpg]
2023-08-01 02:24:03:【image.before】图片准备下载: 291640/00035.webp [35/41], [https://cdn-msp.18comic.vip/media/photos/291640/00035.webp] → [D:/jmcomic/145504/00035.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00015.webp [15/41], [https://cdn-msp.18comic.vip/media/photos/291640/00015.webp] → [D:/jmcomic/145504/00015.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00036.webp [36/41], [https://cdn-msp.18comic.vip/media/photos/291640/00036.webp] → [D:/jmcomic/145504/00036.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00029.webp [29/41], [https://cdn-msp.18comic.vip/media/photos/291640/00029.webp] → [D:/jmcomic/145504/00029.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00030.webp [30/41], [https://cdn-msp.18comic.vip/media/photos/291640/00030.webp] → [D:/jmcomic/145504/00030.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00037.webp [37/41], [https://cdn-msp.18comic.vip/media/photos/291640/00037.webp] → [D:/jmcomic/145504/00037.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00038.webp [38/41], [https://cdn-msp.18comic.vip/media/photos/291640/00038.webp] → [D:/jmcomic/145504/00038.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00019.webp [19/41], [https://cdn-msp.18comic.vip/media/photos/291640/00019.webp] → [D:/jmcomic/145504/00019.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00039.webp [39/41], [https://cdn-msp.18comic.vip/media/photos/291640/00039.webp] → [D:/jmcomic/145504/00039.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00024.webp [24/41], [https://cdn-msp.18comic.vip/media/photos/291640/00024.webp] → [D:/jmcomic/145504/00024.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00040.webp [40/41], [https://cdn-msp.18comic.vip/media/photos/291640/00040.webp] → [D:/jmcomic/145504/00040.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00026.webp [26/41], [https://cdn-msp.18comic.vip/media/photos/291640/00026.webp] → [D:/jmcomic/145504/00026.jpg]
2023-08-01 02:24:04:【image.before】图片准备下载: 291640/00041.webp [41/41], [https://cdn-msp.18comic.vip/media/photos/291640/00041.webp] → [D:/jmcomic/145504/00041.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00001.webp [1/41], [https://cdn-msp.18comic.vip/media/photos/291640/00001.webp] → [D:/jmcomic/145504/00001.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00010.webp [10/41], [https://cdn-msp.18comic.vip/media/photos/291640/00010.webp] → [D:/jmcomic/145504/00010.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00012.webp [12/41], [https://cdn-msp.18comic.vip/media/photos/291640/00012.webp] → [D:/jmcomic/145504/00012.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00032.webp [32/41], [https://cdn-msp.18comic.vip/media/photos/291640/00032.webp] → [D:/jmcomic/145504/00032.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00011.webp [11/41], [https://cdn-msp.18comic.vip/media/photos/291640/00011.webp] → [D:/jmcomic/145504/00011.jpg]
2023-08-01 02:24:04:【image.after】图片下载完成: 291640/00034.webp [34/41], [https://cdn-msp.18comic.vip/media/photos/291640/00034.webp] → [D:/jmcomic/145504/00034.jpg]
2023-08-01 02:24:05:【image.after】图片下载完成: 291640/00023.webp [23/41], [https://cdn-msp.18comic.vip/media/photos/291640/00023.webp] → [D:/jmcomic/145504/00023.jpg]
2023-08-01 02:24:05:【image.after】图片下载完成: 291640/00002.webp [2/41], [https://cdn-msp.18comic.vip/media/photos/291640/00002.webp] → [D:/jmcomic/145504/00002.jpg]
2023-08-01 02:24:05:【image.after】图片下载完成: 291640/00038.webp [38/41], [https://cdn-msp.18comic.vip/media/photos/291640/00038.webp] → [D:/jmcomic/145504/00038.jpg]
2023-08-01 02:24:05:【image.after】图片下载完成: 291640/00041.webp [41/41], [https://cdn-msp.18comic.vip/media/photos/291640/00041.webp] → [D:/jmcomic/145504/00041.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00035.webp [35/41], [https://cdn-msp.18comic.vip/media/photos/291640/00035.webp] → [D:/jmcomic/145504/00035.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00009.webp [9/41], [https://cdn-msp.18comic.vip/media/photos/291640/00009.webp] → [D:/jmcomic/145504/00009.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00031.webp [31/41], [https://cdn-msp.18comic.vip/media/photos/291640/00031.webp] → [D:/jmcomic/145504/00031.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00033.webp [33/41], [https://cdn-msp.18comic.vip/media/photos/291640/00033.webp] → [D:/jmcomic/145504/00033.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00027.webp [27/41], [https://cdn-msp.18comic.vip/media/photos/291640/00027.webp] → [D:/jmcomic/145504/00027.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00039.webp [39/41], [https://cdn-msp.18comic.vip/media/photos/291640/00039.webp] → [D:/jmcomic/145504/00039.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00036.webp [36/41], [https://cdn-msp.18comic.vip/media/photos/291640/00036.webp] → [D:/jmcomic/145504/00036.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00020.webp [20/41], [https://cdn-msp.18comic.vip/media/photos/291640/00020.webp] → [D:/jmcomic/145504/00020.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00037.webp [37/41], [https://cdn-msp.18comic.vip/media/photos/291640/00037.webp] → [D:/jmcomic/145504/00037.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00040.webp [40/41], [https://cdn-msp.18comic.vip/media/photos/291640/00040.webp] → [D:/jmcomic/145504/00040.jpg]
2023-08-01 02:24:06:【image.after】图片下载完成: 291640/00004.webp [4/41], [https://cdn-msp.18comic.vip/media/photos/291640/00004.webp] → [D:/jmcomic/145504/00004.jpg]
2023-08-01 02:24:07:【image.after】图片下载完成: 291640/00005.webp [5/41], [https://cdn-msp.18comic.vip/media/photos/291640/00005.webp] → [D:/jmcomic/145504/00005.jpg]
2023-08-01 02:24:07:【image.after】图片下载完成: 291640/00025.webp [25/41], [https://cdn-msp.18comic.vip/media/photos/291640/00025.webp] → [D:/jmcomic/145504/00025.jpg]
2023-08-01 02:24:07:【image.after】图片下载完成: 291640/00014.webp [14/41], [https://cdn-msp.18comic.vip/media/photos/291640/00014.webp] → [D:/jmcomic/145504/00014.jpg]
2023-08-01 02:24:07:【image.after】图片下载完成: 291640/00028.webp [28/41], [https://cdn-msp.18comic.vip/media/photos/291640/00028.webp] → [D:/jmcomic/145504/00028.jpg]
2023-08-01 02:24:07:【image.after】图片下载完成: 291640/00018.webp [18/41], [https://cdn-msp.18comic.vip/media/photos/291640/00018.webp] → [D:/jmcomic/145504/00018.jpg]
2023-08-01 02:24:08:【image.after】图片下载完成: 291640/00022.webp [22/41], [https://cdn-msp.18comic.vip/media/photos/291640/00022.webp] → [D:/jmcomic/145504/00022.jpg]
2023-08-01 02:24:08:【image.after】图片下载完成: 291640/00016.webp [16/41], [https://cdn-msp.18comic.vip/media/photos/291640/00016.webp] → [D:/jmcomic/145504/00016.jpg]
2023-08-01 02:24:08:【image.after】图片下载完成: 291640/00006.webp [6/41], [https://cdn-msp.18comic.vip/media/photos/291640/00006.webp] → [D:/jmcomic/145504/00006.jpg]
2023-08-01 02:24:08:【image.after】图片下载完成: 291640/00013.webp [13/41], [https://cdn-msp.18comic.vip/media/photos/291640/00013.webp] → [D:/jmcomic/145504/00013.jpg]
2023-08-01 02:24:08:【photo.after】章节下载完成: [291640] (145504[104/104])
2023-08-01 02:24:08:【album.after】本子下载完成: [145504]
2023-08-01 02:24:08:【plugin.invoke】调用插件: [zip]
2023-08-01 02:24:08:【plugin.zip.finish】压缩章节[291640]成功 → D:/GitProject/dev/pip/jmcomic/健身教练 完結.zip
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00017.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00007.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00021.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00003.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00008.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00015.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00029.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00030.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00019.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00024.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00026.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00001.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00010.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00012.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00032.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00011.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00034.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00023.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00002.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00038.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00041.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00035.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00009.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00031.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00033.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00027.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00039.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00036.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00020.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00037.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00040.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00004.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00005.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00025.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00014.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00028.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00018.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00022.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00016.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00006.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除原文件: D:/jmcomic/145504/00013.jpg
2023-08-01 02:24:08:【plugin.zip.remove】移除文件夹: D:/jmcomic/145504

进程已结束，退出代码为 0

"""
