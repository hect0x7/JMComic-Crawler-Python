# 教程：下载后转为 PDF / ZIP / 长图

## 1. 需求场景

下载本子后，很多用户有进一步导出的需求：
- 导出为 **PDF**：方便在电子阅读器上查看
- 导出为 **ZIP**：方便传输和存档
- 合并为 **长图**：方便一张图看完整个章节

jmcomic 内置了三个开箱即用的导出 Feature，对应这三种需求：

| Feature | 效果 |
|---------|------|
| `Feature.export_pdf` | 下载完自动导出为 PDF |
| `Feature.export_zip` | 下载完自动打包为 ZIP |
| `Feature.export_long_img` | 下载完自动拼接为长图 PNG |


> 也许你知道，这些功能之前是以插件形式 (JmOptionPlugin) 存在的。
> 
> 是的，传统方式需要在 option 配置文件中编写插件配置，门槛偏高。
> 
> 因此，从v2.6.19起，jmcomic 引入了上述的 **Feature** 机制，尽可能简化这些最常用的功能，让小白也能用一行代码搞定导出。


## 2. 快速上手

### 2.1 导出 PDF——基本用法示例

```python
from jmcomic import download_album, Feature

# 只需要加一个 extra 参数，就能在下载完成后自动导出 PDF
download_album('123', extra=Feature.export_pdf)

# 如果要传 option 参数，就是如下写法，三个参数
download_album('123', option, extra=Feature.export_pdf)
```

**效果**：在本子下载完以后，默认在**下载根目录**下生成包含所有本子图片的 PDF 文件。如果你没有自定义过option，下载根目录就是你的工作目录（即你运行python脚本或cli的目录）。如果你配置过option，会放在dir_rule.base_dir下面。

```text
./
├── [JM123]本子标题.pdf       ← 整本合并为 1 个 PDF，注意pdf文件名的格式，默认包含本子禁漫车号+本子标题
```

### 2.2 需要多种导出格式（PDF、ZIP等）——直接组合 Feature

用 `+` 号组合，同时导出多种格式：

```python
# 下载完后同时导出 PDF 和 ZIP
download_album('123', option, extra=Feature.export_pdf + Feature.export_zip)

# 也支持列表语法，|语法
download_album('123', option, extra=[Feature.export_pdf, Feature.export_zip])
download_album('123', option, extra=Feature.export_pdf | Feature.export_zip)
```

效果同pdf，会在本子下载完以后，额外在对应的下载目录下，生成包含所有本子图片的 PDF 文件和 ZIP 文件：

```text
./
├── [JM123]本子标题.pdf       ← 整本合并为 1 个 PDF
├── [JM123]本子标题.zip       ← 整本合并为 1 个 zip 压缩包
```


### 2.3 自定义参数

如果你了解插件配置，可以同样使用Feature传递插件的自定义参数，例如改变输出目录、命名规则等：

```python
# 示例 1：指定输出目录和命名规则
download_album('123', option, extra=Feature.export_pdf(
    # 下面是自定义参数
    pdf_dir='D:/my_pdfs',          # PDF 保存到 D:/my_pdfs 文件夹
    filename_rule='Atitle',        # 用本子标题作为文件名
    delete_original_file=True,     # 合并完 PDF 后删除原图
))
```

> 💡 **小白必读：命名规则（filename_rule）的小知识**
> - `A` 开头的占位符（如 `Atitle`, `Aid`）代表 **Album (本子)**。
> - `P` 开头的占位符（如 `Ptitle`, `Pid`）代表 **Photo (章节)**。
> - `download_photo` （下载单章）时，由于程序既知道当前章节，也知道它属于哪个本子，所以 **`Pxxx` 和 `Axxx` 都可以用**。
> - `download_album` （下载整本）时，由于是按本子合并的，程序没有具体的“当前章节”，此时 **只能用 `Axxx`，不能用 `Pxxx`**，否则会报错。

```python
# 示例 2：全都要——ZIP 存盘 + 长图阅读
combo = (
    Feature.export_zip(zip_dir='D:/zips')
    + Feature.export_long_img(img_dir='D:/long_imgs')
)
download_album('123', option, extra=combo)
```

### 2.4 download_photo 也支持

```python
from jmcomic import download_photo, Feature

# 对单个章节导出
download_photo('456', option, extra=Feature.export_pdf)
```

效果：在对应的下载目录下生成以章节标题命名的 PDF：

```text
./
├── [JM{Pid}]章节标题.pdf       ← 该章节导出为 1 个 PDF
```

> 💡 **提示**：同一个 Feature，通过 `download_album` 和 `download_photo` 调用时会自动适配不同的导出行为，详见下方 [智能适配规则](#25-智能适配规则)。

### 2.5 智能适配规则

内置的导出 Feature 会根据调用的 API **自动适配**参数：

| 调用方式            | Feature.export_pdf | Feature.export_zip | Feature.export_long_img |
|-----------------|-------------------|-------------------|----------------------|
| `download_album` | 整本合并为 1 个 PDF<br>`[JM本子号]本子标题.pdf` | 整本打包为 1 个 ZIP<br>`[JM本子号]本子标题.zip` | 所有章节合并为 1 张长图<br>`[JM本子号]本子标题.png` |
| `download_photo` | 该章节导出为 PDF<br>`[JM章节号]章节标题.pdf` | 该章节打包为 ZIP<br>`[JM章节号]章节标题.zip` | 该章节拼接为长图<br>`[JM章节号]章节标题.png` |

当你显式传入参数时（如 `filename_rule='Ptitle'`），**你的配置优先**，不会被自适应覆盖。

> 💡 **提示**：更多可选参数（如加密密码 `encrypt`、后缀名 `suffix` 等），参考 [Plugin 插件参数大全](../option_file_syntax.md#3-option插件配置项)。

## 3. 传统写法（YAML 插件配置）

如果你更习惯配置文件，仍然可以使用传统的插件配置方式：

```yaml
# option.yml
plugins:
  after_album: # 整本下载完以后
    - plugin: img2pdf # 合并pdf
      kwargs:
        pdf_dir: ./output
        filename_rule: Atitle
    - plugin: zip # 合并为压缩文件
      kwargs:
        level: album
        zip_dir: ./output
```

传统写法的更多细节见 → [Plugin 插件教程](./6_plugin.md)

## 4. Feature 架构设计

### 类层次

```text
Feature (基类)
  ├── PluginFeature     ← 封装插件调用，参数根据来源自适应
  └── 你的自定义 Feature  ← 继承 Feature，实现任意逻辑
```

- **Feature 基类**：通用的附加行为抽象，不绑定任何具体实现。默认在所有生命周期钩子中执行。
- **PluginFeature**：Feature 的子类，专门封装 jmcomic 插件。除了调用插件之外，还会根据调用来源动态适配 `filename_rule` 参数；ZIP 的打包粒度则由插件在运行时根据上下文自动推导。

### 执行流程

Feature **自然嵌入到 downloader 的生命周期钩子**中自动触发：

```text
api.download_album(extra=Feature.export_pdf)
  │
  ├→ dler.add_features(pdf, 'download_album')   # 注册: [(pdf, 'download_album')]
  │
  └→ dler.download_album(id)
       │
       ├→ before_album(album)
       │
       ├→ download_by_photo_detail(photo)
       │    ├→ before_photo(photo)
       │    ├→ download jmcomic images ...      # 下载禁漫图片
       │    └→ after_photo(photo)
       │         └→ _invoke_features_for('after_photo')
       │              └→ pdf.should_invoke('after_photo', 'download_album') → False ✗ 跳过
       │
       └→ after_album(album)
            └→ _invoke_features_for('after_album')
                 └→ pdf.should_invoke('after_album', 'download_album') → True ✓ 执行!
                      └→ _adapt_plugin_kwargs(from, when) # 动态生成插件参数
                           └→ option.invoke(pdf, kwargs) # 调用pdf插件，传入参数
```

> 💡 **关键点**：
>
> - **执行时机**：`PluginFeature` 根据注册来源自动推导（`download_album` → `after_album`，`download_photo` → `after_photo`）。自定义 Feature 默认在所有钩子都会执行，你可以覆写 `should_invoke` 来控制。
> - **参数自适应**：`PluginFeature` 的 `filename_rule` 前缀（A/P）会根据来源动态适配。ZIP 的打包粒度由插件根据上下文自动推导。用户显式传入的参数不会被覆盖。

### 自定义 Feature

Feature 基类完全不绑定插件，你可以实现任意逻辑，欢迎贡献你的feature到本项目中：

```python
from jmcomic import Feature, download_album

class NotifyFeature(Feature):
    """下载完成后发送通知"""
    def invoke(self, option, **kwargs):
        album = kwargs.get('album')
        if album:
            print(f'下载完成通知: {album.name}')

# 使用
download_album('123', option, extra=NotifyFeature())
```

