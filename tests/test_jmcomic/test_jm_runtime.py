import asyncio
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from jmcomic import (
    DownloadCancelledException,
    JmAsyncRuntime,
    JmSimpleRuntime,
    JmSyncRuntime,
    download_batch,
    download_batch_async,
    get_jm_runtime,
    jm_task_context,
)


class Test_Jm_Runtime(unittest.TestCase):

    def test_launcher_expands_arguments_and_returns_done_futures(self):
        runtime = JmSyncRuntime(id_workers=2)
        try:
            positional = runtime.multi_thread_launcher(
                [(1, 2), (3, 4)],
                lambda left, right: left + right,
                level='id',
            )
            keyword = runtime.multi_thread_launcher(
                [{'left': 5, 'right': 6}],
                lambda left, right: left + right,
                level='id',
            )

            self.assertEqual([3, 7], [future.result() for future in positional])
            self.assertEqual([11], [future.result() for future in keyword])
            self.assertTrue(all(future.done() for future in positional + keyword))
        finally:
            runtime.close()

    def test_launcher_can_return_without_waiting(self):
        started = threading.Event()
        release = threading.Event()
        runtime = JmSyncRuntime(id_workers=1)

        def blocked(_item):
            started.set()
            release.wait(timeout=2)

        try:
            futures = runtime.multi_thread_launcher(
                [1],
                blocked,
                False,
                level='id',
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
        runtime = JmSyncRuntime(id_workers=2)

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
                    level='id',
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
        runtime = JmSyncRuntime(id_executor=executor)

        def blocked(_item):
            first_started.set()
            release_first.wait(timeout=2)

        def launch():
            try:
                runtime.multi_thread_launcher(
                    [1, 2],
                    blocked,
                    level='id',
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
            runtime = JmSyncRuntime(id_executor=executor)
            futures = runtime.multi_thread_launcher(
                [1, 2],
                lambda item: item * 2,
                level='id',
            )
            self.assertEqual([2, 4], [future.result() for future in futures])

            runtime.close()
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))
        finally:
            executor.shutdown(wait=True)

    def test_simple_runtime_uses_one_executor_without_level(self):
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            runtime = JmSimpleRuntime(executor=executor)
            futures = runtime.multi_thread_launcher(
                [1, 2],
                lambda item: item * 2,
            )
            self.assertEqual([2, 4], [future.result() for future in futures])

            runtime.close()
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))
        finally:
            executor.shutdown(wait=True)

    def test_sync_batch_explicitly_closes_runtime_created_by_api(self):
        observed = []

        def download_one(jmid, *_args, **_kwargs):
            observed.append(get_jm_runtime())
            return jmid

        self.assertEqual(
            {'1'},
            set(download_batch(download_one, ['1'], option=object())),
        )
        self.assertEqual(1, len(observed))
        with self.assertRaisesRegex(RuntimeError, 'JmRuntime is closed'):
            observed[0].executor('id', 1)

    def test_async_batch_explicitly_closes_runtime_created_by_api(self):
        observed = []

        async def download_one(jmid, *_args, **_kwargs):
            observed.append(get_jm_runtime())
            return jmid

        result = asyncio.run(download_batch_async(
            download_one,
            ['1'],
            option=object(),
        ))

        self.assertEqual({'1'}, set(result))
        self.assertEqual(1, len(observed))
        self.assertIsInstance(observed[0], JmAsyncRuntime)
        with self.assertRaisesRegex(RuntimeError, 'JmRuntime is closed'):
            observed[0].executor('decode', 1)

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
            runtime = JmSyncRuntime(id_executor=executor)
            with jm_task_context(runtime=runtime):
                with self.assertRaisesRegex(DownloadCancelledException, 'stop'):
                    download_batch(
                        download_one,
                        ['1', '2'],
                        option=object(),
                    )

            self.assertEqual(['2'], completed)
            self.assertEqual(9, executor.submit(lambda: 9).result(timeout=1))


if __name__ == '__main__':
    unittest.main()
