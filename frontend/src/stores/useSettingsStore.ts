import { create } from "zustand";

/** 持久化到 localStorage 的通用设置 */
interface SettingsState {
  defaultMaxPages: number;      // 爬取默认页数
  defaultPageSize: number;      // 表格默认每页条数

  setDefaultMaxPages: (n: number) => void;
  setDefaultPageSize: (n: number) => void;
}

function loadNum(key: string, fallback: number): number {
  try {
    const v = localStorage.getItem(key);
    if (v != null) {
      const n = Number(v);
      if (!isNaN(n) && n > 0) return n;
    }
  } catch { /* ignore */ }
  return fallback;
}

const initialMaxPages = loadNum("settings_defaultMaxPages", 30);
const initialPageSize = loadNum("settings_defaultPageSize", 30);

export const useSettingsStore = create<SettingsState>((set) => ({
  defaultMaxPages: initialMaxPages,
  defaultPageSize: initialPageSize,

  setDefaultMaxPages: (n) => {
    localStorage.setItem("settings_defaultMaxPages", String(n));
    set({ defaultMaxPages: n });
  },

  setDefaultPageSize: (n) => {
    localStorage.setItem("settings_defaultPageSize", String(n));
    set({ defaultPageSize: n });
  },
}));
