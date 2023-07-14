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

    def test_photo_sort(self):
        client = self.option.build_jm_client()

        # 测试用例 - 单章本子
        single_photo_album_is = str_to_list('''
        430371
        438696
        432888
        ''')

        # 测试用例 - 多章本子
        multi_photo_album_is = str_to_list('''
        400222
        122061
        ''')

        photo_dict: Dict[str, JmPhotoDetail] = multi_call(client.get_photo_detail, single_photo_album_is)
        album_dict: Dict[str, JmAlbumDetail] = multi_call(client.get_album_detail, single_photo_album_is)

        for each in photo_dict.values():
            each: JmPhotoDetail
            self.assertEqual(each.album_index, 1)

        for each in album_dict.values():
            each: JmAlbumDetail
            self.assertEqual(each[0].album_index, 1)

        print_eye_catching('【通过】测试用例 - 单章本子')
        multi_photo_album_dict: Dict[JmAlbumDetail, List[JmPhotoDetail]] = {}

        def run(aid):
            album = client.get_album_detail(aid)

            photo_dict = multi_call(
                client.get_photo_detail,
                (photo.photo_id for photo in album),
                launcher=thread_pool_executor,
            )

            multi_photo_album_dict[album] = list(photo_dict.values())

        multi_thread_launcher(
            iter_objs=multi_photo_album_is,
            apply_each_obj_func=run,
        )

        for album, photo_ls in multi_photo_album_dict.items():
            self.assertListEqual(
                sorted([each.sort for each in album]),
                sorted([ans.sort for ans in photo_ls]),
                album.album_id
            )

    def test_get_jmcomic_url(self):
        func_list = {
            self.client.get_jmcomic_url,
            self.client.get_jmcomic_domain_all,
            JmModuleConfig.get_jmcomic_url,
            JmModuleConfig.get_jmcomic_domain_all,
        }

        exception_list = []

        def run_func_async(func):
            try:
                func()
            except BaseException as e:
                exception_list.append(e)
                traceback_print_exec()

        multi_thread_launcher(
            iter_objs=func_list,
            apply_each_obj_func=run_func_async,
        )

        if len(exception_list) == 0:
            return

        for e in exception_list:
            print(e)

        raise AssertionError(exception_list)
