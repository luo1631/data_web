"""
去重逻辑：MD5 哈希计算。

用于爬虫入库阶段判断房源内容是否变更。
"""

import hashlib
import json

# MD5 计算参与字段（顺序固定，确保确定性）
MD5_FIELDS = [
    "total_price",
    "unit_price",
    "area",
    "room_count",
    "hall_count",
    "bathroom_count",
    "floor_level",
    "total_floors",
    "orientation",
    "decoration",
    "building_type",
    "building_structure",
    "has_elevator",
    "community_name",
    "title",           # 标题变更也视为内容更新
    "listing_date",    # 挂牌日期变更（重新上架等）
]


def compute_md5(data: dict) -> str:
    """计算房源关键字段的 MD5 哈希值。

    用于：
    - 去重：同一 external_id + 相同 MD5 → 跳过
    - 变更检测：同一 external_id + 不同 MD5 → 更新

    Args:
        data: clean_listing() 返回的 dict

    Returns:
        32 位十六进制 MD5 字符串
    """
    # 按固定顺序提取字段，N/A 值用空字符串
    parts = []
    for field in MD5_FIELDS:
        val = data.get(field)
        if val is None:
            parts.append("")
        elif isinstance(val, bool):
            parts.append("1" if val else "0")
        else:
            parts.append(str(val))

    canonical = json.dumps(parts, ensure_ascii=False, sort_keys=False)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()
