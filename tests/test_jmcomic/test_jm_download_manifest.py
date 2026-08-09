import asyncio
import os
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from test_jmcomic import *
from jmcomic.jm_async_client import AsyncJmApiClient
from jmcomic.jm_downloader import record_download_duration


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
        self.context_event_list = []
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
        self.context_event_list.append((group, get_jm_task_context()))
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


class Test_Download_Manifest(unittest.TestCase):

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
        self.assertIsNone(result.duration)

        album.duration = 1.25
        self.assertIsNone(result.duration)

        manifest.duration = 2.5

        self.assertEqual(result.duration, 2.5)

    def test_duration_decorator_accepts_keyword_entity_arguments(self):
        album, photo, _ = new_album_photo_images()
        sync_times = iter((10.0, 12.5))
        async_times = iter((20.0, 24.0))

        class Downloader:

            @record_download_duration('album_started_at', clock=lambda: next(sync_times))
            def download_album(self, album_id):
                return album

            @record_download_duration('photo_started_at', clock=lambda: next(async_times))
            async def download_photo(self, photo_id):
                return photo

        downloader = Downloader()

        self.assertIs(downloader.download_album(album_id='123'), album)
        self.assertEqual(album.duration, 2.5)
        self.assertIs(asyncio.run(downloader.download_photo(photo_id='456')), photo)
        self.assertEqual(photo.duration, 4.0)

    def test_export_plugins_allow_omitting_downloader(self):
        _, photo, _ = new_album_photo_images()
        option = ContractOption('/tmp')

        cases = (
            (Img2pdfPlugin, 'img2pdf', 'decide_filepath', 'write_img_2_pdf', '/tmp/photo.pdf', (['/tmp/1.jpg'], ['/tmp/photo'])),
            (LongImgPlugin, 'PIL', 'decide_filepath', 'write_img_2_long_img', '/tmp/photo.png', ['/tmp/1.jpg']),
        )
        for plugin_class, module_name, filepath_method, write_method, output_path, write_result in cases:
            with self.subTest(plugin=plugin_class.plugin_key):
                plugin = plugin_class(option)
                fake_module = SimpleNamespace(Image=object())
                with patch.dict(sys.modules, {module_name: fake_module}), \
                        patch.object(plugin, filepath_method, return_value=output_path), \
                        patch.object(plugin, write_method, return_value=write_result), \
                        patch.object(plugin, 'log'):
                    plugin.invoke(photo=photo)

    def test_record_export_filepath_uses_top_level_album_manifest(self):
        album, photo, _ = new_album_photo_images()
        downloader = BaseDownloader(ContractOption('/tmp'))
        manifest = downloader.begin_manifest(album)

        downloader.record_export_filepath(photo, '/tmp/album.PDF')

        self.assertIs(downloader.finish_manifest(album), manifest)
        self.assertEqual(manifest.export_filepath_dict, {'pdf': ['/tmp/album.PDF']})

    def test_record_export_filepath_uses_top_level_photo_manifest(self):
        _, photo, _ = new_album_photo_images()
        downloader = BaseDownloader(ContractOption('/tmp'))
        manifest = downloader.begin_manifest(photo)

        downloader.record_export_filepath(photo, '/tmp/photo.zip')

        self.assertIs(downloader.finish_manifest(photo), manifest)
        self.assertEqual(manifest.export_filepath_dict, {'zip': ['/tmp/photo.zip']})


    @staticmethod
    def new_manifest_downloader(base_dir, top_level='album'):
        album, photo, image_list = new_album_photo_images()
        option = ContractOption(base_dir)
        downloader = BaseDownloader(option)
        if top_level == 'album':
            downloader.begin_manifest(album)
        else:
            downloader.begin_manifest(photo)

        downloader.download_success_dict[album] = {
            photo: [
                (option.decide_image_filepath(image), image)
                for image in image_list
            ]
        }
        return album, photo, image_list, downloader

    def test_record_export_filepath_groups_real_suffixes(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, _, downloader = self.new_manifest_downloader(temp_dir)
            cbz_path = os.path.join(temp_dir, 'album.cbz')
            pdf_path = os.path.join(temp_dir, 'photo.PDF')
            png_path = os.path.join(temp_dir, 'photo.png')

            downloader.record_export_filepath(album, cbz_path)
            downloader.record_export_filepath(photo, pdf_path)
            downloader.record_export_filepath(photo, png_path)

            manifest = downloader.manifest_dict[album]
            self.assertEqual(manifest.export_filepath_dict, {
                'cbz': [cbz_path],
                'pdf': [pdf_path],
                'png': [png_path],
            })

    def test_record_export_filepath_rejects_missing_manifest(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _ = new_album_photo_images()
            downloader = BaseDownloader(ContractOption(temp_dir))

            with self.assertRaisesRegex(JmcomicException, '没有活动的下载清单'):
                downloader.record_export_filepath(album, os.path.join(temp_dir, 'album.zip'))

    def test_record_export_filepath_ignores_paths_without_suffix(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            manifest = downloader.manifest_dict[album]

            downloader.record_export_filepath(album, os.path.join(temp_dir, 'export'))

            self.assertEqual(manifest.export_filepath_dict, {})

    def test_zip_album_registers_configured_suffix_once_after_success(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = ZipPlugin(downloader.option)
            zip_dir = os.path.join(temp_dir, 'exports')
            expected_path = plugin.decide_filepath(album, None, 'Aid', 'cbz', os.path.abspath(zip_dir), None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', filepath))
                return original_record(detail, filepath)

            def fake_zip_album(*args, **kwargs):
                order.append(('zip_album', expected_path))

            def fake_after_zip(_paths):
                order.append(('after_zip', None))
                self.assertEqual(
                    downloader.manifest_dict[album].export_filepath_dict,
                    {'cbz': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.object(plugin, 'zip_album', side_effect=fake_zip_album), \
                    patch.object(plugin, 'after_zip', side_effect=fake_after_zip):
                plugin.invoke(
                    downloader=downloader,
                    album=album,
                    filename_rule='Aid',
                    suffix='cbz',
                    zip_dir=zip_dir,
                )

            self.assertEqual(order, [
                ('zip_album', expected_path),
                ('record', expected_path),
                ('after_zip', None),
            ])

    def test_zip_photo_registers_to_album_manifest_once_after_success(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = ZipPlugin(downloader.option)
            zip_dir = os.path.join(temp_dir, 'exports')
            expected_path = plugin.decide_filepath(photo.from_album, photo, 'Pid', 'cbz', os.path.abspath(zip_dir), None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', detail, filepath))
                return original_record(detail, filepath)

            def fake_zip_photo(current_photo, image_list, zip_path, path_to_delete, encrypt):
                self.assertIs(current_photo, photo)
                self.assertEqual(zip_path, expected_path)
                order.append(('zip_photo', current_photo, zip_path))

            def fake_after_zip(_paths):
                order.append(('after_zip', None, None))
                self.assertEqual(
                    downloader.manifest_dict[album].export_filepath_dict,
                    {'cbz': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.object(plugin, 'zip_photo', side_effect=fake_zip_photo), \
                    patch.object(plugin, 'after_zip', side_effect=fake_after_zip):
                plugin.invoke(
                    downloader=downloader,
                    album=album,
                    level='photo',
                    filename_rule='Pid',
                    suffix='cbz',
                    zip_dir=zip_dir,
                )

            self.assertEqual(order, [
                ('zip_photo', photo, expected_path),
                ('record', photo, expected_path),
                ('after_zip', None, None),
            ])
            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict['cbz'].count(expected_path), 1)

    def test_pdf_registers_once_before_optional_deletion(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = Img2pdfPlugin(downloader.option)
            expected_path = plugin.decide_filepath(album, None, 'Aid', 'pdf', temp_dir, None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', filepath))
                return original_record(detail, filepath)

            def fake_write(pdf_filepath, current_album, current_photo, encrypt):
                self.assertEqual(pdf_filepath, expected_path)
                self.assertIs(current_album, album)
                self.assertIsNone(current_photo)
                order.append(('write', pdf_filepath))
                return ['img1.jpg'], ['photo_dir']

            def fake_delete(paths):
                order.append(('delete', list(paths)))
                self.assertEqual(
                    downloader.manifest_dict[album].export_filepath_dict,
                    {'pdf': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.dict(sys.modules, {'img2pdf': object()}), \
                    patch.object(plugin, 'write_img_2_pdf', side_effect=fake_write), \
                    patch.object(plugin, 'execute_deletion', side_effect=fake_delete):
                plugin.invoke(
                    album=album,
                    downloader=downloader,
                    pdf_dir=temp_dir,
                    filename_rule='Aid',
                )

            self.assertEqual(order[0], ('write', expected_path))
            self.assertEqual(order[1], ('record', expected_path))
            self.assertEqual(order[2], ('delete', ['img1.jpg', 'photo_dir']))
            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict['pdf'].count(expected_path), 1)

    def test_pdf_photo_level_registers_photo_detail_once(self):
        with TemporaryDirectory() as temp_dir:
            _, photo, _, downloader = self.new_manifest_downloader(temp_dir, top_level='photo')
            plugin = Img2pdfPlugin(downloader.option)
            expected_path = plugin.decide_filepath(None, photo, 'Pid', 'pdf', temp_dir, None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', detail, filepath))
                return original_record(detail, filepath)

            def fake_write(pdf_filepath, current_album, current_photo, encrypt):
                self.assertEqual(pdf_filepath, expected_path)
                self.assertIsNone(current_album)
                self.assertIs(current_photo, photo)
                order.append(('write', current_photo, pdf_filepath))
                return ['img1.jpg'], ['photo_dir']

            def fake_delete(paths):
                order.append(('delete', list(paths)))
                self.assertEqual(
                    downloader.manifest_dict[photo].export_filepath_dict,
                    {'pdf': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.dict(sys.modules, {'img2pdf': object()}), \
                    patch.object(plugin, 'write_img_2_pdf', side_effect=fake_write), \
                    patch.object(plugin, 'execute_deletion', side_effect=fake_delete):
                plugin.invoke(
                    photo=photo,
                    downloader=downloader,
                    pdf_dir=temp_dir,
                    filename_rule='Pid',
                )

            self.assertEqual(order[0], ('write', photo, expected_path))
            self.assertEqual(order[1], ('record', photo, expected_path))
            self.assertEqual(order[2], ('delete', ['img1.jpg', 'photo_dir']))
            self.assertEqual(downloader.manifest_dict[photo].export_filepath_dict['pdf'].count(expected_path), 1)

    def test_pdf_missing_library_registers_nothing(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = Img2pdfPlugin(downloader.option)
            original_import = __import__

            def fake_import(name, *args, **kwargs):
                if name == 'img2pdf':
                    raise ImportError('img2pdf missing')
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=fake_import):
                with self.assertRaises(PluginValidationException):
                    plugin.invoke(
                        album=album,
                        downloader=downloader,
                        pdf_dir=temp_dir,
                        filename_rule='Aid',
                    )

            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict, {})

    def test_pdf_empty_source_registers_nothing(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = Img2pdfPlugin(downloader.option)

            with patch.dict(sys.modules, {'img2pdf': object()}), \
                    patch.object(plugin, 'write_img_2_pdf', return_value=None), \
                    patch.object(plugin, 'execute_deletion') as delete_mock:
                plugin.invoke(
                    album=album,
                    downloader=downloader,
                    pdf_dir=temp_dir,
                    filename_rule='Aid',
                )

            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict, {})
            delete_mock.assert_not_called()

    def test_long_img_registers_once_before_optional_deletion(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = LongImgPlugin(downloader.option)
            expected_path = plugin.decide_filepath(album, None, 'Aid', 'png', temp_dir, None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', filepath))
                return original_record(detail, filepath)

            def fake_write(long_img_path, current_album, current_photo):
                self.assertEqual(long_img_path, expected_path)
                self.assertIs(current_album, album)
                self.assertIsNone(current_photo)
                order.append(('write', long_img_path))
                return ['img1.jpg']

            def fake_delete(paths):
                order.append(('delete', list(paths)))
                self.assertEqual(
                    downloader.manifest_dict[album].export_filepath_dict,
                    {'png': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.dict(sys.modules, {'PIL': SimpleNamespace(Image=object())}), \
                    patch.object(plugin, 'write_img_2_long_img', side_effect=fake_write), \
                    patch.object(plugin, 'execute_deletion', side_effect=fake_delete):
                plugin.invoke(
                    album=album,
                    downloader=downloader,
                    img_dir=temp_dir,
                    filename_rule='Aid',
                )

            self.assertEqual(order[0], ('write', expected_path))
            self.assertEqual(order[1], ('record', expected_path))
            self.assertEqual(order[2], ('delete', ['img1.jpg']))
            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict['png'].count(expected_path), 1)

    def test_long_img_photo_level_registers_photo_detail_once(self):
        with TemporaryDirectory() as temp_dir:
            _, photo, _, downloader = self.new_manifest_downloader(temp_dir, top_level='photo')
            plugin = LongImgPlugin(downloader.option)
            expected_path = plugin.decide_filepath(None, photo, 'Pid', 'png', temp_dir, None)
            order = []
            original_record = downloader.record_export_filepath

            def record(detail, filepath):
                order.append(('record', detail, filepath))
                return original_record(detail, filepath)

            def fake_write(long_img_path, current_album, current_photo):
                self.assertEqual(long_img_path, expected_path)
                self.assertIsNone(current_album)
                self.assertIs(current_photo, photo)
                order.append(('write', current_photo, long_img_path))
                return ['img1.jpg']

            def fake_delete(paths):
                order.append(('delete', list(paths)))
                self.assertEqual(
                    downloader.manifest_dict[photo].export_filepath_dict,
                    {'png': [expected_path]},
                )

            downloader.record_export_filepath = record

            with patch.dict(sys.modules, {'PIL': SimpleNamespace(Image=object())}), \
                    patch.object(plugin, 'write_img_2_long_img', side_effect=fake_write), \
                    patch.object(plugin, 'execute_deletion', side_effect=fake_delete):
                plugin.invoke(
                    photo=photo,
                    downloader=downloader,
                    img_dir=temp_dir,
                    filename_rule='Pid',
                )

            self.assertEqual(order[0], ('write', photo, expected_path))
            self.assertEqual(order[1], ('record', photo, expected_path))
            self.assertEqual(order[2], ('delete', ['img1.jpg']))
            self.assertEqual(downloader.manifest_dict[photo].export_filepath_dict['png'].count(expected_path), 1)

    def test_long_img_missing_library_registers_nothing(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = LongImgPlugin(downloader.option)
            original_import = __import__

            def fake_import(name, *args, **kwargs):
                if name == 'PIL':
                    raise ImportError('PIL missing')
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=fake_import):
                with self.assertRaises(PluginValidationException):
                    plugin.invoke(
                        album=album,
                        downloader=downloader,
                        img_dir=temp_dir,
                        filename_rule='Aid',
                    )

            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict, {})

    def test_long_img_empty_source_registers_nothing(self):
        with TemporaryDirectory() as temp_dir:
            album, _, _, downloader = self.new_manifest_downloader(temp_dir)
            plugin = LongImgPlugin(downloader.option)

            with patch.dict(sys.modules, {'PIL': SimpleNamespace(Image=object())}), \
                    patch.object(plugin, 'write_img_2_long_img', return_value=None), \
                    patch.object(plugin, 'execute_deletion') as delete_mock:
                plugin.invoke(
                    album=album,
                    downloader=downloader,
                    img_dir=temp_dir,
                    filename_rule='Aid',
                )

            self.assertEqual(downloader.manifest_dict[album].export_filepath_dict, {})
            delete_mock.assert_not_called()


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

    def test_entity_timing_contexts_are_nested_and_do_not_leak(self):
        with TemporaryDirectory() as temp_dir:
            album, photo, image_list, option, downloader = self.new_downloader(temp_dir, image_count=2)
            self.create_cached_images(option, image_list)

            with patch('jmcomic.jm_downloader.perf_counter', side_effect=range(1, 9)):
                downloader.download_album(album.id)

            context_by_group = {}
            for group, context in option.context_event_list:
                context_by_group.setdefault(group, []).append(context)

            self.assertEqual(1, context_by_group['before_album'][0].get('album_started_at'))
            self.assertEqual(
                {'album_started_at': 1, 'photo_started_at': 2},
                context_by_group['before_photo'][0],
            )
            self.assertEqual(
                [3, 5],
                [context['image_started_at'] for context in context_by_group['before_image']],
            )
            self.assertEqual(
                [2, 2],
                [context['photo_started_at'] for context in context_by_group['before_image']],
            )
            self.assertEqual({}, get_jm_task_context())

    def test_sync_download_album_duration_includes_detail_and_manifest(self):
        clock = {'now': 10.0}
        contexts = []
        album = SimpleNamespace(duration=None)
        downloader = object.__new__(JmDownloader)

        def get_album_detail(_album_id):
            contexts.append(get_jm_task_context())
            clock['now'] = 20.0
            return album

        def begin_manifest(_album):
            contexts.append(get_jm_task_context())
            clock['now'] = 30.0

        def download_by_album_detail(_album):
            contexts.append(get_jm_task_context())
            clock['now'] = 40.0

        def finish_manifest(_album):
            contexts.append(get_jm_task_context())
            clock['now'] = 50.0

        downloader.client = SimpleNamespace(get_album_detail=get_album_detail)
        downloader.begin_manifest = begin_manifest
        downloader.download_by_album_detail = download_by_album_detail
        downloader.finish_manifest = finish_manifest

        with patch('jmcomic.jm_downloader.perf_counter', side_effect=lambda: clock['now']):
            result = JmDownloader.download_album(downloader, '123')

        self.assertIs(result, album)
        self.assertEqual(40.0, album.duration)
        self.assertEqual([10.0] * 4, [context.get('album_started_at') for context in contexts])
        self.assertEqual({}, get_jm_task_context())

    def test_sync_download_photo_duration_includes_detail_and_manifest(self):
        clock = {'now': 10.0}
        contexts = []
        photo = SimpleNamespace(duration=None)
        downloader = object.__new__(JmDownloader)

        def get_photo_detail(_photo_id):
            contexts.append(get_jm_task_context())
            clock['now'] = 20.0
            return photo

        def begin_manifest(_photo):
            contexts.append(get_jm_task_context())
            clock['now'] = 30.0

        def download_by_photo_detail(_photo):
            contexts.append(get_jm_task_context())
            clock['now'] = 40.0

        def finish_manifest(_photo):
            contexts.append(get_jm_task_context())
            clock['now'] = 50.0

        downloader.client = SimpleNamespace(get_photo_detail=get_photo_detail)
        downloader.begin_manifest = begin_manifest
        downloader.download_by_photo_detail = download_by_photo_detail
        downloader.finish_manifest = finish_manifest

        with patch('jmcomic.jm_downloader.perf_counter', side_effect=lambda: clock['now']):
            result = JmDownloader.download_photo(downloader, '456')

        self.assertIs(result, photo)
        self.assertEqual(40.0, photo.duration)
        self.assertEqual([10.0] * 4, [context.get('photo_started_at') for context in contexts])
        self.assertEqual({}, get_jm_task_context())

    def test_async_download_album_duration_includes_detail_and_manifest(self):
        async def run_test():
            clock = {'now': 10.0}
            contexts = []
            album = SimpleNamespace(duration=None)
            downloader = object.__new__(JmAsyncDownloader)

            async def get_album_detail(_album_id):
                contexts.append(get_jm_task_context())
                clock['now'] = 20.0
                return album

            def begin_manifest(_album):
                contexts.append(get_jm_task_context())
                clock['now'] = 30.0

            async def download_by_album_detail(_album):
                contexts.append(get_jm_task_context())
                clock['now'] = 40.0

            def finish_manifest(_album):
                contexts.append(get_jm_task_context())
                clock['now'] = 50.0

            downloader.client = SimpleNamespace(get_album_detail=get_album_detail)
            downloader.begin_manifest = begin_manifest
            downloader.download_by_album_detail = download_by_album_detail
            downloader.finish_manifest = finish_manifest

            with patch('jmcomic.jm_downloader.perf_counter', side_effect=lambda: clock['now']):
                result = await JmAsyncDownloader.download_album(downloader, '123')

            self.assertIs(result, album)
            self.assertEqual(40.0, album.duration)
            self.assertEqual([10.0] * 4, [context.get('album_started_at') for context in contexts])
            self.assertEqual({}, get_jm_task_context())

        asyncio.run(run_test())

    def test_async_download_photo_duration_includes_detail_and_manifest(self):
        async def run_test():
            clock = {'now': 10.0}
            contexts = []
            photo = SimpleNamespace(duration=None)
            downloader = object.__new__(JmAsyncDownloader)

            async def get_photo_detail(_photo_id):
                contexts.append(get_jm_task_context())
                clock['now'] = 20.0
                return photo

            def begin_manifest(_photo):
                contexts.append(get_jm_task_context())
                clock['now'] = 30.0

            async def download_by_photo_detail(_photo):
                contexts.append(get_jm_task_context())
                clock['now'] = 40.0

            def finish_manifest(_photo):
                contexts.append(get_jm_task_context())
                clock['now'] = 50.0

            downloader.client = SimpleNamespace(get_photo_detail=get_photo_detail)
            downloader.begin_manifest = begin_manifest
            downloader.download_by_photo_detail = download_by_photo_detail
            downloader.finish_manifest = finish_manifest

            with patch('jmcomic.jm_downloader.perf_counter', side_effect=lambda: clock['now']):
                result = await JmAsyncDownloader.download_photo(downloader, '456')

            self.assertIs(result, photo)
            self.assertEqual(40.0, photo.duration)
            self.assertEqual([10.0] * 4, [context.get('photo_started_at') for context in contexts])
            self.assertEqual({}, get_jm_task_context())

        asyncio.run(run_test())

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
