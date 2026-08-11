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

## 2. 日志过滤，只保留特定 topic

最简单的方式是使用内置插件配置：

```yaml
log: true

plugins:
  after_init:
    - plugin: log_topic_filter # 日志 topic 过滤插件
      kwargs:
        whitelist: [ # 只保留 api 和 html，这两个是 Client 发请求时会打印的日志 topic
          'api',
          'html',
        ]
```

这个插件底层使用标准 `logging.Filter`。jmcomic 将每条日志的 topic 放在 `LogRecord.topic` 中，需要通过代码自定义时可以直接使用 logging API：

```python
import logging

from jmcomic import jm_logger


class TopicFilter(logging.Filter):
    def __init__(self, whitelist):
        super().__init__()
        self.whitelist = set(whitelist)

    def filter(self, record):
        return getattr(record, 'topic', None) in self.whitelist


jm_logger.addFilter(TopicFilter({'api', 'html'}))
```

Filter 加在 `jm_logger` 上会作用于它的所有 Handler；如果只想过滤某个输出目标，也可以将 Filter 加到对应的 Handler 上。

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

## 4. 并发下载的日志上下文

场景：当你在同时运行多个下载任务时，你希望区分哪些日志属于哪些任务，或者你希望结构化展示下载任务 对应的 下载日志。

首先，你需要设定一个任务id，这一步是在定义你的**任务维度**。下载一个本子还是多个本子都可以算作一个任务。

```python
from jmcomic import download_album, jm_task_context

with jm_task_context(task_id='task-1'): # 设置这个下载本子123的任务id为 task-1
    download_album(123)

with jm_task_context(task_id='task-1'): # 设置这三个本子的任务id为 task-1
    download_album([123, 456, 789])
```

设置了task_id以后，整个 download_album 内的日志打印都会具有这个task_id标识。

> [!NOTE]
> jmcomic 使用 [ContextVar](https://docs.python.org/3/library/contextvars.html) 把上下文传播到库内部创建的下载线程或async task里。你设置的task_id其实就是上下文里的一个字段

最直接的效果是，默认终端日志会自动显示任务 ID：

```text
[2026-01-01 12:00:00] [MainThread]:[task_id=task-1; album=123] 【album.after】本子下载完成: [123]
```

接下来你可以实现更高级的功能，比如收集任务对应的日志：

给 `jm_logger` 添加一个 Handler。每当 jmcomic 产生一条日志，Handler 都可以从 `record.jm_task_context` 中取出它所属的 `task_id`，从而按任务收集日志。完整代码如下：

```python
import logging
from collections import defaultdict

from jmcomic import jm_logger, download_album, jm_task_context

task_logs_dict = defaultdict(list)  # 收集任务日志，任务id -> 日志列表


class TaskLogHandler(logging.Handler):
  def emit(self, record):
    context: dict = getattr(record, 'jm_task_context', None) or {}  # 通过 jm_task_context 字段取出任务上下文
    task_id = context.get('task_id')  # 任务上下文里的task_id，就是你上面自定义的 task-1
    if task_id is not None:
      task_logs_dict[task_id].append(self.format(record))  # 收集日志


handler = TaskLogHandler()
handler.setFormatter(jm_logger.handlers[0].formatter)  # 复用jmcomic默认 Handler 的日志格式，你也可以自定义日志格式
jm_logger.addHandler(handler)

# 自定义handler后，再正常使用下载方法
task_id = 'task-1'
with jm_task_context(task_id=task_id):  # 任务id
  download_album(123)
```

任务上下文里，常用字段如下：

| 字段 | 类型     | 谁来设置 | 含义                                                                    | 示例 |
| --- |--------| --- |-----------------------------------------------------------------------| --- |
| `task_id` | 你传入的类型；本例需可哈希，建议使用 `str` | 由你通过 `jm_task_context` 设置 | 你的一次下载任务标识                                                            | `task-1` |
| `download_type` | `str`  | jmcomic 自动设置 | 你使用的download入口函数类型，例如 download_album -> album                         | `album` / `photo` |
| `jm_id` | `str`  | jmcomic 自动设置 | 你使用的download入口函数的入参，例如 download_album(123) -> 123。传入多个 ID 时，每个 ID 都在各自隔离的上下文中记录对应的 `jm_id`，并继承同一个 `task_id`。 | `123` |

> [!NOTE]
> 默认终端日志仅在 `task_id` 有值时显示任务上下文，并一同显示 `download_type` 和 `jm_id`。未设置 `task_id` 时，上下文仍会正常传递，但不会显示在默认日志中。

你也可以放入其他对象到任务上下文里，比如放入一个局部queue用来收集日志。在 jm_task_context 方法里传入即可 `jm_task_context(**fields)`

## 5. 深度自定义：两类不同的拦截手段

根据你的需求复杂度，你可以选择以下方式：

| 方式 | 适用场景 | 推荐程度 |
| --- | --- | --- |
| 操作 `jm_logger` | 修改输出位置、格式和过滤规则，或者接入标准日志系统 | 推荐 |
| 接管 `JmModuleConfig.EXECUTOR_LOG` | 完全替换日志分发逻辑，或者接入不兼容 `logging` 的系统 | 仅限特殊需求 |

### 5.1 操作 `jm_logger`

jmcomic 使用名为 `jmcomic` 的标准 Python Logger。下面的示例会移除默认输出方式，并将日志写入文件：

```python
import logging

from jmcomic import jm_logger


jm_logger.handlers.clear()
jm_logger.addHandler(
    logging.FileHandler('jm_download.log', encoding='utf-8')
)
```

`handlers.clear()` 会同时移除默认的终端输出。如果希望日志同时显示在终端并写入文件，只需要保留原有 Handler，再追加新的 `FileHandler`。

### 5.2 接管 `EXECUTOR_LOG`

只有标准 `logging` 无法满足需求时，才建议替换 `EXECUTOR_LOG`：

```python
from jmcomic import JmModuleConfig


def custom_log(topic: str, msg, error: Exception = None):
    # topic 是日志主题，例如 api、album.after、plugin.error
    # msg 是日志内容；error 是可选的异常对象
    print(topic, msg, error)


JmModuleConfig.EXECUTOR_LOG = custom_log
```

这是全局设置，会影响当前进程中之后产生的全部 jmcomic 日志。普通的文件输出、日志过滤和格式调整，应优先操作 `jm_logger`。
