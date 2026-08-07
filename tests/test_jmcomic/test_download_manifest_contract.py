import asyncio
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from test_jmcomic import *
from jmcomic.jm_async_client import AsyncJmApiClient


def new_album_photo_images(image_count=1):
    album = JmAlbumDetail(
        album_id='123',
        scramble_id='220980',
        name='album',
        episode_list=[('456', '1', 'photo')],
        page_count=image_count,
        pub_date='',
        update_date='',
        likes='0',
        views='0',
        comment_count=0,
        works=[],
        actors=[],
        authors=['author'],
        tags=['tag'],
    )
    photo = JmPhotoDetail(
        photo_id='456',
        name='photo',
        series_id='123',
        sort=1,
        scramble_id='220980',
        page_arr=[f'{index:05}.jpg' for index in range(1, image_count + 1)],
        data_original_domain='cdn.example',
        from_album=album,
    )
    return album, photo, list(photo)


class ContractOption:

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.plugin_event_list = []
        self.after_image_callback = None
        self.dir_rule = SimpleNamespace(
            base_dir=base_dir,
            decide_album_root_dir=lambda _album: os.path.join(base_dir, 'album'),
        )
        self.download = SimpleNamespace(
            threading=SimpleNamespace(image=1, photo=1),
        )

    def decide_image_save_dir(self, _photo):
        return os.path.join(self.base_dir, 'album', 'photo')

    def decide_image_filepath(self, image):
        return os.path.join(self.decide_image_save_dir(image.from_photo), image.filename)

    def decide_download_cache(self, _image):
        return True

    def decide_download_image_decode(self, _image):
        return False

    def decide_photo_batch_count(self, _album):
        return 1

    def decide_image_batch_count(self, _photo):
        return 1

    def call_all_plugin(self, group, **kwargs):
        self.plugin_event_list.append((group, kwargs))
        if group == 'after_image' and self.after_image_callback is not None:
            self.after_image_callback(kwargs['image'])


class ContractSyncClient:

    def __init__(self, album, photo):
        self.album = album
        self.photo = photo
        self.image_download_count = 0

    def get_album_detail(self, _album_id):
        return self.album

    def get_photo_detail(self, _photo_id):
        return self.photo

    def check_photo(self, _photo):
        return None

    def download_by_image_detail(self, _image, save_path, decode_image):
        self.image_download_count += 1
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(b'image')


class ContractSyncDownloader(JmDownloader):

    def __init__(self, option, album, photo, image_list):
        self._contract_client = ContractSyncClient(album, photo)
        self._contract_album = album
        self._contract_photo = photo
        self._contract_image_list = image_list
        super().__init__(option)

    def create_client(self):
        return self._contract_client

    def do_filter(self, detail):
        if detail is self._contract_album:
            return [self._contract_photo]
        if detail is self._contract_photo:
            return list(self._contract_image_list)
        return detail

    def execute_on_condition(self, iter_objs, apply, count_batch):
        for detail in self.do_filter(iter_objs):
            apply(detail)


class ContractAsyncClient:

    def __init__(self, album, photo):
        self.album = album
        self.photo = photo
        self.image_download_count = 0

    async def get_album_detail(self, _album_id):
        return self.album

    async def get_photo_detail(self, _photo_id):
        return self.photo

    async def check_photo(self, _photo):
        return None


class ContractAsyncDownloader(JmAsyncDownloader):

    def __init__(self, option, album, photo, image_list):
        self._contract_album = album
        self._contract_photo = photo
        self._contract_image_list = image_list
        super().__init__(option)
        self.client = ContractAsyncClient(album, photo)

    def do_filter(self, detail):
        if detail is self._contract_album:
            return [self._contract_photo]
        if detail is self._contract_photo:
            return list(self._contract_image_list)
        return detail


class Test_Download_Manifest_Public_Contract(unittest.TestCase):

    def test_downloadable_defaults(self):
        album, photo, image_list = new_album_photo_images()

        for detail in (album, photo, image_list[0]):
            self.assertEqual(detail.save_path, '')
            self.assertFalse(detail.exists)
            self.assertFalse(detail.skip)
            self.assertTrue(detail.cache)
            self.assertIsNone(detail.duration)

    def test_manifest_containers_are_not_shared(self):
        first = DownloadManifest()
        second = DownloadManifest()

        first.image_filepath_list.append('/tmp/1.jpg')
        first.export_filepath_dict['pdf'] = ['/tmp/1.pdf']

        self.assertEqual(second.image_filepath_list, [])
        self.assertEqual(second.export_filepath_dict, {})

    def test_export_filepath_lookup_normalizes_suffix(self):
        manifest = DownloadManifest()
        manifest.export_filepath_dict['pdf'] = ['/tmp/1.pdf']

        self.assertEqual(manifest.get_export_filepath_list('pdf'), ['/tmp/1.pdf'])
        self.assertEqual(manifest.get_export_filepath_list('.PDF'), ['/tmp/1.pdf'])
        self.assertEqual(manifest.get_export_filepath_list('zip'), [])

    def test_download_result_remains_a_two_item_tuple(self):
        album, _, _ = new_album_photo_images()
        option = ContractOption('/tmp')
        downloader = BaseDownloader(option)
        manifest = DownloadManifest()
        downloader.manifest_dict[album] = manifest

        result = DownloadResult(album, downloader)
        unpacked_album, unpacked_downloader = result

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIs(unpacked_album, album)
        self.assertIs(unpacked_downloader, downloader)
        self.assertIs(result.manifest, manifest)


class Test_Detail_Cache_Copy_Contract(unittest.TestCase):

    def test_sync_detail_cache_returns_clean_copy(self):
        class CachedClient(AbstractJmClient):
            func_to_cache = ['fetch_detail_entity']

            def fetch_detail_entity(self, _album_id):
                self.fetch_count += 1
                album, _, _ = new_album_photo_images()
                return album

        client = object.__new__(CachedClient)
        client.CLIENT_CACHE = {}
        client.fetch_count = 0
        client.enable_cache()

        first = client.fetch_detail_entity('123')
        first.save_path = '/download/123'
        first.duration = 1.5
        first.tags.append('mutated')
        second = client.fetch_detail_entity('123')

        self.assertEqual(client.fetch_count, 1)
        self.assertIsNot(first, second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.save_path, '')
        self.assertIsNone(second.duration)
        self.assertNotIn('mutated', second.tags)

    def test_async_detail_cache_returns_clean_copy(self):
        async def run_test():
            client = object.__new__(AsyncJmApiClient)
            client._cache = {}
            client.request_count = 0

            class Response:
                encoded_data = 'encoded'
                res_data = {
                    'id': '123',
                    'name': 'album',
                    'author': ['author'],
                    'images': [],
                    'description': '',
                    'total_views': '0',
                    'likes': '0',
                    'series': [],
                    'comment_total': '0',
                    'tags': ['tag'],
                    'works': [],
                    'actors': [],
                    'related_list': [],
                }

            async def req_api(_url, **_kwargs):
                client.request_count += 1
                return Response()

            client.req_api = req_api

            first = await client.get_album_detail('123')
            first.save_path = '/download/123'
            first.duration = 1.5
            first.tags.append('mutated')
            second = await client.get_album_detail('123')

            self.assertEqual(client.request_count, 1)
            self.assertIsNot(first, second)
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.save_path, '')
            self.assertIsNone(second.duration)
            self.assertNotIn('mutated', second.tags)

        asyncio.run(run_test())


class Test_Sync_Download_Manifest_Contract(unittest.TestCase):

    def new_downloader(self, base_dir, image_count=1):
        album, photo, image_list = new_album_photo_images(image_count)
        option = ContractOption(base_dir)
        downloader = ContractSyncDownloader(option, album, photo, image_list)
        return album, photo, image_list, option, downloader

    @staticmethod
    def create_cached_images(option, image_list):
        for image in image_list:
            filepath = option.decide_image_filepath(image)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(b'cached')

    def test_album_photo_image_paths_and_durations(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, image_list, option, downloader = self.new_downloader(temp_dir)
            self.create_cached_images(option, image_list)

            downloader.download_album(album.id)

            self.assertEqual(album.save_path, option.dir_rule.decide_album_root_dir(album))
            self.assertEqual(photo.save_path, option.decide_image_save_dir(photo))
            self.assertEqual(image_list[0].save_path, option.decide_image_filepath(image_list[0]))
            self.assertIsInstance(album.duration, float)
            self.assertIsInstance(photo.duration, float)
            self.assertIsInstance(image_list[0].duration, float)

    def test_cache_hit_triggers_after_image_and_success_record(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, image_list, option, downloader = self.new_downloader(temp_dir)
            self.create_cached_images(option, image_list)

            downloader.download_album(album.id)

            after_image_events = [event for event, _ in option.plugin_event_list if event == 'after_image']
            self.assertEqual(after_image_events, ['after_image'])
            self.assertEqual(downloader._contract_client.image_download_count, 0)
            self.assertEqual(
                downloader.download_success_dict[album][photo],
                [(image_list[0].save_path, image_list[0])],
            )

    def test_album_manifest_collects_cached_images_in_entity_order(self):
        with TemporaryDirectory() as temp_dir:
            album, _, image_list, option, downloader = self.new_downloader(temp_dir, image_count=2)
            self.create_cached_images(option, image_list)

            downloader.download_album(album.id)

            manifest = downloader.manifest_dict[album]
            self.assertEqual(
                manifest.image_filepath_list,
                [image.save_path for image in image_list],
            )

    def test_album_internal_photo_does_not_create_another_manifest(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, image_list, option, downloader = self.new_downloader(temp_dir)
            self.create_cached_images(option, image_list)

            downloader.download_album(album.id)

            self.assertEqual(set(downloader.manifest_dict), {album})
            self.assertNotIn(photo, downloader.manifest_dict)

    def test_top_level_photo_creates_photo_manifest(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, image_list, option, downloader = self.new_downloader(temp_dir)
            self.create_cached_images(option, image_list)

            downloaded_photo = downloader.download_photo(photo.id)

            self.assertIs(downloaded_photo, photo)
            self.assertEqual(set(downloader.manifest_dict), {photo})
            self.assertEqual(
                downloader.manifest_dict[photo].image_filepath_list,
                [image.save_path for image in image_list],
            )

    def test_skipped_image_has_duration_but_is_not_in_manifest(self):
        with TemporaryDirectory() as temp_dir:
            album, _, image_list, option, downloader = self.new_downloader(temp_dir)
            image_list[0].skip = True

            downloader.download_album(album.id)

            self.assertIsInstance(image_list[0].duration, float)
            self.assertEqual(downloader.manifest_dict[album].image_filepath_list, [])

    def test_manifest_uses_final_path_after_image_plugin(self):
        with TemporaryDirectory() as temp_dir:
            album, _, image_list, option, downloader = self.new_downloader(temp_dir)
            self.create_cached_images(option, image_list)
            final_path = os.path.join(temp_dir, 'converted', '00001.webp')
            option.after_image_callback = lambda image: setattr(image, 'save_path', final_path)

            downloader.download_album(album.id)

            self.assertEqual(image_list[0].save_path, final_path)
            self.assertEqual(downloader.manifest_dict[album].image_filepath_list, [final_path])


class Test_Async_Download_Manifest_Contract(unittest.TestCase):

    def test_cache_hit_paths_durations_after_image_and_manifest(self):
        async def run_test(temp_dir):
            album, photo, image_list = new_album_photo_images()
            option = ContractOption(temp_dir)
            image = image_list[0]
            filepath = option.decide_image_filepath(image)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(b'cached')

            downloader = ContractAsyncDownloader(option, album, photo, image_list)
            try:
                await downloader.download_album(album.id)

                self.assertEqual(album.save_path, option.dir_rule.decide_album_root_dir(album))
                self.assertEqual(photo.save_path, option.decide_image_save_dir(photo))
                self.assertEqual(image.save_path, filepath)
                self.assertIsInstance(album.duration, float)
                self.assertIsInstance(photo.duration, float)
                self.assertIsInstance(image.duration, float)
                after_image_events = [event for event, _ in option.plugin_event_list if event == 'after_image']
                self.assertEqual(after_image_events, ['after_image'])
                self.assertEqual(downloader.download_success_dict[album][photo], [(filepath, image)])
                self.assertEqual(downloader.manifest_dict[album].image_filepath_list, [filepath])
            finally:
                downloader.shutdown()

        with TemporaryDirectory() as temp_dir:
            asyncio.run(run_test(temp_dir))
