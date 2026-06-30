"""数据分析 API 端点：总览、区县对比、价格分布、趋势、聚类、特征重要性"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from analytics.stats import get_overview_stats, get_district_compare
from analytics.regression import analyze_feature_importance
from analytics.clustering import get_clusters
from analytics.trends import get_price_trends
from app.utils.response import ok, error

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def analytics_overview(
    district_id: int | None = Query(None, description="区县 ID"),
    db: AsyncSession = Depends(get_db),
):
    """分析总览 — 包含各区县排名的全维度描述性统计。"""
    try:
        data = await get_overview_stats(db, district_id=district_id)
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/district-compare")
async def district_compare(db: AsyncSession = Depends(get_db)):
    """区县对比 — 每个区县的均价、中位数、标准差。"""
    try:
        data = await get_district_compare(db)
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/price-distribution")
async def price_distribution(
    district_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """价格分布 — 价格段、面积段、房龄段分布（复用 overview 的子集）。"""
    try:
        full = await get_overview_stats(db, district_id=district_id)
        return ok(data={
            "total": full["total_listings"],
            "price_distribution": full["price_distribution"],
            "area_distribution": full["area_distribution"],
            "age_distribution": full["age_distribution"],
        })
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/feature-importance")
async def feature_importance(
    district_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """特征重要性 — RandomForest 模型输出特征权重排序。"""
    try:
        data = await analyze_feature_importance(db, district_id=district_id)
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/clusters")
async def clusters(
    district_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """聚类分析 — K-Means 房源画像 + PCA 2D 散点图。"""
    try:
        data = await get_clusters(db, district_id=district_id)
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/trends")
async def trends(
    district_id: int | None = Query(None),
    months: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
):
    """价格趋势 — 月度均价 + 环比/同比 + SMA 平滑。"""
    try:
        data = await get_price_trends(db, district_id=district_id, months=months)
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))
