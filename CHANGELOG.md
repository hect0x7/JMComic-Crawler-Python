# Changelog

本文件记录 jmcomic 的版本变化。2.7.0之前的changelog请见github release。

条目分类参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.7.4] - 2026-08-09

### Added
- 新增下载清单 `DownloadManifest`，聚合一次顶层下载产生的图片路径和导出文件。
- `DownloadResult` 新增 `manifest` 和 `duration` 属性，同时保持原有二元组解包兼容性。
- 搜索、分类和收藏夹分页结果新增 `page_number` 字段，可直接获取当前页码。

### Changed
- 同步与异步下载流程统一记录成功下载及缓存命中的图片，并使用图片插件处理后的最终保存路径。
- `result.duration` 记录从调用下载 API 到返回所用的总时间；本子、章节和图片实体分别记录各自的下载耗时。
- Feature 根据当前 `TaskContext` 判断顶层下载类型，不再需要额外传入 `feature_from`。
- ZIP、PDF 和长图插件产物按文件后缀登记到下载清单。
- 详情缓存返回独立干净副本，避免下载路径、耗时等状态污染后续缓存结果。
