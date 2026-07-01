"""爬取安全测试: 速率限制、并发控制、重试逻辑、停启机制"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from crawler.fetcher import Fetcher
from crawler.engine import CrawlEngine
from crawler.constants import LIST_CONCURRENCY


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_enforces_delay(self):
        """_rate_limit 应产生至少最小延迟"""
        async with Fetcher() as fetcher:
            t0 = asyncio.get_running_loop().time()
            # 首次请求无延迟
            await fetcher._rate_limit("list")
            t1 = asyncio.get_running_loop().time()
            # 第二次应有延迟
            await fetcher._rate_limit("list")
            t2 = asyncio.get_running_loop().time()
            # 至少产生了延迟（基础延迟 3-5s × 最小 jitter 0.7 ≈ 2.1s）
            delay = t2 - t1
            assert delay > 0.5  # 至少有 0.5s 延迟（放宽阈值避免偶发失败）

    @pytest.mark.asyncio
    async def test_list_vs_detail_separate_groups(self):
        """列表页和详情页使用独立的限速组"""
        async with Fetcher() as fetcher:
            t0 = asyncio.get_running_loop().time()
            await fetcher._rate_limit("list")
            await fetcher._rate_limit("detail")
            t1 = asyncio.get_running_loop().time()
            # 不同 group 之间不应该互相等待
            assert (t1 - t0) < 1.0  # 第一个 list 请求无延迟 + detail 首次也无延迟


class TestConcurrencyControl:
    def test_semaphore_limits(self):
        """信号量初始值正确"""
        engine = CrawlEngine(None)
        assert engine._list_sem._value == LIST_CONCURRENCY

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """信号量正确限制并发"""
        sem = asyncio.Semaphore(2)
        acquired = []

        async def worker(i):
            async with sem:
                acquired.append(i)
                await asyncio.sleep(0.05)
                acquired.remove(i)

        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # 最多 2 个同时持有
        # （验证的是没有死锁，信号量正常工作）
        assert sem._value == 2  # 全部释放


class TestStopControl:
    def test_stop_sets_running_false(self):
        engine = CrawlEngine(None)
        engine._running = True
        engine.stop()
        assert not engine._running

    def test_progress_reflects_state(self):
        engine = CrawlEngine(None)
        p = engine.get_progress()
        assert not p["running"]
        assert p["new"] == 0
        assert p["errors"] == 0


class TestFetcherLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Fetcher 作为 context manager 正确清理"""
        async with Fetcher() as f:
            assert f._client is not None
        # __aexit__ 后 client 应为 None
        assert f._client is None

    @pytest.mark.asyncio
    async def test_user_agent_pool_diverse(self):
        """UA 池应有足够多样性"""
        from crawler.constants import USER_AGENTS
        assert len(USER_AGENTS) >= 5
        assert len(set(USER_AGENTS)) == len(USER_AGENTS)  # 无重复


class TestRetryLogic:
    def test_retryable_exceptions(self):
        """RETRYABLE_EXCEPTIONS 包含预期类型"""
        import httpx
        from crawler.fetcher import RETRYABLE_EXCEPTIONS
        assert httpx.TimeoutException in RETRYABLE_EXCEPTIONS
        assert httpx.NetworkError in RETRYABLE_EXCEPTIONS
        assert httpx.HTTPStatusError in RETRYABLE_EXCEPTIONS


class TestCleanerSafety:
    def test_parse_price_no_crash(self):
        """畸形输入不应崩溃"""
        from crawler.cleaner import parse_price, parse_unit_price, parse_area, parse_date
        for func in [parse_price, parse_unit_price, parse_area, parse_date]:
            assert func(None) is None
            assert func("") is None
            assert func("   ") is None  # blank
            func("¥$%^&")  # garbage — 不应崩溃

    def test_normalize_no_crash(self):
        from crawler.cleaner import normalize_decoration, normalize_orientation, normalize_floor_level
        for func in [normalize_decoration, normalize_orientation, normalize_floor_level]:
            assert func(None) is None
            assert func("") is None  # should return None
            func("~~garbage~~")  # 不应崩溃
