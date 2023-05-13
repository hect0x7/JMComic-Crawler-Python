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
    album: JmAlbumDetail = client.get_album_detail('427413')

    def show(p):
        p: JmPhotoDetail = client.get_photo_detail(p.photo_id)
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
    search_album: JmSearchPage = client.search_album(search_query='+MANA +无修正')
    for album_id, title, *_args in search_album:
        print(f'[{album_id}]：{title}')


def main():
    search_jm_album()
    download_jm_album()
    get_album_photo_detail()


if __name__ == '__main__':
    main()
