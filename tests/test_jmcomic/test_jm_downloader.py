from test_jmcomic import *


class Test_Downloader(JmTestConfigurable):
    """
    Test cases for JmDownloader class and related functionality
    """

    @classmethod
    def new_option(cls):
        """Use downloader-specific test configuration"""
        try:
            return create_option_by_env('JM_OPTION_PATH_TEST')
        except JmcomicException:
            return create_option('./assets/option/option_test_downloader.yml')

    def test_downloader_initialization(self):
        """Test that downloader initializes correctly with option"""
        downloader = JmDownloader(self.option)
        
        self.assertIsNotNone(downloader.option)
        self.assertIsNotNone(downloader.client)
        self.assertEqual(len(downloader.download_success_dict), 0)
        self.assertEqual(len(downloader.download_failed_image), 0)
        self.assertEqual(len(downloader.download_failed_photo), 0)

    def test_has_download_failures_property(self):
        """Test has_download_failures property"""
        downloader = JmDownloader(self.option)
        
        # Initially no failures
        self.assertFalse(downloader.has_download_failures)
        
        # Add a fake image failure
        fake_image = type('FakeImage', (), {'id': '1'})()
        fake_exception = Exception('test error')
        downloader.download_failed_image.append((fake_image, fake_exception))
        
        self.assertTrue(downloader.has_download_failures)
        
        # Clear and add photo failure
        downloader.download_failed_image.clear()
        fake_photo = type('FakePhoto', (), {'id': '1'})()
        downloader.download_failed_photo.append((fake_photo, fake_exception))
        
        self.assertTrue(downloader.has_download_failures)

    def test_all_success_property_with_no_downloads(self):
        """Test all_success property when no downloads have occurred"""
        downloader = JmDownloader(self.option)
        
        # No downloads yet, should be True
        self.assertTrue(downloader.all_success)

    def test_all_success_property_with_failures(self):
        """Test all_success property when there are failures"""
        downloader = JmDownloader(self.option)
        
        # Add a failure
        fake_image = type('FakeImage', (), {'id': '1'})()
        downloader.download_failed_image.append((fake_image, Exception('test')))
        
        self.assertFalse(downloader.all_success)

    def test_raise_if_has_exception_no_failures(self):
        """Test raise_if_has_exception when there are no failures"""
        downloader = JmDownloader(self.option)
        
        # Should not raise
        try:
            downloader.raise_if_has_exception()
        except Exception as e:
            self.fail(f"Should not raise exception when no failures: {e}")

    def test_raise_if_has_exception_with_image_failures(self):
        """Test raise_if_has_exception with image failures"""
        downloader = JmDownloader(self.option)
        
        # Add fake image failure
        fake_image = type('FakeImage', (), {'id': '1', 'download_url': 'http://test.com/img.jpg'})()
        downloader.download_failed_image.append((fake_image, Exception('download failed')))
        
        # Should raise PartialDownloadFailedException
        with self.assertRaises(PartialDownloadFailedException) as context:
            downloader.raise_if_has_exception()
        
        exception = context.exception
        self.assertIn('部分下载失败', str(exception))
        self.assertIn('图片下载失败', str(exception))
        self.assertEqual(exception.downloader, downloader)

    def test_raise_if_has_exception_with_photo_failures(self):
        """Test raise_if_has_exception with photo failures"""
        downloader = JmDownloader(self.option)
        
        # Add fake photo failure
        fake_photo = type('FakePhoto', (), {'id': '123'})()
        downloader.download_failed_photo.append((fake_photo, Exception('photo failed')))
        
        # Should raise PartialDownloadFailedException
        with self.assertRaises(PartialDownloadFailedException) as context:
            downloader.raise_if_has_exception()
        
        exception = context.exception
        self.assertIn('部分下载失败', str(exception))
        self.assertIn('章节下载失败', str(exception))

    def test_raise_if_has_exception_with_both_failures(self):
        """Test raise_if_has_exception with both image and photo failures"""
        downloader = JmDownloader(self.option)
        
        # Add both types of failures
        fake_image = type('FakeImage', (), {'id': '1', 'download_url': 'http://test.com/img.jpg'})()
        fake_photo = type('FakePhoto', (), {'id': '123'})()
        downloader.download_failed_image.append((fake_image, Exception('img failed')))
        downloader.download_failed_photo.append((fake_photo, Exception('photo failed')))
        
        with self.assertRaises(PartialDownloadFailedException) as context:
            downloader.raise_if_has_exception()
        
        exception = context.exception
        msg = str(exception)
        self.assertIn('部分下载失败', msg)
        self.assertIn('章节下载失败', msg)
        self.assertIn('图片下载失败', msg)

    def test_do_filter_default_behavior(self):
        """Test do_filter returns detail unchanged by default"""
        downloader = JmDownloader(self.option)
        
        # Get a real photo detail
        photo = self.client.get_photo_detail('438516')
        
        # Default filter should return the same object
        filtered = downloader.do_filter(photo)
        self.assertEqual(filtered, photo)

    def test_do_filter_custom_implementation(self):
        """Test do_filter with custom filtering"""
        class FilteredDownloader(JmDownloader):
            def do_filter(self, detail):
                # Only download first 2 items
                if detail.is_photo():
                    return detail[0:2]
                return detail
        
        downloader = FilteredDownloader(self.option)
        photo = self.client.get_photo_detail('438516')
        
        filtered = downloader.do_filter(photo)
        self.assertEqual(len(filtered), 2)

    def test_context_manager_normal_exit(self):
        """Test downloader as context manager with normal exit"""
        with JmDownloader(self.option) as downloader:
            self.assertIsNotNone(downloader)
        # Should exit cleanly

    def test_context_manager_exception_exit(self):
        """Test downloader as context manager with exception"""
        try:
            with JmDownloader(self.option) as downloader:
                raise ValueError("test exception")
        except ValueError:
            pass  # Expected

    def test_downloader_use_class_method(self):
        """Test the use() class method to replace global downloader"""
        original_class = JmModuleConfig.CLASS_DOWNLOADER
        
        try:
            # Use custom downloader
            DoNotDownloadImage.use()
            self.assertEqual(JmModuleConfig.CLASS_DOWNLOADER, DoNotDownloadImage)
        finally:
            # Restore original
            JmModuleConfig.CLASS_DOWNLOADER = original_class

    def test_do_not_download_image_downloader(self):
        """Test DoNotDownloadImage downloader"""
        option = self.new_option()
        downloader = DoNotDownloadImage(option)
        
        # Get a photo
        photo = self.client.get_photo_detail('438516')
        image = photo[0]
        
        # Should not actually download, just create directory
        downloader.download_by_image_detail(image)
        
        # Verify directory was created but image not downloaded
        img_path = option.decide_image_filepath(image)
        img_dir = os.path.dirname(img_path)
        self.assertTrue(os.path.exists(img_dir))

    def test_just_download_specific_count_image_downloader(self):
        """Test JustDownloadSpecificCountImage downloader"""
        original_class = JmModuleConfig.CLASS_DOWNLOADER
        
        try:
            # Set to download only 2 images
            JustDownloadSpecificCountImage.use(count=2)
            
            option = self.new_option()
            downloader = JustDownloadSpecificCountImage(option)
            
            # Verify count is set
            self.assertEqual(downloader.count, 2)
            
            # Test countdown
            self.assertTrue(downloader.try_countdown())  # count becomes 1
            self.assertTrue(downloader.try_countdown())  # count becomes 0
            self.assertFalse(downloader.try_countdown())  # count is -1, should return False
            
        finally:
            JmModuleConfig.CLASS_DOWNLOADER = original_class

    def test_just_download_specific_count_thread_safety(self):
        """Test thread safety of JustDownloadSpecificCountImage countdown"""
        from threading import Thread
        
        JustDownloadSpecificCountImage.count = 10
        downloader = JustDownloadSpecificCountImage(self.option)
        
        results = []
        
        def countdown_worker():
            for _ in range(5):
                results.append(downloader.try_countdown())
        
        threads = [Thread(target=countdown_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have exactly 10 True results and rest False
        true_count = sum(1 for r in results if r)
        self.assertEqual(true_count, 10)

    def test_execute_on_condition_with_small_batch(self):
        """Test execute_on_condition uses thread pool for small batch"""
        downloader = JmDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        
        # Mock the apply function
        call_count = [0]
        
        def mock_apply(image):
            call_count[0] += 1
        
        # Execute with batch size smaller than total
        downloader.execute_on_condition(
            iter_objs=photo[0:5],
            apply=mock_apply,
            count_batch=2  # Smaller than 5, should use thread pool
        )
        
        # Should have called mock_apply for each image
        self.assertEqual(call_count[0], 5)

    def test_execute_on_condition_with_large_batch(self):
        """Test execute_on_condition uses multi-thread launcher for large batch"""
        downloader = JmDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        
        call_count = [0]
        
        def mock_apply(image):
            call_count[0] += 1
        
        # Execute with batch size larger than total
        downloader.execute_on_condition(
            iter_objs=photo[0:3],
            apply=mock_apply,
            count_batch=10  # Larger than 3, should use multi_thread_launcher
        )
        
        self.assertEqual(call_count[0], 3)

    def test_execute_on_condition_with_empty_list(self):
        """Test execute_on_condition with empty list after filtering"""
        class EmptyFilterDownloader(JmDownloader):
            def do_filter(self, detail):
                return []  # Return empty list
        
        downloader = EmptyFilterDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        
        call_count = [0]
        
        def mock_apply(image):
            call_count[0] += 1
        
        # Should not call apply at all
        downloader.execute_on_condition(
            iter_objs=photo,
            apply=mock_apply,
            count_batch=5
        )
        
        self.assertEqual(call_count[0], 0)

    def test_download_success_dict_structure(self):
        """Test that download_success_dict maintains correct structure"""
        class TrackingDownloader(DoNotDownloadImage):
            pass
        
        downloader = TrackingDownloader(self.option)
        
        # Download a small album
        album = downloader.download_album('438516')
        
        # Verify structure
        self.assertIn(album, downloader.download_success_dict)
        
        for photo in album:
            self.assertIn(photo, downloader.download_success_dict[album])
            # Each photo should have a list of downloaded images
            self.assertIsInstance(downloader.download_success_dict[album][photo], list)

    def test_callback_methods_called(self):
        """Test that callback methods are called during download"""
        class CallbackTracker(DoNotDownloadImage):
            def __init__(self, option):
                super().__init__(option)
                self.callbacks_called = []
            
            def before_album(self, album):
                self.callbacks_called.append('before_album')
                super().before_album(album)
            
            def after_album(self, album):
                self.callbacks_called.append('after_album')
                super().after_album(album)
            
            def before_photo(self, photo):
                self.callbacks_called.append('before_photo')
                super().before_photo(photo)
            
            def after_photo(self, photo):
                self.callbacks_called.append('after_photo')
                super().after_photo(photo)
            
            def before_image(self, image, img_save_path):
                self.callbacks_called.append('before_image')
                super().before_image(image, img_save_path)
            
            def after_image(self, image, img_save_path):
                self.callbacks_called.append('after_image')
                super().after_image(image, img_save_path)
        
        downloader = CallbackTracker(self.option)
        
        # Download a photo
        downloader.download_photo('438516')
        
        # Verify callbacks were called in order
        self.assertIn('before_photo', downloader.callbacks_called)
        self.assertIn('after_photo', downloader.callbacks_called)
        self.assertIn('before_image', downloader.callbacks_called)
        self.assertIn('after_image', downloader.callbacks_called)
        
        # before should come before after
        before_photo_idx = downloader.callbacks_called.index('before_photo')
        after_photo_idx = downloader.callbacks_called.index('after_photo')
        self.assertLess(before_photo_idx, after_photo_idx)

    def test_skip_flag_on_album(self):
        """Test that album with skip=True is not downloaded"""
        class SkipTestDownloader(DoNotDownloadImage):
            def __init__(self, option):
                super().__init__(option)
                self.photo_download_called = False
            
            def download_by_photo_detail(self, photo):
                self.photo_download_called = True
                super().download_by_photo_detail(photo)
        
        downloader = SkipTestDownloader(self.option)
        
        album = self.client.get_album_detail('438516')
        album.skip = True
        
        downloader.download_by_album_detail(album)
        
        # Should not have called photo download
        self.assertFalse(downloader.photo_download_called)

    def test_skip_flag_on_photo(self):
        """Test that photo with skip=True is not downloaded"""
        class SkipTestDownloader(DoNotDownloadImage):
            def __init__(self, option):
                super().__init__(option)
                self.image_download_called = False
            
            def download_by_image_detail(self, image):
                self.image_download_called = True
                super().download_by_image_detail(image)
        
        downloader = SkipTestDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        photo.skip = True
        
        downloader.download_by_photo_detail(photo)
        
        # Should not have called image download
        self.assertFalse(downloader.image_download_called)

    def test_skip_flag_on_image(self):
        """Test that image with skip=True is not downloaded"""
        downloader = DoNotDownloadImage(self.option)
        
        photo = self.client.get_photo_detail('438516')
        image = photo[0]
        image.skip = True
        
        # Should return early without downloading
        downloader.download_by_image_detail(image)
        
        # Verify it didn't try to download (no exception should be raised)

    def test_catch_exception_decorator_for_image(self):
        """Test that catch_exception decorator catches image download errors"""
        class FailingImageDownloader(JmDownloader):
            @catch_exception
            def download_by_image_detail(self, image):
                raise ValueError("Simulated image download failure")
        
        downloader = FailingImageDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        image = photo[0]
        
        # Should catch exception and add to failed list
        try:
            downloader.download_by_image_detail(image)
        except ValueError:
            pass  # Expected to re-raise
        
        # Should have recorded the failure
        self.assertEqual(len(downloader.download_failed_image), 1)
        self.assertEqual(downloader.download_failed_image[0][0], image)

    def test_catch_exception_decorator_for_photo(self):
        """Test that catch_exception decorator catches photo download errors"""
        class FailingPhotoDownloader(JmDownloader):
            @catch_exception
            def download_by_photo_detail(self, photo):
                raise RuntimeError("Simulated photo download failure")
        
        downloader = FailingPhotoDownloader(self.option)
        
        photo = self.client.get_photo_detail('438516')
        
        # Should catch exception and add to failed list
        try:
            downloader.download_by_photo_detail(photo)
        except RuntimeError:
            pass  # Expected to re-raise
        
        # Should have recorded the failure
        self.assertEqual(len(downloader.download_failed_photo), 1)
        self.assertEqual(downloader.download_failed_photo[0][0], photo)
