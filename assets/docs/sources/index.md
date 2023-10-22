# jmcomic



## Features

- Bypasses Cloudflare anti-bot measures.
- Multiple usage options:
  - GitHub Actions: Requires only a GitHub account. See tutorial → [download_album_via_github_actions.md](./download_album_via_github_actions.md)).
  - Command line: No need to write Python code, simple and easy to use.
  - Python code: The most flexible and powerful method, requires some basic knowledge of Python programming.
- Supports two client implementations: web-based and mobile-based. Switchable through configuration (mobile-based has better IP compatibility, web-based has higher efficiency).
- Supports automatic request retry and domain switching mechanism.
- Multi-threaded downloading (can be fine-tuned to one thread per image, highly efficient).
- Highly configurable:
  - Can be used without configuration, very convenient.
  - Configuration can be generated from a configuration file, supports multiple file formats.
  - Configuration options include: `request domain`, `client implementation`, `number of chapters/images downloaded simultaneously`, `image format conversion`, `download path rules`, `request metadata (headers, cookies, proxies)`, and more.
- Highly extensible:
  - Supports Plugin plugins for easy functionality extension and use of other plugins.
    - Currently built-in plugins: `login plugin`, `hardware usage monitoring plugin`, `only download new chapters plugin`, `zip compression plugin`.
  - Supports custom callback functions before and after downloading album/chapter/images.
  - Supports custom debug logging.
  - Supports custom classes: `Downloader (responsible for scheduling)`, `Option (responsible for configuration)`, `Client (responsible for requests)`, `entity classes`, and more.



## Install

- Install via official pip source (recommended, and also used for updates):

  ```shell
  pip install jmcomic -i https://pypi.org/project --upgrade
  ```

- Install via GitHub code:

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```



## Usage

1. The simplest way to use:

* Python code

```python
import jmcomic
# Pass the ID of the album you want to download, and it will download all chapters of the album to your local machine.
jmcomic.download_album('422866')
```

* Command line

```shell
jmcomic 422866
```



2. Customize the downloading behavior using an option: 

For example, if you want to convert all downloaded images to the .jpg format, you can create a YAML file with the following content (refer to [option file syntax](./option_file_syntax.yml)):

```yml
download:
  image:
    suffix: .jpg # Don't forget the '.'
```

Then, use one of the following ways:

* Python code

```python
from jmcomic import download_album, create_option
option = create_option('/path/to/your/optionfile')
download_album('422866', option)
```

* Command line

```shell
jmcomic 422866 --option="/path/to/your/optionfile"
```





## Acknowledgement

### Image Segmentation Algorithm Code + JMComic Mobile API

[![Readme Card](https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt)](https://github.com/tonquer/JMComic-qt)





