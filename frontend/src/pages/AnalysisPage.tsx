import { useState } from "react";
import Spinner from "../components/ui/Spinner";
import Select from "../components/ui/Select";
import { useThemeStore } from "../stores/useThemeStore";
import { useDistricts, useAnalysisSummary } from "../hooks/useAnalytics";
import { t } from "../i18n";

export default function AnalysisPage() {
  const { lang } = useThemeStore();
  const { districts } = useDistricts();
  const [districtId, setDistrictId] = useState<number | undefined>(undefined);
  const { summary, loading } = useAnalysisSummary(districtId);

  const districtOpts = [
    { value: "", label: "全市" },
    ...districts.map((d) => ({ value: String(d.id), label: d.name })),
  ];

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("analysis.title", lang)}</h1>
        <Select
          value={districtId != null ? String(districtId) : ""}
          onChange={(e) => setDistrictId(e.target.value ? Number(e.target.value) : undefined)}
          options={districtOpts}
          className="w-40"
        />
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Spinner size="lg" />
        </div>
      ) : !summary ? (
        <div className="flex-1 flex items-center justify-center opacity-40 text-sm">
          {t("common.error", lang)}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-4">
          {/* 概览卡片 */}
          <section>
            <h2 className="text-sm font-medium mb-2 opacity-60">{t("analysis.overview", lang)}</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <Card label={t("analysis.totalListings", lang)} value={summary.total_listings.toLocaleString()} />
              <Card label={t("analysis.avgPrice", lang)} value={summary.avg_total_price ? `${summary.avg_total_price}万` : "-"} />
              <Card label={t("analysis.medianPrice", lang)} value={summary.median_total_price ? `${summary.median_total_price}万` : "-"} />
              <Card label={t("analysis.minPrice", lang)} value={summary.min_price ? `${summary.min_price}万` : "-"} />
              <Card label={t("analysis.maxPrice", lang)} value={summary.max_price ? `${summary.max_price}万` : "-"} />
              <Card label={t("analysis.avgUnitPrice", lang)} value={summary.avg_unit_price ? summary.avg_unit_price.toLocaleString() : "-"} />
            </div>
          </section>

          {/* 价格分布 */}
          {summary.price_bins.length > 0 && (
            <section className="rounded border border-[var(--color-accent)] p-4">
              <h2 className="text-sm font-medium mb-3">{t("analysis.priceDistribution", lang)}</h2>
              <div className="space-y-1.5">
                {summary.price_bins.map((bin) => {
                  const maxCount = Math.max(...summary.price_bins.map((b) => b.count), 1);
                  const pct = (bin.count / maxCount) * 100;
                  return (
                    <div key={bin.range_label} className="flex items-center gap-2 text-xs">
                      <span className="w-20 text-right opacity-60">{bin.range_label}</span>
                      <div className="flex-1 h-5 rounded bg-[var(--color-accent)]/30 relative overflow-hidden">
                        <div
                          className="absolute inset-y-0 left-0 bg-[var(--color-primary)]/60 rounded transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-12 text-right">{bin.count}</span>
                      <span className="w-10 text-right opacity-40">{bin.pct}%</span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* 图表占位 */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ChartPlaceholder title={t("analysis.districtCompare", lang)}>
              各区县均价柱状图（Phase 5 实现）
            </ChartPlaceholder>
            <ChartPlaceholder title={t("analysis.areaPrice", lang)}>
              面积-价格散点图（Phase 5 实现）
            </ChartPlaceholder>
            <ChartPlaceholder title={t("analysis.decorationPie", lang)}>
              装修情况饼图（Phase 5 实现）
            </ChartPlaceholder>
            <ChartPlaceholder title={t("analysis.priceTrend", lang)}>
              近12个月价格趋势折线图（Phase 5 实现）
            </ChartPlaceholder>
          </section>

          {/* 结论 */}
          <section className="rounded border border-[var(--color-accent)] p-4">
            <h2 className="text-sm font-medium mb-2">{t("analysis.conclusion", lang)}</h2>
            <div className="text-xs space-y-1 opacity-70">
              <p>
                当前在售房源 <strong>{summary.total_listings.toLocaleString()}</strong> 套，
                均价 <strong>{summary.avg_total_price?.toFixed(0) ?? "-"}万</strong>，
                中位价 <strong>{summary.median_total_price?.toFixed(0) ?? "-"}万</strong>，
                单价约 <strong>{summary.avg_unit_price?.toLocaleString() ?? "-"}元/㎡</strong>。
              </p>
              <p>
                价格集中于 <strong>
                  {summary.price_bins
                    .slice()
                    .sort((a, b) => b.count - a.count)[0]?.range_label ?? "-"}
                </strong>区间。
                详细的多维度分析结论将在 <strong>Phase 5</strong> 完成数据建模后输出。
              </p>
            </div>
          </section>
        </div>
      )}
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

function ChartPlaceholder({ title, children }: { title: string; children: string }) {
  return (
    <div className="rounded border border-[var(--color-accent)] border-dashed p-6 flex flex-col items-center justify-center gap-2 min-h-[200px]">
      <h3 className="text-xs font-medium opacity-60">{title}</h3>
      <p className="text-xs opacity-30">{children}</p>
    </div>
  );
}
