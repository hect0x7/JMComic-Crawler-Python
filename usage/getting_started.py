"""
--------------------
    API快速上手
--------------------
"""
import jmcomic  # 导入此模块，需要先安装.

jmcomic.download_album('422866')  # 传入要下载的album的id，即可下载整个album到本地.
# 上面的这行代码，还有一个可选参数option: JmOption，表示配置项，
# 配置项的作用是告诉程序下载时候的一些选择，
# 比如，要下载到哪个文件夹，使用怎样的路径组织方式（比如[/作者/本子id/图片] 或者 [/作者/本子名称/图片]）.
# 如果没有配置，则会使用 JmOption.default()，下载的路径是[当前工作文件夹/本子章节名称/图片].


"""
--------------------
    配置文件上手
--------------------
"""
from jmcomic import JmModuleConfig, JmOption, create_option

# 先获取默认的JmOption对象
option = JmOption.default()

# 可以把对象保存为文件，方便编辑
option.to_file('./保存路径.yml')  # yml格式
option.to_file('./保存路径.json')  # json格式

# 如果你修改了默认配置，现在想用你修改后的配置来下载，使用如下代码
option = JmOption.from_file('./保存路径.yml')
# 或者
option = create_option('./保存路径.yml')
# 使用你的option配置来下载
jmcomic.download_album('23333', option)


"""

--------------------
    配置文件进阶
--------------------

定制option有几种方式？

方式1. 针对一个option对象生效
    JmOption.construct({xxx: yyy})  -- 简单配置推荐
    JmOption.from_file('配置文件路径') -- 复杂配置推荐
    
方式2. 针对所有option对象生效，全局配置，配置的优先级次于1
    JmModuleConfig.default_option_dict['xxx'] = yyy

下面以配置代理为例

"""
from jmcomic import JmOption, ProxyBuilder, download_album

# 方式1. 定制一个option对象
option = JmOption.construct({
    'client': {
        'postman': {
            'meta_data': {
                'proxies': ProxyBuilder.clash_proxy(),
            }
        }
    }
})
# 调用下载api需要传入此option
download_album('xxx', option)

# 方式2. 使用全局配置
JmModuleConfig.default_option_dict['client']['postman']['meta_data']['proxies'] = ProxyBuilder.clash_proxy()
# 调用下载api**不需要**传入option
download_album('xxx')


"""
--------------------
    批量下载介绍
--------------------
"""
from jmcomic import download_album

# 如果你想要批量下载，可以使用 list/set/tuple/生成器 作为第一个参数。
# 第二个参数依然是可选的JmOption对象
download_album(['422866', '1', '2', '3'])  # list
download_album({'422866', '1', '2', '3'})  # set
download_album(('422866', '1', '2', '3'))  # tuple
download_album(aid for aid in ('422866', '1', '2', '3'))  # 生成器


"""
--------------------
    获取域名介绍
--------------------
"""
from jmcomic import JmModuleConfig

# 方式1: 访问禁漫发布页
domain_ls = JmModuleConfig.get_jmcomic_url_all()
print(url_ls)

# 方式2: 访问禁漫的永久网域
url = JmModuleConfig.get_jmcomic_url()
print(url)

# Q：download_album(xxx)，没有传入option，那么访问JM使用的默认域名是什么?
# A：默认域名是: JmModuleConfig.get_jmcomic_url()，如果想定制此默认域名：
# 做法1: 定制option，见上
# 做法2: JmModuleConfig.DOMAIN = '18comic.vip'
