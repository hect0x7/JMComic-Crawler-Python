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

    def test_strict_dependencies(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/572

        测试开启 plugins.strict_dependencies 后：
        1. 启用的插件缺少依赖库时，在 option 初始化（after_init）阶段直接报错
        2. 未开启时保持原有行为，不校验
        """
        from jmcomic import JmOption, JmModuleConfig, JmcomicException

        # 临时给 img2pdf 插件声明一个必然不存在的依赖，保证测试不依赖运行环境装了什么库
        pclass = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
        origin_deps = pclass.optional_dependencies
        pclass.optional_dependencies = ('__lib_not_exists__',)
        try:
            # 1) 开启 strict_dependencies，构建 option 时应直接抛异常
            dic = {
                'plugins': {
                    'strict_dependencies': True,
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            with self.assertRaises(JmcomicException) as ctx:
                JmOption.construct(dic)
            self.assertIn('strict_dependencies', str(ctx.exception))
            self.assertIn('pip install jmcomic[plugins]', str(ctx.exception))
            print('✅ strict_dependencies on: missing lib raises at option init.')

            # 2) 未开启时，不做校验，正常构建
            dic2 = {
                'plugins': {
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            option = JmOption.construct(dic2)
            self.assertIsNotNone(option)
            print('✅ strict_dependencies off: keeps silent as before.')
        finally:
            pclass.optional_dependencies = origin_deps

    def test_strict_dependencies_kwargs_aware(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/pull/575 (CodeRabbit review)

        校验应感知插件配置（required_dependencies_for），并直接测真实解析器，
        只 mock importlib.util.find_spec 模拟库缺失，不替换解析器本身：
        1. 未加密 zip：真实解析器返回 ()，即便 pyzipper/py7zr 缺失也不误报
        2. 加密 zip（impl=7z）：解析器返回 py7zr，缺失时报错
        3. 默认加密 zip：解析器返回 pyzipper，缺失时报错
        4. img2pdf 未加密：解析器返回 (img2pdf,)，不查 pikepdf
        5. img2pdf 加密：解析器返回 (img2pdf, pikepdf)，缺失时报错
        """
        import importlib.util as _iu
        from unittest import mock

        from jmcomic import JmOption, JmcomicException

        real_find_spec = _iu.find_spec

        def find_spec_missing(*missing):
            def fake(name, *args, **kwargs):
                if name in missing:
                    return None
                return real_find_spec(name, *args, **kwargs)
            return fake

        def build_zip(kwargs):
            return {'plugins': {'strict_dependencies': True,
                                'after_album': [{'plugin': 'zip', 'kwargs': kwargs}]}}

        # 1) 未加密 zip：不查任何加密库
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pyzipper', 'py7zr')):
            self.assertIsNotNone(JmOption.construct(build_zip({'zip_dir': './'})))
        print('✅ real resolver: plain zip needs no optional lib.')

        # 2) 加密 zip（impl=7z）：查 py7zr
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('py7zr')):
            with self.assertRaises(JmcomicException):
                JmOption.construct(build_zip({'zip_dir': './', 'encrypt': {'impl': '7z'}}))
        print('✅ real resolver: 7z zip requires py7zr.')

        # 3) 默认加密 zip：查 pyzipper
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pyzipper')):
            with self.assertRaises(JmcomicException):
                JmOption.construct(build_zip({'zip_dir': './', 'encrypt': {'type': 'sha256'}}))
        print('✅ real resolver: encrypted zip requires pyzipper.')

        # 4) img2pdf 未加密：不查 pikepdf
        dic4 = {'plugins': {'strict_dependencies': True,
                            'after_album': [{'plugin': 'img2pdf'}]}}
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pikepdf')):
            self.assertIsNotNone(JmOption.construct(dic4))

        # 5) img2pdf 加密：查 pikepdf
        dic5 = {'plugins': {'strict_dependencies': True,
                            'after_album': [{'plugin': 'img2pdf', 'kwargs': {'encrypt': {'type': 'sha256'}}}]}}
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pikepdf')):
            with self.assertRaises(JmcomicException):
                JmOption.construct(dic5)
        print('✅ real resolver: img2pdf requires pikepdf only when encrypt.')

    def test_strict_dependencies_rejects_non_mapping_encrypt(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/pull/575 (CodeRabbit review)

        encrypt 必须是映射。写成真值标量（encrypt: enabled）时，之前会在
        required_dependencies_for 里 encrypt.get(...) 抛 AttributeError，
        报错既不是 JmcomicException、也绕过了配置校验机制。
        现在应统一抛出可读的配置错误。
        """
        from jmcomic import JmOption, JmcomicException

        for bad in ('enabled', True, 1):
            dic = {'plugins': {'strict_dependencies': True,
                               'after_album': [{'plugin': 'zip',
                                                'kwargs': {'zip_dir': './', 'encrypt': bad}}]}}
            # 不能是 AttributeError
            try:
                JmOption.construct(dic)
            except JmcomicException as e:
                self.assertIn('encrypt', str(e))
            except AttributeError as e:
                self.fail(f'encrypt={bad!r} 仍抛 AttributeError: {e}')
            else:
                self.fail(f'encrypt={bad!r} 应当抛配置错误，实际构建成功')
        print('✅ non-mapping encrypt rejected with a readable config error.')

        # 未开启 strict_dependencies 时，construct 阶段不校验插件配置，
        # 但真正调用 zip 插件时应抛出可读的配置错误，而不是 AttributeError
        from jmcomic import JmModuleConfig

        zip_cls = JmModuleConfig.REGISTRY_PLUGIN['zip']

        class _FakeOption:
            pass

        fake = _FakeOption()
        try:
            zip_cls(fake).check_encrypt_param('enabled')
        except JmcomicException as e:
            self.assertIn('encrypt', str(e))
        except AttributeError as e:
            self.fail(f'zip 插件仍抛 AttributeError: {e}')
        else:
            self.fail('非 mapping 的 encrypt 应当抛配置错误')
        print('✅ non-mapping encrypt rejected instead of raising AttributeError.')

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
                                'fields': {'language': 'zh', 'series index': '1'},
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
            self.assertIsNone(root.find('.//dc:series_index', ns), '非法Dublin Core元素名应被忽略')
            self.assertIsNone(root.find('.//{"series index"}', ns))
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
