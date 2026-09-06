import asyncio
from concurrent.futures import Future
from types import SimpleNamespace
from threading import Thread
import unittest
from unittest.mock import AsyncMock, Mock, patch

from jmcomic import (
    BaseDownloader,
    DownloadCancelledException,
    DownloadControl,
    JmImageDetail,
    JmAsyncDownloader,
    JmAsyncRuntime,
    JmDownloader,
    bind_jm_task_context,
    download_album,
    download_batch,
    download_batch_async,
    JTC,
    jm_task_context,
)


class Test_Cancellation(unittest.IsolatedAsyncioTestCase):

    def test_control_is_idempotent_and_visible_across_threads(self):
        control = DownloadControl()
        seen = []

        with jm_task_context(control=control):
            worker = bind_jm_task_context(
                lambda: seen.append(JTC.get_control())
            )
            thread = Thread(target=worker)
            thread.start()
            thread.join()

        self.assertEqual(seen, [control])
        self.assertFalse(control.is_cancelled)
        self.assertTrue(control.cancel(123))
        self.assertFalse(control.cancel('ignored second reason'))
        self.assertTrue(control.is_cancelled)
        self.assertEqual(control.reason, '123')

        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException) as caught:
                BaseDownloader.raise_if_cancelled()

        self.assertIs(caught.exception.control, control)
        self.assertEqual(caught.exception.reason, '123')
        self.assertEqual(
            caught.exception.context,
            {'control': control, 'reason': '123'},
        )

    def test_downloader_classmethod_is_overrideable(self):
        BaseDownloader.raise_if_cancelled()

        control = DownloadControl()
        control.cancel()
        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException):
                BaseDownloader.raise_if_cancelled()

        seen = []

        class CustomDownloader(BaseDownloader):

            @classmethod
            def raise_if_cancelled(cls) -> None:
                seen.append(cls)

        object.__new__(CustomDownloader).raise_if_cancelled()
        self.assertEqual(seen, [CustomDownloader])

    def test_exception_keeps_normal_jmcomic_constructor_shape(self):
        control = DownloadControl()
        exception = DownloadCancelledException(
            'explicit reason',
            {'control': control, 'reason': 'explicit reason'},
        )

        self.assertIs(exception.control, control)
        self.assertEqual(exception.reason, 'explicit reason')
        self.assertEqual(str(exception), 'explicit reason')

    def test_sync_api_uses_control_from_caller_context(self):
        control = DownloadControl()
        seen = []

        class ProbeDownloader:

            def __init__(self, _option):
                self.manifest_dict = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def add_features(self, _extra):
                pass

            def download_album(self, _album_id):
                seen.append(JTC.get_control())
                control.cancel('api probe')
                BaseDownloader.raise_if_cancelled()

        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException):
                download_album('123', option=object(), downloader=ProbeDownloader)

        self.assertEqual(seen, [control])

    def test_sync_batch_raises_cancellation_instead_of_failed_result(self):
        control = DownloadControl()

        def cancel_first(jmid, *_args, **_kwargs):
            control.cancel(f'stopped at {jmid}')
            BaseDownloader.raise_if_cancelled()

        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException):
                download_batch(cancel_first, ['123', '456'], option=object())

    def test_sync_batch_propagates_manual_cancellation_without_control(self):
        def stop(_jmid, *_args, **_kwargs):
            raise DownloadCancelledException('manual stop')

        with self.assertRaisesRegex(DownloadCancelledException, 'manual stop'):
            download_batch(stop, ['123'], option=object())

    async def test_empty_batches_do_not_invoke_downloader_cancellation(self):
        control = DownloadControl()
        control.cancel('already stopped')

        with jm_task_context(control=control):
            self.assertEqual(
                download_batch(lambda *_args: None, [], option=object()),
                set(),
            )
            self.assertEqual(
                await download_batch_async(lambda *_args: None, [], option=object()),
                set(),
            )

    async def test_async_batch_prefers_control_cancellation_over_task_cancellation(self):
        async def stop_differently(jmid, *_args, **_kwargs):
            if str(jmid) == '1':
                raise asyncio.CancelledError('external cancellation')
            raise DownloadCancelledException('control cancellation')

        with self.assertRaisesRegex(DownloadCancelledException, 'control cancellation'):
            await download_batch_async(stop_differently, ['1', '2'], option=object())

    async def test_async_batch_waits_for_cancelled_children_to_finish(self):
        ready = asyncio.Event()
        never = asyncio.Event()
        started = []
        finished = []

        async def wait_until_cancelled(jmid, *_args, **_kwargs):
            started.append(str(jmid))
            if len(started) == 2:
                ready.set()
            try:
                await never.wait()
            finally:
                await asyncio.sleep(0)
                finished.append(str(jmid))

        batch = asyncio.create_task(download_batch_async(
            wait_until_cancelled,
            ['1', '2'],
            option=object(),
        ))
        await ready.wait()
        batch.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await batch

        self.assertCountEqual(finished, ['1', '2'])

    def test_feature_chain_stops_at_cancellation_boundary(self):
        control = DownloadControl()
        option = Mock()
        downloader = BaseDownloader(option)
        first = Mock()
        second = Mock()
        first.should_invoke.return_value = True
        second.should_invoke.return_value = True
        first.invoke.side_effect = lambda *_args, **_kwargs: control.cancel('feature stop')
        downloader._feature_list = [first, second]

        with jm_task_context(download_type='album', control=control):
            with self.assertRaises(DownloadCancelledException):
                downloader._invoke_features_for('after_album', album=object())

        first.invoke.assert_called_once()
        second.invoke.assert_not_called()

    def test_sync_downloader_converts_client_failure_after_cancellation(self):
        control = DownloadControl()
        downloader = object.__new__(JmDownloader)
        downloader.client = Mock()

        def fail_after_cancel(_album_id):
            control.cancel('请求期间取消')
            raise RuntimeError('请求失败')

        downloader.client.get_album_detail.side_effect = fail_after_cancel

        with jm_task_context(control=control):
            with self.assertRaisesRegex(DownloadCancelledException, '请求期间取消'):
                downloader.download_album('123')

    async def test_async_downloader_converts_client_failure_after_cancellation(self):
        control = DownloadControl()
        downloader = object.__new__(JmAsyncDownloader)
        downloader.client = Mock()

        async def fail_after_cancel(_album_id):
            control.cancel('异步请求期间取消')
            raise RuntimeError('请求失败')

        downloader.client.get_album_detail = fail_after_cancel

        with jm_task_context(control=control):
            with self.assertRaisesRegex(DownloadCancelledException, '异步请求期间取消'):
                await downloader.download_album('123')

    async def test_control_cancellation_is_not_recorded_as_image_failure(self):
        control = DownloadControl()
        control.cancel('stop before image')
        downloader = object.__new__(JmAsyncDownloader)
        downloader.download_failed_image = []

        async def cancelled(_image):
            downloader.raise_if_cancelled()

        downloader._download_single_image = cancelled

        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException):
                await downloader._safe_download_image(object())

        self.assertEqual(downloader.download_failed_image, [])

    async def test_external_task_cancellation_is_not_swallowed(self):
        downloader = object.__new__(JmAsyncDownloader)

        async def wait_forever(_image):
            await asyncio.Event().wait()

        downloader._download_single_image = wait_forever
        task = asyncio.create_task(downloader._safe_download_image(object()))
        await asyncio.sleep(0)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_current_async_image_is_recorded_before_control_cancellation(self):
        control = DownloadControl()
        downloader = object.__new__(JmAsyncDownloader)
        downloader.option = Mock()
        downloader.client = Mock()
        downloader.client.get_jm_image = AsyncMock()
        downloader.client.get_jm_image.return_value.content = b'image'
        downloader._image_semaphore = asyncio.Semaphore(1)

        async def run_inline(func, *args):
            return func(*args)

        downloader._run_in_decode_pool = run_inline
        downloader._save_raw = Mock(side_effect=lambda *_args: control.cancel('save finished'))
        downloader.option.decide_image_filepath.return_value = 'image.jpg'
        downloader.option.decide_download_cache.return_value = False
        downloader.option.decide_download_image_decode.return_value = False

        image = Mock(spec=JmImageDetail)
        image.skip = False
        image.scramble_id = None
        image.download_url = 'https://example.invalid/image.jpg'
        image.index = 1
        image.from_photo = Mock()
        photo = image.from_photo
        album = photo.from_album
        photo.is_album.return_value = False
        downloader.download_success_dict = {album: {photo: []}}
        downloader.manifest_dict = {}
        downloader.begin_manifest(photo)
        downloader.before_image = AsyncMock()

        with patch('jmcomic.jm_async_downloader.os.path.exists', return_value=False):
            with jm_task_context(control=control):
                with self.assertRaises(DownloadCancelledException):
                    await downloader._download_single_image(image)

        self.assertEqual(downloader.finish_manifest(photo).image_filepath_list, ['image.jpg'])
        downloader._save_raw.assert_called_once()
        downloader.option.call_all_plugin.assert_not_called()

    def test_sync_image_saved_during_cancellation_is_in_manifest(self):
        control = DownloadControl()
        downloader = object.__new__(JmDownloader)
        downloader.option = Mock()
        downloader.option.decide_image_filepath.return_value = 'image.jpg'
        downloader.option.decide_download_cache.return_value = False
        downloader.option.decide_download_image_decode.return_value = False
        downloader.client = Mock()
        downloader.client.download_by_image_detail.side_effect = (
            lambda *_args, **_kwargs: control.cancel('save finished')
        )
        downloader.before_image = Mock()
        image = Mock(spec=JmImageDetail)
        image.skip = False
        image.index = 1
        image.from_photo = Mock()
        photo = image.from_photo
        album = photo.from_album
        photo.is_album.return_value = False
        downloader.download_success_dict = {album: {photo: []}}
        downloader.manifest_dict = {}
        downloader.begin_manifest(photo)

        with jm_task_context(control=control):
            with self.assertRaises(DownloadCancelledException):
                downloader.download_by_image_detail(image)

        self.assertEqual(downloader.finish_manifest(photo).image_filepath_list, ['image.jpg'])
        downloader.client.download_by_image_detail.assert_called_once()
        downloader.option.call_all_plugin.assert_not_called()

    async def test_cancelled_decode_logs_worker_failure_and_preserves_cancellation(self):
        future = Future()
        submitted = asyncio.Event()
        executor = Mock()

        def submit(*_args):
            submitted.set()
            return future

        executor.submit.side_effect = submit
        runtime = JmAsyncRuntime(decode_workers=1)
        downloader = object.__new__(JmAsyncDownloader)
        downloader._decode_worker = 1
        error = OSError('save failed')
        try:
            with patch.object(runtime, 'executor', return_value=executor):
                with patch('jmcomic.jm_async_downloader.jm_log') as log:
                    with jm_task_context(runtime=runtime):
                        task = asyncio.create_task(downloader._run_in_decode_pool(lambda: None))
                        await asyncio.wait_for(submitted.wait(), timeout=1)
                        task.cancel()
                        await asyncio.sleep(0)
                        future.set_exception(error)
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    log.assert_called_once_with('dler.cancel.drain.exception', error)
        finally:
            runtime.close()

    async def test_image_cancelled_while_waiting_for_semaphore_never_requests(self):
        control = DownloadControl()
        downloader = object.__new__(JmAsyncDownloader)
        downloader.option = Mock()
        downloader.client = Mock()
        downloader.client.get_jm_image = AsyncMock()
        downloader._image_semaphore = asyncio.Semaphore(1)
        await downloader._image_semaphore.acquire()
        downloader.option.decide_image_filepath.return_value = 'image.jpg'
        downloader.option.decide_download_cache.return_value = False
        downloader.option.decide_download_image_decode.return_value = False
        before_reached = asyncio.Event()

        async def before_image(_image, _path):
            before_reached.set()

        downloader.before_image = before_image
        downloader.after_image = AsyncMock()
        image = SimpleNamespace(
            skip=False,
            scramble_id=None,
            download_url='https://example.invalid/image.jpg',
        )

        with patch('jmcomic.jm_async_downloader.os.path.exists', return_value=False):
            with jm_task_context(control=control):
                task = asyncio.create_task(downloader._download_single_image(image))
                await asyncio.wait_for(before_reached.wait(), timeout=1)
                await asyncio.sleep(0)
                control.cancel('queued image')
                downloader._image_semaphore.release()
                with self.assertRaises(DownloadCancelledException):
                    await task

        downloader.client.get_jm_image.assert_not_awaited()

    async def test_photo_cancelled_while_waiting_for_semaphore_never_requests(self):
        control = DownloadControl()
        downloader = object.__new__(JmAsyncDownloader)
        downloader.option = Mock()
        downloader.option.decide_image_save_dir.return_value = 'photo'
        downloader.client = Mock()
        downloader.client.check_photo = AsyncMock()
        downloader._photo_semaphore = asyncio.Semaphore(1)
        await downloader._photo_semaphore.acquire()
        photo = SimpleNamespace()

        with jm_task_context(control=control):
            task = asyncio.create_task(downloader.download_by_photo_detail(photo))
            await asyncio.sleep(0)
            control.cancel('queued photo')
            downloader._photo_semaphore.release()
            with self.assertRaises(DownloadCancelledException):
                await task

        downloader.client.check_photo.assert_not_awaited()
