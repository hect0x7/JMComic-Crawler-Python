from test_jmcomic import *


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
            def invoke(self, option, **kwargs):
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
            def invoke(self, option, **kwargs):
                pass

        base = MyFeature()
        self.assertTrue(base.should_invoke('download_album', 'after_album'))
        self.assertTrue(base.should_invoke('download_album', 'after_photo'))

        # PluginFeature 根据来源推导执行时机
        pf = Feature.export_pdf
        # download_album → 只在 after_album 执行
        self.assertTrue(pf.should_invoke('download_album', 'after_album'))
        self.assertFalse(pf.should_invoke('download_album', 'after_photo'))
        # download_photo → 只在 after_photo 执行
        self.assertTrue(pf.should_invoke('download_photo', 'after_photo'))
        self.assertFalse(pf.should_invoke('download_photo', 'after_album'))

    def test_adapt_kwargs(self):
        """测试 PluginFeature 参数动态适配"""
        when = 'after_album'
        
        pdf = Feature.export_pdf
        adapted = pdf._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['filename_rule'], '[JM{Aid}]{Atitle}')

        zip_f = Feature.export_zip
        adapted = zip_f._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['filename_rule'], '[JM{Aid}]{Atitle}')

        long_img = Feature.export_long_img
        adapted = long_img._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['filename_rule'], '[JM{Aid}]{Atitle}')

        # download_photo 模式
        when = 'after_photo'
        adapted = pdf._adapt_plugin_kwargs(self.option, 'download_photo', when)
        self.assertEqual(adapted['filename_rule'], '[JM{Pid}]{Ptitle}')

        # 用户显式传入的参数不被动态适配 (通过 kwargs 机制自带)
        custom = Feature.export_zip(filename_rule='Ptitle')
        adapted = custom._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['filename_rule'], 'Ptitle')  # 用户显式指定，不被 setdefault 覆盖

    def test_dynamic_base_dir(self):
        """测试不指定导出目录时，自动适配为 option.dir_rule.base_dir"""
        self.option.dir_rule.base_dir = './custom_base'
        when = 'after_album'

        # 1. PDF
        adapted = Feature.export_pdf._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['pdf_dir'], './custom_base')

        # 2. ZIP
        adapted = Feature.export_zip._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['zip_dir'], './custom_base')

        # 3. LongImg
        adapted = Feature.export_long_img._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['img_dir'], './custom_base')

        # 4. 如果显式指定了，则不应被覆盖
        custom_pdf = Feature.export_pdf(pdf_dir='./explicit_dir')
        adapted = custom_pdf._adapt_plugin_kwargs(self.option, 'download_album', when)
        self.assertEqual(adapted['pdf_dir'], './explicit_dir')

    def test_download_use_feature(self):
        album_id = '438516'

        # 记录被执行的次数，便于断言
        custom_feature_call_count = 0

        class MyCounterFeature(Feature):
            def invoke(self, option, **kwargs):
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

        # 测试 download_batch (Iterable 批量输入): 确保 extra 参数不被丢弃
        jmcomic.download_batch(jmcomic.download_album, [album_id], self.option, extra=counter_feature)
        # 上面增加了 1 个 album (包含 1 个 photo)，因此 invoke 追加 2 次，总计 5 次
        self.assertEqual(custom_feature_call_count, 5)

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
        album, _dler = jmcomic.download_album(album_id, self.option, extra=combo)

        # 验证文件是否精确生成
        # 通过 download_album 注册，动态适配后默认规则均为：[JM{Aid}]{Atitle}
        rule = '[JM{Aid}]{Atitle}'
        pdf_name = DirRule.apply_rule_to_filename(album, None, rule) + '.pdf'
        zip_name = DirRule.apply_rule_to_filename(album, None, rule) + '.zip'
        png_name = DirRule.apply_rule_to_filename(album, None, rule) + '.png'

        import os
        pdf_path = os.path.join(export_dir, pdf_name)
        zip_path = os.path.join(export_dir, zip_name)
        png_path = os.path.join(export_dir, png_name)

        self.assertTrue(os.path.exists(pdf_path), f"未生成精确匹配的 PDF 文件: {pdf_path}")
        self.assertTrue(os.path.exists(zip_path), f"未生成精确匹配的 ZIP 文件: {zip_path}")
        self.assertTrue(os.path.exists(png_path), f"未生成精确匹配的 PNG 长图: {png_path}")

    def test_export_features_photo(self):
        photo_id = '438516'
        export_dir = self.option.dir_rule.base_dir

        # 测试单个章节的 PDF 导出
        f_pdf = Feature.export_pdf(pdf_dir=export_dir)
        photo, _dler = jmcomic.download_photo(photo_id, self.option, extra=f_pdf)

        # 验证文件是否按照 [JM{Pid}]{Ptitle} 规则生成
        rule = '[JM{Pid}]{Ptitle}'
        pdf_name = DirRule.apply_rule_to_filename(None, photo, rule) + '.pdf'

        import os
        pdf_path = os.path.join(export_dir, pdf_name)
        self.assertTrue(os.path.exists(pdf_path), f"未生成精确匹配的 PDF 文件 (章节级): {pdf_path}")

    def test_export_album_use_photo_rule(self):
        """
        负面测试：在 Album 模式下强行使用 Photo 级规则（Ptitle），预期报错。
        本子=album，本子的章节=photo。下载本子时，photo对象为None。
        """
        album_id = '438516'
        # 强行使用 Ptitle
        f = Feature.export_pdf(filename_rule='Ptitle')

        # 验证底层 invoke 会抛出 AttributeError
        # 因为在 download_album 的 after_album 阶段，photo 为 None
        with self.assertRaises(AttributeError):
            album = self.client.get_album_detail(album_id)
            f.invoke(self.option, feature_from='download_album', when='after_album', album=album, photo=None)
