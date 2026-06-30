import { create } from "zustand";
import type { ListingFilter } from "../types/common";

interface FilterState {
  filters: ListingFilter;
  setFilter: <K extends keyof ListingFilter>(key: K, value: ListingFilter[K]) => void;
  resetFilters: () => void;
}

const defaults: ListingFilter = {
  status: "active",
  sort_by: "last_updated_at",
  order: "desc",
  page: 1,
  page_size: 30,
};

export const useFilterStore = create<FilterState>((set) => ({
  filters: { ...defaults },

  setFilter: (key, value) =>
    set((s) => ({
      filters: { ...s.filters, [key]: value, page: key === "page" ? (value as number) : 1 },
    })),

  resetFilters: () => set({ filters: { ...defaults } }),
}));
