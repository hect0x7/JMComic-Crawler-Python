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
        photo_id = '350234'
        option = self.new_option()

        flawed_rule = {
            'base_dir': option.dir_rule.base_dir,
            'rule': '{Atitle}/{Aid}_photo.jpg'
        }

        from jmcomic.jm_downloader import DoNotDownloadImage

        # 将四个需要校验的插件全部进行孤立测试，避免前一个插件后续报错导致循环终端
        test_plugins = ['download_cover', 'img2pdf', 'long_img', 'zip']
        option.plugins['before_photo'] = [
            {
                'plugin': plugin_key,
                'kwargs': {'dir_rule': flawed_rule},
                'safe': False  # 防止内部catch异常
            }
            for plugin_key in test_plugins
        ]

        download_photo(photo_id, option, downloader=DoNotDownloadImage)
        print('✅ All folder rule plugins assert completed safely without KeyError.')

    def test_calibre_metadata(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/573

        测试 calibre_metadata 插件：
        1. after_album 阶段生成 metadata.opf，包含书名/作者/标签/identifier
        2. fields 静态字段（如 language）按维护者建议写入
        3. 作者为空时兜底 DEFAULT_AUTHOR；XML 特殊字符正确转义
        """
        import tempfile
        import shutil
        import xml.etree.ElementTree as ET

        from jmcomic import JmOption, JmModuleConfig, JmAlbumDetail

        album = JmAlbumDetail(
            album_id='123456',
            scramble_id='220980',
            name='测试<本子>名 & 特殊"字符"',
            episode_list=[],
            page_count=10,
            pub_date='2026-01-01',
            update_date='2026-01-02',
            likes='1K',
            views='2K',
            comment_count=0,
            works=['作品A'],
            actors=['角色A'],
            authors=['作者甲'],
            tags=['tag1', '中文标签'],
            description='简介 <b>含XML特殊字符</b>',
        )

        tmp = tempfile.mkdtemp(prefix='jm_test_calibre_')
        try:
            dic = {
                'dir_rule': {'rule': 'Bd_Atitle', 'base_dir': tmp},
                'plugins': {
                    'after_album': [
                        {
                            'plugin': 'calibre_metadata',
                            'kwargs': {
                                'dir_rule': {
                                    'rule': 'Bd/Atitle/metadata.opf',
                                    'base_dir': tmp,
                                },
                                'fields': {'language': 'zh'},
                            },
                        },
                    ],
                },
            }
            option = JmOption.construct(dic)
            option.call_all_plugin('after_album', album=album, downloader=None)

            import glob
            opf_list = glob.glob(os.path.join(tmp, '**', 'metadata.opf'), recursive=True)
            self.assertEqual(len(opf_list), 1, f'expected 1 opf, got: {opf_list}')
            opf_path = opf_list[0]

            root = ET.parse(opf_path).getroot()
            ns = {'dc': 'http://purl.org/dc/elements/1.1/', 'opf': 'http://www.idpf.org/2007/opf'}

            self.assertEqual(root.find('.//dc:title', ns).text, album.title)
            self.assertEqual(root.find('.//dc:creator', ns).text, '作者甲')
            self.assertEqual(
                [e.text for e in root.findall('.//dc:subject', ns)],
                ['tag1', '中文标签'],
            )
            self.assertEqual(root.find('.//dc:identifier', ns).text, 'jmcomic:123456')
            self.assertEqual(root.find('.//dc:language', ns).text, 'zh')
            self.assertEqual(root.find('.//dc:description', ns).text, '简介 <b>含XML特殊字符</b>')
            self.assertIsNone(root.find('.//{*}manifest'), 'include_cover=False 时不应有 manifest')
            print('✅ metadata.opf generated with escaped title/tags/identifier/fields.')

            # 作者为空时兜底 DEFAULT_AUTHOR
            album2 = JmAlbumDetail(
                album_id='654321', scramble_id='220980', name='无作者本子',
                episode_list=[], page_count=1, pub_date='', update_date='',
                likes='', views='', comment_count=0,
                works=[], actors=[], authors=[], tags=[],
            )
            dic2 = {
                'plugins': {
                    'after_album': [
                        {
                            'plugin': 'calibre_metadata',
                            'kwargs': {'dir_rule': {'rule': 'Bd/Aid/metadata.opf', 'base_dir': tmp}},
                        },
                    ],
                },
            }
            option2 = JmOption.construct(dic2)
            option2.call_all_plugin('after_album', album=album2, downloader=None)

            opf2 = os.path.join(tmp, '654321', 'metadata.opf')
            root2 = ET.parse(opf2).getroot()
            self.assertEqual(
                root2.find('.//dc:creator', ns).text,
                JmModuleConfig.DEFAULT_AUTHOR,
            )
            self.assertEqual(root2.find('.//dc:identifier', ns).text, 'jmcomic:654321')
            print('✅ author falls back to DEFAULT_AUTHOR when authors is empty.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
