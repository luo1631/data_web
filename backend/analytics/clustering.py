"""
聚类分析模块：K-Means 房源画像聚类 + PCA 降维为 2D 散点图数据。
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing

N_CLUSTERS = 5
CLUSTER_LABELS = {
    0: "刚需小户",
    1: "次新改善",
    2: "核心豪宅",
    3: "老城旧房",
    4: "远郊大盘",
}


async def get_clusters(db: AsyncSession, district_id: int | None = None) -> dict:
    """K-Means 聚类 + PCA。

    Returns:
        {clusters: [{id, label, size, avg_unit_price, avg_area, avg_age}],
         scatter: [{x, y, cluster_id}],
         pca_variance: float,
         sample_size: int}
    """
    stmt = select(
        Listing.unit_price, Listing.area, Listing.total_floors,
        Listing.listing_age_days, Listing.room_count,
        Listing.decoration, Listing.floor_level,
    ).where(
        Listing.status == "active",
        Listing.unit_price.isnot(None),
        Listing.area.isnot(None),
        Listing.total_floors.isnot(None),
    )

    if district_id is not None:
        stmt = stmt.where(Listing.district_id == district_id)

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return {"clusters": [], "scatter": [], "pca_variance": 0, "sample_size": 0}

    cols = ["unit_price", "area", "total_floors", "listing_age_days", "room_count", "decoration", "floor_level"]
    df = pd.DataFrame(rows, columns=cols)

    # 填充缺失值
    for c in ["unit_price", "area", "total_floors"]:
        df[c] = df[c].fillna(df[c].median() if not df[c].isna().all() else 0)
    df["listing_age_days"] = df["listing_age_days"].fillna(0)
    df["room_count"] = df["room_count"].fillna(2)
    # 装修编码
    deco_map = {"毛坯": 0, "简装": 1, "中装": 2, "精装": 3, "豪装": 4}
    df["decoration_code"] = df["decoration"].map(deco_map).fillna(1).astype(int)
    floor_map = {"低楼层": 0, "中楼层": 1, "高楼层": 2}
    df["floor_code"] = df["floor_level"].map(floor_map).fillna(1).astype(int)

    features = ["unit_price", "area", "total_floors", "listing_age_days", "room_count", "decoration_code", "floor_code"]
    X = df[features].values

    # K-Means
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    N = min(N_CLUSTERS, len(df))
    kmeans = KMeans(n_clusters=N, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # PCA 降维
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(X_scaled)

    # 聚类画像
    df["cluster"] = labels
    clusters = []
    for cid in range(N):
        mask = df["cluster"] == cid
        size = mask.sum()
        clusters.append({
            "id": cid,
            "label": CLUSTER_LABELS.get(cid, f"聚类{cid}"),
            "size": int(size),
            "pct": round(size / len(df) * 100, 1),
            "avg_unit_price": round(float(df.loc[mask, "unit_price"].mean()), 2),
            "avg_area": round(float(df.loc[mask, "area"].mean()), 2),
            "avg_age_days": round(float(df.loc[mask, "listing_age_days"].mean()), 0),
            "avg_floors": round(float(df.loc[mask, "total_floors"].mean()), 1),
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
    }
