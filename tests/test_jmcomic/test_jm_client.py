import asyncio
from types import SimpleNamespace

from test_jmcomic import *


class Test_Client(JmTestConfigurable):

    def test_download_image(self):
        jm_photo_id = 'JM438516'
        photo = self.client.get_photo_detail(jm_photo_id)
        image = photo[0]
        filepath = self.option.decide_image_filepath(image)
        self.client.download_by_image_detail(image, filepath)
        print(filepath)

    def test_fetch_album(self):
        album_id = "JM438516"
        self.client.get_album_detail(album_id)

    def test_search(self):
        page: JmSearchPage = self.client.search_tag('+无修正 +中文 -全彩')
        print(f'总数: {page.total}, 分页大小: {page.page_size}，页数: {page.page_count}')

        if len(page) >= 1:
            for aid, ainfo in page[0:1:1]:
                print(aid, ainfo)

        for aid, atitle, tags in page.iter_id_title_tag():
            print(aid, atitle, tags)

        aid = '438516'
        page = self.client.search_site(aid)
        search_aid, ainfo = page[0]
        self.assertEqual(search_aid, aid)

    def test_gt_300_photo(self):
        photo_id = '147643'
        photo: JmPhotoDetail = self.client.get_photo_detail(photo_id)
        image = photo[3000]
        print(image.img_url)
        self.client.download_by_image_detail(image, self.option.decide_image_filepath(image))

    def test_album_missing(self):
        """
        Verify get_album_detail raises MissingAlbumPhotoException for a missing album.
        
        Asserts that requesting album with ID '530595' causes a MissingAlbumPhotoException to be raised.
        """
        self.assertRaises(
            MissingAlbumPhotoException,
            self.client.get_album_detail,
            '530595'
        )

    def test_detail_property_list(self):
        """
        Validate that selected property lists of album 410090 match expected values after conversion to Chinese.
        
        Fetches album detail for ID 410090 and compares the first up to nine entries of its `works`, `actors`, `tags`,
        and `authors` lists against expected values, converting both sides with `JmcomicText.to_zh_cn` before asserting
        element-wise equality.
        """
        album = self.client.get_album_detail(410090)

        ans = [
            (album.works, ['原神', 'Genshin']),
            (album.actors, ['申鶴', '神里綾華', '甘雨']),
            (album.tags, ['C101', '巨乳', '校服', '口交', '乳交', '群交', '連褲襪', '中文', '禁漫漢化組', '纯爱']),
            (album.authors, ['うぱ西']),
        ]

        for pair in ans:
            left = pair[0][0:9]
            right = pair[1][0:9]
            for i, ans in enumerate(right):
                self.assertEqual(JmcomicText.to_zh_cn(left[i]), JmcomicText.to_zh_cn(ans))

    def test_photo_sort(self):
        client = self.option.build_jm_client()
        get_photo_detail = lambda *args: client.get_photo_detail(*args, fetch_album=False, fetch_scramble_id=False)
        get_album_detail = client.get_album_detail

        # 测试用例 - 单章本子
        single_photo_album_is = str_to_list('''
        430371
        438696
        432888
        ''')

        # 测试用例 - 多章本子
        multi_photo_album_is = str_to_list('''
        282293
        122061
        ''')

        photo_dict: Dict[str, JmPhotoDetail] = multi_call(get_photo_detail, single_photo_album_is)
        album_dict: Dict[str, JmAlbumDetail] = multi_call(get_album_detail, single_photo_album_is)

        for each in photo_dict.values():
            each: JmPhotoDetail
            self.assertEqual(each.album_index, 1)

        for each in album_dict.values():
            each: JmAlbumDetail
            self.assertEqual(each[0].album_index, 1)

        print_eye_catching('【通过】测试用例 - 单章本子')
        multi_photo_album_dict: Dict[JmAlbumDetail, List[JmPhotoDetail]] = {}

        def run(aid):
            album = get_album_detail(aid)

            photo_dict = multi_call(
                get_photo_detail,
                (photo.photo_id for photo in album),
                launcher=thread_pool_executor,
            )

            multi_photo_album_dict[album] = list(photo_dict.values())

        multi_thread_launcher(
            iter_objs=multi_photo_album_is,
            apply_each_obj_func=run,
        )

        for album, photo_ls in multi_photo_album_dict.items():
            ls1 = sorted([each.sort for each in album])
            ls2 = sorted([ans.sort for ans in photo_ls])
            print(ls1)
            print(ls2)
            self.assertListEqual(
                ls1,
                ls2,
                album.album_id
            )

    def test_getitem_and_slice(self):
        cl: JmcomicClient = self.client
        cases = [
            ['400222', 0, [400222]],
            ['400222', 1, [413446]],
            ['400222', (None, 1), [400222]],
            ['400222', (1, 3), [413446, 413447]],
            ['413447', (1, 3), [2, 3], []],
        ]

        for [jmid, slicearg, *args] in cases:
            ans = args[0]

            if len(args) == 1:
                func = cl.get_album_detail
            else:
                func = cl.get_photo_detail

            jmentity = func(jmid)

            ls: List[Union[JmPhotoDetail, JmImageDetail]]
            if isinstance(slicearg, int):
                ls = [jmentity[slicearg]]
            elif len(slicearg) == 2:
                ls = jmentity[slicearg[0]: slicearg[1]]
            else:
                ls = jmentity[slicearg[0]: slicearg[1]: slicearg[2]]

            if len(args) == 1:
                self.assertListEqual(
                    list1=[int(e.id) for e in ls],
                    list2=ans,
                )
            else:
                self.assertListEqual(
                    list1=[int(e.img_file_name) for e in ls],
                    list2=ans,
                )

    def test_search_params(self):
        elist = []

        def search_and_test(expected_result, params):
            try:
                page = self.client.search_site(**params)
                print(page)
                self.assertEqual(int(page[0][0]), expected_result)
            except Exception as e:
                elist.append(e)

        # 定义测试用例
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

        multi_thread_launcher(
            iter_objs=cases.items(),
            apply_each_obj_func=search_and_test,
        )

        if len(elist) == 0:
            return

        for e in elist:
            print(e)

        raise AssertionError(elist)

    def test_comment_count(self):
        aid = 'JM438516'
        album = self.client.get_album_detail(aid)
        self.assertGreater(album.comment_count, 0)
        page = self.client.search_site('无修正')
        for i in range(3):
            aid, _atitle = page[i]
            self.assertGreaterEqual(
                self.client.get_album_detail(aid).comment_count,
                0,
                aid,
            )

    def test_album_pagination(self):
        album_id = '302820'
        api_client = self.option.new_jm_client(impl='api')
        html_client = self.option.new_jm_client(impl='html')

        api_gen = api_client.album_pagination_gen(album_id)
        api_page = next(api_gen)
        api_page_2 = next(api_gen)
        api_gen.close()

        html_page = None
        failed_domains = []
        for domain in html_client.get_html_domain_all():
            html_client.set_domain_list([domain])
            try:
                html_page = html_client.album_pagination(album_id, page=1)
                break
            except Exception as e:
                failed_domains.append((domain, e))
                continue

        for domain, error in failed_domains:
            print(f'本子评论请求失败，域名: {domain}, 异常: {error}')
        self.assertIsNotNone(
            html_page,
            f'所有网页域名均无法获取本子评论，失败域名: {failed_domains}',
        )
        api_comments = list(api_page)
        html_comments = list(html_page)

        self.assertTrue(api_comments)
        self.assertTrue(list(api_page_2))
        self.assertTrue(html_comments)
        self.assertEqual(api_page.page_number, 1)
        self.assertEqual(api_page_2.page_number, 2)
        self.assertEqual(html_page.page_number, 1)
        self.assertIsInstance(api_page.raw_data, AdvancedDict)
        self.assertIsInstance(html_page.raw_data, AdvancedDict)
        self.assertGreaterEqual(api_page.comment_count, len(api_page))
        self.assertGreaterEqual(html_page.comment_count, len(html_page))
        self.assertGreater(api_page.total, 0)
        self.assertGreater(html_page.total, 0)
        self.assertEqual(api_page.total, api_page_2.total)

        html_gen_without_total = html_client.album_pagination_gen(
            album_id,
            page=1,
            need_total=False,
        )
        html_page_without_total = next(html_gen_without_total)
        html_page_2_without_total = next(html_gen_without_total)
        html_gen_without_total.close()

        self.assertTrue(list(html_page_2_without_total))
        self.assertIsNone(html_page_without_total.total)
        self.assertIsNone(html_page_without_total.page_count)
        self.assertIsNone(html_page_2_without_total.total)
        self.assertIsNone(html_page_2_without_total.page_count)
        self.assertEqual(html_page_without_total.page_number, 1)
        self.assertEqual(html_page_2_without_total.page_number, 2)

        api_forum_gen = api_client.forum_pagination_gen(page=1)
        api_forum_page = next(api_forum_gen)
        api_forum_page_2 = next(api_forum_gen)
        api_forum_gen.close()

        html_forum_gen = html_client.forum_pagination_gen(page=1, with_ad_wcm=1)
        html_forum_page = next(html_forum_gen)
        html_forum_page_2 = next(html_forum_gen)
        html_forum_gen.close()

        self.assertTrue(list(api_forum_page))
        self.assertTrue(list(api_forum_page_2))
        self.assertTrue(list(html_forum_page))
        self.assertTrue(list(html_forum_page_2))
        self.assertEqual(api_forum_page.page_number, 1)
        self.assertEqual(api_forum_page_2.page_number, 2)
        self.assertEqual(html_forum_page.page_number, 1)
        self.assertEqual(html_forum_page_2.page_number, 2)
        self.assertGreater(api_forum_page.total, 0)
        self.assertIsNone(html_forum_page.total)
        self.assertIsNone(html_forum_page.page_count)
        self.assertIsInstance(api_forum_page.raw_data, AdvancedDict)
        self.assertIsInstance(html_forum_page.raw_data, AdvancedDict)
        self.assertTrue(any(comment.album_id for comment in html_forum_page))
        self.assertTrue(any(comment.user_id for comment in html_forum_page))

        for comment in (api_comments[0], html_comments[0]):
            self.assertIsInstance(comment.raw_data, AdvancedDict)
            self.assertTrue(comment.comment_id)
            self.assertEqual(str(comment.album_id), album_id)
            self.assertIsInstance(comment.content, str)
            self.assertIsInstance(comment.is_spoiler, bool)
            self.assertIn(str(comment.comment_id), str(comment))
            self.assertIn(comment.content, str(comment))

        api_comments_by_cid = {
            str(comment.comment_id): comment
            for comment in api_comments
        }
        html_comments_by_cid = {
            str(comment.comment_id): comment
            for comment in html_comments
        }
        common_cids = api_comments_by_cid.keys() & html_comments_by_cid.keys()
        self.assertTrue(common_cids)

        checked_reply = False
        api_pages = {1: api_page, 2: api_page_2}
        for reply_page_number in range(1, 6):
            candidate_api_page = api_pages.get(reply_page_number)
            if candidate_api_page is None:
                candidate_api_page = api_client.album_pagination(
                    album_id,
                    page=reply_page_number,
                )
            candidate_html_page = (
                html_page_without_total
                if reply_page_number == 1
                else html_client.album_pagination(
                    album_id,
                    page=reply_page_number,
                    need_total=False,
                )
            )
            html_reply_comments = {
                str(comment.comment_id): comment
                for comment in candidate_html_page
            }
            for api_comment in candidate_api_page:
                api_replies = api_comment.replies
                html_comment = html_reply_comments.get(str(api_comment.comment_id))
                if not api_replies or html_comment is None:
                    continue

                html_replies = html_comment.replies
                if not html_replies:
                    continue

                api_replies_by_cid = {
                    str(reply.comment_id): reply
                    for reply in api_replies
                }
                html_replies_by_cid = {
                    str(reply.comment_id): reply
                    for reply in html_replies
                }
                common_reply_cids = api_replies_by_cid.keys() & html_replies_by_cid.keys()
                if not common_reply_cids:
                    continue

                reply_cid = next(iter(common_reply_cids))
                api_reply = api_replies_by_cid[reply_cid]
                html_reply = html_replies_by_cid[reply_cid]
                self.assertEqual(str(html_reply.comment_id), reply_cid)
                self.assertEqual(str(api_reply.comment_id), reply_cid)
                self.assertIsInstance(api_reply.raw_data, AdvancedDict)
                self.assertIsInstance(html_reply.raw_data, AdvancedDict)
                self.assertIsInstance(api_reply.content, str)
                self.assertFalse(api_reply.content.startswith('<div'))
                self.assertEqual(
                    str(html_reply.parent_comment_id),
                    str(api_comment.comment_id),
                )
                self.assertGreater(candidate_api_page.comment_count, len(candidate_api_page))
                self.assertGreater(candidate_html_page.comment_count, len(candidate_html_page))
                checked_reply = True
                break

            if checked_reply:
                break

        self.assertTrue(checked_reply, 'API/HTML 前 5 页没有可对照的回评')

    def test_html_forum_comment_id_parsing(self):
        page = JmPageTool.parse_html_to_album_comment_page(AdvancedDict({
            'code': '''
                <div class="timeline" data-cid="100">
                    <div class="timeline-left">
                        <a href="/user/test-user">
                            <img class="timeline-avatar" data-userid="200" src="/media/users/999.jpg">
                        </a>
                    </div>
                    <div class="timeline-content">first comment</div>
                    <div class="timeline-ft"><a href="/photo/300/">photo</a></div>
                </div>
                <div class="timeline" data-cid="101">
                    <div class="timeline-left">
                        <a href="/user/other-user"><img src="/media/users/201.jpg"></a>
                    </div>
                    <div class="timeline-content">second comment</div>
                    <div class="timeline-ft"><a href="/album/301/">album</a></div>
                </div>
            ''',
        }), page_number=1)

        self.assertEqual(page.page_number, 1)
        self.assertEqual(page[0].user_id, '200')
        self.assertEqual(page[0].album_id, '300')
        self.assertEqual(page[1].user_id, '201')
        self.assertEqual(page[1].album_id, '301')

    def test_html_favorite_total_uses_labeled_count(self):
        for label, expected_total in [('總數', 6), ('总数', 12)]:
            with self.subTest(label=label):
                html = f'''
                    <style>
                        .modal {{ width : 50px; height: 50px; }}
                        .modal-content {{ inset: 0 / auto 35px; }}
                    </style>
                    <div>{label} : {expected_total}\n / 600</div>
                    <select class="user-select" name="movefolder-fid">
                        <option value="0">全部</option>
                    </select>
                '''

                page = JmPageTool.parse_html_to_favorite_page(html, page_number=1)

                self.assertEqual(page.total, expected_total)
                self.assertEqual(page.page_number, 1)

    def test_get_detail(self):
        client = self.client

        album = client.get_album_detail(400222)
        print(album.id, album.name, album.tags)

        for photo in album[0:3]:
            photo = client.get_photo_detail(photo.photo_id)
            print(photo.id, photo.name)

    def test_cache_result_equal(self):
        cl = self.client
        cases = [
            (123, False, False),
            (123,),
            (123, False, True),
            (123, True, False),
        ]

        ans = None
        for args in cases:
            photo = cl.get_photo_detail(*args)
            if ans is None:
                ans = photo
            else:
                self.assertIsNot(ans, photo)
                self.assertEqual(ans.id, photo.id)
                self.assertEqual(ans.name, photo.name)
                self.assertEqual(ans.tags, photo.tags)

    def test_search_generator(self):
        JmModuleConfig.FLAG_DECODE_URL_WHEN_LOGGING = False

        gen = self.client.search_gen('MANA')
        for i, page in enumerate(gen):
            print(page.total)
            page = gen.send({
                'search_query': 'MANA +无修正',
                'page': 1
            })
            print(page.total)
            break

    def test_cache_level(self):
        cases = [
            (
                True,
                'level_option',
                'level_client',
                CacheRegistry.level_client,
            )
        ]

        def run(arg1, arg2, arg3, arg4):
            op = self.new_option()

            c1 = op.new_jm_client(cache=arg1)
            c2 = op.new_jm_client(cache=arg2)
            c3 = op.new_jm_client(cache=arg3)
            c4 = op.new_jm_client(cache=arg4)
            c5 = op.new_jm_client(cache=False)

            self.assertIs(
                c1.get_cache_dict(),
                c2.get_cache_dict(),
                'clients in the same option level should share a cache dict',
            )
            self.assertIsNot(
                c3.get_cache_dict(),
                c4.get_cache_dict(),
                'clients in the client level should use separate cache dicts',
            )
            self.assertIsNot(
                c1.get_cache_dict(),
                c3.get_cache_dict(),
                'different cache levels should not share a cache dict',
            )
            self.assertIsNone(c5.get_cache_dict(), 'cache=False should disable caching')

        for case in cases:
            run(*case)

    def test_search_advanced(self):
        if not self.client.is_given_type(JmHtmlClient):
            return

        # noinspection PyTypeChecker
        html_cl: JmHtmlClient = self.client
        # 循环获取分页
        for page in html_cl.search_gen(
                search_query='mana',
                page=1,  # 起始页码
                category=JmMagicConstants.CATEGORY_DOUJIN,
                sub_category=JmMagicConstants.SUB_DOUJIN_CG,
                time=JmMagicConstants.TIME_ALL,
        ):
            self.print_page(page)

        print_sep()
        for page in html_cl.categories_filter_gen(
                page=1,  # 起始页码
                category=JmMagicConstants.CATEGORY_DOUJIN,
                sub_category=JmMagicConstants.SUB_DOUJIN_CG,
                time=JmMagicConstants.TIME_ALL,
        ):
            self.print_page(page)
            break

    def test_page_number(self):
        search_page = JmPageTool.parse_api_to_search_page(
            AdvancedDict.wrap({'total': '0', 'content': []}),
            page_number=3,
        )
        favorite_page = JmPageTool.parse_api_to_favorite_page(
            AdvancedDict.wrap({'total': '0', 'list': [], 'folder_list': []}),
            page_number=4,
        )
        album = SimpleNamespace(album_id='123', name='album', tags=['tag'])
        single_album_page = JmSearchPage.wrap_single_album(album, page_number=5)

        self.assertEqual(search_page.page_number, 3)
        self.assertEqual(favorite_page.page_number, 4)
        self.assertEqual(single_album_page.page_number, 5)

        comment_page = JmAlbumCommentPage([], 1, '<html>', {'code': 'ok'}, page_number=6)
        self.assertEqual(comment_page.raw_html, '<html>')
        self.assertEqual(comment_page.raw_data.code, 'ok')
        self.assertEqual(comment_page.page_number, 6)

    def test_page_number_in_sync_generator(self):
        def get_page(page):
            return JmSearchPage([], 100, page)

        generator = JmcomicClient.do_page_iter(None, {}, 1, get_page)

        self.assertEqual(next(generator).page_number, 1)
        self.assertEqual(generator.send({'page': 3}).page_number, 3)

    def test_page_number_in_async_generator(self):
        async def run():
            async def get_page(page):
                return JmSearchPage([], 100, page)

            generator = AsyncJmcomicClient.do_page_iter(None, {}, 1, get_page)

            self.assertEqual((await generator.asend(None)).page_number, 1)
            self.assertEqual((await generator.asend({'page': 3})).page_number, 3)
            await generator.aclose()

        asyncio.run(run())

    @staticmethod
    def print_page(page):
        # 打印page内容
        for aid, atitle in page:
            print(aid, atitle)

    def test_download_cover(self):
        album_id = 123
        self.client.download_album_cover(album_id, f'{self.option.dir_rule.base_dir}/{album_id}.webp')
        self.client.download_album_cover(album_id, f'{self.option.dir_rule.base_dir}/{album_id}_3x4.webp', '_3x4')

    def test_ranking(self):
        """
        Fetches and prints the jmcomic monthly ranking for current month.
        
        This test retrieves the page 1 ranking data from the configured client and writes it to standard output.
        """
        print(self.client.month_ranking(1))

    def test_indexed_entity_slice(self):
        from collections.abc import Sequence
        
        # 获取真实的 JmSearchPage 对象
        page = self.client.search_site("中文", page=1)
        empty_page = self.client.search_site("测试很长的不知道什么鬼123", page=1)

        self.assertTrue(isinstance(page, Sequence))

        # 切片越界应该正常截断，不报错
        items = page[:1000]
        self.assertEqual(len(items), len(page))
        self.assertEqual(page[1000:2000], [])
        
        self.assertEqual(empty_page[:10], [])

        # 负数切片
        if len(page) >= 2:
            rev = page[::-1]
            self.assertEqual(rev[0], page[-1])
            self.assertEqual(rev[-1], page[0])

        if len(page) >= 2:
            self.assertEqual(page[-1], page[len(page) - 1])
            self.assertEqual(page[-2], page[len(page) - 2])
        
        with self.assertRaises(IndexError):
            _ = page[len(page) + 10]
        with self.assertRaises(IndexError):
            _ = page[-(len(page) + 10)]

        res = []
        for i in page:
            res.append(i)
        self.assertEqual(len(res), len(page))

        if len(page) > 0:
            # JmSearchPage overrides __iter__ to yield different elements than __getitem__
            # So we take an item from iter() to test __contains__
            first_item = next(iter(page))
            self.assertTrue(first_item in page)
