import { useState, useEffect, useCallback, useRef } from "react";
import { fetchListings } from "../api/listings";
import type { Listing, ListingFilter } from "../types/common";

export function useListings(initialFilters: ListingFilter = {}) {
  const [data, setData] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<ListingFilter>({
    status: "active",
    sort_by: "last_updated_at",
    order: "desc",
    page: 1,
    page_size: 30,
    ...initialFilters,
  });
  // ref 跟踪最新 filters，避免 stale closure
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const load = useCallback(async (f: ListingFilter) => {
    setLoading(true);
    try {
      const res = await fetchListings(f);
      setData(res.items);
      setTotal(res.total);
      setFilters(f);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(filters); }, []); // eslint-disable-line

  const updateFilter = useCallback(
    <K extends keyof ListingFilter>(key: K, value: ListingFilter[K]) => {
      const next = { ...filtersRef.current, [key]: value, page: key === "page" ? (value as number) : 1 };
      load(next);
    },
    [load],
  );

  /** 批量更新多个筛选条件，只触发一次 API 请求 */
  const updateFilters = useCallback(
    (patch: Partial<ListingFilter>) => {
      const next = { ...filtersRef.current, ...patch, page: 1 };
      load(next);
    },
    [load],
  );

  const setPage = useCallback(
    (page: number) => updateFilter("page", page),
    [updateFilter],
  );

  return { data, total, loading, filters, updateFilter, updateFilters, setPage, reload: () => load(filtersRef.current) };
}
