"""数据分析 Pydantic Schema — 所有 /analytics 端点的响应模型"""

from pydantic import BaseModel


# ── 分布项 ──
class DistributionItem(BaseModel):
    range_label: str
    count: int
    pct: float


class CategoricalItem(BaseModel):
    label: str
    count: int
    pct: float


# ── 总览 ──
class DistrictRankItem(BaseModel):
    name: str
    count: int
    avg_unit_price: float | None


class OverviewStats(BaseModel):
    total_listings: int
    valid_price_count: int = 0
    valid_total_count: int = 0
    avg_total_price: float | None
    median_total_price: float | None
    avg_unit_price: float | None
    median_unit_price: float | None
    avg_area: float | None
    median_area: float | None
    total_price_std: float | None
    unit_price_std: float | None
    urban_count: int = 0
    urban_avg_unit_price: float | None = None
    suburb_count: int = 0
    suburb_avg_unit_price: float | None = None
    district_ranking: list[DistrictRankItem]
    price_distribution: list[DistributionItem]
    area_distribution: list[DistributionItem]
    age_distribution: list[DistributionItem]
    layout_distribution: list[CategoricalItem]
    decoration_distribution: list[CategoricalItem]
    orientation_distribution: list[CategoricalItem]


# ── 区县对比 ──
class DistrictCompareItem(BaseModel):
    name: str
    is_urban: bool
    count: int
    avg_total_price: float | None
    avg_unit_price: float | None
    median_unit_price: float | None
    std_unit_price: float | None


# ── 特征重要性 ──
class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float
    pct: float


class FeatureImportance(BaseModel):
    feature_importance: list[FeatureImportanceItem]
    r2_score: float | None
    sample_size: int
    limitations: list[str]


# ── 聚类 ──
class ClusterItem(BaseModel):
    id: int
    label: str
    size: int
    pct: float
    avg_unit_price: float
    avg_area: float
    avg_age_days: float
    avg_floors: float


class ScatterPoint(BaseModel):
    x: float
    y: float
    cluster_id: int


class ClusterResult(BaseModel):
    clusters: list[ClusterItem]
    scatter: list[ScatterPoint]
    pca_variance: float
    sample_size: int
    k_selected: int = 0


# ── 趋势 ──
class TrendItem(BaseModel):
    date: str
    avg_unit_price: float
    count: int
    sma_7: float | None


class PriceTrends(BaseModel):
    trends: list[TrendItem]
    source: str
    prediction_date: str | None = None
    predicted_price: float | None = None
    status_note: str | None = None


# ── 价格预测 ──
class PredictRequest(BaseModel):
    district_id: int | None = None
    area: float
    room_count: int = 3
    hall_count: int = 2
    floor_level: str = "中楼层"
    orientation: str = "南"
    decoration: str = "精装"
    building_type: str | None = None


class SimilarListing(BaseModel):
    id: int
    title: str | None
    community_name: str | None
    total_price: float | None
    unit_price: float | None
    area: float | None
    room_count: int | None
    hall_count: int | None
    floor_level: str | None
    orientation: str | None
    decoration: str | None
    district_name: str | None
    source_url: str | None


class PredictResponse(BaseModel):
    predicted_unit_price: float | None
    predicted_total_price: float | None
    confidence: str
    sample_size: int
    r2_score: float | None
    similar_listings: list[SimilarListing]
