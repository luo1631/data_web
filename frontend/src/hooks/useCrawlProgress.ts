import { useCallback, useEffect } from "react";
import { useCrawlStore } from "../stores/useCrawlStore";
import {
  createCrawlSSE, startCrawl, stopCrawl,
  fetchCrawlBatches,
} from "../api/crawl";
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
    // 不断开 SSE — 等后端推送最终的 stopped/completed 状态
    // SSE 的 onmessage 会收到最终状态并自动清理
  }, [store]);

  const loadBatches = useCallback(async (): Promise<CrawlBatch[]> => {
    return fetchCrawlBatches();
  }, []);

  // 页面加载时检测是否有 running 批次，自动重连 SSE
  const reconnect = useCallback(async () => {
    const batches = await fetchCrawlBatches();
    const running = batches.find((b) => b.status === "running");
    if (running && !store.activeBatchId) {
      store.setActiveBatch(running.id);
      const es = createCrawlSSE(
        running.id,
        (progress) => {
          store.updateProgress(progress);
          if (progress.status !== "running") store.setActiveBatch(null);
        },
        () => store.setActiveBatch(null),
      );
      store.setEventSource(es);
    }
    return batches;
  }, [store]);

  // 自动重连一次
  useEffect(() => { reconnect(); }, []); // eslint-disable-line

  return {
    activeBatchId: store.activeBatchId,
    progress: store.progress,
    isRunning: store.progress?.status === "running",
    start,
    stop,
    loadBatches,
    reconnect,
  };
}
