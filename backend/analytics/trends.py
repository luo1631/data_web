"""
价格趋势分析模块：每日 6:00 定时计算日级均价 + SMA-7 + 次日预测。

计算策略:
  - 每日 6:00 自动计算一次当日趋势快照
  - 服务启动时若当前时间 > 6:00，则在启动 5 分钟后补算一次
  - API 直接返回内存缓存，无实时数据库查询
"""

import logging
import threading
from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy import func, select, and_

from app.database import async_session

logger = logging.getLogger("analytics.trends")

# ── 全局缓存 ──
_TREND_CACHE: dict = {
    "data": None,          # dict | None  — get_price_trends 的返回值
    "computed_at": None,   # datetime | None
    "status": "empty",     # "ready" | "pending" | "empty"
}

_LOCK = threading.Lock()
PREDICTION_WINDOW = 30
DEFAULT_DAYS = 60


async def compute_and_cache() -> None:
    """执行数据库查询 + 趋势计算 + 写入全局缓存。

    此函数在异步事件循环中运行（由 APScheduler 调度）。
    """
    from app.models.listing import Listing
    from app.models.price_history import PriceHistory

    logger.info("[Trends] 开始计算价格趋势快照...")

    try:
        async with async_session() as db:
            cutoff = date.today() - timedelta(days=DEFAULT_DAYS)

            # 优先 price_history
            ph_result = await db.execute(
                select(
                    func.strftime("%Y-%m-%d", PriceHistory.record_date).label("date"),
                    func.avg(PriceHistory.unit_price).label("avg_price"),
                    func.count().label("cnt"),
                ).select_from(PriceHistory).join(
                    Listing, PriceHistory.listing_id == Listing.id
                ).where(
                    Listing.status == "active",
                    PriceHistory.record_date >= cutoff,
                ).group_by("date").order_by("date")
            )
            rows = ph_result.all()
            source = "price_history"

            if not rows:
                # 回退 1: listing_date（详情页解析填充，当前批量爬虫仅采集列表页故多为空）
                l_result = await db.execute(
                    select(
                        func.strftime("%Y-%m-%d", Listing.listing_date).label("date"),
                        func.avg(Listing.unit_price).label("avg_price"),
                        func.count().label("cnt"),
                    ).where(
                        Listing.status == "active",
                        Listing.listing_date.isnot(None),
                        Listing.unit_price > 0,
                    ).group_by("date").order_by("date")
                )
                rows = l_result.all()
                source = "listing_date"

            if not rows:
                # 回退 2: first_seen_at（爬虫首次入库时自动填充，保证有数据）
                fs_result = await db.execute(
                    select(
                        func.strftime("%Y-%m-%d", Listing.first_seen_at).label("date"),
                        func.avg(Listing.unit_price).label("avg_price"),
                        func.count().label("cnt"),
                    ).where(
                        Listing.status == "active",
                        Listing.unit_price > 0,
                    ).group_by("date").order_by("date")
                )
                rows = fs_result.all()
                source = "first_seen_at"

            if not rows:
                with _LOCK:
                    _TREND_CACHE["data"] = {"trends": [], "source": "none", "prediction_date": None, "predicted_price": None}
                    _TREND_CACHE["computed_at"] = datetime.now()
                    _TREND_CACHE["status"] = "empty"
                logger.warning("[Trends] 无可用数据，缓存为空")
                return

            trends = [
                {"date": d, "avg_unit_price": round(float(a), 2), "count": c}
                for d, a, c in rows
            ]

        # 计算衍生指标（SMA-7 + 预测）
        result = _add_derived(trends, source)

        with _LOCK:
            _TREND_CACHE["data"] = result
            _TREND_CACHE["computed_at"] = datetime.now()
            _TREND_CACHE["status"] = "ready"

        logger.info(
            "[Trends] 计算完成: %d 天数据, source=%s, predicted=%s",
            len(trends), source, result.get("predicted_price"),
        )

    except Exception:
        logger.exception("[Trends] 价格趋势计算失败")
        with _LOCK:
            _TREND_CACHE["status"] = "empty"


def get_cached_trends() -> dict:
    """返回缓存的价格趋势数据（线程安全）。

    API 端点直接调用此函数，不访问数据库。
    """
    with _LOCK:
        if _TREND_CACHE["status"] == "ready":
            return _TREND_CACHE["data"]
        return {
            "trends": [],
            "source": "none",
            "prediction_date": None,
            "predicted_price": None,
            "status_note": _TREND_CACHE["status"],
        }


def get_cache_status() -> dict:
    """返回缓存状态（调试用）。"""
    with _LOCK:
        return {
            "status": _TREND_CACHE["status"],
            "computed_at": _TREND_CACHE["computed_at"].isoformat() if _TREND_CACHE["computed_at"] else None,
        }


def setup_trends_scheduler(scheduler, startup_time: datetime | None = None) -> None:
    """注册趋势计算的定时任务。

    规则:
      1. 每日 6:00 自动计算
      2. 服务启动时立即计算一次（避免前端空数据等待）

    Args:
        scheduler: APScheduler AsyncIOScheduler 实例
        startup_time: 应用启动时间，默认 now()
    """
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger

    now = startup_time or datetime.now()

    # 每日 6:00
    scheduler.add_job(
        func=compute_and_cache,
        trigger=CronTrigger(hour=6, minute=0),
        id="trends_daily_6am",
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("[Trends] 已注册每日 6:00 趋势计算任务")

    # 启动时立即计算一次（2 秒延迟，给其他初始化留时间）
    scheduler.add_job(
        func=compute_and_cache,
        trigger=DateTrigger(run_date=now + timedelta(seconds=2)),
        id="trends_startup_bootstrap",
        replace_existing=True,
    )
    logger.info("[Trends] 启动补算已调度，将在 %s 执行首次计算", (now + timedelta(seconds=2)).strftime("%H:%M:%S"))


# ── 内部计算函数 ──

def _add_derived(trends: list[dict], source: str) -> dict:
    """计算 SMA-7 均线和次日线性回归预测。"""
    for i in range(len(trends)):
        window = [t["avg_unit_price"] for t in trends[max(0, i - 6):i + 1] if t["avg_unit_price"]]
        trends[i]["sma_7"] = round(sum(window) / len(window), 2) if window else None

    next_date, next_price = _predict_next_day(trends)
    return {
        "trends": trends,
        "source": source,
        "prediction_date": next_date,
        "predicted_price": next_price,
    }


def _predict_next_day(trends: list[dict]) -> tuple[str | None, float | None]:
    """简单线性回归预测次日价格。

    规则：历史数据少于 3 天时不预测（线性拟合无意义）。
    """
    prices = [t["avg_unit_price"] for t in trends if t["avg_unit_price"]]
    if len(prices) < 3:
        return None, None

    window = trends[-PREDICTION_WINDOW:]
    x = np.arange(len(window), dtype=float)
    y = np.array([t["avg_unit_price"] for t in window], dtype=float)

    n = len(x)
    x_mean = x.mean()
    y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    slope = ((x - x_mean) * (y - y_mean)).sum() / denom if denom != 0 else 0.0
    intercept = y_mean - slope * x_mean
    predicted_raw = round(float(slope * len(prices) + intercept), 2)

    last_price = prices[-1]
    if last_price > 0:
        predicted_raw = max(predicted_raw, last_price * 0.7)
        predicted_raw = min(predicted_raw, last_price * 1.3)

    last_date_str = window[-1]["date"]
    last_date = date.fromisoformat(last_date_str)
    next_date = last_date + timedelta(days=1)

    return next_date.isoformat(), predicted_raw
