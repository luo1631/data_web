"""
列表页解析器 — m.fang.com 移动站。

每条房源格式:
  <li class="listhouse" data-bg='{"houseid":"204649634", ...}'>
    <a href="/esf/cq/3_204649634.html">
      <div class="txt">
        <h3>标题</h3>
        <div class="price"><em>1200</em>万</div>
      </div>
"""

import json
import re
from bs4 import BeautifulSoup


class ListParser:
    """移动站列表页解析器"""

    @staticmethod
    def parse_listing_data(html: str) -> list[dict]:
        """从列表页提取所有房源的基本信息（JSON + HTML）。

        Returns:
            [{house_id, title, total_price, room_layout, area,
              orientation, community_name, floor_info, decoration, listing_date}]
        """
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("li.listhouse")
        result = []

        for li in items:
            data = {}
            # 从链接 href 提取完整 house_id（如 3_204649634）
            link = li.select_one("a[href*='/esf/cq/']")
            if link:
                href = link.get("href", "")
                m = re.search(r'/esf/cq/([^/?]+)\.html', href)
                if m:
                    data["house_id"] = m.group(1)

            # 回退: data-bg JSON
            if not data.get("house_id"):
                bg_attr = li.get("data-bg", "")
                if bg_attr:
                    try:
                        bg = json.loads(bg_attr.replace("'", '"'))
                        raw_id = bg.get("houseid", "")
                        if raw_id:
                            # 推断前缀（通常格式: type_number）
                            listingtype = bg.get("listingtype", "2")
                            prefix = listingtype.split(",")[0] if "," in listingtype else "3"
                            data["house_id"] = f"{prefix}_{raw_id}"
                    except json.JSONDecodeError:
                        pass

            if not data.get("house_id"):
                continue

            # 3. 提取文本字段
            title_el = li.select_one("h3, .tit, .title")
            if title_el:
                data["title"] = title_el.get_text(strip=True)

            price_el = li.select_one(".price em, .price strong, .price, .totalprice")
            if price_el:
                txt = price_el.get_text(strip=True)
                m = re.search(r'([\d.]+)\s*万', txt)
                if m:
                    data["total_price"] = float(m.group(1))

            # 户型/面积/朝向等 — 从 li 的全部文本中提取
            full_text = li.get_text(" ", strip=True)
            # 户型
            m = re.search(r'(\d+)室(\d+)厅(\d+)卫', full_text)
            if m:
                data["room_count"] = int(m.group(1))
                data["hall_count"] = int(m.group(2))
                data["bathroom_count"] = int(m.group(3))
            else:
                m2 = re.search(r'(\d+)室(\d+)厅', full_text)
                if m2:
                    data["room_count"] = int(m2.group(1))
                    data["hall_count"] = int(m2.group(2))

            # 面积
            m = re.search(r'([\d.]+)\s*m?㎡|([\d.]+)\s*[平米/]', full_text)
            area_m = re.search(r'([\d.]+)\s*m?[²㎡]', full_text)
            if not area_m:
                area_m = re.search(r'([\d.]+)\s*平米', full_text)
            if area_m:
                data["area"] = float(area_m.group(1))

            # 朝向
            for o in ["南", "北", "东南", "西南", "东北", "西北", "东", "西", "南北"]:
                if o in full_text:
                    data["orientation"] = o
                    break

            # 楼层
            for kw in ["低楼层", "中楼层", "高楼层", "底层", "中层", "高层"]:
                if kw in full_text:
                    data["floor_level"] = kw
                    break

            # 装修
            for kw in ["精装", "豪装", "简装", "毛坯", "中装"]:
                if kw in full_text:
                    data["decoration"] = kw
                    break

            # 小区名
            comm_el = li.select_one(".community, .xiaoqu, .plot, a[href*='xiaoqu']")
            if comm_el:
                data["community_name"] = comm_el.get_text(strip=True)

            result.append(data)

        return result

    @staticmethod
    def parse_total_count(html: str) -> int:
        """从列表页提取总房源数（隐藏 input total 或文本）。"""
        # <input type="hidden" id="total" value="523534"/>
        m = re.search(r'(?:total|totalCount)[\"\']?\s*value=[\"\']?(\d+)', html, re.I)
        if m:
            return int(m.group(1))
        # 文本 "共 523534 套"
        m = re.search(r'(\d[\d,]*)\s*(?:套|条|房源)', html)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0
