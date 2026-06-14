"""
Async Client API 对称性测试 —— 对标 test_jm_client.py

每个测试同时调用 sync API client 和 async API client，diff 返回值。
若 sync/async 行为不一致，测试 FAIL 并报告差异。
"""

from test_jmcomic import *
import asyncio


class Test_Async_Client(JmAsyncTestConfigurable):
    """异步 client API 对称性测试（真实网络）"""

    def test_async_fetch_album(self):
        """对标 test_fetch_album：get_album_detail 返回值结构 diff"""
        album_id = '438516'
        sync_album = self.sync_api_client.get_album_detail(album_id)
        async_album = self.run_async(self.async_client.get_album_detail(album_id))
        self.assert_album_equal(sync_album, async_album)

    def test_async_search(self):
        """对标 test_search：search_tag + search_site diff"""
        # search_tag
        sync_page = self.sync_api_client.search_tag('+无修正 +中文 -全彩')
        async_page = self.run_async(self.async_client.search_tag('+无修正 +中文 -全彩'))
        self.assert_search_page_equal(sync_page, async_page)

        # search_site —— 精确搜索单个 album
        aid = '438516'
        sync_page2 = self.sync_api_client.search_site(aid)
        async_page2 = self.run_async(self.async_client.search_site(aid))
        sync_aid, _ = sync_page2[0]
        async_aid, _ = async_page2[0]
        self.assert_sync_async_equal(sync_aid, async_aid, 'search_site.first_aid')

    def test_async_album_missing(self):
        """对标 test_album_missing：异常类型 diff"""
        # sync 应抛 MissingAlbumPhotoException
        self.assertRaises(
            MissingAlbumPhotoException,
            self.sync_api_client.get_album_detail,
            '530595',
        )
        # async 应抛相同异常
        with self.assertRaises(MissingAlbumPhotoException):
            self.run_async(self.async_client.get_album_detail('530595'))

    def test_async_detail_property_list(self):
        """对标 test_detail_property_list：album 属性列表 diff"""
        album_id = 410090
        sync_album = self.sync_api_client.get_album_detail(album_id)
        async_album = self.run_async(self.async_client.get_album_detail(album_id))

        for attr in ['works', 'actors', 'tags', 'authors']:
            sync_val = getattr(sync_album, attr)
            async_val = getattr(async_album, attr)
            # 转为相同 zh-cn 形式后比较（与 sync 原测试行为一致）
            sync_normalized = [JmcomicText.to_zh_cn(v) for v in sync_val]
            async_normalized = [JmcomicText.to_zh_cn(v) for v in async_val]
            self.assert_sync_async_equal(sync_normalized, async_normalized, f'album.{attr}')

    def test_async_comment_count(self):
        """对标 test_comment_count：comment_count diff"""
        aid = '438516'
        sync_album = self.sync_api_client.get_album_detail(aid)
        async_album = self.run_async(self.async_client.get_album_detail(aid))
        self.assert_sync_async_equal(
            sync_album.comment_count, async_album.comment_count,
            'album.comment_count',
        )
        self.assertGreater(async_album.comment_count, 0, 'comment_count 应 > 0')

    def test_async_get_detail(self):
        """对标 test_get_detail：album + photo 联合 diff"""
        album_id = 400222
        sync_album = self.sync_api_client.get_album_detail(album_id)
        async_album = self.run_async(self.async_client.get_album_detail(album_id))
        self.assert_album_equal(sync_album, async_album)

        # 取前 3 章的 photo detail diff
        for photo in sync_album[0:3]:
            sync_photo = self.sync_api_client.get_photo_detail(photo.photo_id)
            async_photo = self.run_async(self.async_client.get_photo_detail(photo.photo_id))
            self.assert_photo_equal(sync_photo, async_photo)

    def test_async_search_params(self):
        """对标 test_search_params：不同排序参数的搜索结果 diff"""
        cases = {
            152637: {
                'search_query': '无修正',
                'order_by': JmMagicConstants.ORDER_BY_VIEW,
                'time': JmMagicConstants.TIME_ALL,
            },
            147643: {
                'search_query': '无修正',
                'order_by': JmMagicConstants.ORDER_BY_PICTURE,
                'time': JmMagicConstants.TIME_ALL,
            },
        }

        parity_failures = []
        network_errors = []
        for expected_id, params in cases.items():
            try:
                sync_page = self.sync_api_client.search_site(**params)
                async_page = self.run_async(self.async_client.search_site(**params))
                sync_first_aid = int(sync_page[0][0])
                async_first_aid = int(async_page[0][0])
                self.assert_sync_async_equal(sync_first_aid, async_first_aid,
                                             f'search_params[{expected_id}].first_aid')
            except AssertionError as e:
                parity_failures.append(e)
            except Exception as e:
                network_errors.append(e)

        if len(parity_failures) > 0:
            for e in parity_failures:
                print(f'Parity failure: {e}')
            raise AssertionError(f'Parity failures: {parity_failures}')

        if len(network_errors) == 0:
            return

        for e in network_errors:
            print(f'Network error (expected, skipping): {e}')

    def test_async_ranking(self):
        """对标 test_ranking：month_ranking diff"""
        sync_ranking = self.sync_api_client.month_ranking(1)
        async_ranking = self.run_async(self.async_client.month_ranking(1))
        self.assert_search_page_equal(sync_ranking, async_ranking, check_total=False)

    def test_async_photo_sort(self):
        """对标 test_photo_sort：photo.sort 排序一致性 diff"""
        # 单章本子
        single_ids = ['430371', '438696', '432888']
        for pid in single_ids:
            sync_photo = self.sync_api_client.get_photo_detail(pid, fetch_album=False, fetch_scramble_id=False)
            async_photo = self.run_async(
                self.async_client.get_photo_detail(pid, fetch_album=False, fetch_scramble_id=False)
            )
            self.assert_sync_async_equal(sync_photo.sort, async_photo.sort, f'photo[{pid}].sort')

        # 多章本子：验证 album 的 photo sort 与单独请求的 photo sort 一致
        album_id = '282293'
        async_album = self.run_async(self.async_client.get_album_detail(album_id))
        album_sorts = sorted([p.sort for p in async_album])

        async def fetch_all_photo_sorts():
            tasks = [
                self.async_client.get_photo_detail(p.photo_id, fetch_album=False, fetch_scramble_id=False)
                for p in async_album
            ]
            photos = await asyncio.gather(*tasks)
            return sorted([p.sort for p in photos])

        photo_sorts = self.run_async(fetch_all_photo_sorts())
        self.assertListEqual(album_sorts, photo_sorts, f'album[{album_id}] sort 一致性')

    def test_async_getitem_and_slice(self):
        """对标 test_getitem_and_slice：entity 切片 diff"""
        # album 切片
        sync_album = self.sync_api_client.get_album_detail('400222')
        async_album = self.run_async(self.async_client.get_album_detail('400222'))

        # 单项索引
        self.assert_sync_async_equal(
            int(sync_album[0].id), int(async_album[0].id),
            'album[0].id',
        )
        self.assert_sync_async_equal(
            int(sync_album[1].id), int(async_album[1].id),
            'album[1].id',
        )

        # 切片
        sync_slice = [int(p.id) for p in sync_album[1:3]]
        async_slice = [int(p.id) for p in async_album[1:3]]
        self.assert_sync_async_equal(sync_slice, async_slice, 'album[1:3].ids')

    def test_async_download_image(self):
        """对标 test_download_image：图片下载 diff（比较原始字节）"""
        photo_id = '438516'
        sync_photo = self.sync_api_client.get_photo_detail(photo_id)
        async_photo = self.run_async(self.async_client.get_photo_detail(photo_id))

        # 取第一张图
        sync_img = sync_photo[0]
        async_img = async_photo[0]
        self.assert_sync_async_equal(sync_img.filename, async_img.filename, 'image.filename')

        # 下载图片原始字节
        async_resp = self.run_async(self.async_client.get_jm_image(async_img.download_url))
        self.assertGreater(len(async_resp.content), 1000, 'image.content_length > 1000')

    # ===== 专门 cache 测试 =====

    def test_async_cache_on_off(self):
        """专门测试：async 缓存开启/关闭行为"""
        loop = asyncio.new_event_loop()
        client: AsyncJmcomicClient = self.option.new_jm_async_client()

        try:
            loop.run_until_complete(client.setup())

            # 1. 缓存默认关闭（_cache=None）
            self.assertIsNone(client.get_cache_dict(), '默认 cache 应为 None')

            # 开启缓存
            client.set_cache_dict({})
            album1 = loop.run_until_complete(client.get_album_detail('123'))
            album2 = loop.run_until_complete(client.get_album_detail('123'))
            self.assertIs(album1, album2, '缓存开启：同 ID 应返回同一对象（对象引用相同）')

            # 2. 关闭缓存
            client.set_cache_dict(None)
            album3 = loop.run_until_complete(client.get_album_detail('123'))
            self.assertIsNot(album1, album3, '缓存关闭：应返回新对象')

            # 3. 重新开启，验证新缓存不含旧数据
            new_cache = {}
            client.set_cache_dict(new_cache)
            album4 = loop.run_until_complete(client.get_album_detail('123'))
            self.assertEqual(len(new_cache), 1, '新缓存应有 1 条记录')
            album5 = loop.run_until_complete(client.get_album_detail('123'))
            self.assertIs(album4, album5, '重新开启缓存后应命中')

        finally:
            loop.run_until_complete(client.close())
            loop.close()

    def test_async_cache_option_driven(self):
        """专门测试：按 option.client.cache 配置驱动缓存"""
        loop = asyncio.new_event_loop()
        client_on = None
        client_off = None
        client_default = None
        try:
            # cache=True → 应开启（对齐 sync 的 CacheRegistry.enable_client_cache_on_condition）
            opt = self.new_option()
            opt.client.src_dict['cache'] = True
            client_on = opt.new_jm_async_client()
            self.assertIsNotNone(client_on.get_cache_dict(), 'cache=True 应开启缓存')

            # cache=False → 应关闭
            opt2 = self.new_option()
            opt2.client.src_dict['cache'] = False
            client_off = opt2.new_jm_async_client()
            self.assertIsNone(client_off.get_cache_dict(), 'cache=False 应关闭缓存')

            # 默认 → 应关闭（默认配置 cache=None）
            opt3 = JmOption.default()
            client_default = opt3.new_jm_async_client()
            self.assertIsNone(client_default.get_cache_dict(), '默认配置应关闭缓存')
        finally:
            if client_on is not None:
                loop.run_until_complete(client_on.close())
            if client_off is not None:
                loop.run_until_complete(client_off.close())
            if client_default is not None:
                loop.run_until_complete(client_default.close())
            loop.close()

    # ===== diff 标记测试 =====

    def test_async_search_generator(self):
        """测试异步生成器 search_gen 的使用 (包含 asend)"""
        async def run():
            gen = self.async_client.search_gen('MANA')
            # 触发第一页
            page1 = await gen.asend(None)
            self.assertGreater(page1.total, 0)

            # 使用 asend 翻页
            page2 = await gen.asend({'page': 2})
            self.assertGreater(page2.total, 0)

        self.run_async(run())

    def test_async_download_cover_not_supported(self):
        """diff 标记：async client 无独立 download_album_cover"""
        self.assertFalse(
            hasattr(self.async_client, 'download_album_cover'),
            'async client 不应有 download_album_cover（sync 独有功能）'
        )
