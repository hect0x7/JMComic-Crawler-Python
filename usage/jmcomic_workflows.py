# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
jm_albums = '''
380460



'''


def main():
    from jmcomic import create_option, str_to_list, download_album, print_eye_catching

    def get_option():
        # 读取 option 配置文件
        option = create_option('../assets/config/workflow_option.yml')

        # 启用 client 的缓存
        client = option.build_jm_client()
        client.enable_cache()

        # 检查环境变量中是否有禁漫的用户名和密码，如果有则登录

        def get_env(name):
            import os
            value = os.getenv(name, None)

            if value is None or value == '':
                return None

            return value

        username = get_env('JM_USERNAME')
        password = get_env('JM_PASSWORD')

        if username is not None and password is not None:
            client.login(username, password, True)
            print_eye_catching(f'登录禁漫成功')

        return option

    # 调用jmcomic的download_album方法，下载漫画
    download_album(str_to_list(jm_albums), option=get_option())


if __name__ == '__main__':
    main()
