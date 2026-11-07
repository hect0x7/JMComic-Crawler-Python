"""
command-line usage

1. jmcomic - download album/photo:

  $ jmcomic 123 456 p333 --option="D:/option.yml"

2. jmv - view album detail (extract digits from text as album id, supports multiple ids & --json):

  $ jmv 350234
  $ jmv 350234 JM438516 -y
  $ jmv 438516 --json
  $ jmv 350谁还没看过234
  $ jmv abc123141 --option="D:/option.yml"

"""
import importlib.util
import os.path
from typing import List, Optional


def get_env(name, default):
    import os
    value = os.getenv(name, None)
    if value is None or value == '':
        return default

    return value


class JmcomicUI:

    def __init__(self) -> None:
        self.option_path: Optional[str] = None
        self.progress_enabled = True
        self.dry_run = False
        self.raw_id_list: List[str] = []
        self.album_id_list: List[str] = []
        self.photo_id_list: List[str] = []

    def parse_arg(self):
        import argparse
        parser = argparse.ArgumentParser(prog='python -m jmcomic', description='JMComic Command Line Downloader')
        parser.add_argument(
            'id_list',
            nargs='*',
            help='input all album/photo ids that you want to download, separating them by spaces. '
                 'Need add a "p" prefix to indicate a photo id, such as `123 456 p333`.',
            default=[],
        )

        parser.add_argument(
            '--option',
            help='path to the option file, you can also specify it by env `JM_OPTION_PATH`',
            type=str,
            default=get_env('JM_OPTION_PATH', ''),
        )
        parser.add_argument(
            '--no-progress',
            action='store_false',
            dest='progress_enabled',
            help='do not automatically enable the download progress plugin',
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='preview mock downloads without network requests or file writes; ignores --option',
        )

        args = parser.parse_args()
        if args.dry_run and not args.progress_enabled:
            parser.error('--dry-run 用于预览进度条，不能与 --no-progress 同时使用')
        self.dry_run = args.dry_run
        self.progress_enabled = args.progress_enabled
        option = args.option
        if len(option) == 0 or option == "''":
            self.option_path = None
        else:
            self.option_path = os.path.abspath(option)

        self.raw_id_list = args.id_list
        self.parse_raw_id()

    def parse_raw_id(self):

        def parse(text):
            from .jm_toolkit import JmcomicText

            try:
                return JmcomicText.parse_to_jm_id(text)
            except Exception as e:
                print(e.args[0])
                exit(1)

        for raw_id in self.raw_id_list:
            if raw_id.startswith('p'):
                self.photo_id_list.append(parse(raw_id[1:]))
            elif raw_id.startswith('a'):
                self.album_id_list.append(parse(raw_id[1:]))
            else:
                self.album_id_list.append(parse(raw_id))

    def main(self):
        self.parse_arg()
        if self.dry_run:
            if importlib.util.find_spec('rich') is None:
                raise SystemExit('预览进度条需要 rich，请先执行：pip install rich')
            from .jm_plugin import DownloadProgressPlugin
            DownloadProgressPlugin.preview(self.album_id_list, self.photo_id_list)
            return

        from .api import create_option, JmOption
        from .jm_task_context import jm_task_context
        with jm_task_context(cli_no_progress=not self.progress_enabled):
            if self.option_path is not None:
                option = create_option(self.option_path)
            else:
                option = JmOption.default()

        self.enable_download_progress(option)

        from .api import jm_log
        jm_log('command_line',
               f'start downloading...\n'
               f'- using option: [{self.option_path or "default"}]\n'
               f'to be downloaded: \n'
               f'- album: {self.album_id_list}\n'
               f'- photo: {self.photo_id_list}')

        self.run(option)

    def enable_download_progress(self, option):
        option_enabled = self.option_has_download_progress(option)
        if not self.progress_enabled:
            return

        if option_enabled:
            return

        if importlib.util.find_spec('rich') is None:
            from .jm_config import jm_log
            jm_log('command_line.progress',
                   '未安装 rich，继续使用普通日志。如需显示下载进度，请执行：pip install rich')
            return

        from .jm_plugin import DownloadProgressPlugin
        DownloadProgressPlugin.build(option).invoke()

    @staticmethod
    def option_has_download_progress(option):
        plugin_list = option.plugins.get('after_init', []) or []
        return any(plugin.get('plugin') == 'download_progress' for plugin in plugin_list)

    def run(self, option):
        import sys
        from .api import download_album, download_photo
        from .jm_task_context import bind_jm_task_context

        results = []
        if len(self.album_id_list) == 0:
            results.append(download_photo(self.photo_id_list, option))
        elif len(self.photo_id_list) == 0:
            results.append(download_album(self.album_id_list, option))
        else:
            # 同时下载album和photo
            from threading import Thread
            errors = []

            def run_task(fn, id_list):
                try:
                    results.append(fn(id_list, option))
                except BaseException as e:
                    errors.append(e)

            tasks = [
                Thread(target=bind_jm_task_context(run_task), args=(download_album, self.album_id_list)),
                Thread(target=bind_jm_task_context(run_task), args=(download_photo, self.photo_id_list)),
            ]
            for t in tasks:
                t.start()
            for t in tasks:
                t.join()

            if errors:
                raise errors[0]

        if any(res is not None and not res.all_succeeded for res in results):
            sys.exit(1)


def main():
    JmcomicUI().main()


class JmViewUI:

    def __init__(self) -> None:
        self.raw_text: str = ''
        self.raw_text_list: List[str] = []
        self.option_path: Optional[str] = None
        self.auto_exit: bool = False
        self.json_output: bool = False

    def parse_arg(self):
        import argparse
        parser = argparse.ArgumentParser(
            prog='jmv',
            description='JMComic Album Viewer - 从文本中提取数字作为album ID，查看本子详情（支持多车号与 --json 输出）',
        )
        parser.add_argument(
            'texts',
            metavar='text',
            nargs='+',
            help='一个或多个包含数字的禁漫车号，例如 "350234"、"JM438516" 或 "350谁还没看过234"',
        )
        parser.add_argument(
            '--option',
            help='option 文件路径，也可通过环境变量 JM_OPTION_PATH 指定',
            type=str,
            default=get_env('JM_OPTION_PATH', ''),
        )
        parser.add_argument(
            '--json',
            action='store_true',
            dest='json_output',
            help='以纯 JSON 格式输出本子详情（单车号输出对象，多车号输出数组，自动跳过回车确认）',
        )
        parser.add_argument(
            '-y', '--yes',
            action='store_true',
            help='执行完毕后直接退出，无需按回车确认',
        )

        args = parser.parse_args()
        self.raw_text_list = list(args.texts)
        self.raw_text = self.raw_text_list[0] if self.raw_text_list else ''
        self.json_output = args.json_output
        self.auto_exit = args.yes or args.json_output

        option_str = args.option
        if len(option_str) == 0 or option_str == "''":
            self.option_path = None
        else:
            self.option_path = os.path.abspath(option_str)

    def extract_album_id(self, text: Optional[str] = None) -> str:
        import re
        import sys
        target = self.raw_text if text is None else text
        numbers = re.findall(r'\d+', target)
        if not numbers:
            msg = f'❌❌❌ 解析失败: 无法从 "{target}" 中提取到任何数字 ❌❌❌'
            if self.json_output:
                print(msg, file=sys.stderr)
            else:
                from .api import jm_log
                jm_log('jmv', msg)
            sys.exit(1)
        return ''.join(numbers)

    def extract_album_ids(self) -> List[str]:
        texts = self.raw_text_list if self.raw_text_list else ([self.raw_text] if self.raw_text else [])
        return [self.extract_album_id(t) for t in texts]

    @staticmethod
    def album_to_dict(album) -> dict:
        from .jm_toolkit import JmcomicText
        return {
            'album_id': album.album_id,
            'name': album.name,
            'url': JmcomicText.format_album_url(album.album_id),
            'cover_url': JmcomicText.get_album_cover_url(album.album_id),
            'authors': list(album.authors or []),
            'pub_date': album.pub_date,
            'update_date': album.update_date,
            'page_count': album.page_count,
            'views': album.views,
            'likes': album.likes,
            'comment_count': album.comment_count,
            'tags': list(album.tags or []),
            'actors': list(album.actors or []),
            'works': list(album.works or []),
            'description': album.description,
            'episodes': [
                {
                    'photo_id': str(pid),
                    'index': int(pindex) if str(pindex).isdigit() else pindex,
                    'title': pname.strip(),
                }
                for pid, pindex, pname in (album.episode_list or [])
            ],
        }

    @staticmethod
    def _truncate_list(items, limit=10):
        if len(items) <= limit:
            return ', '.join(items)
        return ', '.join(items[:limit]) + f' ...等{len(items)}个'

    def print_album_detail(self, album):
        from jmcomic import JmcomicText

        sep = '─' * 50

        print(f'\n{sep}')
        print(f'  📖 标题:  {album.name}')
        print(f'  🆔 ID:    JM{album.album_id}')
        print(f'  🔗 链接:  {JmcomicText.format_album_url(album.album_id)}')
        print(f'  🎨 封面:  {JmcomicText.get_album_cover_url(album.album_id)}')
        print(f'  ✍️ 作者:  {self._truncate_list(album.authors) if album.authors else "未知"}')
        print(sep)

        print(f'  📅 发布日期:  {album.pub_date}')
        print(f'  📅 更新日期:  {album.update_date}')
        print(f'  📄 总页数:    {album.page_count}')
        print(f'  👀 观看:      {album.views}')
        print(f'  ❤️ 点赞:     {album.likes}')
        print(f'  💬 评论:      {album.comment_count}')
        print(sep)

        if album.tags:
            print(f'  🏷️ 标签:  {self._truncate_list(album.tags)}')
        if album.actors:
            print(f'  🎭 人物:  {self._truncate_list(album.actors)}')
        if album.works:
            print(f'  📚 作品:  {self._truncate_list(album.works)}')

        if album.description:
            print(f'  📝 简介:  {album.description}')

        print(sep)
        episode_count = len(album.episode_list)
        print(f'  📑 章节 ({episode_count}):')
        for pid, pindex, pname in album.episode_list:
            pname = pname.strip()
            print(f'     第{pindex}話  {pname}  (id: {pid})')

        print(f'{sep}\n')

    def _pause(self):
        if not self.auto_exit:
            input('\n[运行结束] 请按回车键关闭窗口... (下次运行可附加 -y 参数跳过确认)')

    def main(self):
        import io
        import json
        import sys
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        self.parse_arg()

        import atexit
        atexit.register(self._pause)

        album_ids = self.extract_album_ids()

        from .api import create_option, JmModuleConfig, JmOption, jm_log
        prev_log_flag = JmModuleConfig.FLAG_ENABLE_JM_LOG
        if self.json_output:
            JmModuleConfig.FLAG_ENABLE_JM_LOG = False

        has_error = False
        json_items = []
        try:
            if self.option_path is not None:
                option = create_option(self.option_path)
                if self.json_output:
                    JmModuleConfig.FLAG_ENABLE_JM_LOG = False
            else:
                option = JmOption.default()

            client = option.new_jm_client()
            for album_id in album_ids:
                if not self.json_output:
                    jm_log('jmv', f'🔍 正在查询 禁漫车号 - [{album_id}] 的详情...')
                try:
                    album = client.get_album_detail(album_id)
                except Exception as e:
                    has_error = True
                    err_msg = f'❌❌❌ 获取失败: album {album_id} 详情请求出错, 原因: {e}'
                    if self.json_output:
                        print(err_msg, file=sys.stderr)
                    else:
                        jm_log('jmv', err_msg, e)
                    continue

                if self.json_output:
                    json_items.append(self.album_to_dict(album))
                else:
                    self.print_album_detail(album)
        finally:
            if self.json_output:
                JmModuleConfig.FLAG_ENABLE_JM_LOG = prev_log_flag

        if self.json_output and (json_items or not has_error):
            payload = json_items[0] if len(album_ids) == 1 and len(json_items) == 1 else json_items
            print(json.dumps(payload, ensure_ascii=False, indent=2))

        if has_error:
            sys.exit(1)


def view_main():
    JmViewUI().main()
