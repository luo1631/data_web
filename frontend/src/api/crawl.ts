/** 爬取控制 API 请求层 */

import apiClient from "./client";
import type {
  APIResponse,
  CrawlBatch,
  CrawlProgress,
  CrawlStartRequest,
  CrawlStartResponse,
} from "../types/common";

/** 启动爬取任务 */
export async function startCrawl(
  req: CrawlStartRequest,
): Promise<CrawlStartResponse> {
  const resp = await apiClient.post<APIResponse<CrawlStartResponse>>(
    "/crawl/start",
    req,
  );
  return resp.data.data!;
}

/** 查询爬取进度 */
export async function fetchCrawlProgress(
  batchId: number,
): Promise<CrawlProgress | null> {
  const resp = await apiClient.get<APIResponse<CrawlProgress>>(
    `/crawl/status/${batchId}`,
  );
  return resp.data.data;
}

/** 停止爬取 */
export async function stopCrawl(
  batchId: number,
): Promise<{ stopped: boolean }> {
  const resp = await apiClient.post<APIResponse<{ stopped: boolean }>>(
    `/crawl/stop/${batchId}`,
  );
  return resp.data.data ?? { stopped: false };
}

/** 历史爬取批次列表 */
export async function fetchCrawlBatches(): Promise<CrawlBatch[]> {
  const resp = await apiClient.get<APIResponse<CrawlBatch[]>>(
    "/crawl/batches",
  );
  return resp.data.data ?? [];
}

/** 创建 SSE 连接监听爬取进度 */
export function createCrawlSSE(
  batchId: number,
  onMessage: (progress: CrawlProgress) => void,
  onComplete?: () => void,
): EventSource {
  const base = apiClient.defaults.baseURL ?? "http://localhost:8000/api/v1";
  const es = new EventSource(`${base}/crawl/status/${batchId}/stream`);

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as CrawlProgress;
      onMessage(data);
      if (data.status === "completed" || data.status === "failed") {
        es.close();
        onComplete?.();
      }
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = () => {
    // 仅当连接已关闭时才通知完成（SSE 在遇到瞬时错误时会自动重连）
    if (es.readyState === EventSource.CLOSED) {
      onComplete?.();
    }
  };

  return es;
}
