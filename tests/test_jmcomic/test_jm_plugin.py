import os
import sys

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
        photo_id = '123'
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
        import subprocess
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
            # 执行真实策略与安装封装，只模拟 pip 子进程，避免修改测试环境。
            with mock.patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout='')) as mock_run:
                option = JmOption.construct(dic)
                self.assertIsNotNone(option)
                mock_run.assert_called_once_with(
                    [sys.executable, '-m', 'pip', 'install', '__fake_lib_to_install__'],
                    capture_output=True, text=True, check=True,
                )
            print('✅ auto-install: triggers install_missing_dependencies with missing packages.')

            # 模拟安装抛错，严格失败
            with mock.patch('subprocess.run', side_effect=subprocess.CalledProcessError(
                    1, ['pip', 'install', '__fake_lib_to_install__'], stderr='模拟安装失败',
            )) as mock_run:
                with self.assertRaises(JmcomicException) as ctx:
                    JmOption.construct(dic)
                mock_run.assert_called_once()
            self.assertIn('自动安装依赖', str(ctx.exception))
            self.assertIn('模拟安装失败', str(ctx.exception))
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
                JmOption.construct(build_zip({'zip_dir': './', 'encrypt': {'impl': '7z', 'password': 'demo'}}))
        print('✅ real resolver: 7z zip requires py7zr.')

        # 3) 默认加密 zip：查 pyzipper
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pyzipper')):
            with self.assertRaises(JmcomicException):
                JmOption.construct(build_zip({'zip_dir': './', 'encrypt': {'type': 'sha256', 'password': 'demo'}}))
        print('✅ real resolver: encrypted zip requires pyzipper.')

        # 4) img2pdf 未加密：不查 pikepdf
        dic4 = {'plugins': {'after_album': [{'plugin': 'img2pdf'}]}}
        with mock.patch('importlib.util.find_spec', side_effect=find_spec_missing('pikepdf')):
            self.assertIsNotNone(JmOption.construct(dic4))

        # 5) img2pdf 加密：查 pikepdf
        dic5 = {'plugins': {'after_album': [{'plugin': 'img2pdf', 'kwargs': {'encrypt': {'type': 'sha256', 'password': 'demo'}}}]}}
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

        # img2pdf 同样继承 JmOptionPlugin 的 encrypt 校验与密码决策能力
        pdf_cls = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
        with self.assertRaises(JmcomicException):
            pdf_cls.check_encrypt_param('enabled')

        from unittest.mock import patch
        with patch.dict(sys.modules, {'pikepdf': object(), 'pyzipper': object()}):
            pdf_plugin = pdf_cls(fake)
            pdf_plugin.log_enable = False
            fixed_pwd, is_rand = pdf_plugin.decide_password({'password': 123456}, 'demo.pdf')
            self.assertEqual(fixed_pwd, '123456')
            self.assertFalse(is_rand)

            rand_pwd, is_rand = pdf_plugin.decide_password({'type': 'random'}, 'demo.pdf')
            self.assertEqual(len(rand_pwd), 48)
            self.assertTrue(is_rand)

            # 固定密码必须显式配置 password：缺失时报错，空字符串交由底层加密库处理
            for plugin in (pdf_plugin, JmModuleConfig.REGISTRY_PLUGIN['zip'](fake)):
                plugin.log_enable = False
                for encrypt in ({}, {'password': None}):
                    with self.subTest(plugin=plugin.plugin_key, encrypt=encrypt):
                        with self.assertRaises(JmcomicException) as cm:
                            plugin.decide_password(encrypt, 'demo')
                        self.assertIn('password', str(cm.exception))
                self.assertEqual(('', False), plugin.decide_password({'password': ''}, 'demo'))
        print('✅ non-mapping encrypt rejected and decide_password shared across zip & img2pdf.')

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

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, JmcomicException

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
                with self.assertRaises(JmcomicException) as ctx:
                    plugin.raise_if_failed_folders()
                self.assertIn('坏掉的收藏夹', ctx.exception.msg)
                self.assertIn('导出失败', ctx.exception.msg)
            print('✅ Failed folder retried and reported instead of being dropped silently.')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_favorite_folder_export_failure_respects_safe(self):
        """通过插件入口验证导出失败遵循 safe，不受 valid 策略影响。"""
        from unittest.mock import patch
        from jmcomic import FavoriteFolderExportPlugin, JmcomicException

        option = self.new_option()
        plugin = FavoriteFolderExportPlugin(option)
        plugin.max_retry = 0
        plugin.failed_folders = [('bad', '失败收藏夹', RuntimeError('导出失败'))]

        for valid in ('log', 'ignore', 'raise'):
            for safe in (True, False):
                with self.subTest(valid=valid, safe=safe):
                    option.plugins['main'] = [dict(
                        plugin='favorite_folder_export', valid=valid, safe=safe,
                    )]
                    with (
                        patch.object(FavoriteFolderExportPlugin, 'build', return_value=plugin),
                        patch.object(plugin, 'invoke', side_effect=plugin.raise_if_failed_folders),
                    ):
                        if safe:
                            option.call_all_plugin('main')
                        else:
                            with self.assertRaises(JmcomicException) as ctx:
                                option.call_all_plugin('main')
                            self.assertIn('失败收藏夹', ctx.exception.msg)

    def test_favorite_folder_export_empty_encrypted_zip_skips_command(self):
        """没有成功文件时不启动 7z，失败汇总仍能正常抛出。"""
        from unittest.mock import patch
        from jmcomic import FavoriteFolderExportPlugin, JmcomicException

        plugin = FavoriteFolderExportPlugin(self.new_option())
        plugin.max_retry = 0
        plugin.failed_folders = [('bad', '失败收藏夹', RuntimeError('导出失败'))]
        with patch.object(plugin, 'execute_multi_line_cmd') as execute:
            plugin.zip_with_password([], 'export.7z')
            execute.assert_not_called()
        with self.assertRaises(JmcomicException):
            plugin.raise_if_failed_folders()

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

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, JmcomicException

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
                    with self.assertRaises(JmcomicException):
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

        from jmcomic.jm_plugin import FavoriteFolderExportPlugin, JmcomicException

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
                    with self.assertRaises(JmcomicException):
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

    def test_async_plugin_invocation_and_download_cover(self):
        """测试 call_all_plugin_async：download_cover 走 async_invoke，同步插件自动走 asyncio.to_thread 工作线程"""
        import asyncio
        import tempfile
        import shutil
        import threading
        from jmcomic.jm_async_downloader import JmAsyncDownloader
        from jmcomic.jm_plugin import JmOptionPlugin

        tmp = tempfile.mkdtemp(prefix='jm_test_async_plugin_')
        try:
            option = self.new_option()
            cover_calls = []
            sync_thread_names = []
            main_thread = threading.current_thread().name

            class DummySyncPlugin(JmOptionPlugin):
                plugin_key = 'dummy_sync_for_async_test'

                def invoke(self, **kwargs):
                    sync_thread_names.append(threading.current_thread().name)

            JmModuleConfig.register_plugin(DummySyncPlugin)

            option.plugins['before_album'] = [
                {
                    'plugin': 'download_cover',
                    'kwargs': {
                        'dir_rule': {'base_dir': tmp, 'rule': 'Bd/{Aid}_cover.jpg'},
                        'size': '_3x4',
                    },
                    'safe': False,
                },
                {
                    'plugin': 'dummy_sync_for_async_test',
                    'kwargs': {},
                    'safe': False,
                },
            ]

            class FakeAsyncClient:
                async def download_album_cover(self, album_id, save_path, size='', decode_executor=None):
                    cover_calls.append((album_id, save_path, size, decode_executor))

            dler = JmAsyncDownloader(option, decode_worker=1)
            dler.client = FakeAsyncClient()
            album = JmAlbumDetail(
                album_id='123',
                scramble_id='0',
                name='test_album',
                episode_list=[],
                page_count=1,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )

            try:
                asyncio.run(dler._dispatch_plugin('before_album', album=album, downloader=dler))
                self.assertEqual(1, len(cover_calls))
                self.assertEqual('123', cover_calls[0][0])
                self.assertEqual('_3x4', cover_calls[0][2])
                self.assertIs(cover_calls[0][3], dler._decode_pool)
                self.assertEqual(1, len(sync_thread_names))
                self.assertNotEqual(main_thread, sync_thread_names[0])
                self.assertFalse(sync_thread_names[0].startswith('jm-async-decode'))

                class CancelledAsyncPlugin(JmOptionPlugin):
                    plugin_key = 'cancelled_async_for_test'

                    async def async_invoke(self, **kwargs):
                        raise asyncio.CancelledError()

                JmModuleConfig.register_plugin(CancelledAsyncPlugin)
                option.plugins['cancel_test'] = [{'plugin': 'cancelled_async_for_test', 'safe': True}]
                with self.assertRaises(asyncio.CancelledError):
                    asyncio.run(option.call_all_plugin_async('cancel_test', safe=True))

                from jmcomic.jm_client_interface import AsyncJmcomicClient

                class DummyCoverClient(AsyncJmcomicClient):
                    async def get_jm_image(self, img_url):
                        class FakeImgResp:
                            def require_success(self_resp):
                                pass

                            def transfer_to(self_resp, path, scramble_id, decode_image=True, img_url=None):
                                with open(path, 'wb') as f:
                                    f.write(b'cover_bytes')

                        return FakeImgResp()

                cover_out = os.path.join(tmp, 'real_cover.jpg')
                asyncio.run(
                    DummyCoverClient().download_album_cover('123', cover_out, decode_executor=dler._decode_pool))
                self.assertGreater(os.path.getsize(cover_out), 0)
            finally:
                dler.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_calibre_metadata_plugin_sync_and_async_thread_offload(self):
        """测试 calibre_metadata 插件同步/异步复用逻辑，验证 async_invoke 中 export_opf 在工作线程执行"""
        import asyncio
        import shutil
        import sys
        import tempfile
        import threading
        from types import SimpleNamespace
        from unittest.mock import patch
        from jmcomic.jm_async_downloader import JmAsyncDownloader

        tmp = tempfile.mkdtemp(prefix='jm_test_calibre_plugin_')
        try:
            option = self.new_option()
            export_calls = []
            cover_calls = []

            def fake_export_opf(album, opf_path, fields=None, include_cover=False, on_ignored=None):
                if fields and 'unsupported' in fields and on_ignored is not None:
                    on_ignored('unsupported', {'language', 'publisher'})
                with open(opf_path, 'w', encoding='utf-8') as f:
                    f.write(f'<package>{album.id}</package>')
                export_calls.append((threading.current_thread().name, opf_path, fields, include_cover))

            fake_calibre = SimpleNamespace(export_opf=fake_export_opf)
            album = JmAlbumDetail(
                album_id='456',
                scramble_id='0',
                name='calibre_album',
                episode_list=[],
                page_count=1,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )

            class FakeSyncClient:
                def download_album_cover(self_cl, album_id, save_path, size=''):
                    cover_calls.append(('sync', album_id, save_path, size, None))
                    with open(save_path, 'wb') as f:
                        f.write(b'sync_cover')

            class FakeAsyncClient:
                async def download_album_cover(self_cl, album_id, save_path, size='', decode_executor=None):
                    cover_calls.append(('async', album_id, save_path, size, decode_executor))
                    with open(save_path, 'wb') as f:
                        f.write(b'async_cover')

            with patch.dict(sys.modules, {'jmcomic_calibre': fake_calibre}):
                # 1. 同步 invoke
                sync_dler = SimpleNamespace(client=FakeSyncClient())
                option.plugins['calibre_sync'] = [{
                    'plugin': 'calibre_metadata',
                    'kwargs': {
                        'dir_rule': {'base_dir': tmp, 'rule': 'Bd/sync_{Aid}/metadata.opf'},
                        'include_cover': True,
                        'fields': {'language': 'zh', 'unsupported': 'x'},
                    },
                    'safe': False,
                }]
                option.call_all_plugin('calibre_sync', album=album, downloader=sync_dler, safe=False)
                self.assertEqual(1, len(export_calls))
                self.assertTrue(os.path.exists(export_calls[0][1]))
                self.assertEqual('sync', cover_calls[0][0])

                # 2. 异步 async_invoke（带 JmAsyncDownloader：封面走 decode_pool，export_opf 走 asyncio.to_thread 工作线程而非 decode_pool）
                main_thread = threading.current_thread().name
                dler = JmAsyncDownloader(option, decode_worker=1)
                dler.client = FakeAsyncClient()
                try:
                    option.plugins['calibre_async'] = [{
                        'plugin': 'calibre_metadata',
                        'kwargs': {
                            'dir_rule': {'base_dir': tmp, 'rule': 'Bd/async_{Aid}/metadata.opf'},
                            'include_cover': True,
                            'fields': {'language': 'zh'},
                        },
                        'safe': False,
                    }]
                    asyncio.run(dler._dispatch_plugin('calibre_async', album=album, downloader=dler))
                    self.assertEqual(2, len(export_calls))
                    self.assertNotEqual(main_thread, export_calls[1][0])
                    self.assertFalse(export_calls[1][0].startswith('jm-async-decode'))
                    self.assertEqual('async', cover_calls[1][0])
                    self.assertIs(cover_calls[1][4], dler._decode_pool)

                    # 再次触发时命中封面缓存，不重复下载封面
                    asyncio.run(dler._dispatch_plugin('calibre_async', album=album, downloader=dler))
                    self.assertEqual(2, len(cover_calls))
                    self.assertEqual(3, len(export_calls))
                finally:
                    dler.shutdown()

                # 3. 异步 async_invoke（无 downloader 且 include_cover=False：export_opf 走 asyncio.to_thread）
                option.plugins['calibre_async_no_dler'] = [{
                    'plugin': 'calibre_metadata',
                    'kwargs': {
                        'dir_rule': {'base_dir': tmp, 'rule': 'Bd/nodler_{Aid}/metadata.opf'},
                        'include_cover': False,
                    },
                    'safe': False,
                }]
                asyncio.run(option.call_all_plugin_async('calibre_async_no_dler', album=album, safe=False))
                self.assertEqual(4, len(export_calls))
                self.assertNotEqual(main_thread, export_calls[3][0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_zip_plugin_after_photo_scopes_to_current_photo(self):
        """
        多章节本子将 zip 插件配置在 after_photo 且开启 delete_original_file=True 时：
        1. 第一章完成时只打包并删除第一章的图片与目录，不得误删正在下载的第二章图片/目录；
        2. 第二章完成时只打包并删除第二章的图片与目录，不得覆盖清空第一章已生成的 zip，也不得因第一章目录已删除而抛 FileNotFoundError。
        """
        import shutil
        import tempfile
        import zipfile
        from jmcomic import JmAlbumDetail, JmOption, JmPhotoDetail
        from jmcomic.jm_downloader import JmDownloader

        tmp = tempfile.mkdtemp(prefix='jm_test_zip_after_photo_')
        try:
            img_base = os.path.join(tmp, 'images')
            zip_base = os.path.join(tmp, 'zips')
            opt = JmOption.construct({
                'dir_rule': {
                    'base_dir': img_base,
                    'rule': 'Bd / Aid / Ptitle',
                },
                'plugins': {
                    'after_photo': [{
                        'plugin': 'zip',
                        'kwargs': {
                            'filename_rule': 'Ptitle',
                            'zip_dir': zip_base,
                            'delete_original_file': True,
                        },
                        'safe': False,
                    }],
                },
            })

            album = JmAlbumDetail(
                album_id='145504',
                scramble_id='0',
                name='测试多章本子',
                episode_list=[('145504', '1', '第一章', ''), ('145505', '2', '第二章', '')],
                page_count=4,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )
            photo1 = JmPhotoDetail(
                photo_id='145504',
                scramble_id='0',
                name='第一章',
                series_id='145504',
                sort='1',
                page_arr=['00001.webp', '00002.webp'],
                data_original_domain='example.com',
                from_album=album,
            )
            photo2 = JmPhotoDetail(
                photo_id='145505',
                scramble_id='0',
                name='第二章',
                series_id='145504',
                sort='2',
                page_arr=['00001.webp', '00002.webp'],
                data_original_domain='example.com',
                from_album=album,
            )

            dir1 = opt.decide_image_save_dir(photo1)
            dir2 = opt.decide_image_save_dir(photo2)
            p1_img1 = os.path.join(dir1, '00001.webp')
            p1_img2 = os.path.join(dir1, '00002.webp')
            p2_img1 = os.path.join(dir2, '00001.webp')
            p2_img2 = os.path.join(dir2, '00002.webp')
            for p in (p1_img1, p1_img2, p2_img1):
                with open(p, 'wb') as f:
                    f.write(b'img_data')

            dler = JmDownloader(opt)
            dler.begin_manifest(album)
            image11, image12 = photo1[0], photo1[1]
            image21, image22 = photo2[0], photo2[1]
            image11.save_path, image12.save_path = p1_img1, p1_img2
            image21.save_path, image22.save_path = p2_img1, p2_img2
            # 模拟两章并发启动：photo1 已下完两张图，photo2 刚下完第一张图
            dler.download_success_dict[album] = {
                photo1: [(p1_img1, image11), (p1_img2, image12)],
                photo2: [(p2_img1, image21)],
            }

            # 1) photo1 触发 after_photo
            dler.after_photo(photo1)
            zip1_path = os.path.join(zip_base, '第一章.zip')
            zip2_path = os.path.join(zip_base, '第二章.zip')
            self.assertTrue(os.path.exists(zip1_path))
            self.assertFalse(os.path.exists(zip2_path))
            self.assertFalse(os.path.exists(dir1))
            # photo2 仍在下载中的图片和目录必须完好无损
            self.assertTrue(os.path.exists(p2_img1))

            # 2) photo2 随后下完第二张图并触发 after_photo
            with open(p2_img2, 'wb') as f:
                f.write(b'img_data')
            dler.download_success_dict[album][photo2].append((p2_img2, image22))
            dler.after_photo(photo2)

            self.assertTrue(os.path.exists(zip2_path))
            self.assertFalse(os.path.exists(dir2))
            with zipfile.ZipFile(zip1_path, 'r') as z1:
                self.assertEqual(['00001.webp', '00002.webp'], sorted(z1.namelist()))
            with zipfile.ZipFile(zip2_path, 'r') as z2:
                self.assertEqual(['00001.webp', '00002.webp'], sorted(z2.namelist()))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_zip_migrate_level_only_when_explicit(self):
        """
        验证 _migrate_zip_level 仅在用户显式配置了已废弃的 level 参数时触发迁移与提示日志：
        1. after_album / after_photo 未配置 level 时保持原钩子不变，且不打印 option.migrate 日志；
        2. after_album + level=photo 自动迁移至 after_photo 并移除 level；
        3. after_photo + level=album 自动迁移至 after_album 并移除 level；
        4. level 与所在钩子一致时保持原钩子，移除 level 并打印过时提示。
        """
        from unittest.mock import patch
        from jmcomic import JmOption

        # 1) 未写 level 或显式 level=None（YAML level: null）：after_album 与 after_photo 均原样保留，不打迁移日志
        with patch('jmcomic.jm_option.jm_log') as mock_log:
            opt_album = JmOption.construct({
                'plugins': {
                    'after_album': [{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}],
                }
            })
            opt_photo = JmOption.construct({
                'plugins': {
                    'after_photo': [{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}],
                }
            })
            opt_null_album = JmOption.construct({
                'plugins': {
                    'after_album': [{'plugin': 'zip', 'kwargs': {'level': None, 'zip_dir': './z'}}],
                }
            })
            opt_null_photo = JmOption.construct({
                'plugins': {
                    'after_photo': [{'plugin': 'zip', 'kwargs': {'level': None, 'zip_dir': './z'}}],
                }
            })
        self.assertEqual(1, len(opt_album.plugins['after_album']))
        self.assertNotIn('after_photo', opt_album.plugins)
        self.assertEqual(1, len(opt_photo.plugins['after_photo']))
        self.assertNotIn('after_album', opt_photo.plugins)
        self.assertEqual([{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}], opt_null_album.plugins.src_dict['after_album'])
        self.assertNotIn('after_photo', opt_null_album.plugins)
        self.assertEqual([{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}], opt_null_photo.plugins.src_dict['after_photo'])
        self.assertNotIn('after_album', opt_null_photo.plugins)
        migrate_calls = [c for c in mock_log.call_args_list if c.args and c.args[0] == 'option.migrate']
        self.assertEqual([], migrate_calls)

        # 2) after_album + level=photo -> 迁移到 after_photo
        with patch('jmcomic.jm_option.jm_log') as mock_log:
            opt_m1 = JmOption.construct({
                'plugins': {
                    'after_album': [{'plugin': 'zip', 'kwargs': {'level': 'photo', 'zip_dir': './z'}}],
                }
            })
        self.assertEqual([], opt_m1.plugins.src_dict['after_album'])
        self.assertEqual([{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}], opt_m1.plugins.src_dict['after_photo'])
        self.assertEqual(1, sum(1 for c in mock_log.call_args_list if c.args and c.args[0] == 'option.migrate'))

        # 3) after_photo + level=album -> 迁移到 after_album
        with patch('jmcomic.jm_option.jm_log') as mock_log:
            opt_m2 = JmOption.construct({
                'plugins': {
                    'after_photo': [{'plugin': 'zip', 'kwargs': {'level': 'album', 'zip_dir': './z'}}],
                }
            })
        self.assertEqual([], opt_m2.plugins.src_dict['after_photo'])
        self.assertEqual([{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}], opt_m2.plugins.src_dict['after_album'])
        self.assertEqual(1, sum(1 for c in mock_log.call_args_list if c.args and c.args[0] == 'option.migrate'))

        # 4) 冗余但方向一致的 level -> 留在原钩子、移除 level 并提示一次
        for group, lv in (('after_album', 'album'), ('after_photo', 'photo')):
            with patch('jmcomic.jm_option.jm_log') as mock_log:
                opt_same = JmOption.construct({
                    'plugins': {
                        group: [{'plugin': 'zip', 'kwargs': {'level': lv, 'zip_dir': './z'}}],
                    }
                })
            self.assertEqual([{'plugin': 'zip', 'kwargs': {'zip_dir': './z'}}], opt_same.plugins.src_dict[group])
            self.assertEqual(1, sum(1 for c in mock_log.call_args_list if c.args and c.args[0] == 'option.migrate'))

    def test_after_album_zip_without_level_merges_chapters_with_default_filename_rule(self):
        """
        用户不写 version、不写 level、也不写 filename_rule，直接将 zip 配在 after_album 时：
        1. after_photo 阶段不应触发按章打包；
        2. after_album 阶段应默认以 Atitle 命名，将多章图片合并进同一个压缩包，并清理所有章节原图。
        """
        import shutil
        import tempfile
        import zipfile
        from jmcomic import JmAlbumDetail, JmOption, JmPhotoDetail
        from jmcomic.jm_downloader import JmDownloader

        tmp = tempfile.mkdtemp(prefix='jm_test_zip_after_album_')
        try:
            img_base = os.path.join(tmp, 'images')
            zip_base = os.path.join(tmp, 'zips')
            opt = JmOption.construct({
                'dir_rule': {
                    'base_dir': img_base,
                    'rule': 'Bd / Aid / Ptitle',
                },
                'plugins': {
                    'after_album': [{
                        'plugin': 'zip',
                        'kwargs': {
                            'zip_dir': zip_base,
                            'delete_original_file': True,
                        },
                        'safe': False,
                    }],
                },
            })

            album = JmAlbumDetail(
                album_id='145504',
                scramble_id='0',
                name='整本合并测试本',
                episode_list=[('145504', '1', '第一章'), ('145505', '2', '第二章')],
                page_count=2,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )
            photo1 = JmPhotoDetail(
                photo_id='145504',
                scramble_id='0',
                name='第一章',
                series_id='145504',
                sort='1',
                page_arr=['00001.webp'],
                data_original_domain='example.com',
                from_album=album,
            )
            photo2 = JmPhotoDetail(
                photo_id='145505',
                scramble_id='0',
                name='第二章',
                series_id='145504',
                sort='2',
                page_arr=['00001.webp'],
                data_original_domain='example.com',
                from_album=album,
            )

            dir1 = opt.decide_image_save_dir(photo1)
            dir2 = opt.decide_image_save_dir(photo2)
            p1_img = os.path.join(dir1, '00001.webp')
            p2_img = os.path.join(dir2, '00001.webp')
            for p, content in ((p1_img, b'chap1'), (p2_img, b'chap2')):
                with open(p, 'wb') as f:
                    f.write(content)

            dler = JmDownloader(opt)
            dler.begin_manifest(album)
            image1, image2 = photo1[0], photo2[0]
            image1.save_path, image2.save_path = p1_img, p2_img
            dler.download_success_dict[album] = {
                photo1: [(p1_img, image1)],
                photo2: [(p2_img, image2)],
            }

            # after_photo 不应触发任何 zip
            dler.after_photo(photo1)
            dler.after_photo(photo2)
            self.assertFalse(os.path.exists(zip_base))
            self.assertTrue(os.path.exists(p1_img))
            self.assertTrue(os.path.exists(p2_img))

            # after_album 合并为一个整本压缩包（默认 [JM{Aid}]{Atitle}.zip）
            dler.after_album(album)
            merged_zip = os.path.join(zip_base, '[JM145504]整本合并测试本.zip')
            self.assertTrue(os.path.isfile(merged_zip))
            with zipfile.ZipFile(merged_zip, 'r') as zf:
                names = sorted(n.replace('\\', '/') for n in zf.namelist())
                self.assertEqual(['第一章/00001.webp', '第二章/00001.webp'], names)
            self.assertFalse(os.path.exists(dir1))
            self.assertFalse(os.path.exists(dir2))

            # after_photo 默认 [JM{Pid}]{Ptitle}.zip
            zip_photo_base = os.path.join(tmp, 'zips_photo')
            opt_photo = JmOption.construct({
                'dir_rule': {'base_dir': img_base, 'rule': 'Bd / Aid / Ptitle'},
                'plugins': {
                    'after_photo': [{
                        'plugin': 'zip',
                        'kwargs': {'zip_dir': zip_photo_base, 'delete_original_file': True},
                        'safe': False,
                    }],
                },
            })
            dir1_re = opt_photo.decide_image_save_dir(photo1)
            p1_img_re = os.path.join(dir1_re, '00001.webp')
            with open(p1_img_re, 'wb') as f:
                f.write(b'chap1-photo')
            dler_photo = JmDownloader(opt_photo)
            dler_photo.begin_manifest(photo1)
            image1.save_path = p1_img_re
            dler_photo.download_success_dict[album] = {photo1: [(p1_img_re, image1)]}
            dler_photo.after_photo(photo1)
            self.assertTrue(os.path.isfile(os.path.join(zip_photo_base, '[JM145504]第一章.zip')))
            self.assertFalse(os.path.exists(dir1_re))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_img2pdf_and_long_img_after_album_default_filename_rule(self):
        """
        验证 img2pdf 与 long_img 插件未显式指定 filename_rule 时：
        1. after_album 默认生成 [JM{Aid}]{Atitle}，after_photo 默认生成 [JM{Pid}]{Ptitle}（与 Feature / zip 统一）；
        2. 存在空标题章节（目录落到本子根目录）或未下载章节时，不会误建空目录，也不会把子目录当作图片文件读取。
        """
        import shutil
        import tempfile
        import types
        from PIL import Image
        from jmcomic import JmAlbumDetail, JmModuleConfig, JmOption, JmPhotoDetail
        from unittest.mock import patch

        tmp = tempfile.mkdtemp(prefix='jm_test_export_default_rule_')
        try:
            img_base = os.path.join(tmp, 'images')
            out_base = os.path.join(tmp, 'out')
            opt = JmOption.construct({
                'dir_rule': {
                    'base_dir': img_base,
                    'rule': 'Bd / Aid / Ptitle',
                },
            })
            album = JmAlbumDetail(
                album_id='438516',
                scramble_id='0',
                name='导出默认命名测试',
                episode_list=[('438516', '1', '单章'), ('438517', '2', ''), ('438518', '3', '未下载章')],
                page_count=1,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )
            photo = JmPhotoDetail(
                photo_id='438516',
                scramble_id='0',
                name='单章',
                series_id='0',
                sort='1',
                page_arr=['00001.png'],
                data_original_domain='example.com',
                from_album=album,
            )
            save_dir = opt.decide_image_save_dir(photo)
            img_file = os.path.join(save_dir, '00001.png')
            Image.new('RGB', (4, 4), color='white').save(img_file)

            long_cls = JmModuleConfig.REGISTRY_PLUGIN['long_img']
            long_cls(opt).invoke(album=album, photo=None, img_dir=out_base)
            self.assertTrue(os.path.isfile(os.path.join(out_base, '[JM438516]导出默认命名测试.png')))
            long_cls(opt).invoke(album=None, photo=photo, img_dir=out_base)
            self.assertTrue(os.path.isfile(os.path.join(out_base, '[JM438516]单章.png')))
            self.assertFalse(os.path.exists(os.path.join(img_base, '438516', '未下载章')))

            converted_inputs = []
            fake_img2pdf = types.SimpleNamespace(
                convert=lambda paths: (converted_inputs.extend(paths) or b'%PDF-1.4\n')
            )
            pdf_cls = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
            with patch.dict('sys.modules', {'img2pdf': fake_img2pdf}):
                pdf_cls(opt).invoke(album=album, photo=None, pdf_dir=out_base)
                pdf_cls(opt).invoke(album=None, photo=photo, pdf_dir=out_base)
            self.assertTrue(os.path.isfile(os.path.join(out_base, '[JM438516]导出默认命名测试.pdf')))
            self.assertTrue(os.path.isfile(os.path.join(out_base, '[JM438516]单章.pdf')))
            self.assertEqual(
                [os.path.normpath(img_file), os.path.normpath(img_file)],
                [os.path.normpath(p) for p in converted_inputs],
            )
            self.assertFalse(os.path.exists(os.path.join(img_base, '438516', '未下载章')))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_img2pdf_and_long_img_unified_collection_and_safe_deletion(self):
        """
        验证 img2pdf 与 long_img 统一的三步导出行为：
        1. 有 downloader 记录时优先按章节与图片 index 提取记录图，不扫无关文件；
        2. 无 downloader 回退扫目录时，遇到非图片文件（如 notes.txt）跳过不崩、不生成 0 字节坏文件；
        3. delete_original_file=True 时仅删除已成功合成的图片并尝试清理空目录，保留非图片文件及非空目录。
        """
        import shutil
        import tempfile
        import types
        from PIL import Image
        from jmcomic import JmAlbumDetail, JmImageDetail, JmModuleConfig, JmOption, JmPhotoDetail
        from jmcomic.jm_downloader import JmDownloader
        from unittest.mock import patch

        tmp = tempfile.mkdtemp(prefix='jm_test_export_unified_')
        try:
            img_base = os.path.join(tmp, 'images')
            out_base = os.path.join(tmp, 'out')
            opt = JmOption.construct({
                'dir_rule': {
                    'base_dir': img_base,
                    'rule': 'Bd / Aid / Ptitle',
                },
            })
            album = JmAlbumDetail(
                album_id='500001',
                scramble_id='0',
                name='统一导出行为测试',
                episode_list=[('500001', '1', '第一章'), ('500002', '2', '第二章')],
                page_count=3,
                pub_date='',
                update_date='',
                likes='',
                views='',
                comment_count=0,
                works=[],
                actors=[],
                tags=[],
                authors=[],
                description='',
            )
            photo1 = JmPhotoDetail(
                photo_id='500001', scramble_id='0', name='第一章', series_id='500001',
                sort='1', page_arr=['p2.png', 'p1.png'], data_original_domain='example.com', from_album=album,
            )
            photo2 = JmPhotoDetail(
                photo_id='500002', scramble_id='0', name='第二章', series_id='500001',
                sort='2', page_arr=['c2.png'], data_original_domain='example.com', from_album=album,
            )

            # A. downloader 记录模式：乱序插入 + 混合额外文件，按 index 排序且仅删记录图片
            dir1 = opt.decide_image_save_dir(photo1)
            dir2 = opt.decide_image_save_dir(photo2)
            img_p1 = os.path.join(dir1, 'b_page1.png')
            img_p2 = os.path.join(dir1, 'a_page2.png')
            img_c2 = os.path.join(dir2, 'c2.png')
            extra_note = os.path.join(dir1, 'notes.txt')
            Image.new('RGB', (8, 4), color='red').save(img_p1)
            Image.new('RGB', (4, 4), color='green').save(img_p2)
            Image.new('RGB', (6, 4), color='blue').save(img_c2)
            with open(extra_note, 'w', encoding='utf-8') as f:
                f.write('keep me')

            d1 = JmImageDetail.of('500001', '0', 'https://example.com/b_page1.png', from_photo=photo1, index=1)
            d2 = JmImageDetail.of('500001', '0', 'https://example.com/a_page2.png', from_photo=photo1, index=2)
            d3 = JmImageDetail.of('500002', '0', 'https://example.com/c2.png', from_photo=photo2, index=1)
            d1.save_path, d2.save_path, d3.save_path = img_p1, img_p2, img_c2
            dler = JmDownloader(opt)
            dler.begin_manifest(album)
            # 故意把第二章和第 2 页排在前面，检验按章节/页码 index 排序
            dler.download_success_dict[album] = {
                photo2: [(img_c2, d3)],
                photo1: [(img_p2, d2), (img_p1, d1)],
            }

            recorded_batch = []
            fake_img2pdf_ok = types.SimpleNamespace(
                convert=lambda paths: (recorded_batch.extend(paths) or b'%PDF-1.4\n')
            )
            pdf_cls = JmModuleConfig.REGISTRY_PLUGIN['img2pdf']
            with patch.dict('sys.modules', {'img2pdf': fake_img2pdf_ok}):
                pdf_cls(opt).invoke(album=album, photo=None, downloader=dler, pdf_dir=out_base, delete_original_file=True)

            self.assertEqual(
                [os.path.normpath(img_p1), os.path.normpath(img_p2), os.path.normpath(img_c2)],
                [os.path.normpath(p) for p in recorded_batch],
            )
            self.assertFalse(os.path.exists(img_p1))
            self.assertFalse(os.path.exists(img_p2))
            self.assertFalse(os.path.exists(img_c2))
            # dir1 因保留了 notes.txt 不应被删，dir2 为空应被清理
            self.assertTrue(os.path.isfile(extra_note))
            self.assertTrue(os.path.isdir(dir1))
            self.assertFalse(os.path.exists(dir2))

            # B. 无 downloader 回退目录扫描模式：目录含 notes.txt 且不同宽度触发 resize，测试 long_img 与 img2pdf 容错及安全删除
            for mode in ('long_img', 'img2pdf'):
                sub_dir1 = opt.decide_image_save_dir(photo1)
                sub_dir2 = opt.decide_image_save_dir(photo2)
                f1 = os.path.join(sub_dir1, '001.png')
                f2 = os.path.join(sub_dir2, '002.png')
                note = os.path.join(sub_dir1, 'readme.txt')
                Image.new('RGB', (10, 6), color='white').save(f1)
                Image.new('RGB', (5, 6), color='black').save(f2)
                with open(note, 'w', encoding='utf-8') as nf:
                    nf.write('non-image note')

                if mode == 'long_img':
                    long_cls = JmModuleConfig.REGISTRY_PLUGIN['long_img']
                    out_file = os.path.join(out_base, f'fallback_{mode}.png')
                    long_cls(opt).invoke(
                        album=album, photo=None, img_dir=out_base,
                        filename_rule=f'fallback_{mode}', delete_original_file=True,
                    )
                    self.assertTrue(os.path.isfile(out_file))
                else:
                    def strict_convert(paths):
                        for p in paths:
                            if not p.endswith('.png'):
                                raise ValueError(f'Cannot read non-image: {p}')
                        return b'%PDF-1.4\n'

                    fake_strict_pdf = types.SimpleNamespace(convert=strict_convert)
                    out_file = os.path.join(out_base, f'fallback_{mode}.pdf')
                    with patch.dict('sys.modules', {'img2pdf': fake_strict_pdf}):
                        pdf_cls(opt).invoke(
                            album=album, photo=None, pdf_dir=out_base,
                            filename_rule=f'fallback_{mode}', delete_original_file=True,
                        )
                    self.assertTrue(os.path.isfile(out_file))
                    self.assertGreater(os.path.getsize(out_file), 0)

                self.assertFalse(os.path.exists(f1))
                self.assertFalse(os.path.exists(f2))
                self.assertTrue(os.path.isfile(note))
                self.assertTrue(os.path.isdir(sub_dir1))
                self.assertFalse(os.path.exists(sub_dir2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
