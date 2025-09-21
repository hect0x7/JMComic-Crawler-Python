from PIL import Image

from .jm_exception import *


class JmcomicText:
    pattern_jm_domain = compile(r'https://([\w.-]+)')
    pattern_jm_pa_id = [
        (compile(r'(photos?|albums?)/(\d+)'), 2),
        (compile(r'id=(\d+)'), 1),
    ]
    pattern_html_jm_pub_domain = compile(r'[\w-]+\.\w+/?\w+')

    pattern_html_photo_photo_id = compile(r'<meta property="og:url" content=".*?/photo/(\d+)/?.*?">')
    pattern_html_photo_scramble_id = compile(r'var scramble_id = (\d+);')
    pattern_html_photo_name = compile(r'<title>([\s\S]*?)\|.*</title>')
    # pattern_html_photo_data_original_list = compile(r'data-original="(.*?)" id="album_photo_.+?"')
    pattern_html_photo_data_original_domain = compile(r'src="https://(.*?)/media/albums/blank')
    pattern_html_photo_data_original_0 = compile(r'data-original="(.*?)"[^>]*?id="album_photo[^>]*?data-page="0"')
    pattern_html_photo_tags = compile(r'<meta name="keywords"[\s\S]*?content="(.*?)"')
    pattern_html_photo_series_id = compile(r'var series_id = (\d+);')
    pattern_html_photo_sort = compile(r'var sort = (\d+);')
    pattern_html_photo_page_arr = compile(r'var page_arr = (.*?);')

    pattern_html_b64_decode_content = compile(r'const html = base64DecodeUtf8\("(.*?)"\)')
    pattern_html_album_album_id = compile(r'<span class="number">.*?：JM(\d+)</span>')
    pattern_html_album_scramble_id = compile(r'var scramble_id = (\d+);')
    pattern_html_album_name = compile(r'id="book-name"[^>]*?>([\s\S]*?)<')
    pattern_html_album_description = compile(r'叙述：([\s\S]*?)</h2>')
    pattern_html_album_episode_list = compile(r'data-album="(\d+)"[^>]*>[\s\S]*?第(\d+)[话話]([\s\S]*?)<[\s\S]*?>')
    pattern_html_album_page_count = compile(r'<span class="pagecount">.*?:(\d+)</span>')
    pattern_html_album_pub_date = compile(r'>上架日期 : (.*?)</span>')
    pattern_html_album_update_date = compile(r'>更新日期 : (.*?)</span>')
    pattern_html_tag_a = compile(r'<a[^>]*?>\s*(\S*)\s*</a>')
    # 作品
    pattern_html_album_works = [
        compile(r'<span itemprop="author" data-type="works">([\s\S]*?)</span>'),
        pattern_html_tag_a,
    ]
    # 登場人物
    pattern_html_album_actors = [
        compile(r'<span itemprop="author" data-type="actor">([\s\S]*?)</span>'),
        pattern_html_tag_a,
    ]
    # 标签
    pattern_html_album_tags = [
        compile(r'<span itemprop="genre" data-type="tags">([\s\S]*?)</span>'),
        pattern_html_tag_a,
    ]
    # 作者
    pattern_html_album_authors = [
        compile(r'<span itemprop="author" data-type="author">([\s\S]*?)</span>'),
        pattern_html_tag_a,
    ]
    # 點擊喜歡
    pattern_html_album_likes = compile(r'<span id="albim_likes_\d+">(.*?)</span>')
    # 觀看
    pattern_html_album_views = compile(r'<span>(.*?)</span>\n *<span>(次觀看|观看次数|次观看次数)</span>')
    # 評論(div)
    pattern_html_album_comment_count = compile(r'<div class="badge"[^>]*?id="total_video_comments">(\d+)</div>'), 0

    # 提取接口返回值信息
    pattern_ajax_favorite_msg = compile(r'</button>(.*?)</div>')
    # 提取api接口返回值里的json，防止返回值里有无关日志导致json解析报错
    pattern_api_response_json_object = compile(r'\{[\s\S]*?}')

    @classmethod
    def parse_to_jm_domain(cls, text: str):
        if text.startswith(JmModuleConfig.PROT):
            return cls.pattern_jm_domain.search(text)[1]

        return text

    @classmethod
    def parse_to_jm_id(cls, text) -> str:
        if isinstance(text, int):
            return str(text)

        ExceptionTool.require_true(isinstance(text, str), f"无法解析jm车号, 参数类型为: {type(text)}")

        # 43210
        if text.isdigit():
            return text

        # Jm43210
        ExceptionTool.require_true(len(text) >= 2, f"无法解析jm车号, 文本太短: {text}")

        # text: JM12341
        c0 = text[0]
        c1 = text[1]
        if (c0 == 'J' or c0 == 'j') and (c1 == 'M' or c1 == 'm'):
            # JM123456
            return text[2:]
        else:
            # https://xxx/photo/412038
            # https://xxx/album/?id=412038
            for p, i in cls.pattern_jm_pa_id:
                match = p.search(text)
                if match is not None:
                    return match[i]

            ExceptionTool.raises(f"无法解析jm车号, 文本为: {text}")

    @classmethod
    def analyse_jm_pub_html(cls, html: str, domain_keyword=('jm', 'comic')) -> List[str]:
        domain_ls = cls.pattern_html_jm_pub_domain.findall(html)

        return list(filter(
            lambda domain: any(kw in domain for kw in domain_keyword),
            domain_ls
        ))

    @classmethod
    def parse_jm_base64_html(cls, resp_text: str) -> str:
        from base64 import b64decode
        html_b64 = PatternTool.match_or_default(resp_text, cls.pattern_html_b64_decode_content, None)
        if html_b64 is None:
            return resp_text
        html = b64decode(html_b64).decode()
        return html

    @classmethod
    def analyse_jm_photo_html(cls, html: str) -> JmPhotoDetail:
        return cls.reflect_new_instance(
            html,
            "pattern_html_photo_",
            JmModuleConfig.photo_class()
        )

    @classmethod
    def analyse_jm_album_html(cls, html: str) -> JmAlbumDetail:
        return cls.reflect_new_instance(
            cls.parse_jm_base64_html(html),
            "pattern_html_album_",
            JmModuleConfig.album_class()
        )

    @classmethod
    def reflect_new_instance(cls, html: str, cls_field_prefix: str, clazz: type):

        def match_field(field_name: str, pattern: Union[Pattern, List[Pattern]], text):

            if isinstance(pattern, list):
                # 如果是 pattern 是 List[re.Pattern]，
                # 取最后一个 pattern 用于 match field，
                # 其他的 pattern 用来给文本缩小范围（相当于多次正则匹配）
                last_pattern = pattern[len(pattern) - 1]
                # 缩小文本
                for i in range(0, len(pattern) - 1):
                    match: Match = pattern[i].search(text)
                    if match is None:
                        return None
                    text = match[0]

                return last_pattern.findall(text)

            if field_name.endswith("_list"):
                return pattern.findall(text)
            else:
                match = pattern.search(text)
                if match is not None:
                    return match[1]
                return None

        field_dict = {}
        pattern_name: str
        for pattern_name, pattern in cls.__dict__.items():
            if not pattern_name.startswith(cls_field_prefix):
                continue

            # 支持如果不匹配，使用默认值
            if isinstance(pattern, tuple):
                pattern, default = pattern
            else:
                default = None

            # 获取字段名和值
            field_name = pattern_name[pattern_name.index(cls_field_prefix) + len(cls_field_prefix):]
            field_value = match_field(field_name, pattern, html)

            if field_value is None:
                if default is None:
                    ExceptionTool.raises_regex(
                        f"文本没有匹配上字段：字段名为'{field_name}'，pattern: [{pattern}]"
                        + (f"\n响应文本=[{html}]" if len(html) < 200 else
                           f'响应文本过长(len={len(html)})，不打印'
                           ),
                        html=html,
                        pattern=pattern,
                    )
                else:
                    field_value = default

            # 保存字段
            field_dict[field_name] = field_value

        return clazz(**field_dict)

    @classmethod
    def format_url(cls, path, domain):
        ExceptionTool.require_true(isinstance(domain, str) and len(domain) != 0, '域名为空')

        if domain.startswith(JmModuleConfig.PROT):
            return f'{domain}{path}'

        return f'{JmModuleConfig.PROT}{domain}{path}'

    @classmethod
    def format_album_url(cls, aid, domain='18comic.vip'):
        """
        把album_id变为可访问的URL，方便print打印后用浏览器访问
        """
        return cls.format_url(f'/album/{aid}/', domain)

    class DSLReplacer:

        def __init__(self):
            self.dsl_dict: Dict[Pattern, Callable[[Match], str]] = {}

        def parse_dsl_text(self, text) -> str:
            for pattern, replacer in self.dsl_dict.items():
                text = pattern.sub(replacer, text)
            return text

        def add_dsl_and_replacer(self, dsl: str, replacer: Callable[[Match], str]):
            pattern = compile(dsl)
            self.dsl_dict[pattern] = replacer

    @classmethod
    def match_os_env(cls, match: Match) -> str:
        name = match[1]
        value = os.getenv(name, None)
        ExceptionTool.require_true(value is not None, f'未配置环境变量: {name}')
        return value

    dsl_replacer = DSLReplacer()

    @classmethod
    def parse_to_abspath(cls, dsl_text: str) -> str:
        return os.path.abspath(cls.parse_dsl_text(dsl_text))

    @classmethod
    def parse_dsl_text(cls, dsl_text: str) -> str:
        return cls.dsl_replacer.parse_dsl_text(dsl_text)

    bracket_map = {'(': ')',
                   '[': ']',
                   '【': '】',
                   '（': '）',
                   }

    @classmethod
    def parse_orig_album_name(cls, name: str, default=None):
        word_list = cls.tokenize(name)

        for word in word_list:
            if word[0] in cls.bracket_map:
                continue

            return word

        return default

    @classmethod
    def tokenize(cls, title: str) -> List[str]:
        """
        繞道#2 [暴碧漢化組] [えーすけ（123）] よりみち#2 (COMIC 快樂天 2024年1月號) [中國翻譯] [DL版]
        :return: ['繞道#2', '[暴碧漢化組]', '[えーすけ（123）]', 'よりみち#2', '(COMIC 快樂天 2024年1月號)', '[中國翻譯]', '[DL版]']
        """
        title = title.strip()
        ret = []
        bracket_map = cls.bracket_map

        char_list = []
        i = 0
        length = len(title)

        def add(w=None):
            if w is None:
                w = ''.join(char_list).strip()

            if w == '':
                return

            ret.append(w)
            char_list.clear()

        def find_right_pair(left_pair, i):
            stack = [left_pair]
            j = i + 1

            while j < length and len(stack) != 0:
                c = title[j]
                if c in bracket_map:
                    stack.append(c)
                elif c == bracket_map[stack[-1]]:
                    stack.pop()

                j += 1

            if len(stack) == 0:
                return j
            else:
                return -1

        while i < length:
            c = title[i]

            if c in bracket_map:
                # 上一个单词结束
                add()
                # 定位右括号
                j = find_right_pair(c, i)
                if j == -1:
                    # 括号未闭合
                    char_list.append(c)
                    i += 1
                    continue
                # 整个括号的单词结束
                add(title[i:j])
                # 移动指针
                i = j
            else:
                char_list.append(c)
                i += 1

        add()
        return ret

    @classmethod
    def to_zh_cn(cls, s):
        import zhconv
        return zhconv.convert(s, 'zh-cn')

    @classmethod
    def try_mkdir(cls, save_dir: str):
        try:
            mkdir_if_not_exists(save_dir)
        except OSError as e:
            if e.errno == 36:
                # 目录名过长
                limit = JmModuleConfig.VAR_FILE_NAME_LENGTH_LIMIT
                jm_log('error', f'目录名过长，无法创建目录，强制缩短到{limit}个字符并重试')
                save_dir = save_dir[0:limit]
                return cls.try_mkdir(save_dir)
            raise e
        return save_dir

    # noinspection PyTypeChecker
    @classmethod
    def try_parse_json_object(cls, resp_text: str) -> dict:
        import json
        text = resp_text.strip()
        if text.startswith('{') and text.endswith('}'):
            # fast case
            return json.loads(text)

        for match in cls.pattern_api_response_json_object.finditer(text):
            try:
                return json.loads(match.group(0))
            except Exception as e:
                jm_log('parse_json_object.error', e)

        raise AssertionError(f'未解析出json数据: {cls.limit_text(resp_text, 200)}')

    @classmethod
    def limit_text(cls, text: str, limit: int) -> str:
        length = len(text)
        return text if length <= limit else (text[:limit] + f'...({length - limit}')

    @classmethod
    def get_album_cover_url(cls,
                            album_id: Union[str, int],
                            image_domain: Optional[str] = None,
                            size: str = '',
                            ) -> str:
        """
        根据本子id生成封面url

        :param album_id: 本子id
        :param image_domain: 图片cdn域名（可传入裸域或含协议的域名）
        :param size: 尺寸后缀，例如搜索列表页会使用 size="_3x4" 的封面图
        """
        if image_domain is None:
            import random
            image_domain = random.choice(JmModuleConfig.DOMAIN_IMAGE_LIST)

        path = f'/media/albums/{cls.parse_to_jm_id(album_id)}{size}.jpg'
        return cls.format_url(path, image_domain)


# 支持dsl: #{???} -> os.getenv(???)
JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', JmcomicText.match_os_env)


class PatternTool:

    @classmethod
    def match_or_default(cls, html: str, pattern: Pattern, default):
        match = pattern.search(html)
        return default if match is None else match[1]

    @classmethod
    def require_match(cls, html: str, pattern: Pattern, msg, rindex=1):
        match = pattern.search(html)
        if match is not None:
            return match[rindex] if rindex is not None else match

        ExceptionTool.raises_regex(
            msg,
            html=html,
            pattern=pattern,
        )

    @classmethod
    def require_not_match(cls, html: str, pattern: Pattern, *, msg_func):
        match = pattern.search(html)
        if match is None:
            return

        ExceptionTool.raises_regex(
            msg_func(match),
            html=html,
            pattern=pattern,
        )


class JmPageTool:
    # 用来缩减html的长度
    pattern_html_search_shorten_for = compile(r'<div class="well well-sm">([\s\S]*)<div class="row">')

    # 用来提取搜索页面的album的信息
    pattern_html_search_album_info_list = compile(
        r'<a href="/album/(\d+)/[\s\S]*?title="(.*?)"([\s\S]*?)<div class="title-truncate tags .*>([\s\S]*?)</div>'
    )

    # 用来提取分类页面的album的信息
    pattern_html_category_album_info_list = compile(
        r'<a href="/album/(\d+)/[^>]*>[^>]*?'
        r'title="(.*?)"[^>]*>[ \n]*</a>[ \n]*'
        r'<div class="label-loveicon">([\s\S]*?)'
        r'<div class="clearfix">'
    )

    # 用来查找tag列表
    pattern_html_search_tags = compile(r'<a[^>]*?>(.*?)</a>')

    # 查找错误，例如 [错误，關鍵字過短，請至少輸入兩個字以上。]
    pattern_html_search_error = compile(r'<fieldset>\n<legend>(.*?)</legend>\n<div class=.*?>\n(.*?)\n</div>\n</fieldset>')

    pattern_html_search_total = compile(r'class="text-white">(\d+)</span> A漫.'), 0

    # 收藏页面的本子结果
    pattern_html_favorite_content = compile(
        r'<div id="favorites_album_[^>]*?>[\s\S]*?'
        r'<a href="/album/(\d+)/[^"]*">[\s\S]*?'
        r'<div class="video-title title-truncate">([^<]*?)'
        r'</div>'
    )

    # 收藏夹的收藏总数
    pattern_html_favorite_total = compile(r' : (\d+)[^/]*/\D*(\d+)')

    # 所有的收藏夹
    pattern_html_favorite_folder_list = [
        compile(r'<select class="user-select" name="movefolder-fid">([\s\S]*)</select>'),
        compile(r'<option value="(\d+)">([^<]*?)</option>')
    ]

    @classmethod
    def parse_html_to_search_page(cls, html: str) -> JmSearchPage:
        # 1. 检查是否失败
        PatternTool.require_not_match(
            html,
            cls.pattern_html_search_error,
            msg_func=lambda match: '{}: {}'.format(match[1], match[2])
        )

        # 2. 缩小文本范围
        html = PatternTool.require_match(
            html,
            cls.pattern_html_search_shorten_for,
            msg='未匹配到搜索结果',
        )

        # 3. 提取结果
        content = []  # content这个名字来源于api版搜索返回值
        total = int(PatternTool.match_or_default(html, *cls.pattern_html_search_total))  # 总结果数

        album_info_list = cls.pattern_html_search_album_info_list.findall(html)

        for (album_id, title, _label_category_text, tag_text) in album_info_list:
            # 从label_category_text中可以解析出label-category和label-sub
            # 这里不作解析，因为没什么用...
            tags = cls.pattern_html_search_tags.findall(tag_text)
            content.append((
                album_id, dict(name=title, tags=tags)  # 改成name是为了兼容 parse_api_resp_to_page
            ))

        return JmSearchPage(content, total)

    @classmethod
    def parse_html_to_category_page(cls, html: str) -> JmSearchPage:
        content = []
        total = int(PatternTool.match_or_default(html, *cls.pattern_html_search_total))

        album_info_list = cls.pattern_html_category_album_info_list.findall(html)

        for (album_id, title, tag_text) in album_info_list:
            tags = cls.pattern_html_search_tags.findall(tag_text)
            content.append((
                album_id, dict(name=title, tags=tags)  # 改成name是为了兼容 parse_api_resp_to_page
            ))

        return JmSearchPage(content, total)

    @classmethod
    def parse_html_to_favorite_page(cls, html: str) -> JmFavoritePage:
        total = int(PatternTool.require_match(
            html,
            cls.pattern_html_favorite_total,
            '未匹配到收藏夹的本子总数',
        ))

        # 收藏夹的本子结果
        content = cls.pattern_html_favorite_content.findall(html)
        content = [
            (aid, {'name': atitle})
            for aid, atitle in content
        ]

        # 匹配收藏夹列表
        p1, p2 = cls.pattern_html_favorite_folder_list
        folder_list_text = PatternTool.require_match(html, p1, '未匹配到收藏夹列表')
        folder_list_raw = p2.findall(folder_list_text)
        folder_list = [{'name': fname, 'FID': fid} for fid, fname in folder_list_raw]

        return JmFavoritePage(content, folder_list, total)

    @classmethod
    def parse_api_to_search_page(cls, data: AdvancedDict) -> JmSearchPage:
        """
        model_data: {
          "search_query": "MANA",
          "total": "177",
          "content": [
            {
              "id": "441923",
              "author": "MANA",
              "description": "",
              "name": "[MANA] 神里绫华5",
              "image": "",
              "category": {
                "id": "1",
                "title": "同人"
              },
              "category_sub": {
                "id": "1",
                "title": "同人"
              }
            }
          ]
        }
        """
        total: int = int(data.total or 0)  # 2024.1.5 data.total可能为None
        content = cls.adapt_content(data.content)
        return JmSearchPage(content, total)

    @classmethod
    def parse_api_to_favorite_page(cls, data: AdvancedDict) -> JmFavoritePage:
        """
        {
          "list": [
            {
              "id": "363859",
              "author": "紺菓",
              "description": "",
              "name": "[無邪氣漢化組] (C99) [紺色果實 (紺菓)] サレンの樂しい夢 (プリンセスコネクト!Re:Dive) [中國翻譯]",
              "latest_ep": null,
              "latest_ep_aid": null,
              "image": "",
              "category": {
                "id": "1",
                "title": "同人"
              },
              "category_sub": {
                "id": "1",
                "title": "同人"
              }
            }
          ],
          "folder_list": [
            {
              "0": "123",
              "FID": "123",
              "1": "456",
              "UID": "456",
              "2": "收藏夹名",
              "name": "收藏夹名"
            }
          ],
          "total": "87",
          "count": 20
        }
        """
        total: int = int(data.total)
        # count: int = int(data.count)
        content = cls.adapt_content(data.list)
        folder_list = data.get('folder_list', [])

        return JmFavoritePage(content, folder_list, total)

    @classmethod
    def adapt_content(cls, content):
        def adapt_item(item: AdvancedDict):
            item: dict = item.src_dict
            item.setdefault('tags', [])
            return item

        content = [
            (item.id, adapt_item(item)) for item in content
        ]
        return content


class JmApiAdaptTool:
    """
    本类负责把移动端的api返回值，适配为标准的实体类

    # album
    {
      "id": 123,
      "name": "[狗野叉漢化]",
      "author": [
        "AREA188"
      ],
      "images": [
        "00004.webp"
      ],
      "description": null,
      "total_views": "41314",
      "likes": "918",
      "series": [],
      "series_id": "0",
      "comment_total": "5",
      "tags": [
        "全彩",
        "中文"
      ],
      "works": [],
      "actors": [],
      "related_list": [
        {
          "id": "333718",
          "author": "been",
          "description": "",
          "name": "[been]The illusion of lies（1）[中國語][無修正][全彩]",
          "image": ""
        }
      ],
      "liked": false,
      "is_favorite": false
    }

    # photo
    {
      "id": 413446,
      "series": [
        {
          "id": "487043",
          "name": "第48話",
          "sort": "48"
        }
      ],
      "tags": "慾望 調教 NTL 地鐵 戲劇",
      "name": "癡漢成癮-第2話",
      "images": [
        "00047.webp"
      ],
      "series_id": "400222",
      "is_favorite": false,
      "liked": false
    }
    """
    field_adapter = {
        JmAlbumDetail: [
            'likes',
            'tags',
            'works',
            'actors',
            'related_list',
            'name',
            'description',
            ('id', 'album_id'),
            ('author', 'authors'),
            ('total_views', 'views'),
            ('comment_total', 'comment_count'),
        ],
        JmPhotoDetail: [
            'name',
            'series_id',
            'tags',
            ('id', 'photo_id'),
            ('images', 'page_arr'),

        ]
    }

    @classmethod
    def parse_entity(cls, data: dict, clazz: type):
        adapter = cls.get_adapter(clazz)

        fields = {}
        for k in adapter:
            if isinstance(k, str):
                v = data[k]
                fields[k] = v
            elif isinstance(k, tuple):
                k, rename_k = k
                v = data[k]
                fields[rename_k] = v

        if issubclass(clazz, JmAlbumDetail):
            cls.post_adapt_album(data, clazz, fields)
        else:
            cls.post_adapt_photo(data, clazz, fields)

        return clazz(**fields)

    @classmethod
    def get_adapter(cls, clazz: type):
        for k, v in cls.field_adapter.items():
            if issubclass(clazz, k):
                return v

        ExceptionTool.raises(f'不支持的类型: {clazz}')

    @classmethod
    def post_adapt_album(cls, data: dict, _clazz: type, fields: dict):
        series = data['series']
        episode_list = []
        for chapter in series:
            chapter = AdvancedDict(chapter)
            # photo_id, photo_index, photo_title, photo_pub_date
            episode_list.append(
                (chapter.id, chapter.sort, chapter.name)
            )
        fields['episode_list'] = episode_list
        for it in 'scramble_id', 'page_count', 'pub_date', 'update_date':
            fields[it] = '0'

    @classmethod
    def post_adapt_photo(cls, data: dict, _clazz: type, fields: dict):
        # 1. 获取sort字段，如果data['series']中没有，使用默认值1
        sort = 1
        series: list = data['series']  # series中的sort从1开始
        for chapter in series:
            chapter = AdvancedDict(chapter)
            if int(chapter.id) == int(data['id']):
                sort = chapter.sort
                break

        fields['sort'] = sort
        import random
        fields['data_original_domain'] = random.choice(JmModuleConfig.DOMAIN_IMAGE_LIST)


class JmImageTool:

    @classmethod
    def save_resp_img(cls, resp: Any, filepath: str, need_convert=True):
        """
        接收HTTP响应对象，将其保存到图片文件.
        如果需要改变图片的文件格式，比如 .jpg → .png，则需要指定参数 neet_convert=True.
        如果不需要改变图片的文件格式，使用 need_convert=False，可以跳过PIL解析图片，效率更高.

        :param resp: JmImageResp
        :param filepath: 图片文件路径
        :param need_convert: 是否转换图片
        """
        if need_convert is False:
            cls.save_directly(resp, filepath)
        else:
            cls.save_image(cls.open_image(resp.content), filepath)

    @classmethod
    def save_image(cls, image: Image, filepath: str):
        """
        保存图片

        :param image: PIL.Image对象
        :param filepath: 保存文件路径
        """
        image.save(filepath)

    @classmethod
    def save_directly(cls, resp, filepath):
        from common import save_resp_content
        save_resp_content(resp, filepath)

    @classmethod
    def decode_and_save(cls,
                        num: int,
                        img_src: Image,
                        decoded_save_path: str
                        ) -> None:
        """
        解密图片并保存
        :param num: 分割数，可以用 cls.calculate_segmentation_num 计算
        :param img_src: 原始图片
        :param decoded_save_path: 解密图片的保存路径
        """

        # 无需解密，直接保存
        if num == 0:
            cls.save_image(img_src, decoded_save_path)
            return

        import math
        w, h = img_src.size

        # 创建新的解密图片
        img_decode = Image.new("RGB", (w, h))
        over = h % num
        for i in range(num):
            move = math.floor(h / num)
            y_src = h - (move * (i + 1)) - over
            y_dst = move * i

            if i == 0:
                move += over
            else:
                y_dst += over

            img_decode.paste(
                img_src.crop((
                    0, y_src,
                    w, y_src + move
                )),
                (
                    0, y_dst,
                    w, y_dst + move
                )
            )

            # save every step result
            # cls.save_image(img_decode, change_file_name(
            #     decoded_save_path,
            #     f'{of_file_name(decoded_save_path, trim_suffix=True)}_{i}{of_file_suffix(decoded_save_path)}'
            # ))

        # 保存到新的解密文件
        cls.save_image(img_decode, decoded_save_path)

    @classmethod
    def open_image(cls, fp: Union[str, bytes]):
        from io import BytesIO
        fp = fp if isinstance(fp, str) else BytesIO(fp)
        return Image.open(fp)

    @classmethod
    def get_num(cls, scramble_id, aid, filename: str) -> int:
        """
        获得图片分割数
        """

        scramble_id = int(scramble_id)
        aid = int(aid)

        if aid < scramble_id:
            return 0
        elif aid < JmMagicConstants.SCRAMBLE_268850:
            return 10
        else:
            import hashlib
            x = 10 if aid < JmMagicConstants.SCRAMBLE_421926 else 8
            s = f"{aid}{filename}"  # 拼接
            s = s.encode()
            s = hashlib.md5(s).hexdigest()
            num = ord(s[-1])
            num %= x
            num = num * 2 + 2
            return num

    @classmethod
    def get_num_by_url(cls, scramble_id, url) -> int:
        """
        获得图片分割数
        """
        return cls.get_num(
            scramble_id,
            aid=JmcomicText.parse_to_jm_id(url),
            filename=of_file_name(url, True),
        )

    @classmethod
    def get_num_by_detail(cls, detail: JmImageDetail) -> int:
        """
        获得图片分割数
        """
        return cls.get_num(detail.scramble_id, detail.aid, detail.img_file_name)


class JmCryptoTool:
    """
    禁漫加解密相关逻辑
    """

    @classmethod
    def token_and_tokenparam(cls,
                             ts,
                             ver=None,
                             secret=None,
                             ):
        """
        计算禁漫接口的请求headers的token和tokenparam

        :param ts: 时间戳
        :param ver: app版本
        :param secret: 密钥
        :return (token, tokenparam)
        """

        if ver is None:
            ver = JmMagicConstants.APP_VERSION

        if secret is None:
            secret = JmMagicConstants.APP_TOKEN_SECRET

        # tokenparam: 1700566805,1.6.3
        tokenparam = '{},{}'.format(ts, ver)

        # token: 81498a20feea7fbb7149c637e49702e3
        token = cls.md5hex(f'{ts}{secret}')

        return token, tokenparam

    @classmethod
    def decode_resp_data(cls,
                         data: str,
                         ts,
                         secret=None,
                         ) -> str:
        """
        解密接口返回值

        :param data: resp.json()['data']
        :param ts: 时间戳
        :param secret: 密钥
        :return: json格式的字符串
        """
        if secret is None:
            secret = JmMagicConstants.APP_DATA_SECRET

        # 1. base64解码
        import base64
        data_b64 = base64.b64decode(data)

        # 2. AES-ECB解密
        key = cls.md5hex(f'{ts}{secret}').encode('utf-8')
        from Crypto.Cipher import AES
        data_aes = AES.new(key, AES.MODE_ECB).decrypt(data_b64)

        # 3. 移除末尾的padding
        data = data_aes[:-data_aes[-1]]

        # 4. 解码为字符串 (json)
        res = data.decode('utf-8')

        return res

    @classmethod
    def md5hex(cls, key: str):
        ExceptionTool.require_true(isinstance(key, str), 'key参数需为字符串')

        from hashlib import md5
        return md5(key.encode("utf-8")).hexdigest()
