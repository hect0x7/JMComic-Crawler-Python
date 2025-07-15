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
        self.assertRaises(
            MissingAlbumPhotoException,
            self.client.get_album_detail,
            '0'
        )

    def test_detail_property_list(self):
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
                'order_by': JmMagicConstants.ORDER_BY_LIKE,
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
                ans = id(photo)
            else:
                self.assertEqual(ans, id(photo))

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
        def get(cl):
            return cl.get_album_detail('123')

        def assertEqual(first_cl, second_cl, msg):
            self.assertEqual(
                get(first_cl),
                get(second_cl),
                msg,
            )

        def assertNotEqual(first_cl, second_cl, msg):
            return self.assertNotEqual(
                get(first_cl),
                get(second_cl),
                msg,
            )

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

            # c1 == c2
            # c3 == c4
            # c1 != c3
            assertEqual(c1, c2, 'equals in same option level')
            assertNotEqual(c3, c4, 'not equals in client level')
            assertNotEqual(c1, c3, 'not equals in different level')

            # c5 != c1, c2, c3, c4
            obj = get(c5)
            self.assertNotEqual(obj, get(c1))
            self.assertNotEqual(obj, get(c3))

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

    @staticmethod
    def print_page(page):
        # 打印page内容
        for aid, atitle in page:
            print(aid, atitle)
