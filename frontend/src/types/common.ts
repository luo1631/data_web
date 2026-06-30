export interface APIResponse<T> {
  code: number;
  message: string;
  data: T | null;
}

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
