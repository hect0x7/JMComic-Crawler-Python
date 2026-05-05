# Feature 机制——下载附加行为

## 1. 需求场景

下载本子后，很多用户有进一步导出的需求：
- 导出为 **PDF**：方便在电子阅读器上查看
- 导出为 **ZIP**：方便传输和存档
- 合并为 **长图**：方便一张图看完整个章节

jmcomic 一直通过内置插件（`img2pdf`、`zip`、`long_img`）支持这些功能，但传统方式需要在 YAML 配置文件中编写插件配置，门槛偏高。

从最新版本起，jmcomic 引入了 **Feature（特性）** 机制——一套通用的**下载附加行为系统**，让你用一行代码搞定导出。Feature 不仅能调用插件，还能封装任意自定义逻辑（通知、清理等），并且会根据调用方式自动选择最合理的配置。

内置了三个开箱即用的导出 Feature：

| Feature | 效果 |
|---------|------|
| `Feature.export_pdf` | 下载完自动导出为 PDF |
| `Feature.export_zip` | 下载完自动打包为 ZIP |
| `Feature.export_long_img` | 下载完自动拼接为长图 PNG |

## 2. 快速上手

### 2.1 导出 PDF——基本用法示例

```python
from jmcomic import download_album, Feature

# 只需要加一个 extra 参数，就能在下载完成后自动导出 PDF
download_album('123', option, extra=Feature.export_pdf)
```

效果：在**当前工作目录**下生成以本子标题命名的 PDF 文件：

```
./
├── [本子标题].pdf       ← 整本合并为 1 个 PDF
```

### 2.2 需要多种导出格式（PDF、ZIP）——直接组合 Feature

用 `+` 号组合，同时导出多种格式：

```python
# 下载完后同时导出 PDF 和 ZIP
download_album('123', option, extra=Feature.export_pdf + Feature.export_zip)

# 也支持列表语法
download_album('123', option, extra=[Feature.export_pdf, Feature.export_zip])
```

### 2.3 自定义参数

像调用函数一样传入自定义参数，可以改变输出目录、命名规则等：

```python
# 示例 1：指定输出目录和命名规则
download_album('123', option, extra=Feature.export_pdf(
    pdf_dir='D:/my_pdfs',          # PDF 保存到 D:/my_pdfs 文件夹
    filename_rule='Ptitle',        # 用章节标题作为文件名
    delete_original_file=True,     # 合并完 PDF 后删除原图
))

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

效果：在当前工作目录下生成以章节标题命名的 PDF：

```
./
├── [章节标题].pdf       ← 该章节导出为 1 个 PDF
```

> 💡 **提示**：同一个 Feature，通过 `download_album` 和 `download_photo` 调用时会自动适配不同的导出行为，详见下方 [智能适配规则](#智能适配规则)。

### 2.5 智能适配规则

内置的导出 Feature 会根据调用的 API **自动适配**参数（命名规则、打包级别等）：

| 调用方式 | Feature.export_pdf | Feature.export_zip | Feature.export_long_img |
|---------|-------------------|-------------------|----------------------|
| `download_album` | 整本合并为 1 个 PDF<br>`[本子标题].pdf` | 整本打包为 1 个 ZIP<br>`[本子标题].zip` | 所有章节合并为 1 张长图<br>`[本子ID].png` |
| `download_photo` | 该章节导出为 PDF<br>`[章节标题].pdf` | 该章节打包为 ZIP<br>`[章节标题].zip` | 该章节拼接为长图<br>`[章节ID].png` |

当你显式传入参数时（如 `filename_rule='Ptitle'`），**你的配置优先**，不会被自适应覆盖。

> 💡 **提示**：更多可选参数（如加密密码 `encrypt`、后缀名 `suffix` 等），参考 [Plugin 插件参数大全](./6_plugin.md#参数)。

## 3. 传统写法（YAML 插件配置）

如果你更习惯配置文件，仍然可以使用传统的插件配置方式：

```yaml
# option.yml
plugins:
  after_album:
    - plugin: img2pdf
      kwargs:
        pdf_dir: ./output
        filename_rule: Atitle
    - plugin: zip
      kwargs:
        level: album
        zip_dir: ./output
```

传统写法的更多细节见 → [Plugin 插件教程](./6_plugin.md)

## 4. Feature 架构设计

### 类层次

```
Feature (基类)
  ├── PluginFeature     ← 封装插件调用，参数根据来源自适应
  └── 你的自定义 Feature  ← 继承 Feature，实现任意逻辑
```

- **Feature 基类**：通用的附加行为抽象，不绑定任何具体实现。默认在所有生命周期钩子中执行。
- **PluginFeature**：Feature 的子类，专门封装 jmcomic 插件。除了调用插件之外，还会根据调用来源动态适配 `filename_rule`、`level` 等参数。

### 执行流程

Feature **自然嵌入到 downloader 的生命周期钩子**中自动触发：

```
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
       │    ├→ download images ...
       │    └→ after_photo(photo)
       │         └→ _invoke_features_for('after_photo')
       │              └→ pdf.should_invoke('after_photo', 'download_album') → False ✗ 跳过
       │
       └→ after_album(album)
            └→ _invoke_features_for('after_album')
                 └→ pdf.should_invoke('after_album', 'download_album') → True ✓ 执行!
                      └→ _adapt_kwargs('download_album')
                           # Atitle 不变, Ptitle→Atitle, Pid→Aid, level→album
```

> 💡 **关键点**：
>
> - **执行时机**：`PluginFeature` 根据注册来源自动推导（`download_album` → `after_album`，`download_photo` → `after_photo`）。自定义 Feature 默认在所有钩子都会执行，你可以覆写 `should_invoke` 来控制。
> - **参数自适应**：`PluginFeature` 的 `filename_rule` 前缀（A/P）和 `level`（album/photo）会根据来源动态适配。用户显式传入的参数不会被覆盖。

### 自定义 Feature

Feature 基类完全不绑定插件，你可以实现任意逻辑：

```python
from jmcomic import Feature, download_album

class NotifyFeature(Feature):
    """下载完成后发送通知"""
    def invoke(self, option, **context):
        album = context.get('album')
        if album:
            print(f'下载完成通知: {album.name}')

# 使用
download_album('123', option, extra=NotifyFeature())
```

### 自定义 PluginFeature

如果你注册了自定义插件，也可以创建对应的 PluginFeature：

```python
from jmcomic import PluginFeature, Feature

# 假设你注册了一个 plugin_key 为 'my_export' 的插件
Feature.my_export = PluginFeature('my_export', output_dir='./my_output')

# 使用
download_album('123', option, extra=Feature.my_export)
```
