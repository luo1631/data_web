import { useState, useEffect } from "react";
import { Play, Square } from "lucide-react";
import Button from "../components/ui/Button";
import Chip from "../components/ui/Chip";
import Select from "../components/ui/Select";
import Spinner from "../components/ui/Spinner";
import { useThemeStore } from "../stores/useThemeStore";
import { useCrawlProgress } from "../hooks/useCrawlProgress";
import { useDistricts } from "../hooks/useAnalytics";
import { t } from "../i18n";
import type { CrawlBatch, CrawlStartRequest } from "../types/common";

export default function CrawlPage() {
  const { lang } = useThemeStore();
  const { districts, loading: districtsLoading } = useDistricts();
  const crawl = useCrawlProgress();

  const [crawlType, setCrawlType] = useState<string>("full");
  const [maxPages, setMaxPages] = useState(100);
  const [historyBatches, setHistoryBatches] = useState<CrawlBatch[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setHistoryLoading(true);
      const batches = await crawl.loadBatches();
      setHistoryBatches(batches);
      setHistoryLoading(false);
    })();
  }, [crawl.progress]); // eslint-disable-line

  const isRunning = crawl.isRunning;

  const handleStart = async () => {
    const req: CrawlStartRequest = {
      type: crawlType,
      districts: crawl.selectedDistricts.length > 0 ? crawl.selectedDistricts : [],
      max_pages_per_district: maxPages,
    };
    await crawl.start(req);
  };

  const handleStop = async () => {
    if (!crawl.activeBatchId) return;
    await crawl.stop();
  };

  const allDsIds = districts.map((d) => d.id);
  const allSelected =
    crawl.selectedDistricts.length === allDsIds.length && allDsIds.length > 0;

  return (
    <div className="h-full flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">{t("crawl.title", lang)}</h1>

      {/* 控制面板 */}
      <section className="rounded border border-[var(--color-accent)] p-4">
        <h2 className="text-sm font-medium mb-3">{t("crawl.selectDistricts", lang)}</h2>

        {districtsLoading ? (
          <Spinner size="sm" />
        ) : (
          <div className="flex flex-wrap gap-1.5 mb-3 max-h-32 overflow-y-auto">
            {districts.map((d) => (
              <Chip
                key={d.id}
                label={d.name}
                active={crawl.selectedDistricts.includes(d.id)}
                onClick={() => crawl.toggleDistrict(d.id)}
              />
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 mb-3 text-xs">
          <button
            type="button"
            className="text-[var(--color-primary)] underline"
            onClick={() =>
              allSelected
                ? crawl.clearSelection()
                : crawl.selectAllDistricts(allDsIds)
            }
          >
            {allSelected ? t("crawl.clearAll", lang) : t("crawl.selectAll", lang)}
          </button>
          <span className="opacity-40">
            {crawl.selectedDistricts.length > 0
              ? t("crawl.selectedCount", lang, { n: crawl.selectedDistricts.length })
              : t("crawl.noSelection", lang, { total: districts.length })}
          </span>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <Select
            label={t("crawl.crawlType", lang)}
            value={crawlType}
            onChange={(e) => setCrawlType(e.target.value)}
            options={[
              { value: "full", label: t("crawl.fullCrawl", lang) },
              { value: "incremental", label: t("crawl.incremental", lang) },
            ]}
          />
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium opacity-60">{t("crawl.maxPages", lang)}</label>
            <input
              type="number" min={1} max={100} value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="w-20 rounded border border-[var(--color-accent)] bg-[var(--color-bg)] px-2 py-1.5 text-sm"
              aria-label={t("crawl.maxPages", lang)}
            />
          </div>
          <div className="flex gap-2">
            {isRunning ? (
              <Button variant="danger" onClick={handleStop}>
                <Square size={16} /> {t("crawl.stopCrawl", lang)}
              </Button>
            ) : (
              <Button onClick={handleStart}>
                <Play size={16} /> {t("crawl.startCrawl", lang)}
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* 实时进度 */}
      {crawl.progress && (
        <section className="rounded border border-[var(--color-accent)] p-4">
          <h2 className="text-sm font-medium mb-3">
            {t("crawl.progress", lang)}
            {isRunning && <Spinner size="sm" className="inline ml-2" />}
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <Stat label={t("crawl.batch", lang)} value={`#${crawl.progress.batch_id}`} />
            <Stat label={t("crawl.totalTasks", lang)} value={crawl.progress.total_tasks} />
            <Stat label={t("crawl.completedTasks", lang)} value={crawl.progress.completed_tasks} />
            <Stat label={t("crawl.newListings", lang)} value={crawl.progress.new_listings} />
            <Stat label={t("crawl.updatedListings", lang)} value={crawl.progress.updated_listings} />
          </div>

          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--color-accent)]">
                  <th className="text-left py-1 px-2">{t("crawl.colDistrict", lang)}</th>
                  <th className="text-left py-1 px-2">{t("crawl.colStatus", lang)}</th>
                  <th className="text-right py-1 px-2">{t("crawl.colPages", lang)}</th>
                  <th className="text-right py-1 px-2">{t("crawl.colListings", lang)}</th>
                </tr>
              </thead>
              <tbody>
                {crawl.progress.tasks.map((t) => (
                  <tr key={t.id} className="border-b border-[var(--color-accent)]/30">
                    <td className="py-1 px-2">{t.district_name || `#${t.district_id}`}</td>
                    <td className="py-1 px-2">
                      <span
                        className={
                          t.status === "running" ? "text-blue-600"
                          : t.status === "completed" ? "text-green-600"
                          : t.status === "failed" ? "text-red-600"
                          : "opacity-50"
                        }
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="text-right py-1 px-2">{t.page_end || "-"}</td>
                    <td className="text-right py-1 px-2">{t.listings_found}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!crawl.progress && (
        <div className="flex-1 flex items-center justify-center opacity-40 text-sm">
          {t("crawl.noActiveCrawl", lang)}
        </div>
      )}

      {/* 历史批次 */}
      <section className="rounded border border-[var(--color-accent)] p-4">
        <h2 className="text-sm font-medium mb-3">
          {t("crawl.historyBatches", lang)}
          {historyLoading && <Spinner size="sm" className="inline ml-2" />}
        </h2>
        {historyBatches.length === 0 ? (
          <p className="text-xs opacity-40">{t("crawl.noHistory", lang)}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--color-accent)]">
                  <th className="text-left py-1 px-2">{t("crawl.colId", lang)}</th>
                  <th className="text-left py-1 px-2">{t("crawl.colType", lang)}</th>
                  <th className="text-left py-1 px-2">{t("crawl.colStatus", lang)}</th>
                  <th className="text-right py-1 px-2">{t("crawl.colNew", lang)}</th>
                  <th className="text-right py-1 px-2">{t("crawl.colUpdated", lang)}</th>
                </tr>
              </thead>
              <tbody>
                {historyBatches.map((b) => (
                  <tr
                    key={b.id}
                    className="border-b border-[var(--color-accent)]/30 cursor-pointer hover:bg-[var(--color-accent)]/20"
                    onClick={() => crawl.loadBatch(b.id)}
                  >
                    <td className="py-1 px-2">#{b.id}</td>
                    <td className="py-1 px-2">{b.type}</td>
                    <td className="py-1 px-2">{b.status}</td>
                    <td className="text-right py-1 px-2">{b.new_listings}</td>
                    <td className="text-right py-1 px-2">
                      {b.finished_at ? new Date(b.finished_at).toLocaleString() : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded bg-[var(--color-accent)]/30 p-2 text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-[10px] opacity-60">{label}</div>
    </div>
  );
}
