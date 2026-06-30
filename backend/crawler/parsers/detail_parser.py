"""
详情页 HTML 解析器：从 fang.com 房源详情页提取结构化字段。

所有字段提取方法独立且容错——单个字段解析失败不影响其他字段。
"""

from dataclasses import dataclass, field
import re
from bs4 import BeautifulSoup, Tag


@dataclass
class ParsedListing:
    """爬虫中间数据结构——从详情页提取的原始字段（清洗前）。

    价格字段保存的是加密原文（字体解密前的乱码文本），
    需经 FontDecryptor 解密后由 cleaner 模块清洗。
    """

    external_id: str
    source_url: str

    # 价格（加密原文）
    total_price_raw: str | None = None
    unit_price_raw: str | None = None

    # 基本信息
    title: str | None = None
    area: str | None = None         # 如 "89.5㎡"

    # 户型
    room_count: int | None = None
    hall_count: int | None = None
    bathroom_count: int | None = None

    # 楼层
    floor_level: str | None = None          # 低/中/高楼层
    total_floors: int | None = None         # 总楼层

    # 房屋属性
    orientation: str | None = None
    decoration: str | None = None
    building_type: str | None = None
    building_structure: str | None = None
    has_elevator: bool | None = None

    # 小区信息
    community_name: str | None = None
    community_address: str | None = None

    # 挂牌
    listing_date: str | None = None  # 原始日期字符串

    # 字体反爬
    font_url: str | None = None


class DetailParser:
    """fang.com 房源详情页解析器。

    用法:
        parser = DetailParser(external_id="1234567890", source_url="https://...")
        parsed = parser.parse(html)
    """

    def __init__(self, external_id: str, source_url: str):
        self.external_id = external_id
        self.source_url = source_url
        self._soup: BeautifulSoup | None = None

    # ── main entry ───────────────────────────────────

    def parse(self, html: str) -> ParsedListing:
        """解析详情页 HTML，返回 ParsedListing。

        Args:
            html: 详情页原始 HTML

        Returns:
            ParsedListing — 各字段可能为 None，不抛异常
        """
        self._soup = BeautifulSoup(html, "lxml")

        listing = ParsedListing(
            external_id=self.external_id,
            source_url=self.source_url,
        )

        # 逐个字段提取，各自容错
        listing.title = self._extract_title()
        listing.font_url = self._extract_font_url()
        listing.total_price_raw, listing.unit_price_raw = self._extract_prices()
        listing.area = self._extract_area()
        listing.room_count, listing.hall_count, listing.bathroom_count = self._extract_room_layout()
        listing.floor_level, listing.total_floors = self._extract_floor_info()
        listing.orientation = self._extract_orientation()
        listing.decoration = self._extract_decoration()
        listing.building_type = self._extract_building_type()
        listing.building_structure = self._extract_building_structure()
        listing.has_elevator = self._extract_elevator()
        listing.community_name = self._extract_community_name()
        listing.community_address = self._extract_community_address()
        listing.listing_date = self._extract_listing_date()

        return listing

    # ── field extractors ─────────────────────────────

    def _extract_title(self) -> str | None:
        try:
            tag = self._soup.select_one("title, h1, .title h1, .house-title")
            if tag:
                return tag.get_text(strip=True)
        except Exception:
            pass
        return None

    def _extract_font_url(self) -> str | None:
        """从 CSS 或 <style> 中提取 @font-face 的字体文件 URL。

        fang.com 字体 URL 格式: //img.fang.com/font/house*.woff
        """
        try:
            # 查找所有 style 标签
            for style_tag in self._soup.find_all("style"):
                css_text = style_tag.string or ""
                match = re.search(
                    r"url\(['\"]?(//[^'\")]*?\.woff[^'\")]*)['\"]?\)",
                    css_text, re.IGNORECASE
                )
                if match:
                    return match.group(1)

            # 查找 link[rel=stylesheet] 中的字体引用（备选）
            for link_tag in self._soup.find_all("link", rel="stylesheet"):
                href = link_tag.get("href", "")
                if "font" in href.lower() and ".woff" in href.lower():
                    return href

        except Exception:
            pass
        return None

    def _extract_prices(self) -> tuple[str | None, str | None]:
        """提取总价和单价（加密原文）。"""
        total_raw = None
        unit_raw = None
        try:
            # 总价：页面中 class 含 price 或 total 的元素
            for cls in [".price", ".total-price", ".totalPrice", ".jiage", ".price-total"]:
                tag = self._soup.select_one(cls)
                if tag:
                    text = tag.get_text(strip=True)
                    if text and text != "0":
                        total_raw = text
                        break

            # 单价：页面中 class 含 unit 或 danjia 的元素
            for cls in [".unit-price", ".unitPrice", ".danjia", ".price-unit", ".dj"]:
                tag = self._soup.select_one(cls)
                if tag:
                    text = tag.get_text(strip=True)
                    if text and text != "0":
                        unit_raw = text
                        break

            # 备选：从表格/列表项提取
            if not total_raw or not unit_raw:
                total_raw, unit_raw = self._extract_prices_from_table()

        except Exception:
            pass
        return total_raw, unit_raw

    def _extract_prices_from_table(self) -> tuple[str | None, str | None]:
        """从详情页信息表格中提取价格（备选方案）。"""
        total_raw = None
        unit_raw = None
        try:
            items = self._soup.select(
                ".houseInfo dl, .info-table tr, .info-item, .base-info li, .trl-item"
            )
            for item in items:
                text = item.get_text(strip=True)
                if not text:
                    continue
                if "总价" in text or "售价" in text:
                    match = re.search(r'([一-鿿\d.]+万?)', text)
                    if match:
                        total_raw = match.group(1)
                if "单价" in text:
                    match = re.search(r'([一-鿿\d.]+元?/?\s*㎡?)', text)
                    if match:
                        unit_raw = match.group(1)
            return total_raw, unit_raw
        except Exception:
            return total_raw, unit_raw

    def _extract_area(self) -> str | None:
        try:
            tag = self._soup.select_one(
                ".area, .build-area, .buildArea, .mianji, "
                ".info-item:has(>:-soup-contains('面积')) span, "
                ".trl-item:has(>:-soup-contains('面积')) .rcont"
            )
            if tag:
                text = tag.get_text(strip=True)
                return text
        except Exception:
            pass
        return self._find_kv("面积")

    def _extract_room_layout(self) -> tuple[int | None, int | None, int | None]:
        """提取户型：室/厅/卫。格式如 '3室2厅1卫'。"""
        try:
            # 尝试找到户型文本
            for selector in [
                ".room, .huxing, .layout, .house-type, .hx",
                ".info-item:has(>:-soup-contains('户型')) span",
                ".trl-item:has(>:-soup-contains('户型')) .rcont",
            ]:
                tag = self._soup.select_one(selector)
                if tag:
                    text = tag.get_text(strip=True)
                    r, h, b = self._parse_layout_text(text)
                    if any(x is not None for x in (r, h, b)):
                        return r, h, b

            # 备选：从全文搜索
            text = self._soup.get_text()
            return self._parse_layout_text(text)

        except Exception:
            pass
        return None, None, None

    @staticmethod
    def _parse_layout_text(text: str) -> tuple[int | None, int | None, int | None]:
        match = re.search(r'(\d+)\s*室\s*(\d+)\s*厅\s*(\d+)\s*[卫]?', text)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
        # 备选：数字序列 "3/2/1"
        match = re.search(r'(\d+)/(\d+)/(\d+)', text)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
        return None, None, None

    def _extract_floor_info(self) -> tuple[str | None, int | None]:
        """提取楼层信息：格式如 '中楼层(共32层)' 或 '中层/共32层'。"""
        raw = None
        try:
            for selector in [
                ".floor, .floor-info, .ceng, .louceng",
                ".info-item:has(>:-soup-contains('楼层')) span",
                ".trl-item:has(>:-soup-contains('楼层')) .rcont",
            ]:
                tag = self._soup.select_one(selector)
                if tag:
                    raw = tag.get_text(strip=True)
                    break
            if not raw:
                raw = self._find_kv("楼层")
        except Exception:
            pass

        if not raw:
            return None, None

        floor_level = None
        total_floors = None

        if "低" in raw or "底" in raw:
            floor_level = "低楼层"
        elif "中" in raw:
            floor_level = "中楼层"
        elif "高" in raw or "顶" in raw:
            floor_level = "高楼层"

        match = re.search(r'共\s*(\d+)\s*层', raw)
        if match:
            total_floors = int(match.group(1))
        else:
            match = re.search(r'/(\d+)\s*层', raw)
            if match:
                total_floors = int(match.group(1))

        return floor_level, total_floors

    def _extract_orientation(self) -> str | None:
        return (
            self._find_kv_selector(
                [".orientation", ".chaoxiang", ".cx"],
                "朝向"
            )
        )

    def _extract_decoration(self) -> str | None:
        return (
            self._find_kv_selector(
                [".decoration", ".zhuangxiu", ".zx", ".fitment"],
                "装修"
            )
        )

    def _extract_building_type(self) -> str | None:
        return (
            self._find_kv_selector(
                [".building-type", ".jianzhu-type", ".jzlx"],
                "建筑类型"
            )
        )

    def _extract_building_structure(self) -> str | None:
        return (
            self._find_kv_selector(
                [".building-structure", ".jianzhu-structure", ".jzjg"],
                "建筑结构"
            )
        )

    def _extract_elevator(self) -> bool | None:
        raw = self._find_kv("电梯")
        if raw:
            if "有" in raw:
                return True
            if "无" in raw or "没有" in raw:
                return False
        return None

    def _extract_community_name(self) -> str | None:
        try:
            for selector in [
                ".community-name, .communityName, .xiaoqu-name, .xq-name",
                ".info-item:has(>:-soup-contains('小区')) span, .info-item:has(>:-soup-contains('小区')) a",
                ".trl-item:has(>:-soup-contains('小区')) .rcont a",
                "a[href*='community'], a[href*='xiaoqu']",
            ]:
                tag = self._soup.select_one(selector)
                if tag:
                    text = tag.get_text(strip=True)
                    if text and len(text) >= 2:
                        return text
        except Exception:
            pass
        return self._find_kv("小区")

    def _extract_community_address(self) -> str | None:
        return self._find_kv("地址")

    def _extract_listing_date(self) -> str | None:
        return (
            self._find_kv_selector(
                [".listing-date, .listingDate, .gp-date, .guapai-date"],
                "挂牌"
            )
        )

    # ── helpers ──────────────────────────────────────

    def _find_kv(self, keyword: str) -> str | None:
        """在信息列表中找到 key-value 对中的 value。"""
        try:
            items = self._soup.select(
                ".info-item, .trl-item, .base-info li, .houseInfo dl, "
                ".info-table tr, .detail-info li"
            )
            for item in items:
                text = item.get_text(strip=True)
                if keyword in text:
                    # 尝试提取 key 之后的 value
                    parts = re.split(r'[：:\s]+', text, maxsplit=1)
                    if len(parts) >= 2:
                        return parts[-1].strip()
                    # 如果是 dl 结构，取 dd
                    if item.name == "dl":
                        dd = item.find("dd")
                        if dd:
                            return dd.get_text(strip=True)
            return None
        except Exception:
            return None

    def _find_kv_selector(
        self, selectors: list[str], keyword: str
    ) -> str | None:
        """先用 CSS 选择器找，失败后用关键词查找。"""
        try:
            for sel in selectors:
                tag = self._soup.select_one(sel)
                if tag:
                    text = tag.get_text(strip=True)
                    if text:
                        return text
        except Exception:
            pass
        return self._find_kv(keyword)
