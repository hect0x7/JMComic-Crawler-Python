# 域名与重试策略

访问禁漫时，常遇到网络不畅或默认域名失效的情况。jmcomic 提供了静态配置、动态获取和重试插件机制来应对。

下面演示如何配置和获取稳定或最新的可用域名。

## 1. 静态配置域名

如果你的网络环境下，某些域名（如 `18comic.vip`, `18comic.org`）可以稳定访问，最直接的方式是在配置文件中写死这些域名。

```yaml
# option.yml 示例
client:
  impl: html
  domain:
    html:
      - 18comic.vip
      - 18comic.org
```

```python
from jmcomic import *

# 通过配置文件构建并获取配置好的 Option 和 Client
# Option会加载上面的域名列表，在请求时如果第一个域名失败，会自动重试列表中的下一个域名。
op = create_option('option.yml')
cl = op.new_jm_client()
```

## 2. 动态获取域名

如果静态配置的域名失效，可以通过调用以下内置的 API 动态获取最新的禁漫域名。

> [!NOTE]
> 默认情况下，以下 API 在请求外网时会自动使用系统代理。但在 Linux 服务器等无全局代理的环境中，如果需要手动指定代理，你可以自行创建一个配置了 proxy 的 postman 对象并作为参数传入：
> `JmModuleConfig.get_html_domain_all(postman=JmModuleConfig.new_postman(proxies={'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}))`


### 2.1 抓取全部可用域名（推荐）

通过请求禁漫的官方发布页，获取所有公告的最新的网页端域名列表。

```python
from jmcomic import *

# 获取全量域名列表
domain_list = JmModuleConfig.get_html_domain_all()
print(f"全量域名列表：{domain_list}")

# 将获取到的域名替换掉全局默认域名列表
JmModuleConfig.DOMAIN_HTML_LIST = domain_list

op = create_option('option.yml')
# 新建的 Client 会默认使用刚刚更新的 DOMAIN_HTML_LIST 
cl = op.new_jm_client()
```

> [!WARNING]
> `get_html_domain_all_via_github` 已废弃。原 GitHub 仓库不再提供禁漫域名，兼容入口目前会转发到
> `get_html_domain_all`，并将在未来版本移除。

### 2.2 获取单个跳转域名

除了获取全部域名，也可以通过访问永久跳转页获取单个重定向用的新域名。

```python
from jmcomic import *

# 获取当前可用的单一网页端域名
domain = JmModuleConfig.get_html_domain()

op = JmOption.default()
op.client = op.new_jm_client(domain_list=[domain], impl='html')
```


## 3. 内置智能域名轮询（原 AdvancedRetryPlugin）

自 `v2.7.12` 起，同步与异步客户端均已**默认内置**智能域名容错策略（无需再手动配置 `advanced_retry` 插件）：

- 自动记录各域名的历史失败次数
- 每轮重试前按失败次数升序排列，失败多的域名自动后置
- 对相对路径请求按 `client.retry_times` 轮询域名列表，而完整图片 URL 仅针对自身重试，不跨 API 域名空转

> 若旧版 `option.yml` 中仍保留 `plugin: advanced_retry`，程序会正常兼容运行并打印一条提示日志，直接删除该插件配置即可。
