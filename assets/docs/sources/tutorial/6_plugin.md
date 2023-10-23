# Plugin - 插件

plugin(扩展/插件)是v2.2.0新引入的机制，使用插件可以实现灵活无感知的功能增强。

plugin的机制为，可在`特定时间` 回调 `特定插件`。

目前jmcomic已经内置了一些强大的插件，源码位于 src/jmcomic/jm_plugin.py。

配置插件的方式请查看 [option_file_syntax](../option_file_syntax.md#3-option插件配置项)



## 示例1. 使用login插件，自动登录禁漫

特定时间：after_init（option对象实例化完毕后）

特定插件：login

插件功能：登录JM，获取并保存cookies，所有的Client都会使用这个cookies。

首先，你需要在option配置文件当中配置如下内容，来实现在after_init时，调用login插件。

```yml
plugins:
  after_init: # 时机
    - plugin: login # 插件的key
      kwargs:
          # 下面是给插件的参数 (kwargs)，由插件类自定义
          username: un # 禁漫帐号
          password: pw # 密码
```

有了上述option配置，当你调用下面的代码时，login插件就会执行。

```python
import jmcomic
option = jmcomic.create_option('xxx.yml')
# 程序走到这里，login插件已经调用完毕了。
```



## 示例2. 自定义插件

下面演示自定义插件，分为3步:

1. 自定义plugin类
2. 让plugin类生效
3. 使用plugin的key

* 如果你有好的plugin想法，也欢迎向我提PR，将你的plugin内置到jmcomic模块中

```python
# 1. 自定义plugin类
from jmcomic import JmOptionPlugin, JmModuleConfig, create_option


class MyPlugin(JmOptionPlugin):
    # 指定你的插件的key
    plugin_key = 'myplugin'

    # 覆盖invoke方法，设定方法只有一个参数，名为`hello_plugin`
    def invoke(self, hello_plugin) -> None:
        print(hello_plugin)

# 2. 让plugin类生效
JmModuleConfig.register_plugin(MyPlugin)
```

接下来，在option中配置如下内容来使用你的插件

```yml
# 3. 在配置文件中使用plugin
plugins:
  after_init: # 时机
    - plugin: myplugin # 插件的key
      kwargs:
        hello_plugin: this is my plugin invoke method's parameter # 你自定义的插件的参数
```

完成上述步骤后，每当你使用下面的代码，你的plugin会被调用，控制台就会打印出 `this is my plugin invoke method's parameter`

```python
from jmcomic import create_option
option = create_option('xxx')
```





