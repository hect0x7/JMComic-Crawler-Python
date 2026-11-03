# Plugin - 插件

plugin(扩展/插件)是v2.2.0新引入的机制，使用插件可以实现灵活无感知的功能增强。

目前jmcomic已经内置了一些插件，源码位于 src/jmcomic/jm_plugin.py。

你可以在这里查看这些插件的配置→ [option_file_syntax](../option_file_syntax.md#3-option)

## 1. 插件机制介绍

你可以在option配置文件中配置插件，插件会特定的<u>`事件`</u>发生时自动执行。

jmcomic里的内置事件如下：

- `after_init`: option对象创建后


- `before_image`: 下载图片前
- `before_album`: 下载本子前
- `before_photo`: 下载章节前


- `after_image`: 下载图片后
- `after_album`: 下载本子后
- `after_photo`: 下载章节后

举例：你可以配置一个 `usage_log` 插件，在option对象创建后（`after_init`）时开始执行，持续打印 CPU、内存等硬件占用情况。

> [!NOTE]
> 登录不需要插件：账号密码写在配置文件顶层的 `auth` 下，jmcomic 会在需要时自动登录，详见 [登录指南](./17_login.md)。

## 2. 示例：在after_init时调用usage_log插件

配置方式：将以下配置写入option文件

```yaml
plugins: # 插件配置项
  after_init: # 在after_init事件时自动执行插件
    - plugin: usage_log # 插件的key
      kwargs: # 下面是给插件的参数 (kwargs)，由插件类自定义
        interval: 0.5 # 每隔 0.5 秒打印一次
        enable_warning: true # 占用过大时发出预警
```

有了上述option配置，当你调用下面的代码时，usage_log插件就会执行。

```python
import jmcomic

option = jmcomic.create_option_by_file('xxx.yml')  # 创建option对象
# 程序走到这里，usage_log插件已经开始在后台打印硬件占用了
option.download_album(123)
```

## 3. 综合示例：登录、增量下载与分章压缩

下面把多个插件组合起来，完成这些需求：

1. 使用登录状态下载本子（配置顶层 `auth`，不需要插件）；
2. 只下载指定章节之后的新章节；
3. 将图片转换为 JPG；
4. 每个章节分别压缩，并在压缩成功后删除原图片。

先创建并加载配置文件：

```python
from jmcomic import create_option

# 加载配置时会执行 after_init 插件，其中 find_update 会开始下载
create_option('myoption.yml')
```

然后在 `myoption.yml` 中组合插件：

```yaml
dir_rule:
  rule: Bd_Aid
  base_dir: ./downloads

download:
  image:
    suffix: .jpg

auth:
  username: your_username
  password: your_password

plugins:
  after_init:
    - plugin: find_update
      kwargs:
        145504: 290266  # 只下载本子 145504 中章节 290266 之后的新章节

  after_album:
    - plugin: zip
      kwargs:
        level: photo
        filename_rule: Ptitle
        zip_dir: ./downloads
        delete_original_file: true
```

这里的执行顺序是：`find_update` 发起增量下载，下载前按 `auth` 自动登录；每个本子下载完成后，`zip` 插件按章节生成压缩文件并删除已成功压缩的原图片。


## 4. 怎么手动调用插件

你可以使用下面的代码触发某个事件

```python
# 假设你已经创建了option对象
from jmcomic import JmOption

option: JmOption
# 手动调用after_init事件下的插件
option.call_all_plugin('after_init')
# 手动调用一个特定事件的插件（如果你没有配置这个事件的插件，那么无事发生。）
option.call_all_plugin('my_event')

```

## 5. 示例：自定义插件

* 如果你有好的plugin想法，也欢迎向我提PR，将你的plugin内置到jmcomic模块中

下面演示自定义插件，分为3步:

1. 自定义plugin类
2. 让plugin类生效
3. 使用plugin的key

```python
# 1. 自定义plugin类
from jmcomic import JmOptionPlugin, JmModuleConfig


# 自定义一个类，继承JmOptionPlugin
class MyPlugin(JmOptionPlugin):
    # 指定你的插件的key
    plugin_key = 'myplugin'

    # 实现invoke方法
    # 方法的参数可以自定义，这里假设方法只有一个参数 word
    def invoke(self, word) -> None:
        print(word)


# 2. 让plugin类生效
JmModuleConfig.register_plugin(MyPlugin)
```

接下来，在option中配置如下内容来使用你的插件

```yaml
# 3. 在配置文件中使用plugin
plugins:
  after_init: # 事件
    - plugin: myplugin # 你自定义的插件key
      kwargs:
        word: hello jmcomic # 你自定义的插件的参数
```

完成上述步骤后，每当你使用下面的代码，你的plugin会被调用，控制台就会打印出 `hello jmcomic`

```python
from jmcomic import create_option

option = create_option('xxx')
```

## 高级：异步插件生命周期控制

如果你编写的插件是异步的（比如启动了新线程处理任务），此时主程序可能会先于插件执行完毕而退出。为解决此问题，`JmOptionPlugin` 提供了注册等待挂起的功能：

```python
import threading
import time
from jmcomic import JmOptionPlugin, JmModuleConfig

class MyAsyncPlugin(JmOptionPlugin):
    plugin_key = 'my_async_plugin'

    def invoke(self, **kwargs) -> None:
        # 1. 告诉 option 有一个异步插件正在运行，请主线程在退出前关掉我或等我
        self.enter_wait_list()
        self.is_running = True
        
        # 2. 启动一个新的线程...
        self.thread = threading.Thread(target=self.do_async_work)
        self.thread.start()
    
    def do_async_work(self):
        while self.is_running:
            print('异步工作运行中...')
            time.sleep(1)

    def wait_until_finish(self):
        # 3. 覆写 wait_until_finish 方法，实现优雅停机 / 强制阻塞等待的逻辑
        # 主程序在结束时必定会调用它（如果此前挂起了该插件）
        self.is_running = False # 发送停机信号
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join() # 阻塞直到线程安全退出

JmModuleConfig.register_plugin(MyAsyncPlugin)
```

这样，程序在所有任务执行完退出的最后一刻，会通过 `option.wait_all_plugins_finish()` 遍历所有调用过 `enter_wait_list()` 挂起的插件，并调用其 `wait_until_finish()` 方法。只要你在该方法中实现了停机信号或阻塞等待的发送，主线程就会等待你的异步逻辑全部安全并优雅地退出。


