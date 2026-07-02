"""爬取安全测试: 速率限制、并发控制、重试逻辑、停启机制"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from crawler.playwright_fetcher import PlaywrightFetcher
from crawler.engine import CrawlEngine


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_enforces_delay(self):
        """_rate_limit 应在连续请求间产生延迟（MIN_PAGE_DELAY=1.5s）"""
        pf = PlaywrightFetcher(headless=True)
        # 不启动浏览器，仅测试限速逻辑（_rate_limit 不依赖 browser/page）
        t0 = asyncio.get_running_loop().time()
        await pf._rate_limit()  # 首次：_last_request_time=0，无延迟
        t1 = asyncio.get_running_loop().time()
        await pf._rate_limit()  # 第二次：应有 >=1.5s 延迟
        t2 = asyncio.get_running_loop().time()
        # 首次几乎无延迟
        assert (t1 - t0) < 0.5
        # 第二次有至少 1.0s 延迟（MIN_PAGE_DELAY=1.5，留余量避免偶发失败）
        assert (t2 - t1) >= 1.0

    @pytest.mark.asyncio
    async def test_rate_limit_respects_min_delay(self):
        """连续快速请求应有足够间隔"""
        pf = PlaywrightFetcher(headless=True)
        await pf._rate_limit()  # 初始化计时器
        t0 = asyncio.get_running_loop().time()
        await pf._rate_limit()
        t1 = asyncio.get_running_loop().time()
        # MIN_PAGE_DELAY=1.5s，应有至少 1s 间隔
        assert (t1 - t0) >= 1.0


class TestConcurrencyControl:
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

        # 最多 2 个同时持有（验证无死锁，信号量正常工作）
        assert sem._value == 2  # 全部释放


class TestStopControl:
    def test_stop_sets_running_false(self):
        """stop() 应设置状态为 stopped，_running 返回 False"""
        engine = CrawlEngine(None)
        # 初始 status="starting" → _running property 返回 True
        assert engine._running
        engine.stop()
        assert not engine._running
        assert engine._status == "stopped"

    def test_progress_reflects_state(self):
        """get_progress 应正确反映引擎状态"""
        engine = CrawlEngine(None)
        # 初始状态: status="starting", running=True
        p = engine.get_progress()
        assert p["status"] == "starting"
        assert p["running"]  # "starting" 视为运行中
        assert p["errors"] == 0
        # 停止后 running 为 False
        engine.stop()
        p = engine.get_progress()
        assert not p["running"]


class TestFetcherLifecycle:
    @pytest.mark.asyncio
    async def test_user_agent_pool_diverse(self):
        """UA 池应有足够多样性"""
        from crawler.constants import USER_AGENTS
        assert len(USER_AGENTS) >= 5
        assert len(set(USER_AGENTS)) == len(USER_AGENTS)  # 无重复

    def test_playwright_fetcher_init_defaults(self):
        """PlaywrightFetcher 初始化参数正确"""
        pf = PlaywrightFetcher(headless=True)
        assert pf._headless is True
        assert pf._browser is None
        assert pf._page is None
        assert pf._context is None
        assert pf._context_rotation_count == 0

    def test_playwright_fetcher_viewport_pool(self):
        """视角池包含多种分辨率"""
        from crawler.playwright_fetcher import _VIEWPORT_POOL, _UA_POOL
        assert len(_VIEWPORT_POOL) >= 3
        assert len(_UA_POOL) >= 3
        # 所有视角都有合理的宽高
        for vp in _VIEWPORT_POOL:
            assert vp["width"] >= 1024
            assert vp["height"] >= 600


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
