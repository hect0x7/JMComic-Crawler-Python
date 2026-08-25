# Changelog

本文件记录 jmcomic 的版本变化。2.7.0 之前的更新记录请见 GitHub Releases。

条目分类参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.7.5] - 2026-08-25

### Summary

本次更新修复网页端收藏夹总数误解析，并同步禁漫 APP 2.1.2 的移动端版本号。

### Fixed
- 修复收藏夹页面改版后，总数正则优先命中 CSS 尺寸、导致 `JmHtmlClient.favorite_folder().total` 错误返回 `50` 的问题。

### Changed
- 更新禁漫移动端版本号至 `2.1.2`。
- `RequestRetryAllFailException` 现在会保留并输出各域名、各次重试的原始异常，便于定位真实失败原因。

## [2.7.4] - 2026-08-09

### Summary

本次更新让同步和异步下载进度更直观、下载结果更易处理，还可以分页浏览全站评论并直接获取当前页码。

### Added
- 新增 `download_progress` 插件：`jmcomic` 命令安装 `rich` 后默认启用，可通过 `--no-progress` 关闭自动启用；同步和异步下载在交互终端中默认展示最近 6 条日志，并在下方显示彩色的本子、章节两级进度；支持通过 `log_file` 和 `terminal_log_lines` 自定义日志文件与终端日志行数；IDE 运行面板等不支持动态界面的环境只在结束后输出汇总；完整日志写入文件且不再重复输出 `INFO` 字段。

![download_progress 插件效果](https://raw.githubusercontent.com/hect0x7/JMComic-Crawler-Python/v2.7.4/assets/docs/sources/images/download_progress_terminal.png)

- 新增下载清单 `DownloadManifest`，聚合一次顶层下载产生的图片路径和导出文件。
- `DownloadResult` 新增 `manifest` 和 `duration` 属性，同时保持原有二元组解包兼容性。
- 新增获取全站评论分页及生成器 API，支持 HTML、API 和异步 API 客户端。
- 搜索、分类、收藏夹和评论分页结果新增 `page_number` 字段，可直接获取当前页码。
- GitHub Actions 下载支持压缩图片，减少最终压缩包体积。

### Changed
- `JmDownloader.use()` 和 `JmAsyncDownloader.use()` 现在会记录替换前后的 Downloader class，异步下载 API 也会使用已替换的默认异步 Downloader。
- 同步与异步下载流程统一记录成功下载及缓存命中的图片，并使用图片插件处理后的最终保存路径。
- `result.duration` 记录从调用下载 API 到返回所用的总时间；本子、章节和图片实体分别记录各自的下载耗时。
- Feature 根据当前 `TaskContext` 判断顶层下载类型，不再需要额外传入 `feature_from`。
- ZIP、PDF 和长图插件产物按文件后缀登记到下载清单。
- 详情缓存返回独立干净副本，避免下载路径、耗时等状态污染后续缓存结果。
- `JmAlbumComment` 新增可读的字符串输出，支持直接打印评论。
- 完善 HTML 评论解析，补齐全站评论中的本子 ID 和用户 ID。
- 全站评论生成器分别使用 API 总页数和 HTML 重复页判断结束，避免两类响应混用同一停止条件。
- 使用 `--no-progress` 但 Option 已配置 `download_progress` 时，在固定启动面板中显示冲突提醒。
- GitHub Release 改为从对应版本的 `CHANGELOG.md` 生成发布说明，并支持手动触发发布流程。
- 重写下载返回值与异步下载文档，统一使用同时兼容 GitHub 和 MkDocs 的提示及折叠语法。
- 综合插件示例并入插件教程，移除使用价值较低的“模块自定义”教程，并将日志接管方式迁移到日志教程。

### Removed
- 按照弃用计划移除 `jmcomic.cl` 兼容模块，请使用 `jmcomic.cli`。

## [2.7.3] - 2026-08-03

### Added
- 新增获取本子评论的 API。
- 新增任务上下文，可按任务维度标记、传播和收集日志。

### Changed
- 精简下载 API 参数。
- 兼容 `jm-view-server` 项目改名。
- 完善任务日志及下载 API 使用文档。

## [2.7.2] - 2026-07-16

### Added
- 异步 API 新增 `categories_filter_gen`。

### Changed
- 更新 JM 内置域名。
- 完善异步 API、测试和异步使用文档。

### Removed
- 移除已经失效的 GitHub 域名抓取实现。

## [2.7.1] - 2026-07-04

### Changed
- 优化异步请求的重试配置。
- 调整批量下载返回值类型。
- `IndexedEntity` 继承 `Sequence`，支持标准切片协议。
- 更新 README 导览图。

## [2.7.0] - 2026-06-15

### Added
- 新增完整的异步 Client、Downloader 和下载 API。
- HTML 正则解析失败时自动保存网页内容，方便定位解析问题。
- 新增同步与异步下载性能 Benchmark。

### Changed
- 补充异步 API 相关文档并优化既有文档。
