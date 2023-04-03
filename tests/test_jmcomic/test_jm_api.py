from test_jmcomic import *


class Test_Api(JmTestConfigurable):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move_workspace('download')

    def test_download_photo_by_id(self):
        """
        测试jmcomic模块的api的使用
        """
        photo_id = "438516"
        jmcomic.download_photo(photo_id, self.option)

    def test_download_album_by_id(self):
        """
        测试jmcomic模块的api的使用
        """
        album_id = '438516'
        jmcomic.download_album(album_id, self.option)

    def test_batch(self):
        album_ls = str_to_list('''
        326361
        366867
        438516
        ''')

        test_cases: Iterable = [
            {e: None for e in album_ls}.keys(),
            {i: e for i, e in enumerate(album_ls)}.values(),
            set(album_ls),
            tuple(album_ls),
            album_ls,
        ]

        for case in test_cases:
            ret1 = jmcomic.download_album(case, self.option)
            self.assertEqual(len(ret1), len(album_ls), str(case))

            ret2 = jmcomic.download_album_batch(case, self.option)
            self.assertEqual(len(ret2), len(album_ls), str(case))

        # 测试 Generator
        ret2 = jmcomic.download_album_batch((e for e in album_ls), self.option)
        self.assertEqual(len(ret2), len(album_ls), 'Generator')

    def test_jm_option_advice(self):
        class MyAdvice(JmOptionAdvice):
            def decide_image_filepath(self,
                                      option: 'JmOption',
                                      photo_detail: JmPhotoDetail,
                                      index: int,
                                      ) -> StrNone:
                return workspace(f'{time_stamp()}_{photo_detail[index].img_file_name}.test.png')

        option = JmOption.default()
        option.register_advice(MyAdvice())
        jmcomic.download_album('366867', option)
