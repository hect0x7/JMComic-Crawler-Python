# 域名与重试策略

访问禁漫时，常遇到网络不畅或默认域名失效的情况。jmcomic 支持静态、动态两种配置域名方式，并内置了轮询策略。

> **💡 默认逻辑（不配置域名时）**
>
> 日常使用通常**无需手动配置域名**，jmcomic 会根据客户端类型自动处理：
> - **移动端（`impl: api`，默认）**：使用内置的 `JmModuleConfig.DOMAIN_API_LIST`，并在初始化时自动拉取最新 API 域名与图床域名。
> - **网页端（`impl: html`）**：未配置域名时，自动调用 `JmModuleConfig.get_html_domain()` 访问官方永久跳转页获取可用域名。
>
> 只有当默认域名在你当前网络下无法访问时，才需要按下面两种方式手动配置。

## 1. 静态配置域名

如果你已知某些域名（如 `18comic.vip`, `18comic.org`）在当前网络下可以稳定访问，最直接的方式是在配置文件中写死：

```yaml
# option.yml
client:
  impl: html
  domain:
    html:
      - 18comic.vip
      - 18comic.org
```

```python
from jmcomic import *

# 加载配置文件；请求失败时会自动按上面配置的域名列表轮询重试
op = create_option('option.yml')
cl = op.new_jm_client()
```

## 2. 动态配置域名

如果网页端域名失效，可以在代码中调用内置接口实时抓取最新可用域名，再选择**全局生效**或**局部生效**：

```python
from jmcomic import *

# ── 第一步：动态获取可用域名（二选一） ──
# 方式 1（推荐）：访问官方发布页，获取全部可用网页端域名列表
domain_list = JmModuleConfig.get_html_domain_all()

# 方式 2：访问永久跳转页，仅获取单个重定向新域名
# domain_list = [JmModuleConfig.get_html_domain()]


# ── 第二步：将域名设置生效（二选一） ──
op = JmOption.default()

# 用法 A【设置到全局】：替换模块默认域名列表，后续所有新创建的网页端 Client 自动生效
JmModuleConfig.DOMAIN_HTML_LIST = domain_list
cl = op.new_jm_client(impl='html')

# 用法 B【局部设置到 Client】：仅传给当前 Client 实例，不修改全局配置
cl = op.new_jm_client(impl='html', domain_list=domain_list)
```

> [!NOTE]
> 上述获取域名的接口默认自动使用系统代理。在 Linux 服务器等无全局代理的环境中，可手动传入带代理的 `postman`：
> `JmModuleConfig.get_html_domain_all(postman=JmModuleConfig.new_postman(proxies='127.0.0.1:7890'))`

## 3. 内置轮询策略

无论使用默认域名还是手动配置的域名，同步与异步客户端均默认启用内置的智能轮询与重试机制，无需额外配置插件：

- **失败后置轮询**：自动记录各域名的失败次数，每次重试前按失败次数升序排列，失败多的域名自动后置，优先请求健康节点。
- **图床 CDN 自动切节点**：下载图片遇到超时、5xx 或空响应时，自动切换 `JmModuleConfig.DOMAIN_IMAGE_LIST` 中的备用图床节点（API 模式还会自动收录服务端下发的最新图床域名至首位）。
- **重试预算控制**：由配置项 `client.retry_times`（默认 `5`）控制请求失败后的额外重试轮数。
