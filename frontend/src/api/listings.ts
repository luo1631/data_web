/** 房源 API 请求层 */

import apiClient from "./client";
import type {
  APIResponse,
  PaginatedResponse,
  Listing,
  ListingDetail,
  ListingFilter,
  ListingSummary,
  PricePoint,
} from "../types/common";

/** 房源列表（分页+筛选+排序） */
export async function fetchListings(
  filters: ListingFilter = {},
): Promise<PaginatedResponse<Listing>> {
  const params: Record<string, string | number | undefined> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params[key] = value;
    }
  }
  const resp = await apiClient.get<APIResponse<PaginatedResponse<Listing>>>(
    "/listings",
    { params },
  );
  return resp.data.data!;
}

/** 房源详情（含价格历史） */
export async function fetchListingDetail(
  id: number,
): Promise<ListingDetail> {
  const resp = await apiClient.get<APIResponse<ListingDetail>>(
    `/listings/${id}`,
  );
  return resp.data.data!;
}

/** 房源价格历史 */
export async function fetchListingPriceHistory(
  id: number,
): Promise<PricePoint[]> {
  const resp = await apiClient.get<APIResponse<PricePoint[]>>(
    `/listings/${id}/history`,
  );
  return resp.data.data ?? [];
}

/** 房源汇总统计 */
export async function fetchListingSummary(
  districtId?: number,
): Promise<ListingSummary> {
  const resp = await apiClient.get<APIResponse<ListingSummary>>(
    "/listings/stats/summary",
    { params: districtId !== undefined ? { district_id: districtId } : {} },
  );
  return resp.data.data!;
}
