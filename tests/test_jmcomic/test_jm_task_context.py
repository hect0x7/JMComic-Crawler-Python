import asyncio
import logging
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from jmcomic import (
    BaseDownloader,
    Feature,
    JmAsyncDownloader,
    JmDownloader,
    JmModuleConfig,
    JmOption,
    JmOptionPlugin,
    JM_TASK_CONTEXT,
    PhotoConcurrentFetcherProxy,
    PrettyFormatter,
    bind_jm_task_context,
    default_jm_logging,
    download_album,
    download_batch,
    download_batch_async,
    download_photo_async,
    get_jm_task_context,
    jm_log,
    jm_task_context,
    jm_logger,
)


class ListHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class Test_Jm_Task_Context(unittest.TestCase):

    def test_public_context_var_names_log_record_field(self):
        self.assertEqual('jm_task_context', JM_TASK_CONTEXT.name)

    def test_nested_context_restores_on_normal_and_exception_exit(self):
        self.assertEqual({}, get_jm_task_context())

        with jm_task_context(session_id='outer'):
            self.assertEqual({'session_id': 'outer'}, get_jm_task_context())
            with jm_task_context(session_id='inner', task_id='task'):
                self.assertEqual(
                    {'session_id': 'inner', 'task_id': 'task'},
                    get_jm_task_context(),
                )
            self.assertEqual({'session_id': 'outer'}, get_jm_task_context())

            with self.assertRaisesRegex(RuntimeError, 'stop'):
                with jm_task_context(task_id='failed'):
                    raise RuntimeError('stop')

            self.assertEqual({'session_id': 'outer'}, get_jm_task_context())

        self.assertEqual({}, get_jm_task_context())

    def test_bound_context_survives_thread_pool_and_does_not_leak(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with jm_task_context(session_id='A'):
                future_a = executor.submit(bind_jm_task_context(get_jm_task_context))
            with jm_task_context(session_id='B'):
                future_b = executor.submit(bind_jm_task_context(get_jm_task_context))

            empty = executor.submit(get_jm_task_context)

            self.assertEqual({'session_id': 'A'}, future_a.result())
            self.assertEqual({'session_id': 'B'}, future_b.result())
            self.assertEqual({}, empty.result())

    def test_bind_rejects_async_callable(self):
        async def async_work():
            return None

        with self.assertRaisesRegex(TypeError, 'synchronous callables'):
            bind_jm_task_context(async_work)

    def test_default_logger_and_custom_executors_can_read_context(self):
        handler = ListHandler()
        original_handlers = jm_logger.handlers[:]
        original_executor = JmModuleConfig.EXECUTOR_LOG
        jm_logger.handlers[:] = [handler]

        try:
            with jm_task_context(session_id='logger'):
                default_jm_logging('test.context', 'message')

            self.assertEqual(
                {'session_id': 'logger'},
                getattr(handler.records[0], JM_TASK_CONTEXT.name),
            )

            captured = []

            def executor_two_args(topic, msg):
                captured.append((topic, msg, get_jm_task_context()))

            JmModuleConfig.EXECUTOR_LOG = executor_two_args
            with jm_task_context(session_id='custom-2'):
                jm_log('test.custom', 'message')

            error = ValueError('failed')

            def executor_three_args(topic, msg, e):
                captured.append((topic, msg, e, get_jm_task_context()))

            JmModuleConfig.EXECUTOR_LOG = executor_three_args
            with jm_task_context(session_id='custom-3'):
                jm_log('test.custom.error', 'message', error)

            self.assertEqual(
                ('test.custom', 'message', {'session_id': 'custom-2'}),
                captured[0],
            )
            self.assertEqual(
                ('test.custom.error', 'message', error, {'session_id': 'custom-3'}),
                captured[1],
            )
        finally:
            JmModuleConfig.EXECUTOR_LOG = original_executor
            jm_logger.handlers[:] = original_handlers

    def test_pretty_formatter_uses_topic_colors(self):
        formatter = PrettyFormatter()

        def make_record(topic, context, level=logging.INFO):
            record = logging.LogRecord(
                name='jmcomic',
                level=level,
                pathname=__file__,
                lineno=1,
                msg=topic,
                args=(),
                exc_info=None,
            )
            record.topic = topic
            record.jm_task_context = context
            return record

        task_context = {
            'task_id': 'task-A',
            'download_type': 'album',
            'jm_id': '1',
        }
        self.assertTrue(formatter.format(
            make_record('album.before', task_context)
        ).startswith(formatter.TOPIC_COLORS['album']))
        self.assertTrue(formatter.format(
            make_record('image.before', task_context)
        ).startswith(formatter.TOPIC_COLORS['image']))

        self.assertTrue(formatter.format(
            make_record('image.failed', task_context, logging.ERROR)
        ).startswith(formatter.ERROR_COLOR))
        self.assertTrue(formatter.format(
            make_record('image.warning', task_context, logging.WARNING)
        ).startswith(formatter.WARN_COLOR))

    def test_public_downloads_add_task_context_to_downloader_logs(self):
        class FakeSyncDownloader:

            def __init__(self, _option):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def add_features(self, *_args):
                pass

            def download_album(self, album_id):
                jm_log('album.before', 'message')
                return album_id

            def raise_if_has_exception(self):
                pass

        class FakeAsyncDownloader:

            def __init__(self, _option):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

            def add_features(self, *_args):
                pass

            async def download_photo(self, photo_id):
                jm_log('photo.before', 'message')
                return photo_id

            def raise_if_has_exception(self):
                pass

        handler = ListHandler()
        original_handlers = jm_logger.handlers[:]
        jm_logger.handlers[:] = [handler]
        try:
            jm_log('plugin.usage_log.log', 'unrelated background log')
            with jm_task_context(session_id='session-1', task_id='task-1'):
                download_album(
                    '123',
                    option=object(),
                    downloader=FakeSyncDownloader,
                )
                asyncio.run(download_photo_async(
                    '456',
                    option=object(),
                    downloader=FakeAsyncDownloader,
                ))
        finally:
            jm_logger.handlers[:] = original_handlers

        task_records = [
            record
            for record in handler.records
            if (getattr(record, JM_TASK_CONTEXT.name, None) or {}).get('session_id') == 'session-1'
        ]
        self.assertEqual(
            ['album.before', 'photo.before'],
            [record.topic for record in task_records],
        )
        self.assertEqual(
            {
                'session_id': 'session-1',
                'task_id': 'task-1',
                'download_type': 'album',
                'jm_id': '123',
            },
            task_records[0].jm_task_context,
        )
        self.assertEqual(
            {
                'session_id': 'session-1',
                'task_id': 'task-1',
                'download_type': 'photo',
                'jm_id': '456',
            },
            task_records[1].jm_task_context,
        )

    def test_plugin_invocation_can_read_current_task_context(self):
        observed = []

        class TaskAwarePlugin(JmOptionPlugin):
            plugin_key = 'test_task_aware'

            def invoke(self):
                observed.append(self.jm_task_context)
                self.log('plugin-message')

        option = object.__new__(JmOption)
        handler = ListHandler()
        original_handlers = jm_logger.handlers[:]
        jm_logger.handlers[:] = [handler]
        try:
            with jm_task_context(session_id='plugin-session', task_id='plugin-task'):
                option.invoke_plugin(TaskAwarePlugin, None, {}, {})
        finally:
            jm_logger.handlers[:] = original_handlers

        self.assertEqual([{
            'session_id': 'plugin-session',
            'task_id': 'plugin-task',
        }], observed)
        self.assertEqual(
            [
                'plugin.invoke',
                'plugin.test_task_aware',
            ],
            [record.topic for record in handler.records],
        )
        self.assertEqual(
            [{
                'session_id': 'plugin-session',
                'task_id': 'plugin-task',
            }] * 2,
            [record.jm_task_context for record in handler.records],
        )

    def test_feature_invocation_can_read_current_task_context(self):
        observed = []

        class TaskAwareFeature(Feature):

            def invoke(self, _option, feature_from, when, **_kwargs):
                observed.append((feature_from, when, self.jm_task_context))

        downloader = BaseDownloader(object())
        downloader.add_features(TaskAwareFeature(), 'download_album')

        with jm_task_context(session_id='feature-session', task_id='feature-task'):
            downloader._invoke_features_for('after_album')

        self.assertEqual([(
            'download_album',
            'after_album',
            {
                'session_id': 'feature-session',
                'task_id': 'feature-task',
            },
        )], observed)

    def test_sync_batch_binds_parent_and_item_context(self):
        def fake_download(jmid, _option, _downloader, **_kwargs):
            context = get_jm_task_context()
            return (
                str(jmid),
                context['session_id'],
                context['download_type'],
                context['jm_id'],
            )

        with jm_task_context(session_id='sync-batch'):
            result = download_batch(fake_download, ['1', '2'], option=object())

        self.assertEqual(
            {
                ('1', 'sync-batch', 'fake_download', '1'),
                ('2', 'sync-batch', 'fake_download', '2'),
            },
            set(result),
        )
        self.assertEqual({}, get_jm_task_context())

    def test_concurrent_sync_sessions_do_not_cross(self):
        barrier = threading.Barrier(2)

        def fake_download(jmid, _option, _downloader, **_kwargs):
            barrier.wait(timeout=2)
            context = get_jm_task_context()
            return context['session_id'], context['jm_id'], str(jmid)

        def run_session(session_id, jmid):
            with jm_task_context(session_id=session_id):
                return download_batch(
                    fake_download,
                    [jmid],
                    option=object(),
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(run_session, 'session-A', '1')
            future_b = executor.submit(run_session, 'session-B', '2')

            self.assertEqual(
                {('session-A', '1', '1')},
                set(future_a.result()),
            )
            self.assertEqual(
                {('session-B', '2', '2')},
                set(future_b.result()),
            )

    def test_batch_failure_log_keeps_item_context(self):
        handler = ListHandler()
        original_handlers = jm_logger.handlers[:]
        jm_logger.handlers[:] = [handler]

        def fail(jmid, _option, _downloader, **_kwargs):
            raise ValueError(f'failed-{jmid}')

        try:
            with jm_task_context(session_id='failed-session'):
                result = download_batch(fail, ['404'], option=object())
        finally:
            jm_logger.handlers[:] = original_handlers

        self.assertIn('404', result.failed)
        self.assertEqual(1, len(handler.records))
        self.assertEqual(
            {
                'session_id': 'failed-session',
                'download_type': 'fail',
                'jm_id': '404',
            },
            handler.records[0].jm_task_context,
        )

    def test_sync_downloader_propagates_both_threading_branches(self):
        downloader = object.__new__(JmDownloader)
        BaseDownloader.__init__(downloader, object())

        for count_batch in (3, 1):
            observed = Queue()

            with jm_task_context(session_id=f'workers-{count_batch}'):
                downloader.execute_on_condition(
                    iter_objs=[1, 2, 3],
                    apply=lambda _item: observed.put(get_jm_task_context()),
                    count_batch=count_batch,
                )

            contexts = [observed.get_nowait() for _ in range(3)]
            self.assertEqual(
                [{
                    'session_id': f'workers-{count_batch}',
                }] * 3,
                contexts,
            )

    def test_async_batch_and_decode_pool_propagate_context(self):
        async def run_test():
            async def fake_download(jmid, _option, _downloader, **_kwargs):
                await asyncio.sleep(0)
                context = get_jm_task_context()
                return (
                    str(jmid),
                    context['session_id'],
                    context['download_type'],
                    context['jm_id'],
                )

            with jm_task_context(session_id='async-batch'):
                batch_result = await download_batch_async(
                    fake_download,
                    ['1', '2'],
                    option=object(),
                )

            downloader = object.__new__(JmAsyncDownloader)
            downloader._decode_pool = ThreadPoolExecutor(max_workers=1)
            try:
                with jm_task_context(session_id='decode-pool'):
                    executor_context = await downloader._run_in_decode_pool(
                        get_jm_task_context
                    )

                loop = asyncio.get_running_loop()
                leaked_context = await loop.run_in_executor(
                    downloader._decode_pool,
                    get_jm_task_context,
                )
            finally:
                downloader.shutdown()

            return batch_result, executor_context, leaked_context

        batch_result, executor_context, leaked_context = asyncio.run(run_test())

        self.assertEqual(
            {
                ('1', 'async-batch', 'fake_download', '1'),
                ('2', 'async-batch', 'fake_download', '2'),
            },
            set(batch_result),
        )
        self.assertEqual({'session_id': 'decode-pool'}, executor_context)
        self.assertEqual({}, leaked_context)

    def test_photo_concurrent_proxy_propagates_context(self):
        class FakeClient:
            pass

        proxy = PhotoConcurrentFetcherProxy(FakeClient(), max_workers=1)
        try:
            with jm_task_context(session_id='client-proxy'):
                future = proxy.get_future('context', get_jm_task_context)

            self.assertEqual({'session_id': 'client-proxy'}, future.result())
        finally:
            proxy.executors.shutdown(wait=True)


if __name__ == '__main__':
    unittest.main()
