from test_jmcomic import *

try:
    import jmcomic_calibre  # noqa: F401
    HAS_JMCOMIC_CALIBRE = True
except ImportError:
    HAS_JMCOMIC_CALIBRE = False


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

    def test_dependencies_strategy_failed_fast(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/572

        测试默认/显式配置 plugins.dependencies_strategy: failed-fast：
        1. 默认情况下，启用的插件缺少依赖库时，在 option 初始化阶段直接报错，报错提示包含3种解决方案
        2. 显式配置 dependencies_strategy: failed-fast 同样快速失败
        3. 配置 ignore-only-log 时，仅打印日志不报错
        """
        from jmcomic import JmOption, JmModuleConfig, JmcomicException

        pclass = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
        origin_deps = pclass.plugin_dependencies
        pclass.plugin_dependencies = ('__lib_not_exists__',)
        try:
            # 1) 默认策略（即 failed-fast），构建 option 时应直接抛异常
            dic_default = {
                'plugins': {
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            with self.assertRaises(JmcomicException) as ctx:
                JmOption.construct(dic_default)
            err_text = str(ctx.exception)
            self.assertIn('dependencies_strategy: failed-fast', err_text)
            self.assertIn('pip install jmcomic[plugins]', err_text)
            self.assertIn('pip install __lib_not_exists__', err_text)
            print('✅ default strategy (failed-fast): missing lib raises at option init with guide.')

            # 2) 显式配置 dependencies_strategy: failed-fast
            dic_explicit = {
                'plugins': {
                    'dependencies_strategy': 'failed-fast',
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            with self.assertRaises(JmcomicException) as ctx:
                JmOption.construct(dic_explicit)
            self.assertIn('dependencies_strategy: failed-fast', str(ctx.exception))
            print('✅ explicit failed-fast: missing lib raises at option init.')

            # 3) 配置 ignore-only-log: 仅打印警告，不阻断构建
            dic_ignore = {
                'plugins': {
                    'dependencies_strategy': 'ignore-only-log',
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            option = JmOption.construct(dic_ignore)
            self.assertIsNotNone(option)
            print('✅ ignore-only-log: logs warning and builds successfully.')
        finally:
            pclass.plugin_dependencies = origin_deps

    def test_dependencies_strategy_auto_install(self):
        """
        测试 plugins.dependencies_strategy: auto-install 行为：
        1. 缺失依赖时，触发 install_missing_dependencies
        2. 若 pip 安装失败，严格抛出异常
        """
        from unittest import mock
        from jmcomic import JmOption, JmModuleConfig, JmcomicException

        pclass = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
        origin_deps = pclass.plugin_dependencies
        pclass.plugin_dependencies = ('__fake_lib_to_install__',)
        try:
            dic = {
                'plugins': {
                    'dependencies_strategy': 'auto-install',
                    'after_album': [{'plugin': 'img2pdf'}],
                }
            }
            # 模拟安装成功
            with mock.patch.object(pclass, 'install_missing_dependencies') as mock_install:
                option = JmOption.construct(dic)
                self.assertIsNotNone(option)
                mock_install.assert_called_once_with(['__fake_lib_to_install__'])
            print('✅ auto-install: triggers install_missing_dependencies with missing packages.')

            # 模拟安装抛错，严格失败
            with self.assertRaises(JmcomicException) as ctx:
                JmOption.construct(dic)
            self.assertIn('自动安装依赖', str(ctx.exception))
            print('✅ auto-install: strict failure when pip install fails.')
        finally:
            pclass.plugin_dependencies = origin_deps

    def test_dependencies_strategy_kwargs_aware(self):
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
                # img2pdf 是 img2pdf 插件的无条件依赖，未显式列入 missing 时
                # 固定返回非 None，避免用例结果取决于运行环境装没装 img2pdf，
                # 也让加密用例能确定性地走到 pikepdf 检查
                if name == 'img2pdf':
                    return object()
                return real_find_spec(name, *args, **kwargs)
            return fake

        def build_zip(kwargs):
            return {'plugins': {'after_album': [{'plugin': 'zip', 'kwargs': kwargs}]}}

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
        dic4 = {'plugins': {'after_album': [{'plugin': 'img2pdf'}]}}
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pikepdf')):
            self.assertIsNotNone(JmOption.construct(dic4))

        # 5) img2pdf 加密：查 pikepdf
        dic5 = {'plugins': {'after_album': [{'plugin': 'img2pdf', 'kwargs': {'encrypt': {'type': 'sha256'}}}]}}
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
            dic = {'plugins': {'after_album': [{'plugin': 'zip',
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

        # 真正调用 zip 插件时也应抛出可读的配置错误，而不是 AttributeError
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

    @unittest.skipUnless(
        HAS_JMCOMIC_CALIBRE,
        '这条用例依赖 jmcomic-calibre 生成 OPF：pip install jmcomic-calibre',
    )
    def test_calibre_metadata(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/573

        测试 calibre_metadata 插件（OPF 由 jmcomic-calibre 生成）：
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

    def test_favorite_folder_export_retry_and_failure_report(self):
        """
        source: https://github.com/hect0x7/JMComic-Crawler-Python/issues/447

        收藏夹导出时，单个收藏夹抓取失败不应该被静默丢掉：
        1. 失败的收藏夹会按 max_retry 重试（max_retry 指重试次数，总尝试次数是 max_retry + 1）
        2. 重试仍失败的收藏夹会被汇总抛出，而不是无声无息
        3. 成功的收藏夹不受影响
        """
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, PluginValidationException

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_fav_export_')
        try:
            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_enable = False
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'export.zip'))
            plugin.zip_password = None
            plugin.delete_original_file = False
            plugin.max_retry = 3
            plugin.files = []
            plugin.failed_folders = []

            fetch_calls = []

            def fake_fetch(fid):
                fetch_calls.append(fid)
                if fid == 'bad':
                    raise RuntimeError('会话已失效')
                return ['page']

            def fake_save(page_data, fid, fname):
                return os.path.join(tmp, f'{fid}.csv')

            with (
                patch.object(plugin, 'fetch_folder_page_data', side_effect=fake_fetch),
                patch.object(plugin, 'save_folder_page_data_to_file', side_effect=fake_save),
                patch.object(plugin, 'retry_backoff'),
            ):
                plugin.handle_folder('good', '正常收藏夹')
                plugin.handle_folder('bad', '坏掉的收藏夹')

                # 正常收藏夹只取一次；失败的收藏夹共尝试 max_retry + 1 次（首次 + 3 次重试）
                self.assertEqual(['good', 'bad', 'bad', 'bad', 'bad'], fetch_calls)
                self.assertEqual([os.path.join(tmp, 'good.csv')], plugin.files)
                self.assertEqual(1, len(plugin.failed_folders))
                self.assertEqual('bad', plugin.failed_folders[0][0])

                # 导出结束后应抛出明确异常，而不是静默返回
                with self.assertRaises(PluginValidationException) as ctx:
                    plugin.raise_if_failed_folders()
                self.assertIn('坏掉的收藏夹', ctx.exception.msg)
                self.assertIn('导出失败', ctx.exception.msg)
            print('✅ Failed folder retried and reported instead of being dropped silently.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_favorite_folder_export_all_success_does_not_raise(self):
        """全部成功时导出不应抛出异常。"""
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_fav_ok_')
        try:
            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_enable = False
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'export.zip'))
            plugin.max_retry = 2
            plugin.files = []
            plugin.failed_folders = []

            saved = os.path.join(tmp, '1.csv')
            with (
                patch.object(plugin, 'fetch_folder_page_data', return_value=['page']),
                patch.object(plugin, 'save_folder_page_data_to_file', return_value=saved),
            ):
                plugin.handle_folder('1', '收藏夹1')

            self.assertEqual([saved], plugin.files)
            self.assertEqual([], plugin.failed_folders)
            plugin.raise_if_failed_folders()
            print('✅ Successful export raises nothing.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_favorite_folder_export_max_retry_zero(self):
        """
        max_retry=0 表示不重试：只尝试一次，失败后直接记进 failed_folders。
        """
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_fav_zero_')
        try:
            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_enable = False
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'export.zip'))
            plugin.max_retry = 0
            plugin.files = []
            plugin.failed_folders = []

            fetch_calls = []

            def fake_fetch(fid):
                fetch_calls.append(fid)
                raise RuntimeError('会话已失效')

            with (
                patch.object(plugin, 'fetch_folder_page_data', side_effect=fake_fetch),
                patch.object(plugin, 'retry_backoff'),
            ):
                plugin.handle_folder('bad', '坏掉的收藏夹')

            # max_retry=0 → 只尝试一次，不应出现重试
            self.assertEqual(['bad'], fetch_calls)
            self.assertEqual(1, len(plugin.failed_folders))
            print('✅ max_retry=0 means no retry, single attempt only.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_favorite_folder_export_zips_successful_files_before_raising(self):
        """
        开启 zip 时，即使有收藏夹导出失败，成功抓下来的文件也应该先打包完成，
        再统一抛出失败汇总——不能因为一个收藏夹失败就把整批已成功的数据丢掉。
        """
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, PluginValidationException

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_fav_zip_')
        try:
            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_enable = True
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'export.zip'))
            plugin.zip_password = None
            plugin.delete_original_file = False
            plugin.max_retry = 0
            plugin.files = []
            plugin.failed_folders = []

            # 模拟 main() 里的收藏夹枚举结果。
            # 注意 '0'（特殊收藏栏【全部】）也会被 main() 枚举到，
            # 所以这里必须显式让它无数据，否则会平白多出一个导出文件。
            class FakePage:
                def iter_folder_id_name(self):
                    return [('good', '正常收藏夹'), ('bad', '坏掉的收藏夹')]

            class FakeClient:
                def favorite_folder(self):
                    return FakePage()

            zipped = []
            deleted = []
            events = []

            def fake_fetch(fid):
                if fid in ('bad', '0'):
                    raise RuntimeError('会话已失效')
                return ['page']

            def fake_zip(files, filepath):
                zipped.append(list(files))
                events.append('zip')

            def fake_delete(files):
                deleted.append(list(files))
                events.append('delete')

            with (
                patch.object(plugin, 'fetch_folder_page_data', side_effect=fake_fetch),
                patch.object(plugin, 'save_folder_page_data_to_file',
                             side_effect=lambda page_data, fid, fname: os.path.join(tmp, f'{fid}.csv')),
                patch.object(plugin, 'zip_folder_without_password', side_effect=fake_zip),
                patch.object(plugin, 'execute_deletion', side_effect=fake_delete),
            ):
                # main() 里通过 option.build_jm_client 拿 client，这里直接替换 option 的方法
                with patch.object(plugin.option, 'build_jm_client', return_value=FakeClient()):
                    with self.assertRaises(PluginValidationException):
                        plugin.main()

            # 成功的文件必须先被打包，且打包发生在抛错之前
            self.assertEqual(1, len(zipped))
            self.assertEqual([os.path.join(tmp, 'good.csv')], zipped[0])
            self.assertEqual(1, len(deleted))
            # 打包必须先于删源，否则删源会把还没进包的源文件删掉
            self.assertEqual(['zip', 'delete'], events)
            print('✅ Successful files zipped before the failure summary is raised.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_favorite_folder_export_encrypted_zip_only_includes_exported_files(self):
        """
        zip_password 非空时走 7z 加密打包，同样只能打包本次导出的文件。

        原实现是 `7z a "{zip}" "./"`，会把 save_dir 下的一切都卷进去：
        上一轮遗留的旧导出、失败收藏夹写了一半的 csv。
        这些文件不在 execute_deletion 的删除范围内，等于往产物里混入无关数据。
        """
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, PluginValidationException

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_fav_enc_')
        try:
            # 干扰项：历史遗留导出 + 失败留下的半截文件
            stale = os.path.join(tmp, 'old_export.csv')
            half = os.path.join(tmp, 'bad.csv')
            with open(stale, 'w', encoding='utf-8') as f:
                f.write('id,author,name\n9,z,w\n')
            with open(half, 'w', encoding='utf-8') as f:
                f.write('id,author,name\n2,b,y\n')

            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_enable = True
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'export.zip'))
            plugin.zip_password = 'secret'
            plugin.delete_original_file = False
            plugin.max_retry = 0
            plugin.files = []
            plugin.failed_folders = []

            class FakePage:
                def iter_folder_id_name(self):
                    return [('good', '正常收藏夹'), ('bad', '坏掉的收藏夹')]

            class FakeClient:
                def favorite_folder(self):
                    return FakePage()

            def fake_fetch(fid):
                if fid in ('bad', '0'):
                    raise RuntimeError('会话已失效')
                return ['page']

            captured = {}

            def fake_zip_with_password(files, zip_path):
                captured['files'] = list(files)

            with (
                patch.object(plugin, 'fetch_folder_page_data', side_effect=fake_fetch),
                patch.object(plugin, 'save_folder_page_data_to_file',
                             side_effect=lambda page_data, fid, fname: os.path.join(tmp, f'{fid}.csv')),
                patch.object(plugin, 'zip_with_password', side_effect=fake_zip_with_password),
                patch.object(plugin, 'execute_deletion'),
            ):
                with patch.object(plugin.option, 'build_jm_client', return_value=FakeClient()):
                    with self.assertRaises(PluginValidationException):
                        plugin.main()

            self.assertEqual([os.path.join(tmp, 'good.csv')], captured['files'])
            self.assertNotIn(stale, captured['files'])
            self.assertNotIn(half, captured['files'])
            print('✅ Encrypted zip receives only this run\'s exported files.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_zip_with_password_does_not_archive_whole_save_dir(self):
        """7z 命令必须逐个列举文件，不能再用 './' 打包整个 save_dir。"""
        import tempfile
        import shutil
        from unittest.mock import patch

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin

        option = self.new_option()
        tmp = tempfile.mkdtemp(prefix='jm_test_7z_cmd_')
        try:
            plugin = FavoriteFolderExportPlugin(option)
            plugin.save_dir = tmp
            plugin.zip_filepath = os.path.abspath(os.path.join(tmp, 'out.zip'))
            plugin.zip_password = 'secret'

            good = os.path.join(tmp, 'good.csv')
            cmds = []
            with patch.object(plugin, 'execute_multi_line_cmd', side_effect=cmds.append):
                plugin.zip_with_password([good], plugin.zip_filepath)

            self.assertEqual(1, len(cmds))
            cmd = cmds[0]
            self.assertIn('good.csv', cmd)
            self.assertNotIn('"./"', cmd)
            self.assertNotIn("'./'", cmd)
            print('✅ 7z command enumerates files instead of archiving "./".')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
