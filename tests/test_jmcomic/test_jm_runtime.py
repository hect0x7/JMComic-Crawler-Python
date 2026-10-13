import asyncio
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from jmcomic import (
    DownloadCancelledException,
    JmAsyncRuntime,
    JmRuntime,
    JmTempRuntime,
    JmSyncRuntime,
    download_batch,
    download_batch_async,
    JTC,
    jm_task_context,
)


class Test_Jm_Runtime(unittest.TestCase):

    def test_launcher_expands_arguments_and_returns_done_futures(self):
        runtime = JmSyncRuntime(album_workers=2)
        try:
            positional = runtime.multi_thread_launcher(
                [(1, 2), (3, 4)],
                lambda left, right: left + right,
                level='album',
            )
            keyword = runtime.multi_thread_launcher(
                [{'left': 5, 'right': 6}],
                lambda left, right: left + right,
                level='album',
            )

            self.assertEqual([3, 7], [future.result() for future in positional])
            self.assertEqual([11], [future.result() for future in keyword])
            self.assertTrue(all(future.done() for future in positional + keyword))
        finally:
            runtime.close()

    def test_launcher_can_return_without_waiting(self):
        started = threading.Event()
        release = threading.Event()
        runtime = JmSyncRuntime(album_workers=1)

        def blocked(_item):
            started.set()
            release.wait(timeout=2)

        try:
            futures = runtime.multi_thread_launcher(
                [1],
                blocked,
                False,
                level='album',
            )
            self.assertTrue(started.wait(timeout=1))
            self.assertFalse(futures[0].done())
        finally:
            release.set()
            runtime.close()

    def test_launcher_waits_for_all_tasks_and_keeps_worker_error_in_future(self):
        sibling_started = threading.Event()
        release_sibling = threading.Event()
        launcher_done = threading.Event()
        futures = []
        runtime = JmSyncRuntime(album_workers=2)

        def work(item):
            if item == 'error':
                raise ValueError('worker failed')
            sibling_started.set()
            release_sibling.wait(timeout=2)

        def launch():
            try:
                futures.extend(runtime.multi_thread_launcher(
                    ['error', 'sibling'],
                    work,
                    level='album',
                ))
            finally:
                launcher_done.set()

        thread = threading.Thread(target=launch)
        thread.start()
        try:
            self.assertTrue(sibling_started.wait(timeout=1))
            self.assertFalse(launcher_done.is_set())
            release_sibling.set()
            self.assertTrue(launcher_done.wait(timeout=1))
            self.assertEqual(2, len(futures))
            with self.assertRaisesRegex(ValueError, 'worker failed'):
                futures[0].result()
            self.assertIsNone(futures[1].result())
        finally:
            release_sibling.set()
            thread.join(timeout=1)
            runtime.close()

    def test_launcher_waits_for_submitted_tasks_when_submit_fails(self):
        first_started = threading.Event()
        release_first = threading.Event()
        launcher_done = threading.Event()
        raised = []

        class FailSecondSubmitExecutor(ThreadPoolExecutor):

            def __init__(self):
                super().__init__(max_workers=1)
                self.submit_count = 0

            def submit(self, fn, /, *args, **kwargs):
                self.submit_count += 1
                if self.submit_count == 2:
                    raise RuntimeError('submit failed')
                return super().submit(fn, *args, **kwargs)

        executor = FailSecondSubmitExecutor()
        runtime = JmSyncRuntime(album_executor=executor)

        def blocked(_item):
            first_started.set()
            release_first.wait(timeout=2)

        def launch():
            try:
                runtime.multi_thread_launcher(
                    [1, 2],
                    blocked,
                    level='album',
                )
            except BaseException as error:
                raised.append(error)
            finally:
                launcher_done.set()

        thread = threading.Thread(target=launch)
        thread.start()
        try:
            self.assertTrue(first_started.wait(timeout=1))
            self.assertFalse(launcher_done.is_set())
            release_first.set()
            self.assertTrue(launcher_done.wait(timeout=1))
            self.assertEqual(1, len(raised))
            self.assertIsInstance(raised[0], RuntimeError)
            self.assertEqual('submit failed', str(raised[0]))
        finally:
            release_first.set()
            thread.join(timeout=1)
            runtime.close()
            executor.shutdown(wait=True)

    def test_runtime_does_not_close_external_executor(self):
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            runtime = JmSyncRuntime(album_executor=executor)
            futures = runtime.multi_thread_launcher(
                [1, 2],
                lambda item: item * 2,
                level='album',
            )
            self.assertEqual([2, 4], [future.result() for future in futures])

            runtime.close()
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))
        finally:
            executor.shutdown(wait=True)

    def test_temp_runtime_uses_one_executor_without_level(self):
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            runtime = JmTempRuntime(executor=executor)
            futures = runtime.multi_thread_launcher(
                [1, 2],
                lambda item: item * 2,
            )
            self.assertEqual([2, 4], [future.result() for future in futures])

            runtime.close()
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))
        finally:
            executor.shutdown(wait=True)

    def test_sync_batch_does_not_create_or_inject_runtime_by_default(self):
        observed = []

        def download_one(jmid, *_args, **_kwargs):
            observed.append(JTC.get_runtime())
            return jmid

        self.assertEqual(
            {'1'},
            set(download_batch(download_one, ['1'], option=object())),
        )
        self.assertEqual(1, len(observed))
        self.assertIsNone(observed[0])

    def test_async_batch_does_not_create_or_inject_runtime_by_default(self):
        observed = []

        async def download_one(jmid, *_args, **_kwargs):
            observed.append(JTC.get_runtime())
            return jmid

        result = asyncio.run(download_batch_async(
            download_one,
            ['1'],
            option=object(),
        ))

        self.assertEqual({'1'}, set(result))
        self.assertEqual(1, len(observed))
        self.assertIsNone(observed[0])

    def test_sync_batch_collects_failure_after_siblings_finish(self):
        completed = []

        def download_one(jmid, *_args, **_kwargs):
            if jmid == '404':
                raise ValueError('missing')
            time.sleep(0.02)
            completed.append(jmid)
            return jmid

        result = download_batch(
            download_one,
            ['200', '404'],
            option=object(),
        )

        self.assertEqual({'200'}, set(result))
        self.assertEqual(['200'], completed)
        self.assertIsInstance(result.failed['404'], ValueError)

    def test_sync_batch_waits_for_siblings_before_raising_cancellation(self):
        barrier = threading.Barrier(2)
        completed = []

        def download_one(jmid, *_args, **_kwargs):
            barrier.wait(timeout=1)
            if jmid == '1':
                raise DownloadCancelledException('stop')
            time.sleep(0.02)
            completed.append(jmid)
            return jmid

        with ThreadPoolExecutor(max_workers=2) as executor:
            runtime = JmSyncRuntime(album_executor=executor)
            with jm_task_context(runtime=runtime):
                with self.assertRaisesRegex(DownloadCancelledException, 'stop'):
                    download_batch(
                        download_one,
                        ['1', '2'],
                        option=object(),
                    )

            self.assertEqual(['2'], completed)
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))

    def test_sync_runtime_supports_album_naming_and_rejects_shared_executor_with_deadlock_hint(self):
        runtime = JmSyncRuntime(album_workers=3, photo_workers=2, image_workers=10)
        try:
            self.assertEqual(3, runtime._workers['album'])
            self.assertEqual(2, runtime._workers['photo'])
            self.assertEqual(10, runtime._workers['image'])
            self.assertEqual(3, runtime.executor('album')._max_workers)
            # 严格拒绝过时的 'id' 层
            with self.assertRaises(ValueError):
                runtime.executor('id')
        finally:
            runtime.close()

        with ThreadPoolExecutor(max_workers=2) as shared_executor:
            with self.assertRaisesRegex(ValueError, 'starvation deadlock'):
                JmSyncRuntime(photo_executor=shared_executor, image_executor=shared_executor)

    def test_sync_runtime_unset_album_workers_does_not_fix_batch_pool(self):
        """CR-3 / Mode B: 当 JmSyncRuntime 未配置 album 层时，download_batch 不会固化 album 线程池，各批次独立"""
        runtime = JmSyncRuntime(image_workers=10)
        try:
            self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_ALBUM))
            self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_PHOTO))
            self.assertTrue(runtime.has_executor(JmRuntime.LEVEL_IMAGE))

            with jm_task_context(runtime=runtime):
                res1 = download_batch(lambda aid, *_: aid, ['1', '2'], option=object())
                self.assertEqual({'1', '2'}, set(res1))
                # 依然未配置 album executor，没有被污染
                self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_ALBUM))

                res2 = download_batch(lambda aid, *_: aid, ['3', '4', '5'], option=object())
                self.assertEqual({'3', '4', '5'}, set(res2))
                self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_ALBUM))
        finally:
            runtime.close()

    def test_runtime_level_constants_and_has_executor_behavior(self):
        self.assertEqual('album', JmRuntime.LEVEL_ALBUM)
        self.assertEqual('photo', JmRuntime.LEVEL_PHOTO)
        self.assertEqual('image', JmRuntime.LEVEL_IMAGE)
        self.assertEqual('decode', JmRuntime.LEVEL_DECODE)
        self.assertEqual('default', JmRuntime.LEVEL_DEFAULT)

        temp = JmTempRuntime(workers=2)
        try:
            self.assertTrue(temp.has_executor())
            self.assertTrue(temp.has_executor(JmRuntime.LEVEL_DEFAULT))
        finally:
            temp.close()

        async_rt = JmAsyncRuntime(decode_workers=4)
        try:
            self.assertTrue(async_rt.has_executor())
            self.assertTrue(async_rt.has_executor(JmRuntime.LEVEL_DECODE))
        finally:
            async_rt.close()


if __name__ == '__main__':
    unittest.main()
