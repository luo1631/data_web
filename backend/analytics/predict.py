"""
价格预测模块：KNN 加权平均估值 + 相似房源推荐。

原理：在所有在售房源中找到与用户条件最相似的 K 套，
      按距离倒数加权平均计算预测价格。

性能: 模块级缓存（10 分钟 TTL），缓存 fitted ColumnTransformer + NearestNeighbors，
      避免每次请求重新加载全量数据 + 重复训练。
"""

import time
import pandas as pd
import numpy as np

from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.neighbors import NearestNeighbors

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.district import District
from app.models.community import Community

# ── 模块级模型缓存 ──
_MODEL_CACHE: dict = {}       # key → {ts, preprocessor, knn, df, ...}
_MODEL_CACHE_TTL = 600        # 10 分钟

NUM_FEATURES = ["area", "room_count", "hall_count"]
CAT_FEATURES = ["floor_level", "orientation", "decoration", "district_id"]
K_NEIGHBORS = 30
TOP_SIMILAR = 5


async def predict_price(
    db: AsyncSession,
    district_id: int | None,
    area: float,
    room_count: int,
    hall_count: int,
    floor_level: str,
    orientation: str,
    decoration: str,
    building_type: str | None = None,
) -> dict:
    # ── 缓存命中：复用已训练的 preprocessor + KNN + DataFrame ──
    cache_key = str(district_id)
    now = time.time()
    cached = _MODEL_CACHE.get(cache_key)
    if cached and now - cached["ts"] < _MODEL_CACHE_TTL and cached["df"] is not None:
        preprocessor = cached["preprocessor"]
        knn = cached["knn"]
        df = cached["df"]
        _rooms = cached["_rooms"]
        _halls = cached["_halls"]
    else:
        # ── 1. 加载数据 ──
        cols = [
            Listing.unit_price, Listing.total_price, Listing.area,
            Listing.room_count, Listing.hall_count,
            Listing.floor_level, Listing.orientation, Listing.decoration,
            Listing.district_id,
            Listing.title, Listing.community_id, Listing.source_url, Listing.id,
        ]
        stmt = select(*cols).where(
            Listing.status == "active",
            Listing.unit_price.isnot(None),
            Listing.area.isnot(None),
            Listing.area.between(20, 500),
            Listing.unit_price.between(500, 80000),
        )
        if district_id:
            sub = stmt.where(Listing.district_id == district_id)
            cnt = await db.scalar(select(func.count()).select_from(sub.subquery()))
            if cnt >= 100:
                stmt = sub

        result = await db.execute(stmt)
        rows = result.all()
        if len(rows) < 30:
            _MODEL_CACHE[cache_key] = {"ts": now, "preprocessor": None, "knn": None, "df": None, "_rooms": [], "_halls": []}
            return {
                "predicted_unit_price": None, "predicted_total_price": None,
                "confidence": "low", "sample_size": len(rows),
                "r2_score": None, "similar_listings": [],
            }

        col_names = [
            "unit_price", "total_price", "area",
            "room_count", "hall_count",
            "floor_level", "orientation", "decoration", "district_id",
            "title", "community_id", "source_url", "id",
        ]
        df = pd.DataFrame(rows, columns=col_names)

        # 数值列 — Decimal → float → 填充 NaN
        for c in ["unit_price", "total_price", "area", "room_count", "hall_count"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["area"] = df["area"].fillna(df["area"].median())
        df["room_count"] = df["room_count"].fillna(3)
        df["hall_count"] = df["hall_count"].fillna(2)
        df["unit_price"] = df["unit_price"].fillna(df["unit_price"].median())
        df["total_price"] = df["total_price"].fillna(df["total_price"].median())
        df = df.dropna(subset=NUM_FEATURES + ["unit_price"])

        _rooms = df["room_count"].astype(int).tolist()
        _halls = df["hall_count"].astype(int).tolist()

        # 类别列
        for c in CAT_FEATURES:
            if c in df.columns:
                df[c] = df[c].fillna("未知").astype(str)

        # ── 2. 特征预处理 + KNN（只训练一次，缓存复用）──
        preprocessor = ColumnTransformer([
            ("num", StandardScaler(), NUM_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", max_categories=20), CAT_FEATURES),
        ])
        X = df[NUM_FEATURES + CAT_FEATURES]
        X_prep = preprocessor.fit_transform(X)

        knn = NearestNeighbors(n_neighbors=min(K_NEIGHBORS, len(df)), metric="euclidean")
        knn.fit(X_prep)

        _MODEL_CACHE[cache_key] = {
            "ts": now, "preprocessor": preprocessor, "knn": knn,
            "df": df, "_rooms": _rooms, "_halls": _halls,
        }

    # ── 3. 用户输入（每次请求重新计算）──
    user_row = {
        "area": area,
        "room_count": float(room_count),
        "hall_count": float(hall_count),
        "floor_level": floor_level or "中楼层",
        "orientation": orientation or "南",
        "decoration": decoration or "精装",
        "district_id": str(district_id) if district_id else "不限",
    }
    user_df = pd.DataFrame([user_row])[NUM_FEATURES + CAT_FEATURES]
    user_prep = preprocessor.transform(user_df)

    # ── 4. KNN 搜索 ──
    distances, indices = knn.kneighbors(user_prep)

    # ── 5. 加权平均 ──
    prices = df["unit_price"].values[indices[0]].astype(float)
    dists = distances[0] + 0.01
    weights = 1.0 / dists
    weights /= weights.sum()
    pred_unit = float(np.dot(prices, weights))

    areas = df["area"].values[indices[0]].astype(float)
    pred_total = round(float(np.dot(prices * areas / 10000, weights)), 2)

    # ── 6. 置信度 ──
    median_price = float(df["unit_price"].median())
    deviation = abs(pred_unit - median_price) / median_price
    mean_dist = float(dists.mean())
    if mean_dist < 1.0 and deviation < 0.3:
        confidence = "high"
    elif mean_dist < 2.5 and deviation < 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    # ── 7. 查询社区/区县名 ──
    top_idx_list = list(indices[0][:TOP_SIMILAR])
    cids = [int(df.iloc[i]["community_id"]) for i in top_idx_list if pd.notna(df.iloc[i]["community_id"])]
    dids = [int(df.iloc[i]["district_id"]) for i in top_idx_list if pd.notna(df.iloc[i]["district_id"])]

    comm_map: dict[int, str] = {}
    if cids:
        cr = await db.execute(select(Community.id, Community.name).where(Community.id.in_(cids)))
        comm_map = {c_id: c_name for c_id, c_name in cr.all()}
    dist_map: dict[int, str] = {}
    if dids:
        dr = await db.execute(select(District.id, District.name).where(District.id.in_(dids)))
        dist_map = {d_id: d_name for d_id, d_name in dr.all()}

    similar = []
    for i in top_idx_list:
        row = df.iloc[i]
        cid = int(row["community_id"]) if pd.notna(row["community_id"]) else 0
        did = int(row["district_id"]) if pd.notna(row["district_id"]) else 0
        similar.append({
            "id": int(row["id"]),
            "title": str(row["title"]) if pd.notna(row["title"]) else None,
            "community_name": comm_map.get(cid),
            "total_price": float(row["total_price"]),
            "unit_price": float(row["unit_price"]),
            "area": float(row["area"]),
            "room_count": int(_rooms[i]),
            "hall_count": int(_halls[i]),
            "floor_level": str(row["floor_level"]) if pd.notna(row["floor_level"]) else None,
            "orientation": str(row["orientation"]) if pd.notna(row["orientation"]) else None,
            "decoration": str(row["decoration"]) if pd.notna(row["decoration"]) else None,
            "district_name": dist_map.get(did),
            "source_url": str(row["source_url"]) if pd.notna(row["source_url"]) else None,
        })

    return {
        "predicted_unit_price": round(pred_unit, 0),
        "predicted_total_price": pred_total,
        "confidence": confidence,
        "sample_size": len(df),
        "r2_score": None,
        "similar_listings": similar,
    }
