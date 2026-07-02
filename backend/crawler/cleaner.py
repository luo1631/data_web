"""
数据清洗模块：将爬取的原始字段标准化为数据库就绪格式。

所有函数均为纯函数，输入 raw → 输出 cleaned，无副作用。
"""

import re
from datetime import date, datetime

from crawler.constants import (
    PRICE_OUTLIER,
    DECORATION_MAP,
    ORIENTATION_MAP,
    FLOOR_LEVEL_MAP,
)


def clean_listing(
    parsed: "ParsedListing",  # noqa: F821
    decrypted_total: str | None,
    decrypted_unit: str | None,
) -> dict:
    """将解析后的房源数据清洗为 DB 就绪的 dict。

    Args:
        parsed: 从详情页解析出的 ParsedListing
        decrypted_total: 字体解密后的总价文本（如 "132.5万"）
        decrypted_unit: 字体解密后的单价文本（如 "14865元/㎡"）

    Returns:
        清洗后的 dict，包含以下规范化字段:
          total_price, unit_price, area, room_count, hall_count,
          bathroom_count, floor_level, total_floors, orientation,
          decoration, building_type, building_structure, has_elevator,
          community_name, community_address, listing_date, title
        所有值都可能为 None。
    """
    # 价格：优先使用 parsed 中已有的 float 值（移动站），否则从字符串解析
    total_price = parsed.total_price if isinstance(parsed.total_price, (int, float)) else (
        parse_price(decrypted_total) if decrypted_total else None
    )
    unit_price = parsed.unit_price if isinstance(parsed.unit_price, (int, float)) else (
        parse_unit_price(decrypted_unit) if decrypted_unit else None
    )
    area = parse_area(str(parsed.area)) if parsed.area else None

    # 交叉验证：如果单总价和面积都有，计算验证
    if total_price is not None and unit_price is not None and area is not None:
        computed_total = unit_price * area / 10000
        if computed_total > 0:
            diff_ratio = abs(total_price - computed_total) / computed_total
            if diff_ratio > PRICE_OUTLIER["cross_check_tolerance"]:
                import logging
                logging.getLogger(__name__).warning(
                    f"Price cross-check mismatch: total={total_price}万, "
                    f"unit={unit_price}元/㎡, area={area}㎡, expected={computed_total:.1f}万"
                )

    listing_date = parse_date(parsed.listing_date)

    # 计算挂牌天数
    listing_age_days = None
    if listing_date:
        listing_age_days = (date.today() - listing_date).days

    return {
        "total_price": total_price,
        "unit_price": unit_price,
        "area": area,
        "room_count": parsed.room_count,
        "hall_count": parsed.hall_count,
        "bathroom_count": parsed.bathroom_count,
        "floor_level": normalize_floor_level(parsed.floor_level),
        "total_floors": parsed.total_floors,
        "orientation": normalize_orientation(parsed.orientation),
        "decoration": normalize_decoration(parsed.decoration),
        "building_type": parsed.building_type,
        "building_structure": parsed.building_structure,
        "has_elevator": parsed.has_elevator,
        "community_name": parsed.community_name,
        "community_address": parsed.community_address,
        "listing_date": listing_date,
        "listing_age_days": listing_age_days,
        "title": parsed.title,
    }


# ── 解析函数 ─────────────────────────────────────

def parse_price(text: str) -> float | None:
    """解析总价文本。

    Examples:
        "132.5万" → 132.5
        "132.5"   → 132.5
        "132万"    → 132.0
    """
    if not text:
        return None
    text = text.strip().replace(" ", "").replace(",", "")
    # 匹配数字（含小数点）
    match = re.search(r'(\d+\.?\d*)', text)
    if not match:
        return None
    value = float(match.group(1))
    # 如果有 "万" 字，已经是万元；如果是纯数字 > 10000，可能是元，转万元
    if "万" not in text and value > 10000:
        value = value / 10000
    return round(value, 2)


def parse_unit_price(text: str) -> float | None:
    """解析单价文本。

    Examples:
        "14865元/㎡" → 14865.0
        "14865"      → 14865.0
        "1.5万/㎡"   → 15000.0
    """
    if not text:
        return None
    text = text.strip().replace(" ", "").replace(",", "")

    match = re.search(r'(\d+\.?\d*)', text)
    if not match:
        return None
    value = float(match.group(1))
    if "万" in text:
        value *= 10000
    return round(value, 2)


def parse_area(text: str) -> float | None:
    """解析面积文本。

    Examples:
        "89.5㎡" → 89.5
        "89.5"   → 89.5
        "89.5平米" → 89.5
    """
    if not text:
        return None
    text = text.strip().replace(" ", "").replace(",", "")
    match = re.search(r'(\d+\.?\d*)', text)
    if not match:
        return None
    return round(float(match.group(1)), 2)


def parse_date(text: str) -> date | None:
    """解析日期文本，支持多种格式。

    Examples:
        "2024-01-15"          → date(2024, 1, 15)
        "2024年1月15日"       → date(2024, 1, 15)
        "2024/01/15"          → date(2024, 1, 15)
    """
    if not text:
        return None
    text = text.strip()

    # 尝试 ISO 格式
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # 尝试中文格式
    match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    return None


# ── 标准化函数 ───────────────────────────────────

def normalize_decoration(text: str | None) -> str | None:
    """标准化装修程度。

    Examples:
        "精装修" → "精装"
        "豪华装修" → "豪装"
        "其他装修" → "其他"
    """
    if not text:
        return None
    text = text.strip()
    # 精确匹配
    if text in DECORATION_MAP:
        return DECORATION_MAP[text]
    # 模糊匹配
    for key, val in DECORATION_MAP.items():
        if key in text or text in key:
            return val
    return text


def normalize_orientation(text: str | None) -> str | None:
    """标准化朝向。

    Examples:
        "朝南" → "南"
        "南北通透" → "南北"
    """
    if not text:
        return None
    text = text.strip()
    if text in ORIENTATION_MAP:
        return ORIENTATION_MAP[text]
    for key, val in ORIENTATION_MAP.items():
        if key in text or text in key:
            return val
    return text


def normalize_floor_level(text: str | None) -> str | None:
    """标准化楼层描述。

    Examples:
        "低层" → "低楼层"
        "中层/共32层" → "中楼层"
        "顶层" → "高楼层"
    """
    if not text:
        return None
    text = text.strip()
    for key, val in FLOOR_LEVEL_MAP.items():
        if key in text:
            return val
    return text


# ── 列表页数据清洗 ───────────────────────────────

def clean_list_page_data(data: dict) -> dict:
    """将列表页解析结果直接清洗为 DB 就绪 dict（不爬详情页）。

    列表页已含：title, total_price, area, room/hall/bathroom,
    orientation, decoration, floor_level, building_type, total_floors,
    community_name, community_address。
    单价可由总价÷面积推算。
    """
    total_price = data.get("total_price")
    area = data.get("area")

    # 推算单价（列表页单价有时为域名加密字体，优先用解析值，否则推算）
    unit_price = data.get("unit_price")
    if unit_price is None and total_price is not None and area is not None and area > 0:
        unit_price = round(total_price * 10000 / area, 2)

    # listing_date: 列表页不含此信息，使用 None（DB 会以 first_seen_at 兜底）
    listing_date = data.get("listing_date")

    return {
        "total_price": total_price,
        "unit_price": unit_price,
        "area": area,
        "listing_type": data.get("listing_type", "regular"),
        "room_count": data.get("room_count"),
        "hall_count": data.get("hall_count"),
        "bathroom_count": data.get("bathroom_count"),
        "floor_level": normalize_floor_level(data.get("floor_level")),
        "total_floors": data.get("total_floors"),
        "orientation": normalize_orientation(data.get("orientation")),
        "decoration": normalize_decoration(data.get("decoration")),
        "building_type": data.get("building_type"),
        "building_structure": None,
        "has_elevator": None,
        "community_name": data.get("community_name"),
        "community_address": data.get("community_address"),
        "listing_date": listing_date,
        "listing_age_days": None if not listing_date else (date.today() - listing_date).days,
        "title": data.get("title"),
    }


# ── 异常值检测 ───────────────────────────────────

def is_price_outlier(
    total_price: float | None,
    unit_price: float | None,
    area: float | None,
) -> bool:
    """检测价格异常值。

    使用 IQR 之外加基本逻辑校验。返回 True 表示疑似异常。

    Args:
        total_price: 总价（万元）
        unit_price: 单价（元/㎡）
        area: 面积（㎡）

    Returns:
        是否异常
    """
    cfg = PRICE_OUTLIER

    # 基本范围检查
    if total_price is not None:
        if total_price < cfg["total_price_min"] or total_price > cfg["total_price_max"]:
            return True

    if unit_price is not None:
        if unit_price < cfg["unit_price_min"] or unit_price > cfg["unit_price_max"]:
            return True

    if area is not None:
        if area < cfg["area_min"] or area > cfg["area_max"]:
            return True

    # 交叉验证：总价 ≈ 单价 × 面积 / 10000
    if total_price and unit_price and area and area > 0:
        expected = unit_price * area / 10000
        if expected > 0:
            diff = abs(total_price - expected) / expected
            if diff > cfg["cross_check_tolerance"]:
                return True

    return False
