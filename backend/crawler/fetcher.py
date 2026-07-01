"""
HTTP 客户端 — cq.esf.fang.com 全局列表页。

注：httpx 仅用于首页；翻页需 Playwright 绕过滑块验证。
    此模块保留给不需要翻页的快速首页抓取场景。
"""

import asyncio
import random
import re
import logging
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
from crawler.constants import (
    SEED_URL, LIST_PAGE_TEMPLATE, DETAIL_URL_TEMPLATE, USER_AGENTS,
)

RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException, httpx.NetworkError,
    httpx.RemoteProtocolError, httpx.HTTPStatusError,
)

logger = logging.getLogger(__name__)


class Fetcher:
    """httpx 客户端 — 仅首页抓取"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "Fetcher":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        await self._seed()
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_page(self, page: int) -> tuple[str, str]:
        """抓取全局列表页。page=1 → 首页，page>=2 → /house/i3{N}/"""
        url = SEED_URL if page <= 1 else LIST_PAGE_TEMPLATE.format(page=str(page))
        html = await self._fetch(url)
        return html, url

    async def _seed(self) -> None:
        try:
            resp = await self._client.get(SEED_URL, headers={
                "User-Agent": random.choice(USER_AGENTS),
            })
            if resp.status_code < 400:
                logger.debug(f"Seeded {len(dict(self._client.cookies))} cookies")
        except Exception:
            pass

    async def _fetch(self, url: str) -> str:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": SEED_URL,
        }
        return await self._retry_request(self._client, url, headers)

    @staticmethod
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=5, min=5, max=60),
           retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
           reraise=True)
    async def _retry_request(client: httpx.AsyncClient, url: str, headers: dict) -> str:
        resp = await client.get(url, headers=headers)
        if resp.status_code in (429, 403):
            resp.raise_for_status()
        resp.raise_for_status()
        content = resp.content
        if re.search(rb'charset\s*=\s*[\"\']?(?:gbk|gb2312)', content[:2000], re.I):
            return content.decode('gb18030', errors='replace')
        return resp.text
