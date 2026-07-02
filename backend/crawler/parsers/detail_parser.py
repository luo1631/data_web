"""
详情页解析器 — m.fang.com 移动站。

移动站 SSR 渲染，所有数据直接在 HTML 源码中，无需字体解密。
"""

import re
from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass
class ParsedListing:
    """爬虫中间数据结构"""
    external_id: str
    source_url: str

    title: str | None = None
    total_price: float | None = None       # 万元 (已解密)
    unit_price: float | None = None        # 元/㎡ (已解密)
    area: float | None = None              # ㎡
    room_count: int | None = None
    hall_count: int | None = None
    bathroom_count: int | None = None
    floor_level: str | None = None
    total_floors: int | None = None
    orientation: str | None = None
    decoration: str | None = None
    building_type: str | None = None
    building_structure: str | None = None
    has_elevator: bool | None = None
    community_name: str | None = None
    community_address: str | None = None
    listing_date: str | None = None
    community_lng: float | None = None     # 百度地图坐标
    community_lat: float | None = None


class DetailParser:
    """移动站详情页解析器"""

    def __init__(self, external_id: str, source_url: str):
        self.external_id = external_id
        self.source_url = source_url

    def parse(self, html: str) -> ParsedListing:
        soup = BeautifulSoup(html, "lxml")
        listing = ParsedListing(external_id=self.external_id, source_url=self.source_url)

        listing.title = self._extract_title(soup)
        listing.total_price, listing.unit_price = self._extract_prices(soup)
        listing.area = self._extract_area(soup)
        listing.room_count, listing.hall_count, listing.bathroom_count = self._extract_layout(soup)
        listing.floor_level, listing.total_floors = self._extract_floor(soup)
        listing.orientation = self._extract_orientation(soup)
        listing.decoration = self._extract_decoration(soup)
        listing.building_type = self._extract_building_type(soup)
        listing.community_name = self._extract_community(soup)
        listing.community_address = self._extract_address(soup)
        listing.listing_date = self._extract_listing_date(soup)
        listing.community_lng, listing.community_lat = self._extract_coords(html)

        return listing

    # ── extractors ──

    def _extract_title(self, soup):
        el = soup.select_one("h1, .title, .fy-name")
        return el.get_text(strip=True) if el else None

    def _extract_prices(self, soup):
        total = None
        unit = None
        # 总价: <div class="price"><em>1200</em>万</div> 或 <li>1200万<span>总价</span></li>
        full_text = soup.get_text(" ", strip=True)
        m = re.search(r'总价[:\s]*([\d.]+)\s*万', full_text)
        if m:
            total = float(m.group(1))
        else:
            m = re.search(r'([\d.]+)\s*万[^元]*总价', full_text)
            if m:
                total = float(m.group(1))
        if not total:
            # 从第一个价格元素取
            el = soup.select_one(".price em, .sale-price em, .total-price em, .total-price strong")
            if el:
                txt = el.get_text(strip=True)
                m = re.search(r'([\d.]+)', txt)
                if m:
                    total = float(m.group(1))

        # 单价: "26328元/平米" → 26328
        m = re.search(r'单价[:\s]*([\d,]+)\s*元', full_text)
        if m:
            unit = float(m.group(1).replace(",", ""))
        else:
            m = re.search(r'([\d,]+)\s*元/[平㎡米m]', full_text)
            if m:
                unit = float(m.group(1).replace(",", ""))

        return total, unit

    def _extract_area(self, soup):
        full = soup.get_text(" ", strip=True)
        m = re.search(r'(?:面积|建面|建筑面积)[:\s]*([\d.]+)\s*m?[²㎡]', full)
        if m:
            return float(m.group(1))
        m = re.search(r'([\d.]+)\s*m?[²㎡].*(?:面积|建面)', full)
        return float(m.group(1)) if m else None

    def _extract_layout(self, soup):
        full = soup.get_text(" ", strip=True)
        m = re.search(r'(\d+)室(\d+)厅(\d+)卫', full)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.search(r'(\d+)室(\d+)厅', full)
        return (int(m.group(1)), int(m.group(2)), None) if m else (None, None, None)

    def _extract_floor(self, soup):
        full = soup.get_text(" ", strip=True)
        floor_level = None
        total_floors = None
        if "低楼层" in full or "底层" in full:
            floor_level = "低楼层"
        elif "中楼层" in full or "中层" in full:
            floor_level = "中楼层"
        elif "高楼层" in full or "高层" in full or "顶层" in full:
            floor_level = "高楼层"

        # 楼层: 3层 或 共32层
        m = re.search(r'共\s*(\d+)\s*层', full)
        if m:
            total_floors = int(m.group(1))
        else:
            m = re.search(r'^(?:低|中|高)?楼层[^层]*(\d+)\s*层', full)
            if not m:
                m = re.search(r'楼层[:\s]*(\d+)', full)
            if m:
                total_floors = int(m.group(1))

        return floor_level, total_floors

    def _extract_orientation(self, soup):
        full = soup.get_text(" ", strip=True)
        for o in ["南", "北", "南北", "东南", "西南", "东北", "西北", "东", "西"]:
            if f"朝向{o}" in full or f"朝{o}" in full:
                return o
        m = re.search(r'朝向[:\s]*(\S{1,3})', full)
        return m.group(1) if m else None

    def _extract_decoration(self, soup):
        full = soup.get_text(" ", strip=True)
        for kw in ["精装修", "精装", "豪装", "豪华装修", "简装", "简单装修", "毛坯", "中装"]:
            if kw in full:
                return kw
        m = re.search(r'装修[:\s]*(\S{2,6})', full)
        return m.group(1) if m else None

    def _extract_building_type(self, soup):
        full = soup.get_text(" ", strip=True)
        for kw in ["独栋", "板楼", "塔楼", "板塔结合", "联排", "双拼", "叠拼"]:
            if kw in full:
                return kw
        return None

    def _extract_community(self, soup):
        el = soup.select_one(".community-name, .xiaoqu-name, .plot-name, a[href*='xiaoqu']")
        if el:
            return el.get_text(strip=True)
        full = soup.get_text(" ", strip=True)
        m = re.search(r'小区[:\s]*(\S{2,30})', full)
        return m.group(1) if m else None

    def _extract_address(self, soup):
        el = soup.select_one(".address, .plot-address, .map-address, .lp-map-btxt, .showMapList")
        if el:
            return el.get_text(strip=True)
        # 纯文本兜底：含区县名的长文本
        full = soup.get_text(" ", strip=True)
        m = re.search(r'(?:重庆)?(?:两江新区|渝中|南岸|沙坪坝|九龙坡|巴南|大渡口|北碚|璧山|江津|永川|合川|长寿|涪陵|南川|綦江|大足|铜梁|潼南|荣昌|万州|开州|梁平|武隆|城口|丰都|垫江|忠县|云阳|奉节|巫山|巫溪|黔江|石柱|秀山|酉阳|彭水)\S{0,50}', full)
        return m.group(0) if m else None

    def _extract_listing_date(self, soup):
        full = soup.get_text(" ", strip=True)
        for kw in ["发布", "挂牌", "上架"]:
            pat = kw + r'[:\s]*(\d{4}-\d{2}-\d{2})'
            m = re.search(pat, full)
            if m:
                return m.group(1)
        return None

    def _extract_coords(self, html):
        """从 HTML 中提取百度地图坐标。"""
        m = re.search(r'markers=([\d.]+),([\d.]+)', html)
        if m:
            return float(m.group(1)), float(m.group(2))
        return None, None
