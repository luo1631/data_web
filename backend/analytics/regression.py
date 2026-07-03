"""
价格影响因素分析：RandomForest 特征重要性排序。

定位: "影响房价的关键因素排序"，非精准估值工具。
因为缺少学区、地铁距离、楼层系数等变量，R² 通常 < 0.6。

性能: 模块级缓存（10 分钟 TTL），同参数请求直接命中。
"""

import time
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing

# ── 模块级缓存 ──
_CACHE: dict = {}
_CACHE_TTL = 600  # 10 分钟

# 用于回归的特征列表
NUMERIC_FEATURES = ["area", "total_floors", "listing_age_days"]
CATEGORICAL_FEATURES = [
    "room_count", "hall_count", "bathroom_count",
    "floor_level", "orientation", "decoration",
    "building_type", "has_elevator",
]


async def analyze_feature_importance(
    db: AsyncSession, district_id: int | None = None, include_court_auction: bool = True
) -> dict:
    """RandomForest 特征重要性分析。

    Returns:
        {feature_importance: [{feature, importance, pct}], r2_score, sample_size, limitations: [...]}
    无数据时返回空结果。结果缓存 10 分钟。
    """
    cache_key = f"{district_id}_{include_court_auction}"
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and now - cached["ts"] < _CACHE_TTL:
        return cached["data"]
    # 查询数据
    stmt = select(
        Listing.unit_price,
        Listing.area,
        Listing.total_floors,
        Listing.listing_age_days,
        Listing.room_count,
        Listing.hall_count,
        Listing.bathroom_count,
        Listing.floor_level,
        Listing.orientation,
        Listing.decoration,
        Listing.building_type,
        Listing.has_elevator,
        Listing.district_id,
    ).where(Listing.status == "active", Listing.unit_price.isnot(None))

    if district_id is not None:
        stmt = stmt.where(Listing.district_id == district_id)

    if not include_court_auction:
        stmt = stmt.where(Listing.listing_type == "regular")

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return {"feature_importance": [], "r2_score": None, "sample_size": 0, "limitations": []}

    # 构建 DataFrame
    cols = [
        "unit_price", "area", "total_floors", "listing_age_days",
        "room_count", "hall_count", "bathroom_count",
        "floor_level", "orientation", "decoration",
        "building_type", "has_elevator", "district_id",
    ]
    df = pd.DataFrame(rows, columns=cols)

    # ── 类型转换：SQLAlchemy Decimal → float ──
    df["unit_price"] = df["unit_price"].astype(float)
    for c in NUMERIC_FEATURES:
        df[c] = df[c].astype(float)
    for c in NUMERIC_FEATURES:
        df[c] = df[c].fillna(df[c].median() if not df[c].isna().all() else 0)
    for c in CATEGORICAL_FEATURES:
        df[c] = df[c].fillna("未知").astype(str)

    # 添加区县作为类别特征
    df["district_id"] = df["district_id"].fillna(0).astype(int).astype(str)
    CAT_FEATURES = CATEGORICAL_FEATURES + ["district_id"]

    X = df[NUMERIC_FEATURES + CAT_FEATURES]
    y = df["unit_price"]

    # 预处理
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", max_categories=20), CAT_FEATURES),
    ])

    model = Pipeline([
        ("prep", preprocessor),
        ("rf", RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)),
    ])

    try:
        model.fit(X, y)
    except Exception:
        return {"feature_importance": [], "r2_score": None, "sample_size": len(df), "limitations": ["模型拟合失败"]}

    # R² (交叉验证)
    try:
        scores = cross_val_score(model, X, y, cv=3, scoring="r2")
        r2 = round(float(scores.mean()), 4)
    except Exception:
        r2 = None

    # 特征重要性提取
    rf = model.named_steps["rf"]
    # 获取变换后的特征名
    ohe = model.named_steps["prep"].named_transformers_["cat"]
    cat_names = ohe.get_feature_names_out(CAT_FEATURES)
    all_names = list(NUMERIC_FEATURES) + list(cat_names)

    importances = rf.feature_importances_
    total_imp = importances.sum()
    if total_imp == 0:
        return {"feature_importance": [], "r2_score": r2, "sample_size": len(df), "limitations": []}

    # 聚合类别特征的 importance（把 one-hot 展开的列合并回原特征）
    feat_imp = {}
    for name, imp in zip(NUMERIC_FEATURES, importances[:len(NUMERIC_FEATURES)]):
        feat_imp[name] = float(imp)

    for i, feat in enumerate(CAT_FEATURES):
        val = sum(float(v) for j, v in enumerate(importances[len(NUMERIC_FEATURES):]) if cat_names[j].startswith(feat))
        feat_imp[feat] = val

    # 排序
    sorted_feats = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)
    imp_list = [
        {
            "feature": name,
            "importance": round(v, 6),
            "pct": round(v / total_imp * 100, 1),
        }
        for name, v in sorted_feats
    ]

    limitations = [
        "未纳入学区归属、地铁距离、楼层系数等高影响变量，R² 仅供参考",
        "模型定位为因素重要性排序（排序方向有效），非精准估值工具",
        "类别特征在 one-hot 编码后权重被稀释，排序偏向连续变量（面积等），仅作参考",
    ]

    data = {
        "feature_importance": imp_list,
        "r2_score": r2,
        "sample_size": len(df),
        "limitations": limitations,
    }
    _CACHE[cache_key] = {"ts": now, "data": data}
    return data
