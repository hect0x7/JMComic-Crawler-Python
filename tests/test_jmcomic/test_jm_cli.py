from concurrent.futures import ThreadPoolExecutor

from test_jmcomic import *
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jmcomic.cli import JmcomicUI, JmViewUI
from jmcomic import JmSyncRuntime, JTC, jm_task_context


class Test_Cli(JmTestConfigurable):
    """测试 CLI 命令 (jmcomic + jmv)"""

    album_id = '123'

    def test_dry_run_skips_option_and_real_downloads(self):
        ui = JmcomicUI()
        with patch('sys.argv', ['jmcomic', '100001', 'p200001', '--dry-run', '--option', 'unused.yml']), \
                patch('jmcomic.cli.importlib.util.find_spec', return_value=object()), \
                patch('jmcomic.api.create_option', side_effect=AssertionError('不能读取配置')), \
                patch('jmcomic.api.JmOption.default', side_effect=AssertionError('不能创建 Option')), \
                patch.object(ui, 'run', side_effect=AssertionError('不能执行真实下载')), \
                patch('jmcomic.jm_plugin.DownloadProgressPlugin.preview') as preview:
            ui.main()
        preview.assert_called_once_with(['100001'], ['200001'])

    def test_dry_run_rejects_no_progress(self):
        with patch('sys.argv', ['jmcomic', '--dry-run', '--no-progress']), \
                patch('sys.stderr', StringIO()):
            with self.assertRaises(SystemExit) as caught:
                JmcomicUI().parse_arg()
        self.assertEqual(2, caught.exception.code)

    # ========== jmcomic 命令测试 ==========

    def test_jmcomic_progress_enabled_by_default(self):
        ui = JmcomicUI()
        with patch('sys.argv', ['jmcomic', self.album_id]):
            ui.parse_arg()

        self.assertTrue(ui.progress_enabled)

    def test_jmcomic_no_progress_arg(self):
        ui = JmcomicUI()
        with patch('sys.argv', ['jmcomic', self.album_id, '--no-progress']):
            ui.parse_arg()

        self.assertFalse(ui.progress_enabled)

    def test_jmcomic_enable_download_progress(self):
        ui = JmcomicUI()
        option = SimpleNamespace(plugins={})
        plugin = MagicMock()

        with patch('jmcomic.cli.importlib.util.find_spec', return_value=object()), \
                patch('jmcomic.jm_plugin.DownloadProgressPlugin.build', return_value=plugin) as build:
            ui.enable_download_progress(option)

        build.assert_called_once_with(option)
        plugin.invoke.assert_called_once_with()

    def test_jmcomic_does_not_enable_progress_twice(self):
        ui = JmcomicUI()
        option = SimpleNamespace(plugins={
            'after_init': [{'plugin': 'download_progress'}]
        })

        with patch('jmcomic.jm_plugin.DownloadProgressPlugin.build') as build:
            ui.enable_download_progress(option)

        build.assert_not_called()

    def test_jmcomic_no_progress_context_wraps_option_creation(self):
        ui = JmcomicUI()
        option = SimpleNamespace(plugins={})

        def parse_arg():
            ui.progress_enabled = False
            ui.option_path = None

        def create_default_option():
            self.assertTrue(JTC.get_context().get('cli_no_progress'))
            return option

        with patch.object(ui, 'parse_arg', side_effect=parse_arg), \
                patch('jmcomic.api.JmOption.default', side_effect=create_default_option), \
                patch.object(ui, 'enable_download_progress'), \
                patch.object(ui, 'run'), \
                patch('jmcomic.api.jm_log'):
            ui.main()

        self.assertNotIn('cli_no_progress', JTC.get_context())

    def test_jmcomic_falls_back_without_rich(self):
        ui = JmcomicUI()
        option = SimpleNamespace(plugins={})

        with patch('jmcomic.cli.importlib.util.find_spec', return_value=None), \
                patch('jmcomic.jm_config.jm_log') as jm_log:
            ui.enable_download_progress(option)

        jm_log.assert_called_once_with(
            'command_line.progress',
            '未安装 rich，继续使用普通日志。如需显示下载进度，请执行：pip install rich'
        )

    def test_jmcomic_parse_album_id(self):
        """jmcomic 解析 album id"""
        ui = JmcomicUI()
        ui.raw_id_list = [self.album_id]
        ui.parse_raw_id()
        self.assertEqual(ui.album_id_list, [self.album_id])

    def test_jmcomic_parse_photo_id(self):
        """jmcomic 解析 photo id (p前缀)"""
        ui = JmcomicUI()
        ui.raw_id_list = [f'p{self.album_id}']
        ui.parse_raw_id()
        self.assertEqual(ui.photo_id_list, [self.album_id])

    def test_jmcomic_parse_mixed(self):
        """jmcomic 同时解析 album 和 photo"""
        ui = JmcomicUI()
        ui.raw_id_list = [self.album_id, f'p{self.album_id}']
        ui.parse_raw_id()
        self.assertEqual(ui.album_id_list, [self.album_id])
        self.assertEqual(ui.photo_id_list, [self.album_id])

    def test_jmcomic_mixed_threads_inherit_runtime(self):
        ui = JmcomicUI()
        ui.album_id_list = ['1']
        ui.photo_id_list = ['2']
        option = SimpleNamespace()
        observed = []

        def record(ids, actual_option):
            observed.append((
                ids,
                actual_option,
                JTC.get_runtime(),
                JTC.get_context(),
            ))

        with ThreadPoolExecutor(max_workers=1) as executor:
            runtime = JmSyncRuntime(album_executor=executor)
            with patch('jmcomic.api.download_album', side_effect=record), \
                    patch('jmcomic.api.download_photo', side_effect=record):
                with jm_task_context(task_id='cli-job', runtime=runtime):
                    ui.run(option)

        self.assertCountEqual(
            [(ids, actual_option) for ids, actual_option, _executor, _context in observed],
            [(['1'], option), (['2'], option)],
        )
        self.assertEqual(
            [seen for _ids, _option, seen, _context in observed],
            [runtime, runtime],
        )
        self.assertEqual(
            [context for _ids, _option, _executor, context in observed],
            [
                {'task_id': 'cli-job', 'runtime': runtime},
                {'task_id': 'cli-job', 'runtime': runtime},
            ],
        )

    def test_jmcomic_exits_nonzero_on_batch_failures(self):
        from jmcomic.jm_downloader import BatchResult

        failed_batch = BatchResult()
        failed_batch.failed['999999'] = RuntimeError('missing')
        ok_batch = BatchResult()

        # 1) 仅 album 失败 -> exit(1)
        ui_album = JmcomicUI()
        ui_album.album_id_list = ['999999']
        with patch('jmcomic.api.download_album', return_value=failed_batch):
            with self.assertRaises(SystemExit) as ctx:
                ui_album.run(SimpleNamespace())
        self.assertEqual(1, ctx.exception.code)

        # 2) 仅 photo 失败 -> exit(1)
        ui_photo = JmcomicUI()
        ui_photo.photo_id_list = ['888888']
        with patch('jmcomic.api.download_photo', return_value=failed_batch):
            with self.assertRaises(SystemExit) as ctx:
                ui_photo.run(SimpleNamespace())
        self.assertEqual(1, ctx.exception.code)

        # 3) 混合模式其中一个批次有失败 -> exit(1)
        ui_mixed = JmcomicUI()
        ui_mixed.album_id_list = ['1']
        ui_mixed.photo_id_list = ['2']
        with patch('jmcomic.api.download_album', return_value=ok_batch), \
                patch('jmcomic.api.download_photo', return_value=failed_batch):
            with self.assertRaises(SystemExit) as ctx:
                ui_mixed.run(SimpleNamespace())
        self.assertEqual(1, ctx.exception.code)

        # 4) 全部成功 -> 不抛 SystemExit
        ui_ok = JmcomicUI()
        ui_ok.album_id_list = ['1']
        with patch('jmcomic.api.download_album', return_value=ok_batch):
            ui_ok.run(SimpleNamespace())

    def test_jmcomic_mixed_mode_propagates_unhandled_thread_exception(self):
        ui = JmcomicUI()
        ui.album_id_list = ['1']
        ui.photo_id_list = ['2']

        with patch('jmcomic.api.download_album', side_effect=ValueError('auth boom')), \
                patch('jmcomic.api.download_photo', return_value=None):
            with self.assertRaises(ValueError) as ctx:
                ui.run(SimpleNamespace())
        self.assertIn('auth boom', str(ctx.exception))

    def test_jmcomic_download_album(self):
        """jmcomic 真实下载 album 123"""
        JustDownloadSpecificCountImage.count = 5
        album, _dler = download_album(self.album_id, self.option, downloader=JustDownloadSpecificCountImage)
        self.assertEqual(album.album_id, self.album_id)
        self.assertTrue(len(album.name) > 0, '标题不应为空')

    # ========== jmv 命令测试 ==========

    def test_entry_points_installed(self):
        """验证控制台命令行是否被正确安装到了所在系统的环境变量里"""
        import shutil
        import subprocess
        for cmd in ['jmcomic', 'jmv']:
            self.assertIsNotNone(
                shutil.which(cmd),
                f"Command '{cmd}' not found in PATH. Please verify entry_points in setup.py or [project.scripts] in pyproject.toml and ensure the package is installed."
            )

            try:
                subprocess.run(
                    [cmd, "--help"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                self.fail(f"Command '{cmd} --help' timed out execution.")
            except subprocess.CalledProcessError as e:
                self.fail(f"Command '{cmd} --help' failed with exit code {e.returncode}. Stderr: {e.stderr.strip()}")
            except OSError as e:
                self.fail(f"Failed to execute command '{cmd}': {e}")

    def test_python_m_jmcomic_entry(self):
        """验证 `python -m jmcomic --help` 可直接调用包主入口"""
        import subprocess
        import sys
        res = subprocess.run(
            [sys.executable, '-m', 'jmcomic', '--help'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, res.returncode, msg=res.stderr)
        self.assertIn('python -m jmcomic', res.stdout)

    # -- extract_album_id --

    def test_jmv_extract_pure_digits(self):
        """jmv 纯数字文本"""
        ui = JmViewUI()
        ui.raw_text = '350234'
        self.assertEqual(ui.extract_album_id(), '350234')

    def test_jmv_extract_digits_scattered(self):
        """jmv 数字散布在文本中，应拼接所有数字"""
        ui = JmViewUI()
        ui.raw_text = '350谁还没看过234'
        self.assertEqual(ui.extract_album_id(), '350234')

    def test_jmv_extract_jm_prefix(self):
        """jmv JM前缀的车号"""
        ui = JmViewUI()
        ui.raw_text = 'JM350234'
        self.assertEqual(ui.extract_album_id(), '350234')

    def test_jmv_extract_jm_url(self):
        """jmv 支持从禁漫链接中提取车号，不混入域名中的 18"""
        ui = JmViewUI()
        self.assertEqual(ui.extract_album_id('https://18comic.vip/album/350234/'), '350234')
        self.assertEqual(ui.extract_album_id('https://18comic.vip/photo/350234'), '350234')
        self.assertEqual(ui.extract_album_id('https://18comic.vip/album/?id=350234'), '350234')
        self.assertEqual(ui.extract_album_id('JM 350 234'), '350234')

    def test_jmv_extract_no_digits_exits(self):
        """jmv 没有数字时应 exit(1)"""
        ui = JmViewUI()
        ui.raw_text = 'abcdef'
        with self.assertRaises(SystemExit) as ctx:
            ui.extract_album_id()
        self.assertEqual(ctx.exception.code, 1)

    # -- _truncate_list --

    def test_jmv_truncate_list_under_limit(self):
        """不超过限制时完整显示"""
        items = ['a', 'b', 'c']
        result = JmViewUI._truncate_list(items, limit=10)
        self.assertEqual(result, 'a, b, c')

    def test_jmv_truncate_list_at_limit(self):
        """刚好等于限制时完整显示"""
        items = [str(i) for i in range(10)]
        result = JmViewUI._truncate_list(items, limit=10)
        self.assertNotIn('...', result)

    def test_jmv_truncate_list_over_limit(self):
        """超过限制时截断并显示总数"""
        items = [str(i) for i in range(20)]
        result = JmViewUI._truncate_list(items, limit=10)
        self.assertIn('...等20个', result)

    # -- 真实网络请求 --

    def test_jmv_get_album_detail_real(self):
        """jmv 真实请求 album 123 的详情"""
        album = self.client.get_album_detail(self.album_id)

        self.assertEqual(album.album_id, self.album_id)
        self.assertTrue(len(album.name) > 0, '标题不应为空')
        self.assertTrue(len(album.episode_list) > 0, '章节列表不应为空')

    def test_jmv_print_album_detail_real(self):
        """jmv 真实请求并打印 album 123 的详情，校验输出内容"""
        album = self.client.get_album_detail(self.album_id)
        ui = JmViewUI()

        with patch('sys.stdout', new_callable=StringIO) as mock_out:
            ui.print_album_detail(album)
            output = mock_out.getvalue()

        # 校验基本信息
        self.assertIn(f'JM{self.album_id}', output)
        self.assertIn(album.name, output)
        self.assertIn(JmcomicText.format_album_url(album.album_id), output)

        # 校验章节
        self.assertIn(f'章节 ({len(album.episode_list)})', output)

    def test_jmv_print_truncates_real(self):
        """jmv 真实请求 album 123，验证超长列表被截断"""
        album = self.client.get_album_detail(self.album_id)
        ui = JmViewUI()

        with patch('sys.stdout', new_callable=StringIO) as mock_out:
            ui.print_album_detail(album)
            output = mock_out.getvalue()

        # 作者/标签数量如果非常多，应触发截断
        if len(album.authors) > 10:
            self.assertIn(f'...等{len(album.authors)}个', output)
        if len(album.tags) > 10:
            self.assertIn(f'...等{len(album.tags)}个', output)

    def test_jmv_multi_ids_and_json_output(self):
        import json

        fake_album_1 = SimpleNamespace(
            album_id='100',
            name='Album One',
            authors=[f'author_{i}' for i in range(12)],
            pub_date='2026-01-01',
            update_date='2026-01-02',
            page_count=24,
            views='10K',
            likes='1K',
            comment_count=5,
            tags=['全彩', '中文'],
            actors=['角色A'],
            works=['作品A'],
            description='简介1',
            episode_list=[('1001', '1', ' 第1話 ')],
        )
        fake_album_2 = SimpleNamespace(
            album_id='200',
            name='Album Two',
            authors=['author_b'],
            pub_date='2026-02-01',
            update_date='2026-02-02',
            page_count=18,
            views='20K',
            likes='2K',
            comment_count=8,
            tags=['单行本'],
            actors=[],
            works=[],
            description='',
            episode_list=[('2001', '1', '单章')],
        )
        album_map = {'100': fake_album_1, '200': fake_album_2}

        class FakeClient:
            def get_album_detail(self, aid):
                if aid not in album_map:
                    raise RuntimeError(f'missing {aid}')
                return album_map[aid]

        fake_option = SimpleNamespace(new_jm_client=lambda: FakeClient())
        prev_flag = JmModuleConfig.FLAG_ENABLE_JM_LOG

        # 1) 单车号 --json：输出纯 JSON 对象，不截断作者列表，自动跳过 pause，恢复日志开关
        ui_single = JmViewUI()
        with patch('sys.argv', ['jmv', 'JM100', '--json']),                 patch('atexit.register'),                 patch('jmcomic.api.JmOption.default', return_value=fake_option),                 patch('sys.stdout', new_callable=StringIO) as out_single:
            ui_single.main()

        self.assertTrue(ui_single.auto_exit)
        self.assertEqual(prev_flag, JmModuleConfig.FLAG_ENABLE_JM_LOG)
        data_single = json.loads(out_single.getvalue())
        self.assertIsInstance(data_single, dict)
        self.assertEqual('100', data_single['album_id'])
        self.assertEqual(12, len(data_single['authors']))
        self.assertEqual([{'photo_id': '1001', 'index': 1, 'title': '第1話'}], data_single['episodes'])

        # 2) 多车号 --json：输出纯 JSON 数组
        ui_multi = JmViewUI()
        with patch('sys.argv', ['jmv', '100', 'abc200', '--json']),                 patch('atexit.register'),                 patch('jmcomic.api.JmOption.default', return_value=fake_option),                 patch('sys.stdout', new_callable=StringIO) as out_multi:
            ui_multi.main()

        data_multi = json.loads(out_multi.getvalue())
        self.assertIsInstance(data_multi, list)
        self.assertEqual(['100', '200'], [item['album_id'] for item in data_multi])

        # 3) 多车号部分失败：成功的照常输出，失败写 stderr 并以退出码 1 结束
        ui_partial = JmViewUI()
        with patch('sys.argv', ['jmv', '999', '100', '--json']),                 patch('atexit.register'),                 patch('jmcomic.api.JmOption.default', return_value=fake_option),                 patch('sys.stdout', new_callable=StringIO) as out_partial,                 patch('sys.stderr', new_callable=StringIO) as err_partial:
            with self.assertRaises(SystemExit) as ctx:
                ui_partial.main()

        self.assertEqual(1, ctx.exception.code)
        self.assertIn('missing 999', err_partial.getvalue())
        partial_list = json.loads(out_partial.getvalue())
        self.assertEqual([{'album_id': '100'}], [{'album_id': x['album_id']} for x in partial_list])
