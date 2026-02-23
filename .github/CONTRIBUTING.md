# 🤝 参与贡献 (Contributing)

首先，非常感谢每一位愿意为 `jmcomic` 贡献代码和力量的机长！将 `jmcomic` 驶向更广阔的天空，离不开各位的添砖加瓦。

如果把每一次启动爬虫看作是一次狂热的航班起飞，那么这份文档就是塔台（仓库维护者）下发的**飞行手册与航权指南**。在改造战机、请求起飞之前，请务必花两分钟阅读这套协同规则。

## 💡 航前申报 (Before Writing Code)

如果你的航线规划（代码改动）涉及核心组件或者需要编写超过几行代码，**强烈建议你先通过提交一个 Issue 向塔台申请**，详细讨论你想要拓展的功能或重构的想法。

在投入大量燃油（精力）之前，我们应该先在技术路线和实现方式上达成一致，避免你的心血被白白浪费或航线规划不被塔台接受。

## 💻 登机准备与试飞 (Build and Test)

### 1. 组装战机 (Build)

参与贡献的第一步，是将本项目 **[Fork](https://github.com/hect0x7/JMComic-Crawler-Python/fork)** 到你个人的机库（GitHub 账号）下，然后克隆到控制台，并独立切出你的任务分支：

```bash
git clone https://github.com/<your_user_name>/JMComic-Crawler-Python.git
cd JMComic-Crawler-Python
git checkout dev 
git checkout -b <your_feature_branch>
```

强烈建议使用现代化的包管理器（如 [uv](https://github.com/astral-sh/uv)）进行极速的沙盒隔离开发，避免污染你本地的系统空域：

```bash
# 自动打通虚拟环境并注满燃油（安装源码及开发依赖）
uv venv
uv pip install -r requirements-dev.txt -e ./
```

### 2. 空中改造 (Coding)

在战机组装完毕并建立好安全的沙盒后，你就可以开始编写代码进行你的改装了。

在动工之前，请务必仔细阅读本文档末尾的《[🛠️ 引擎改装规范（Coding Guidelines）](#%EF%B8%8F-引擎改装规范-coding-guidelines)》 部分。那里记载了你必须要遵守的架构底线（如统一日志与异常拆解机制）。这能确保你的航线设计不偏离塔台的预设轨迹，避免在安检时因为违规操作被打回。

### 3. 试飞运行 (Test)

向原仓库 `dev` 航道发起 PR 之前，你需要作为机长执行跑道级自检，**请务必保证你新编撰的代码能够顺利通过试飞用例**。

你可以任选以下两种自检方式之一：

**选项 A：本地试飞 (终端测试)**
本项目使用 Python 标准库 `unittest` 作为本地质检验证，跑通所有测试：
```bash
cd ./tests/
uv run python -m unittest
```

**选项 B：云端试飞 (GitHub Actions)**
如果你的本地环境不便配置，也可以直接将代码推送至你个人 Fork 仓库的 `dev` 分支。云端塔台会在后台自动触发 `test_api.yml` 动作。
> 💡 请前往你个人仓库的 **Actions** 面板，确保最新地推流全部亮起绿灯。

## 📥 申请接入航线 (Pull Request)

`jmcomic` 的代码管线有着极其明确的空域隔离，发起 PR 时请务必挂对你的目标分支：

- 🟢 **`dev` 航道 (代码开发)**：所有的**功能特性 (feat)**、**功能重构 (refactor)** 或 **Bug 修复 (fix)** 的 PR，均需指向原仓库的 `dev` 航道。由塔台（维护者）合并试飞后集中推向主发版链路。

- 📘 **`docs` 航道 (文档维护)**：本航道直通项目专属的 **[在线文档 (Read the Docs)](https://jmcomic.readthedocs.io/zh-cn/latest/)**。所有不涉及功能性代码修改的**纯粹文档更新**，请直接提交至此分支。入线后它将即刻触发并全网同步部署，绕过复杂的流水安检。需要注意的是，`docs` 航道的进度通常会超前于主系统 (`master`)，塔台会在新版发布或定期检修时统一将二者对齐同步。

- 🚫 **禁飞区 (禁止直飞 master)**：为防止外部航班意外触发 `release_auto.yml` 这个威力巨大的自动发版工作流，**本项目不接受任何直接指向 `master` 分支的 PR**。所有的新功能与代码改造必须经由 `dev` 航道降落并完成试飞，新版本号的最终敲定与发布由塔台统一操控。

PR 申请后，我会尽快 review 各位机长的代码并反馈通讯。再次感谢你的付出！🎉

---

## 🚀 发版巡航 (Release Process)

项目使用自动化流水线进行发版，此流程仅由塔台（维护者）在合并至 `master` 分支时触发。

### 1. 触发条件
当代码被推送（或 PR 合并）至 `master` 分支，且 **Commit Message 以 `v` 开头**时，GitHub Actions 会自动启动 `release_auto.yml` 工作流，执行以下操作：
1. 自动根据 Commit Message 创建 GitHub Release 标签。
2. 自动构建项目并发布至 [PyPI](https://pypi.org/project/jmcomic/)。

### 2. Commit 格式指令 (仅针对维护者)
当塔台（维护者）准备好发布新版本并合入 `master` 时，需要根据 `.github/release.py` 的解析要求使用特定格式的 Commit Message：

**格式：** `v<版本号>: <更新项1>; <更新项2>; ...`

*   **示例：** `v2.1.0: 修复搜索解析异常; 优化多线程下载效率; 新增插件系统`
*   **黑匣子解析逻辑：**
    *   **Tag**：冒号 `:` 前的内容（如 `v2.1.0`）。
    *   **Body**：冒号 `:` 后的内容，程序会将分号 `;` 分割的每一项转化为有序列表。

---

## 🛠️ 引擎改装规范 (Coding Guidelines)

> 📌 **塔台公告**：本《引擎改装规范》将伴随舰队的探索进度**持续迭代更新**。当前的强制适航指令主要聚焦于 **黑匣子 (日志记录)** 与 **空难溯源 (异常处理)** 两大核心电传模块。

### 📝 测试与操作手册 (Tests & Docs)

在完成代码改造后，机长请务必补全以下配套设施，这是确保新战机安全入库的必要纲领：

- **补充伴飞测试 (Tests)**：如果你打造了新型挂载（新功能）或排查掉了深层故障（Bug），你必须在 `tests/` 目录下为其编写对应的试飞用例。每一行核心代码都应当能通过稳定飞行测试。
- **更新操作手册 (Docs)**：如果你实现了向其他机长开放的新仪表盘能力（功能入口），你还需要同步更新操作手册。文档应安放在 `assets/docs/` 下的对应位置。如果不知道该放哪，欢迎在 PR 中呼叫塔台。

---

### 💻 核心架构指令 (Architecture Rules)

在为 `jmcomic` 编写或改造代码时，请尽量增加类型注解 (Type hints) 并遵守合理地命名。除此之外，为确保全机队的统一性，请尽量遵循以下架构规范：

#### 1. 统一使用黑匣子网关 (统一日志)
所有的业务代码请统一使用 `from jmcomic import jm_log` 进行留痕。**避免**直接 `import logging` 或手动去拼接带有 `【】` 的日志头：
```python
from jmcomic import jm_log, jm_logger

# ❌ 避免直接调用底层 logger（jm_logger 是 jmcomic 内部原始的 logging.Logger 实例）
jm_logger.info("【api】请求成功")

# ✅ 推荐做法，统一走网关，系统会自动套用格式化主题
jm_log('api', '请求成功') 
```

#### 2. 优雅记录坠机日志 (异常处理)
在飞行途中捕获到不可预料的 Exception 时，**无需**使用 `traceback.format_exc()` 费力拼装栈残骸。直接将异常对象作为入参传入 `jm_log` 即可，底层引擎会自动完整解析现场：
```python
try:
    do_something()
except Exception as e:
    # ❌ 避免手动拼装残骸，否则日志过滤系统会把它当成纯文本
    import traceback
    jm_log('req.error', f'{e}\n{traceback.format_exc()}')
    
    # ✅ 推荐做法：直接上交异常对象本体，清爽且精准
    jm_log('req.error', e)
```

#### 3. 触发系统级警报 (统一抛错)
当发生预期的业务级阻断时，请尽量避免直接抛出内置的裸 Exception。通过内置的 `ExceptionTool` 抛出，能确保异常准确传达给用户外部装配的监听器 (`ExceptionListener`)：
```python
from jmcomic import ExceptionTool

# ❌ 避免直接 raise 底层异常，这会导致外部监听器失效
raise Exception("解析 json 数据失败")

# ✅ 推荐做法：通过工具类附带上下文信息抛出
ExceptionTool.raises_resp(msg="解析 json 数据失败", resp=response)
```
