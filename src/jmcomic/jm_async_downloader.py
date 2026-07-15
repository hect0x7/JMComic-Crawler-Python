"""
异步下载器 —— 对齐 sync JmDownloader

设计原则：
- 继承 JmDownloader，复用回调体系（before_album/after_album 等）和 plugin 调用
- 下载 IO（asyncio）与 CPU 解密（ThreadPoolExecutor）流水线化
- 通过 asyncio.Semaphore 控制并发
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from .jm_downloader import BaseDownloader
from .jm_entity import JmAlbumDetail, JmPhotoDetail, JmImageDetail
from .jm_toolkit import JmImageTool
from .jm_config import jm_log
from .jm_option import JmOption


class JmAsyncDownloader(BaseDownloader):
    """
    全异步流水线下载器。

    核心设计：
    - 下载 IO 与 CPU 解密（ThreadPoolExecutor）完全流水线化
    - 通过 asyncio.Semaphore 实现并发控制
    - 继承 JmDownloader 的回调体系和 Plugin 调用
    """

    def __init__(self,
                 option: JmOption,
                 image_concurrency: int | None = None,
                 photo_concurrency: int | None = None,
                 decode_worker: int | None = None,
                 ) -> None:
        super().__init__(option)
        # 提取图片并发配置（使用 is None 判断，避免 0 被 or 静默替换为默认值）
        image_concurrency = int(image_concurrency if image_concurrency is not None else option.download.threading.image)
        if image_concurrency <= 0:
            raise ValueError(f"image_concurrency must be > 0, got {image_concurrency}")

        photo_concurrency = int(photo_concurrency if photo_concurrency is not None else option.download.threading.photo)
        if photo_concurrency <= 0:
            raise ValueError(f"photo_concurrency must be > 0, got {photo_concurrency}")

        self._image_concurrency = image_concurrency
        self._image_semaphore = asyncio.Semaphore(image_concurrency)
        self._photo_semaphore = asyncio.Semaphore(photo_concurrency)

        # 解密线程池（CPU 密集操作卸载）
        self._decode_pool = ThreadPoolExecutor(max_workers=decode_worker, thread_name_prefix='jm-async-decode')

    # ======================================================================
    # 核心下载流程 — 对齐 sync JmDownloader
    # ======================================================================

    async def download_album(self, album_id) -> JmAlbumDetail:
        """对齐 sync JmDownloader.download_album"""
        album = await self.client.get_album_detail(album_id)
        await self.download_by_album_detail(album)
        return album

    async def download_by_album_detail(self, album: JmAlbumDetail):
        """
        异步下载整个本子。
        对齐 sync JmDownloader.download_by_album_detail 的回调链路。
        """
        await self.before_album(album)
        if album.skip:
            return

        photos = list(self.do_filter(album))

        # 即使过滤后 photos 为空，也要执行 after_album（对齐 sync：execute_on_condition
        # 在 count_real==0 时提前返回，但调用方仍会走到 after_album，触发其插件与 Feature）。
        if photos:
            # photo 级并发由 _photo_semaphore 控制（默认 3），包裹整段 photo 下载（见 download_by_photo_detail）。
            photo_tasks = [self._safe_download_photo(photo) for photo in photos]
            await asyncio.gather(*photo_tasks)

        await self.after_album(album)

    async def _safe_download_photo(self, photo: JmPhotoDetail):
        """包装 download_by_photo_detail，对齐 sync @catch_exception 的异常记录"""
        try:
            await self.download_by_photo_detail(photo)
        except Exception as e:
            jm_log('photo.failed', f'章节下载失败: [{photo.id}], 异常: [{e}]', e)
            self.download_failed_photo.append((photo, e))

    async def download_photo(self, photo_id) -> JmPhotoDetail:
        """对齐 sync JmDownloader.download_photo"""
        photo = await self.client.get_photo_detail(photo_id)
        await self.download_by_photo_detail(photo)
        return photo

    async def download_by_photo_detail(self, photo: JmPhotoDetail):
        """
        异步下载一个章节的所有图片。
        对齐 sync JmDownloader.download_by_photo_detail 的回调链路。
        """
        # _photo_semaphore 包裹整段 photo 下载（check_photo + 全部图片），
        # 真正限制「同时下载的章节数」（对齐 sync：每个 photo 占用 photo 线程池一个槽位）。
        # 章节内图片再由共享的 _image_semaphore 二级限流。
        async with self._photo_semaphore:
            await self.client.check_photo(photo)

            await self.before_photo(photo)
            if photo.skip:
                return

            images = self.do_filter(photo)
            image_list = list(images) if images is not None else []

            # 即使过滤后图片为空，也要执行 after_photo（对齐 sync，触发 after_photo 插件与 Feature）。
            if image_list:
                # 直接创建所有下载协程，由 _image_semaphore 实现滑动窗口流控
                download_tasks = [
                    self._safe_download_image(image)
                    for image in image_list
                ]
                await asyncio.gather(*download_tasks)

            await self.after_photo(photo)

    async def _safe_download_image(self, image: JmImageDetail):
        """
        包装 _download_single_image，对齐 sync @catch_exception 的异常记录。
        异常由此统一捕获和记录，不再在内部重复 try/except。
        """
        try:
            await self._download_single_image(image)
        except Exception as e:
            jm_log('image.failed', f'图片下载失败: [{image.download_url}], 异常: [{e}]', e)
            self.download_failed_image.append((image, e))

    async def _download_single_image(self, image: JmImageDetail):
        """
        下载并解密单张图片的完整流程。
        对齐 sync JmDownloader.download_by_image_detail 的逻辑。
        """
        img_save_path = self.option.decide_image_filepath(image)
        image.save_path = img_save_path
        image.exists = os.path.exists(img_save_path)
        image.cache = self.option.decide_download_cache(image)

        await self.before_image(image, img_save_path)
        if image.skip:
            return

        # 检查缓存，跳过下载
        if image.cache and image.exists:
            return

        decode_image = self.option.decide_download_image_decode(image)

        # 异步下载图片（受 image semaphore 限流，并将解密写盘过程也锁入信号量范围内，防大字节积压）
        async with self._image_semaphore:
            img_resp = await self.client.get_jm_image(image.download_url)
            img_bytes = img_resp.content

            # 提交到线程池解密并保存
            loop = asyncio.get_running_loop()
            if decode_image and image.scramble_id:
                await loop.run_in_executor(
                    self._decode_pool,
                    self._decode_and_save,
                    img_bytes,
                    int(image.scramble_id),
                    int(image.aid),
                    image.img_file_name,
                    img_save_path,
                )
            else:
                # 不解密保存。对齐 sync transfer_to(decode_image=False)：
                # 当目标后缀与原图后缀不一致时，需经 PIL 做格式转换。
                # 与 sync 一致：比较后缀前先剥离 url 的 ?query 部分，避免 query 干扰后缀判定。
                from common import suffix_not_equal
                img_url = image.download_url
                qi = img_url.find('?')
                if qi != -1:
                    img_url = img_url[:qi]
                need_convert = suffix_not_equal(img_url, img_save_path)
                await loop.run_in_executor(
                    self._decode_pool,
                    self._save_raw,
                    img_bytes,
                    img_save_path,
                    need_convert,
                )

        await self.after_image(image, img_save_path)

    # ======================================================================
    # 磁盘写入（在线程池中执行）
    # ======================================================================

    @staticmethod
    def _decode_and_save(image_bytes, scramble_id, aid, img_file_name, save_path):
        """
        解密图片并保存到磁盘（在线程池中执行）。
        与 Sync 版对齐的直接写文件方式。
        保存目录已由 decide_image_filepath(ensure_exists=True) 创建，此处不重复 makedirs。
        """
        num = JmImageTool.get_num(scramble_id, aid, img_file_name)
        img_src = JmImageTool.open_image(image_bytes)
        JmImageTool.decode_and_save(num, img_src, save_path)

    @staticmethod
    def _save_raw(image_bytes, save_path, need_convert=False):
        """
        不解密保存。
        - need_convert=False：直接写原始字节（如 .gif，或后缀与原图一致时）。
        - need_convert=True：经 PIL 按 save_path 后缀做格式转换（对齐 sync save_resp_img）。
        保存目录已由 decide_image_filepath(ensure_exists=True) 创建，此处不重复 makedirs。
        """
        if need_convert:
            JmImageTool.save_image(JmImageTool.open_image(image_bytes), save_path)
        else:
            with open(save_path, 'wb') as f:
                f.write(image_bytes)

    # ======================================================================
    # 生命周期
    # ======================================================================

    async def before_album(self, album: JmAlbumDetail):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().before_album, album)

    async def after_album(self, album: JmAlbumDetail):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().after_album, album)

    async def before_photo(self, photo: JmPhotoDetail):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().before_photo, photo)

    async def after_photo(self, photo: JmPhotoDetail):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().after_photo, photo)

    async def before_image(self, image: JmImageDetail, img_save_path: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().before_image, image, img_save_path)

    async def after_image(self, image: JmImageDetail, img_save_path: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._decode_pool, super().after_image, image, img_save_path)

    def shutdown(self):
        """关闭解密线程池"""
        self._decode_pool.shutdown(wait=False)

    async def __aenter__(self):
        # 创建并独占一个 async client（含 AsyncSession）。
        self.client = self.option.new_jm_async_client(max_clients=self._image_concurrency)
        try:
            await self.client.setup()
        except BaseException:
            try:
                await self.client.close()
            except BaseException as cleanup_error:
                jm_log('dler.cleanup.exception',
                       f'初始化失败后的资源清理也发生异常: {cleanup_error}', cleanup_error)
            finally:
                self.client = None
                self.shutdown()
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 关闭顺序：先关网络 client（释放 AsyncSession / libcurl multi handle / 后台任务），
        # 再关解密线程池。两者都要在异常路径下保证释放。
        try:
            if self.client is not None:
                await self.client.close()
        finally:
            self.client = None
            self.shutdown()

        if exc_type is not None:
            jm_log('dler.exception',
                   f'{self.__class__.__name__} Exit with exception: {exc_type, str(exc_val)}')
