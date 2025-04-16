from test_jmcomic import *


class Test_Api(JmTestConfigurable):

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

            ret2 = jmcomic.download_album(case, self.option)
            self.assertEqual(len(ret2), len(album_ls), str(case))

        # 测试 Generator
        ret2 = jmcomic.download_album((e for e in album_ls), self.option)
        self.assertEqual(len(ret2), len(album_ls), 'Generator')

    def test_get_jmcomic_domain(self):
        func_list = {
            self.client.get_html_domain,
            self.client.get_html_domain_all,
            self.client.get_html_domain_all_via_github,
            # JmModuleConfig.get_jmcomic_url,
            # JmModuleConfig.get_jmcomic_domain_all,
        }

        exception_list = []

        def run_func_async(func):
            try:
                print(func())
            except BaseException as e:
                exception_list.append(e)
                traceback_print_exec()

        multi_thread_launcher(
            iter_objs=func_list,
            apply_each_obj_func=run_func_async,
        )

        if len(exception_list) == 0:
            return

        if self.client.is_given_type(JmApiClient):
            return

        for e in exception_list:
            print(e)

        raise AssertionError(exception_list)

    def test_partial_exception(self):
        class TestDownloader(JmDownloader):
            def do_filter(self, detail: DetailEntity):
                if detail.is_photo():
                    return detail[0:2]
                if detail.is_album():
                    return detail[0:2]
                return super().do_filter(detail)

            @catch_exception
            def download_by_image_detail(self, image: JmImageDetail):
                raise Exception('test_partial_exception')

            @catch_exception
            def download_by_photo_detail(self, photo: JmPhotoDetail):
                if photo.index != 2:
                    raise Exception('test_partial_exception')
                return super().download_by_photo_detail(photo)

        self.assertRaises(
            PartialDownloadFailedException,
            lambda: download_album(182150, downloader=TestDownloader, check_exception=True)
        )
        self.assertRaises(
            PartialDownloadFailedException,
            lambda: download_photo(182151, downloader=TestDownloader, check_exception=True)
        )
