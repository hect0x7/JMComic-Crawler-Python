"""
command-line usage

1. jmcomic - download album/photo:

  $ jmcomic 123 456 p333 --option="D:/option.yml"

2. jmv - view album detail (extract digits from text as album id):

  $ jmv 350234
  $ jmv 350谁还没看过234
  $ jmv abc123141 --option="D:/option.yml"

"""
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

        args = parser.parse_args()
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
        from .api import jm_log
        jm_log('command_line',
               f'start downloading...\n'
               f'- using option: [{self.option_path or "default"}]\n'
               f'to be downloaded: \n'
               f'- album: {self.album_id_list}\n'
               f'- photo: {self.photo_id_list}')

        from .api import create_option, JmOption
        if self.option_path is not None:
            option = create_option(self.option_path)
        else:
            option = JmOption.default()

        self.run(option)

    def run(self, option):
        from .api import download_album, download_photo
        from common import MultiTaskLauncher

        if len(self.album_id_list) == 0:
            download_photo(self.photo_id_list, option)
        elif len(self.photo_id_list) == 0:
            download_album(self.album_id_list, option)
        else:
            # 同时下载album和photo
            launcher = MultiTaskLauncher()

            launcher.create_task(
                target=download_album,
                args=(self.album_id_list, option)
            )
            launcher.create_task(
                target=download_photo,
                args=(self.photo_id_list, option)
            )

            launcher.wait_finish()


def main():
    JmcomicUI().main()


class JmViewUI:

    def __init__(self) -> None:
        self.raw_text: str = ''
        self.option_path: Optional[str] = None
        self.auto_exit: bool = False

    def parse_arg(self):
        import argparse
        parser = argparse.ArgumentParser(
            prog='jmv',
            description='JMComic Album Viewer - 从文本中提取数字作为album ID，查看本子详情',
        )
        parser.add_argument(
            'text',
            help='包含数字的禁漫车号，例如 "350谁还没看过234"，会提取出 "350234" 作为 album ID',
        )
        parser.add_argument(
            '--option',
            help='option 文件路径，也可通过环境变量 JM_OPTION_PATH 指定',
            type=str,
            default=get_env('JM_OPTION_PATH', ''),
        )
        parser.add_argument(
            '-y', '--yes',
            action='store_true',
            help='执行完毕后直接退出，无需按回车确认',
        )

        args = parser.parse_args()
        self.raw_text = args.text
        self.auto_exit = args.yes

        option_str = args.option
        if len(option_str) == 0 or option_str == "''":
            self.option_path = None
        else:
            self.option_path = os.path.abspath(option_str)

    def extract_album_id(self) -> str:
        import re
        numbers = re.findall(r'\d+', self.raw_text)
        if not numbers:
            from .api import jm_log
            jm_log('jmv', f'❌❌❌ 解析失败: 无法从 "{self.raw_text}" 中提取到任何数字 ❌❌❌')
            exit(1)
        album_id = ''.join(numbers)
        return album_id

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
        self.parse_arg()

        import atexit
        atexit.register(self._pause)

        album_id = self.extract_album_id()

        from .api import jm_log
        jm_log('jmv', f'🔍 正在查询 禁漫车号 - [{album_id}] 的详情...')

        from .api import create_option, JmOption
        if self.option_path is not None:
            option = create_option(self.option_path)
        else:
            option = JmOption.default()

        client = option.new_jm_client()
        try:
            album = client.get_album_detail(album_id)
        except Exception as e:
            jm_log('jmv', f'❌❌❌ 获取失败: album {album_id} 详情请求出错, 原因: {e}', e)
            exit(1)

        self.print_album_detail(album)


def view_main():
    JmViewUI().main()
