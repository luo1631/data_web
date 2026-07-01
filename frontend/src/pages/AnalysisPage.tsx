import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import Spinner from "../components/ui/Spinner";
import BarChart from "../components/charts/BarChart";
import PieChart from "../components/charts/PieChart";
import ScatterChart from "../components/charts/ScatterChart";
import MapChart from "../components/charts/MapChart";
import { useThemeStore } from "../stores/useThemeStore";
import {
  fetchOverview, fetchDistrictCompare, fetchFeatureImportance,
  fetchClusters, fetchTrends, fetchMapPrices, fetchPrediction,
  type OverviewStats, type DistrictCompareItem, type FeatureImportance,
  type ClusterResult, type PriceTrends, type MapPriceItem,
  type PredictRequest, type PredictResponse,
} from "../api/analytics";
import { DISTRICTS } from "../constants/districts";
import { t } from "../i18n";
import LineChart from "../components/charts/LineChart";

type Tab = "overview" | "map" | "districts" | "factors" | "clusters" | "trends" | "predict";

const TAB_KEYS: Tab[] = ["overview", "map", "districts", "factors", "clusters", "trends", "predict"];

export default function AnalysisPage() {
  const lang = useThemeStore((s) => s.lang);
  const [tab, setTab] = useState<Tab>("overview");
  const location = useLocation();

  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [compare, setCompare] = useState<DistrictCompareItem[]>([]);
  const [importance, setImportance] = useState<FeatureImportance | null>(null);
  const [cluster, setCluster] = useState<ClusterResult | null>(null);
  const [trends, setTrends] = useState<PriceTrends | null>(null);
  const [mapData, setMapData] = useState<MapPriceItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (tab: Tab) => {
    setLoading(true);
    try {
      if (tab === "overview" || tab === "districts") {
        const [o, c] = await Promise.all([fetchOverview(), fetchDistrictCompare()]);
        setOverview(o);
        setCompare(c);
      }
      if (tab === "factors") setImportance(await fetchFeatureImportance());
      if (tab === "clusters") setCluster(await fetchClusters());
      if (tab === "trends") setTrends(await fetchTrends());
      if (tab === "map") setMapData(await fetchMapPrices());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(tab); }, [tab, load]);
  useEffect(() => {
    if (location.pathname === "/analysis") load(tab);
  }, [location.pathname]); // eslint-disable-line

  return (
    <div className="h-full flex flex-col gap-6">
      {/* Tab 切换栏 */}
      <div className="flex gap-1 bg-[var(--color-accent-bg)] p-1 rounded-[var(--radius-lg)] shrink-0">
        {TAB_KEYS.map((key) => (
          <button
            key={key} type="button"
            className={`flex-1 px-3 py-2 text-xs font-medium rounded-[var(--radius-md)] transition-all duration-[var(--duration-fast)] ${
              tab === key
                ? "bg-[var(--color-brand)] text-[var(--color-text-inverse)]"
                : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]"
            }`}
            onClick={() => setTab(key)}
          >
            {t(`analysis.tabs.${key}`, lang)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Spinner size="lg" /></div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {tab === "overview" && <OverviewTab overview={overview} lang={lang} />}
          {tab === "map" && <MapTab data={mapData} lang={lang} />}
          {tab === "districts" && <DistrictsTab compare={compare} lang={lang} />}
          {tab === "factors" && <FactorsTab importance={importance} lang={lang} />}
          {tab === "clusters" && <ClustersTab cluster={cluster} lang={lang} />}
          {tab === "trends" && <TrendsTab trends={trends} lang={lang} />}
          {tab === "predict" && <PredictTab lang={lang} />}
        </div>
      )}
    </div>
  );
}

// ── 通用卡片 class ──
const cardCls = "rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] p-4 border border-[var(--color-border-light)]";
const cardStyle = { boxShadow: "var(--elevation-1)" } as React.CSSProperties;

// ── 价格趋势 Tab ──
function TrendsTab({ trends, lang }: { trends: PriceTrends | null; lang: string }) {
  const empty = !trends || trends.trends.length === 0;
  const items = trends?.trends ?? [];
  const sourceLabels: Record<string, Record<string, string>> = {
    zh: { price_history: "价格历史表", listings: "挂牌日期估算", first_seen_at: "首次采集时间", none: "无数据" },
    en: { price_history: "Price History", listings: "List Date Est.", first_seen_at: "First Seen", none: "None" },
  };

  // 构建含预测日期的 x 轴
  const dates = items.map((d) => d.date);
  const prices = items.map((d) => d.avg_unit_price);
  const sma7 = items.map((d) => d.sma_7 ?? undefined);
  // 数据少于3天不预测（规则见后端 _predict_next_day）
  const hasPrediction = trends?.prediction_date != null && trends?.predicted_price != null && items.length >= 3;

  const allDates = hasPrediction ? [...dates, trends!.prediction_date!] : dates;
  // 预测线: [前 n-1 天留空, 最后实际值(连线起点), 预测值(虚线终点)]
  // 总长度 = n+1，与 allDates 严格对齐
  const predLine = hasPrediction
    ? [...Array(items.length - 1).fill(undefined), prices[prices.length - 1], trends!.predicted_price!]
    : [];

  return (
    <div className="space-y-4">
      {empty && <EmptyHint text={t("analysis.noTrends", lang)} />}

      {/* 预测提示 */}
      {hasPrediction && (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-brand)]/30 bg-[var(--color-brand)]/5 p-3 flex items-center gap-3">
          <span className="text-lg">🔮</span>
          <div>
            <div className="text-xs font-semibold text-[var(--color-text-primary)]">
              {trends!.prediction_date} {t("analysis.predictedPrice", lang)}: <span className="text-[var(--color-brand)] text-sm">{trends!.predicted_price!.toLocaleString()}</span> 元/㎡
            </div>
            <div className="text-xs text-[var(--color-text-tertiary)]">{t("analysis.predictionHint", lang)}</div>
          </div>
        </div>
      )}

      {/* 日价格趋势线 */}
      <div className={cardCls} style={cardStyle}>
        <LineChart title={t("analysis.monthlyTrend", lang)} height={300}
          xData={allDates}
          series={[
            { name: t("analysis.avgUnitPrice", lang), data: [...prices, undefined], color: "#3d5a62" },
            { name: t("analysis.sma7", lang), data: [...sma7, undefined], color: "#e8a87c", lineStyle: "dashed" },
            ...(hasPrediction ? [{ name: t("analysis.predictedPrice", lang), data: predLine, color: "#e74c3c", lineStyle: "dotted" as const }] : []),
          ]}
        />
      </div>

      {/* 明细表 */}
      {!empty && (
        <div className="overflow-x-auto rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border-light)]" style={cardStyle}>
          <table className="w-full text-xs">
            <thead><tr className="bg-[var(--color-brand)]">
              <th className="py-2 px-3 text-left font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{lang === "zh" ? "日期" : "Date"}</th>
              <th className="py-2 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.avgUnitPrice", lang)}</th>
              <th className="py-2 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.sma7", lang)}</th>
              <th className="py-2 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thCount", lang)}</th>
            </tr></thead>
            <tbody>
              {items.map((d, idx) => (
                <tr key={d.date} className={`border-t border-[var(--color-border-light)] transition-colors ${idx % 2 === 1 ? "bg-[var(--color-accent-bg)]/40" : ""}`}>
                  <td className="py-1.5 px-3">{d.date}</td>
                  <td className="py-1.5 px-3 text-right font-medium text-[var(--color-brand)]">{d.avg_unit_price.toLocaleString()}</td>
                  <td className="py-1.5 px-3 text-right">{d.sma_7?.toLocaleString() ?? "-"}</td>
                  <td className="py-1.5 px-3 text-right">{d.count.toLocaleString()}</td>
                </tr>
              ))}
              {hasPrediction && (
                <tr className="border-t border-[var(--color-brand)]/30 bg-[var(--color-brand)]/5">
                  <td className="py-1.5 px-3 font-medium">{trends!.prediction_date} 🔮</td>
                  <td className="py-1.5 px-3 text-right font-bold text-[var(--color-brand)]">{trends!.predicted_price!.toLocaleString()}</td>
                  <td className="py-1.5 px-3 text-right text-[var(--color-text-tertiary)]">-</td>
                  <td className="py-1.5 px-3 text-right text-[var(--color-text-tertiary)]">-</td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="px-3 py-1.5 text-xs text-[var(--color-text-tertiary)]">
            {t("analysis.dataSource", lang)}: {sourceLabels[lang]?.[trends?.source ?? "none"] ?? trends?.source}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 价格预测 Tab ──
function PredictTab({ lang }: { lang: string }) {
  const [form, setForm] = useState<PredictRequest>({
    district_id: 1,
    area: 100,
    room_count: 3,
    hall_count: 2,
    floor_level: "中楼层",
    orientation: "南",
    decoration: "精装",
    building_type: null,
  });
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetchPrediction(form);
      setResult(r);
    } catch {
      setError(lang === "zh" ? "预测失败，请检查数据是否充足" : "Prediction failed. Check data availability.");
    } finally {
      setLoading(false);
    }
  };

  const update = (k: keyof PredictRequest, v: any) => setForm((f) => ({ ...f, [k]: v }));

  const distName = DISTRICTS.find((d) => d.id === form.district_id)?.name ?? "";
  const confColors: Record<string, string> = {
    high: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400",
    medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
    low: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  };
  const confLabels: Record<string, Record<string, string>> = {
    zh: { high: "高置信度", medium: "中置信度", low: "低置信度" },
    en: { high: "High", medium: "Medium", low: "Low" },
  };

  // 统一 select 样式
  const selectCls = "w-full rounded-[var(--radius-xs)] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] px-2 py-1.5 text-xs hover:border-[var(--color-brand)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--color-brand)]/30 focus:border-[var(--color-brand)] transition-all duration-[var(--duration-fast)]";

  return (
    <div className="space-y-4">
      {/* 表单 */}
      <div className={cardCls} style={cardStyle}>
        <h3 className="text-base font-semibold mb-4">
          {lang === "zh" ? "选择房源条件" : "Select Criteria"}
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* 区县 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">{lang === "zh" ? "区县" : "District"}</label>
            <select className={selectCls}
              value={form.district_id ?? ""}
              onChange={(e) => update("district_id", e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{lang === "zh" ? "不限" : "Any"}</option>
              {DISTRICTS.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>

          {/* 面积 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">
              {lang === "zh" ? "面积(㎡)" : "Area(㎡)"} <span className="font-medium text-[var(--color-text-primary)]">{form.area}</span>
            </label>
            <input type="range" min={30} max={300} step={5} value={form.area}
              className="w-full accent-[var(--color-brand)]"
              onChange={(e) => update("area", Number(e.target.value))}
            />
            <div className="flex justify-between text-xs text-[var(--color-text-tertiary)]"><span>30</span><span>300</span></div>
          </div>

          {/* 户型 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">{lang === "zh" ? "户型" : "Layout"}</label>
            <div className="flex gap-1">
              <select className={selectCls + " flex-1"}
                value={form.room_count} onChange={(e) => update("room_count", Number(e.target.value))}>
                {[1,2,3,4,5,6].map((n) => <option key={n} value={n}>{n}{lang === "zh" ? "室" : ""}</option>)}
              </select>
              <select className={selectCls + " flex-1"}
                value={form.hall_count} onChange={(e) => update("hall_count", Number(e.target.value))}>
                {[1,2,3].map((n) => <option key={n} value={n}>{n}{lang === "zh" ? "厅" : ""}</option>)}
              </select>
            </div>
          </div>

          {/* 楼层 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">{lang === "zh" ? "楼层" : "Floor"}</label>
            <select className={selectCls}
              value={form.floor_level} onChange={(e) => update("floor_level", e.target.value)}>
              {["低楼层","中楼层","高楼层"].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* 朝向 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">{lang === "zh" ? "朝向" : "Orient"}</label>
            <select className={selectCls}
              value={form.orientation} onChange={(e) => update("orientation", e.target.value)}>
              {["南","北","南北","东南","西南","东北","西北","东","西","东西"].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* 装修 */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-1">{lang === "zh" ? "装修" : "Decor"}</label>
            <select className={selectCls}
              value={form.decoration} onChange={(e) => update("decoration", e.target.value)}>
              {["精装","豪装","简装","中装","毛坯"].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* 预测按钮 */}
          <div className="flex items-end">
            <button type="button" disabled={loading}
              className="w-full rounded-[var(--radius-sm)] bg-[var(--color-brand)] text-[var(--color-text-inverse)] font-medium py-1.5 text-xs hover:bg-[var(--color-brand-hover)] active:bg-[var(--color-brand-pressed)] disabled:opacity-40 transition-all duration-[var(--duration-fast)]"
              onClick={handleSubmit}
            >
              {loading ? <Spinner size="sm" className="inline" /> : (lang === "zh" ? "💰 预测价格" : "💰 Predict")}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-[var(--radius-sm)] bg-red-50 dark:bg-red-900/20 border border-red-300/40 px-3 py-2 text-xs text-red-700 dark:text-red-400">{error}</div>
      )}

      {/* 预测结果 */}
      {result && (
        <>
          <div className={`${cardCls} !p-5`} style={cardStyle}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-base font-semibold">{lang === "zh" ? "预测结果" : "Prediction"}</h3>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-[var(--radius-pill)] ${confColors[result.confidence] ?? ""}`}>
                {confLabels[lang]?.[result.confidence] ?? result.confidence}
              </span>
            </div>
            <div className="text-xs text-[var(--color-text-secondary)] mb-4">
              {distName} · {form.area}㎡ · {form.room_count}{lang==="zh"?"室":"BR"}{form.hall_count}{lang==="zh"?"厅":""} · {form.floor_level} · {form.orientation} · {form.decoration}
              {result.sample_size > 0 && ` · ${lang==="zh"?"样本":"Samples"}: ${result.sample_size}`}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 rounded-[var(--radius-md)] bg-[var(--color-accent-bg)]">
                <div className="text-xs text-[var(--color-text-secondary)] mb-1">{lang === "zh" ? "预测单价" : "Est. Unit Price"}</div>
                <div className="text-2xl font-bold text-[var(--color-brand)]">
                  {result.predicted_unit_price?.toLocaleString() ?? "-"}
                </div>
                <div className="text-xs text-[var(--color-text-tertiary)]">{lang === "zh" ? "元/㎡" : "¥/㎡"}</div>
              </div>
              <div className="text-center p-4 rounded-[var(--radius-md)] bg-[var(--color-accent-bg)]">
                <div className="text-xs text-[var(--color-text-secondary)] mb-1">{lang === "zh" ? "预测总价" : "Est. Total"}</div>
                <div className="text-2xl font-bold text-[var(--color-brand)]">
                  {result.predicted_total_price?.toLocaleString() ?? "-"}
                </div>
                <div className="text-xs text-[var(--color-text-tertiary)]">万</div>
              </div>
            </div>
          </div>

          {/* 相似房源 */}
          {result.similar_listings.length > 0 && (
            <div>
              <h3 className="text-base font-semibold mb-3">{lang === "zh" ? "相似在售房源" : "Similar Listings"}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {result.similar_listings.map((s) => (
                  <div key={s.id} className={`${cardCls} !p-3 hover:border-[var(--color-brand)]/30 cursor-pointer transition-all duration-[var(--duration-fast)]`}
                    style={{ boxShadow: "var(--elevation-1)" }}
                    onClick={() => s.source_url ? window.open((s.source_url.startsWith("http")?"":"https://cq.esf.fang.com")+s.source_url.replace("https://cq.esf.fang.com",""), "_blank") : null}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <div className="text-xs font-medium truncate flex-1 mr-2">{s.community_name ?? s.title ?? "-"}</div>
                      <div className="text-xs font-bold text-[var(--color-brand)] shrink-0">{s.total_price?.toLocaleString() ?? "-"}万</div>
                    </div>
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1 truncate">{s.title}</div>
                    <div className="flex flex-wrap gap-1 text-xs text-[var(--color-text-tertiary)]">
                      {s.district_name && <span>{s.district_name}</span>}
                      {s.area && <span>{s.area}㎡</span>}
                      {s.room_count != null && <span>{s.room_count}室{s.hall_count}厅</span>}
                      {s.orientation && <span>{s.orientation}</span>}
                      {s.decoration && <span>{s.decoration}</span>}
                      {s.floor_level && <span>{s.floor_level}</span>}
                    </div>
                    <div className="mt-1.5 text-xs text-[var(--color-brand)] font-medium">
                      {s.unit_price?.toLocaleString() ?? "-"} {lang==="zh"?"元/㎡":"¥/㎡"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── 总览 Tab ──
function OverviewTab({ overview, lang }: { overview: OverviewStats | null; lang: string }) {
  const o = overview;
  const total = o?.total_listings ?? 0;
  // 按均价降序排列（方便横向柱状图阅读）
  const sortedRanking = [...(o?.district_ranking ?? [])].sort((a, b) => (b.avg_unit_price ?? 0) - (a.avg_unit_price ?? 0)).slice(0, 15);
  return (
    <div className="space-y-4">
      {total === 0 && <EmptyHint text={t("analysis.noDataHint", lang)} />}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        <StatCard label={t("analysis.totalListings", lang)} value={total.toLocaleString()} />
        <StatCard label={t("analysis.avgPrice", lang)} value={o?.avg_total_price ? `${o.avg_total_price}${t("storage.priceUnit", lang)}` : "-"} />
        <StatCard label={t("analysis.medianPrice", lang)} value={o?.median_total_price ? `${o.median_total_price}${t("storage.priceUnit", lang)}` : "-"} />
        <StatCard label={t("analysis.avgUnitPrice", lang)} value={o?.avg_unit_price?.toLocaleString() ?? "0"} hint={o?.valid_price_count ? `(${(o.valid_price_count / total * 100).toFixed(0)}% 有效)` : undefined} />
        <StatCard label={t("analysis.avgArea", lang)} value={o?.avg_area ? `${o.avg_area}㎡` : "-"} />
        <StatCard label={t("analysis.priceStd", lang)} value={o?.unit_price_std?.toLocaleString() ?? "0"} />
      </div>

      {/* 城市/郊区分组均价 */}
      {o && (o.urban_count > 0 || o.suburb_count > 0) && (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-accent-bg)]/50 p-3">
          <div className="flex items-center gap-4 text-xs">
            <span className="font-medium text-[var(--color-text-secondary)]">{lang === "zh" ? "分组均价" : "By Region"}:</span>
            {o.urban_count > 0 && (
              <span className="text-[var(--color-text-primary)]">
                🏙️ {lang === "zh" ? "主城" : "Urban"} <span className="font-bold text-[var(--color-brand)]">{o.urban_avg_unit_price?.toLocaleString() ?? "-"}</span> 元/㎡
                <span className="text-[var(--color-text-tertiary)] ml-1">({o.urban_count.toLocaleString()} {lang === "zh" ? "套" : "units"}, {(o.urban_count/total*100).toFixed(0)}%)</span>
              </span>
            )}
            {o.suburb_count > 0 && (
              <span className="text-[var(--color-text-primary)]">
                🏘️ {lang === "zh" ? "郊区" : "Suburb"} <span className="font-bold text-[var(--color-brand)]">{o.suburb_avg_unit_price?.toLocaleString() ?? "-"}</span> 元/㎡
                <span className="text-[var(--color-text-tertiary)] ml-1">({o.suburb_count.toLocaleString()} {lang === "zh" ? "套" : "units"}, {(o.suburb_count/total*100).toFixed(0)}%)</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* 数据来源说明 */}
      {total > 0 && (
        <div className="text-[11px] text-[var(--color-text-tertiary)] leading-relaxed">
          {lang === "zh"
            ? "⚠️ 数据来源为 fang.com 挂牌房源，主城区房源占比偏高（约85%），郊区样本稀疏。全局均价 ≈ 主城均价 × 主城权重 + 郊区均价 × 郊区权重，当前更偏向主城区。实际全市均价应低于此数值。"
            : "⚠️ Data from fang.com listings. Urban districts are overrepresented (~85%). The global average is weighted toward urban prices. Actual city-wide average is likely lower."}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className={cardCls} style={cardStyle}>
          <BarChart title={t("analysis.priceDistribution", lang)} height={220}
            xData={o?.price_distribution?.map((d) => d.range_label) ?? []}
            series={[{ name: t("analysis.listingCount", lang), data: o?.price_distribution?.map((d) => d.count) ?? [], color: "#3d5a62" }]}
          />
        </div>
        <div className={cardCls} style={cardStyle}>
          <PieChart title={t("analysis.decorationPie", lang)} height={220}
            data={o?.decoration_distribution?.map((d) => ({ name: d.label, value: d.count })) ?? []}
            roseType
          />
        </div>
      </div>

      <div className={cardCls} style={cardStyle}>
        <BarChart title={t("analysis.districtRanking", lang)} height={280}
          xData={sortedRanking.map((d) => d.name)}
          series={[{ name: t("analysis.avgUnitPrice", lang), data: sortedRanking.map((d) => d.avg_unit_price ?? 0), color: "#6b838a" }]}
          horizontal
        />
      </div>
    </div>
  );
}

// ── 区县对比 Tab ──
function DistrictsTab({ compare, lang }: { compare: DistrictCompareItem[]; lang: string }) {
  const empty = compare.length === 0;
  return (
    <div className="space-y-4">
      {empty && <EmptyHint text={t("analysis.noDataHint", lang)} />}
      <div className={cardCls} style={cardStyle}>
        <BarChart title={t("analysis.districtBar", lang)} height={300}
          xData={compare.map((d) => d.name)}
          series={[{ name: t("analysis.avgUnitPrice", lang), data: compare.map((d) => d.avg_unit_price ?? 0), color: "#3d5a62" }]}
        />
      </div>
      {!empty && (
        <div className="overflow-x-auto rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border-light)]" style={cardStyle}>
          <table className="w-full text-xs">
            <thead><tr className="bg-[var(--color-brand)]">
              <th className="py-2.5 px-3 text-left font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thDistrict", lang)}</th>
              <th className="py-2.5 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thCount", lang)}</th>
              <th className="py-2.5 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thAvgPrice", lang)}</th>
              <th className="py-2.5 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thMedian", lang)}</th>
              <th className="py-2.5 px-3 text-right font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("analysis.thStd", lang)}</th>
            </tr></thead>
            <tbody>
              {compare.map((d, idx) => (
                <tr key={d.name} className={`border-t border-[var(--color-border-light)] transition-colors ${idx % 2 === 1 ? "bg-[var(--color-accent-bg)]/40" : ""}`}>
                  <td className="py-2 px-3">{d.name}</td>
                  <td className="py-2 px-3 text-right">{d.count.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right font-medium text-[var(--color-brand)]">{d.avg_unit_price?.toLocaleString() ?? "-"}</td>
                  <td className="py-2 px-3 text-right">{d.median_unit_price?.toLocaleString() ?? "-"}</td>
                  <td className="py-2 px-3 text-right">{d.std_unit_price?.toLocaleString() ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// 特征名 → 中文映射
const FEATURE_LABEL_MAP: Record<string, string> = {
  area: "面积",
  total_floors: "总楼层",
  listing_age_days: "挂牌天数",
  room_count: "室数",
  hall_count: "厅数",
  bathroom_count: "卫生间",
  floor_level: "楼层",
  orientation: "朝向",
  decoration: "装修",
  building_type: "建筑类型",
  has_elevator: "有无电梯",
  district_id: "所在区县",
};

// ── 因素分析 Tab ──
function FactorsTab({ importance, lang }: { importance: FeatureImportance | null; lang: string }) {
  const empty = !importance || importance.sample_size === 0;
  const mapped = (importance?.feature_importance ?? []).map((f) => ({
    ...f,
    label: lang === "zh" ? (FEATURE_LABEL_MAP[f.feature] ?? f.feature) : f.feature,
  }));
  return (
    <div className="space-y-4">
      {empty && <EmptyHint text={t("analysis.noDataHint", lang)} />}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label={t("analysis.sampleSize", lang)} value={(importance?.sample_size ?? 0).toLocaleString()} />
        <StatCard label={t("analysis.r2Score", lang)} value={importance?.r2_score != null ? importance.r2_score.toFixed(4) : "-"} />
      </div>
      <div className={cardCls} style={cardStyle}>
        <BarChart title={t("analysis.featureImportance", lang)} height={280}
          xData={mapped.map((f) => f.label)}
          series={[{ name: t("analysis.importancePct", lang), data: mapped.map((f) => f.pct), color: "#bdbdca" }]}
          horizontal
        />
      </div>
      {!empty && (
        <div className="rounded-[var(--radius-md)] border border-amber-300/40 bg-amber-50/50 dark:bg-amber-900/20 p-3 text-xs space-y-1" style={{ color: "var(--color-warning)" }}>
          <p className="font-medium" style={{ color: "var(--color-warning)" }}>{t("analysis.modelLimitations", lang)}</p>
          {importance?.limitations?.map((lim, i) => (
            <p key={i}>• {lim}</p>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 聚类 Tab ──
function ClustersTab({ cluster, lang }: { cluster: ClusterResult | null; lang: string }) {
  const empty = !cluster || cluster.sample_size === 0;
  return (
    <div className="space-y-4">
      {empty && <EmptyHint text={t("analysis.noDataHint", lang)} />}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {(cluster?.clusters ?? []).map((c) => (
          <div key={c.id} className={`${cardCls} text-center !p-3`} style={cardStyle}>
            <div className="text-sm font-bold text-[var(--color-brand)]">{c.label}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">{c.size.toLocaleString()} {t("analysis.units", lang)} ({c.pct}%)</div>
            <div className="text-xs mt-1">{t("analysis.avgPriceLabel", lang)} {c.avg_unit_price.toLocaleString()}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">{c.avg_area}㎡ / {c.avg_floors}{t("analysis.floors", lang)}</div>
          </div>
        ))}
      </div>
      <div className={cardCls} style={cardStyle}>
        <ScatterChart title={t("analysis.clusterScatter", lang)} height={300}
          data={cluster?.scatter ?? []}
          clusters={(cluster?.clusters ?? []).map((c) => ({ id: c.id, label: c.label }))}
        />
      </div>
      <p className="text-xs text-[var(--color-text-secondary)]">{t("analysis.pcaVariance", lang)}: {cluster ? (cluster.pca_variance * 100).toFixed(1) : "0.0"}%</p>
    </div>
  );
}

// ── 地图 Tab ──
function MapTab({ data, lang }: { data: MapPriceItem[]; lang: string }) {
  if (data.length === 0) return <EmptyHint text={t("analysis.noMapData", lang)} />;
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const maxPrice = sorted[0];
  const minPrice = sorted[sorted.length - 1];
  // 加权平均 = Σ(区均价 × 房源数) / Σ(房源数)，与 Overview 全局均价算法一致
  const totalListings = sorted.reduce((s, d) => s + (d.count ?? 0), 0);
  const weightedSum = sorted.reduce((s, d) => s + d.value * (d.count ?? 0), 0);
  const avgAll = totalListings > 0 ? Math.round(weightedSum / totalListings) : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <MiniStat label={t("analysis.totalListings", lang)} value={totalListings.toLocaleString()} />
        <MiniStat label={t("analysis.avgUnitPrice", lang)} value={avgAll.toLocaleString()} />
        <MiniStat label={t("analysis.maxPrice", lang)} value={maxPrice ? `${maxPrice.value.toLocaleString()} (${maxPrice.name})` : "-"} />
        <MiniStat label={t("analysis.minPrice", lang)} value={minPrice ? `${minPrice.value.toLocaleString()} (${minPrice.name})` : "-"} />
      </div>
      <div className={cardCls} style={cardStyle}>
        <MapChart data={data} height={460} lang={lang} />
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--color-accent-bg)] px-3 py-2 text-center">
      <div className="text-sm font-bold text-[var(--color-brand)]">{value}</div>
      <div className="text-xs text-[var(--color-text-secondary)] mt-0.5">{label}</div>
    </div>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className={`${cardCls} text-center !p-3`} style={cardStyle}>
      <div className="text-base font-bold text-[var(--color-brand)]">{value}</div>
      <div className="text-xs text-[var(--color-text-secondary)] mt-0.5">{label}</div>
      {hint && <div className="text-[10px] text-[var(--color-text-tertiary)] mt-0.5">{hint}</div>}
    </div>
  );
}

function EmptyHint({ text }: { text?: string }) {
  return (
    <div className="rounded-[var(--radius-sm)] bg-amber-50/50 dark:bg-amber-900/20 border border-amber-300/40 px-3 py-2 text-xs" style={{ color: "var(--color-warning)" }}>
      {text ?? "No data"}
    </div>
  );
}
