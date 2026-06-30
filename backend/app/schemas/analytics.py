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
    avg_total_price: float | None
    median_total_price: float | None
    avg_unit_price: float | None
    median_unit_price: float | None
    avg_area: float | None
    median_area: float | None
    total_price_std: float | None
    unit_price_std: float | None
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


# ── 趋势 ──
class TrendItem(BaseModel):
    month: str
    avg_unit_price: float
    count: int
    mom_pct: float | None
    yoy_pct: float | None
    sma_3: float | None


class PriceTrends(BaseModel):
    trends: list[TrendItem]
    source: str
