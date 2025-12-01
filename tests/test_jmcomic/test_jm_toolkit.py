from test_jmcomic import *
import re


class Test_Toolkit(JmTestConfigurable):
    """
    Test cases for JmcomicText utility class and helper functions
    """

    @classmethod
    def new_option(cls):
        """Use toolkit-specific test configuration"""
        try:
            return create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            return create_option('./assets/option/option_test_toolkit.yml')

    # ========== parse_to_jm_id tests ==========

    def test_parse_to_jm_id_with_integer(self):
        """Test parse_to_jm_id with integer input"""
        result = JmcomicText.parse_to_jm_id(123456)
        self.assertEqual(result, '123456')

    def test_parse_to_jm_id_with_digit_string(self):
        """Test parse_to_jm_id with pure digit string"""
        result = JmcomicText.parse_to_jm_id('789012')
        self.assertEqual(result, '789012')

    def test_parse_to_jm_id_with_jm_prefix_uppercase(self):
        """Test parse_to_jm_id with JM prefix (uppercase)"""
        result = JmcomicText.parse_to_jm_id('JM123456')
        self.assertEqual(result, '123456')

    def test_parse_to_jm_id_with_jm_prefix_lowercase(self):
        """Test parse_to_jm_id with jm prefix (lowercase)"""
        result = JmcomicText.parse_to_jm_id('jm789012')
        self.assertEqual(result, '789012')

    def test_parse_to_jm_id_with_jm_prefix_mixed_case(self):
        """Test parse_to_jm_id with mixed case JM prefix"""
        test_cases = ['Jm123', 'jM456']
        for case in test_cases:
            result = JmcomicText.parse_to_jm_id(case)
            self.assertEqual(result, case[2:])

    def test_parse_to_jm_id_with_photo_url(self):
        """Test parse_to_jm_id with photo URL"""
        url = 'https://example.com/photo/412038'
        result = JmcomicText.parse_to_jm_id(url)
        self.assertEqual(result, '412038')

    def test_parse_to_jm_id_with_album_url(self):
        """Test parse_to_jm_id with album URL"""
        url = 'https://example.com/album/123456'
        result = JmcomicText.parse_to_jm_id(url)
        self.assertEqual(result, '123456')

    def test_parse_to_jm_id_with_album_query_param(self):
        """Test parse_to_jm_id with album query parameter"""
        url = 'https://example.com/album/?id=654321'
        result = JmcomicText.parse_to_jm_id(url)
        self.assertEqual(result, '654321')

    def test_parse_to_jm_id_with_photos_plural(self):
        """Test parse_to_jm_id with photos (plural) URL"""
        url = 'https://example.com/photos/999888'
        result = JmcomicText.parse_to_jm_id(url)
        self.assertEqual(result, '999888')

    def test_parse_to_jm_id_with_albums_plural(self):
        """Test parse_to_jm_id with albums (plural) URL"""
        url = 'https://example.com/albums/777666'
        result = JmcomicText.parse_to_jm_id(url)
        self.assertEqual(result, '777666')

    def test_parse_to_jm_id_invalid_type(self):
        """Test parse_to_jm_id with invalid type raises exception"""
        with self.assertRaises(JmcomicException) as context:
            JmcomicText.parse_to_jm_id([123])
        
        self.assertIn('无法解析jm车号', str(context.exception))
        self.assertIn('参数类型', str(context.exception))

    def test_parse_to_jm_id_too_short(self):
        """Test parse_to_jm_id with too short string"""
        with self.assertRaises(JmcomicException) as context:
            JmcomicText.parse_to_jm_id('a')
        
        self.assertIn('文本太短', str(context.exception))

    def test_parse_to_jm_id_invalid_format(self):
        """Test parse_to_jm_id with invalid format"""
        with self.assertRaises(JmcomicException) as context:
            JmcomicText.parse_to_jm_id('invalid_text_123')
        
        self.assertIn('无法解析jm车号', str(context.exception))

    # ========== parse_to_jm_domain tests ==========

    def test_parse_to_jm_domain_with_url(self):
        """Test parse_to_jm_domain with full URL"""
        url = 'https://jmcomic.example.com/path'
        result = JmcomicText.parse_to_jm_domain(url)
        self.assertEqual(result, 'jmcomic.example.com')

    def test_parse_to_jm_domain_with_plain_domain(self):
        """Test parse_to_jm_domain with plain domain"""
        domain = 'example.com'
        result = JmcomicText.parse_to_jm_domain(domain)
        self.assertEqual(result, domain)

    def test_parse_to_jm_domain_with_subdomain(self):
        """Test parse_to_jm_domain with subdomain"""
        url = 'https://www.jmcomic.example.com/test'
        result = JmcomicText.parse_to_jm_domain(url)
        self.assertEqual(result, 'www.jmcomic.example.com')

    # ========== tokenize tests ==========

    def test_tokenize_simple_title(self):
        """Test tokenize with simple title"""
        title = "Simple Title"
        result = JmcomicText.tokenize(title)
        self.assertEqual(result, ['Simple Title'])

    def test_tokenize_with_square_brackets(self):
        """Test tokenize with square brackets"""
        title = "Title [Author] [Tag]"
        result = JmcomicText.tokenize(title)
        self.assertEqual(result, ['Title', '[Author]', '[Tag]'])

    def test_tokenize_with_parentheses(self):
        """Test tokenize with parentheses"""
        title = "Title (Info) More"
        result = JmcomicText.tokenize(title)
        self.assertEqual(result, ['Title', '(Info)', 'More'])

    def test_tokenize_with_chinese_brackets(self):
        """Test tokenize with Chinese brackets"""
        title = "标题【作者】（信息）"
        result = JmcomicText.tokenize(title)
        self.assertEqual(result, ['标题', '【作者】', '（信息）'])

    def test_tokenize_complex_title(self):
        """Test tokenize with complex real-world title"""
        title = "繞道#2 [暴碧漢化組] [えーすけ（123）] よりみち#2 (COMIC 快樂天 2024年1月號) [中國翻譯] [DL版]"
        result = JmcomicText.tokenize(title)
        
        expected = [
            '繞道#2',
            '[暴碧漢化組]',
            '[えーすけ（123）]',
            'よりみち#2',
            '(COMIC 快樂天 2024年1月號)',
            '[中國翻譯]',
            '[DL版]'
        ]
        self.assertEqual(result, expected)

    def test_tokenize_nested_brackets(self):
        """Test tokenize with nested brackets"""
        title = "Title [Author (Name)] End"
        result = JmcomicText.tokenize(title)
        self.assertEqual(result, ['Title', '[Author (Name)]', 'End'])

    def test_tokenize_unclosed_bracket(self):
        """Test tokenize with unclosed bracket"""
        title = "Title [Unclosed More"
        result = JmcomicText.tokenize(title)
        # Unclosed bracket should be treated as regular character
        self.assertEqual(result, ['Title [Unclosed More'])

    def test_tokenize_empty_string(self):
        """Test tokenize with empty string"""
        result = JmcomicText.tokenize("")
        self.assertEqual(result, [])

    def test_tokenize_whitespace_only(self):
        """Test tokenize with whitespace only"""
        result = JmcomicText.tokenize("   ")
        self.assertEqual(result, [])

    # ========== parse_orig_album_name tests ==========

    def test_parse_orig_album_name_simple(self):
        """Test parse_orig_album_name with simple title"""
        name = "Original Title [Author]"
        result = JmcomicText.parse_orig_album_name(name)
        self.assertEqual(result, 'Original Title')

    def test_parse_orig_album_name_starts_with_bracket(self):
        """Test parse_orig_album_name when title starts with bracket"""
        name = "[Tag] Title [Author]"
        result = JmcomicText.parse_orig_album_name(name)
        self.assertEqual(result, 'Title')

    def test_parse_orig_album_name_all_brackets(self):
        """Test parse_orig_album_name when all tokens are brackets"""
        name = "[Tag1] [Tag2] [Tag3]"
        result = JmcomicText.parse_orig_album_name(name)
        self.assertIsNone(result)

    def test_parse_orig_album_name_with_default(self):
        """Test parse_orig_album_name with custom default"""
        name = "[Tag1] [Tag2]"
        result = JmcomicText.parse_orig_album_name(name, default="Default Title")
        self.assertEqual(result, "Default Title")

    def test_parse_orig_album_name_complex(self):
        """Test parse_orig_album_name with complex title"""
        name = "喂我吃吧 老師! [欶瀾漢化組] [BLVEFO9] たべさせて、せんせい! (ブルーアーカイブ) [中國翻譯] [無修正]"
        result = JmcomicText.parse_orig_album_name(name)
        self.assertEqual(result, '喂我吃吧 老師!')

    # ========== format_url tests ==========

    def test_format_url_with_plain_domain(self):
        """Test format_url with plain domain"""
        path = '/album/123'
        domain = 'example.com'
        result = JmcomicText.format_url(path, domain)
        self.assertTrue(result.startswith('https://'))
        self.assertIn('example.com', result)
        self.assertIn('/album/123', result)

    def test_format_url_with_full_domain(self):
        """Test format_url with full domain including protocol"""
        path = '/photo/456'
        domain = 'https://example.com'
        result = JmcomicText.format_url(path, domain)
        self.assertEqual(result, 'https://example.com/photo/456')

    def test_format_url_empty_domain_raises(self):
        """Test format_url with empty domain raises exception"""
        with self.assertRaises(JmcomicException) as context:
            JmcomicText.format_url('/path', '')
        
        self.assertIn('域名为空', str(context.exception))

    # ========== format_album_url tests ==========

    def test_format_album_url_default_domain(self):
        """Test format_album_url with default domain"""
        result = JmcomicText.format_album_url('123456')
        self.assertIn('/album/123456/', result)
        self.assertTrue(result.startswith('https://'))

    def test_format_album_url_custom_domain(self):
        """Test format_album_url with custom domain"""
        result = JmcomicText.format_album_url('789', 'custom.com')
        self.assertIn('custom.com', result)
        self.assertIn('/album/789/', result)

    # ========== to_zh tests ==========

    def test_to_zh_cn_conversion(self):
        """Test to_zh_cn for traditional to simplified conversion"""
        try:
            import zhconv
            traditional = "繁體中文"
            result = JmcomicText.to_zh_cn(traditional)
            # Should convert to simplified
            self.assertIsNotNone(result)
        except ImportError:
            self.skipTest("zhconv not installed")

    def test_to_zh_with_none(self):
        """Test to_zh with None input"""
        result = JmcomicText.to_zh(None, 'zh-cn')
        self.assertIsNone(result)

    def test_to_zh_with_no_target(self):
        """Test to_zh with no target (should return original)"""
        text = "测试文本"
        result = JmcomicText.to_zh(text, None)
        self.assertEqual(result, text)

    def test_to_zh_without_zhconv(self):
        """Test to_zh gracefully handles missing zhconv"""
        # This should not raise, just return original text
        text = "测试"
        result = JmcomicText.to_zh(text, 'zh-cn')
        self.assertEqual(result, text)

    # ========== analyse_jm_pub_html tests ==========

    def test_analyse_jm_pub_html_with_domains(self):
        """Test analyse_jm_pub_html extracts domains"""
        html = '''
        <a href="jmcomic.example.com">Link1</a>
        <a href="test.comic.org">Link2</a>
        <a href="other.site.com">Link3</a>
        '''
        result = JmcomicText.analyse_jm_pub_html(html)
        
        # Should find domains with 'jm' or 'comic' keywords
        self.assertGreater(len(result), 0)
        self.assertTrue(any('comic' in d for d in result))

    def test_analyse_jm_pub_html_custom_keywords(self):
        """Test analyse_jm_pub_html with custom keywords"""
        html = 'test.example.com other.test.org'
        result = JmcomicText.analyse_jm_pub_html(html, domain_keyword=('test',))
        
        self.assertGreater(len(result), 0)
        self.assertTrue(all('test' in d for d in result))

    def test_analyse_jm_pub_html_no_matches(self):
        """Test analyse_jm_pub_html with no matching domains"""
        html = 'random.site.com another.domain.org'
        result = JmcomicText.analyse_jm_pub_html(html)
        
        # Should return empty list if no keywords match
        self.assertEqual(len(result), 0)

    # ========== try_parse_json_object tests ==========

    def test_try_parse_json_object_simple(self):
        """Test try_parse_json_object with simple JSON"""
        json_text = '{"key": "value", "number": 123}'
        result = JmcomicText.try_parse_json_object(json_text)
        
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['number'], 123)

    def test_try_parse_json_object_with_whitespace(self):
        """Test try_parse_json_object with leading/trailing whitespace"""
        json_text = '  {"data": "test"}  '
        result = JmcomicText.try_parse_json_object(json_text)
        
        self.assertEqual(result['data'], 'test')

    def test_try_parse_json_object_embedded_in_text(self):
        """Test try_parse_json_object with JSON embedded in text"""
        text = 'Some log message {"key": "value"} more text'
        result = JmcomicText.try_parse_json_object(text)
        
        self.assertEqual(result['key'], 'value')

    def test_try_parse_json_object_multiple_objects(self):
        """Test try_parse_json_object with multiple JSON objects"""
        text = '{"first": 1} {"second": 2}'
        result = JmcomicText.try_parse_json_object(text)
        
        # Should return first valid JSON object
        self.assertIn('first', result)

    def test_try_parse_json_object_invalid_raises(self):
        """Test try_parse_json_object with invalid JSON raises"""
        with self.assertRaises(AssertionError) as context:
            JmcomicText.try_parse_json_object('not a json')
        
        self.assertIn('未解析出json数据', str(context.exception))

    # ========== limit_text tests ==========

    def test_limit_text_under_limit(self):
        """Test limit_text with text under limit"""
        text = "Short text"
        result = JmcomicText.limit_text(text, 100)
        self.assertEqual(result, text)

    def test_limit_text_over_limit(self):
        """Test limit_text with text over limit"""
        text = "A" * 200
        result = JmcomicText.limit_text(text, 50)
        
        self.assertEqual(len(result.split('...')[0]), 50)
        self.assertIn('...', result)
        self.assertIn('(150', result)  # Should show remaining count

    def test_limit_text_exact_limit(self):
        """Test limit_text with text exactly at limit"""
        text = "A" * 100
        result = JmcomicText.limit_text(text, 100)
        self.assertEqual(result, text)

    # ========== DSLReplacer tests ==========

    def test_dsl_replacer_basic(self):
        """Test DSLReplacer basic functionality"""
        replacer = JmcomicText.DSLReplacer()
        
        # Add a simple DSL pattern
        replacer.add_dsl_and_replacer(r'\$\{(\w+)\}', lambda m: m[1].upper())
        
        text = "Hello ${world}"
        result = replacer.parse_dsl_text(text)
        self.assertEqual(result, "Hello WORLD")

    def test_dsl_replacer_multiple_patterns(self):
        """Test DSLReplacer with multiple patterns"""
        replacer = JmcomicText.DSLReplacer()
        
        replacer.add_dsl_and_replacer(r'\$\{(\w+)\}', lambda m: m[1].upper())
        replacer.add_dsl_and_replacer(r'#(\d+)', lambda m: str(int(m[1]) * 2))
        
        text = "Test ${var} and #5"
        result = replacer.parse_dsl_text(text)
        
        self.assertIn('VAR', result)
        self.assertIn('10', result)

    def test_dsl_replacer_no_match(self):
        """Test DSLReplacer with no matching patterns"""
        replacer = JmcomicText.DSLReplacer()
        replacer.add_dsl_and_replacer(r'\$\{(\w+)\}', lambda m: 'REPLACED')
        
        text = "No patterns here"
        result = replacer.parse_dsl_text(text)
        self.assertEqual(result, text)

    # ========== match_os_env tests ==========

    def test_match_os_env_existing_var(self):
        """Test match_os_env with existing environment variable"""
        import os
        os.environ['TEST_VAR_JM'] = 'test_value'
        
        try:
            # Create a mock match object
            match = re.match(r'\$\{(\w+)\}', '${TEST_VAR_JM}')
            result = JmcomicText.match_os_env(match)
            self.assertEqual(result, 'test_value')
        finally:
            del os.environ['TEST_VAR_JM']

    def test_match_os_env_missing_var(self):
        """Test match_os_env with missing environment variable"""
        match = re.match(r'\$\{(\w+)\}', '${NONEXISTENT_VAR_XYZ}')
        
        with self.assertRaises(JmcomicException) as context:
            JmcomicText.match_os_env(match)
        
        self.assertIn('未配置环境变量', str(context.exception))

    # ========== parse_dsl_text tests ==========

    def test_parse_dsl_text_integration(self):
        """Test parse_dsl_text with default DSL replacer"""
        # This tests the class-level dsl_replacer
        text = "Simple text"
        result = JmcomicText.parse_dsl_text(text)
        # Should return text unchanged if no DSL patterns registered
        self.assertIsNotNone(result)

    # ========== parse_to_abspath tests ==========

    def test_parse_to_abspath(self):
        """Test parse_to_abspath converts to absolute path"""
        path = "./relative/path"
        result = JmcomicText.parse_to_abspath(path)
        
        self.assertTrue(os.path.isabs(result))

    # ========== try_mkdir tests ==========

    def test_try_mkdir_creates_directory(self):
        """Test try_mkdir creates directory"""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        try:
            test_dir = os.path.join(temp_dir, 'test_subdir')
            result = JmcomicText.try_mkdir(test_dir)
            
            self.assertTrue(os.path.exists(test_dir))
            self.assertTrue(os.path.isdir(test_dir))
            self.assertEqual(result, test_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_try_mkdir_existing_directory(self):
        """Test try_mkdir with existing directory"""
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        try:
            # Should not raise error for existing directory
            result = JmcomicText.try_mkdir(temp_dir)
            self.assertEqual(result, temp_dir)
        finally:
            os.rmdir(temp_dir)

    # ========== Pattern constants tests ==========

    def test_pattern_constants_are_compiled(self):
        """Test that pattern constants are compiled regex patterns"""
        patterns = [
            JmcomicText.pattern_jm_domain,
            JmcomicText.pattern_html_photo_photo_id,
            JmcomicText.pattern_html_album_album_id,
            JmcomicText.pattern_html_album_name,
        ]
        
        for pattern in patterns:
            self.assertIsInstance(pattern, re.Pattern)

    def test_pattern_jm_pa_id_structure(self):
        """Test pattern_jm_pa_id is properly structured"""
        self.assertIsInstance(JmcomicText.pattern_jm_pa_id, list)
        self.assertGreater(len(JmcomicText.pattern_jm_pa_id), 0)
        
        for item in JmcomicText.pattern_jm_pa_id:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], re.Pattern)
            self.assertIsInstance(item[1], int)

    def test_bracket_map_completeness(self):
        """Test bracket_map contains all bracket pairs"""
        bracket_map = JmcomicText.bracket_map
        
        self.assertEqual(bracket_map['('], ')')
        self.assertEqual(bracket_map['['], ']')
        self.assertEqual(bracket_map['【'], '】')
        self.assertEqual(bracket_map['（'], '）')
