# 自定义下载文件夹名

## 0. 最简单直接粗暴有效的方式

使用插件`replace_path_string`：

这个插件可以直接替换下载文件夹路径，配置示例如下（把如下配置放入option配置文件即可）：

```yml
plugins:
  after_init:
    - plugin: replace_path_string
      kwargs:
        replace: 
          # {左边写你要替换的原文}: {右边写替换成什么文本}
          kyockcho: きょくちょ
```
该示例会把文件夹路径中所有`kyockcho`都变为`きょくちょ`，例如：

`D:/a/[kyockcho]本子名称 - kyockcho/` 改为↓

`D:/a/[きょくちょ]本子名称 - きょくちょ/` 

---------------
**_如果上述简单的文本替换无法满足你，或者你需要更灵活的组合逻辑，那么下面的 f-string 语法正适合你。_**

## 1. DirRule 与 f-string 语法

当你使用 `download_album` 下载本子时，本子会以一定的路径规则（DirRule）下载到你的磁盘上。

路径规则通过 `dir_rule.rule` 配置，支持 **f-string 模板语法**，你可以用 `{变量名}` 自由组合出想要的文件夹名。

### 1.1 快速上手

```yaml
dir_rule:
  base_dir: D:/a/b/c/
  # 使用 f-string 模板：本子标题作为文件夹名
  rule: Bd / {Atitle}
```

上例表示把图片下载到 `{base_dir}/{本子标题}/` 下。假设本子标题为「社团学姐」，下载结果为：

```
D:/a/b/c/社团学姐/00001.webp
D:/a/b/c/社团学姐/00002.webp
...
```

### 1.2 语法规则

`rule` 由 **分隔符** 切分为多个"片段"，每个片段独立解析后按 `/` 拼接成最终路径：

- 使用 `/` 分隔（推荐）：`Bd / {Atitle} / {Pname}`
- 使用 `_` 分隔（兼容旧写法）：`Bd_{Atitle}_{Pname}`

> [!IMPORTANT]
> `/` 和 `_` **二选一**，不可混用。含 `/` 时按 `/` 切分，不含 `/` 时按 `_` 切分。
> 
> 如果你的文件夹名本身需要包含 `_`，请使用 `/` 作为分隔符，例如：`Bd / {Aid}_{Atitle}`

每个片段中使用 `{变量名}` 引用实体属性，变量名由 **前缀 + 属性名** 组成：

| 前缀 | 含义 | 对应实体类 |
|:---:|:---|:---|
| `A` | 本子（Album）| `JmAlbumDetail` |
| `P` | 章节（Photo）| `JmPhotoDetail` |

例如 `{Atitle}` = 本子的 title，`{Pname}` = 章节的 name。

特殊片段 `Bd` 代表 `base_dir`（根目录），通常放在最前面，也可以省略（会自动补上）。

### 1.3 f-string 示例

```yaml
# ✅ 本子ID + 本子标题
rule: Bd / {Aid}-{Atitle}
# 结果: D:/a/b/c/248965-社团学姐/

# ✅ 【作者】原始名称
rule: Bd / {Aauthoroname}
# 结果: D:/a/b/c/【BLVEFO9】喂我吃吧 老師!/

# ✅ 带本子ID的两级目录（本子 → 章节）
rule: Bd / [{Aid}]{Atitle} / 第{Pindex}話
# 结果: D:/a/b/c/[248965]社团学姐/第3話/

# ✅ JM车号 + 章节标题
rule: Bd / JM{Aid} / {Pname}
# 结果: D:/a/b/c/JM248965/第3话 xxx/

# ✅ 复合格式：作者-ID-原始名称
rule: Bd / {Aauthor}-{Aid}-{Aoname}
# 结果: D:/a/b/c/BLVEFO9-248965-喂我吃吧 老師!/
```

> [!TIP]
> 每个 `{...}` 内的变量会被 Python 的 `str.format()` 渲染，因此你可以任意组合文字与变量。
> `{Aid}` 和 `{Pid}` 返回的都是字符串，可以直接拼接。

---

## 2. 可用变量速查表

以下列出了 f-string 中可使用的所有内置变量。

### 本子变量（A 前缀）

| 变量名 | 类型 | 说明 | 示例值 |
|:---|:---|:---|:---|
| `{Aid}` | str | 本子 ID | `"248965"` |
| `{Aalbum_id}` | str | 同 `{Aid}` | `"248965"` |
| `{Aname}` | str | 本子名称（原始完整标题） | `"喂我吃吧 老師! [欶瀾漢化組]..."` |
| `{Atitle}` | str | 同 `{Aname}` | 同上 |
| `{Aoname}` | str | 提取出的原始名称（去除作者/汉化组等标签） | `"喂我吃吧 老師!"` |
| `{Aauthor}` | str | 第一作者 | `"BLVEFO9"` |
| `{Aauthoroname}` | str | `【作者】原始名称` | `"【BLVEFO9】喂我吃吧 老師!"` |
| `{Aidoname}` | str | `[ID] 原始名称` | `"[248965] 喂我吃吧 老師!"` |
| `{Adescription}` | str | 本子描述 | `"..."` |
| `{Apage_count}` | int | 总页数 | `42` |
| `{Apub_date}` | str | 发布日期 | `"2023-01-15"` |
| `{Aupdate_date}` | str | 更新日期 | `"2023-06-20"` |
| `{Alikes}` | str | 点赞数 | `"1K"` |
| `{Aviews}` | str | 观看数 | `"40K"` |
| `{Acomment_count}` | int | 评论数 | `128` |

### 章节变量（P 前缀）

| 变量名 | 类型 | 说明 | 示例值 |
|:---|:---|:---|:---|
| `{Pid}` | str | 章节 ID | `"212214"` |
| `{Pphoto_id}` | str | 同 `{Pid}` | `"212214"` |
| `{Pname}` | str | 章节名称 | `"94 突然打來"` |
| `{Ptitle}` | str | 同 `{Pname}` | 同上 |
| `{Poname}` | str | 章节的原始名称（去除标签） | `"94 突然打來"` |
| `{Pauthor}` | str | 章节作者（优先取本子作者） | `"BLVEFO9"` |
| `{Pauthoroname}` | str | `【作者】章节原始名称` | `"【BLVEFO9】94 突然打來"` |
| `{Pidoname}` | str | `[ID] 章节原始名称` | `"[212214] 94 突然打來"` |
| `{Psort}` | int | 章节排序值 | `3` |
| `{Pindex}` | int | 章节在本子中的序号（从1开始） | `3` |
| `{Palbum_index}` | int | 同 `{Pindex}` | `3` |
| `{Pindextitle}` | str | `第X話 章节名称` | `"第3話 94 突然打來"` |
| `{Palbum_id}` | str | 所属本子 ID | `"248965"` |

> [!NOTE]
> 变量的实际来源是实体类的**实例字段**和 **`@property`** 属性。如果你需要更多字段，可以在代码中调用 `album.get_properties_dict()` 或 `photo.get_properties_dict()` 打印查看所有可用的 key。

---

## 3. 简繁体统一（normalize_zh）

在一些源站中，同一作品或章节名称可能存在简体/繁体差异，导致在不同环境下生成重复或不一致的文件夹名。v2.6.10 引入了 `dir_rule.normalize_zh` 配置，用于可选地对目录名进行繁/简体规范化。

示例用法：

```yaml
dir_rule:
  base_dir: D:/a/b/c/
  rule: Bd / {Atitle}
  normalize_zh: zh-cn # 可选值：None（默认，不转换）/ zh-cn / zh-tw
```

说明：

- 当 `normalize_zh` 为 `zh-cn` 时，会把目录名中的中文规范为简体；为 `zh-tw` 时规范为繁体；为 `None` 或不配置时维持历史行为（不转换）。

- 该功能依赖可选库 `zhconv`（非必需），若未安装或转换失败，系统会回退为原始字符串并继续下载，不会导致失败。


## 4. 实战示例集

### 最基础：仅用章节名

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / {Pname}
```

结果：`D:/comics/94 突然打來/00001.webp`

---

### 本子 → 章节 二级目录

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / {Atitle} / {Pname}
```

结果：`D:/comics/社团学姐/94 突然打來/00001.webp`

---

### 文件夹名 = 作者 + 标题

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / 【{Aauthor}】{Atitle}
```

结果：`D:/comics/【BLVEFO9】喂我吃吧 老師!/00001.webp`

也可以直接使用内置的组合属性：

```yaml
rule: Bd / {Aauthoroname}
```

效果相同。

---

### 文件夹名 = 禁漫车号 + 标题

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / JM{Aid}-{Aoname}
```

结果：`D:/comics/JM248965-喂我吃吧 老師!/00001.webp`

---

### 文件夹名 = 第x话 + 标题

```yaml
# 直接使用内置属性 Pindextitle
dir_rule:
  rule: Bd / {Pindextitle}
```

结果：`./第3話 94 突然打來/00001.webp`

---

### 使用发布日期归档

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / {Apub_date} / [{Aid}]{Aoname}
```

结果：`D:/comics/2023-01-15/[248965]喂我吃吧 老師!/00001.webp`

---

### 完整三级目录：按作者 → 本子 → 章节

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / {Aauthor} / [{Aid}]{Aoname} / {Pindextitle}
```

结果：`D:/comics/BLVEFO9/[248965]喂我吃吧 老師!/第3話 94 突然打來/00001.webp`

---

### 兼容旧写法（传统 DSL）

以下旧写法仍然可用，但推荐逐步迁移至 f-string 语法：

```yaml
# 旧写法（等效）
rule: Bd_Pname

# f-string 新写法（推荐）
rule: Bd / {Pname}
```

```yaml
# 旧写法
rule: Bd / Atitle / Pindextitle

# f-string 新写法（推荐）
rule: Bd / {Atitle} / {Pindextitle}
```
