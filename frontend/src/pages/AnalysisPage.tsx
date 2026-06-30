import { useState, useEffect, useCallback } from "react";
import Spinner from "../components/ui/Spinner";
import Select from "../components/ui/Select";
import BarChart from "../components/charts/BarChart";
import PieChart from "../components/charts/PieChart";
import LineChart from "../components/charts/LineChart";
import ScatterChart from "../components/charts/ScatterChart";
import MapChart from "../components/charts/MapChart";
import { useThemeStore } from "../stores/useThemeStore";
import { useDistricts } from "../hooks/useAnalytics";
import {
  fetchOverview, fetchDistrictCompare, fetchFeatureImportance,
  fetchClusters, fetchTrends,
  type OverviewStats, type DistrictCompareItem, type FeatureImportance,
  type ClusterResult, type PriceTrends,
} from "../api/analytics";
import { fetchMapPrices, type MapPriceItem } from "../api/analytics";
import { t } from "../i18n";

type Tab = "overview" | "map" | "districts" | "factors" | "clusters" | "trends";

export default function AnalysisPage() {
  const { lang } = useThemeStore();
  const { districts } = useDistricts();
  const [districtId, setDistrictId] = useState<number | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("overview");

  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [compare, setCompare] = useState<DistrictCompareItem[]>([]);
  const [importance, setImportance] = useState<FeatureImportance | null>(null);
  const [cluster, setCluster] = useState<ClusterResult | null>(null);
  const [trendData, setTrendData] = useState<PriceTrends | null>(null);
  const [mapData, setMapData] = useState<MapPriceItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (tab: Tab, did?: number) => {
    setLoading(true);
    try {
      if (tab === "overview" || tab === "districts") {
        const [o, c] = await Promise.all([fetchOverview(did), fetchDistrictCompare()]);
        setOverview(o);
        setCompare(c);
      }
      if (tab === "factors") {
        setImportance(await fetchFeatureImportance(did));
      }
      if (tab === "clusters") {
        setCluster(await fetchClusters(did));
      }
      if (tab === "trends") {
        setTrendData(await fetchTrends(did));
      }
      if (tab === "map") {
        setMapData(await fetchMapPrices());
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(tab, districtId); }, [tab, districtId, load]);

  const districtOpts = [
    { value: "", label: "全市" },
    ...districts.map((d) => ({ value: String(d.id), label: d.name })),
  ];

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: t("analysis.overview", lang) },
    { key: "map", label: "地图" },
    { key: "districts", label: t("analysis.districtCompare", lang) },
    { key: "factors", label: "因素分析" },
    { key: "clusters", label: "聚类画像" },
    { key: "trends", label: t("analysis.priceTrend", lang) },
  ];

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("analysis.title", lang)}</h1>
        <Select
          value={districtId != null ? String(districtId) : ""}
          onChange={(e) => setDistrictId(e.target.value ? Number(e.target.value) : undefined)}
          options={districtOpts} className="w-40"
        />
      </div>

      {/* Tab 栏 */}
      <div className="flex gap-1 border-b border-[var(--color-accent)] pb-1">
        {TABS.map(({ key, label }) => (
          <button
            key={key} type="button"
            className={`px-3 py-1.5 text-xs rounded-t transition-colors ${tab === key ? "bg-[var(--color-primary)] text-[var(--color-text-white)]" : "hover:bg-[var(--color-accent)]"}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Spinner size="lg" /></div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {tab === "overview" && overview && <OverviewTab overview={overview} lang={lang} />}
          {tab === "map" && <MapTab data={mapData} />}
          {tab === "districts" && compare.length > 0 && <DistrictsTab compare={compare} />}
          {tab === "factors" && importance && <FactorsTab importance={importance} />}
          {tab === "clusters" && cluster && <ClustersTab cluster={cluster} />}
          {tab === "trends" && trendData && <TrendsTab trendData={trendData} />}
        </div>
      )}
    </div>
  );
}

// ── 总览 Tab ──
function OverviewTab({ overview, lang }: { overview: OverviewStats; lang: string }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        <Card label={t("analysis.totalListings", lang)} value={overview.total_listings.toLocaleString()} />
        <Card label={t("analysis.avgPrice", lang)} value={overview.avg_total_price ? `${overview.avg_total_price}万` : "-"} />
        <Card label={t("analysis.medianPrice", lang)} value={overview.median_total_price ? `${overview.median_total_price}万` : "-"} />
        <Card label="均价(元/㎡)" value={overview.avg_unit_price?.toLocaleString() ?? "-"} />
        <Card label="面积均值" value={overview.avg_area ? `${overview.avg_area}㎡` : "-"} />
        <Card label="标准差(单价)" value={overview.unit_price_std?.toLocaleString() ?? "-"} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded border border-[var(--color-accent)]">
          <BarChart title={t("analysis.priceDistribution", lang)}
            xData={overview.price_distribution.map((d) => d.range_label)}
            series={[{ name: "房源数", data: overview.price_distribution.map((d) => d.count), color: "#5470c6" }]}
          />
        </div>
        <div className="rounded border border-[var(--color-accent)]">
          <PieChart title={t("analysis.decorationPie", lang)}
            data={overview.decoration_distribution.map((d) => ({ name: d.label, value: d.count }))}
            roseType
          />
        </div>
      </div>

      {/* 区县排名 */}
      <div className="rounded border border-[var(--color-accent)]">
        <BarChart title="区县均价排名 (Top 15)"
          xData={overview.district_ranking.slice(0, 15).map((d) => d.name)}
          series={[{ name: "均价(元/㎡)", data: overview.district_ranking.slice(0, 15).map((d) => d.avg_unit_price ?? 0), color: "#91cc75" }]}
          horizontal
        />
      </div>
    </div>
  );
}

// ── 区县对比 Tab ──
function DistrictsTab({ compare }: { compare: DistrictCompareItem[] }) {
  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--color-accent)]">
        <BarChart title="各区县均价对比"
          xData={compare.map((d) => d.name)}
          series={[{ name: "均价(元/㎡)", data: compare.map((d) => d.avg_unit_price ?? 0), color: "#5470c6" }]}
          height={400}
        />
      </div>
      <div className="overflow-x-auto rounded border border-[var(--color-accent)]">
        <table className="w-full text-xs">
          <thead><tr className="bg-[var(--color-accent)]/50">
            <th className="py-2 px-3 text-left">区县</th>
            <th className="py-2 px-3 text-right">房源数</th>
            <th className="py-2 px-3 text-right">均价(元/㎡)</th>
            <th className="py-2 px-3 text-right">中位价</th>
            <th className="py-2 px-3 text-right">标准差</th>
          </tr></thead>
          <tbody>
            {compare.map((d) => (
              <tr key={d.name} className="border-t border-[var(--color-accent)]/30">
                <td className="py-1 px-3">{d.name}</td>
                <td className="py-1 px-3 text-right">{d.count.toLocaleString()}</td>
                <td className="py-1 px-3 text-right">{d.avg_unit_price?.toLocaleString() ?? "-"}</td>
                <td className="py-1 px-3 text-right">{d.median_unit_price?.toLocaleString() ?? "-"}</td>
                <td className="py-1 px-3 text-right">{d.std_unit_price?.toLocaleString() ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 因素分析 Tab ──
function FactorsTab({ importance }: { importance: FeatureImportance }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Card label="样本数" value={importance.sample_size.toLocaleString()} />
        <Card label="R² 得分" value={importance.r2_score != null ? importance.r2_score.toFixed(4) : "-"} />
      </div>

      <div className="rounded border border-[var(--color-accent)]">
        <BarChart title="特征重要性排序 (RandomForest)"
          xData={importance.feature_importance.map((f) => f.feature)}
          series={[{ name: "重要性(%)", data: importance.feature_importance.map((f) => f.pct), color: "#ee6666" }]}
          horizontal
        />
      </div>

      <div className="rounded border border-[var(--color-accent)] p-3 text-xs opacity-70 space-y-1">
        <p className="font-medium">⚠ 模型局限性</p>
        {importance.limitations.map((lim, i) => (
          <p key={i}>• {lim}</p>
        ))}
      </div>
    </div>
  );
}

// ── 聚类 Tab ──
function ClustersTab({ cluster }: { cluster: ClusterResult }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {cluster.clusters.map((c) => (
          <div key={c.id} className="rounded border border-[var(--color-accent)] p-3 text-center">
            <div className="text-sm font-bold text-[var(--color-primary)]">{c.label}</div>
            <div className="text-xs opacity-50">{c.size.toLocaleString()} 套 ({c.pct}%)</div>
            <div className="text-xs mt-1">均价 {c.avg_unit_price.toLocaleString()}</div>
            <div className="text-xs">{c.avg_area}㎡ / {c.avg_floors}层</div>
          </div>
        ))}
      </div>

      <div className="rounded border border-[var(--color-accent)]">
        <ScatterChart title="房源聚类 (PCA 2D)"
          data={cluster.scatter}
          clusters={cluster.clusters.map((c) => ({ id: c.id, label: c.label }))}
        />
      </div>
      <p className="text-xs opacity-40">PCA 解释方差: {(cluster.pca_variance * 100).toFixed(1)}%</p>
    </div>
  );
}

// ── 趋势 Tab ──
function TrendsTab({ trendData }: { trendData: PriceTrends }) {
  const hasTrends = trendData.trends.length > 0;
  return (
    <div className="space-y-4">
      {!hasTrends && <p className="text-sm opacity-40">暂无足够的历史数据生成趋势。</p>}
      {hasTrends && (
        <>
          <div className="rounded border border-[var(--color-accent)]">
            <LineChart title="月度均价趋势"
              xData={trendData.trends.map((t) => t.month)}
              series={[
                { name: "均价(元/㎡)", data: trendData.trends.map((t) => t.avg_unit_price), color: "#5470c6" },
                ...(trendData.trends[0]?.sma_3 ? [{ name: "SMA-3", data: trendData.trends.map((t) => t.sma_3 ?? 0), color: "#fac858" }] : []),
              ]}
            />
          </div>
          <div className="rounded border border-[var(--color-accent)]">
            <LineChart title="环比/同比变化"
              xData={trendData.trends.map((t) => t.month)}
              series={[
                { name: "环比(%)", data: trendData.trends.map((t) => t.mom_pct ?? 0), color: "#91cc75" },
                { name: "同比(%)", data: trendData.trends.map((t) => t.yoy_pct ?? 0), color: "#ee6666" },
              ]}
              smooth={false}
            />
          </div>
          <p className="text-xs opacity-40">数据来源: {trendData.source === "price_history" ? "价格历史表" : "挂牌日期估算"}</p>
        </>
      )}
    </div>
  );
}

// ── 地图 Tab ──
function MapTab({ data }: { data: MapPriceItem[] }) {
  if (data.length === 0) {
    return <div className="flex-1 flex items-center justify-center opacity-40 text-sm">暂无地图数据</div>;
  }
  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--color-accent)]">
        <MapChart
          title="重庆市各区县二手房均价热力图"
          data={data}
          height={520}
        />
      </div>
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-xs">
        {data.slice(0, 12).map((d) => (
          <div key={d.name} className="rounded bg-[var(--color-accent)]/30 p-2 text-center">
            <div className="font-medium">{d.name}</div>
            <div className="opacity-60">{d.value > 0 ? d.value.toLocaleString() : "-"} 元/㎡</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-accent)] p-3 text-center">
      <div className="text-lg font-bold text-[var(--color-primary)]">{value}</div>
      <div className="text-[10px] opacity-50 mt-0.5">{label}</div>
    </div>
  );
}
