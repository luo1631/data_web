"""
聚类分析模块：K-Means 房源画像聚类 + PCA 降维为 2D 散点图数据。

设计原则:
  - 聚类仅基于物理属性（面积、户型、楼层、装修等），不包含价格
  - 价格作为输出统计量，用于描述每个聚类的市场定位
  - 使用肘部法则确定最佳 K 值，避免硬编码

性能: 模块级缓存（10 分钟 TTL），同参数请求直接命中。
"""

import time
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing

# ── 模块级缓存 ──
_CACHE: dict = {}
_CACHE_TTL = 600  # 10 分钟

# K 值搜索范围（最少 5 个以提供足够细分的房源画像）
K_MIN, K_MAX = 5, 8


async def get_clusters(db: AsyncSession, district_id: int | None = None, include_court_auction: bool = True) -> dict:
    """K-Means 聚类 + PCA。

    使用肘部法则从 [K_MIN, K_MAX] 范围内选择最佳 K 值。
    聚类特征仅包含物理属性，price 仅作为输出统计标签。
    结果缓存 10 分钟。

    Returns:
        {clusters: [{id, label, size, avg_unit_price, avg_area, avg_age}],
         scatter: [{x, y, cluster_id}],
         pca_variance: float,
         sample_size: int,
         k_selected: int}
    """
    cache_key = f"{district_id}_{include_court_auction}"
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and now - cached["ts"] < _CACHE_TTL:
        return cached["data"]
    stmt = select(
        Listing.unit_price, Listing.area, Listing.room_count,
        Listing.decoration, Listing.total_floors,
        Listing.listing_age_days,
    ).where(
        Listing.status == "active",
        Listing.area.isnot(None),
        Listing.room_count.isnot(None),
        Listing.unit_price.isnot(None),
    )

    if district_id is not None:
        stmt = stmt.where(Listing.district_id == district_id)

    if not include_court_auction:
        stmt = stmt.where(Listing.listing_type == "regular")

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return {"clusters": [], "scatter": [], "pca_variance": 0, "sample_size": 0, "k_selected": 0}

    cols = ["unit_price", "area", "room_count", "decoration", "total_floors", "listing_age_days"]
    df = pd.DataFrame(rows, columns=cols)

    # ── 类型转换：SQLAlchemy 返回的 Decimal 需要显式转 float ──
    df["unit_price"] = df["unit_price"].astype(float)
    df["area"] = df["area"].astype(float)
    df["room_count"] = df["room_count"].astype(float)
    df["area"] = df["area"].fillna(df["area"].median())
    df["room_count"] = df["room_count"].fillna(2)
    # 装修编码
    deco_map = {"毛坯": 0, "简装": 1, "中装": 2, "精装": 3, "豪装": 4}
    df["decoration_code"] = df["decoration"].map(deco_map).fillna(1).astype(int)
    # total_floors
    if df["total_floors"].isna().all():
        df["total_floors"] = 6
    else:
        df["total_floors"] = df["total_floors"].fillna(df["total_floors"].median())
    df["total_floors"] = df["total_floors"].astype(float)
    # 房龄
    if df["listing_age_days"].isna().all():
        df["listing_age_days"] = 365
    else:
        df["listing_age_days"] = df["listing_age_days"].fillna(df["listing_age_days"].median())
    df["listing_age_days"] = df["listing_age_days"].astype(float)

    # ── 聚类特征：仅物理属性，不含 unit_price ──
    features = ["area", "room_count", "decoration_code", "total_floors", "listing_age_days"]
    X = df[features].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── 肘部法则 + 轮廓系数联合选择最佳 K ──
    max_k = min(K_MAX, len(df) - 1)
    min_k = min(K_MIN, max_k)
    inertias = []
    for k in range(min_k, max_k + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append((k, km.inertia_))

    # 从肘部法则取出前 3 个候选 K，再用轮廓系数精选
    elbow_candidates = _elbow_candidates(inertias, min_k, max_k)

    if len(elbow_candidates) > 1:
        # 对候选 K 值跑 silhouette_score，选最高分
        best_k = min_k
        best_score = -1
        for k in elbow_candidates:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)
            score = silhouette_score(X_scaled, labels, sample_size=min(2000, len(X_scaled)))
            if score > best_score:
                best_score = score
                best_k = k
        N = best_k
    else:
        N = elbow_candidates[0] if elbow_candidates else min_k

    kmeans = KMeans(n_clusters=N, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # PCA 降维
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(X_scaled)

    # 聚类画像（price 仅作为输出统计）
    df["cluster"] = labels
    global_price_80 = float(df["unit_price"].quantile(0.8))
    clusters = []
    for cid in range(N):
        mask = df["cluster"] == cid
        size = mask.sum()
        row = df.loc[mask]
        clusters.append({
            "id": cid,
            "label": _auto_label(row, global_price_80),
            "size": int(size),
            "pct": round(size / len(df) * 100, 1),
            "avg_unit_price": round(float(row["unit_price"].mean()), 2),
            "avg_area": round(float(row["area"].mean()), 2),
            "avg_age_days": round(float(row["listing_age_days"].mean()), 1),
            "avg_floors": round(float(row["total_floors"].mean()), 1),
        })

    scatter = [
        {"x": round(float(x), 4), "y": round(float(y), 4), "cluster_id": int(l)}
        for (x, y), l in zip(xy, labels)
    ]

    data = {
        "clusters": clusters,
        "scatter": scatter,
        "pca_variance": round(float(pca.explained_variance_ratio_.sum()), 4),
        "sample_size": len(df),
        "k_selected": N,
    }
    _CACHE[cache_key] = {"ts": now, "data": data}
    return data


def _elbow_candidates(inertias: list[tuple[int, float]], k_min: int, k_max: int) -> list[int]:
    """肘部法则：返回惯性下降的拐点候选（前 3 个），供轮廓系数精选。

    拐点 = 加速度（二阶差分）最大的 K 值。
    如果拐点不明确，返回 [k_min, k_min+1, ..., 至多 k_max]。
    """
    if len(inertias) <= 2:
        return [k_min]

    vals = [v for _, v in inertias]
    deltas = [vals[i] - vals[i + 1] for i in range(len(vals) - 1)]
    if len(deltas) <= 1:
        return [k_min, min(k_min + 1, k_max)]

    accels = [deltas[i] - deltas[i + 1] for i in range(len(deltas) - 1)]
    if not accels or max(accels) <= 0:
        # 无明确拐点时返回中间几个 K 值
        mid = (k_min + k_max) // 2
        return sorted(set([k_min, mid, k_max]))

    # 按加速度降序排列，取前 3 个候选
    indexed = sorted(enumerate(accels), key=lambda x: x[1], reverse=True)
    candidates = []
    for idx, _ in indexed[:3]:
        k = k_min + idx + 1
        if k_min <= k <= k_max:
            candidates.append(k)
    # 确保至少包含 k_min 和 k_max
    if k_min not in candidates:
        candidates.append(k_min)
    if k_max not in candidates:
        candidates.append(k_max)
    return sorted(set(candidates))


def _auto_label(row: pd.DataFrame, global_price_80: float) -> str:
    """根据聚类中心的物理属性自动生成标签。

    标签格式: [价位][户型档][/楼层]
    价位: 经济/品质/改善/豪宅
    户型档: 小户型/中等户型/大户型
    楼层: 高层(≥20层)/多层(≤7层)，中间地带不附加
    """
    area = float(row["area"].mean())
    price = float(row["unit_price"].mean())
    floors = float(row["total_floors"].mean())

    # 价位（对比全局 80 分位）
    if price >= global_price_80 * 1.5:
        price_tier = "豪宅"
    elif price >= global_price_80:
        price_tier = "改善"
    elif price >= global_price_80 * 0.7:
        price_tier = "品质"
    else:
        price_tier = "经济"

    # 户型档
    if area >= 130:
        area_tier = "大户型"
    elif area >= 80:
        area_tier = "中等户型"
    else:
        area_tier = "小户型"

    base = f"{price_tier}{area_tier}"

    # 楼层
    if floors >= 20:
        base += "/高层"
    elif floors <= 7:
        base += "/多层"

    return base
