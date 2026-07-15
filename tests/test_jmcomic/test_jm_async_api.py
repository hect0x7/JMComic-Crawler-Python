"""
Async API 行为一致性测试 (参考 test_jm_api.py)

测试 download_album_async / download_photo_async / download_batch_async 的行为，
确保与 sync 版 download_album / download_photo / download_batch 行为一致。
"""

import asyncio
import threading
from test_jmcomic import *
from jmcomic import (
    download_album_async, download_photo_async, download_batch_async,
    download_album, download_photo,
)
from jmcomic.jm_async_downloader import JmAsyncDownloader
from jmcomic.jm_entity import JmAlbumDetail, JmPhotoDetail


class Test_Async_Api(JmAsyncTestConfigurable):
    """异步 API 行为一致性测试（真实网络）"""

    def test_async_download_photo_by_id(self):
        """测试 download_photo_async：验证返回值与同步版本保持一致"""
        photo_id = '438516'
        callback_result = {}
        caller_thread = threading.get_ident()

        def callback(photo, downloader):
            callback_result['photo'] = photo
            callback_result['downloader'] = downloader
            callback_result['thread'] = threading.get_ident()

        # sync
        sync_photo, sync_dler = download_photo(photo_id, self.option)
        # async
        async_photo, async_dler = asyncio.run(download_photo_async(
            photo_id,
            self.option,
            callback=callback,
        ))

        self.assertIsInstance(async_dler, JmAsyncDownloader, 'downloader 必须是异步版本')
        self.assertIsInstance(async_photo, JmPhotoDetail, '返回值必须包含 photo')
        self.assert_sync_async_equal(sync_photo.photo_id, async_photo.photo_id, 'photo.photo_id')
        self.assertIs(callback_result['photo'], async_photo)
        self.assertIs(callback_result['downloader'], async_dler)
        self.assertNotEqual(callback_result['thread'], caller_thread, '同步 callback 不应阻塞事件循环线程')
        self.assertIsNone(async_dler.client, '顶层异步下载结束后 downloader client 应已关闭')

    def test_async_download_album_by_id(self):
        """测试 download_album_async：验证返回值与同步版本保持一致"""
        album_id = '438516'
        callback_result = {}

        async def callback(album, downloader):
            await asyncio.sleep(0)
            callback_result['album'] = album
            callback_result['downloader'] = downloader

        # sync
        sync_album, sync_dler = download_album(album_id, self.option)
        # async
        async_album, async_dler = asyncio.run(download_album_async(
            album_id,
            self.option,
            callback=callback,
        ))

        self.assertIsInstance(async_dler, JmAsyncDownloader, 'downloader 必须是异步版本')
        self.assertIsInstance(async_album, JmAlbumDetail, '返回值必须包含 album')
        self.assert_album_equal(sync_album, async_album)
        self.assertIs(callback_result['album'], async_album)
        self.assertIs(callback_result['downloader'], async_dler)
        self.assertIsNone(async_dler.client, '顶层异步下载结束后 downloader client 应已关闭')

    def test_async_batch(self):
        """测试 download_batch_async：验证返回集合大小与同步版本保持一致"""
        album_ls = str_to_list('''
        326361
        366867
        438516
        ''')

        # sync
        sync_ret = download_album(album_ls, self.option)
        # async
        async_ret = asyncio.run(download_batch_async(
            download_album_async, album_ls, self.option,
        ))

        # 返回值数量一致
        self.assert_sync_async_equal(len(sync_ret), len(async_ret), 'batch.result_count')

        # 提取 album_ids 比较（set 无序，所以排序比较）
        sync_ids = sorted(str(r[0].album_id) for r in sync_ret)
        async_ids = sorted(str(r[0].album_id) for r in async_ret)
        self.assert_sync_async_equal(sync_ids, async_ids, 'batch.album_ids')

    def test_async_partial_exception(self):
        """
        测试部分失败场景：验证异常传播行为与同步版本保持一致

        核心断言：sync 和 async 在 check_exception=True 时，
        最终都应抛出 PartialDownloadFailedException。
        """

        # ===== Sync 版 =====
        class SyncTestDownloader(JmDownloader):
            def do_filter(self, detail: DetailEntity):
                if detail.is_photo():
                    return detail[0:2]
                if detail.is_album():
                    return detail[0:2]
                return super().do_filter(detail)

            @catch_exception
            def download_by_image_detail(self, image: JmImageDetail):
                raise Exception('test_partial_exception')

        sync_raised = False
        try:
            download_album(182150, downloader=SyncTestDownloader, check_exception=True)
        except PartialDownloadFailedException:
            sync_raised = True

        # ===== Async 版 =====
        class AsyncTestDownloader(JmAsyncDownloader):
            def do_filter(self, detail):
                if isinstance(detail, JmAlbumDetail):
                    return list(detail)[0:2]
                if isinstance(detail, JmPhotoDetail):
                    return list(detail)[0:2]
                return detail

            async def _download_single_image(self, image):
                raise Exception('test_partial_exception')

        async_raised = False
        try:
            asyncio.run(download_album_async(
                182150, downloader=AsyncTestDownloader, check_exception=True,
            ))
        except PartialDownloadFailedException:
            async_raised = True

        # 核心断言：最终异常行为一致
        self.assertTrue(sync_raised, 'sync 应抛出 PartialDownloadFailedException')
        self.assertTrue(async_raised, 'async 应抛出 PartialDownloadFailedException')
        self.assert_sync_async_equal(sync_raised, async_raised, 'partial_exception.raised')
