"""

使用命令行下载禁漫本子

1. 基本用法
# 下载album 123 456，下载photo 333。彼此之间使用空格间隔
```
jmcomic 123 456 p333
```

2. 自定义option

2.1. 通过命令行
```
jmcomic 123 --option="D:/a.yml"
```

2.2. 通过环境变量
设置环境: JM_OPTION_PATH = D:/a.yml
命令行的命令不变
```
jmcomic 123
```



"""
