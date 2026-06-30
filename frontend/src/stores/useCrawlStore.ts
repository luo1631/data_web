import { create } from "zustand";
import type { CrawlProgress, CrawlTask } from "../types/common";

interface CrawlState {
  /** 当前活跃的批次 ID */
  activeBatchId: number | null;
  /** SSE 连接 */
  eventSource: EventSource | null;
  /** 进度数据 */
  progress: CrawlProgress | null;
  /** 选中的区县 ID 列表 */
  selectedDistricts: number[];

  setActiveBatch: (id: number | null) => void;
  setEventSource: (es: EventSource | null) => void;
  updateProgress: (p: CrawlProgress) => void;
  toggleDistrict: (id: number) => void;
  selectAllDistricts: (ids: number[]) => void;
  clearSelection: () => void;
  reset: () => void;
}

export const useCrawlStore = create<CrawlState>((set, get) => ({
  activeBatchId: null,
  eventSource: null,
  progress: null,
  selectedDistricts: [],

  setActiveBatch: (id) => set({ activeBatchId: id }),

  setEventSource: (es) => {
    const prev = get().eventSource;
    if (prev) prev.close();
    set({ eventSource: es });
  },

  updateProgress: (p) => set({ progress: p }),

  toggleDistrict: (id) => {
    const sel = get().selectedDistricts;
    if (sel.includes(id)) {
      set({ selectedDistricts: sel.filter((x) => x !== id) });
    } else {
      set({ selectedDistricts: [...sel, id] });
    }
  },

  selectAllDistricts: (ids) => set({ selectedDistricts: ids }),

  clearSelection: () => set({ selectedDistricts: [] }),

  reset: () => {
    get().eventSource?.close();
    set({
      activeBatchId: null,
      eventSource: null,
      progress: null,
      selectedDistricts: [],
    });
  },
}));
