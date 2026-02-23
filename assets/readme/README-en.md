<!-- 顶部标题 & 统计徽章 -->
<div align="center">
  <h1 style="margin-top: 0" align="center">Python API for JMComic</h1>

  <p align="center">
    <a href="../../README.md">简体中文</a> •
    <strong>English</strong> •
    <a href="./README-jp.md">日本語</a> •
    <a href="./README-kr.md">한국어</a>
  </p>

  <p align="center">
  <strong>Provide Python API to access JMComic (Web & Mobile), integrates GitHub Actions downloader🚀</strong>
  </p>

[![GitHub](https://img.shields.io/badge/-GitHub-181717?logo=github)](https://github.com/hect0x7)
[![Stars](https://img.shields.io/github/stars/hect0x7/JMComic-Crawler-Python?color=orange&label=stars&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/stargazers)
[![Forks](https://img.shields.io/github/forks/hect0x7/JMComic-Crawler-Python?color=green&label=forks&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/forks)
[![GitHub latest releases](https://img.shields.io/github/v/release/hect0x7/JMComic-Crawler-Python?color=blue&label=version)](https://github.com/hect0x7/JMComic-Crawler-Python/releases/latest)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/jmcomic?style=flat&color=hotpink)](https://pepy.tech/projects/jmcomic)
[![Licence](https://img.shields.io/github/license/hect0x7/JMComic-Crawler-Python?color=red)](https://github.com/hect0x7/JMComic-Crawler-Python)

</div>




> This project encapsulates a Python API for crawling JM.
> 
> With a few simple lines of Python code, you can download albums from JM to your local machine, with properly processed images.
> 
> **🧭 Quick Guide**
> - [Tutorial: Downloading JM Albums using GitHub Actions](../docs/sources/tutorial/1_github_actions.md)
> - [Tutorial: Exporting and downloading your JM favorites data](../docs/sources/tutorial/10_export_favorites.md)
> - [Tower Broadcast: Welcome captains to join and contribute code](../../.github/CONTRIBUTING.md)
> 
> **Friendly Prompt: Cherish JM. In order to reduce the pressure on JM servers, please do not download too many albums at once 🙏🙏🙏.**


![introduction.jpg](../docs/sources/images/introduction.jpg)


## Introduction

The core function of this project is to download albums.

Based on this, an easy-to-use, highly extensible framework is designed to meet various download requirements.

Currently, the core functions are relatively stable, and the project is in the maintenance phase.

In addition to downloading, other JM interfaces are also implemented on demand. Existing features:

- Login
- Search albums (supports all search parameters)
- Image downloading and decoding
- Categories/Rankings
- Album/Chapter details
- Personal favorites
- Interface encryption and decryption (for the APP API)

## Installation Guide

> ⚠ If you have not installed Python, you must install Python before executing the following steps. [Download from Python Official Site](https://www.python.org/downloads/)
> **Version 3.12+ is recommended.**

* Install via official pip source (recommended, the update command is identical)

  ```shell
  pip install jmcomic -U
  ```
* Install from source code

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```

## Quick Start

### 1. Downloading an album

All you need is the following code to download all chapter images of the album `JM123`:

```python
import jmcomic  # Import this module, you need to install it first.
jmcomic.download_album('123')  # Pass the ID of the album to download the entire album locally.
```

The `download_album` method above also accepts an `option` parameter to control the configuration, which includes JM domain names, network proxies, image format conversions, plugins, and more.

You might need these options. It is recommended to create an option instance from a configuration file and use it to download albums, as shown in the next section:

### 2. Using option for advanced downloading

1. First, create a configuration file, let's say `option.yml`

   This file uses a specific format, please refer to the documentation → [Configuration File Guide](../docs/sources/option_file_syntax.md)

   Here is a demonstration. Assuming you want to convert the downloaded images into `png` format, you should write the following into `option.yml`:

```yml
download:
  image:
    suffix: .png # This option converts the downloaded image to png format
```

2. Secondly, run the following Python code

```python
import jmcomic

# Create configuration object
option = jmcomic.create_option_by_file('Path to your configuration file, e.g. D:/option.yml')
# Download the album using the option configured
jmcomic.download_album(123, option)
# Equivalent to: option.download_album(123)
```

### 3. Using the Command Line
> If your only goal is to download albums, using the command line is simpler and more straightforward.
> 
> For example, on Windows, press `Win + R`, enter `jmcomic xxx`, and you can download the album.

Examples:

Command to download album 123:

```sh
jmcomic 123
```

Command to download chapter 456 of album 123:
```sh
jmcomic 123 p456
```

The command-line mode also supports custom options. You can use environment variables or command line arguments:

a. Specify the option file path via `--option` argument

```sh
jmcomic 123 --option="D:/a.yml"
```

b. Set the environment variable `JM_OPTION_PATH` to the option file path (recommended)

> Please Google how to configure environment variables. By using powershell: `setx JM_OPTION_PATH "D:/a.yml"` (Requires a restart to take effect).

```sh
jmcomic 123
```



## Advanced Usage

Please check the documentation homepage → [jmcomic.readthedocs.io (Chinese language)](https://jmcomic.readthedocs.io/zh-cn/latest)

*(Tip: jmcomic provides many options. For most download requirements, you can find a corresponding configuration or plugin setup.)*

## Key Features

- **Bypass Cloudflare anti-bot mechanisms**
- **Implement the latest decryption logic for the JM APP API (1.6.3)**
- Multiple usages:

  - GitHub Actions: Enter the album ID directly on the webpage to download ([Tutorial: Download JM Albums using GitHub Actions](../docs/sources/tutorial/1_github_actions.md))
  - Command Line: No need to write Python code, easy to use ([Tutorial: Download JM Albums by Command Line](../docs/sources/tutorial/2_command_line.md))
  - Python Code: The most powerful usage, requiring basic Python programming knowledge
- Supports both **Web** and **Mobile** implementations, switchable via configuration (**Mobile is IP restriction-free and very compatible, Web restricts some IP regions but offers higher efficiency**)
- Built-in **auto-retry and domain switching** mechanisms
- **Multi-threaded downloading** (can be fine-tuned to one-thread-per-image, greatly boosting speed)
- **Highly configurable**

  - Can work smoothly out of the box without configurations
  - Supported formats to generate `Option` instances
  - Configurable items include: `Domains` `Clients` `Disk Caching` `Concurrent chapters/images downloads` `Format Conversions` `Path rules` `Request Meta (headers, cookies, proxies)` `Simplified/Traditional Chinese Conversion`, etc.
- **Highly Extensible**

  - Supports custom callbacks before/after downloading albums/chapters/images
  - Customizable objects: `Downloader` `Option` `Client` `Entities`, etc.
  - Supports custom logging and exception listener mechanics
  - **Embedded with powerful Plugins** to easily extend features or inject others':
    - `Login Plugin`
    - `Hardware usage monitor plugin`
    - `Filter-new-chapter plugin`
    - `Zip-files plugin`
    - `Client proxy plugin`
    - `Specific image suffix format downloader`
    - `Send via QQ Mail plugin`
    - `Log topic filter plugin`
    - `Auto fetch browser cookies plugin`
    - `Export favorites to CSV plugin`
    - `Merge images into PDF plugin`
    - `Merge images into Long png plugin`
    - `Local chapter web-viewer plugin`
    - `Subscribe album update plugin`
    - `Skip small chapters plugin`
    - `Duplicate detection and deletion plugin`
    - `Path string replacement plugin`
    - `Advanced retry plugin`
    - `Download cover plugin`

## Prerequisites

* Version **3.12+** is recommended, with a minimum compatible version of 3.9.
  > Note: Python 3.9 and earlier versions reached their End Of Life (EOL) in 2025. You may encounter third-party library incompatibilities at any time if you use version 3.9 or below.

* Since this is a personal project, the documentation/examples may occasionally be out of sync. Please feel free to open an Issue for any clarifications.

## Directory Structure

* `.github`: GitHub Actions configuration files
* `assets`: Resources aside from pure code
  * `docs`: Documentation
  * `option`: Test/example configurations
* `src`: Main code base
  * `jmcomic`: Core `jmcomic` package
* `tests`: Unit tests relying on `unittest`
* `usage`: Examples of usage implementations

## Acknowledgments

### Image Segmentation logic + JM Mobile APIs Support

<a href="https://github.com/tonquer/JMComic-qt">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
  </picture>
</a>
