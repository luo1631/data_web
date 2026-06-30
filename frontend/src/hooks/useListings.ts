import { useState, useEffect, useCallback } from "react";
import { fetchListings, fetchListingSummary } from "../api/listings";
import type { Listing, ListingFilter, ListingSummary } from "../types/common";

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
      const next = { ...filters, [key]: value, page: key === "page" ? (value as number) : 1 };
      load(next);
    },
    [filters, load],
  );

  const setPage = useCallback(
    (page: number) => updateFilter("page", page),
    [updateFilter],
  );

  return { data, total, loading, filters, updateFilter, setPage, reload: () => load(filters) };
}

export function useListingSummary(districtId?: number) {
  const [summary, setSummary] = useState<ListingSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (did?: number) => {
    setLoading(true);
    try {
      const s = await fetchListingSummary(did);
      setSummary(s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(districtId); }, [districtId, load]);

  return { summary, loading, reload: () => load(districtId) };
}
