import { useState, useEffect, useCallback } from "react";
import { fetchDistricts, fetchDistrictStats } from "../api/districts";
import { fetchListingSummary } from "../api/listings";
import type { District, DistrictStats, ListingSummary } from "../types/common";

export function useDistricts() {
  const [districts, setDistricts] = useState<District[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchDistricts();
      setDistricts(d);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { districts, loading, reload: load };
}

export function useDistrictStats(districtId: number | null) {
  const [stats, setStats] = useState<DistrictStats | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    try {
      const s = await fetchDistrictStats(id);
      setStats(s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (districtId !== null) load(districtId);
  }, [districtId, load]);

  return { stats, loading };
}

export function useAnalysisSummary(districtId?: number) {
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

  return { summary, loading };
}
