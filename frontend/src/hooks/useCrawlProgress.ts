import { useCallback } from "react";
import { useCrawlStore } from "../stores/useCrawlStore";
import { createCrawlSSE, startCrawl, stopCrawl, fetchCrawlProgress, fetchCrawlBatches } from "../api/crawl";
import type { CrawlBatch, CrawlStartRequest } from "../types/common";

export function useCrawlProgress() {
  const store = useCrawlStore();

  const start = useCallback(async (req: CrawlStartRequest) => {
    const res = await startCrawl(req);
    store.setActiveBatch(res.batch_id);

    const es = createCrawlSSE(
      res.batch_id,
      (progress) => store.updateProgress(progress),
      () => store.setActiveBatch(null),
    );
    store.setEventSource(es);

    return res;
  }, [store]);

  const stop = useCallback(async () => {
    if (!store.activeBatchId) return;
    await stopCrawl(store.activeBatchId);
    store.setEventSource(null); // 关闭 SSE 连接
    store.setActiveBatch(null);
  }, [store]);

  const loadBatch = useCallback(async (batchId: number) => {
    const p = await fetchCrawlProgress(batchId);
    if (p) store.updateProgress(p);
  }, [store]);

  const loadBatches = useCallback(async (): Promise<CrawlBatch[]> => {
    return fetchCrawlBatches();
  }, []);

  return {
    activeBatchId: store.activeBatchId,
    progress: store.progress,
    selectedDistricts: store.selectedDistricts,
    isRunning: store.progress?.status === "running",
    toggleDistrict: store.toggleDistrict,
    selectAllDistricts: store.selectAllDistricts,
    clearSelection: store.clearSelection,
    start,
    stop,
    loadBatch,
    loadBatches,
  };
}
