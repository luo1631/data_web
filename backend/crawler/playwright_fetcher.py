"""
Playwright 爬虫 — 使用本机 Edge 浏览器绕过滑块验证。

cq.esf.fang.com 的 /house/ 路径要求 JS 滑块验证，
Edge 真实浏览器指纹可直接通过。

v2.0: 支持运行时上下文轮换 (rotate_context)，降低长时间爬取的指纹追踪风险。

用法:
    async with PlaywrightFetcher() as pf:
        html, url = await pf.fetch_page(page=2, fang_code="a058")
        # 每 N 页后可轮换上下文
        await pf.rotate_context()
"""

import asyncio
import logging
import random

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from crawler.constants import SEED_URL, DISTRICT_LIST_URL, DISTRICT_LIST_PAGE_URL

logger = logging.getLogger(__name__)

PAGE_LOAD_TIMEOUT = 30_000
ELEMENT_WAIT_TIMEOUT = 10_000
MIN_PAGE_DELAY = 1.5
MAX_PAGE_DELAY = 3.0
CAPTCHA_EXTRA_DELAY = 8.0
PROGRESSIVE_DELAY_PER_10 = 0.5
NAVIGATE_RETRIES = 3
NAVIGATE_RETRY_DELAY = 2.0
NAVIGATE_RETRY_BACKOFF = 4.0

# 多 UA 池 — 上下文轮换时随机选取
_UA_POOL = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Chrome on Windows (older)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

# 视角池 — 模拟不同屏幕
_VIEWPORT_POOL = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1200},
]


class PlaywrightFetcher:
    """基于本机 Edge 的页面抓取器，支持上下文轮换。"""

    def __init__(self, headless: bool = True, lite_mode: bool = False):
        self._headless = headless
        self._lite_mode = lite_mode  # 轻量模式：最低限度反检测，用于安居客等
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._last_request_time = 0.0
        self._context_rotation_count = 0

    async def __aenter__(self) -> "PlaywrightFetcher":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            channel="msedge",
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-proxy-server",          # 绕过系统代理，直连 fang.com
            ],
        )
        await self._create_context()
        return self

    async def __aexit__(self, *args) -> None:
        for obj in [self._page, self._context, self._browser, self._playwright]:
            if obj:
                try:
                    c = obj.close() if hasattr(obj, 'close') else obj.stop()
                    if asyncio.iscoroutine(c):
                        await c
                except Exception:
                    pass

    # ── 上下文轮换 ──────────────────────────────────

    async def rotate_context(self) -> None:
        """关闭当前上下文，用新的 UA/视角重新创建。

        清除所有 cookies、localStorage、sessionStorage，
        防止长时间爬取被指纹追踪。
        """
        self._context_rotation_count += 1

        # 关闭旧上下文
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        # 轮换前短暂休息（模拟人类关闭浏览器→重开的时间间隔）
        rest = random.uniform(3.0, 8.0)
        logger.debug(f"上下文轮换 #{self._context_rotation_count}: 休息 {rest:.1f}s")
        await asyncio.sleep(rest)

        await self._create_context()

        # 重新播种（访问首页建立初始 cookie）
        await self._seed()

        logger.info(
            f"[Rotate] context rotation complete (#{self._context_rotation_count})"
        )

    async def _create_context(self) -> None:
        """创建新的浏览器上下文，使用随机指纹参数。"""
        ua = random.choice(_UA_POOL)
        vp = random.choice(_VIEWPORT_POOL)

        self._context = await self._browser.new_context(
            user_agent=ua,
            viewport=vp,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            geolocation={
                "longitude": 106.55 + random.uniform(-0.1, 0.1),
                "latitude": 29.57 + random.uniform(-0.1, 0.1),
            },
            permissions=["geolocation"],
        )

        # 反检测脚本 — lite_mode 只用最低限度脚本
        if self._lite_mode:
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
            """)
        else:
            await self._context.add_init_script("""
                // 隐藏 webdriver 标记
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                // 模拟 Chrome 对象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                // 覆盖 permissions.query
                const origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({
                        state: Notification.permission,
                        onchange: null
                    }) : origQuery(parameters)
                );
                // 覆盖 plugins 数组（真实浏览器有插件）
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                // 覆盖 languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            """)

        self._page = await self._context.new_page()
        self._page.set_default_timeout(PAGE_LOAD_TIMEOUT)
        self._last_request_time = 0.0

        logger.debug(
            f"新上下文: UA={ua[:60]}..., viewport={vp['width']}x{vp['height']}"
        )

    # ── 页面抓取 ────────────────────────────────────

    async def fetch_page(
        self, page: int = 1, fang_code: str | None = None
    ) -> tuple[str, str]:
        """抓取 fang.com 列表页。

        Args:
            page: 页码（从 1 开始）
            fang_code: 区县代码（如 "a058"），None 则为全局列表
        """
        if fang_code:
            if page <= 1:
                url = DISTRICT_LIST_URL.format(code=fang_code)
            else:
                url = DISTRICT_LIST_PAGE_URL.format(
                    code=fang_code, page=str(page)
                )
        else:
            url = SEED_URL

        await self._rate_limit(page=page)
        html = await self._navigate(url)

        if self.is_captcha_page(html):
            logger.warning(
                f"验证码页: page {page} ({fang_code}), "
                f"额外等待 {CAPTCHA_EXTRA_DELAY}s"
            )
            await asyncio.sleep(CAPTCHA_EXTRA_DELAY)

        return html, url

    async def fetch_url(
        self, url: str, page: int = 1, delay_range: tuple[float, float] = (3.0, 6.0)
    ) -> tuple[str, str]:
        """抓取任意 URL（用于安居客等非 fang.com 站点）。

        Args:
            url: 完整 URL
            page: 页码（用于限速计算）
            delay_range: (min, max) 延迟范围（秒）
        """
        await self._rate_limit_anjuke(page=page, delay_range=delay_range)
        html = await self._navigate_generic(url)
        return html, url

    async def _navigate_generic(self, url: str) -> str:
        """通用导航 — 不等 fang.com 选择器，直接获取内容后返回。

        用于安居客等非 fang.com 站点，避免 wait_for_selector 超时
        期间触发目标站点的 bot 检测。
        """
        last_error = ""
        for attempt in range(1, NAVIGATE_RETRIES + 1):
            try:
                await self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_LOAD_TIMEOUT,
                )
                # 等待页面渲染（不等特定选择器）
                await asyncio.sleep(1.5)

                content = await self._page.content()
                if content and len(content) > 500:
                    return content
                last_error = f"内容过短 ({len(content)} bytes)"

            except PlaywrightTimeout as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)

            if attempt < NAVIGATE_RETRIES:
                wait = 5 + attempt * 3
                await asyncio.sleep(wait)

        logger.error(f"导航失败 after {NAVIGATE_RETRIES} attempts: {url}")
        try:
            return await self._page.content()
        except Exception:
            return ""

    async def _navigate(self, url: str) -> str:
        """导航到 URL 并返回页面内容，最多重试 NAVIGATE_RETRIES 次。"""
        last_error = ""
        for attempt in range(1, NAVIGATE_RETRIES + 1):
            try:
                await self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_LOAD_TIMEOUT,
                )
                # 等待关键元素（多种可能的选择器）
                try:
                    await self._page.wait_for_selector(
                        "dl[data-bg], dl[data-bgfp], .shop_list, li.listhouse, .houseList dl",
                        timeout=ELEMENT_WAIT_TIMEOUT,
                    )
                except Exception:
                    # 选择器超时 → 可能是 JS 慢渲染或页面结构变化
                    await asyncio.sleep(2.0)

                # 模拟人类行为：偶尔滚动
                if random.random() < 0.3:
                    try:
                        await self._page.evaluate(
                            f"window.scrollBy(0, {random.randint(200, 800)})"
                        )
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                    except Exception:
                        pass

                content = await self._page.content()
                if content and len(content) > 500:
                    return content
                last_error = f"内容过短 ({len(content)} bytes)"

            except PlaywrightTimeout as e:
                last_error = str(e)
                logger.warning(
                    f"导航超时 attempt {attempt}/{NAVIGATE_RETRIES}: {url}"
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"导航失败 attempt {attempt}/{NAVIGATE_RETRIES}: {e}"
                )

            if attempt < NAVIGATE_RETRIES:
                wait = NAVIGATE_RETRY_DELAY + attempt * NAVIGATE_RETRY_BACKOFF
                logger.info(
                    f"  等待 {wait:.0f}s 后重试 {attempt+1}/{NAVIGATE_RETRIES}"
                )
                await asyncio.sleep(wait)

        logger.error(
            f"全部 {NAVIGATE_RETRIES} 次导航失败: {url} — {last_error}"
        )
        try:
            return await self._page.content()
        except Exception:
            return ""

    # ── 辅助 ────────────────────────────────────────

    async def _seed(self) -> None:
        """访问首页建立初始 cookie / 会话。"""
        try:
            await self._page.goto(
                SEED_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_LOAD_TIMEOUT,
            )
            await asyncio.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            logger.debug(f"Seed 失败 (非致命): {e}")

    async def _rate_limit(
        self, page: int = 1, captcha_encountered: bool = False
    ) -> None:
        """翻页限速：基础延迟 + 渐进增量 + 少量随机抖动。

        page: 当前页码，页数越高延迟越大（模拟人类浏览速度衰减）
        captcha_encountered: 是否刚遇到验证码
        """
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time

        # 基础随机延迟
        base = random.uniform(MIN_PAGE_DELAY, MAX_PAGE_DELAY)
        # 翻页渐进
        progressive = (page // 10) * PROGRESSIVE_DELAY_PER_10
        # 验证码惩罚
        captcha_penalty = CAPTCHA_EXTRA_DELAY if captcha_encountered else 0
        # 随机抖动 (±20%)
        jitter = random.uniform(-0.2, 0.2) * base

        target = base + progressive + captcha_penalty + jitter
        target = max(0.8, target)  # 最小 0.8s

        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()

    async def _rate_limit_anjuke(
        self, page: int = 1, delay_range: tuple[float, float] = (3.0, 6.0)
    ) -> None:
        """安居客专用限速 — 比 fang.com 更保守，避免 IP 限速。

        Args:
            page: 当前页码
            delay_range: (min_seconds, max_seconds)
        """
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time

        base = random.uniform(*delay_range)
        # 翻页渐进: 每 10 页 +1s
        progressive = (page // 10) * 1.0
        # 随机抖动 ±30%
        jitter = random.uniform(-0.3, 0.3) * base

        target = base + progressive + jitter
        target = max(delay_range[0], target)

        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()

    @staticmethod
    def is_captcha_page(html: str) -> bool:
        """检测页面是否为 fang.com 验证码页面。"""
        if not html:
            return False
        if len(html) < 2000 and (
            "请完成下列验证" in html or "slider" in html
        ):
            return True
        if "请完成下列验证后继续" in html:
            return True
        if "checkyzm" in html and len(html) < 5000:
            return True
        return False
