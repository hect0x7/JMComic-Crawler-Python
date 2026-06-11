"""
Async vs Sync 性能评测脚本

对标本项目内置的 JmAsyncDownloader 与 JmDownloader，分两个维度独立计时：
  1. 元数据查询（get_album_detail + check_photo）
  2. 图片下载与解密

设计：
  - 并发配置对齐，排除变量干扰
  - 每轮物理清空下载目录，禁用缓存
  - 多轮取均值，CI 全量 / 本地限量
  - 输出 Markdown 报告到 PERFORMANCE_REPORT.md
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
import random

# 确保能找到本项目源码
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import jmcomic
from jmcomic import (
    JmOption, JmDownloader, JmAlbumDetail,
    create_option, jm_log,
)
from jmcomic.jm_async_downloader import JmAsyncDownloader

# ================================================================
#  全局配置 — 环境感知
# ================================================================

ALBUM_ID = os.environ.get('BENCHMARK_ALBUM_ID', '350234')
CONCURRENCY = int(os.environ.get('BENCHMARK_CONCURRENCY', '8'))

# 配置文件路径（CI 与本地兼容）
_OPTION_CANDIDATES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../assets/option/option_test_api.yml')),
]
OPTION_PATH = next((p for p in _OPTION_CANDIDATES if os.path.exists(p)), _OPTION_CANDIDATES[0])

IS_CI = os.environ.get('GITHUB_ACTIONS') == 'true'
LIMIT_IMAGES: int | None = None if IS_CI else 3  # 本地限 3 张，CI 全量
TEST_ROUNDS = 5 if IS_CI else 3
CI_REPEAT = 3 if IS_CI else 1  # CI 每轮重复下载次数，模拟批量压力


# ================================================================
#  工具函数
# ================================================================

def new_option(name: str) -> tuple[JmOption, str]:
    """
    创建对齐后的 option 实例与隔离的临时下载目录。
    同步/异步共享同一套并发配置，禁用缓存和插件。
    """
    option = create_option(OPTION_PATH)

    # 1. 对齐并发
    option.download.threading.image = CONCURRENCY
    option.download.threading.photo = CONCURRENCY

    # 2. 禁用缓存
    option.download['cache'] = False
    option.decide_download_cache = lambda _img: False

    # 3. 禁用插件
    option.plugins = {}

    # 4. 隔离下载目录
    base_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     f'../assets/temp_{name}_{random.randint(10000, 99999)}')
    )
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.makedirs(base_dir, exist_ok=True)
    option.dir_rule.base_dir = base_dir

    return option, base_dir


def clean_download_dir(base_dir: str):
    """清空下载目录下的所有子目录"""
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)


# ================================================================
#  Sync 维度
# ================================================================

def run_sync_query(option: JmOption) -> tuple[float | None, JmAlbumDetail | None]:
    """同步查询评测"""
    start = time.time()
    try:
        client = option.new_jm_client()
        album = None
        for _ in range(CI_REPEAT):
            album = client.get_album_detail(ALBUM_ID)
            for photo in album:
                client.check_photo(photo)
        return time.time() - start, album
    except Exception as e:
        print(f'  ❌ Sync Query 失败: {e}')
        return None, None


def run_sync_download(option: JmOption, album: JmAlbumDetail, base_dir: str) -> float | None:
    """同步下载评测"""
    start = time.time()
    try:
        for rep in range(CI_REPEAT):
            if rep > 0:
                clean_download_dir(base_dir)

            dler = JmDownloader(option)
            if LIMIT_IMAGES is not None:
                orig_filter = dler.do_filter
                dler.do_filter = lambda objs: (
                    objs[:LIMIT_IMAGES]
                    if objs and hasattr(objs[0], 'img_url')
                    else orig_filter(objs)
                )
            dler.download_by_album_detail(album)
        return time.time() - start
    except Exception as e:
        print(f'  ❌ Sync Download 失败: {e}')
        return None


# ================================================================
#  Async 维度
# ================================================================

async def run_async_query(option: JmOption) -> tuple[float | None, JmAlbumDetail | None]:
    """异步查询评测"""
    start = time.time()
    try:
        async with await option.new_jm_async_client() as client:
            album = None
            for _ in range(CI_REPEAT):
                album = await client.get_album_detail(ALBUM_ID)
                await asyncio.gather(*(client.check_photo(photo) for photo in album))
            return time.time() - start, album
    except Exception as e:
        print(f'  ❌ Async Query 失败: {e}')
        return None, None


async def run_async_download(option: JmOption, album: JmAlbumDetail, base_dir: str) -> float | None:
    """异步下载评测"""
    start = time.time()
    try:
        async with JmAsyncDownloader(option) as dler:
            for rep in range(CI_REPEAT):
                if rep > 0:
                    clean_download_dir(base_dir)
                    dler.download_failed_image.clear()
                    dler.download_failed_photo.clear()

                if LIMIT_IMAGES is not None:
                    orig_filter = dler.do_filter
                    dler.do_filter = lambda objs: (
                        objs[:LIMIT_IMAGES]
                        if objs and hasattr(objs[0], 'img_url')
                        else orig_filter(objs)
                    )
                await dler.download_by_album_detail(album)

            if dler.download_failed_image:
                print(f'  ⚠️ Async 下载存在 {len(dler.download_failed_image)} 张失败图片')

        return time.time() - start
    except Exception as e:
        print(f'  ❌ Async Download 失败: {e}')
        import traceback
        traceback.print_exc()
        return None


# ================================================================
#  主流程
# ================================================================

async def run_benchmark():
    print(f'🚀 开始 Async vs Sync 性能评测 (并发={CONCURRENCY}, 轮次={TEST_ROUNDS})')
    print(f'🌍 环境: CI={IS_CI}, 图片限制={LIMIT_IMAGES or "全量"}, Album={ALBUM_ID}')

    stats_query = {'Sync': [], 'Async': []}
    stats_download = {'Sync': [], 'Async': []}

    for r in range(TEST_ROUNDS):
        print(f'\n--- 第 {r + 1}/{TEST_ROUNDS} 轮 ---')

        # ── Sync ──
        opt_sync, dir_sync = new_option('sync')

        t_sq, album_sync = await asyncio.to_thread(run_sync_query, opt_sync)
        if t_sq is not None:
            stats_query['Sync'].append(t_sq)
            print(f'  Sync  查询: {t_sq:.4f}s')

        if album_sync is not None:
            t_sd = await asyncio.to_thread(run_sync_download, opt_sync, album_sync, dir_sync)
            if t_sd is not None:
                stats_download['Sync'].append(t_sd)
                print(f'  Sync  下载: {t_sd:.4f}s')

        shutil.rmtree(dir_sync, ignore_errors=True)

        # ── Async ──
        opt_async, dir_async = new_option('async')

        t_aq, album_async = await run_async_query(opt_async)
        if t_aq is not None:
            stats_query['Async'].append(t_aq)
            print(f'  Async 查询: {t_aq:.4f}s')

        if album_async is not None:
            t_ad = await run_async_download(opt_async, album_async, dir_async)
            if t_ad is not None:
                stats_download['Async'].append(t_ad)
                print(f'  Async 下载: {t_ad:.4f}s')

        shutil.rmtree(dir_async, ignore_errors=True)

    # ── 汇总 ──
    def avg(lst):
        return sum(lst) / len(lst) if lst else 0

    avgs = {
        'sq': avg(stats_query['Sync']),
        'aq': avg(stats_query['Async']),
        'sd': avg(stats_download['Sync']),
        'ad': avg(stats_download['Async']),
    }

    # ── 生成 Markdown 报告 ──
    def perf_line(sync_val, async_val):
        if sync_val > 0 and async_val > 0:
            diff = sync_val - async_val
            pct = abs(diff / sync_val) * 100
            word = '提升' if diff > 0 else '下降'
            return f'🏆 结论: **性能{word} {pct:.2f}%**（Async {"快" if diff > 0 else "慢"} {abs(diff):.4f}s）\n'
        return '⚠️ 数据不足，无法计算\n'

    report = (
        f'# 🔬 Async vs Sync 性能对比报告\n\n'
        f'| 配置项 | 值 |\n'
        f'| :--- | :--- |\n'
        f'| 运行环境 | {"GitHub Actions (CI)" if IS_CI else "本地开发"} |\n'
        f'| Album | {ALBUM_ID} |\n'
        f'| 图片规模 | {"全量" if IS_CI else f"限制 {LIMIT_IMAGES} 张"} |\n'
        f'| 并发配置 | {CONCURRENCY} |\n'
        f'| 测试轮次 | {TEST_ROUNDS} 轮 × {CI_REPEAT} 次重复 |\n'
        f'| 缓存策略 | 强制禁用，每轮物理清空 |\n\n'
        f'## 📊 元数据查询性能\n\n'
        f'| 模式 | 平均耗时 | 状态 |\n'
        f'| :--- | :--- | :--- |\n'
        f'| Sync  Query | {avgs["sq"]:.4f}s | {"✅" if avgs["sq"] > 0 else "❌"} |\n'
        f'| Async Query | {avgs["aq"]:.4f}s | {"✅" if avgs["aq"] > 0 else "❌"} |\n\n'
        f'{perf_line(avgs["sq"], avgs["aq"])}\n'
        f'## 📊 图片下载与解密性能\n\n'
        f'| 模式 | 平均耗时 | 状态 |\n'
        f'| :--- | :--- | :--- |\n'
        f'| Sync  Download | {avgs["sd"]:.4f}s | {"✅" if avgs["sd"] > 0 else "❌"} |\n'
        f'| Async Download | {avgs["ad"]:.4f}s | {"✅" if avgs["ad"] > 0 else "❌"} |\n\n'
        f'{perf_line(avgs["sd"], avgs["ad"])}'
    )

    with open('PERFORMANCE_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f'\n✅ 评测完成，报告已生成: PERFORMANCE_REPORT.md')
    print(f'Query    Sync={avgs["sq"]:.4f}s  Async={avgs["aq"]:.4f}s')
    print(f'Download Sync={avgs["sd"]:.4f}s  Async={avgs["ad"]:.4f}s')


if __name__ == '__main__':
    # 隔离系统代理干扰
    os.environ['no_proxy'] = '*'
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    asyncio.run(run_benchmark())
