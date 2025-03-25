# 命令行教程

## 1. 基本用法

```
# 下载album 123 456，下载photo 333。彼此之间使用空格间隔
jmcomic 123 456 p333
```

## 2. 自定义option

### 2.1. 通过命令行
使用 --option 参数指定option配置文件路径

```sh
jmcomic 123 --option="D:/a.yml"
```

### 2.2. 使用环境变量
配置环境变量 `JM_OPTION_PATH` 为option配置文件路径

> 请自行google配置环境变量的方式，或使用powershell命令:  `setx JM_OPTION_PATH "D:/a.yml"` 重启后生效

```sh
jmcomic 123
```
