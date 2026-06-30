/** 区县 API 请求层 */

import apiClient from "./client";
import type { APIResponse, District, DistrictStats } from "../types/common";

/** 区县列表（含房源计数） */
export async function fetchDistricts(): Promise<District[]> {
  const resp = await apiClient.get<APIResponse<District[]>>("/districts");
  return resp.data.data ?? [];
}

/** 区县维度统计 */
export async function fetchDistrictStats(
  id: number,
): Promise<DistrictStats | null> {
  const resp = await apiClient.get<APIResponse<DistrictStats>>(
    `/districts/${id}/stats`,
  );
  return resp.data.data;
}
