/** 数据分析 API 请求层 */

import apiClient from "./client";
import type { APIResponse, ListingSummary } from "../types/common";

export interface OverviewStats {
  total_listings: number;
  avg_total_price: number | null;
  median_total_price: number | null;
  avg_unit_price: number | null;
  median_unit_price: number | null;
  avg_area: number | null;
  median_area: number | null;
  total_price_std: number | null;
  unit_price_std: number | null;
  district_ranking: { name: string; count: number; avg_unit_price: number | null }[];
  price_distribution: { range_label: string; count: number; pct: number }[];
  area_distribution: { range_label: string; count: number; pct: number }[];
  age_distribution: { range_label: string; count: number; pct: number }[];
  layout_distribution: { label: string; count: number; pct: number }[];
  decoration_distribution: { label: string; count: number; pct: number }[];
  orientation_distribution: { label: string; count: number; pct: number }[];
}

export interface DistrictCompareItem {
  name: string; is_urban: boolean; count: number;
  avg_total_price: number | null; avg_unit_price: number | null;
  median_unit_price: number | null; std_unit_price: number | null;
}

export interface FeatureImportance {
  feature_importance: { feature: string; importance: number; pct: number }[];
  r2_score: number | null;
  sample_size: number;
  limitations: string[];
}

export interface ClusterResult {
  clusters: { id: number; label: string; size: number; pct: number;
    avg_unit_price: number; avg_area: number; avg_age_days: number; avg_floors: number }[];
  scatter: { x: number; y: number; cluster_id: number }[];
  pca_variance: number;
  sample_size: number;
}

export interface PriceTrends {
  trends: { month: string; avg_unit_price: number; count: number;
    mom_pct: number | null; yoy_pct: number | null; sma_3: number | null }[];
  source: string;
}

export async function fetchOverview(districtId?: number): Promise<OverviewStats> {
  const resp = await apiClient.get<APIResponse<OverviewStats>>("/analytics/overview", { params: districtId ? { district_id: districtId } : {} });
  return resp.data.data!;
}

export async function fetchDistrictCompare(): Promise<DistrictCompareItem[]> {
  const resp = await apiClient.get<APIResponse<DistrictCompareItem[]>>("/analytics/district-compare");
  return resp.data.data ?? [];
}

export async function fetchPriceDistribution(districtId?: number) {
  const resp = await apiClient.get<APIResponse<any>>("/analytics/price-distribution", { params: districtId ? { district_id: districtId } : {} });
  return resp.data.data!;
}

export async function fetchFeatureImportance(districtId?: number): Promise<FeatureImportance> {
  const resp = await apiClient.get<APIResponse<FeatureImportance>>("/analytics/feature-importance", { params: districtId ? { district_id: districtId } : {} });
  return resp.data.data!;
}

export async function fetchClusters(districtId?: number): Promise<ClusterResult> {
  const resp = await apiClient.get<APIResponse<ClusterResult>>("/analytics/clusters", { params: districtId ? { district_id: districtId } : {} });
  return resp.data.data!;
}

export async function fetchTrends(districtId?: number, months = 12): Promise<PriceTrends> {
  const resp = await apiClient.get<APIResponse<PriceTrends>>("/analytics/trends", { params: { ...(districtId ? { district_id: districtId } : {}), months } });
  return resp.data.data!;
}
