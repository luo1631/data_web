"""
Playwright 爬虫 — 使用本机 Edge 浏览器绕过滑块验证。

cq.esf.fang.com 的 /house/ 路径要求 JS 滑块验证，
Edge 真实浏览器指纹可直接通过。

用法:
    async with PlaywrightFetcher() as pf:
        html, url = await pf.fetch_page(page=2)
"""

import asyncio
import logging
import random

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from crawler.constants import SEED_URL, DISTRICT_LIST_URL, DISTRICT_LIST_PAGE_URL

logger = logging.getLogger(__name__)

PAGE_LOAD_TIMEOUT = 30_000
ELEMENT_WAIT_TIMEOUT = 10_000
MIN_PAGE_DELAY = 1.5
MAX_PAGE_DELAY = 3.0
CAPTCHA_EXTRA_DELAY = 8.0     # 被反爬时额外等待
PROGRESSIVE_DELAY_PER_10 = 0.5 # 每 10 页加 0.5s
NAVIGATE_RETRIES = 3
NAVIGATE_RETRY_DELAY = 2.0
NAVIGATE_RETRY_BACKOFF = 4.0    # 每次重试前额外等待（指数增长: 2s, 6s, 10s）


class PlaywrightFetcher:
    """基于本机 Edge 的页面抓取器。"""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._viewport = {"width": 1920, "height": 1080}
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._last_request_time = 0.0

    async def __aenter__(self) -> "PlaywrightFetcher":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            channel="msedge",
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
            ),
            viewport=self._viewport,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            geolocation={"longitude": 106.55, "latitude": 29.57},
        )
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
            const orig = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : orig(p);
        """)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(PAGE_LOAD_TIMEOUT)
        await self._seed()
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

    async def fetch_page(self, page: int = 1, fang_code: str | None = None) -> tuple[str, str]:
        """抓取列表页。

        Args:
            page: 页码（从 1 开始）
            fang_code: 区县代码（如 \"a058\"），None 则为全局列表
        """
        if fang_code:
            if page <= 1:
                url = DISTRICT_LIST_URL.format(code=fang_code)
            else:
                url = DISTRICT_LIST_PAGE_URL.format(code=fang_code, page=str(page))
        else:
            url = SEED_URL if page <= 1 else DISTRICT_LIST_PAGE_URL.format(code="", page=str(page))  # won't work for global
        await self._rate_limit(page=page)
        html = await self._navigate(url)
        # 检测验证码页：遇到则额外等待，让后续请求降速
        if self.is_captcha_page(html):
            logger.warning(f"Captcha page detected at page {page} ({fang_code}), waiting extra {CAPTCHA_EXTRA_DELAY}s")
            await asyncio.sleep(CAPTCHA_EXTRA_DELAY)
        return html, url

    async def _navigate(self, url: str) -> str:
        """导航到 URL 并返回页面内容，最多重试 NAVIGATE_RETRIES 次。"""
        last_error = ""
        for attempt in range(1, NAVIGATE_RETRIES + 1):
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                try:
                    await self._page.wait_for_selector(
                        "dl[data-bg], .shop_list, li.listhouse",
                        timeout=ELEMENT_WAIT_TIMEOUT,
                    )
                except Exception:
                    await asyncio.sleep(1.5)   # 选择器超时，JS 慢渲染
                content = await self._page.content()
                if content and len(content) > 500:
                    return content
                last_error = f"empty content ({len(content)} bytes)"
            except PlaywrightTimeout as e:
                last_error = str(e)
                logger.warning(f"Navigate attempt {attempt}/{NAVIGATE_RETRIES} timeout: {url}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Navigate attempt {attempt}/{NAVIGATE_RETRIES} failed: {e}")

            if attempt < NAVIGATE_RETRIES:
                wait = NAVIGATE_RETRY_DELAY + attempt * NAVIGATE_RETRY_BACKOFF
                logger.info(f"  waiting {wait:.0f}s before retry {attempt+1}/{NAVIGATE_RETRIES}")
                await asyncio.sleep(wait)

        logger.error(f"All {NAVIGATE_RETRIES} navigate attempts failed for {url}: {last_error}")
        try:
            return await self._page.content()
        except Exception:
            return ""

    async def _seed(self) -> None:
        try:
            await self._page.goto(SEED_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.warning(f"Seed failed: {e}")

    async def _rate_limit(self, page: int = 1, captcha_encountered: bool = False) -> None:
        """翻页限速：基础延迟 + 翻页渐进增量 + 验证码惩罚。

        page: 当前页码，页数越高延迟越大（模拟人类浏览速度衰减）
        captcha_encountered: 是否刚遇到验证码，需要额外等待
        """
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time

        # 基础随机延迟
        base = random.uniform(MIN_PAGE_DELAY, MAX_PAGE_DELAY)
        # 翻页渐进：每 10 页加 PROGRESSIVE_DELAY_PER_10 秒
        progressive = (page // 10) * PROGRESSIVE_DELAY_PER_10
        # 验证码惩罚
        captcha_penalty = CAPTCHA_EXTRA_DELAY if captcha_encountered else 0

        target = base + progressive + captcha_penalty
        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()

    @staticmethod
    def is_captcha_page(html: str) -> bool:
        """检测页面是否为 fang.com 滑块验证码页面。"""
        if not html:
            return False
        if len(html) < 2000 and ("请完成下列验证" in html or "slider" in html):
            return True
        if "请完成下列验证后继续" in html:
            return True
        if "checkyzm" in html and len(html) < 5000:
            return True
        return False
