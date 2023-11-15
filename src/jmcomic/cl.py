"""
command-line usage

for example, download album 123 456, photo 333:

$ jmcomic 123 456 p333 --option="D:/option.yml"


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
