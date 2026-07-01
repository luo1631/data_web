"""数据分析 API 端点：总览、区县对比、价格分布、趋势、聚类、特征重要性、价格预测"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from analytics.stats import get_overview_stats, get_district_compare
from analytics.regression import analyze_feature_importance
from analytics.clustering import get_clusters
from analytics.trends import get_cached_trends, get_cache_status
from analytics.predict import predict_price
from app.schemas.analytics import PredictRequest, PredictResponse
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
async def trends():
    """价格趋势 — 日级均价 + SMA-7 均线 + 次日价格预测。

    数据由后台定时任务维护（每日 6:00 + 启动补算），
    此接口直接返回内存缓存，零数据库查询。
    """
    try:
        data = get_cached_trends()
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/trends/status")
async def trends_status():
    """趋势缓存状态（调试用）。"""
    return ok(data=get_cache_status())


@router.post("/predict")
async def predict(
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
):
    """价格预测 + 相似房源推荐。"""
    try:
        data = await predict_price(
            db,
            district_id=req.district_id,
            area=req.area,
            room_count=req.room_count,
            hall_count=req.hall_count,
            floor_level=req.floor_level,
            orientation=req.orientation,
            decoration=req.decoration,
            building_type=req.building_type,
        )
        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))
