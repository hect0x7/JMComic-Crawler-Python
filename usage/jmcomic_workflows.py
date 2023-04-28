from jmcomic import *

def get_option():
    option = create_option('../assets/config/workflow_option.yml')
    return option


# 下方填入你要下载的本子的id，一行一个。
# 每行的首尾可以有空白字符
jm_albums = str_to_list('''
412541
372772
443817
317548
442079
408254
445551
445827
369580
412984
410279
354992
259641
380252
304647
226154
405621
399412
420730
424457
423503
424036
434241
436311
426904
438048
429328
392075
378556
245400
229682
431829
429305
434007
440507
442086

''')

# 调用jmcomic的download_album方法，下载漫画
download_album(jm_albums, option=get_option())
