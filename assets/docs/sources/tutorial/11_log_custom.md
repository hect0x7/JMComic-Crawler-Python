# 日志自定义

本文档缘起于 GitHub Discussions: [discussions/195](https://github.com/hect0x7/JMComic-Crawler-Python/discussions/195)

下面是这个问题的解决方法：

## 1. 日志完全开启/关闭

使用代码：

```
from jmcomic import disable_jm_log 
disable_jm_log()
```

使用配置：

```yaml
log: false
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
    - plugin: client_proxy # 提高移动端的请求效率的插件
      log: false # 插件自身不打印日志
      kwargs:
        proxy_client_key: photo_concurrent_fetcher_proxy
        whitelist: [ api, ]
```

## 4. 完全自定义 jmcomic 日志

你可以自定义jmcomic的模块日志打印函数，参考文档：[模块自定义](./4_module_custom.md#自定义log)
