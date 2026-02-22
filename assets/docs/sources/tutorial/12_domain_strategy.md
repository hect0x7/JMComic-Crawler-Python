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

> **注意**：
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

### 2.2 通过 GitHub 兜底获取域名

如果连禁漫的发布页本身都被墙了无法访问，可以请求禁漫官方放在 GitHub 的仓库来解析最新域名。

```python
from jmcomic import *

# 该请求发往 github.com，在大多数常规网络中均能保持连通
domains = JmModuleConfig.get_html_domain_all_via_github()

op = JmOption.default()
# 可以结合重试机制，允许失败时轮换多次
op.client.retry_times = 3

# 应用域名池新建包含该域名的 Client (记得指定 impl='html')
# 将新建的 client 赋值回 op，使其在后续的下载中生效
op.client = op.new_jm_client(domain_list=domains, impl='html')

download_album('438696', op)
```

### 2.3 获取单个跳转域名

除了获取全部域名，也可以通过访问永久跳转页获取单个重定向用的新域名。

```python
from jmcomic import *

# 获取当前可用的单一网页端域名
domain = JmModuleConfig.get_html_domain()

op = JmOption.default()
op.client = op.new_jm_client(domain_list=[domain], impl='html')
```


## 3. 使用高级重试插件（AdvancedRetryPlugin）

默认的机制是在单次请求报错时，按顺序尝试数组内的下一个域名。
如果经常遇到连接断开或超时，可以使用 `advanced_retry` 插件。该插件提供：
- 记录历史失败次数
- 限制单个域名的最大失败次数（超过则拉黑废弃）
- 对列表循环多轮尝试等容错机制

**在 option.yml 中配置启用：**

```yaml
plugins:
  after_init:
    - plugin: advanced_retry      # 声明并开启高级重试插件
      kwargs:
        retry_config:
          retry_rounds: 3             # 整个域名数组支持轮询尝试的圈数
          retry_domain_max_times: 5   # 单个域名允许的最大失败次数
```

配置后，用该 option 构建的 Client 在下载和请求时，就会自动切入高级容错策略。
