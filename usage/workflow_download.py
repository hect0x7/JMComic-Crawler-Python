# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
jm_albums = '''
452859




'''


def main():
    from jmcomic import str_to_list, download_album
    # 下载漫画
    download_album(str_to_list(jm_albums), option=get_option())


def get_option():
    from jmcomic import create_option, print_eye_catching

    # 读取 option 配置文件
    option = create_option('../assets/config/option_workflow_download.yml')
    hook_debug(option)

    # 启用 client 的缓存
    client = option.build_jm_client()
    client.enable_cache()

    # 检查环境变量中是否有禁漫的用户名和密码，如果有则登录
    # 禁漫的大部分本子，下载是不需要登录的，少部分敏感题材需要登录
    # 如果你希望以登录状态下载本子，你需要自己配置一下Github Actions的 `secrets`
    # 配置的方式很简单，网页上点一点就可以了
    # 具体做法请去看官方教程：https://docs.github.com/en/actions/security-guides/encrypted-secrets

    # 萌新注意！！！如果你想 `开源` 你的禁漫帐号，你也可以直接把账号密码写到下面的代码😅

    username = get_env('JM_USERNAME')
    password = get_env('JM_PASSWORD')

    if username is not None and password is not None:
        client.login(username, password, True)
        print_eye_catching(f'登录禁漫成功')

    return option


def hook_debug(option):
    from jmcomic import JmHtmlClient, workspace, mkdir_if_not_exists

    jm_download_dir = get_env('JM_DOWNLOAD_DIR') or workspace()
    mkdir_if_not_exists(jm_download_dir)

    class RaiseErrorAwareClient(JmHtmlClient):

        @classmethod
        def raise_request_error(cls, resp, msg=None):
            from common import write_text, fix_windir_name, format_ts
            write_text(
                f'{jm_download_dir}/{fix_windir_name(resp.url)}',
                resp.text
            )

            return super().raise_request_error(resp, msg)

    option.jm_client_impl_mapping['html'] = RaiseErrorAwareClient


def get_env(name):
    import os
    value = os.getenv(name, None)

    if value is None or value == '':
        return None

    return value


if __name__ == '__main__':
    main()
