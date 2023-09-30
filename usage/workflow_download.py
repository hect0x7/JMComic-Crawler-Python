from jmcomic import *
from jmcomic.cl import get_env, JmcomicUI

# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
# 你也可以填入本子网址，程序会识别出本子id
# 例如:
# [https://18comic.vip/album/452859/mana-ディシア-1-原神-中国語-無修正] -> [452859]
#
jm_albums = '''



'''

# 单独下载章节
jm_photos = '''


'''


def get_id_set(env_name):
    aid_set = set()
    for text in [
        jm_albums,
        (get_env(env_name, '')).replace('-', '\n'),
    ]:
        aid_set.update(str_to_set(text))

    return aid_set


def main():
    album_id_set = get_id_set('JM_ALBUM_IDS')
    photo_id_set = get_id_set('JM_PHOTO_IDS')

    helper = JmcomicUI()
    helper.album_id_list = list(album_id_set)
    helper.photo_id_list = list(photo_id_set)

    helper.run(get_option())


def get_option():
    # 读取 option 配置文件
    option = create_option('../assets/config/option_workflow_download.yml')

    # 支持工作流覆盖配置文件的配置
    cover_option_config(option)

    # 把请求错误的html下载到文件，方便GitHub Actions下载查看日志
    log_before_raise()

    # 登录，如果有配置的话
    login_if_configured(option)

    return option


def cover_option_config(option: JmOption):
    dir_rule = get_env('DIR_RULE', None)
    if dir_rule is not None:
        the_old = option.dir_rule
        the_new = DirRule(dir_rule, base_dir=the_old.base_dir)
        option.dir_rule = the_new

    impl = get_env('CLIENT_IMPL', None)
    if impl is not None:
        option.client.impl = impl


def login_if_configured(option):
    # 检查环境变量中是否有禁漫的用户名和密码，如果有则登录
    # 禁漫的大部分本子，下载是不需要登录的，少部分敏感题材需要登录
    # 如果你希望以登录状态下载本子，你需要自己配置一下GitHub Actions的 `secrets`
    # 配置的方式很简单，网页上点一点就可以了
    # 具体做法请去看官方教程：https://docs.github.com/en/actions/security-guides/encrypted-secrets
    # 萌新注意！！！如果你想 `开源` 你的禁漫帐号，你也可以直接把账号密码写到下面的代码😅
    username = get_env('JM_USERNAME', None)
    password = get_env('JM_PASSWORD', None)
    if username is not None and password is not None:
        # 调用login插件
        JmLoginPlugin(option).invoke(username, password)


def log_before_raise():
    jm_download_dir = get_env('JM_DOWNLOAD_DIR', workspace())
    mkdir_if_not_exists(jm_download_dir)

    # 自定义异常抛出函数，在抛出前把HTML响应数据写到下载文件夹（日志留痕）
    def raises(old, msg, extra: dict):
        if ExceptionTool.EXTRA_KEY_RESP not in extra:
            return old(msg, extra)

        resp = extra[ExceptionTool.EXTRA_KEY_RESP]
        # 写文件
        from common import write_text, fix_windir_name
        write_text(f'{jm_download_dir}/{fix_windir_name(resp.url)}', resp.text)

        return old(msg, extra)

    # 应用函数
    ExceptionTool.replace_old_exception_executor(raises)


if __name__ == '__main__':
    main()
