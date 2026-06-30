"""
列表页 HTML 解析器：从 fang.com 区县列表页提取房源 ID 列表。

所有方法均为纯静态方法，无状态，输入 HTML 输出结构化数据。
"""

import re
from bs4 import BeautifulSoup


class ListParser:
    """fang.com 区县列表页解析器。

    房天下列表页 URL 示例:
        /housing/house/list/yubei__0_0_0_0_1_0_0_0/

    注意：房天下 DOM 结构可能随时调整，CSS 选择器需定期验证。
    """

    # ── CSS 选择器（可能需要根据实际页面结构调整）──

    # 列表容器（每一条房源信息）
    LIST_ITEM_SELECTOR = "div.houseList dl, div.list dl, .houseList dl"

    # 房源链接（从链接 href 提取 ID）
    LISTING_LINK_SELECTOR = "a[href*='chushou']"

    # 房源总数文本
    TOTAL_COUNT_SELECTOR = "span.fy_text span, .total span"

    # ── public API ───────────────────────────────────

    @staticmethod
    def parse_listing_ids(html: str) -> list[str]:
        """从列表页 HTML 提取所有房源 external_id。

        Args:
            html: 列表页 HTML 字符串

        Returns:
            房源 ID 列表（空列表表示该页无房源）
        """
        soup = BeautifulSoup(html, "lxml")
        ids: list[str] = []

        # 方式1: 从房源链接提取 ID
        links = soup.select(ListParser.LISTING_LINK_SELECTOR)
        for link in links:
            href = link.get("href", "")
            listing_id = ListParser._extract_id_from_url(href)
            if listing_id:
                ids.append(listing_id)

        # 方式2: 从 data-id 属性提取（备选）
        if not ids:
            items = soup.select(ListParser.LIST_ITEM_SELECTOR)
            for item in items:
                data_id = item.get("data-id", "") or item.get("data-houseid", "")
                if data_id and data_id not in ids:
                    ids.append(str(data_id))

        # 方式3: 正则从全文提取 chushou/数字.htm 链接
        if not ids:
            pattern = re.compile(r'/chushou/(\d+)\.htm')
            ids = pattern.findall(html)

        return list(dict.fromkeys(ids))  # 去重保序

    @staticmethod
    def parse_total_count(html: str) -> int:
        """解析区县总房源数。

        fang.com 页面通常显示 "共找到 XXXX 套房源"

        Args:
            html: 列表页 HTML 字符串

        Returns:
            总房源数，解析失败返回 0
        """
        soup = BeautifulSoup(html, "lxml")
        elems = soup.select(ListParser.TOTAL_COUNT_SELECTOR)
        for elem in elems:
            text = elem.get_text(strip=True)
            match = re.search(r'(\d[\d,]*)', text)
            if match:
                return int(match.group(1).replace(",", ""))

        # 备选：全页搜索
        match = re.search(r'共[^\d]*(\d[\d,]*)[^\d]*套', html)
        if match:
            return int(match.group(1).replace(",", ""))

        return 0

    @staticmethod
    def calculate_total_pages(total_count: int, per_page: int = 30) -> int:
        """根据总房源数估算最大页数。

        房天下每页约 30 条，但最多返回 100 页。
        """
        pages = (total_count + per_page - 1) // per_page
        return min(pages, 100)

    @staticmethod
    def has_listings(html: str) -> bool:
        """检测页面是否包含房源列表。

        用于判断是否到达末页（或该区县无数据）。
        """
        soup = BeautifulSoup(html, "lxml")
        # 有房源链接即说明有数据
        if soup.select(ListParser.LISTING_LINK_SELECTOR):
            return True
        # 检查是否有 "暂无数据" 等提示
        body = soup.get_text()
        if any(kw in body for kw in ["暂无房源", "没有找到", "抱歉"]):
            return False
        # 没有链接但也没有 "暂无数据" → 可能是空页
        return bool(soup.select(ListParser.LIST_ITEM_SELECTOR))

    # ── internal ─────────────────────────────────────

    @staticmethod
    def _extract_id_from_url(url: str) -> str | None:
        """从房源链接中提取 ID。

        预期格式: /chushou/1234567890.htm 或类似变体
        """
        match = re.search(r'/chushou/(\d+)', url)
        if match:
            return match.group(1)
        # 备选：匹配其他可能的 ID 模式（12位以上数字）
        match = re.search(r'/(\d{10,})\.htm', url)
        if match:
            return match.group(1)
        return None
