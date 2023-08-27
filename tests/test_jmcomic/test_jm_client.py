from test_jmcomic import *


class Test_Client(JmTestConfigurable):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move_workspace('download')

    def test_download_image(self):
        jm_photo_id = 'JM438516'
        photo = self.client.get_photo_detail(jm_photo_id, False)
        self.client.download_by_image_detail(
            photo[0],
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
        photo = self.client.get_photo_detail(jm_photo_id, False)
        photo.when_del_save_file = True
        photo.after_save_print_info = True
        del photo

    def test_multi_album_and_single_album(self):
        multi_photo_album_id = [
            "195822",
        ]

        for album_id in multi_photo_album_id:
            album: JmAlbumDetail = self.client.get_album_detail(album_id)
            print(f'本子: [{album.title}] 一共有{album.page_count}页图')

    def test_search(self):
        jm_search_page: JmSearchPage = self.client.search_album('+无修正 +中文 -全彩')
        for album_id, title in reversed(jm_search_page):
            print(album_id, title)

    def test_gt_300_photo(self):
        photo_id = '147643'
        photo: JmPhotoDetail = self.client.get_photo_detail(photo_id, False)
        image = photo[3000]
        print(image.img_url)
        self.client.download_by_image_detail(image, workspace('3000.png'))

    def test_album_missing(self):
        JmModuleConfig.CLASS_EXCEPTION = JmcomicException
        self.assertRaises(
            JmcomicException,
            self.client.get_album_detail,
            '332583'
        )
