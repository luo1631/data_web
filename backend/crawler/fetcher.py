"""
HTTP 客户端封装 — m.fang.com 移动站专用。
"""

import asyncio
import random
import logging
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
from crawler.constants import (
    BASE_URL, SEED_URL, LIST_URL_TEMPLATE, DETAIL_URL_TEMPLATE,
    LIST_PAGE_DELAY, DETAIL_PAGE_DELAY, JITTER_RANGE, USER_AGENTS,
)

RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException, httpx.NetworkError,
    httpx.RemoteProtocolError, httpx.HTTPStatusError,
)

logger = logging.getLogger(__name__)


class Fetcher:
    """移动端异步 HTTP 客户端"""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._last_request: dict[str, float] = {}

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
        # 播种 Cookie（访问首页）
        try:
            resp = await self._client.get(SEED_URL, headers={
                "User-Agent": random.choice(USER_AGENTS),
            })
            if resp.status_code < 400:
                logger.debug(f"Seeded {len(dict(self._client.cookies))} cookies")
        except Exception:
            pass
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_list_page(self, slug: str, page: int) -> str:
        url = LIST_URL_TEMPLATE.format(slug=slug, page=page)
        await self._rate_limit("list")
        return await self._fetch(url)

    async def fetch_detail_page(self, house_id: str) -> str:
        url = DETAIL_URL_TEMPLATE.format(house_id=house_id)
        await self._rate_limit("detail")
        return await self._fetch(url)

    async def _rate_limit(self, group: str) -> None:
        now = asyncio.get_running_loop().time()
        last = self._last_request.get(group, 0)
        elapsed = now - last
        base = random.uniform(*LIST_PAGE_DELAY) if group == "list" else random.uniform(*DETAIL_PAGE_DELAY)
        target = base * random.uniform(*JITTER_RANGE)
        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request[group] = asyncio.get_running_loop().time()

    async def _fetch(self, url: str) -> str:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        return await self._retry_request(self._client, url, headers)

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=60),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
    async def _retry_request(client: httpx.AsyncClient, url: str, headers: dict) -> str:
        resp = await client.get(url, headers=headers)
        if resp.status_code in (429, 403):
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.text
