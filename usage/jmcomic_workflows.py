from jmcomic import *

def get_option():
    option = create_option('../assets/config/workflow_option.yml')
    return option


# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
jm_albums = str_to_list('''
419596
410279
420121
415975
415523
413748
408780
403509
403511

''')

# 调用jmcomic的download_album方法，下载漫画
download_album(jm_albums, option=get_option())
