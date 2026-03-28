from test_jmcomic import *


class Test_Plugin(JmTestConfigurable):

    def test_plugin_missing_album_context(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/523

        测试当仅下载单章(photo)时，如果上下文中缺少 album 对象，
        各个包含路径生成的插件(如 download_cover, img2pdf, long_img, zip)
        是否能正确从 photo.from_album 中提取专辑属性，
        避免解析需要 {Atitle} 等本子级占位符时报错 KeyError。
        """
        option = self.new_option()

        flawed_rule = {
            'base_dir': option.dir_rule.base_dir,
            'rule': '{Atitle}/{Aid}_photo.jpg'
        }

        # 构建本地 fixture，打断真实网络与 API 下载依赖
        album = JmAlbumDetail('111', '', None, {'id': '111', 'title': 'TestAlbum'})
        photo_with_album = JmPhotoDetail('222', '', None, {'id': '222', 'title': 'TestPhoto'})
        photo_with_album.from_album = album

        test_plugins = ['download_cover', 'img2pdf', 'long_img', 'zip']

        for plugin_key in test_plugins:
            plugin_class = option.plugin_dict.get(plugin_key)
            if not plugin_class:
                continue

            # 实例化
            plugin: JmOptionPlugin = plugin_class(option)

            # 孤立测试路径解析，绕过外部 optional dependencies (如 img2pdf, Pillow) 的阻扰
            try:
                # 传入 album=None，预期插件内部提取 photo_with_album 的 from_album 并在路径中成功解析 TestAlbum
                filepath = plugin.decide_filepath(None, photo_with_album, '{Atitle}', '.jpg', None, flawed_rule)
                self.assertIn('TestAlbum', filepath, f"Plugin {plugin_key} Failed to resolve Atitle.")
            except KeyError as e:
                self.fail(f"Plugin {plugin_key} Failed to populate album from photo object: {e}")

        print('✅ All folder rule plugins passed self-contained path generation tests without dependency requirements.')
