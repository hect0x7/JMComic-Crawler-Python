import asyncio
import logging
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from unittest.mock import patch

from jmcomic import (
    BaseDownloader,
    BatchResult,
    JmAsyncRuntime,
    DownloadManifest,
    DownloadControl,
    DownloadCancelledException,
    Feature,
    JTC,
    JmAsyncDownloader,
    JmDownloader,
    JmModuleConfig,
    JmOption,
    JmOptionPlugin,
    JmRuntime,
    JM_TASK_CONTEXT,
    PhotoConcurrentFetcherProxy,
    PrettyFormatter,
    JmTempRuntime,
    JmSyncRuntime,
    bind_jm_task_context,
    default_jm_logging,
    download_album,
    download_batch,
    download_batch_async,
    download_photo_async,
    jm_log,
    JmTaskContext,
    jm_task_context,
    jm_logger,
)


class ListHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class ExecutorProbeDownloader(JmDownloader):

    def __init__(self):
        BaseDownloader.__init__(self, object())
        self.work = lambda _item: None

    def download_by_image_detail(self, image):
        self.work(image)


class PhotoDetails(list):

    @staticmethod
    def is_album():
        return False


class Test_Jm_Task_Context(unittest.TestCase):

    def test_context_exposes_runtime_and_borrows_executor(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            runtime = JmSyncRuntime(album_executor=executor)
            with jm_task_context(task_id='job-42', runtime=runtime):
                self.assertEqual(
                    JTC.get_context(),
                    {'task_id': 'job-42', 'runtime': runtime},
                )
                raw_context = JM_TASK_CONTEXT.get()
                self.assertEqual(raw_context['task_id'], 'job-42')
                self.assertIs(raw_context['runtime'], runtime)
                with self.assertRaises(TypeError):
                    raw_context['mutable'] = True
                self.assertIs(JTC.get_runtime(), runtime)
                with jm_task_context(jm_id='123'):
                    self.assertEqual(
                        JTC.get_context(),
                        {
                            'task_id': 'job-42',
                            'runtime': runtime,
                            'jm_id': '123',
                        },
                    )

                public_bound = executor.submit(bind_jm_task_context(
                    lambda: (
                        JTC.get_context(),
                        JTC.get_runtime(),
                    )
                ))
                self.assertEqual(
                    public_bound.result(timeout=1),
                    ({'task_id': 'job-42', 'runtime': runtime}, runtime),
                )

            self.assertEqual(executor.submit(lambda: 7).result(timeout=1), 7)

    def test_option_is_public_and_propagated(self):
        option = object()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with jm_task_context(option=option, task_id='job-42'):
                self.assertEqual(
                    JTC.get_context(),
                    {'task_id': 'job-42', 'option': option},
                )
                self.assertIs(JTC.get_option(), option)
                future = executor.submit(bind_jm_task_context(JTC.get_option))

            self.assertIs(future.result(timeout=1), option)

        self.assertIsNone(JTC.get_option())

    def test_none_option_runtime_and_nested_runtime_rules(self):
        with jm_task_context(option=None, runtime=None, task_id='job-42'):
            self.assertEqual(JTC.get_context(), {'task_id': 'job-42'})
            self.assertIsNone(JTC.get_option())
            self.assertIsNone(JTC.get_runtime())

        outer = JmSyncRuntime(album_workers=1)
        inner = JmSyncRuntime(album_workers=1)
        try:
            with jm_task_context(runtime=outer):
                self.assertIs(JTC.get_runtime(), outer)
                with jm_task_context(runtime=inner):
                    self.assertIs(JTC.get_runtime(), inner)
                self.assertIs(JTC.get_runtime(), outer)
        finally:
            outer.close()
            inner.close()

        runtime = JmSyncRuntime(album_workers=1)
        with jm_task_context(runtime=runtime):
            pass
        futures = runtime.multi_thread_launcher(
            [1],
            lambda item: item,
            level='album',
        )
        self.assertEqual(1, futures[0].result())
        runtime.close()
        with self.assertRaisesRegex(RuntimeError, 'JmRuntime is closed'):
            runtime.multi_thread_launcher(
                [1],
                lambda item: item,
                level='album',
            )

    def test_runtime_configuration_is_explicit_and_validated(self):
        with self.assertRaisesRegex(TypeError, 'runtime must be'):
            with jm_task_context(runtime='metadata'):
                self.fail('runtime must be a Runtime instance')

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
                JmSyncRuntime(album_workers=1, album_executor=executor)
            with self.assertRaisesRegex(ValueError, 'different executor'):
                JmSyncRuntime(album_executor=executor, photo_executor=executor)
            with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
                JmAsyncRuntime(decode_workers=1, decode_executor=executor)
            with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
                JmTempRuntime(workers=1, executor=executor)

        with self.assertRaisesRegex(ValueError, 'positive integer'):
            JmSyncRuntime(photo_workers=0)
        with self.assertRaisesRegex(ValueError, 'positive integer'):
            JmAsyncRuntime(decode_workers=True)
        with self.assertRaisesRegex(ValueError, 'positive integer'):
            JmTempRuntime(workers=0)

    def test_sync_runtime_reuses_one_album_pool_across_batches(self):
        worker_threads = []

        def fake_download(jmid, _option, _downloader, **_kwargs):
            worker_threads.append(threading.get_ident())
            return str(jmid)

        runtime = JmSyncRuntime(album_workers=1, photo_workers=1, image_workers=1)
        try:
            with jm_task_context(runtime=runtime):
                self.assertEqual(
                    {'1', '2'},
                    set(download_batch(fake_download, ['1', '2'], option=object())),
                )
                self.assertEqual(
                    {'3'},
                    set(download_batch(fake_download, ['3'], option=object())),
                )

            self.assertEqual(1, len(set(worker_threads)))
        finally:
            runtime.close()

    def test_sync_runtime_has_executor_and_on_demand_initialization(self):
        with ThreadPoolExecutor(max_workers=1) as album_executor:
            runtime = JmSyncRuntime(album_executor=album_executor)
            try:
                self.assertTrue(runtime.has_executor(JmRuntime.LEVEL_ALBUM))
                self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_PHOTO))
                self.assertFalse(runtime.has_executor(JmRuntime.LEVEL_IMAGE))

                with jm_task_context(runtime=runtime):
                    photo_futures = runtime.multi_thread_launcher(
                        [1, 2],
                        lambda item: item * 2,
                        level=JmRuntime.LEVEL_PHOTO,
                    )
                    self.assertEqual(
                        [future.result() for future in photo_futures],
                        [2, 4],
                    )
                    self.assertTrue(runtime.has_executor(JmRuntime.LEVEL_PHOTO))

                    image_futures = runtime.multi_thread_launcher(
                        [1],
                        lambda item: item + 1,
                        level=JmRuntime.LEVEL_IMAGE,
                    )
                    self.assertEqual(
                        [future.result() for future in image_futures],
                        [2],
                    )
                    self.assertTrue(runtime.has_executor(JmRuntime.LEVEL_IMAGE))
            finally:
                runtime.close()

            self.assertEqual(album_executor.submit(lambda: 5).result(timeout=1), 5)

    def test_task_context_class_alias_and_nested_runtime_shadowing(self):
        self.assertIs(jm_task_context, JmTaskContext)
        rt1 = JmSyncRuntime(album_workers=1)
        rt2 = JmSyncRuntime(album_workers=2)
        try:
            self.assertIsNone(JTC.get_runtime())
            with JmTaskContext(runtime=rt1):
                self.assertIs(JTC.get_runtime(), rt1)
                with jm_task_context(runtime=rt2):
                    self.assertIs(JTC.get_runtime(), rt2)
                self.assertIs(JTC.get_runtime(), rt1)
            self.assertIsNone(JTC.get_runtime())
        finally:
            rt1.close()
            rt2.close()

    def test_download_control_is_propagated_by_public_binder(self):
        control = DownloadControl()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with jm_task_context(control=control):
                future = executor.submit(bind_jm_task_context(JTC.get_control))

            self.assertIs(future.result(timeout=1), control)
            self.assertIsNone(executor.submit(JTC.get_control).result(timeout=1))

        self.assertTrue(control.cancel('user requested'))
        self.assertFalse(control.cancel('ignored'))
        self.assertTrue(control.is_cancelled)
        self.assertEqual(control.reason, 'user requested')

    def test_public_context_var_names_log_record_field(self):
        self.assertEqual('jm_task_context', JM_TASK_CONTEXT.name)

    def test_nested_context_restores_on_normal_and_exception_exit(self):
        self.assertEqual({}, JTC.get_context())

        with jm_task_context(session_id='outer'):
            self.assertEqual({'session_id': 'outer'}, JTC.get_context())
            with jm_task_context(session_id='inner', task_id='task'):
                self.assertEqual(
                    {'session_id': 'inner', 'task_id': 'task'},
                    JTC.get_context(),
                )
            self.assertEqual({'session_id': 'outer'}, JTC.get_context())

            with self.assertRaisesRegex(RuntimeError, 'stop'):
                with jm_task_context(task_id='failed'):
                    raise RuntimeError('stop')

            self.assertEqual({'session_id': 'outer'}, JTC.get_context())

        self.assertEqual({}, JTC.get_context())

    def test_bound_context_survives_thread_pool_and_does_not_leak(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with jm_task_context(session_id='A'):
                future_a = executor.submit(bind_jm_task_context(JTC.get_context))
            with jm_task_context(session_id='B'):
                future_b = executor.submit(bind_jm_task_context(JTC.get_context))

            empty = executor.submit(JTC.get_context)

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
                captured.append((topic, msg, JTC.get_context()))

            JmModuleConfig.EXECUTOR_LOG = executor_two_args
            with jm_task_context(session_id='custom-2'):
                jm_log('test.custom', 'message')

            error = ValueError('failed')

            def executor_three_args(topic, msg, e):
                captured.append((topic, msg, e, JTC.get_context()))

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
        class AlbumDetail:
            duration = None

            @staticmethod
            def is_album():
                return True

        class PhotoDetail:
            duration = None
            from_album = object()

            @staticmethod
            def is_album():
                return False

        class FakeSyncDownloader(BaseDownloader):

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def download_album(self, _album_id):
                detail = AlbumDetail()
                self.begin_manifest(detail)
                try:
                    jm_log('album.before', 'message')
                finally:
                    self.finish_manifest(detail)
                return detail

        class FakeAsyncDownloader(BaseDownloader):

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                pass

            async def download_photo(self, _photo_id):
                detail = PhotoDetail()
                self.begin_manifest(detail)
                try:
                    jm_log('photo.before', 'message')
                finally:
                    self.finish_manifest(detail)
                return detail

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
        album_context = task_records[0].jm_task_context
        photo_context = task_records[1].jm_task_context
        self.assertEqual(
            {
                'session_id': 'session-1',
                'task_id': 'task-1',
                'download_type': 'album',
                'jm_id': '123',
            },
            {key: album_context[key] for key in ('session_id', 'task_id', 'download_type', 'jm_id')},
        )
        self.assertEqual(
            {
                'session_id': 'session-1',
                'task_id': 'task-1',
                'download_type': 'photo',
                'jm_id': '456',
            },
            {key: photo_context[key] for key in ('session_id', 'task_id', 'download_type', 'jm_id')},
        )
        self.assertIsInstance(album_context.get('task_started_at'), float)
        self.assertIsInstance(photo_context.get('task_started_at'), float)
        self.assertNotIn('runtime', album_context)
        self.assertNotIn('runtime', photo_context)

    def test_sync_result_duration_uses_task_context_and_finishes_after_downloader_exit(self):
        clock = {'now': 10.0}
        observed_contexts = []
        observed_options = []
        option = object()

        class Detail:
            duration = 99.0

            @staticmethod
            def is_album():
                return True

        class FakeDownloader(BaseDownloader):

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                clock['now'] = 20.0

            def download_album(self, _album_id):
                detail = Detail()
                self.begin_manifest(detail)
                try:
                    observed_contexts.append(JTC.get_context())
                    observed_options.append(JTC.get_option())
                finally:
                    self.finish_manifest(detail)
                return detail

        with patch('jmcomic.api.perf_counter', side_effect=lambda: clock['now'], create=True):
            result = download_album('123', option=option, downloader=FakeDownloader)

        self.assertEqual(10.0, observed_contexts[0].get('task_started_at'))
        self.assertEqual(10.0, result.manifest.duration)
        self.assertEqual(10.0, result.duration)
        self.assertEqual(99.0, result.detail.duration)
        self.assertEqual([option], observed_options)
        self.assertEqual({}, JTC.get_context())
        self.assertIsNone(JTC.get_option())

    def test_async_result_duration_uses_task_context_and_finishes_after_downloader_exit(self):
        async def run_test():
            clock = {'now': 100.0}
            observed_contexts = []

            class Detail:
                duration = 99.0
                from_album = object()

                @staticmethod
                def is_album():
                    return False

            class FakeDownloader(BaseDownloader):

                async def __aenter__(self):
                    observed_contexts.append(JTC.get_context())
                    return self

                async def __aexit__(self, *_args):
                    clock['now'] = 130.0

                async def download_photo(self, _photo_id):
                    detail = Detail()
                    self.begin_manifest(detail)
                    self.finish_manifest(detail)
                    return detail

            with patch('jmcomic.api.perf_counter', side_effect=lambda: clock['now'], create=True):
                result = await download_photo_async('456', option=object(), downloader=FakeDownloader)

            return result, observed_contexts

        result, observed_contexts = asyncio.run(run_test())

        self.assertEqual(100.0, observed_contexts[0].get('task_started_at'))
        self.assertEqual(30.0, result.manifest.duration)
        self.assertEqual(30.0, result.duration)
        self.assertEqual(99.0, result.detail.duration)
        self.assertEqual({}, JTC.get_context())

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

            def invoke(self, _option, when, **_kwargs):
                observed.append((when, self.jm_task_context))

        downloader = BaseDownloader(object())

        with jm_task_context(
                session_id='feature-session',
                task_id='feature-task',
                download_type='album',
        ):
            downloader.add_features(TaskAwareFeature())
            downloader._invoke_features_for('after_album')

        self.assertEqual([(
            'after_album',
            {
                'session_id': 'feature-session',
                'task_id': 'feature-task',
                'download_type': 'album',
            },
        )], observed)

    def test_add_features_requires_download_type_context(self):
        downloader = BaseDownloader(object())

        with self.assertRaisesRegex(Exception, 'Feature 注册与执行必须位于下载任务上下文中'):
            downloader.add_features(Feature())

    def test_feature_invocation_requires_download_type_context(self):
        downloader = BaseDownloader(object())

        with jm_task_context(download_type='album'):
            downloader.add_features(Feature())

        with self.assertRaisesRegex(Exception, 'Feature 注册与执行必须位于下载任务上下文中'):
            downloader._invoke_features_for('after_album')

    def test_plugin_feature_uses_download_type_context(self):
        feature = Feature.export_pdf

        with jm_task_context(download_type='album'):
            self.assertTrue(feature.should_invoke('after_album'))
            self.assertFalse(feature.should_invoke('after_photo'))

        with jm_task_context(download_type='photo'):
            self.assertTrue(feature.should_invoke('after_photo'))
            self.assertFalse(feature.should_invoke('after_album'))

    def test_sync_batch_binds_parent_and_item_context(self):
        def fake_download(jmid, _option, _downloader, **_kwargs):
            context = JTC.get_context()
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
                ('1', 'sync-batch', 'batch', '1'),
                ('2', 'sync-batch', 'batch', '2'),
            },
            set(result),
        )
        self.assertEqual({}, JTC.get_context())

    def test_concurrent_sync_sessions_do_not_cross(self):
        barrier = threading.Barrier(2)

        def fake_download(jmid, _option, _downloader, **_kwargs):
            barrier.wait(timeout=2)
            context = JTC.get_context()
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

        option = object()
        try:
            with jm_task_context(session_id='failed-session'):
                result = download_batch(fail, ['404'], option=option)
        finally:
            jm_logger.handlers[:] = original_handlers

        self.assertIn('404', result.failed)
        batch_failure_records = [
            record
            for record in handler.records
            if getattr(record, 'topic', None) == 'batch.failed'
        ]
        self.assertEqual(1, len(batch_failure_records))
        log_context = batch_failure_records[0].jm_task_context
        self.assertEqual(
            {
                'session_id': 'failed-session',
                'download_type': 'batch',
                'jm_id': '404',
            },
            {
                key: log_context[key]
                for key in ('session_id', 'download_type', 'jm_id')
            },
        )
        self.assertIs(log_context['option'], option)
        self.assertNotIn('runtime', log_context)

    def test_sync_downloader_uses_and_closes_temporary_temp_runtime(self):
        downloader = object.__new__(JmDownloader)
        BaseDownloader.__init__(downloader, object())
        created = []

        class ProbeRuntime(JmTempRuntime):

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                created.append(self)

        for count_batch in (3, 1):
            observed = Queue()

            with patch('jmcomic.jm_downloader.JmTempRuntime', ProbeRuntime):
                with jm_task_context(session_id=f'workers-{count_batch}'):
                    downloader.execute_on_condition(
                        iter_objs=[1, 2, 3],
                        apply=lambda _item: observed.put(JTC.get_context()),
                        count_batch=count_batch,
                    )

            contexts = [observed.get_nowait() for _ in range(3)]
            self.assertEqual(
                [f'workers-{count_batch}'] * 3,
                [context['session_id'] for context in contexts],
            )
            self.assertTrue(all('runtime' not in context for context in contexts))
            self.assertTrue(all('option' not in context for context in contexts))
            with self.assertRaisesRegex(RuntimeError, 'JmRuntime is closed'):
                created[-1].executor()

    def test_async_batch_and_decode_pool_propagate_context(self):
        async def run_test():
            async def fake_download(jmid, _option, _downloader, **_kwargs):
                await asyncio.sleep(0)
                context = JTC.get_context()
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

            with ThreadPoolExecutor(max_workers=1) as decode_executor:
                runtime = JmAsyncRuntime(decode_executor=decode_executor)
                with jm_task_context(session_id='decode-pool'):
                    with jm_task_context(runtime=runtime):
                        future = runtime.executor(
                            JmRuntime.LEVEL_DECODE,
                        ).submit(
                            bind_jm_task_context(JTC.get_context),
                        )
                        executor_context = await asyncio.wrap_future(future)

                loop = asyncio.get_running_loop()
                leaked_context = await loop.run_in_executor(
                    decode_executor,
                    JTC.get_context,
                )

            return batch_result, executor_context, leaked_context

        batch_result, executor_context, leaked_context = asyncio.run(run_test())

        self.assertEqual(
            {
                ('1', 'async-batch', 'batch', '1'),
                ('2', 'async-batch', 'batch', '2'),
            },
            set(batch_result),
        )
        self.assertEqual('decode-pool', executor_context['session_id'])
        self.assertIsInstance(executor_context['runtime'], JmAsyncRuntime)
        self.assertEqual({}, leaked_context)

    def test_photo_concurrent_proxy_propagates_context(self):
        class FakeClient:
            pass

        proxy = PhotoConcurrentFetcherProxy(FakeClient(), max_workers=1)
        try:
            with jm_task_context(session_id='client-proxy'):
                future = proxy.get_future('context', JTC.get_context)

            self.assertEqual({'session_id': 'client-proxy'}, future.result())
        finally:
            proxy.executors.shutdown(wait=True)

    def test_sync_runtime_executor_capacity_controls_image_concurrency(self):
        downloader = ExecutorProbeDownloader()
        lock = threading.Lock()
        active = 0
        maximum = 0

        def limited_work(_item):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1

        downloader.work = limited_work
        downloader.do_filter = lambda details: list(details)
        with ThreadPoolExecutor(max_workers=2) as executor:
            runtime = JmSyncRuntime(image_executor=executor)
            with jm_task_context(runtime=runtime):
                downloader.execute_on_condition(
                    PhotoDetails(range(8)),
                    downloader.download_by_image_detail,
                    count_batch=8,
                    level='image',
                )
            runtime.close()
            self.assertEqual(executor.submit(lambda: 1).result(timeout=1), 1)

        self.assertEqual(maximum, 2)

    def test_async_runtime_borrows_shared_executor(self):
        async def scenario():
            with ThreadPoolExecutor(max_workers=1) as executor:
                runtime = JmAsyncRuntime(decode_executor=executor)
                with jm_task_context(session_id='async-runtime', runtime=runtime):
                    future = runtime.executor(
                        JmRuntime.LEVEL_DECODE,
                    ).submit(
                        bind_jm_task_context(
                            lambda: (8, JTC.get_context()['session_id'])
                        ),
                    )
                    value = await asyncio.wrap_future(future)

                self.assertEqual(value, (8, 'async-runtime'))
                self.assertEqual(executor.submit(lambda: 9).result(timeout=1), 9)

        asyncio.run(scenario())

    def test_jtc_facade_getters(self):
        # 根作用域无状态
        self.assertIsNone(JTC.get_runtime())
        self.assertIsNone(JTC.get_option())
        self.assertIsNone(JTC.get_control())
        self.assertEqual(JTC.get_context(), {})

        runtime = JmSyncRuntime()
        option = object()
        control = DownloadControl()

        try:
            with jm_task_context(runtime=runtime, option=option, control=control, custom_field='val'):
                self.assertIs(JTC.get_runtime(), runtime)
                self.assertIs(JTC.get_option(), option)
                self.assertIs(JTC.get_control(), control)
                ctx = JTC.get_context()
                self.assertIs(ctx['runtime'], runtime)
                self.assertIs(ctx['option'], option)
                self.assertIs(ctx['control'], control)
                self.assertEqual(ctx['custom_field'], 'val')
        finally:
            runtime.close()

        # 退出作用域后恢复
        self.assertIsNone(JTC.get_runtime())
        self.assertIsNone(JTC.get_option())
        self.assertIsNone(JTC.get_control())

    def test_runtime_auto_bind_context_and_close_rules(self):
        # 1. 验证 JmSyncRuntime 自动绑定上下文并在退出后关闭自建池
        self.assertIsNone(JTC.get_runtime())
        with JmSyncRuntime(album_workers=2) as runtime:
            self.assertIs(JTC.get_runtime(), runtime)
            self.assertEqual(JTC.get_context()['runtime'], runtime)
            # 内部嵌套 jm_task_context(runtime=runtime) 不报错
            with jm_task_context(runtime=runtime):
                self.assertIs(JTC.get_runtime(), runtime)

        # 退出后已解绑且 runtime 已关闭
        self.assertIsNone(JTC.get_runtime())
        self.assertTrue(runtime._closed)

        # 2. 验证外部 executor 不会被 close 关闭（谁创建谁关闭原则）
        external_pool = ThreadPoolExecutor(max_workers=1)
        try:
            with JmSyncRuntime(album_executor=external_pool) as runtime:
                self.assertIs(JTC.get_runtime(), runtime)
            self.assertIsNone(JTC.get_runtime())
            # 外部池依然可用
            fut = external_pool.submit(lambda: 42)
            self.assertEqual(fut.result(timeout=1), 42)
        finally:
            external_pool.shutdown(wait=True)

        # 3. 验证 JmTempRuntime 不会自动绑定上下文
        with JmTempRuntime(workers=2) as temp_runtime:
            self.assertIsNone(JTC.get_runtime())
        self.assertTrue(temp_runtime._closed)

        # 4. 验证 JmAsyncRuntime 自动绑定
        async def check_async():
            with JmAsyncRuntime(decode_workers=2) as async_runtime:
                self.assertIs(JTC.get_runtime(), async_runtime)
            self.assertIsNone(JTC.get_runtime())
            self.assertTrue(async_runtime._closed)

        asyncio.run(check_async())

    def test_api_control_param_sugar_sync_and_async(self):
        # 1. 非 DownloadControl 参数抛出 TypeError
        with self.assertRaises(TypeError):
            download_album(123456, control="invalid_control")

        # 2. 验证 control 参数成功注入上下文
        control = DownloadControl()
        captured_control = []

        class ProbeDownloader:
            def __init__(self, _option):
                self.manifest_dict = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def add_features(self, _extra):
                pass

            def raise_if_has_exception(self):
                pass

            def download_album(self, album_id):
                captured_control.append(JTC.get_control())
                detail = object()
                self.manifest_dict[detail] = DownloadManifest()
                return detail

        # 单本调用
        download_album(123456, option=object(), downloader=ProbeDownloader, control=control, check_exception=False)
        self.assertEqual(len(captured_control), 1)
        self.assertIs(captured_control[0], control)

        # 批量调用
        captured_control.clear()
        download_album([123, 456], option=object(), downloader=ProbeDownloader, control=control, check_exception=False)
        self.assertEqual(len(captured_control), 2)
        self.assertIs(captured_control[0], control)
        self.assertIs(captured_control[1], control)

    def test_task_context_named_control_and_batch_order_preservation(self):
        control = DownloadControl()

        # 1. 验证 jm_task_context 具名参数 control
        with jm_task_context(control=control):
            self.assertIs(JTC.get_control(), control)

        # 2. 验证非 DownloadControl 抛出 TypeError
        with self.assertRaises(TypeError):
            with jm_task_context(control="invalid"):
                pass

        # 3. 验证 download_batch 保序去重
        called_ids = []

        def dummy_download(aid, *args, **kwargs):
            called_ids.append(aid)
            return aid

        input_ids = [456, 123, 456, 789, 123]
        result = download_batch(dummy_download, input_ids)
        self.assertEqual(list(result), ['456', '123', '789'])
        self.assertEqual(set(called_ids), {'456', '123', '789'})
        self.assertEqual(len(called_ids), 3)

    def test_async_downloader_retains_client_instance_after_exit(self):
        class DummyClient:
            def __init__(self):
                self.closed = False

            async def setup(self):
                pass

            async def close(self):
                self.closed = True

        class DummyOption:
            download = type('Download', (), {'threading': type('Threading', (), {'image': 1, 'photo': 1})()})()
            plugins = {}

            def new_jm_async_client(self, **kwargs):
                return DummyClient()

        async def check():
            dler = JmAsyncDownloader(DummyOption())
            async with dler:
                self.assertIsNotNone(dler.client)
                self.assertFalse(dler.client.closed)
            # 退出后 client 实例仍保留，但已执行 close
            self.assertIsNotNone(dler.client)
            self.assertTrue(dler.client.closed)

        asyncio.run(check())

    def test_batch_result_contract_and_order(self):
        self.assertFalse(issubclass(BatchResult, set))

        result = BatchResult()
        self.assertEqual(len(result), 0)
        self.assertEqual(result.total, 0)
        self.assertTrue(result.all_succeeded)

        result.add(('album1', 'dler1'))
        result.add(('album2', 'dler2'))
        result.add(('album3', 'dler3'))

        # 验证 FIFO 保序迭代与解包
        items = list(result)
        self.assertEqual(items, [('album1', 'dler1'), ('album2', 'dler2'), ('album3', 'dler3')])
        unpacked = [(a, d) for a, d in result]
        self.assertEqual(unpacked, items)

        # 验证包含与长度
        self.assertEqual(len(result), 3)
        self.assertIn(('album2', 'dler2'), result)
        self.assertNotIn(('album4', 'dler4'), result)

        # 验证失败项与统计
        result.failed['999'] = RuntimeError('err')
        self.assertFalse(result.all_succeeded)
        self.assertEqual(result.total, 4)

        # 验证按车号检索与映射语法糖 (1, 2, 3, 4)
        class MockDetail:
            def __init__(self, aid):
                self.id = aid

        class MockResultItem:
            def __init__(self, aid):
                self.detail = MockDetail(aid)

        r1 = MockResultItem('111')
        r2 = MockResultItem('222')
        result.add(r1)
        result.add(r2, aid=222)

        self.assertIn('111', result)
        self.assertIn(111, result)
        self.assertIn('222', result)
        self.assertIn(222, result)
        self.assertNotIn('333', result)
        self.assertIs(result['111'], r1)
        self.assertIs(result[111], r1)
        self.assertIs(result.get('222'), r2)
        self.assertIsNone(result.get('333'))
        self.assertEqual(result.get('333', 'default'), 'default')
        with self.assertRaises(KeyError):
            _ = result['99999']

    def test_jtc_cancellation_methods(self):
        self.assertFalse(JTC.is_cancelled())
        JTC.raise_if_cancelled()  # 未取消时无任何异常

        control = DownloadControl()
        with jm_task_context(control=control):
            self.assertFalse(JTC.is_cancelled())
            JTC.raise_if_cancelled()
            control.cancel('manual cancel')
            self.assertTrue(JTC.is_cancelled())
            with self.assertRaises(DownloadCancelledException) as cm:
                JTC.raise_if_cancelled()
            self.assertIn('manual cancel', str(cm.exception))

    def test_async_with_jm_task_context(self):
        async def run():
            control = DownloadControl()
            async with jm_task_context(session_id='async-ctx', control=control):
                self.assertEqual(JTC.get_context_value('session_id'), 'async-ctx')
                self.assertIs(JTC.get_control(), control)
            self.assertIsNone(JTC.get_context_value('session_id'))
            self.assertIsNone(JTC.get_control())

        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()

