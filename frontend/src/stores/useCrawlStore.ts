import { create } from "zustand";
import type { CrawlProgress } from "../types/common";

interface CrawlState {
  activeBatchId: number | null;
  eventSource: EventSource | null;
  progress: CrawlProgress | null;

  setActiveBatch: (id: number | null) => void;
  setEventSource: (es: EventSource | null) => void;
  updateProgress: (p: CrawlProgress) => void;
  reset: () => void;
}

export const useCrawlStore = create<CrawlState>((set, get) => ({
  activeBatchId: null,
  eventSource: null,
  progress: null,

  setActiveBatch: (id) => set({ activeBatchId: id }),

  setEventSource: (es) => {
    const prev = get().eventSource;
    if (prev) prev.close();
    set({ eventSource: es });
  },

  updateProgress: (p) => set({ progress: p }),

  reset: () => {
    get().eventSource?.close();
    set({
      activeBatchId: null,
      eventSource: null,
      progress: null,
    });
  },
}));
