# 日志自定义

本文档缘起于 GitHub Discussions: [discussions/195](https://github.com/hect0x7/JMComic-Crawler-Python/discussions/195)

下面是这个问题的解决方法：

## 1. 日志完全开启/关闭


使用配置：

```yaml
log: false
```


或者使用代码：

```python
from jmcomic import disable_jm_log 
disable_jm_log()
```

## 2. 日志过滤，只保留特定topic

使用插件配置

```yaml
log: true

plugins:
  after_init:
    - plugin: log_topic_filter # 日志topic过滤插件
      kwargs:
        whitelist: [ # 只保留api和html，这两个是Client发请求时会打的日志topic
          'api',
          'html',
        ]
```

## 3. 屏蔽插件的日志

给插件配置加上一个`log`配置项即可

```yaml
plugins:
  after_init:
    - plugin: client_proxy
      log: false # 插件自身不打印日志
      kwargs:
        proxy_client_key: photo_concurrent_fetcher_proxy
        whitelist: [ api, ]
```

## 4. 深度自定义：两类不同的拦截手段

根据你的需求复杂度，你可以选择以下方式：

- **方式 A：操作 jm_logger (推荐 / 标准)**

  适用于：改变日志输出位置（如文件、监控、后端服务）、调整显示格式、自定义过滤。

- **方式 B：接管 EXECUTOR_LOG (高级 / 深度定制)**

  适用于：需要完全重塑日志的分发逻辑，或者将日志直接桥接到不符合标准 logging 协议的第三方系统。

详细参考文档：[模块自定义](./4_module_custom.md#自定义log)
