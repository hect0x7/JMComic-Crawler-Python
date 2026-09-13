import unittest
from jmcomic import (
    JmAlbumDetail,
    JmcomicText,
    JmApiAdaptTool,
)


class Test_Album_Favorite(unittest.TestCase):

    def test_entity_defaults(self):
        album = JmAlbumDetail(
            album_id=123,
            scramble_id=220980,
            name="测试本子",
            episode_list=[],
            page_count=10,
            pub_date="2026-01-01",
            update_date="2026-01-02",
            likes="100",
            views="1000",
            comment_count=5,
            works=[],
            actors=[],
            authors=["作者A"],
            tags=["标签1"],
        )
        self.assertIs(album.is_favorite, False)
        self.assertIs(album.liked, False)
        self.assertEqual(album.page_count, 10)
        self.assertEqual(album.pub_date, "2026-01-01")

        # Explicit True
        album2 = JmAlbumDetail(
            album_id=123,
            scramble_id=220980,
            name="测试本子",
            episode_list=[],
            page_count=10,
            pub_date="2026-01-01",
            update_date="2026-01-02",
            likes="100",
            views="1000",
            comment_count=5,
            works=[],
            actors=[],
            authors=["作者A"],
            tags=["标签1"],
            is_favorite=True,
            liked=True,
        )
        self.assertIs(album2.is_favorite, True)
        self.assertIs(album2.liked, True)

    def test_html_reflect_is_favorite_and_liked(self):
        # 模拟包含已收藏(btn-primary)和已点赞(style="color:red")的HTML
        html_favorited_and_liked = '''
        <html>
            <span class="number">作品編號：JM1133603</span>
            var scramble_id = 220980;
            <h1 id="book-name">测试本子</h1>
            <h2>叙述：这是一本测试</h2>
            <span class="pagecount">頁數:50</span>
            <span itemprop="datePublished" content="2025-04-22">上架日期 : 2025-04-22</span>
            <span>更新日期 : 2025-04-23</span>
            <span id="albim_likes_1133603">2K</span>
            <span>78K</span>
            <span>次觀看</span>
            <div class="badge" id="total_video_comments">12</div>
            <span itemprop="author" data-type="works"><a href="#">作品A</a></span>
            <span itemprop="author" data-type="actor"><a href="#">人物A</a></span>
            <span itemprop="author" data-type="author"><a href="#">作者A</a></span>
            <span itemprop="genre" data-type="tags"><a href="#">标签A</a></span>
            <a id="album_favorite_1133603" class="btn btn-primary">已收藏</a>
            <a href="#" style="float: right;padding: 5px;" id="love_likes_1133603">
                <i class="glyphicon glyphicon-heart fa-2x" style="color:red" ></i>
            </a>
        </html>
        '''
        album = JmcomicText.analyse_jm_album_html(html_favorited_and_liked)
        self.assertIs(album.is_favorite, True)
        self.assertIs(album.liked, True)
        self.assertEqual(album.page_count, 50)
        self.assertEqual(album.pub_date, "2025-04-22")

        # 模拟未收藏(未带btn-primary)和未点赞(无style="color:red")的HTML
        html_unfavorited_and_unliked = '''
        <html>
            <span class="number">作品編號：JM1133603</span>
            var scramble_id = 220980;
            <h1 id="book-name">测试本子</h1>
            <h2>叙述：这是一本测试</h2>
            <span class="pagecount">頁數:50</span>
            <span itemprop="datePublished" content="2025-04-22">上架日期 : 2025-04-22</span>
            <span>更新日期 : 2025-04-23</span>
            <span id="albim_likes_1133603">2K</span>
            <span>78K</span>
            <span>次觀看</span>
            <div class="badge" id="total_video_comments">12</div>
            <span itemprop="author" data-type="works"><a href="#">作品A</a></span>
            <span itemprop="author" data-type="actor"><a href="#">人物A</a></span>
            <span itemprop="author" data-type="author"><a href="#">作者A</a></span>
            <span itemprop="genre" data-type="tags"><a href="#">标签A</a></span>
            <a id="album_favorite_1133603" class="btn btn-default">收藏</a>
            <a href="#" style="float: right;padding: 5px;" id="love_likes_1133603">
                <i class="glyphicon glyphicon-heart fa-2x" ></i>
            </a>
        </html>
        '''
        album2 = JmcomicText.analyse_jm_album_html(html_unfavorited_and_unliked)
        self.assertIs(album2.is_favorite, False)
        self.assertIs(album2.liked, False)

    def test_api_adapt_album_fields(self):
        api_data = {
            'id': 1133603,
            'name': 'API本子',
            'author': ['测试作者'],
            'total_views': '12345',
            'likes': '678',
            'comment_total': '9',
            'tags': ['Tag1'],
            'works': [],
            'actors': [],
            'related_list': [],
            'series': [],
            'total_photos': 120,
            'addtime': 1745337600,
            'is_favorite': True,
            'liked': True,
            'description': '测试描述',
        }
        album: JmAlbumDetail = JmApiAdaptTool.parse_entity(api_data, JmAlbumDetail)
        self.assertIs(album.is_favorite, True)
        self.assertIs(album.liked, True)
        self.assertEqual(album.page_count, 120)
        self.assertEqual(album.id, '1133603')
        self.assertEqual(album.name, 'API本子')

        # 验证 False 场景
        api_data_false = dict(api_data)
        api_data_false['is_favorite'] = False
        api_data_false['liked'] = False
        album_false = JmApiAdaptTool.parse_entity(api_data_false, JmAlbumDetail)
        self.assertIs(album_false.is_favorite, False)
        self.assertIs(album_false.liked, False)
