# 登录指南

禁漫的大部分本子不登录也能下载，但以下场景需要登录：

- 下载少部分敏感题材的本子；
- 收藏夹、每日签到；
- 查看本子的收藏、点赞状态。

下面介绍如何登录。

## 1. 一条原则：账号只写在顶层 `auth`

所有登录相关的配置，都只写在配置文件的顶层 `auth` 下。jmcomic 登录后拿到的 cookies、用户 ID，也会统一写回 `option.auth`。

`auth` 有两种写法，**二选一**：

| 写法 | 适用的客户端 | 说明 |
|---|---|---|
| 账号密码（推荐） | 网页端 `html`、移动端 `api` 都可以 | jmcomic 在需要时自动登录，拿到新的 cookies |
| 浏览器 cookies | 只适用于网页端 `html` | jmcomic 不登录，原样带上你给的 cookies |

> [!IMPORTANT]
> 不要同时配置账号密码和 cookies。在网页端，jmcomic 看到 `auth` 里已有 cookies 和用户名，就认为已经登录，不会再用账号密码登录。如果这份 cookies 已过期，下载会以未登录状态进行。

### 1.1 写法一：账号密码（推荐）

```yaml
# op.yml
auth:
  username: 你的用户名
  password: 你的密码
```

```python
from jmcomic import create_option_by_file, download_album

option = create_option_by_file('op.yml')

# 下载前会自动登录一次，然后下载
download_album(123, option)
```

### 1.2 写法二：浏览器 cookies（仅网页端）

```yaml
auth:
  cookies:
    AVS: 从浏览器复制的AVS值  # 只需要 AVS 这一项
```

> [!WARNING]
> - cookies 区分域名：你访问的是 `18comic.vip`，cookies 就必须来自 `18comic.vip`（参考 [issue#104](https://github.com/hect0x7/JMComic-Crawler-Python/issues/104)）。
> - 浏览器 cookies 对移动端 `impl: api` 无效。
> - cookies 过期后，jmcomic 不会替你刷新，需要重新复制，或者改用账号密码。

### 1.3 从环境变量读取账号

不想把密码明文写进配置文件时（例如 GitHub Actions），可以用 `${环境变量名}`：

```yaml
auth:
  username: ${JM_USERNAME}
  password: ${JM_PASSWORD}
```

- 创建 option 时自动替换为环境变量的值。
- 环境变量未设置或值为空字符串时，不会报错，等同于没有配置账号，以未登录状态访问。
- `auth.cookies` 也支持这种写法。

## 2. 在代码里使用登录态

如果只是调用 `download_album` 等下载接口，按第 1 章配好 `auth` 就够了，下载前会自动登录。

本章面向在 Python 代码里**直接操作 `client`**（如拉取收藏夹、每日签到、管理收藏），或不想改配置文件、只在代码里为单个 `client` 临时登录的场景。

### 2.1 全局登录：让 option 创建的所有 client 都登录

`option.new_jm_client()` 只会带上 `auth` 里已有的 cookies，**不会**自动登录。

要使 client 登录，可以在创建 client 前先调用一次 `login_with_option_auth()`：

效果：让 option 创建的所有 client 都登录（`download_album` 内部也是调用这个方法的）。


```python
option = create_option_by_file('op.yml')

option.login_with_option_auth()      # 用 auth 里的账号登录，结果写回 option.auth
client = option.new_jm_client()      # 之后创建的 client 都带登录态

for page in client.favorite_folder_gen():
    ...
```

异步版本：

```python
await option.login_with_option_auth_async() # 用 auth 里的账号登录，结果写回 option.auth
async with option.new_jm_async_client() as client:
    ...
```

### 2.2 局部登录：只让一个 client 登录

使用 `client.login()` 只影响这一个 client 的登录，不会修改 `option`：

```python
client = option.new_jm_client()
client.login('你的用户名', '你的密码')

# 也可以直接传入 option.auth 里的账号密码（只登录这一个 client，不写回 option.auth）
client.login(option.auth.username, option.auth.password)
```

### 2.3 插件

需要登录的内置插件会按 `auth` 自动登录，不需要额外配置，包括：

- `find_update`：内部调用下载接口，下载前自动登录；
- `favorite_folder_export`：导出前自动登录。

## 3. jmcomic 内部做了什么（约定）

### 3.1 哪些入口会发起登录

| 入口 | 是否发起登录 |
|---|---|
| `download_album` / `download_photo` / `download_batch` 及对应的异步版本 | `auth` 配了账号密码，并且当前**未登录**时，登录一次；否则不登录。传 `login=False` 可关闭 |
| `favorite_folder_export` 插件 | `auth` 配了账号密码，并且当前**未登录**时，登录一次；否则不登录 |
| `option.login_with_option_auth()` / `login_with_option_auth_async()` | 当前**未登录**时登录；传 `force=True` 时总是登录 |
| `client.login()` | 总是登录，只影响这个 client |
| `option.new_jm_client()` / `build_jm_client()` / `new_jm_async_client()` | 从不登录，只带上已有的 cookies |

“已登录”的判断标准（两条需**同时满足**）：

1. `auth.cookies` 不为空；
2. 对应客户端的用户标识不为空：网页端要求 `auth.username` 不为空；移动端要求 `auth.user_id` 不为 `None`（`user_id` 只能通过登录拿到，不需要手动配置）。

### 3.2 登录成功后写回什么

| 字段 | 写回方式 |
|---|---|
| `auth.cookies` | 合并写入：同名的 cookie 覆盖，其余保留 |
| `auth.user_id` | 覆盖写入 |

写回后，`option.build_jm_client()` 已缓存的 client 会同步更新，之后新建的 client 也会带上这些登录态。

### 3.3 cookies 的合并顺序

创建 client 时，cookies 按以下顺序合并，后者覆盖前者：

1. `client.postman.meta_data.cookies`（旧写法）
2. `auth.cookies`
3. 创建 client 时显式传入的 `cookies`，例如 `option.new_jm_client(cookies={...})`

### 3.4 保存配置文件

`option.to_file()` 保存 `auth` 时：

- 保存 `username`、`password`；
- **不保存** `cookies` 和 `user_id`，因为它们是运行时登录态。

### 3.5 多账号

一个 option 对应一个账号。`option.copy_option()` 得到的副本与原 option **共用同一个 `auth`**，在副本上登录也会改变原 option。需要多个账号时，请为每个账号分别创建 option。

## 4. 旧写法迁移

下面的旧写法仍然可用，但新配置不建议再使用：

| 旧写法 | 迁移到 |
|---|---|
| `client.postman.meta_data.cookies` | `auth.cookies` |
| `login` 插件（`- plugin: login`，`kwargs` 传 `username` / `password`） | 账号密码写在 `auth`，删掉 `login` 插件 |

`login` 插件仅为兼容旧配置而保留：执行时把传入的账号密码写入 `auth`，并且每次都强制登录。

## 5. 常见问题

<details markdown="1">
<summary>从 <code>login</code> 插件迁移到顶层 <code>auth</code> 后有什么变化？（<code>login</code> 插件和 <code>auth</code> 的区别）</summary>

旧写法通常把 `login` 插件配在 `after_init` 下，效果相当于「配置 `auth` + 在创建 `option` 时自动执行一次 `option.login_with_option_auth(force=True)`」。
而顶层 `auth` 只保存凭证，**创建 `option` 时不会主动发起登录**（推迟到需要时再登录）：

- 如果你是调用 `download_album` 等下载接口，不需要改代码，下载前会自动登录；
- 如果你不在下载入口里用，而是创建 `option` 后直接 `option.new_jm_client()` 调接口，迁移为 `auth` 后少了一步初始化自动登录，需要先手动调一次 `option.login_with_option_auth()`（异步为 `await option.login_with_option_auth_async()`），见第 2.1 节。

</details>

<details markdown="1">
<summary>配置了 cookies 还是没有登录态？</summary>

先检查 cookies 的来源域名和实际访问的域名是否一致，再检查是否用的是移动端 `impl: api`（浏览器 cookies 对移动端无效）。

</details>

<details markdown="1">
<summary>配置了账号密码，直接用 client 时却没有登录？</summary>

`new_jm_client()` 不会自动登录，先调用 `option.login_with_option_auth()`，见第 2.1 节。

</details>

<details markdown="1">
<summary>下载时提示需要登录，但我配置了 cookies 和账号密码？</summary>

大概率是 cookies 过期了，而 jmcomic 认为已经登录，所以没有用账号密码重新登录。删掉 `auth.cookies`，只保留账号密码即可。

</details>
