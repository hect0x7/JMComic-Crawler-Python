from jmcomic import *

# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
# 你也可以填入本子网址，程序会识别出本子id
# 例如:
# [https://18comic.vip/album/452859/mana-ディシア-1-原神-中国語-無修正] -> [452859]
#
jm_albums = '''



'''


def get_jm_album_ids():
    aid_set = set()
    for text in [
        jm_albums,
        (get_env('JM_ALBUM_IDS') or '').replace('-', '\n'),
    ]:
        aid_set.update(str_to_set(text))

    return aid_set


def main():
    # 下载漫画
    download_album(get_jm_album_ids(), option=get_option())


def get_option():
    # 读取 option 配置文件
    option = create_option('../assets/config/option_workflow_download.yml')

    # 支持工作流覆盖配置文件的配置
    cover_option_config(option)

    # 覆盖client实现类，实现把请求错误的html下载到文件，方便GitHub Actions下载查看日志
    hook_debug(option)

    # 启用 client 的缓存
    client = option.build_jm_client()
    client.enable_cache()

    # 登录，如果有配置的话
    login_if_configured(client)

    return option


def cover_option_config(option: JmOption):
    dir_rule = get_env('DIR_RULE')
    if dir_rule is not None:
        the_old = option.dir_rule
        the_new = DirRule(dir_rule, base_dir=the_old.base_dir)
        option.dir_rule = the_new


def login_if_configured(client):
    # 检查环境变量中是否有禁漫的用户名和密码，如果有则登录
    # 禁漫的大部分本子，下载是不需要登录的，少部分敏感题材需要登录
    # 如果你希望以登录状态下载本子，你需要自己配置一下GitHub Actions的 `secrets`
    # 配置的方式很简单，网页上点一点就可以了
    # 具体做法请去看官方教程：https://docs.github.com/en/actions/security-guides/encrypted-secrets
    # 萌新注意！！！如果你想 `开源` 你的禁漫帐号，你也可以直接把账号密码写到下面的代码😅
    username = get_env('JM_USERNAME')
    password = get_env('JM_PASSWORD')
    if username is not None and password is not None:
        client.login(username, password, True)
        print_eye_catching(f'登录禁漫成功')


# noinspection PyUnusedLocal
def hook_debug(option):
    jm_download_dir = get_env('JM_DOWNLOAD_DIR') or workspace()
    mkdir_if_not_exists(jm_download_dir)

    class RaiseErrorAwareClient(JmHtmlClient):

        @classmethod
        def raise_request_error(cls, resp, msg=None):
            from common import write_text, fix_windir_name
            write_text(
                f'{jm_download_dir}/{fix_windir_name(resp.url)}',
                resp.text
            )

            return super().raise_request_error(resp, msg)

    JmModuleConfig.CLASS_CLIENT_IMPL['html'] = RaiseErrorAwareClient


def get_env(name):
    import os
    value = os.getenv(name, None)

    if value is None or value == '':
        return None

    return value


if __name__ == '__main__':
    main()
