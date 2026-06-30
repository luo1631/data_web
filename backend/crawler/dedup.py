"""
去重逻辑：MD5 哈希计算、小区名模糊匹配、增量对比。

用于爬虫入库阶段判断房源是否已存在、内容是否变更，
以及小区名的去重匹配。
"""

import hashlib
import json
import re

import jellyfish
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.listing import Listing
from crawler.constants import (
    JARO_WINKLER_THRESHOLD,
    COMMUNITY_NAME_STRIP_CHARS,
)

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


def is_listing_changed(existing: Listing, new_md5: str) -> bool:
    """判断房源关键字段是否变更。

    Args:
        existing: 数据库中已有的 Listing 对象
        new_md5: 新爬取数据计算的 MD5

    Returns:
        True: 内容已变更，需更新
    """
    return (existing.md5_hash or "") != new_md5


async def match_community(
    name: str,
    district_id: int,
    db: AsyncSession,
) -> int | None:
    """在指定区县中查找匹配的小区。

    匹配策略:
      1. 名称规范化（去分隔符、统一大小写）
      2. 精确匹配（规范化后完全相同）
      3. Jaro-Winkler 模糊匹配（> 0.92）

    Args:
        name: 小区名称（原始文本）
        district_id: 所属区县 ID
        db: 数据库读 session

    Returns:
        匹配到的 community.id，无匹配返回 None
    """
    if not name:
        return None

    clean_name = _normalize_community_name(name)

    # 查询该区县下所有小区
    result = await db.execute(
        select(Community.id, Community.name).where(
            Community.district_id == district_id
        )
    )
    communities = result.all()  # list of (id, name)

    if not communities:
        return None

    best_id = None
    best_score = 0.0

    for comm_id, comm_name in communities:
        clean_comm = _normalize_community_name(comm_name)

        # 1. 精确匹配
        if clean_name == clean_comm:
            return comm_id

        # 2. Jaro-Winkler 相似度
        score = jellyfish.jaro_winkler_similarity(clean_name, clean_comm)
        if score > best_score:
            best_score = score
            best_id = comm_id

    if best_score >= JARO_WINKLER_THRESHOLD and best_id is not None:
        return best_id

    return None


def _normalize_community_name(name: str) -> str:
    """规范化小区名称。

    - 去除分隔符（·、-、—、空格等）
    - 转小写
    - 英文数字部分保留

    Examples:
        "龙湖·U城" → "龙湖u城"
        "龙湖 U城" → "龙湖u城"
        "万科-金色家园" → "万科金色家园"
    """
    if not name:
        return ""

    # 去除指定分隔符
    for ch in COMMUNITY_NAME_STRIP_CHARS:
        name = name.replace(ch, "")

    # 去除多余空白
    name = re.sub(r'\s+', '', name)

    return name.lower()
