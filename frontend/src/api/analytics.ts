/** 数据分析 API 请求层 */

import apiClient from "./client";
import type { APIResponse } from "../types/common";

export interface OverviewStats {
  total_listings: number;
  valid_price_count: number;
  valid_total_count: number;
  avg_total_price: number | null;
  median_total_price: number | null;
  avg_unit_price: number | null;
  median_unit_price: number | null;
  avg_area: number | null;
  median_area: number | null;
  total_price_std: number | null;
  unit_price_std: number | null;
  urban_count: number;
  urban_avg_unit_price: number | null;
  suburb_count: number;
  suburb_avg_unit_price: number | null;
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
  k_selected: number;
}

export interface PriceTrends {
  trends: { date: string; avg_unit_price: number; count: number;
    sma_7: number | null }[];
  source: string;
  prediction_date: string | null;
  predicted_price: number | null;
  status_note: string | null;
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

export async function fetchTrends(): Promise<PriceTrends> {
  const resp = await apiClient.get<APIResponse<PriceTrends>>("/analytics/trends");
  return resp.data.data!;
}

// ── 地图 ──

export interface MapPriceItem {
  name: string;
  value: number;
  count: number;
}

export async function fetchMapPrices(): Promise<MapPriceItem[]> {
  const resp = await apiClient.get<APIResponse<MapPriceItem[]>>("/map/district-prices");
  return resp.data.data ?? [];
}

// ── 价格预测 ──

export interface PredictRequest {
  district_id: number | null;
  area: number;
  room_count: number;
  hall_count: number;
  floor_level: string;
  orientation: string;
  decoration: string;
  building_type: string | null;
}

export interface SimilarListing {
  id: number;
  title: string | null;
  community_name: string | null;
  total_price: number | null;
  unit_price: number | null;
  area: number | null;
  room_count: number | null;
  hall_count: number | null;
  floor_level: string | null;
  orientation: string | null;
  decoration: string | null;
  district_name: string | null;
  source_url: string | null;
}

export interface PredictResponse {
  predicted_unit_price: number | null;
  predicted_total_price: number | null;
  confidence: string;
  sample_size: number;
  r2_score: number | null;
  similar_listings: SimilarListing[];
}

export async function fetchPrediction(req: PredictRequest): Promise<PredictResponse> {
  const resp = await apiClient.post<APIResponse<PredictResponse>>("/analytics/predict", req);
  return resp.data.data!;
}
