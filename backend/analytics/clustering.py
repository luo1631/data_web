"""
聚类分析模块：K-Means 房源画像聚类 + PCA 降维为 2D 散点图数据。

设计原则:
  - 聚类仅基于物理属性（面积、户型、楼层、装修等），不包含价格
  - 价格作为输出统计量，用于描述每个聚类的市场定位
  - 使用肘部法则确定最佳 K 值，避免硬编码
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing

# K 值搜索范围
K_MIN, K_MAX = 3, 8


async def get_clusters(db: AsyncSession, district_id: int | None = None) -> dict:
    """K-Means 聚类 + PCA。

    使用肘部法则从 [K_MIN, K_MAX] 范围内选择最佳 K 值。
    聚类特征仅包含物理属性，price 仅作为输出统计标签。

    Returns:
        {clusters: [{id, label, size, avg_unit_price, avg_area, avg_age}],
         scatter: [{x, y, cluster_id}],
         pca_variance: float,
         sample_size: int,
         k_selected: int}
    """
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

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return {"clusters": [], "scatter": [], "pca_variance": 0, "sample_size": 0, "k_selected": 0}

    cols = ["unit_price", "area", "room_count", "decoration", "total_floors", "listing_age_days"]
    df = pd.DataFrame(rows, columns=cols)

    # ── 清洗 ──
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

    # ── 肘部法则选择最佳 K ──
    max_k = min(K_MAX, len(df) - 1)
    min_k = min(K_MIN, max_k)
    inertias = []
    for k in range(min_k, max_k + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append((k, km.inertia_))

    N = _elbow_k(inertias, min_k, max_k)

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

    return {
        "clusters": clusters,
        "scatter": scatter,
        "pca_variance": round(float(pca.explained_variance_ratio_.sum()), 4),
        "sample_size": len(df),
        "k_selected": N,
    }


def _elbow_k(inertias: list[tuple[int, float]], k_min: int, k_max: int) -> int:
    """简易肘部法则：找 inertia 下降曲线的拐点。

    如果拐点不明确（样本太少），回退到 k_min。
    """
    if len(inertias) <= 2:
        return k_min

    vals = [v for _, v in inertias]
    # 计算二阶差分（加速度），拐点 = 加速度变化最大的位置
    deltas = [vals[i] - vals[i + 1] for i in range(len(vals) - 1)]
    if len(deltas) <= 1:
        return k_min

    accels = [deltas[i] - deltas[i + 1] for i in range(len(deltas) - 1)]
    if not accels or max(accels) <= 0:
        return k_min

    best_idx = accels.index(max(accels))
    return k_min + best_idx + 1


def _auto_label(row: pd.DataFrame, global_price_80: float) -> str:
    """根据聚类中心的物理属性自动生成标签。"""
    area = float(row["area"].mean())
    price = float(row["unit_price"].mean())
    age = float(row["listing_age_days"].mean())
    floors = float(row["total_floors"].mean())
    rooms = float(row["room_count"].mean())

    age_years = age / 365.0

    # 按面积+价格区分档次（价格对比全局 80 分位）
    if area >= 130 and price >= global_price_80:
        base = "大户型改善"
    elif area >= 100:
        base = "中等户型"
    elif area >= 60:
        base = "刚需户型"
    else:
        base = "小户型"

    # 附加房龄/楼层信息
    if age_years <= 5:
        base = "次新" + base
    elif age_years >= 15:
        base = "老旧" + base

    # 高层 vs 多层
    if floors >= 20:
        base += "/高层"
    elif floors <= 7:
        base += "/多层"

    return base
