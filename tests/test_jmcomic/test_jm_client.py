from test_jmcomic import *


class Test_Client(JmTestConfigurable):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move_workspace('download')

    def test_download_from_cdn_directly(self):
        photo_id = 'JM438516'
        option = self.option
        cdn_crawler = option.build_cdn_crawler()
        cdn_crawler.download_photo_from_cdn_directly(
            option.build_cdn_request(photo_id),
        )

    def test_download_image(self):
        jm_photo_id = 'JM438516'
        photo_detail = self.client.get_photo_detail(jm_photo_id)
        self.client.download_by_image_detail(
            photo_detail[0],
            img_save_path=workspace('test_download_image.png')
        )

    def test_get_album_detail_by_jm_photo_id(self):
        album_id = "JM438516"
        print_obj_dict(self.client.get_album_detail(album_id))

    def test_get_photo_detail_by_jm_photo_id(self):
        """
        测试通过 JmcomicClient 和 jm_photo_id 获取 JmPhotoDetail对象
        """
        jm_photo_id = 'JM438516'
        photo_detail = self.client.get_photo_detail(jm_photo_id)
        photo_detail.when_del_save_file = True
        photo_detail.after_save_print_info = True
        del photo_detail

    def test_multi_album_and_single_album(self):
        multi_photo_album_id = [
            "195822",
        ]

        for album_id in multi_photo_album_id:
            album_detail: JmAlbumDetail = self.client.get_album_detail(album_id)
            print(f'本子: [{album_detail.title}] 一共有{album_detail.page_count}页图')

    def test_search(self):
        jm_search_page = self.client.search_album('MANA')
        for album_id in jm_search_page.album_id_iter():
            print(album_id)

    def test_gt_300_photo(self):
        photo_id = '147643'
        photo_detail: JmPhotoDetail = self.client.get_photo_detail(photo_id)
        image = photo_detail[3000]
        print(image.img_url)
        self.client.download_by_image_detail(image, workspace('3000.png'))
