import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

project_dir = str(Path(__file__).resolve().parents[2])
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from usage.workflow_download import (
    WorkflowCompressionStats,
    WorkflowImageCompressPlugin,
    WorkflowImageCompressSummaryPlugin,
    compress_image_in_place,
)


class TestWorkflowImageCompression(unittest.TestCase):

    def test_stats_are_thread_safe(self):
        stats = WorkflowCompressionStats()

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _: stats.record(100, 40), range(100)))

        self.assertEqual((100, 10000, 4000), stats.snapshot())

    def test_image_and_summary_logs_include_compression_metrics(self):
        stats = WorkflowCompressionStats()
        image = type('ImageDetail', (), {'save_path': '/tmp/page.webp'})()
        image_logs = []
        image_plugin = WorkflowImageCompressPlugin(None)
        image_plugin.log = image_logs.append

        with patch(
            'usage.workflow_download.compress_image_in_place',
            return_value=('JPEG', 2048, 512, True, '/tmp/page.jpg', None),
        ):
            image_plugin.invoke(image=image, quality=80, stats=stats, convert_to_jpeg=True)

        self.assertEqual('/tmp/page.jpg', image.save_path)
        self.assertEqual((1, 2048, 512), stats.snapshot())
        self.assertIn('压缩比 4.00:1', image_logs[0])

        summary_logs = []
        summary_plugin = WorkflowImageCompressSummaryPlugin(None)
        summary_plugin.log = summary_logs.append
        summary_plugin.invoke(stats=stats)

        self.assertIn('总压缩比 4.00:1', summary_logs[0])
        self.assertIn('总压缩率 75.0%', summary_logs[0])

    def test_multi_frame_webp_is_preserved(self):
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / 'animated.webp'
            frames = [
                Image.new('RGB', (32, 32), color)
                for color in ('red', 'green', 'blue')
            ]
            frames[0].save(
                image_path,
                format='WEBP',
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
            )
            original_content = image_path.read_bytes()

            result = compress_image_in_place(str(image_path), quality=50, convert_to_jpeg=True)

            self.assertEqual('multi_frame', result[-1])
            self.assertEqual(original_content, image_path.read_bytes())
            with Image.open(image_path) as image:
                self.assertEqual(3, image.n_frames)


if __name__ == '__main__':
    unittest.main()
