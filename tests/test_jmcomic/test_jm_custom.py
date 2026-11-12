import os
import traceback

from test_jmcomic import *


class Test_Custom(JmTestConfigurable):

    def test_fstring_entity_prefix_and_default_name(self):
        """自定义实体类保留 A/P 前缀，默认规则沿用 name 定制。"""
        from unittest.mock import patch

        class CustomAlbum(JmAlbumDetail):
            pass

        class CustomPhoto(JmPhotoDetail):
            pass

        album = CustomAlbum('1', '0', '0', [], *['0'] * 10)
        photo = CustomPhoto('2', *['0'] * 7)
        self.assertEqual(album.name, album.get_properties_dict()['Aname'])
        self.assertEqual(photo.name, photo.get_properties_dict()['Pname'])
        self.assertEqual(photo.title, photo.get_properties_dict()['Ptitle'])
        rule = JmOption.default().dir_rule.rule_dsl
        with patch.dict(JmModuleConfig.PFIELD_ADVICE, {'name': lambda p: 'custom-name'}):
            expected = fix_filepath(os.path.join(os.path.abspath('.'), 'custom-name'))
            actual = DirRule(rule, '.').decide_image_save_dir(album, photo)
            self.assertEqual(expected, actual)
            self.assertEqual('custom-name', os.path.basename(actual.rstrip('/\\')))

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

        base_dir: str = fix_filepath(os.getcwd())
        dir_rule = DirRule('Bd / Aaname / Ppname', base_dir)
        # noinspection PyTypeChecker
        save_dir = dir_rule.decide_image_save_dir(
            MyAlbum('1', '0', '0', [], *['0'] * 10),
            MyPhoto('2', *['0'] * 7)
        )

        self.assertEqual(
            os.path.abspath(save_dir),
            os.path.abspath(base_dir + dic[1] + '/' + dic[2]),
        )
        JmModuleConfig.CLASS_ALBUM = JmAlbumDetail
        JmModuleConfig.CLASS_PHOTO = JmPhotoDetail

    def test_extends_api_client(self):
        class MyClient(JmApiClient):
            pass

        JmModuleConfig.register_client(MyClient)

        self.assertListEqual(
            self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list(),
            JmModuleConfig.DOMAIN_API_UPDATED_LIST if JmModuleConfig.DOMAIN_API_UPDATED_LIST else JmModuleConfig.DOMAIN_API_LIST,
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
            traceback.print_exc()
            if self.client.is_api():
                return
            else:
                raise e

        old_domain_html_list = JmModuleConfig.DOMAIN_HTML_LIST
        try:
            JmModuleConfig.DOMAIN_HTML_LIST = [html_domain]
            self.assertListEqual(
                JmModuleConfig.DOMAIN_HTML_LIST,
                self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list()
            )
        finally:
            JmModuleConfig.DOMAIN_HTML_LIST = old_domain_html_list

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
            self.option.new_jm_client(domain_list=[], impl=MyClient.client_key).get_domain_list(),
            JmModuleConfig.DOMAIN_API_UPDATED_LIST if JmModuleConfig.DOMAIN_API_UPDATED_LIST else JmModuleConfig.DOMAIN_API_LIST,
            msg='继承client，不配置域名',
        )
