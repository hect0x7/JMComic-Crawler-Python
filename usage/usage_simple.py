"""

本文件仅演示一些简单的api使用，包含以下内容：
1. 下载本子
2. 获取实体类（本子/章节/图片）
3. 搜索本子
4. 搜索并下载本子（以下载带有 [無修正] 标签的本子为例）

"""

from jmcomic import *

# 核心下载配置
option = create_option(
    f'你的配置文件路径，例如: D:/a/b/c/jmcomic/config.yml'
)
# 提供请求功能的客户端对象
client = option.build_jm_client()


@timeit('下载本子: ')
def download_jm_album():
    ls = str_to_list('''
    438696
    https://18comic.vip/album/497896/

    ''')

    download_album(ls, option)


@timeit('获取实体类: ')
def get_album_photo_detail():
    # 本子实体类
    album: JmAlbumDetail = client.get_album_detail('427413')

    def show(photo: JmPhotoDetail):
        # 章节实体类
        photo = client.get_photo_detail(photo.photo_id, False)

        # 图片实体类
        image: JmImageDetail
        for image in photo:
            print(image.img_url)

    multi_thread_launcher(
        iter_objs=album,
        apply_each_obj_func=show
    )


@timeit('搜索本子: ')
def search_jm_album():
    # 分页查询，search_site就是禁漫网页上的【站内搜索】
    page: JmSearchPage = client.search_site(search_query='+MANA +无修正', page=1)
    # page默认的迭代方式是page.iter_id_title()，每次迭代返回 albun_id, title
    for album_id, title in page:
        print(f'[{album_id}]: {title}')

    # 直接搜索禁漫车号
    page = client.search_site(search_query='427413')
    album: JmAlbumDetail = page.single_album
    print(album.keywords)


@timeit('搜索并下载本子: ')
def search_and_download():
    tag = '無修正'
    # 搜索标签，可以使用search_tag。
    # 搜索第一页。
    page: JmSearchPage = client.search_tag(tag, page=1)

    aid_list = []

    for aid, atitle, tag_list in page.iter_id_title_tag():  # 使用page的iter_id_title_tag迭代器
        if tag in tag_list:
            print(f'[标签/{tag}] 发现目标: [{aid}]: [{atitle}]')
            aid_list.append(aid)

    download_album(aid_list, option)


def main():
    search_jm_album()
    download_jm_album()
    get_album_photo_detail()
    search_and_download()


if __name__ == '__main__':
    main()
