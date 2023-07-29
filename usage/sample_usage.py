from jmcomic import *

jm_option = create_option(
    f'你的配置文件路径，例如: D:/a/b/c/jmcomic/config.yml'
)


@timeit('下载本子集: ')
def download_jm_album():
    ls = str_to_list('''
    438696


    ''')

    download_album(ls, jm_option)  # 效果同下面的代码
    # download_album_batch(ls, jm_option)


@timeit('获取实体类: ')
def get_album_photo_detail():
    client = jm_option.build_jm_client()
    # 启用缓存，会缓存id → album和photo的实体类
    client.enable_cache(debug=True)

    album: JmAlbumDetail = client.get_album_detail('427413')

    def show(p):
        p: JmPhotoDetail = client.get_photo_detail(p.photo_id, False)
        for img in p:
            img: JmImageDetail
            print(img.img_url)

    multi_thread_launcher(
        iter_objs=album,
        apply_each_obj_func=show
    )


@timeit('搜索本子: ')
def search_jm_album():
    client = jm_option.build_jm_client()

    # 分页查询
    search_page: JmSearchPage = client.search_album(search_query='+MANA +无修正', page=1)
    for album_id, title in search_page:
        print(f'[{album_id}]: {title}')

    # 直接搜索禁漫车号
    search_page = client.search_album(search_query='427413')
    album: JmAlbumDetail = search_page.single_album
    print(album.keywords)


@timeit('搜索并下载本子: ')
def search_and_download():
    tag = '無修正'
    search_album: JmSearchPage = cl.search_album(tag, main_tag=3)

    id_list = []

    for arg in search_album.album_info_list:
        (album_id, title, category_none, label_sub_none, tag_list) = arg
        if tag in tag_list:
            print(f'[标签/{tag}] 发现目标: [{album_id}]: [{title}]')
            id_list.append(album_id)

    download_album(id_list, op)


def main():
    search_jm_album()
    download_jm_album()
    get_album_photo_detail()


if __name__ == '__main__':
    main()
