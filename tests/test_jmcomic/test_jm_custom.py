from test_jmcomic import *


class Test_Custom(JmTestConfigurable):

    def test_custom_entity(self):
        """
        测试自定义属性
        """
        dic = {1: 'd', 2: 'e'}

        class MyAlbum(JmAlbumDetail):

            @property
            def aname(self):
                return dic[int(self.album_id)]

        class MyPhoto(JmPhotoDetail):

            @property
            def pname(self):
                return dic[int(self.photo_id)]

        JmModuleConfig.CLASS_ALBUM = MyAlbum
        JmModuleConfig.CLASS_PHOTO = MyPhoto

        base_dir: str = workspace()
        dir_rule = DirRule('Bd_Aaname_Ppname', base_dir)
        # noinspection PyTypeChecker
        save_dir = dir_rule.decide_image_save_dir(
            MyAlbum('1', '0', '0', [], *['0'] * 10),
            MyPhoto('2', *['0'] * 7)
        )

        self.assertEqual(
            os.path.abspath(save_dir),
            os.path.abspath(base_dir + dic[1] + '/' + dic[2]),
        )

    def test_extends_api_client(self):
        class MyClient(JmApiClient):
            pass

        JmModuleConfig.register_client(MyClient)

        self.assertListEqual(
            JmModuleConfig.DOMAIN_API_LIST,
            self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list()
        )

    def test_extends_html_client(self):
        class MyClient(JmHtmlClient):
            pass

        JmModuleConfig.register_client(MyClient)

        try:
            html_domain = self.client.get_html_domain()
        except BaseException as e:
            # 2024-04-29
            # 禁漫的【永久網域】加了cf，GitHub Actions请求也会失败。
            traceback_print_exec()
            if self.client.is_given_type(JmApiClient):
                return
            else:
                raise e

        JmModuleConfig.DOMAIN_HTML_LIST = [html_domain]

        self.assertListEqual(
            JmModuleConfig.DOMAIN_HTML_LIST,
            self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list()
        )

    def test_client_key_missing(self):
        class MyClient(JmcomicClient):
            pass

        # '不重写 client_key'
        self.assertRaises(
            JmcomicException,
            JmModuleConfig.register_client,
            MyClient,
        )

    def test_custom_client_empty_domain(self):
        class MyClient(AbstractJmClient):
            client_key = 'myclient'
            pass

        JmModuleConfig.register_client(MyClient)
        # '自定义client，不配置域名'
        self.assertRaises(
            JmcomicException,
            self.option.new_jm_client,
            domain_list=[],
            impl=MyClient.client_key,
        )

    def test_client_empty_domain(self):
        class MyClient(JmApiClient):
            client_key = 'myclient'
            pass

        JmModuleConfig.register_client(MyClient)
        self.assertListEqual(
            JmModuleConfig.DOMAIN_API_LIST,
            self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list(),
            msg='继承client，不配置域名',
        )
