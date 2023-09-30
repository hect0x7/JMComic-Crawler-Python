"""

该文件介绍不同客户端、以及配置客户端实现的方式（移动端、网页端）

有关不同客户端的介绍:

网页端:
代号为 html
最早实现的客户端，由于网页信息较为丰富，相对而言效率比较高
但是不同域名会限制ip，比如美国ip不能使用 18comic.vip 域名
不同域名的网站稳定性也差别很大
国内直连域名经常换

移动端:
代号为 api
在v2.3.3版本中引入的新客户端实现
比网页端效率比较低，因为同样的信息量，移动端需要请求多个接口
但是不限制ip地区，兼容性很好，国内直连比较稳定



1. 通过配置文件
```yml
client:
  # 下面两行只能选一行放到你的配置文件
  impl: api # 移动端
  impl: html # 网页端

```

2. 通过修改模块配置类 JmModuleConfig

# JmModuleConfig.CLIENT_IMPL_DEFAULT 该字段表示默认的客户端实现
# 当配置文件中不存在client.impl配置时，就使用 JmModuleConfig.CLIENT_IMPL_DEFAULT
# 你可以不在配置文件中配置，而是使用下面的代码（在你创建option前）

JmModuleConfig.CLIENT_IMPL_DEFAULT = 'api' # 移动端
JmModuleConfig.CLIENT_IMPL_DEFAULT = 'html' # 网页端


"""
