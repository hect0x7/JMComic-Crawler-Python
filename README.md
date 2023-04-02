# Python API For JMComic (禁漫天堂)

封装了一套可用于爬取JM的Python API.

简单来说，就是可以通过简单的几行Python代码，实现下载JM上的本子到本地，并且是处理好的图片.

**友情提示：珍爱JM，为了减轻JM的服务器压力，请不要一次性爬取太多本子，西门🙏🙏🙏**.

## 安装教程

* 通过pip官方源安装（推荐）

  ```shell
  pip install jmcomic -i https://pypi.org/project --upgrade
  ```
* 本地安装

  ```shell
  cd ./modules/core/
  pip install -e ./
  ```

## 快速上手

使用下面的两行代码，即可实现功能：把某个本子集（album）里的所有本子（photo）下载到本地

```python
import jmcomic  # 导入此模块，需要先安装.
jmcomic.download_album('422866')  # 传入要下载的album的id，即可下载整个album到本地.
# 上面的这行代码，还有一个可选参数option: JmOption，表示配置项，
# 配置项的作用是告诉程序下载时候的一些选择，
# 比如，要下载到哪个文件夹，使用怎样的路径组织方式（比如[/作者/本子id/图片] 或者 [/作者/本子名称/图片]）.
# 如果没有配置，则会使用 JmOption.default()，下载的路径是[当前工作文件夹/本子名称/图片].
```

进一步的使用可以参考usage文件夹下的示例代码: `jmcomic_getting_started.py` `jmcomic_usage.py`

## 项目特点

- **绕过Cloudflare的反爬虫**
- 支持使用**Github Action**下载漫画，不会编程都能用（[教程：使用Github Actions下载禁漫本子](./assets/docs/教程：使用Github%20Actions下载禁漫本子.md)）
- 可配置性强

  - 不配置也能使用，十分方便
  - 配置可以从**配置文件**生成，无需写Python代码
  - 配置点有：`是否使用磁盘缓存`  `是否使用代理` `图片类型转换` `本子下载路径` `请求元信息（headers,cookies,重试次数）等 `
- 多线程下载（可细化到一图一线程，效率极高）
- 跟进了JM最新的图片分割算法（2023-02-08）

## 使用小说明

* Python >= 3.7
* 项目只有代码注释，没有API文档。因此想深入高级地使用，自行看源码和改造代码叭 ^^_
* JM不是前后端分离的网站，因此本api是通过正则表达式解析HTML网页的信息（详见`JmcomicText`），进而实现的下载图片。

## 项目文件夹介绍

* assets：存放一些非代码的资源文件

  * config：存放配置文件
  * docs：项目文档
* src：存放源代码

  * jmcomic：`jmcomic`模块
* tests：测试目录，存放测试代码，使用unittest
* usage：用法目录，存放示例/使用代码

## 感谢以下项目

### 图片分割算法的来源

[![Readme Card](https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt)](https://github.com/tonquer/JMComic-qt)
