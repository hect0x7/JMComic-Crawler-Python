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

```text
旧路径：D:/a/[kyockcho]本子名称 - kyockcho/
新路径：D:/a/[きょくちょ]本子名称 - きょくちょ/

```

---------------
**_如果上述简单的文本替换无法满足你，或者你需要更灵活的组合逻辑，那么下面的 f-string 语法正适合你。_**

## 1. 目录规则与单段 DSL

当你使用 `download_album` 下载本子时，本子会以一定的路径规则（DirRule）下载到你的磁盘上。

如果你希望文件夹里包含本子/章节信息，就可以通过下面的规则定制文件夹名和保存路径。

使用 `dir_rule` 配置：`base_dir` 指定根目录，`rule` 指定各层目录的命名规则。

### 1.1 rule 的组成

`rule` 由根目录 `Bd` 和多段 DSL 组成，段与段之间用 `/` 分隔。每段 DSL 决定一层文件夹的名字，解析后按顺序拼接成保存路径。

例如：

```yaml
rule: Bd / Atitle / {Pid}-{Ptitle}
```

这条规则有三段：

| 段           | 规则 | 对应的目录层级 |
|:-------------|:---|:---|
| 第一段：固定 | `Bd` | 根目录，即 `base_dir` |
| 第二段：DSL  | `Atitle` | 以本子标题命名的文件夹 |
| 第三段：DSL  | `{Pid}-{Ptitle}` | 以章节 ID 和标题组合命名的文件夹 |

`Bd` 放在最前面，然后接下来说明每一段 DSL 怎么写。

### 1.2 一段 DSL 怎么写

**一段 DSL 规则用于生成一个目录名**，支持以下写法：

| 写法 | 示例 | 含义 |
|:---|:---|:---|
| 单属性简写 | `Atitle`、`Ptitle` | 直接使用本子标题或章节标题 |
| f-string 组合 | `{Pid}-{Ptitle}`、`JM{Aid}` | 组合多个属性或固定文字 |
| 固定文字 | `comics` | 直接使用这段文字作为文件夹名 |

**单属性简写**：本子属性用 `Axxx`，章节属性用 `Pxxx`，其中 `xxx` 是属性名。例如 `Atitle` 表示本子的 `title`，`Ptitle` 表示章节的 `title`。

**组合写法**：需要把多个属性或固定文字放进同一个文件夹名时，用 `{变量名}` 引用属性。例如 `{Pid}-{Ptitle}` 将章节 ID 和标题用 `-` 连接，`JM{Aid}` 在本子 ID 前加上 `JM`。组合写法由 Python 的 `str.format()` 渲染。

**固定文字**：例如 `comics` 会直接生成名为 `comics` 的文件夹。以 `A` 或 `P` 开头的文字会按属性简写解析，应避开这类固定命名。

单个属性优先使用简写，需要组合时再用 `{}`。

### 1.3 完整示例

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / Atitle / {Pid}-{Ptitle}
```

假设本子标题为「社团学姐」，当前章节 ID 为 `212214`，章节标题为「第3话」，各段解析后的结果依次是：

- `Bd` → `D:/comics/`
- `Atitle` → `社团学姐`
- `{Pid}-{Ptitle}` → `212214-第3话`

最终图片路径为：

```text
D:/comics/社团学姐/212214-第3话/00001.webp
```

---

## 2. 可用属性速查表

下表列出常用属性名，可直接作为单段 DSL 简写；需要组合时在属性名外加 `{}`，例如 `Aid` → `JM{Aid}-{Atitle}`。

### 本子变量（A 前缀）

| 变量名 | 类型 | 说明 | 示例值 |
|:---|:---|:---|:---|
| `Aid` | str | 本子 ID | `"248965"` |
| `Aalbum_id` | str | 同 `Aid` | `"248965"` |
| `Aname` | str | 本子名称（原始完整标题） | `"喂我吃吧 老師! [欶瀾漢化組]..."` |
| `Atitle` | str | 同 `Aname` | 同上 |
| `Aoname` | str | 提取出的原始名称（去除作者/汉化组等标签） | `"喂我吃吧 老師!"` |
| `Aauthor` | str | 第一作者 | `"BLVEFO9"` |
| `Aauthoroname` | str | `【作者】原始名称` | `"【BLVEFO9】喂我吃吧 老師!"` |
| `Aidoname` | str | `[ID] 原始名称` | `"[248965] 喂我吃吧 老師!"` |
| `Adescription` | str | 本子描述 | `"..."` |
| `Apage_count` | int | 总页数 | `42` |
| `Apub_date` | str | 发布日期 | `"2023-01-15"` |
| `Aupdate_date` | str | 更新日期 | `"2023-06-20"` |
| `Alikes` | str | 点赞数 | `"1K"` |
| `Aviews` | str | 观看数 | `"40K"` |
| `Acomment_count` | int | 评论数 | `128` |

### 章节变量（P 前缀）

| 变量名 | 类型 | 说明 | 示例值 |
|:---|:---|:---|:---|
| `Pid` | str | 章节 ID | `"212214"` |
| `Pphoto_id` | str | 同 `Pid` | `"212214"` |
| `Pname` | str | 章节名称 | `"94 突然打來"` |
| `Ptitle` | str | 同 `Pname` | 同上 |
| `Poname` | str | 章节的原始名称（去除标签） | `"94 突然打來"` |
| `Pauthor` | str | 章节作者（优先取本子作者） | `"BLVEFO9"` |
| `Pauthoroname` | str | `【作者】章节原始名称` | `"【BLVEFO9】94 突然打來"` |
| `Pidoname` | str | `[ID] 章节原始名称` | `"[212214] 94 突然打來"` |
| `Psort` | int | 章节排序值 | `3` |
| `Pindex` | int | 章节在本子中的序号（从1开始） | `3` |
| `Palbum_index` | int | 同 `Pindex` | `3` |
| `Pindextitle` | str | `第X話 章节名称` | `"第3話 94 突然打來"` |
| `Palbum_id` | str | 所属本子 ID | `"248965"` |

> [!NOTE]
> 变量的实际来源是实体类的**实例字段**和 **`@property`** 属性。如果你需要更多字段，可以在代码中调用 `album.get_properties_dict()` 或 `photo.get_properties_dict()` 打印查看所有可用的 key。

---

## 3. 简繁体统一（normalize_zh）

在一些源站中，同一作品或章节名称可能存在简体/繁体差异，导致在不同环境下生成重复或不一致的文件夹名。v2.6.10 引入了 `dir_rule.normalize_zh` 配置，用于可选地对目录名进行繁/简体规范化。

示例用法：

```yaml
dir_rule:
  base_dir: D:/a/b/c/
  rule: Bd / Atitle
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
  rule: Bd / Pname
```

结果：`D:/comics/94 突然打來/00001.webp`

---

### 本子 → 章节 二级目录

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / Atitle / Pname
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
rule: Bd / Aauthoroname
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
  rule: Bd / Pindextitle
```

结果：`./第3話 94 突然打來/00001.webp`

---

### 使用发布日期归档

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / Apub_date / [{Aid}]{Aoname}
```

结果：`D:/comics/2023-01-15/[248965]喂我吃吧 老師!/00001.webp`

---

### 完整三级目录：按作者 → 本子 → 章节

```yaml
dir_rule:
  base_dir: D:/comics/
  rule: Bd / Aauthor / [{Aid}]{Aoname} / Pindextitle
```

结果：`D:/comics/BLVEFO9/[248965]喂我吃吧 老師!/第3話 94 突然打來/00001.webp`
