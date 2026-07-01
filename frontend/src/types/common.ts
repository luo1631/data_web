// ── 通用响应 ──
export interface APIResponse<T> {
  code: number;
  message: string;
  data: T | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── 区县 ──
export interface District {
  id: number;
  name: string;
  pinyin: string | null;
  is_urban: boolean;
  listing_count: number;
}

export interface DistrictStats {
  id: number;
  name: string;
  listing_count: number;
  avg_total_price: number | null;
  avg_unit_price: number | null;
  median_unit_price: number | null;
}

// ── 房源 ──
export interface Listing {
  id: number;
  external_id: string;
  title: string | null;
  district_id: number | null;
  community_name: string | null;
  total_price: number | null;
  unit_price: number | null;
  area: number | null;
  room_count: number | null;
  hall_count: number | null;
  bathroom_count: number | null;
  floor_level: string | null;
  orientation: string | null;
  decoration: string | null;
  listing_date: string | null;
  listing_age_days: number | null;
  status: string;
  source_url: string | null;
  first_seen_at: string | null;
  last_updated_at: string | null;
}

export interface PricePoint {
  total_price: number | null;
  unit_price: number | null;
  record_date: string;
}

export interface ListingDetail extends Listing {
  total_floors: number | null;
  building_type: string | null;
  building_structure: string | null;
  has_elevator: boolean | null;
  community_address: string | null;
  source_platform: string | null;
  md5_hash: string | null;
  last_seen_at: string | null;
  price_history: PricePoint[];
}

export interface ListingFilter {
  district_id?: number;
  min_price?: number;
  max_price?: number;
  min_unit_price?: number;
  max_unit_price?: number;
  min_area?: number;
  max_area?: number;
  room_count?: number;
  decoration?: string;
  orientation?: string;
  floor_level?: string;
  status?: string;
  keyword?: string;
  sort_by?: string;
  order?: string;
  page?: number;
  page_size?: number;
}

export interface ListingSummary {
  total_listings: number;
  avg_total_price: number | null;
  median_total_price: number | null;
  avg_unit_price: number | null;
  median_unit_price: number | null;
  min_price: number | null;
  max_price: number | null;
  avg_area: number | null;
  price_bins: PriceRangeInfo[];
}

export interface PriceRangeInfo {
  range_label: string;
  count: number;
  pct: number;
}

// ── 小区 ──
export interface Community {
  id: number;
  name: string;
  district_id: number | null;
  address: string | null;
  building_year: number | null;
  property_fee: number | null;
  developer: string | null;
  building_count: number | null;
  household_count: number | null;
  green_rate: number | null;
  plot_ratio: number | null;
  lng: number | null;
  lat: number | null;
  listing_count: number;
  avg_price: number | null;
  created_at: string | null;
}

export interface CommunityDetail extends Community {
  min_price: number | null;
  max_price: number | null;
  min_area: number | null;
  max_area: number | null;
  updated_at: string | null;
}

// ── 获取 ──
export interface CrawlTask {
  id: number;
  district_id: number | null;
  district_name: string | null;
  status: string;
  page_start: number;
  page_end: number | null;
  listings_found: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CrawlBatch {
  id: number;
  type: string;
  status: string;
  total_tasks: number;
  completed_tasks: number;
  new_listings: number;
  updated_listings: number;
  removed_listings: number;
  error_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  tasks: CrawlTask[];
}

export interface CrawlProgress {
  batch_id: number;
  status: string;
  type: string;
  total_tasks: number;
  completed_tasks: number;
  new_listings: number;
  updated_listings: number;
  current_district: string | null;
  tasks: CrawlTask[];
}

export interface CrawlStartRequest {
  max_pages_per_district: number;
}

export interface CrawlStartResponse {
  batch_id: number;
  message: string;
}
