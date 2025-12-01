from test_jmcomic import *
import re


class Test_Exception(JmTestConfigurable):
    """
    Test cases for JmException classes and ExceptionTool
    """

    @classmethod
    def new_option(cls):
        """Use exception-specific test configuration"""
        try:
            return create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            return create_option('./assets/option/option_test_exception.yml')

    def test_jmcomic_exception_basic(self):
        """Test basic JmcomicException creation and properties"""
        msg = "Test error message"
        context = {'key1': 'value1', 'key2': 123}
        
        exc = JmcomicException(msg, context)
        
        self.assertEqual(str(exc), msg)
        self.assertEqual(exc.msg, msg)
        self.assertEqual(exc.context, context)
        self.assertEqual(exc.from_context('key1'), 'value1')
        self.assertEqual(exc.from_context('key2'), 123)
        self.assertEqual(exc.description, 'jmcomic 模块异常')

    def test_jmcomic_exception_from_context(self):
        """Test from_context method retrieves correct values"""
        context = {
            'resp': 'response_object',
            'html': '<html>content</html>',
            'pattern': 'test_pattern'
        }
        
        exc = JmcomicException("test", context)
        
        self.assertEqual(exc.from_context('resp'), 'response_object')
        self.assertEqual(exc.from_context('html'), '<html>content</html>')
        self.assertEqual(exc.from_context('pattern'), 'test_pattern')

    def test_response_unexpected_exception(self):
        """Test ResponseUnexpectedException with resp property"""
        fake_resp = type('FakeResp', (), {'status_code': 404, 'text': 'Not Found'})()
        context = {ExceptionTool.CONTEXT_KEY_RESP: fake_resp}
        
        exc = ResponseUnexpectedException("Unexpected response", context)
        
        self.assertEqual(exc.resp, fake_resp)
        self.assertEqual(exc.resp.status_code, 404)
        self.assertEqual(exc.description, '响应不符合预期异常')

    def test_regular_not_match_exception(self):
        """Test RegularNotMatchException with all properties"""
        pattern = re.compile(r'test_(\d+)')
        html_text = '<html>some content</html>'
        fake_resp = type('FakeResp', (), {'status_code': 200})()
        
        context = {
            ExceptionTool.CONTEXT_KEY_HTML: html_text,
            ExceptionTool.CONTEXT_KEY_RE_PATTERN: pattern,
            ExceptionTool.CONTEXT_KEY_RESP: fake_resp
        }
        
        exc = RegularNotMatchException("Pattern not matched", context)
        
        self.assertEqual(exc.error_text, html_text)
        self.assertEqual(exc.pattern, pattern)
        self.assertEqual(exc.resp, fake_resp)
        self.assertEqual(exc.description, '正则表达式不匹配异常')

    def test_regular_not_match_exception_without_resp(self):
        """Test RegularNotMatchException when resp is None"""
        pattern = re.compile(r'test')
        context = {
            ExceptionTool.CONTEXT_KEY_HTML: 'html',
            ExceptionTool.CONTEXT_KEY_RE_PATTERN: pattern
        }
        
        exc = RegularNotMatchException("No match", context)
        
        self.assertIsNone(exc.resp)

    def test_json_resolve_fail_exception(self):
        """Test JsonResolveFailException"""
        fake_resp = type('FakeResp', (), {'text': 'invalid json'})()
        context = {ExceptionTool.CONTEXT_KEY_RESP: fake_resp}
        
        exc = JsonResolveFailException("JSON parse failed", context)
        
        self.assertEqual(exc.resp, fake_resp)
        self.assertEqual(exc.description, 'Json解析异常')
        self.assertIsInstance(exc, ResponseUnexpectedException)

    def test_missing_album_photo_exception(self):
        """Test MissingAlbumPhotoException with error_jmid property"""
        fake_resp = type('FakeResp', (), {'status_code': 404})()
        jmid = '123456'
        
        context = {
            ExceptionTool.CONTEXT_KEY_RESP: fake_resp,
            ExceptionTool.CONTEXT_KEY_MISSING_JM_ID: jmid
        }
        
        exc = MissingAlbumPhotoException("Album not found", context)
        
        self.assertEqual(exc.error_jmid, jmid)
        self.assertEqual(exc.resp, fake_resp)
        self.assertEqual(exc.description, '不存在本子或章节异常')
        self.assertIsInstance(exc, ResponseUnexpectedException)

    def test_request_retry_all_fail_exception(self):
        """Test RequestRetryAllFailException"""
        exc = RequestRetryAllFailException("All retries failed", {})
        
        self.assertEqual(exc.description, '请求重试全部失败异常')
        self.assertIsInstance(exc, JmcomicException)

    def test_partial_download_failed_exception(self):
        """Test PartialDownloadFailedException with downloader property"""
        fake_downloader = type('FakeDownloader', (), {'name': 'test_downloader'})()
        context = {ExceptionTool.CONTEXT_KEY_DOWNLOADER: fake_downloader}
        
        exc = PartialDownloadFailedException("Partial download failed", context)
        
        self.assertEqual(exc.downloader, fake_downloader)
        self.assertEqual(exc.downloader.name, 'test_downloader')
        self.assertEqual(exc.description, '部分章节或图片下载失败异常')

    def test_exception_tool_raises_default(self):
        """Test ExceptionTool.raises with default parameters"""
        msg = "Test error"
        
        with self.assertRaises(JmcomicException) as context:
            ExceptionTool.raises(msg)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertEqual(exc.context, {})

    def test_exception_tool_raises_with_context(self):
        """Test ExceptionTool.raises with custom context"""
        msg = "Test error"
        ctx = {'key': 'value', 'number': 42}
        
        with self.assertRaises(JmcomicException) as context:
            ExceptionTool.raises(msg, ctx)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertEqual(exc.context, ctx)
        self.assertEqual(exc.from_context('key'), 'value')
        self.assertEqual(exc.from_context('number'), 42)

    def test_exception_tool_raises_with_custom_type(self):
        """Test ExceptionTool.raises with custom exception type"""
        msg = "Custom exception"
        ctx = {'data': 'test'}
        
        with self.assertRaises(RequestRetryAllFailException) as context:
            ExceptionTool.raises(msg, ctx, RequestRetryAllFailException)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertIsInstance(exc, RequestRetryAllFailException)

    def test_exception_tool_raises_regex(self):
        """Test ExceptionTool.raises_regex helper method"""
        msg = "Pattern not found"
        html = "<html>test content</html>"
        pattern = re.compile(r'missing_(\d+)')
        
        with self.assertRaises(RegularNotMatchException) as context:
            ExceptionTool.raises_regex(msg, html, pattern)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertEqual(exc.error_text, html)
        self.assertEqual(exc.pattern, pattern)

    def test_exception_tool_raises_resp(self):
        """Test ExceptionTool.raises_resp helper method"""
        msg = "Response error"
        fake_resp = type('FakeResp', (), {'status': 500})()
        
        with self.assertRaises(ResponseUnexpectedException) as context:
            ExceptionTool.raises_resp(msg, fake_resp)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertEqual(exc.resp, fake_resp)

    def test_exception_tool_raises_resp_custom_type(self):
        """Test ExceptionTool.raises_resp with custom exception type"""
        msg = "JSON error"
        fake_resp = type('FakeResp', (), {'text': 'bad json'})()
        
        with self.assertRaises(JsonResolveFailException) as context:
            ExceptionTool.raises_resp(msg, fake_resp, JsonResolveFailException)
        
        exc = context.exception
        self.assertEqual(str(exc), msg)
        self.assertIsInstance(exc, JsonResolveFailException)

    def test_exception_tool_raise_missing_album(self):
        """Test ExceptionTool.raise_missing for album"""
        fake_resp = type('FakeResp', (), {'status_code': 404})()
        jmid = '123456'
        
        with self.assertRaises(MissingAlbumPhotoException) as context:
            ExceptionTool.raise_missing(fake_resp, jmid)
        
        exc = context.exception
        self.assertIn('本子', str(exc))
        self.assertIn('不存在', str(exc))
        self.assertIn(jmid, str(exc))
        self.assertEqual(exc.error_jmid, jmid)
        self.assertEqual(exc.resp, fake_resp)

    def test_exception_tool_raise_missing_photo(self):
        """Test ExceptionTool.raise_missing for photo"""
        fake_resp = type('FakeResp', (), {'status_code': 404})()
        jmid = '789012'
        
        # Mock the format_album_url to return photo URL
        from jmcomic.jm_toolkit import JmcomicText
        original_format = JmcomicText.format_album_url
        JmcomicText.format_album_url = lambda x: f'https://test.com/photo/{x}'
        
        try:
            with self.assertRaises(MissingAlbumPhotoException) as context:
                ExceptionTool.raise_missing(fake_resp, jmid)
            
            exc = context.exception
            self.assertIn('章节', str(exc))
            self.assertIn('不存在', str(exc))
        finally:
            JmcomicText.format_album_url = original_format

    def test_exception_tool_require_true_passes(self):
        """Test ExceptionTool.require_true when condition is True"""
        # Should not raise
        try:
            ExceptionTool.require_true(True, "This should not raise")
            ExceptionTool.require_true(1 == 1, "This should not raise")
            ExceptionTool.require_true("non-empty", "This should not raise")
        except Exception as e:
            self.fail(f"require_true raised unexpectedly: {e}")

    def test_exception_tool_require_true_fails(self):
        """Test ExceptionTool.require_true when condition is False"""
        msg = "Condition failed"
        
        with self.assertRaises(JmcomicException) as context:
            ExceptionTool.require_true(False, msg)
        
        self.assertEqual(str(context.exception), msg)

    def test_exception_tool_require_true_with_expressions(self):
        """Test ExceptionTool.require_true with various expressions"""
        # Should raise
        with self.assertRaises(JmcomicException):
            ExceptionTool.require_true(0, "Zero is falsy")
        
        with self.assertRaises(JmcomicException):
            ExceptionTool.require_true(None, "None is falsy")
        
        with self.assertRaises(JmcomicException):
            ExceptionTool.require_true("", "Empty string is falsy")

    def test_exception_tool_notify_all_listeners(self):
        """Test ExceptionTool.notify_all_listeners mechanism"""
        # Save original registry
        original_registry = JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.copy()
        
        try:
            # Clear registry and add test listener
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.clear()
            
            called_exceptions = []
            
            def test_listener(exc):
                called_exceptions.append(exc)
            
            # Register listener for JmcomicException
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER[JmcomicException] = test_listener
            
            # Raise an exception
            try:
                ExceptionTool.raises("Test notification")
            except JmcomicException:
                pass
            
            # Verify listener was called
            self.assertEqual(len(called_exceptions), 1)
            self.assertIsInstance(called_exceptions[0], JmcomicException)
            self.assertEqual(str(called_exceptions[0]), "Test notification")
            
        finally:
            # Restore original registry
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER = original_registry

    def test_exception_tool_notify_multiple_listeners(self):
        """Test multiple listeners for exception hierarchy"""
        original_registry = JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.copy()
        
        try:
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.clear()
            
            base_called = []
            specific_called = []
            
            def base_listener(exc):
                base_called.append(exc)
            
            def specific_listener(exc):
                specific_called.append(exc)
            
            # Register listeners for different exception types
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER[JmcomicException] = base_listener
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER[ResponseUnexpectedException] = specific_listener
            
            # Raise ResponseUnexpectedException (subclass of JmcomicException)
            try:
                ExceptionTool.raises_resp("Test", type('Resp', (), {})())
            except ResponseUnexpectedException:
                pass
            
            # Both listeners should be called
            self.assertEqual(len(base_called), 1)
            self.assertEqual(len(specific_called), 1)
            self.assertIsInstance(base_called[0], ResponseUnexpectedException)
            self.assertIsInstance(specific_called[0], ResponseUnexpectedException)
            
        finally:
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER = original_registry

    def test_exception_tool_notify_with_empty_registry(self):
        """Test notify_all_listeners with empty registry"""
        original_registry = JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.copy()
        
        try:
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER.clear()
            
            # Should not raise even with empty registry
            try:
                ExceptionTool.raises("Test with no listeners")
            except JmcomicException:
                pass  # Expected
            
        finally:
            JmModuleConfig.REGISTRY_EXCEPTION_LISTENER = original_registry

    def test_exception_context_keys_constants(self):
        """Test that context key constants are defined correctly"""
        self.assertEqual(ExceptionTool.CONTEXT_KEY_RESP, 'resp')
        self.assertEqual(ExceptionTool.CONTEXT_KEY_HTML, 'html')
        self.assertEqual(ExceptionTool.CONTEXT_KEY_RE_PATTERN, 'pattern')
        self.assertEqual(ExceptionTool.CONTEXT_KEY_MISSING_JM_ID, 'missing_jm_id')
        self.assertEqual(ExceptionTool.CONTEXT_KEY_DOWNLOADER, 'downloader')

    def test_exception_inheritance_hierarchy(self):
        """Test exception class inheritance hierarchy"""
        # Test inheritance relationships
        self.assertTrue(issubclass(ResponseUnexpectedException, JmcomicException))
        self.assertTrue(issubclass(RegularNotMatchException, JmcomicException))
        self.assertTrue(issubclass(JsonResolveFailException, ResponseUnexpectedException))
        self.assertTrue(issubclass(MissingAlbumPhotoException, ResponseUnexpectedException))
        self.assertTrue(issubclass(RequestRetryAllFailException, JmcomicException))
        self.assertTrue(issubclass(PartialDownloadFailedException, JmcomicException))
        
        # Test that they're all ultimately Exceptions
        self.assertTrue(issubclass(JmcomicException, Exception))

    def test_exception_str_representation(self):
        """Test __str__ method returns correct message"""
        test_cases = [
            ("Simple message", {}),
            ("Message with context", {'key': 'value'}),
            ("多语言消息测试", {'data': 123}),
        ]
        
        for msg, ctx in test_cases:
            exc = JmcomicException(msg, ctx)
            self.assertEqual(str(exc), msg)

    def test_exception_with_complex_context(self):
        """Test exceptions with complex context objects"""
        complex_context = {
            'nested': {'key': 'value', 'list': [1, 2, 3]},
            'object': type('TestObj', (), {'attr': 'test'})(),
            'number': 42,
            'string': 'test',
            'none': None,
        }
        
        exc = JmcomicException("Complex context test", complex_context)
        
        self.assertEqual(exc.from_context('nested')['key'], 'value')
        self.assertEqual(exc.from_context('nested')['list'], [1, 2, 3])
        self.assertEqual(exc.from_context('object').attr, 'test')
        self.assertEqual(exc.from_context('number'), 42)
        self.assertEqual(exc.from_context('string'), 'test')
        self.assertIsNone(exc.from_context('none'))
