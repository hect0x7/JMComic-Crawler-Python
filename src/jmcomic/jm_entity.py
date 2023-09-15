from common import *

from .jm_config import *


class JmBaseEntity:

    def save_to_file(self, filepath):
        from common import PackerUtil
        PackerUtil.pack(self, filepath)


class IndexedEntity:
    def getindex(self, index: int):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __getitem__(self, item) -> Any:
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop or len(self)
            step = item.step or 1
            return [self.getindex(index) for index in range(start, stop, step)]

        elif isinstance(item, int):
            return self.getindex(item)

        else:
            raise TypeError(f"Invalid item type for {self.__class__}")

    def __iter__(self):
        for index in range(len(self)):
            yield self.getindex(index)


class DetailEntity(JmBaseEntity, IndexedEntity):

    @property
    def id(self) -> str:
        raise NotImplementedError

    @property
    def title(self) -> str:
        return getattr(self, 'name')

    def __str__(self):
        return f'{self.__class__.__name__}({self.id}-{self.title})'

    @classmethod
    def __alias__(cls):
        # "JmAlbumDetail" -> "album" (本子)
        # "JmPhotoDetail" -> "photo" (章节)
        cls_name = cls.__name__
        return cls_name[cls_name.index("m") + 1: cls_name.rfind("Detail")].lower()


class JmImageDetail(JmBaseEntity):

    def __init__(self,
                 aid,
                 scramble_id,
                 img_url,
                 img_file_name,
                 img_file_suffix,
                 from_photo=None,
                 query_params=None,
                 index=-1,
                 ) -> None:
        self.aid: str = aid
        self.scramble_id: str = scramble_id
        self.img_url: str = img_url
        self.img_file_name: str = img_file_name
        self.img_file_suffix: str = img_file_suffix

        self.from_photo: Optional[JmPhotoDetail] = from_photo
        self.query_params: StrNone = query_params
        self.is_exists: bool = False
        self.index = index

    @property
    def filename(self) -> str:
        return self.img_file_name + self.img_file_suffix

    @property
    def download_url(self) -> str:
        """
        图片的下载路径
        与 self.img_url 的唯一不同是，在最后会带上 ?{self.query_params}
        @return:
        """
        if self.query_params is None:
            return self.img_url

        return f'{self.img_url}?{self.query_params}'

    @classmethod
    def of(cls,
           photo_id: str,
           scramble_id: str,
           data_original: str,
           from_photo=None,
           query_params=None,
           index=-1,
           ) -> 'JmImageDetail':
        """
        该方法用于创建 JmImageDetail 对象
        """

        # /xxx.yyy
        # ↑   ↑
        # x   y
        x = data_original.rfind('/')
        y = data_original.rfind('.')

        return JmImageDetail(
            aid=photo_id,
            scramble_id=scramble_id,
            img_url=data_original,
            img_file_name=data_original[x + 1:y],
            img_file_suffix=data_original[y:],
            from_photo=from_photo,
            query_params=query_params,
            index=index,
        )

    """
    below help for debug method 
    """

    @property
    def tag(self) -> str:
        return f'{self.aid}/{self.filename} [{self.index + 1}/{len(self.from_photo)}]'


class JmPhotoDetail(DetailEntity):

    def __init__(self,
                 photo_id,
                 scramble_id,
                 name,
                 keywords,
                 series_id,
                 sort,
                 page_arr=None,
                 data_original_domain=None,
                 data_original_0=None,
                 author=None,
                 from_album=None,
                 ):
        self.photo_id: str = photo_id
        self.scramble_id: str = scramble_id
        self.name: str = str(name).strip()
        self.sort: int = int(sort)
        self._keywords: str = keywords
        self._series_id: int = int(series_id)

        self._author: StrNone = author
        self.from_album: Optional[JmAlbumDetail] = from_album
        self.index = self.album_index

        # 下面的属性和图片url有关
        if isinstance(page_arr, str):
            import json
            page_arr = json.loads(page_arr)

        # page_arr存放了该photo的所有图片文件名 img_name
        self.page_arr: List[str] = page_arr
        # 图片的cdn域名
        self.data_original_domain: StrNone = data_original_domain
        # 第一张图的URL
        self.data_original_0 = data_original_0

        # 2023-07-14
        # 禁漫的图片url加上了一个参数v，如果没有带上这个参数v，图片会返回空数据
        # 参数v的特点：
        # 1. 值似乎是该photo的更新时间的时间戳，因此所有图片都使用同一个值
        # 2. 值目前在网页端只在photo页面的图片标签的data-original属性出现
        # 这里的模拟思路是，获取到第一个图片标签的data-original，
        # 取出其query参数 → self.data_original_query_params, 该值未来会传递给 JmImageDetail
        self.data_original_query_params = self.get_data_original_query_params(data_original_0)

    @property
    def is_single_album(self) -> bool:
        return self._series_id == 0

    @property
    def tags(self) -> List[str]:
        if self.from_album is not None:
            return self.from_album.tags

        return self._keywords.split(',')

    @property
    def indextitle(self):
        return f'第{self.album_index}話 {self.name}'

    @property
    def album_id(self) -> str:
        return self.photo_id if self.is_single_album else str(self._series_id)

    @property
    def album_index(self) -> int:
        """
        返回这个章节在本子中的序号，从1开始
        """

        # 如果是单章本子，JM给的sort为2。
        # 这里返回1比较符合语义定义
        if self.is_single_album and self.sort == 2:
            return 1

        return self.sort

    @property
    def author(self) -> str:
        # 优先使用 from_album
        if self.from_album is not None:
            return self.from_album.author

        if self._author is not None and self._author != '':
            return self._author.strip()

        # 使用默认
        return JmModuleConfig.default_author

    def create_image_detail(self, index) -> JmImageDetail:
        # 校验参数
        length = len(self.page_arr)
        if index >= length:
            raise JmModuleConfig.exception(f'创建JmImageDetail失败，{index} >= {length}')

        data_original = self.get_img_data_original(self.page_arr[index])

        return JmModuleConfig.image_class().of(
            self.photo_id,
            self.scramble_id,
            data_original,
            from_photo=self,
            query_params=self.data_original_query_params,
            index=index,
        )

    def get_img_data_original(self, img_name: str) -> str:
        """
        根据图片名，生成图片的完整请求路径 URL
        例如：img_name = 01111.webp
        返回：https://cdn-msp2.18comic.org/media/photos/147643/01111.webp
        """
        data_original_domain = self.data_original_domain
        if data_original_domain is None:
            raise JmModuleConfig.exception(f'图片域名为空: {self.__dict__}')

        return f'https://{data_original_domain}/media/photos/{self.photo_id}/{img_name}'

    # noinspection PyMethodMayBeStatic
    def get_data_original_query_params(self, data_original_0: StrNone) -> str:
        if data_original_0 is None:
            return f'v={time_stamp()}'

        index = data_original_0.rfind('?')
        if index == -1:
            return f'v={time_stamp()}'

        return data_original_0[index + 1:]

    @property
    def id(self):
        return self.photo_id

    def getindex(self, index) -> JmImageDetail:
        return self.create_image_detail(index)

    def __getitem__(self, item) -> Union[JmImageDetail, List[JmImageDetail]]:
        return super().__getitem__(item)

    def __len__(self):
        return len(self.page_arr)

    def __iter__(self) -> Generator[JmImageDetail, None, None]:
        return super().__iter__()


class JmAlbumDetail(DetailEntity):

    def __init__(self,
                 album_id,
                 scramble_id,
                 name,
                 episode_list,
                 page_count,
                 pub_date,
                 update_date,
                 likes,
                 views,
                 comment_count,
                 works,
                 actors,
                 authors,
                 tags,
                 related_list=None,
                 ):
        self.album_id: str = album_id
        self.scramble_id: str = scramble_id
        self.name: str = name
        self.page_count = int(page_count)  # 总页数
        self.pub_date: str = pub_date  # 发布日期
        self.update_date: str = update_date  # 更新日期

        self.likes: str = likes  # [1K] 點擊喜歡
        self.views: str = views  # [40K] 次觀看
        self.comment_count: int = self.__parse_comment_count(comment_count)  # 评论数
        self.works: List[str] = works  # 作品
        self.actors: List[str] = actors  # 登場人物
        self.tags: List[str] = tags  # 標籤
        self.authors: List[str] = authors  # 作者

        # 有的 album 没有章节，则自成一章。
        if len(episode_list) == 0:
            # photo_id, photo_index, photo_title, photo_pub_date
            episode_list = [(album_id, 1, name, pub_date)]
        else:
            episode_list = self.distinct_episode(episode_list)

        self.episode_list: List[Tuple] = episode_list
        self.related_list = related_list

    @property
    def author(self):
        """
        作者
        禁漫本子的作者标签可能有多个，全部作者请使用字段 self.author_list
        """
        if len(self.authors) >= 1:
            return self.authors[0]

        return JmModuleConfig.default_author

    @property
    def id(self):
        return self.album_id

    @staticmethod
    def distinct_episode(episode_list):
        ret = []

        def not_exist(episode):
            photo_id = episode[0]
            for each in ret:
                if each[0] == photo_id:
                    return False
            return True

        for episode in episode_list:
            if not_exist(episode):
                ret.append(episode)

        return ret

    # noinspection PyMethodMayBeStatic
    def __parse_comment_count(self, comment_count: str) -> int:
        return int(comment_count)

    def create_photo_detail(self, index) -> Tuple[JmPhotoDetail, Tuple]:
        # 校验参数
        length = len(self.episode_list)

        if index >= length:
            raise JmModuleConfig.exception(f'创建JmPhotoDetail失败，{index} >= {length}')

        # ('212214', '81', '94 突然打來', '2020-08-29')
        pid, pindex, pname, _pub_date = self.episode_list[index]

        photo = JmModuleConfig.photo_class()(
            photo_id=pid,
            scramble_id=self.scramble_id,
            name=pname,
            keywords='',
            series_id=self.album_id,
            sort=pindex,
            author=self.author,
            from_album=self,
            page_arr=None,
            data_original_domain=None
        )

        return photo, (self.episode_list[index])

    def getindex(self, item) -> JmPhotoDetail:
        return self.create_photo_detail(item)[0]

    def __getitem__(self, item) -> Union[JmPhotoDetail, List[JmPhotoDetail]]:
        return super().__getitem__(item)

    def __len__(self):
        return len(self.episode_list)

    def __iter__(self) -> Generator[JmPhotoDetail, None, None]:
        return super().__iter__()


class JmSearchPage(JmBaseEntity, IndexedEntity):
    ContentItem = Tuple[str, Dict[str, Any]]

    def __init__(self, content: List[ContentItem]):
        # [
        #   album_id, {title, tag_list, ...}
        # ]
        self.content = content

    def iter_id(self) -> Generator[str, None, None]:
        """
        返回 album_id 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid

    def iter_id_title(self) -> Generator[Tuple[str, str], None, None]:
        """
        返回 album_id, album_title 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid, ainfo['name']

    def iter_id_title_tag(self) -> Generator[Tuple[str, str, List[str]], None, None]:
        """
        返回 album_id, album_title, album_tag_list 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid, ainfo['name'], ainfo['tag_list']

    # 下面的方法是对单个album的包装

    @property
    def is_single_album(self):
        return hasattr(self, 'album')

    @property
    def single_album(self) -> JmAlbumDetail:
        return getattr(self, 'album')

    @classmethod
    def wrap_single_album(cls, album: JmAlbumDetail) -> 'JmSearchPage':
        page = JmSearchPage([(
            album.album_id, {
                'name': album.name,
                'tag_list': album.tags,
            }
        )])
        setattr(page, 'album', album)
        return page

    # 下面的方法实现方便的元素访问

    def __len__(self):
        return len(self.content)

    def __iter__(self):
        return self.iter_id_title()

    def __getitem__(self, item) -> Union[ContentItem, List[ContentItem]]:
        return super().__getitem__(item)

    def getindex(self, index: int):
        return self.content[index]
