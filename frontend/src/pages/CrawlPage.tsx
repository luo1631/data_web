import { useState, useEffect, useRef } from "react";
import { Play, Square } from "lucide-react";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Spinner from "../components/ui/Spinner";
import { useThemeStore } from "../stores/useThemeStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useCrawlProgress } from "../hooks/useCrawlProgress";
import { t } from "../i18n";
import type { CrawlBatch } from "../types/common";

export default function CrawlPage() {
  const lang = useThemeStore((s) => s.lang);
  const defaultMaxPages = useSettingsStore((s) => s.defaultMaxPages);
  const crawl = useCrawlProgress();

  const [maxPages, setMaxPages] = useState(defaultMaxPages);
  const [batches, setBatches] = useState<CrawlBatch[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const loaded = useRef(false);

  const loadHistory = async () => {
    setHistoryLoading(true);
    const result = await crawl.reconnect();
    setBatches(result);
    setHistoryLoading(false);
  };

  useEffect(() => {
    if (!loaded.current) {
      loaded.current = true;
      loadHistory();
    }
  }, []); // eslint-disable-line

  const isRunning = crawl.isRunning;
  const prevRunning = useRef(false);
  useEffect(() => {
    if (prevRunning.current && !isRunning) {
      loadHistory();
    }
    prevRunning.current = isRunning;
  }, [isRunning]);

  const handleStart = () => {
    crawl.start({ max_pages_per_district: maxPages });
  };

  const handleStop = async () => {
    if (!crawl.activeBatchId) return;
    await crawl.stop();
  };

  const progress = crawl.progress;
  const currentPage = progress?.tasks?.[0]?.page_end ?? 0;
  const historyOnly = batches.filter((b) => !progress || b.id !== progress.batch_id);

  return (
    <div className="h-full flex flex-col gap-8">

      {/* 控制面板 */}
      <section
        className="shrink-0 rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] p-6 border border-[var(--color-border-light)]"
        style={{ boxShadow: "var(--elevation-1)" }}
      >
        <h2 className="text-base font-semibold mb-4">{t("crawl.controlPanel", lang)}</h2>

        <div className="flex items-center gap-3 flex-wrap">
          <Input
            label={t("crawl.maxPages", lang)}
            className="w-24"
            type="number"
            min={5}
            max={200}
            step={5}
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
          />
          <span className="text-xs text-[var(--color-text-secondary)] self-end pb-1">
            {t("crawl.estimatedTime", lang, { n: Math.ceil(maxPages * 5 / 60) })}
          </span>
          <div className="ml-auto flex gap-2 self-end">
            {isRunning ? (
              <Button variant="danger" onClick={handleStop}>
                <Square size={16} /> {t("crawl.stopCrawl", lang)}
              </Button>
            ) : (
              <Button variant="primary" onClick={handleStart}>
                <Play size={16} /> {t("crawl.startCrawl", lang)}
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* 实时进度 */}
      {progress && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
          <StatCard label={t("crawl.batch", lang)} value={`#${progress.batch_id}`} />
          <StatCard label={t("crawl.currentDistrict", lang)} value={progress.current_district || "..."} />
          <StatCard label={t("crawl.pagesDone", lang)} value={currentPage} />
          <StatCard label={t("crawl.newListings", lang)} value={progress.new_listings} />
          <StatCard label={t("crawl.updatedListings", lang)} value={progress.updated_listings} />
        </div>
      )}

      {/* 任务列表 */}
      <section
        className="flex-1 min-h-0 rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] p-6 border border-[var(--color-border-light)] flex flex-col"
        style={{ boxShadow: "var(--elevation-1)" }}
      >
        <h2 className="text-base font-semibold mb-3 shrink-0">
          {isRunning && <Spinner size="sm" className="inline mr-2" />}
          {t("crawl.taskHistory", lang)}
          {historyLoading && <Spinner size="sm" className="inline ml-2" />}
        </h2>
        <div className="flex-1 min-h-0 overflow-auto">
          {!progress && batches.length === 0 ? (
            <p className="text-xs text-[var(--color-text-secondary)] py-12 text-center">
              {t("crawl.noHistory", lang)}
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 z-10">
                <tr className="bg-[var(--color-brand)]">
                  <th className="text-left py-2 px-2 w-10 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">#</th>
                  <th className="text-left py-2 px-2 w-16 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("crawl.colStatus", lang)}</th>
                  <th className="text-left py-2 px-2 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("crawl.colDistrict", lang)}</th>
                  <th className="text-right py-2 px-2 w-14 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("crawl.colNew", lang)}</th>
                  <th className="text-right py-2 px-2 w-12 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("crawl.colPages", lang)}</th>
                  <th className="text-right py-2 px-2 font-medium text-[var(--color-text-inverse)] uppercase tracking-wider">{t("crawl.colTime", lang)}</th>
                </tr>
              </thead>
              <tbody>
                {/* 当前运行中的批次 */}
                {progress && (
                  <tr className="border-t border-[var(--color-border-light)] bg-[var(--color-accent-bg)]/20">
                    <td className="py-1.5 px-2 text-[var(--color-text-secondary)]">#{progress.batch_id}</td>
                    <td className="py-1.5 px-2">
                      <span className="text-[var(--color-warning)] font-medium">{progress.status}</span>
                    </td>
                    <td className="py-1.5 px-2 font-medium text-[var(--color-text-primary)]">
                      {progress.current_district || (lang === "zh" ? "准备中..." : "Preparing...")}
                    </td>
                    <td className="text-right py-1.5 px-2 tabular-nums">{progress.new_listings}</td>
                    <td className="text-right py-1.5 px-2 text-[var(--color-text-secondary)] tabular-nums">{currentPage || "-"}</td>
                    <td className="text-right py-1.5 px-2 text-[var(--color-text-secondary)]">...</td>
                  </tr>
                )}
                {/* 历史批次（每批一行，区县汇总） */}
                {historyOnly.map((b) => {
                  const distNames = b.district_names ?? [];
                  const distSummary = distNames.length > 0
                    ? (distNames.length <= 3
                      ? distNames.join("，")
                      : `${distNames.slice(0, 3).join("，")} ${lang === "zh" ? "等" : "&"} ${distNames.length} ${lang === "zh" ? "个区县" : "districts"}`)
                    : b.total_tasks > 0
                      ? `${b.total_tasks} ${lang === "zh" ? "个区县" : "districts"}`
                      : "-";
                  return (
                    <tr key={b.id} className="border-t border-[var(--color-border-light)] hover:bg-[var(--color-accent-bg)]/50 transition-colors">
                      <td className="py-1.5 px-2 text-[var(--color-text-secondary)]">#{b.id}</td>
                      <td className="py-1.5 px-2">
                        <span className={
                          b.status === "completed" ? "text-[var(--color-success)] font-medium"
                          : b.status === "failed" ? "text-[var(--color-danger)] font-medium"
                          : "text-[var(--color-text-secondary)]"
                        }>{b.status === "running" ? "stopped" : b.status}</span>
                      </td>
                      <td className="py-1.5 px-2 text-[var(--color-text-primary)]">{distSummary}</td>
                      <td className="text-right py-1.5 px-2 tabular-nums">{b.new_listings}</td>
                      <td className="text-right py-1.5 px-2 text-[var(--color-text-secondary)] tabular-nums">{b.total_pages || "-"}</td>
                      <td className="text-right py-1.5 px-2 text-[var(--color-text-secondary)]">
                        {b.finished_at ? new Date(b.finished_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--color-accent-bg)] p-3 text-center">
      <div className="text-base font-semibold text-[var(--color-brand)] tabular-nums">{value}</div>
      <div className="text-xs text-[var(--color-text-secondary)] mt-0.5">{label}</div>
    </div>
  );
}
