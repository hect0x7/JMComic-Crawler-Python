from test_jmcomic import *
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jmcomic.cli import JmcomicUI, JmViewUI
from jmcomic.jm_task_context import get_jm_task_context


class Test_Cli(JmTestConfigurable):
    """测试 CLI 命令 (jmcomic + jmv)"""

    album_id = '350234'

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
            self.assertTrue(get_jm_task_context().get('cli_no_progress'))
            return option

        with patch.object(ui, 'parse_arg', side_effect=parse_arg), \
                patch('jmcomic.api.JmOption.default', side_effect=create_default_option), \
                patch.object(ui, 'enable_download_progress'), \
                patch.object(ui, 'run'), \
                patch('jmcomic.api.jm_log'):
            ui.main()

        self.assertNotIn('cli_no_progress', get_jm_task_context())

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

    def test_jmcomic_download_album(self):
        """jmcomic 真实下载 album 350234"""
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
        """jmv 真实请求 album 350234 的详情"""
        album = self.client.get_album_detail(self.album_id)

        self.assertEqual(album.album_id, self.album_id)
        self.assertTrue(len(album.name) > 0, '标题不应为空')
        self.assertTrue(len(album.episode_list) > 0, '章节列表不应为空')

    def test_jmv_print_album_detail_real(self):
        """jmv 真实请求并打印 album 350234 的详情，校验输出内容"""
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
        """jmv 真实请求 album 350234，验证超长列表被截断"""
        album = self.client.get_album_detail(self.album_id)
        ui = JmViewUI()

        with patch('sys.stdout', new_callable=StringIO) as mock_out:
            ui.print_album_detail(album)
            output = mock_out.getvalue()

        # 350234 的作者/标签数量非常多，应触发截断
        if len(album.authors) > 10:
            self.assertIn(f'...等{len(album.authors)}个', output)
        if len(album.tags) > 10:
            self.assertIn(f'...等{len(album.tags)}个', output)
