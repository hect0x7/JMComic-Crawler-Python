"""
Async Plugin 容错对称性测试 —— 对标 test_jm_plugin.py

验证异步下载器在插件缺失 album 上下文时的容错行为与 sync 一致。
"""
import asyncio

from test_jmcomic import *
from jmcomic import download_photo_async
from jmcomic.jm_async_downloader import JmAsyncDownloader


class Test_Async_Plugin(JmAsyncTestConfigurable):
    """异步插件容错对称性测试（真实网络）"""

    def test_async_plugin_missing_album_context(self):
        """
        对标 test_plugin_missing_album_context

        当仅下载单章(photo)时，上下文中缺少 album 对象。
        各路径生成插件（download_cover, img2pdf, long_img, zip）
        应能从 photo.from_album 中提取专辑属性，避免 KeyError。
        sync 和 async 在此场景下的行为应一致（均不抛出）。
        """
        photo_id = '350234'
        option = self.new_option()

        flawed_rule = {
            'base_dir': option.dir_rule.base_dir,
            'rule': '{Atitle}/{Aid}_photo.jpg',
        }

        # 异步版用一个不真正下载图片的 downloader
        class AsyncDoNotDownload(JmAsyncDownloader):
            async def _download_single_image(self, image):
                # 只确保目录创建（对齐 sync DoNotDownloadImage）
                self.option.decide_image_filepath(image)

        test_plugins = ['download_cover', 'img2pdf', 'long_img', 'zip']
        option.plugins['before_photo'] = [
            {
                'plugin': plugin_key,
                'kwargs': {'dir_rule': flawed_rule},
                'safe': False,  # 防止内部 catch 异常
            }
            for plugin_key in test_plugins
        ]

        # sync：应不抛异常
        sync_ok = True
        try:
            from jmcomic.jm_downloader import DoNotDownloadImage
            download_photo(photo_id, option, downloader=DoNotDownloadImage)
        except KeyError:
            sync_ok = False

        # async：应不抛异常
        async_ok = True
        try:
            asyncio.run(download_photo_async(photo_id, option, downloader=AsyncDoNotDownload))
        except KeyError:
            async_ok = False

        self.assertTrue(sync_ok, 'sync 不应抛 KeyError')
        self.assertTrue(async_ok, 'async 不应抛 KeyError')
        self.assert_sync_async_equal(sync_ok, async_ok, 'plugin_missing_album.ok')
