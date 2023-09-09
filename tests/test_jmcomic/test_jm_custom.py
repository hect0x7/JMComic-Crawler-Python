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
        save_dir = dir_rule.deside_image_save_dir(
            MyAlbum('1', *['0'] * 13),
            MyPhoto('2', *['0'] * 7)
        )

        self.assertEqual(
            os.path.abspath(save_dir),
            os.path.abspath(base_dir + dic[1] + '/' + dic[2]),
        )
