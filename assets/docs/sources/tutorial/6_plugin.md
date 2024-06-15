# Plugin - 插件

plugin(扩展/插件)是v2.2.0新引入的机制，使用插件可以实现灵活无感知的功能增强。

目前jmcomic已经内置了一些插件，源码位于 src/jmcomic/jm_plugin.py。

你可以在这里查看这些插件的配置→ [option_file_syntax](../option_file_syntax.md#3-option插件配置项)

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

举例：你可以配置一个login插件，在option对象创建后（`after_init`）时，调用`login`插件，执行登录禁漫的功能。

这样你后续使用option下载本子时，都会处于已登录状态。已登录状态可以让你访问所有禁漫本子。

## 2. 示例：在after_init时调用login插件

`login`插件功能：登录JM，获取并保存cookies到option内。后续option创建的Client都会携带cookies，即都是登录状态。

配置方式：将以下配置写入option文件

```yaml
plugins: # 插件配置项
  after_init: # 在after_init事件时自动执行插件
    - plugin: login # 插件的key
      kwargs: # 下面是给插件的参数 (kwargs)，由插件类自定义
        username: un # 禁漫帐号
        password: pw # 密码
```

有了上述option配置，当你调用下面的代码时，login插件就会执行。

```python
import jmcomic

option = jmcomic.create_option_by_file('xxx.yml')  # 创建option对象
# 程序走到这里，login插件已经调用完毕了
# 后续下载本子就都是已登录状态里了
option.download_album(123)
```

## 3. 怎么手动调用插件

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

## 4. 示例：自定义插件

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

