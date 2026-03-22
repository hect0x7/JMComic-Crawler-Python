<!-- 顶部标题 & 统计徽章 -->
<div align="center">
  <h1 style="margin-top: 0" align="center">Python API for JMComic</h1>

  <p align="center">
    <strong>简体中文</strong> •
    <a href="./assets/readme/README-en.md">English</a> •
    <a href="./assets/readme/README-jp.md">日本語</a> •
    <a href="./assets/readme/README-kr.md">한국어</a>
  </p>

  <p align="center">
  <strong>提供 Python API 访问禁漫天堂（网页端 & 移动端），集成 GitHub Actions 下载器🚀</strong>
  </p>

[![GitHub](https://img.shields.io/badge/-GitHub-181717?logo=github)](https://github.com/hect0x7)
[![Stars](https://img.shields.io/github/stars/hect0x7/JMComic-Crawler-Python?color=orange&label=stars&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/stargazers)
[![Forks](https://img.shields.io/github/forks/hect0x7/JMComic-Crawler-Python?color=green&label=forks&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/forks)
[![GitHub latest releases](https://img.shields.io/github/v/release/hect0x7/JMComic-Crawler-Python?color=blue&label=version)](https://github.com/hect0x7/JMComic-Crawler-Python/releases/latest)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/jmcomic?style=flat&color=hotpink)](https://pepy.tech/projects/jmcomic)
[![Licence](https://img.shields.io/github/license/hect0x7/JMComic-Crawler-Python?color=red)](https://github.com/hect0x7/JMComic-Crawler-Python)

</div>


> 本项目封装了一套可用于爬取JM的Python API.
> 
> 你可以通过简单的几行Python代码，实现下载JM上的本子到本地，并且是处理好的图片。
> 
> **🧭 快速指路**
> - [教程：使用 GitHub Actions 下载禁漫本子](./assets/docs/sources/tutorial/1_github_actions.md)
> - [教程：导出并下载你的禁漫收藏夹数据](./assets/docs/sources/tutorial/10_export_favorites.md)
> - [塔台广播：欢迎各位机长加入并贡献代码](./.github/CONTRIBUTING.md)
> 
> **友情提示：珍爱JM，为了减轻JM的服务器压力，请不要一次性爬取太多本子，西门🙏🙏🙏**.
> 


![introduction.jpg](./assets/docs/sources/images/introduction.jpg)


## 项目介绍

本项目的核心功能是下载本子。

基于此，设计了一套方便使用、便于扩展，能满足一些特殊下载需求的框架。

目前核心功能实现较为稳定，项目也处于维护阶段。

除了下载功能以外，也实现了其他的一些禁漫接口，按需实现。目前已有功能：

- 登录
- 搜索本子（支持所有搜索项）
- 图片下载解码
- 分类/排行榜
- 本子/章节详情
- 个人收藏夹
- 接口加解密（APP的接口）

## 安装教程

> ⚠如果你没有安装过 Python，需要先前往 [Python 官网下载](https://www.python.org/downloads/) 再执行以下步骤。
>**推荐使用 Python 3.12及以上版本**

* 通过pip官方源安装（推荐，并且更新也是这个命令）

  ```shell
  pip install jmcomic -U
  ```
* 通过源代码安装

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```

## 快速上手

### 1. 下载本子方法

只需要使用如下代码，就可以下载本子`JM123`的所有章节的图片：

```python
import jmcomic  # 导入此模块，需要先安装.
jmcomic.download_album('123')  # 传入要下载的album的id，即可下载整个album到本地.
```

上面的 `download_album`方法还有一个参数`option`，可用于控制下载配置，配置包括禁漫域名、网络代理、图片格式转换、插件等等。

你可能需要这些配置项。推荐使用配置文件创建option，用option下载本子，见下章：

### 2. 使用option配置来下载本子

1. 首先，创建一个配置文件，假设文件名为 `option.yml`

   该文件有特定的写法，你需要参考这个文档 → [配置文件指南](./assets/docs/sources/option_file_syntax.md)

   下面做一个演示，假设你需要把下载的图片转为png格式，你应该把以下内容写进`option.yml`

```yml
download:
  image:
    suffix: .png # 该配置用于把下载的图片转为png格式
```

2. 第二步，运行下面的python代码

```python
import jmcomic

# 创建配置对象
option = jmcomic.create_option_by_file('你的配置文件路径，例如 D:/option.yml')
# 使用option对象来下载本子
jmcomic.download_album(123, option)
# 等价写法: option.download_album(123)
```

### 3. 使用命令行
> 如果只想下载本子，使用命令行会比上述方式更加简单直接
> 
> 例如，在windows上，直接按下 win+R 键，输入`jmcomic xxx`就可以下载本子。

示例：

下载本子123的命令

```sh
jmcomic 123
```
同时下载本子123, 章节456的命令
```sh
jmcomic 123 p456
```

命令行模式也支持自定义option，你可以使用环境变量或者命令行参数：

a. 通过命令行--option参数指定option文件路径

```sh
jmcomic 123 --option="D:/a.yml"
```

b. 配置环境变量 `JM_OPTION_PATH` 为option文件路径（推荐）

> 请自行google配置环境变量的方式，或使用powershell命令:  `setx JM_OPTION_PATH "D:/a.yml"` 重启后生效

```sh
jmcomic 123
```

### 4. 查看本子详情（jmv 命令）

> `jmv` 命令用于快速查看本子详情，不做下载。
> 
> **适用场景**：在某些网站上看到一串*神秘车号*，想快速看看具体是啥本子。此时只需copy原文本，按下 win+R，输入`jmv [粘贴内容]`即可
>
> 支持从任意文本中提取数字作为车号，方便直接粘贴各种格式的车号。

示例：

```sh
# 直接输入车号
jmv 350234

# 从混合文本中提取数字（提取出 350234）
jmv 350谁还没看过234

# 指定option文件（也支持环境变量，用法同上）
jmv 350234 --option="D:/a.yml"

# -y 参数：执行完毕后直接退出，无需按回车确认
jmv 350234 -y
```

输出效果：

```text
🔍 正在查询 禁漫车号 - [350234] 的详情...

──────────────────────────────────────────────────
  📖 标题:  xxx
  🆔 ID:    JM350234
  🔗 链接:  https://18comic.vip/album/350234/
  ✍️ 作者:  Author1, Author2
──────────────────────────────────────────────────
  📅 发布日期:  2022-06-15
  📅 更新日期:  2023-01-01
  📄 总页数:    50
  👀 观看:      2M
  ❤️ 点赞:     77K
  💬 评论:      9801
──────────────────────────────────────────────────
  🏷️ 标签:  标签1, 标签2, ...
  🎭 人物:  角色A, 角色B, ...
  📚 作品:  作品1, 作品2, ...
──────────────────────────────────────────────────
  📑 章节 (2):
     第1話  上  (id: 350234)
     第2話  下  (id: 350235)
──────────────────────────────────────────────────

[运行结束] 请按回车键关闭窗口... (下次运行可附加 -y 参数跳过确认)
```



## 进阶使用

请查阅文档首页 → [jmcomic.readthedocs.io](https://jmcomic.readthedocs.io/zh-cn/latest)

或者查看github仓库的文档 → [github-repo-docs](https://github.com/hect0x7/JMComic-Crawler-Python/blob/master/assets/docs/sources/tutorial/0_common_usage.md)

（提示：jmcomic提供了很多下载配置项，大部分的下载需求你都可以尝试寻找相关配置项或插件来实现。）

## 项目特点

- **绕过Cloudflare的反爬虫**
- **实现禁漫APP接口最新的加解密算法 (1.6.3)**
- 用法多样：

  - GitHub
    Actions：网页上直接输入本子id就能下载（[教程：使用GitHub Actions下载禁漫本子](./assets/docs/sources/tutorial/1_github_actions.md)）
  - 命令行：无需写Python代码，简单易用（[教程：使用命令行下载禁漫本子](./assets/docs/sources/tutorial/2_command_line.md)）
  - Python代码：最本质、最强大的使用方式，需要你有一定的python编程基础
- 支持**网页端**和**移动端**两种客户端实现，可通过配置切换（**移动端不限ip兼容性好，网页端限制ip地区但效率高**）
- 支持**自动重试和域名切换**机制
- **多线程下载**（可细化到一图一线程，效率极高）
- **可配置性强**

  - 不配置也能使用，十分方便
  - 配置可以从配置文件生成，支持多种文件格式
  - 配置点有：`请求域名` `客户端实现` `是否使用磁盘缓存` `同时下载的章节/图片数量` `图片格式转换` `下载路径规则` `请求元信息（headers,cookies,proxies)` `中文繁/简转换` 
    等
- **可扩展性强**

  - 支持自定义本子/章节/图片下载前后的回调函数
  - 支持自定义类：`Downloader（负责调度）` `Option（负责配置）` `Client（负责请求）` `实体类`等
  - 支持自定义日志、异常监听器
  - **支持Plugin插件，可以方便地扩展功能，以及使用别人的插件，目前内置插件有**：
    - `登录插件`
    - `硬件占用监控插件`
    - `只下载新章插件`
    - `压缩文件插件`
    - `客户端代理插件`
    - `下载特定后缀图片插件`
    - `发送QQ邮件插件`
    - `日志主题过滤插件`
    - `自动获取浏览器cookies插件`
    - `导出收藏夹为csv文件插件`
    - `合并所有图片为pdf文件插件`
    - `合并所有图片为长图png插件`
    - `网页观看本地章节插件`
    - `订阅更新插件`
    - `小章节跳过插件`
    - `重复文件检测删除插件`
    - `路径字符串替换插件`
    - `高级重试插件`
    - `封面下载插件`

## 使用小说明

* 推荐使用 **Python 3.12+**，目前最低兼容版本为3.9。
  > 注意：Python 3.9 及更早版本皆已于 2025 年彻底结束官方生命周期 (EOL)，使用3.9及以下随时有可能遇到第三方库不兼容的问题。

* 个人项目，文档和示例会有不及时之处，可以Issue提问。

## 项目文件夹介绍

* .github：GitHub Actions配置文件
* assets：存放一些非代码的资源文件

  * docs：项目文档
  * option：存放配置文件
* src：存放源代码

  * jmcomic：`jmcomic`模块
* tests：测试目录，存放测试代码，使用unittest
* usage：用法目录，存放示例/使用代码

## 感谢以下项目

### 图片分割算法代码+禁漫移动端API

<a href="https://github.com/tonquer/JMComic-qt">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
  </picture>
</a>
