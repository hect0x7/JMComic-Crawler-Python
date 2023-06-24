from common import *

from .jm_config import *


class JmBaseEntity:
    pass


class WorkEntity(JmBaseEntity, SaveableEntity, IterableEntity):
    when_del_save_file = False
    after_save_print_info = True
    attr_char = '_'

    cache_getitem_result = True
    cache_field_name = '__cache_items_dict__'
    detail_save_base_dir = workspace()
    detail_save_file_suffix = '.yml'

    def save_base_dir(self):
        return self.detail_save_base_dir

    def save_file_name(self) -> str:
        def jm_type():
            # "JmAlbumDetail" -> "album"
            cls_name = self.__class__.__name__
            return cls_name[cls_name.index("m") + 1: cls_name.rfind("Detail")].lower()

        return '[{}]{}{}'.format(jm_type(), self.id, self.detail_save_file_suffix)

    @property
    def id(self) -> str:
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __getitem__(self, item) -> Union['JmAlbumDetail', 'JmPhotoDetail']:
        raise NotImplementedError


class JmImageDetail(JmBaseEntity):

    def __init__(self,
                 aid,
                 scramble_id,
                 img_url,
                 img_file_name,
                 img_file_suffix,
                 from_photo=None,
                 ) -> None:
        self.aid: str = aid
        self.scramble_id: str = scramble_id
        self.img_url: str = img_url
        self.img_file_name: str = img_file_name
        self.img_file_suffix: str = img_file_suffix

        self.from_photo: Optional[JmPhotoDetail] = from_photo

    @property
    def filename(self):
        return self.img_file_name + self.img_file_suffix

    @classmethod
    def of(cls,
           photo_id: str,
           scramble_id: str,
           data_original: str,
           from_photo=None,
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
        )


class JmPhotoDetail(WorkEntity):

    def __init__(self,
                 photo_id,
                 scramble_id,
                 title,
                 keywords,
                 series_id,
                 sort,
                 page_arr=None,
                 data_original_domain=None,
                 author=None,
                 from_album=None,
                 ):
        self.photo_id: str = photo_id
        self.scramble_id: str = scramble_id
        self.title: str = str(title).strip()
        self.sort: int = int(sort)
        self._keywords: str = keywords
        self._series_id: int = int(series_id)

        self._author: StrNone = author
        self.from_album: Optional[JmAlbumDetail] = from_album

        # 下面的属性和图片url有关
        if isinstance(page_arr, str):
            import json
            page_arr = json.loads(page_arr)

        # 该photo的所有图片名 img_name
        self.page_arr: List[str] = page_arr
        # 图片域名
        self.data_original_domain: StrNone = data_original_domain
        self.index = self.album_index

    @property
    def is_single_album(self) -> bool:
        return self._series_id == 0

    @property
    def keywords(self) -> List[str]:
        if self.from_album is not None:
            return self.from_album.keywords

        return self._keywords.split(',')

    @property
    def indextitle(self):
        return f'第{self.album_index}話 {self.title}'

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
            raise AssertionError(f'创建JmImageDetail失败，{index} >= {length}')

        data_original = self.get_img_data_original(self.page_arr[index])

        return JmImageDetail.of(
            self.photo_id,
            self.scramble_id,
            data_original,
            from_photo=self
        )

    def get_img_data_original(self, img_name: str) -> str:
        """
        根据图片名，生成图片的完整请求路径 URL
        例如：img_name = 01111.webp
        返回：https://cdn-msp2.18comic.org/media/photos/147643/01111.webp
        """
        data_original_domain = self.data_original_domain
        if data_original_domain is None:
            raise AssertionError(f'图片域名为空: {self.__dict__}')

        return f'https://{data_original_domain}/media/photos/{self.photo_id}/{img_name}'

    def __getitem__(self, item) -> JmImageDetail:
        return self.create_image_detail(item)

    @property
    def id(self):
        return self.photo_id

    def __len__(self):
        return len(self.page_arr)

    def __iter__(self) -> Generator[JmImageDetail, Any, None]:
        return super().__iter__()


class JmAlbumDetail(WorkEntity):

    def __init__(self,
                 album_id,
                 scramble_id,
                 title,
                 episode_list,
                 page_count,
                 author_list,
                 keywords_list,
                 pub_date,
                 update_date,
                 ):
        self.album_id: str = album_id
        self.scramble_id: str = scramble_id
        self.title: str = title
        self.page_count = int(page_count)
        self._author_list: List[str] = author_list
        self._keywords_list: List[str] = keywords_list
        self.pub_date: str = pub_date  # 发布日期
        self.update_date: str = update_date  # 更新日期

        # 有的 album 没有章节，则自成一章。
        if len(episode_list) == 0:
            # photo_id, photo_index_of_album, photo_title, photo_pub_date
            episode_list = [(album_id, 0, title, pub_date)]

        self.episode_list: List[Tuple] = self.distinct_episode(episode_list)

    def create_photo_detail(self, index) -> Tuple[JmPhotoDetail, Tuple]:
        # 校验参数
        length = len(self.episode_list)

        if index >= length:
            raise AssertionError(f'创建JmPhotoDetail失败，{index} >= {length}')

        # episode_info: ('212214', '81', '94 突然打來', '2020-08-29')
        episode_info: tuple = self.episode_list[index]
        photo_id, photo_index_of_album, photo_title, photo_pub_date = episode_info

        photo_detail = JmPhotoDetail(
            photo_id=photo_id,
            scramble_id=self.scramble_id,
            title=photo_title,
            keywords='',
            series_id=self.album_id,
            sort=episode_info[1] if len(self) != 1 else 1,
            author=self.author,
            from_album=self,
            page_arr=None,
            data_original_domain=None
        )

        return photo_detail, episode_info

    @property
    def author(self):
        if len(self._author_list) >= 1:
            return self._author_list[0]
        return JmModuleConfig.default_author

    @property
    def keywords(self) -> List[str]:
        return self._keywords_list

    @property
    def id(self):
        return self.album_id

    def __len__(self):
        return len(self.episode_list)

    def __getitem__(self, item) -> JmPhotoDetail:
        return self.create_photo_detail(item)[0]

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

    def __iter__(self) -> Generator[JmPhotoDetail, Any, None]:
        return super().__iter__()


class JmSearchPage(IterableEntity):

    def __init__(self, album_info_list: List[Tuple[str, str, StrNone, StrNone, List[str]]]):
        # (album_id, title, category_none, label_sub_none, tag_list)
        self.album_info_list = album_info_list

    def __len__(self):
        return len(self.album_info_list)

    def __getitem__(self, item):
        return self.album_info_list[item][0:2]

    @property
    def single_album(self) -> JmAlbumDetail:
        return getattr(self, 'album')

    @classmethod
    def wrap_single_album(cls, album: JmAlbumDetail) -> 'JmSearchPage':
        # ('462257', '[無邪気漢化組] [きょくちょ] 楓と鈴 4.5', '短篇', '漢化', [])
        # (album_id, title, category_none, label_sub_none, tag_list)

        album_info = (
            album.album_id,
            album.title,
            None,
            None,
            album.keywords,
        )
        obj = JmSearchPage([album_info])

        setattr(obj, 'album', album)
        return obj
