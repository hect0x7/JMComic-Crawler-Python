from test_jmcomic import *


class Test_DirTree(JmTestConfigurable):

    def test_dir_tree(self):
        album_detail = JmAlbumDetail(None, None, 'album-title', [], 0, ['album-author'], '')
        photo_detail = JmPhotoDetail('6666', None, 'photo-title', [], '0', [], 'domain', 'photo-author', None)

        ans = {
            'Bd_Author_Title_Image': '/album-author/photo-title/',
            'Bd_Author_Id_Image': '/album-author/6666/',
            'Bd_Title_Title_Image': '/album-title/photo-title/',
            'Bd_Title_Id_Image': '/album-title/6666/',
            'Bd_Title_Image': '/photo-title/',
            'Bd_Id_Image': '/6666/'
        }

        Bd = workspace()
        dic = {}
        for name, flag in DownloadDirTree.accept_flag_dict().items():
            image_save_dir = DownloadDirTree.of(
                Bd, flag
            ).deside_image_save_dir(album_detail, photo_detail)

            dic[name] = image_save_dir.replace(Bd, '/')
            print(f"{name:20s}\t|\t{image_save_dir.replace(Bd, '/')}")

        self.assertDictEqual(ans, dic)
