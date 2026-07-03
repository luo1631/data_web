"""
安居客移动站列表页解析器 — m.anjuke.com Vue SSR HTML。

每页 60 个 <li class="item-wrap"> 卡片，MLIST_MAIN class。
提取: house_id, title, price, unit_price, layout, area, orientation, decoration, community, address。
"""

import json
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 朝向关键词
_ORIENTATIONS = ["南北", "东南", "西南", "东北", "西北", "东西", "南", "北", "东", "西"]

# 装修关键词
_DECORATION_KEYWORDS = [
    "精装修", "豪华装修", "精装", "豪装", "中装", "中等装修", "简装", "简单装修", "毛坯",
]


class AnjukeListParser:
    """安居客移动站列表页解析器。"""

    @staticmethod
    def parse_listing_data(html: str) -> list[dict]:
        """从移动站 HTML 提取所有房源数据。

        自适应策略:
          1. 找出所有 <li class="item-wrap"> 标签
          2. 提取 <a class="cell-wrap MLIST_MAIN"> 中的链接
          3. 从卡片 HTML + body text 提取字段
        """
        soup = BeautifulSoup(html, "lxml")

        # 找出所有房源卡片
        cards = soup.select("li.item-wrap a.cell-wrap")
        if not cards:
            cards = soup.select("a.MLIST_MAIN")
        if not cards:
            cards = soup.select("li.item-wrap a[href*='/cq/sale/']")

        result = []
        for card in cards:
            data = AnjukeListParser._parse_one_card(card)
            if data and data.get("house_id"):
                result.append(data)

        if not result:
            logger.info(
                f"AnjukeListParser: 0 listings parsed "
                f"(html={len(html)}bytes, cards_found={len(cards)})"
            )

        return result

    @staticmethod
    def _parse_one_card(card) -> dict | None:
        """解析单个房源卡片。"""
        data: dict = {}

        # ── 1. house_id ──
        href = card.get("href", "")
        m = re.search(r'/cq/sale/([A-Z]\d+)/', href)
        if m:
            data["house_id"] = m.group(1)
        else:
            return None

        # ── 2. 价格 ──
        price_el = card.select_one(".content-price")
        if price_el:
            txt = price_el.get_text(strip=True)
            m = re.search(r'([\d.]+)', txt)
            if m:
                data["total_price"] = float(m.group(1))

        # ── 3. 单价 ──
        unit_el = card.select_one(".house-avg-price")
        if unit_el:
            txt = unit_el.get_text(strip=True)
            m = re.search(r'([\d,]+)', txt)
            if m:
                data["unit_price"] = float(m.group(1).replace(",", ""))

        # ── 4. 标题 (从 img alt) ──
        img = card.select_one("img")
        if img:
            alt = img.get("alt", "").strip()
            if alt:
                data["title"] = alt

        # ── 5. 从卡片文本提取户型/面积/朝向/装修 ──
        card_text = card.get_text(" ", strip=True)

        # 户型
        m = re.search(r'(\d+)室(\d+)厅(?:(\d+)卫)?', card_text)
        if m:
            data["room_count"] = int(m.group(1))
            data["hall_count"] = int(m.group(2))
            data["bathroom_count"] = int(m.group(3)) if m.group(3) else None

        # 面积
        m = re.search(r'([\d.]+)\s*[㎡m²]', card_text)
        if m:
            data["area"] = float(m.group(1))

        # 朝向
        for o in _ORIENTATIONS:
            if o in card_text:
                data["orientation"] = o
                break

        # 装修
        for dec in _DECORATION_KEYWORDS:
            if dec in card_text:
                data["decoration"] = dec
                break

        # ── 6. 标签 ──
        tags = card.select(".highlight-tag")
        if tags:
            data["tags"] = [t.get_text(strip=True) for t in tags]

        # ── 7. 从 data-ep 属性提取 vpid ──
        ep_attr = card.get("data-ep", "")
        if ep_attr:
            try:
                ep = json.loads(ep_attr)
                vpid = ep.get("exposure", {}).get("vpid", "")
                if vpid:
                    data["anjuke_vpid"] = vpid
            except (json.JSONDecodeError, KeyError):
                pass

        return data

    @staticmethod
    def parse_total_count(html: str) -> int:
        """尝试提取房源总数。"""
        m = re.search(r'(?:共|找到)\s*(\d[\d,]*)\s*套', html)
        if m:
            return int(m.group(1).replace(",", ""))
        # 尝试从 JSON 数据中提取
        m = re.search(r'"totalCount"\s*:\s*(\d+)', html)
        if m:
            return int(m.group(1))
        return 0

    @staticmethod
    def parse_max_page(html: str) -> int:
        """尝试提取最大页码。"""
        # 方式 A: 页面文本
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        # 方式 B: 从翻页链接收集
        pages = set()
        for n in re.findall(r'[?&]page=(\d+)', html):
            pages.add(int(n))
        return max(pages) if pages else 0


def _extract_community_from_text(text: str) -> str | None:
    """从卡片的描述文本中提取小区名。"""
    # 安居客 body 文本格式: "小区名 3室2厅 120㎡ 南 精装修 区域"
    # 小区名在第一段
    parts = text.split()
    if parts:
        first = parts[0]
        if len(first) >= 3 and not re.match(r'^\d+室', first):
            return first
    return None
