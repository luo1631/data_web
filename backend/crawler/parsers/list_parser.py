"""
列表页解析器 — cq.esf.fang.com 桌面站，自适应多格式。

fang.com 在不同区县/房源类型使用不同的 HTML 属性名和 URL 模式：
  - data-bg  + /chushou/（普通二手房）
  - data-bgfp + /fapai/（法拍房）
  - 未来可能有其他 data-* 属性和 URL 格式

本解析器不硬编码属性名，自动检测所有 data-* 属性和房源链接。
"""

import json
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 朝向关键词（按长度降序，避免短词误匹配）
_ORIENTATIONS = ["南北", "东南", "西南", "东北", "西北", "东西", "南", "北", "东", "西"]

# 建筑类型关键词
_BUILDING_TYPE_KEYWORDS = [
    "板塔结合", "板楼", "塔楼", "独栋", "联排", "双拼", "叠拼", "平层",
]

# 装修关键词（按长→短）
_DECORATION_KEYWORDS = [
    "精装修", "豪华装修", "精装", "豪装", "中装", "中等装修", "简装", "简单装修", "毛坯",
]

# 房源链接 URL 模式（自适应扩展）
_LISTING_LINK_PATTERNS = [
    r'/chushou/([^/?]+)\.htm',    # 普通二手房: /chushou/3_123456.htm
    r'/fapai/out_(\d+)\.html',    # 法拍房: /fapai/out_123456.html
]


def _is_listing_link(href: str) -> bool:
    """判断 href 是否为房源详情链接。"""
    if not href:
        return False
    return any(re.search(pat, href) for pat in _LISTING_LINK_PATTERNS)


class ListParser:
    """桌面站列表页自适应解析器"""

    @staticmethod
    def parse_listing_data(html: str) -> list[dict]:
        """从列表页 HTML 提取所有房源数据。

        自适应策略:
          1. 找出所有 <dl> 标签
          2. 筛选包含房源链接的 dl
          3. 对每个 dl 自适应提取字段

        Args:
            html: 列表页 HTML（已解码为 str）
        """
        soup = BeautifulSoup(html, "lxml")

        # 选出所有包含房源链接的 <dl>
        all_dls = soup.select("dl")
        listing_dls = [
            dl for dl in all_dls
            if any(_is_listing_link(a.get("href", "")) for a in dl.select("a"))
        ]

        result = []
        skipped = 0
        for dl in listing_dls:
            data = ListParser._parse_one_dl(dl)
            if data and data.get("house_id"):
                result.append(data)
            else:
                skipped += 1

        if skipped > 0 or len(listing_dls) != len(result):
            logger.info(
                f"parse_listing_data: {len(listing_dls)} DLs found, "
                f"parsed={len(result)}, skipped={skipped}"
            )

        return result

    @staticmethod
    def _parse_one_dl(dl) -> dict | None:
        """解析单个 <dl> 元素 — 自适应字段提取。"""
        data: dict = {}
        dl_text = dl.get_text(" ", strip=True)
        dl_html = str(dl)

        # ── 1. house_id（自适应）──
        # 先试 data-bg / data-bgfp（最常用）
        for attr in ["data-bg", "data-bgfp"]:
            val = dl.get(attr, "")
            if val:
                hid = _extract_houseid_from_json(val)
                if hid:
                    data["house_id"] = hid
                    break
        # 再试其他 data-* 属性（未来新格式）
        if not data.get("house_id"):
            for attr_name in dl.attrs:
                if attr_name.startswith("data-") and attr_name not in ("data-bg", "data-bgfp"):
                    hid = _extract_houseid_from_json(dl.get(attr_name, ""))
                    if hid:
                        data["house_id"] = hid
                        break

        # 方式 B: 从房源链接 URL 提取
        if not data.get("house_id"):
            for a in dl.select("a"):
                href = a.get("href", "")
                hid = _extract_houseid_from_url(href)
                if hid:
                    data["house_id"] = hid
                    break

        if not data.get("house_id"):
            return None

        # ── 2. 标题 ──
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

        unit_el = dl.select_one(".price_right span:not(.red)")
        if unit_el:
            txt = unit_el.get_text(strip=True)
            m = re.search(r'([\d,]+)\s*元', txt)
            if m:
                data["unit_price"] = float(m.group(1).replace(",", ""))

        # ── 4. tel_shop 段落 ──
        tel_el = dl.select_one(".tel_shop")
        if tel_el:
            tel_text = tel_el.get_text(" ", strip=True)

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

            m = re.search(r'([\d.]+)\s*[㎡²]', tel_text)
            if m:
                data["area"] = float(m.group(1))

            for o in _ORIENTATIONS:
                if o + "向" in tel_text or f" {o} " in f" {tel_text} ":
                    data["orientation"] = o
                    break

            type_el = tel_el.select_one(".link_rk, a[href*='baike.fang.com']")
            if type_el:
                bt_text = type_el.get_text(strip=True)
                if any(kw in bt_text for kw in _BUILDING_TYPE_KEYWORDS):
                    data["building_type"] = bt_text
                else:
                    mf = re.search(r'(低层|中层|高层|底层|顶层)', bt_text)
                    if mf:
                        data["floor_level"] = mf.group(1)
                    mt = re.search(r'共\s*(\d+)\s*层', bt_text)
                    if mt:
                        data["total_floors"] = int(mt.group(1))

            if not data.get("total_floors"):
                mt2 = re.search(r'共\s*(\d+)\s*层', tel_text)
                if mt2:
                    data["total_floors"] = int(mt2.group(1))

        # ── 5. add_shop 段落 ──
        add_el = dl.select_one(".add_shop")
        if add_el:
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

            addr_span = add_el.select_one("span")
            if addr_span:
                addr = addr_span.get_text(strip=True)
                if addr and len(addr) >= 4:
                    data["community_address"] = addr

        # ── 6. 兜底提取 ──
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
            if not data.get("floor_level"):
                m = re.search(r'(低|中|高|底|顶)\s*(?:层|楼层)', dl_text)
                if m:
                    level_map = {"低": "低楼层", "中": "中楼层", "高": "高楼层", "底": "低楼层", "顶": "高楼层"}
                    data["floor_level"] = level_map.get(m.group(1))

        if not data.get("total_floors"):
            m = re.search(r'共\s*(\d+)\s*层', dl_text)
            if m:
                data["total_floors"] = int(m.group(1))

        if not data.get("house_id"):
            return None

        # ── 1b. listing_type（从 house_id 前缀或链接推断）──
        hid = data.get("house_id", "")
        if hid.startswith("fp_"):
            data["listing_type"] = "court_auction"
        elif "/fapai/" in dl_html:
            data["listing_type"] = "court_auction"
        else:
            data["listing_type"] = "regular"

        # ── 2. 标题（CSS → text 兜底）──
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
        if not data.get("title"):
            # 纯文本兜底：取 h4 的文字（不管嵌套什么标签）
            h4 = dl.select_one("h4")
            if h4:
                data["title"] = h4.get_text(" ", strip=True)

        # ── 3. 价格（CSS → text 兜底）──
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
        if not data.get("total_price"):
            # 纯文本兜底：找 dl_text 中 "数字万" 或 "数字万元"
            m = re.search(r'([\d.]+)\s*万', dl_text)
            if m:
                val = float(m.group(1))
                # 过滤明显不是总价的数字（如面积数字）
                if 1 < val < 100000:
                    data["total_price"] = val

        unit_el = dl.select_one(".price_right span:not(.red)")
        if unit_el:
            txt = unit_el.get_text(strip=True)
            m = re.search(r'([\d,]+)\s*元', txt)
            if m:
                data["unit_price"] = float(m.group(1).replace(",", ""))
        if not data.get("unit_price"):
            # 纯文本兜底：dl_text 中 "数字元/㎡" 模式
            m = re.search(r'([\d,]+)\s*元\s*/\s*[㎡²]', dl_text)
            if m:
                data["unit_price"] = float(m.group(1).replace(",", ""))

        # ── 4. 户型/面积/朝向 → 优先 CSS，兜底 dl_text ──
        # 收集文本：tel_shop 段落（CSS 命中）或整个 dl_text（兜底）
        tel_el = dl.select_one(".tel_shop")
        meta_text = tel_el.get_text(" ", strip=True) if tel_el else dl_text

        m = re.search(r'(\d+)室(\d+)厅(?:(\d+)卫)?', meta_text)
        if m:
            data["room_count"] = int(m.group(1))
            data["hall_count"] = int(m.group(2))
            data["bathroom_count"] = int(m.group(3)) if m.group(3) else None
        else:
            m = re.search(r'卧室[：:]\s*(\d+)', meta_text)
            if m:
                data["room_count"] = int(m.group(1))

        m = re.search(r'([\d.]+)\s*[㎡²]', meta_text)
        if m:
            data["area"] = float(m.group(1))

        for o in _ORIENTATIONS:
            if o + "向" in meta_text or f" {o} " in f" {meta_text} ":
                data["orientation"] = o
                break

        # 建筑类型 / 楼层（tel_shop 中的链接或纯文本）
        if tel_el:
            type_el = tel_el.select_one(".link_rk, a[href*='baike.fang.com']")
        else:
            type_el = None
        if type_el:
            bt_text = type_el.get_text(strip=True)
            if any(kw in bt_text for kw in _BUILDING_TYPE_KEYWORDS):
                data["building_type"] = bt_text
            else:
                mf = re.search(r'(低层|中层|高层|底层|顶层)', bt_text)
                if mf:
                    data["floor_level"] = mf.group(1)
                mt = re.search(r'共\s*(\d+)\s*层', bt_text)
                if mt:
                    data["total_floors"] = int(mt.group(1))

        if not data.get("total_floors"):
            mt2 = re.search(r'共\s*(\d+)\s*层', meta_text)
            if mt2:
                data["total_floors"] = int(mt2.group(1))

        # ── 5. 小区名/地址 → 优先 CSS，兜底 dl_text ──
        add_el = dl.select_one(".add_shop")
        add_text = add_el.get_text(" ", strip=True) if add_el else dl_text

        comm_link = add_el.select_one("a[href*='/house-xm']") if add_el else None
        if comm_link:
            data["community_name"] = (
                comm_link.get("title", "").strip()
                or comm_link.get_text(strip=True)
            )
        if not data.get("community_name"):
            m = re.search(r'<a[^>]*href="/house-xm\d+/"[^>]*title="([^"]+)"', dl_html)
            if m:
                data["community_name"] = m.group(1).strip()
        if not data.get("community_name"):
            # 纯文本兜底：tel_shop 后面第一段可能是小区名
            m = re.search(r'<a[^>]+title="([^"]+)"[^>]*>', dl_html)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) >= 3 and not any(c in candidate for c in ['>','<','&']):
                    data["community_name"] = candidate

        if add_el:
            addr_span = add_el.select_one("span")
            if addr_span:
                addr = addr_span.get_text(strip=True)
                if addr and len(addr) >= 4:
                    data["community_address"] = addr
        if not data.get("community_address"):
            # 纯文本兜底：元数据中带区县名+后续文本
            m = re.search(r'(?:两江新区|渝中|南岸|沙坪坝|九龙坡|巴南|大渡口|北碚|璧山|江津|永川|合川|长寿|涪陵|南川|綦江|大足|铜梁|潼南|荣昌|万州|开州|梁平|武隆|城口|丰都|垫江|忠县|云阳|奉节|巫山|巫溪|黔江|石柱|秀山|酉阳|彭水)\S{0,30}', dl_text)
            if m:
                data["community_address"] = m.group(0)

        # ── 6. 装修/楼层/房龄 → 纯文本兜底 ──
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
            if not data.get("floor_level"):
                m = re.search(r'(低|中|高|底|顶)\s*(?:层|楼层)', dl_text)
                if m:
                    level_map = {"低": "低楼层", "中": "中楼层", "高": "高楼层", "底": "低楼层", "顶": "高楼层"}
                    data["floor_level"] = level_map.get(m.group(1))

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
        """尝试提取最大页码——自适应多种翻页格式。

        fang.com 翻页 URL 格式历史上变过多次：
          /house-a058-i3{N}/   (当前格式)
          /house/i3{N}/        (旧)
          /house-i3{N}/        (更旧)

        优先取页面文本"共N页"，其次匹配翻页链接中的最大数字。
        新增格式会自动适配（取所有分页数字中的最大值）。
        """
        # 方式 A: 页面文本 "共100页"
        m = re.search(r'共(\d+)页', html)
        if m:
            return int(m.group(1))

        # 方式 B: 收集所有分页链接中的数字，取最大值
        # 匹配 /house...-i3{N}/ 或 /house.../i3{N}/ 等模式
        pages = set()
        for pattern in [
            r'/house(?:-a\d+)?(?:-)?i3(\d+)/',   # /house-a058-i33/  or /house-i33/
            r'/house.*?/i3(\d+)/',                 # any /house.../i3N/  variant
        ]:
            for n in re.findall(pattern, html):
                pages.add(int(n))

        # 方式 C: 尾页链接
        m = re.search(r'/house(?:-a\d+)?(?:-)?i3(\d+)/[^"]*尾页', html)
        if m:
            pages.add(int(m.group(1)))

        return max(pages) if pages else 0


# ── 自适应辅助函数 ─────────────────────────────────────

def _extract_houseid_from_json(attr_value: str) -> str | None:
    """从 data-* 属性值的 JSON 中提取 houseid。

    格式: {"houseid":"123456","housetype":"JUHE",...}
    返回: "3_123456"（前缀由 housetype 决定）
    """
    if not attr_value:
        return None
    try:
        bg_clean = attr_value.replace("&quot;", '"').replace("&#39;", "'")
        bg = json.loads(bg_clean)
        raw_id = bg.get("houseid", "")
        if raw_id:
            listingtype = bg.get("housetype", "2")
            prefix = listingtype.split(",")[0] if "," in listingtype else "3"
            return f"{prefix}_{raw_id}"
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def _extract_houseid_from_url(href: str) -> str | None:
    """从房源链接 URL 中提取 house_id。

    支持 /chushou/3_123456.htm 和 /fapai/out_123456.html 等格式。
    新格式只需在 _LISTING_LINK_PATTERNS 中添加正则即可。
    """
    if not href:
        return None
    for pattern in _LISTING_LINK_PATTERNS:
        m = re.search(pattern, href)
        if m:
            gid = m.group(1)
            if "fapai" in pattern:
                return f"fp_{gid}"
            return gid
    return None
