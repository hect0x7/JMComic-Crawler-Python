# 登录指南

禁漫的大部分本子不登录也能下载。以下场景需要登录：

- 少部分敏感题材的本子；
- 收藏夹、每日签到；
- 查看本子的收藏、点赞状态。

## 1. 一条原则：账号只写在顶层 `auth`

所有登录相关的配置，都只写在配置文件的顶层 `auth` 下。jmcomic 登录后拿到的 cookies、用户名、用户 ID，也会统一写回 `option.auth`。

`auth` 有两种写法，**二选一**：

| 写法 | 适用的客户端 | 说明 |
|---|---|---|
| 账号密码（推荐） | 网页端 `html`、移动端 `api` 都可以 | jmcomic 在需要时自动登录，拿到新的 cookies |
| 浏览器 cookies | 只适用于网页端 `html` | jmcomic 不登录，原样带上你给的 cookies |

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

> [!IMPORTANT]
> 不要同时配置账号密码和 cookies。在网页端，jmcomic 看到 `auth` 里已有 cookies 和用户名，就认为已经登录，不会再用账号密码登录。如果这份 cookies 已过期，下载会以未登录状态进行。

### 1.3 从环境变量读取账号

不想把密码明文写进配置文件时（例如 GitHub Actions），可以用 `${环境变量名}`：

```yaml
auth:
  username: ${JM_USERNAME}
  password: ${JM_PASSWORD}
```

- 创建 option 时替换为环境变量的值；环境变量未设置会直接报错。
- 环境变量的值为空字符串时，等同于没有配置账号，以未登录状态访问。
- `auth.cookies` 下的值也支持这种写法。

## 2. 在代码里使用登录态

### 2.1 让 option 创建的所有 client 都登录

`option.new_jm_client()` 只会带上 `auth` 里已有的 cookies，**不会**自动登录。直接使用 client 时，要先调用一次 `login_with_option_auth()`：

```python
option = create_option_by_file('op.yml')

option.login_with_option_auth()      # 用 auth 里的账号登录，结果写回 option.auth
client = option.new_jm_client()      # 之后创建的 client 都带登录态

for page in client.favorite_folder_gen():
    ...
```

异步版本：

```python
await option.login_with_option_auth_async()
async with option.new_jm_async_client() as client:
    ...
```

### 2.2 只让一个 client 登录

`client.login()` 只影响这一个 client，不会修改 `option`：

```python
client = option.new_jm_client()
client.login('你的用户名', '你的密码')
```

### 2.3 插件

需要登录的内置插件会按 `auth` 自动登录，不需要额外配置：

- `find_update`：内部调用下载接口，下载前自动登录；
- `favorite_folder_export`：导出前自动登录。

## 3. jmcomic 内部做了什么

### 3.1 哪些入口会发起登录

| 入口 | 是否发起登录 |
|---|---|
| `download_album` / `download_photo` / `download_batch` 及对应的异步版本 | `auth` 配了账号密码，并且当前**未登录**时，登录一次；否则不登录。传 `login=False` 可关闭 |
| `favorite_folder_export` 插件 | 同上 |
| `option.login_with_option_auth()` / `login_with_option_auth_async()` | 当前**未登录**时登录；传 `force=True` 时总是登录 |
| `client.login()` | 总是登录，只影响这个 client |
| `option.new_jm_client()` / `build_jm_client()` / `new_jm_async_client()` | 从不登录，只带上已有的 cookies |

“已登录”的判断标准：

- `auth.cookies` 不为空；并且
- 网页端：`auth.username` 不为空；移动端：`auth.user_id` 不为空。`user_id` 只能通过登录拿到，不需要手动配置。

### 3.2 登录成功后写回什么

| 字段 | 写回方式 |
|---|---|
| `auth.cookies` | 合并写入：同名的 cookie 覆盖，其余保留 |
| `auth.username`、`auth.user_id` | 覆盖写入 |

写回后，`option.build_jm_client()` 已缓存的 client 会同步更新，之后新建的 client 也会带上这些登录态。

### 3.3 cookies 的合并顺序

创建 client 时，cookies 按以下顺序合并，后者覆盖前者：

1. `client.postman.meta_data.cookies`（旧写法）
2. `auth.cookies`
3. 创建 client 时显式传入的 `cookies`，例如 `option.new_jm_client(cookies={...})`

### 3.4 保存配置文件

`option.to_file()` 保存 `auth` 时：

- 保存 `username`、`password`；
- **不保存** `cookies` 和 `user_id`，因为它们是运行时登录态；
- 原本写成 `${环境变量名}` 的字段，保存的仍是 `${环境变量名}`，不会把环境变量的值写进文件。

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

**配置了 cookies 还是没有登录态？**

先检查 cookies 的来源域名和实际访问的域名是否一致，再检查是否用的是移动端 `impl: api`（浏览器 cookies 对移动端无效）。

**配置了账号密码，直接用 client 时却没有登录？**

`new_jm_client()` 不会自动登录，先调用 `option.login_with_option_auth()`，见第 2.1 节。

**下载时提示需要登录，但我配置了 cookies 和账号密码？**

大概率是 cookies 过期了，而 jmcomic 认为已经登录，所以没有用账号密码重新登录。删掉 `auth.cookies`，只保留账号密码即可。
