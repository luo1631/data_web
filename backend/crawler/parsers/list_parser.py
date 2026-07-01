"""
列表页解析器 — cq.esf.fang.com 桌面站。

每条房源 HTML 结构:
  <dl class="clearfix" data-bg='{"houseid":"204649634",...}'>
    <dt class="floatl">
      <a href="/chushou/3_204649634.htm">
        <img alt="标题" .../>
      </a>
    </dt>
    <dd>
      <h4 class="clearfix">
        <a href="/chushou/3_204649634.htm" title="完整标题">
          <span class="tit_shop">简短标题</span>
        </a>
      </h4>
      <p class="tel_shop">
        <a class="link_rk">建筑类型</a><i>|</i>
        卧室：N个 <i>|</i> 面积㎡ <i>|</i> 朝向 <i>|</i>
        <span class="people_name">...</span>
      </p>
      <p class="add_shop">
        <a href="/house-xm{N}/" title="小区名">小区名</a>
        <span>地址</span>
      </p>
      <p class="clearfix label">
        <span>标签1</span><span>标签2</span>...
      </p>
    </dd>
    <dd class="price_right">
      <span class="red"><b>总价</b>万</span>
      <span>单价元/㎡</span>
    </dd>
  </dl>
"""

import json
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 朝向关键词（按长度降序，避免短词误匹配）
_ORIENTATIONS = ["南北", "东南", "西南", "东北", "西北", "东西", "南", "北", "东", "西"]

# 楼层关键词 — tel_shop 中出现的楼层描述
_BUILDING_TYPE_KEYWORDS = [
    "板塔结合", "板楼", "塔楼", "独栋", "联排", "双拼", "叠拼", "平层",
]

# 装修关键词（按长→短，避免短词误配）
_DECORATION_KEYWORDS = [
    "精装修", "豪华装修", "精装", "豪装", "中装", "中等装修", "简装", "简单装修", "毛坯",
]


class ListParser:
    """桌面站列表页解析器"""

    @staticmethod
    def parse_listing_data(html: str) -> list[dict]:
        """从列表页 HTML 提取所有房源数据。

        Args:
            html: 列表页 HTML（已解码为 str）

        Returns:
            list[dict]: 每条房源包含 house_id, title, total_price,
                        unit_price, area, room_count, hall_count,
                        bathroom_count, orientation, decoration,
                        floor_level, building_type, community_name,
                        community_address 等字段
        """
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("dl[data-bg]")
        if not items:
            # 回退：按 class="clearfix" 找包含 /chushou/ 链接的 dl
            items = [
                dl for dl in soup.select("dl.clearfix")
                if dl.select_one("a[href*='/chushou/']")
            ]

        result = []
        for dl in items:
            data = ListParser._parse_one_dl(dl)
            if data and data.get("house_id"):
                result.append(data)

        return result

    @staticmethod
    def _parse_one_dl(dl) -> dict | None:
        """解析单个 <dl> 元素。"""
        data: dict = {}
        dl_text = dl.get_text(" ", strip=True)
        dl_html = str(dl)

        # ── 1. house_id ──
        # 方式 A: data-bg JSON 属性
        bg_attr = dl.get("data-bg", "")
        if bg_attr:
            try:
                # 替换 HTML 实体
                bg_clean = bg_attr.replace("&quot;", '"').replace("&#39;", "'")
                bg = json.loads(bg_clean)
                raw_id = bg.get("houseid", "")
                if raw_id:
                    listingtype = bg.get("housetype", "2")
                    prefix = listingtype.split(",")[0] if "," in listingtype else "3"
                    data["house_id"] = f"{prefix}_{raw_id}"
            except (json.JSONDecodeError, KeyError):
                pass

        # 方式 B: 从 /chushou/ 链接提取
        if not data.get("house_id"):
            link = dl.select_one("a[href*='/chushou/']")
            if link:
                m = re.search(r'/chushou/([^/?]+)\.htm', link.get("href", ""))
                if m:
                    data["house_id"] = m.group(1)

        if not data.get("house_id"):
            return None

        # ── 2. 标题 ──
        # 优先取 <a> 的 title 属性（完整标题）
        title_link = dl.select_one("h4 a[title]")
        if title_link:
            data["title"] = title_link.get("title", "").strip()
        if not data.get("title"):
            title_span = dl.select_one(".tit_shop")
            if title_span:
                data["title"] = title_span.get_text(strip=True)
        if not data.get("title"):
            img = dl.select_one("dt img")
            if img:
                data["title"] = img.get("alt", "").strip()

        # ── 3. 价格 ──
        # 总价: <span class="red"><b>1200</b>万</span>
        price_el = dl.select_one(".price_right .red b, .price_right .red strong")
        if price_el:
            txt = price_el.get_text(strip=True)
            m = re.search(r'([\d.]+)', txt)
            if m:
                data["total_price"] = float(m.group(1))
        if not data.get("total_price"):
            m = re.search(r'<b>(\d+)</b>\s*万', dl_html)
            if m:
                data["total_price"] = float(m.group(1))

        # 单价: <span>26327元/㎡</span>
        unit_el = dl.select_one(".price_right span:not(.red)")
        if unit_el:
            txt = unit_el.get_text(strip=True)
            m = re.search(r'([\d,]+)\s*元', txt)
            if m:
                data["unit_price"] = float(m.group(1).replace(",", ""))

        # ── 4. tel_shop 段落: 户型/面积/朝向/建筑类型 ──
        tel_el = dl.select_one(".tel_shop")
        if tel_el:
            tel_text = tel_el.get_text(" ", strip=True)

            # 4a. 户型 — 三种格式:
            #   "3室2厅2卫" / "3室2厅" / "卧室：5个"
            m = re.search(r'(\d+)室(\d+)厅(?:(\d+)卫)?', tel_text)
            if m:
                data["room_count"] = int(m.group(1))
                data["hall_count"] = int(m.group(2))
                data["bathroom_count"] = int(m.group(3)) if m.group(3) else None
            else:
                m = re.search(r'卧室[：:]\s*(\d+)', tel_text)
                if m:
                    data["room_count"] = int(m.group(1))
                    data["hall_count"] = None
                    data["bathroom_count"] = None

            # 4b. 面积: 455.79㎡
            m = re.search(r'([\d.]+)\s*[㎡²]', tel_text)
            if m:
                data["area"] = float(m.group(1))

            # 4c. 朝向 — 匹配 "南向"/"南北"/"东" 等
            #     tel_shop 用 | 分隔，朝向是其中一个独立字段
            for o in _ORIENTATIONS:
                if o + "向" in tel_text or f" {o} " in f" {tel_text} ":
                    data["orientation"] = o
                    break

            # 4d. 建筑类型 / 楼层 — .link_rk 可能包含二者
            #   "独栋"/"板楼"/"塔楼" 等 → building_type
            #   "低层"/"中层"/"高层"/"底层" → floor_level，附带 "共N层" → total_floors
            type_el = tel_el.select_one(".link_rk, a[href*='baike.fang.com']")
            if type_el:
                bt_text = type_el.get_text(strip=True)

                # 判断是否是建筑类型关键词
                if any(kw in bt_text for kw in _BUILDING_TYPE_KEYWORDS):
                    data["building_type"] = bt_text
                else:
                    # 是楼层描述，提取 floor_level + total_floors
                    mf = re.search(r'(低层|中层|高层|底层|顶层)', bt_text)
                    if mf:
                        data["floor_level"] = mf.group(1)
                    # 共N层
                    mt = re.search(r'共\s*(\d+)\s*层', bt_text)
                    if mt:
                        data["total_floors"] = int(mt.group(1))

            # 4e. 如果 type_el 没给 total_floors，从 tel_text 全文提取
            if not data.get("total_floors"):
                mt2 = re.search(r'共\s*(\d+)\s*层', tel_text)
                if mt2:
                    data["total_floors"] = int(mt2.group(1))

        # ── 5. add_shop 段落: 小区名 + 地址 ──
        add_el = dl.select_one(".add_shop")
        if add_el:
            add_text = add_el.get_text(" ", strip=True)

            # 5a. 小区名
            comm_link = add_el.select_one("a[href*='/house-xm']")
            if comm_link:
                data["community_name"] = (
                    comm_link.get("title", "").strip()
                    or comm_link.get_text(strip=True)
                )
            if not data.get("community_name"):
                m = re.search(r'<a[^>]*href="/house-xm\d+/"[^>]*title="([^"]+)"', dl_html)
                if m:
                    data["community_name"] = m.group(1).strip()

            # 5b. 地址
            addr_span = add_el.select_one("span")
            if addr_span:
                addr = addr_span.get_text(strip=True)
                if addr and len(addr) >= 4:
                    data["community_address"] = addr

        # ── 6. 装修/楼层 — 从全文中提取（兜底，tel_shop 未命中时） ──
        if not data.get("decoration"):
            for dec in _DECORATION_KEYWORDS:
                if dec in dl_text:
                    data["decoration"] = dec
                    break

        if not data.get("floor_level"):
            for fl in ["低楼层", "中楼层", "高楼层", "低层", "中层", "高层", "底层", "顶层"]:
                if fl in dl_text:
                    data["floor_level"] = fl
                    break

        # ── 7. total_floors 兜底 ──
        if not data.get("total_floors"):
            m = re.search(r'共\s*(\d+)\s*层', dl_text)
            if m:
                data["total_floors"] = int(m.group(1))

        return data

    @staticmethod
    def parse_total_count(html: str) -> int:
        """尝试从页面提取房源总数。"""
        m = re.search(r'(?:共|共计|找到|约)\s*(\d[\d,]*)\s*(?:套|条|房源)', html)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    @staticmethod
    def parse_max_page(html: str) -> int:
        """尝试提取最大页码。"""
        # 区县页格式: <span class="txt">共100页</span>
        m = re.search(r'共(\d+)页', html)
        if m:
            return int(m.group(1))
        # 旧格式——尾页链接: /house/i3100/
        m = re.search(r'/house(?:-a\d+)?-i3(\d+)/[^"]*尾页', html)
        if m:
            return int(m.group(1))
        # 最后一个分页数字
        pages = re.findall(r'/house(?:-a\d+)?-i3(\d+)/', html)
        if pages:
            return max(int(p) for p in pages)
        return 0
