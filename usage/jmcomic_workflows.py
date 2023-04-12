from jmcomic import *

def get_option():
    option = create_option('../assets/config/workflow_option.yml')
    return option


# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
jm_albums = str_to_list('''
413367
414095
414072
414071
413210
413147
413005
412038
411789
410862
410032
408924
408919
408900
408780
405768
401409
397644
420093
419972
414425
391879
389574
387616
387674


''')

# 调用jmcomic的download_album方法，下载漫画
download_album(jm_albums, option=get_option())
