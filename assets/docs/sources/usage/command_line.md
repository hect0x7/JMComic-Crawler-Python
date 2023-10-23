# 使用命令行下载禁漫本子

1. 基本用法

   ```
   # 下载album 123 456，下载photo 333。彼此之间使用空格间隔
   jmcomic 123 456 p333
   ```

2. 自定义option

   1. 通过命令行，使用 --option 参数指定option配置文件路径

      ```
      jmcomic 123 --option="D:/a.yml"
      ```

   2. 配置环境变量 `JM_OPTION_PATH` 为option配置文件路径

      ```
      set JM_OPTION_PATH="D:/a.yml"
      jmcomic 123
      ```
