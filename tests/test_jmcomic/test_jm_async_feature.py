"""
Async Feature 触发对称性测试 —— 对标 test_jm_feature.py

验证 Feature 在异步下载流程中的触发次数和行为与 sync 一致。
"""
import asyncio

from test_jmcomic import *
from jmcomic import download_album_async, download_photo_async


class Test_Async_Feature(JmAsyncTestConfigurable):
    """异步 Feature 触发对称性测试（真实网络）"""

    def test_async_download_use_feature(self):
        """
        对标 test_download_use_feature：Feature 触发次数 diff

        sync 行为：download_album('438516') 有 1 章 →
        after_photo(1) + after_album(1) = Feature 触发 2 次。
        async 应完全一致。
        """
        album_id = '438516'

        # ===== sync 计数 =====
        sync_count = 0

        class SyncCounter(Feature):
            def invoke(self, option, **kwargs):
                nonlocal sync_count
                sync_count += 1

        jmcomic.download_album(album_id, self.option, extra=SyncCounter())

        # ===== async 计数 =====
        async_count = 0

        class AsyncCounter(Feature):
            def invoke(self, option, **kwargs):
                nonlocal async_count
                async_count += 1

        asyncio.run(download_album_async(album_id, self.option, extra=AsyncCounter()))

        # 核心断言：触发次数一致
        self.assert_sync_async_equal(sync_count, async_count, 'feature.invoke_count (album)')
        self.assertGreater(sync_count, 0, 'album(438516) 有 1 章, 应至少触发 1 次')

        # ===== download_photo 场景 =====
        sync_photo_count = 0

        class SyncPhotoCounter(Feature):
            def invoke(self, option, **kwargs):
                nonlocal sync_photo_count
                sync_photo_count += 1

        # 提取真实 photo_id 传入，避免直接传入 album_id 的偶合性依赖
        photo_id = str(self.sync_api_client.get_album_detail(album_id)[0].photo_id)

        jmcomic.download_photo(photo_id, self.option, extra=SyncPhotoCounter())

        async_photo_count = 0

        class AsyncPhotoCounter(Feature):
            def invoke(self, option, **kwargs):
                nonlocal async_photo_count
                async_photo_count += 1

        asyncio.run(download_photo_async(photo_id, self.option, extra=AsyncPhotoCounter()))

        self.assert_sync_async_equal(sync_photo_count, async_photo_count, 'feature.invoke_count (photo)')
        self.assertEqual(sync_photo_count, 1, 'download_photo 应触发 1 次')

    def test_async_export_album_use_photo_rule(self):
        """
        对标 test_export_album_use_photo_rule：负面测试

        在 Album 模式下强行使用 Photo 级规则（Ptitle），
        sync 在 after_album 阶段 photo=None 导致 AttributeError。
        async 行为应一致。
        """
        album_id = '438516'
        f = Feature.export_pdf(filename_rule='Ptitle')

        # sync：invoke 时 photo=None → AttributeError
        sync_album = self.sync_api_client.get_album_detail(album_id)
        sync_raised = False
        try:
            f.invoke(self.option, feature_from='download_album', when='after_album',
                     album=sync_album, photo=None)
        except AttributeError:
            sync_raised = True

        # async：相同 Feature，使用 async album 实体
        async_album = self.run_async(self.async_client.get_album_detail(album_id))
        async_raised = False
        try:
            f.invoke(self.option, feature_from='download_album', when='after_album',
                     album=async_album, photo=None)
        except AttributeError:
            async_raised = True

        self.assertTrue(sync_raised, 'sync 应抛 AttributeError')
        self.assertTrue(async_raised, 'async 应抛 AttributeError')
        self.assert_sync_async_equal(sync_raised, async_raised, 'export_album_photo_rule.raised')
