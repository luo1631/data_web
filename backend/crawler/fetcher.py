"""
HTTP 客户端封装：UA 轮换、Referer 链、tenacity 重试、速率限制。

用法:
    async with Fetcher() as fetcher:
        html = await fetcher.fetch_list_page("yubei", 1)
"""

import asyncio
import random
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from crawler.constants import (
    BASE_URL,
    LIST_URL_TEMPLATE,
    DETAIL_URL_TEMPLATE,
    LIST_PAGE_DELAY,
    DETAIL_PAGE_DELAY,
    JITTER_RANGE,
    USER_AGENTS,
)

# tenacity 判断可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    httpx.HTTPStatusError,
)


class Fetcher:
    """异步 HTTP 客户端，封装反爬策略。

    作为 async context manager 使用，自动管理连接池生命周期。
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._ua_idx = 0
        # 记录各 semaphore group 的上次请求时间，用于限速
        self._last_request: dict[str, float] = {}

    # ── context manager ──────────────────────────────

    async def __aenter__(self) -> "Fetcher":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        # 先访问首页播种 Cookie（模拟真实用户行为）
        try:
            resp = await self._client.get(BASE_URL + "/", headers={
                "User-Agent": random.choice(USER_AGENTS),
            })
            if resp.status_code < 400:
                cookies = dict(self._client.cookies)
                if cookies:
                    import logging
                    logging.getLogger(__name__).debug(f"Seeded {len(cookies)} cookies")
        except Exception:
            pass  # 播种失败不阻塞爬取
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── public API ───────────────────────────────────

    async def fetch_list_page(self, slug: str, page: int) -> str:
        """获取区县列表页 HTML。

        Args:
            slug: 区县拼音标识（如 yubei）
            page: 页码（1-based）

        Returns:
            原始 HTML 字符串
        """
        url = LIST_URL_TEMPLATE.format(slug=slug, page=page)
        await self._rate_limit("list")
        return await self._fetch(url, referer_step="list")

    async def fetch_detail_page(self, listing_id: str) -> str:
        """获取房源详情页 HTML。

        Args:
            listing_id: 房天下房源 ID

        Returns:
            原始 HTML 字符串
        """
        url = DETAIL_URL_TEMPLATE.format(listing_id=listing_id)
        await self._rate_limit("detail")
        return await self._fetch(url, referer_step="detail")

    async def download_font_file(self, font_url: str) -> bytes:
        """下载字体文件（.woff），无需限速。

        Args:
            font_url: 字体文件 URL（可能是 // 开头）

        Returns:
            字体文件二进制内容
        """
        if font_url.startswith("//"):
            font_url = "https:" + font_url
        elif not font_url.startswith("http"):
            font_url = urljoin(BASE_URL, font_url)

        resp = await self._client.get(font_url)
        resp.raise_for_status()
        return resp.content

    # ── internal ─────────────────────────────────────

    def _rotate_ua(self) -> str:
        """随机选择 User-Agent（非确定性轮换，防指纹）。"""
        return random.choice(USER_AGENTS)

    def _build_headers(self, referer_step: str) -> dict[str, str]:
        """构建请求头，含 UA 和 Referer 链。

        Referer 链: 首页 → 区县列表页（fetch_list_page）/ 列表页（fetch_detail_page）
        """
        headers = {"User-Agent": self._rotate_ua()}

        if referer_step == "list":
            headers["Referer"] = BASE_URL + "/"
        elif referer_step == "detail":
            headers["Referer"] = BASE_URL + "/housing/house/list/"
        # 字体文件不需要 Referer

        return headers

    async def _rate_limit(self, group: str) -> None:
        """限速：确保同 group 的相邻请求间隔 >= 随机延迟。

        实际延迟 = base_delay * jitter，其中 base_delay 在范围内随机，
        jitter 在 JITTER_RANGE 内随机。
        """
        now = asyncio.get_running_loop().time()
        last = self._last_request.get(group, 0)
        elapsed = now - last

        if group == "list":
            base_delay = random.uniform(*LIST_PAGE_DELAY)
        else:
            base_delay = random.uniform(*DETAIL_PAGE_DELAY)

        jitter = random.uniform(*JITTER_RANGE)
        target_delay = base_delay * jitter

        if elapsed < target_delay:
            await asyncio.sleep(target_delay - elapsed)

        self._last_request[group] = asyncio.get_event_loop().time()

    async def _fetch(self, url: str, referer_step: str) -> str:
        """带重试的 HTTP GET 请求。"""
        headers = self._build_headers(referer_step)
        return await self._retry_request(self._client, url, headers)

    # ── retry wrapper ────────────────────────────────

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=60),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
    async def _retry_request(
        client: httpx.AsyncClient, url: str, headers: dict[str, str]
    ) -> str:
        """执行单次请求，tenacity 在外层处理重试逻辑。"""
        resp = await client.get(url, headers=headers)

        if resp.status_code == 429:
            resp.raise_for_status()  # raises httpx.HTTPStatusError → retried

        resp.raise_for_status()
        return resp.text
