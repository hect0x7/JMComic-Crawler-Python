import contextlib
import asyncio
import importlib.util
import logging
import os
import time
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jmcomic import (
    AsyncProgressDownloader,
    DownloadProgressPlugin,
    JmAlbumDetail,
    JmAsyncDownloader,
    JmDownloader,
    JmModuleConfig,
    ProgressDownloader,
    create_option_by_str,
    download_album,
    download_album_async,
    jm_logger,
    new_async_downloader,
)
from jmcomic.jm_config import setup_default_jm_logger
from jmcomic.jm_task_context import jm_task_context


PROJECT_DIR = Path(__file__).resolve().parents[2]
DOCUMENT_FILE = PROJECT_DIR / 'assets' / 'docs' / 'sources' / 'tutorial' / '15_download_progress.md'
PLUGIN_FILE = PROJECT_DIR / 'src' / 'jmcomic' / 'jm_plugin.py'
DOWNLOADER_FILE = PROJECT_DIR / 'src' / 'jmcomic' / 'jm_downloader.py'
RICH_INSTALLED = importlib.util.find_spec('rich') is not None


def create_album(episode_list=None):
    if episode_list is None:
        episode_list = [('101', '1', 'chapter-1'), ('102', '2', 'chapter-2')]
    return JmAlbumDetail(
        album_id='123456',
        scramble_id='220980',
        name='album',
        episode_list=episode_list,
        page_count=5,
        pub_date='',
        update_date='',
        likes='0',
        views='0',
        comment_count=0,
        works=[],
        actors=[],
        authors=['author'],
        tags=['tag'],
    )


class FakeClient:

    image_counts = {'101': 2, '102': 3}

    def __init__(self, album):
        self.album = album

    def get_album_detail(self, album_id):
        assert str(album_id) == self.album.id
        return self.album

    def check_photo(self, photo):
        photo.page_arr = [
            f'{index:05}.jpg'
            for index in range(1, self.image_counts[photo.id] + 1)
        ]
        photo.data_original_domain = 'cdn.example'
        photo.data_original_query_params = 'v=1'


class FakeAsyncClient(FakeClient):

    async def setup(self):
        pass

    async def close(self):
        pass

    async def get_album_detail(self, album_id):
        return super().get_album_detail(album_id)

    async def check_photo(self, photo):
        super().check_photo(photo)


class Test_DownloadProgress(unittest.TestCase):

    def test_progress_display_id_adds_prefix_only_once(self):
        self.assertEqual('JM123456', ProgressDownloader.display_id('123456'))
        self.assertEqual('JM123456', ProgressDownloader.display_id('JM123456'))

    def test_downloader_use_logs_before_and_after_class(self):
        class BeforeDownloader(JmDownloader):
            pass

        class AfterDownloader(JmDownloader):
            pass

        original_downloader = JmModuleConfig.CLASS_DOWNLOADER
        JmModuleConfig.CLASS_DOWNLOADER = BeforeDownloader
        try:
            with self.assertLogs('jmcomic', level='INFO') as captured:
                AfterDownloader.use()

            output = '\n'.join(captured.output)
            self.assertEqual('downloader.use', captured.records[0].topic)
            self.assertIn(
                f'{BeforeDownloader.__module__}.{BeforeDownloader.__qualname__}',
                output,
            )
            self.assertIn(
                f'{AfterDownloader.__module__}.{AfterDownloader.__qualname__}',
                output,
            )
            self.assertIs(AfterDownloader, JmModuleConfig.downloader_class())
        finally:
            JmModuleConfig.CLASS_DOWNLOADER = original_downloader

    def test_async_downloader_use_logs_and_changes_async_default(self):
        class BeforeAsyncDownloader(JmAsyncDownloader):
            pass

        class AfterAsyncDownloader(JmAsyncDownloader):
            pass

        original_downloader = JmModuleConfig.CLASS_ASYNC_DOWNLOADER
        JmModuleConfig.CLASS_ASYNC_DOWNLOADER = BeforeAsyncDownloader
        try:
            with self.assertLogs('jmcomic', level='INFO') as captured:
                AfterAsyncDownloader.use()

            output = '\n'.join(captured.output)
            self.assertEqual('async_downloader.use', captured.records[0].topic)
            self.assertIn(
                f'{BeforeAsyncDownloader.__module__}.{BeforeAsyncDownloader.__qualname__}',
                output,
            )
            self.assertIn(
                f'{AfterAsyncDownloader.__module__}.{AfterAsyncDownloader.__qualname__}',
                output,
            )
            self.assertIs(
                AfterAsyncDownloader,
                JmModuleConfig.async_downloader_class(),
            )

            with patch.object(AfterAsyncDownloader, '__init__', return_value=None):
                downloader = new_async_downloader(option=object())
            self.assertIsInstance(downloader, AfterAsyncDownloader)
        finally:
            JmModuleConfig.CLASS_ASYNC_DOWNLOADER = original_downloader

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_sync_progress_is_rendered_before_download_finishes(self):
        from rich.console import Console

        album = create_album()
        photo = album[0]
        FakeClient(album).check_photo(photo)
        image = photo[0]
        ui_output = StringIO()
        original_console = ProgressDownloader.progress_console
        ProgressDownloader.progress_console = Console(
            file=ui_output,
            force_terminal=True,
            force_interactive=True,
            color_system='standard',
            width=100,
        )
        downloader = None

        try:
            option = create_option_by_str('{}')
            with patch.object(
                ProgressDownloader,
                'create_client',
                return_value=FakeClient(album),
            ):
                downloader = ProgressDownloader(option)
            downloader.before_album(album)
            rendered_before_wait = ui_output.getvalue()
            time.sleep(0.2)
            self.assertEqual(rendered_before_wait, ui_output.getvalue())

            downloader.before_photo(photo)
            image.save_path = 'mock.jpg'
            downloader.after_image(image, image.save_path)

            rendered_during_download = ui_output.getvalue()
            self.assertIn('本子-JM123456', rendered_during_download)
            self.assertIn('章节-JM101', rendered_during_download)
            self.assertIn('1/2', rendered_during_download)
            self.assertNotIn('✓ 本子-JM123456', rendered_during_download)
        finally:
            if downloader is not None:
                downloader.stop_progress()
            ProgressDownloader.progress_console = original_console

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_default_progress_console_respects_non_interactive_output(self):
        original_console = ProgressDownloader.progress_console
        ProgressDownloader.progress_console = None
        try:
            with patch('sys.stdout', StringIO()):
                console = ProgressDownloader.get_progress_console()
            self.assertFalse(console.is_terminal)
            self.assertFalse(console.is_interactive)
        finally:
            ProgressDownloader.progress_console = original_console

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_non_interactive_notice_has_stable_text_layout(self):
        from rich.console import Console

        ui_output = StringIO()
        console = Console(
            file=ui_output,
            force_terminal=False,
            force_interactive=False,
            width=80,
        )
        log_path = Path('downloads') / DownloadProgressPlugin.log_file
        DownloadProgressPlugin.print_non_interactive_notice(
            console,
            log_path,
        )

        rendered = ui_output.getvalue()
        lines = rendered.splitlines()
        self.assertIn('JMComic Progress', lines[0])
        self.assertTrue(any('✓ 下载进度插件已启用' in line for line in lines))
        self.assertTrue(any('显示模式：完成后汇总' in line for line in lines))
        self.assertTrue(any(
            '动态进度：请在 Terminal / PowerShell 中运行' in line
            for line in lines
        ))
        self.assertTrue(any(line.strip(' │') == '详细日志' for line in lines))
        self.assertTrue(any(
            str(log_path) in line
            for line in lines
        ))

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_log_panel_keeps_latest_six_lines(self):
        from rich.console import Console

        ui_output = StringIO()
        console = Console(
            file=ui_output,
            force_terminal=False,
            force_interactive=False,
            width=100,
        )
        ProgressDownloader.reset_progress_logs()
        try:
            for index in range(8):
                ProgressDownloader.append_progress_log(f'log-{index}')
            console.print(ProgressDownloader.build_log_panel())
        finally:
            ProgressDownloader.reset_progress_logs()

        rendered = ui_output.getvalue()
        self.assertIn('JMComic Logs', rendered)
        self.assertNotIn('log-0', rendered)
        self.assertNotIn('log-1', rendered)
        for index in range(2, 8):
            self.assertIn(f'log-{index}', rendered)

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_plugin_accepts_custom_log_file_and_terminal_lines(self):
        from rich.console import Console

        original_console = ProgressDownloader.progress_console
        original_handlers = jm_logger.handlers[:]
        original_downloader = JmModuleConfig.CLASS_DOWNLOADER
        original_async_downloader = JmModuleConfig.CLASS_ASYNC_DOWNLOADER
        ProgressDownloader.progress_console = Console(
            file=StringIO(),
            force_terminal=False,
            force_interactive=False,
        )

        try:
            with TemporaryDirectory() as temp_dir:
                try:
                    log_file = Path(temp_dir) / 'logs' / 'progress.log'
                    create_option_by_str(f'''
plugins:
  after_init:
    - plugin: download_progress
      kwargs:
        log_file: {log_file.as_posix()}
        terminal_log_lines: 3
''')

                    self.assertTrue(log_file.exists())
                    self.assertEqual(3, ProgressDownloader.progress_log_lines.maxlen)
                finally:
                    for handler in jm_logger.handlers[:]:
                        jm_logger.removeHandler(handler)
                        if handler not in original_handlers:
                            handler.close()
        finally:
            jm_logger.handlers[:] = original_handlers
            ProgressDownloader.configure_progress_log_lines(6)
            ProgressDownloader.progress_console = original_console
            JmModuleConfig.CLASS_DOWNLOADER = original_downloader
            JmModuleConfig.CLASS_ASYNC_DOWNLOADER = original_async_downloader

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_non_interactive_progress_only_prints_final_summary(self):
        from rich.console import Console

        album = create_album([('101', '1', 'chapter-1')])
        photo = album[0]
        FakeClient(album).check_photo(photo)
        image = photo[0]
        ui_output = StringIO()
        original_console = ProgressDownloader.progress_console
        ProgressDownloader.progress_console = Console(
            file=ui_output,
            force_terminal=False,
            force_interactive=False,
            width=100,
        )
        downloader = None

        try:
            option = create_option_by_str('{}')
            with patch.object(
                ProgressDownloader,
                'create_client',
                return_value=FakeClient(album),
            ):
                downloader = ProgressDownloader(option)
            downloader.before_album(album)
            downloader.before_photo(photo)
            self.assertEqual('', ui_output.getvalue())

            image.save_path = 'mock.jpg'
            downloader.after_image(image, image.save_path)
            self.assertEqual('', ui_output.getvalue())

            second_image = photo[1]
            second_image.save_path = 'mock-2.jpg'
            downloader.after_image(second_image, second_image.save_path)
            downloader.after_photo(photo)
            self.assertEqual('', ui_output.getvalue())

            downloader.after_album(album)
            self.assertEqual(
                '✓ 下载完成：本子-JM123456，章节 1/1，图片 2/2\n',
                ui_output.getvalue(),
            )
        finally:
            if downloader is not None:
                downloader.stop_progress()
            ProgressDownloader.progress_console = original_console

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_plugin_does_not_close_external_log_handlers(self):
        original_handlers = jm_logger.handlers[:]
        external_handler = logging.Handler()
        jm_logger.handlers[:] = [external_handler]

        try:
            with TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    with patch.object(
                        external_handler,
                        'close',
                        wraps=external_handler.close,
                    ) as close_handler:
                        DownloadProgressPlugin(object()).redirect_log_to_file()
                        self.assertNotIn(external_handler, jm_logger.handlers)
                        close_handler.assert_not_called()
                finally:
                    for handler in jm_logger.handlers[:]:
                        jm_logger.removeHandler(handler)
                        handler.close()
                    os.chdir(previous_cwd)
        finally:
            jm_logger.handlers[:] = original_handlers
            external_handler.close()

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_plugin_uses_real_scheduler_without_stdout_or_image_io(self):
        from rich.console import Console

        album = create_album()
        ui_output = StringIO()
        stdout_output = StringIO()
        original_console = ProgressDownloader.progress_console
        original_downloader = JmModuleConfig.CLASS_DOWNLOADER
        original_async_downloader = JmModuleConfig.CLASS_ASYNC_DOWNLOADER
        ProgressDownloader.progress_console = Console(
            file=ui_output,
            force_terminal=True,
            force_interactive=True,
            color_system='standard',
            width=100,
        )

        def fake_create_client(_downloader):
            return FakeClient(album)

        def fake_download_image(downloader, image):
            image.save_path = str(Path.cwd() / image.filename)
            downloader.before_image(image, image.save_path)
            downloader.after_image(image, image.save_path)

        try:
            with TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    with patch.object(ProgressDownloader, 'create_client', fake_create_client), \
                         patch.object(ProgressDownloader, 'download_by_image_detail', fake_download_image), \
                         contextlib.redirect_stdout(stdout_output):
                        with jm_task_context(cli_no_progress=True):
                            option = create_option_by_str('''
plugins:
  after_init:
    - plugin: download_progress
''')
                        download_album('123456', option)

                    for handler in jm_logger.handlers:
                        handler.flush()

                    log_text = Path('jmcomic-download.log').read_text(encoding='utf-8')
                    self.assertIn('已将默认 Downloader 替换为 ProgressDownloader', log_text)
                    self.assertIn('album.before', log_text)
                    self.assertIn('image.after', log_text)
                    self.assertIn('album.after', log_text)
                    self.assertNotIn(' INFO:', log_text)
                    self.assertEqual(
                        1,
                        sum(
                            isinstance(handler, logging.FileHandler)
                            for handler in jm_logger.handlers
                        ),
                    )
                    self.assertEqual(2, len(jm_logger.handlers))
                finally:
                    for handler in jm_logger.handlers[:]:
                        jm_logger.removeHandler(handler)
                        handler.close()
                    os.chdir(previous_cwd)
        finally:
            ProgressDownloader.progress_console = original_console
            JmModuleConfig.CLASS_DOWNLOADER = original_downloader
            JmModuleConfig.CLASS_ASYNC_DOWNLOADER = original_async_downloader
            setup_default_jm_logger()

        rendered = ui_output.getvalue()
        self.assertEqual('', stdout_output.getvalue())
        self.assertIn('\x1b[', rendered)
        self.assertIn('彩色下载进度插件已启用', rendered)
        self.assertIn('检测到命令行参数 --no-progress', rendered)
        self.assertIn('当前 Option 已配置 download_progress', rendered)
        self.assertIn('JMComic Logs', rendered)
        self.assertIn('album.before', rendered)
        self.assertIn('章节-JM101', rendered)
        self.assertIn('章节-JM102', rendered)
        self.assertIn('✓ 本子-JM123456', rendered)

    @unittest.skipUnless(RICH_INSTALLED, '需要安装 rich 才能测试彩色进度插件')
    def test_plugin_supports_real_async_scheduler_without_network_or_image_io(self):
        from rich.console import Console

        album = create_album()
        ui_output = StringIO()
        stdout_output = StringIO()
        original_console = ProgressDownloader.progress_console
        original_downloader = JmModuleConfig.CLASS_DOWNLOADER
        original_async_downloader = JmModuleConfig.CLASS_ASYNC_DOWNLOADER
        ProgressDownloader.progress_console = Console(
            file=ui_output,
            force_terminal=False,
            force_interactive=False,
            width=100,
        )

        async def fake_download_image(downloader, image):
            image.save_path = str(Path.cwd() / image.filename)
            await downloader.before_image(image, image.save_path)
            await downloader.after_image(image, image.save_path)

        try:
            with TemporaryDirectory() as temp_dir:
                previous_cwd = os.getcwd()
                os.chdir(temp_dir)
                try:
                    with contextlib.redirect_stdout(stdout_output):
                        option = create_option_by_str('''
plugins:
  after_init:
    - plugin: download_progress
''')
                        with patch.object(
                            option,
                            'new_jm_async_client',
                            return_value=FakeAsyncClient(album),
                        ), patch.object(
                            AsyncProgressDownloader,
                            '_download_single_image',
                            fake_download_image,
                        ):
                            asyncio.run(download_album_async('123456', option))

                    for handler in jm_logger.handlers:
                        handler.flush()

                    log_text = Path('jmcomic-download.log').read_text(encoding='utf-8')
                    self.assertIn(
                        '已将默认 Async Downloader 替换为 AsyncProgressDownloader',
                        log_text,
                    )
                    self.assertIn('album.before', log_text)
                    self.assertIn('image.after', log_text)
                    self.assertIn('album.after', log_text)
                finally:
                    for handler in jm_logger.handlers[:]:
                        jm_logger.removeHandler(handler)
                        handler.close()
                    os.chdir(previous_cwd)
        finally:
            ProgressDownloader.progress_console = original_console
            JmModuleConfig.CLASS_DOWNLOADER = original_downloader
            JmModuleConfig.CLASS_ASYNC_DOWNLOADER = original_async_downloader
            setup_default_jm_logger()

        rendered = ui_output.getvalue()
        self.assertEqual('', stdout_output.getvalue())
        self.assertIn('显示模式：完成后汇总', rendered)
        self.assertIn('动态进度：请在 Terminal / PowerShell 中运行', rendered)
        self.assertIn('详细日志', rendered)
        self.assertIn('✓ 下载完成：本子-JM123456，章节 2/2，图片 5/5', rendered)

    def test_plugin_is_registered_and_documentation_only_shows_usage(self):
        document = DOCUMENT_FILE.read_text(encoding='utf-8')
        self.assertIs(
            DownloadProgressPlugin,
            JmModuleConfig.REGISTRY_PLUGIN['download_progress'],
        )
        self.assertIn('plugin: download_progress', document)
        self.assertIn('download_album_async', document)
        self.assertNotIn('class ProgressDownloader', document)
        self.assertNotIn('class DownloadProgressPlugin', document)
        self.assertIn('class ProgressDownloader', PLUGIN_FILE.read_text(encoding='utf-8'))
        self.assertNotIn('class ProgressDownloader', DOWNLOADER_FILE.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
