from . import *


class Test_Feature(JmTestConfigurable):

    def test_feature_combine(self):
        # 1. + 运算
        f1 = Feature.export_pdf + Feature.export_zip
        self.assertIsInstance(f1, FeatureChain)
        self.assertEqual(len(f1._features), 2)

        # 2. | 运算
        f2 = Feature.export_pdf | Feature.export_zip
        self.assertIsInstance(f2, FeatureChain)

        # 3. & 运算
        f3 = Feature.export_pdf & Feature.export_zip
        self.assertIsInstance(f3, FeatureChain)

        # 4. 连续组合
        f4 = Feature.export_pdf + Feature.export_zip + Feature.export_long_img
        self.assertIsInstance(f4, FeatureChain)
        self.assertEqual(len(f4._features), 3)

    def test_plugin_feature_call(self):
        f = Feature.export_pdf(pdf_dir='./test', filename_rule='test')
        self.assertIsInstance(f, PluginFeature)
        self.assertEqual(f.plugin_key, 'img2pdf')
        self.assertEqual(f.kwargs['pdf_dir'], './test')
        self.assertEqual(f.kwargs['filename_rule'], 'test')

    def test_custom_feature(self):
        class MyCustomFeature(Feature):
            def invoke(self, option, **context):
                pass

        my_feature = MyCustomFeature()
        combo = my_feature + Feature.export_pdf
        self.assertIsInstance(combo, FeatureChain)
        self.assertEqual(len(combo._features), 2)
        self.assertIsInstance(combo._features[0], MyCustomFeature)

    def test_should_invoke(self):
        """测试 should_invoke 判断逻辑"""
        # Feature 基类默认在所有钩子中都执行
        class MyFeature(Feature):
            def invoke(self, option, **context):
                pass

        base = MyFeature()
        self.assertTrue(base.should_invoke('after_album', 'download_album'))
        self.assertTrue(base.should_invoke('after_photo', 'download_album'))

        # PluginFeature 根据来源推导执行时机
        pf = Feature.export_pdf
        # download_album → 只在 after_album 执行
        self.assertTrue(pf.should_invoke('after_album', 'download_album'))
        self.assertFalse(pf.should_invoke('after_photo', 'download_album'))
        # download_photo → 只在 after_photo 执行
        self.assertTrue(pf.should_invoke('after_photo', 'download_photo'))
        self.assertFalse(pf.should_invoke('after_album', 'download_photo'))

    def test_adapt_kwargs(self):
        """测试 PluginFeature 参数动态适配"""
        # download_album 模式：P前缀 → A前缀, level → album
        pdf = Feature.export_pdf
        adapted = pdf._adapt_kwargs('download_album')
        self.assertEqual(adapted['filename_rule'], 'Atitle')  # A开头不变

        zip_f = Feature.export_zip
        adapted = zip_f._adapt_kwargs('download_album')
        self.assertEqual(adapted['filename_rule'], 'Atitle')  # Ptitle → Atitle
        self.assertEqual(adapted['level'], 'album')  # photo → album

        long_img = Feature.export_long_img
        adapted = long_img._adapt_kwargs('download_album')
        self.assertEqual(adapted['filename_rule'], 'Aid')  # Pid → Aid

        # download_photo 模式：A前缀 → P前缀, level → photo
        adapted = pdf._adapt_kwargs('download_photo')
        self.assertEqual(adapted['filename_rule'], 'Ptitle')  # Atitle → Ptitle

        # 用户显式传入的参数不被动态适配
        custom = Feature.export_zip(filename_rule='Ptitle', level='photo')
        adapted = custom._adapt_kwargs('download_album')
        self.assertEqual(adapted['filename_rule'], 'Ptitle')  # 用户显式指定，不适配
        self.assertEqual(adapted['level'], 'photo')  # 用户显式指定，不适配

    def test_download_use_feature(self):
        album_id = '438516'

        # 记录被执行的次数，便于断言
        custom_feature_call_count = 0

        class MyCounterFeature(Feature):
            def invoke(self, option, **context):
                nonlocal custom_feature_call_count
                custom_feature_call_count += 1

        counter_feature = MyCounterFeature()

        # 测试 download_album:
        # 自定义 Feature 基类 should_invoke 默认 True，
        # 438516 有 1 个章节，所以 after_photo(1次) + after_album(1次) = 2次
        jmcomic.download_album(album_id, self.option, extra=counter_feature)
        self.assertEqual(custom_feature_call_count, 2)

        # 测试 download_photo: after_photo 触发 1 次
        photo_id = '438516'
        jmcomic.download_photo(photo_id, self.option, extra=counter_feature)
        self.assertEqual(custom_feature_call_count, 3)

    def test_export_features(self):
        album_id = '438516'

        # 直接使用测试环境配置的下载目录
        export_dir = self.option.dir_rule.base_dir

        # 定义导出路径指向测试目录
        f_pdf = Feature.export_pdf(pdf_dir=export_dir)
        f_zip = Feature.export_zip(zip_dir=export_dir)
        f_long_img = Feature.export_long_img(img_dir=export_dir)

        # 组合下载并导出
        combo = f_pdf + f_zip + f_long_img
        album, dler = jmcomic.download_album(album_id, self.option, extra=combo)

        # 验证文件是否精确生成
        # 通过 download_album 注册，动态适配后全部为 album 级别：
        # PDF: Atitle(不变) → [album标题].pdf
        # ZIP: Ptitle→Atitle, level→album → [album标题].zip
        # PNG: Pid→Aid → [album_id].png
        pdf_name = DirRule.apply_rule_to_filename(album, None, 'Atitle') + '.pdf'
        zip_name = DirRule.apply_rule_to_filename(album, None, 'Atitle') + '.zip'
        png_name = DirRule.apply_rule_to_filename(album, None, 'Aid') + '.png'

        import os
        pdf_path = os.path.join(export_dir, pdf_name)
        zip_path = os.path.join(export_dir, zip_name)
        png_path = os.path.join(export_dir, png_name)

        self.assertTrue(os.path.exists(pdf_path), f"未生成精确匹配的 PDF 文件: {pdf_path}")
        self.assertTrue(os.path.exists(zip_path), f"未生成精确匹配的 ZIP 文件: {zip_path}")
        self.assertTrue(os.path.exists(png_path), f"未生成精确匹配的 PNG 长图: {png_path}")
