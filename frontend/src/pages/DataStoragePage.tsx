import { useState, useMemo, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { RotateCcw, RefreshCw, ArrowUpDown } from "lucide-react";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
import Table, { type Column } from "../components/ui/Table";
import { useThemeStore } from "../stores/useThemeStore";
import { useSettingsStore } from "../stores/useSettingsStore";
import { useListings } from "../hooks/useListings";
import { DISTRICTS } from "../constants/districts";
import { t } from "../i18n";
import type { Listing } from "../types/common";

const DECORATION_VALUES = ["毛坯", "简装", "精装", "豪装"] as const;
const ORIENTATION_VALUES = ["南", "北", "南北", "东南", "西南"] as const;
const ROOM_OPTIONS = [1, 2, 3, 4, 5, 6];
const LISTING_TYPE_OPTS: Record<string, Record<string, string>> = {
  zh: { "": "全部类型", regular: "二手房", court_auction: "法拍房" },
  en: { "": "All Types", regular: "Resale", court_auction: "Auction" },
};

export default function DataStoragePage() {
  const lang = useThemeStore((s) => s.lang);
  const defaultPageSize = useSettingsStore((s) => s.defaultPageSize);
  const { data, total, loading, filters, updateFilter, updateFilters, setPage, reload } = useListings({ page_size: defaultPageSize });
  const [sortKey, setSortKey] = useState("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const decorationOpts = useMemo(() => [
    { value: "", label: t("storage.all", lang) },
    ...DECORATION_VALUES.map((v) => ({ value: v, label: v })),
  ], [lang]);

  const orientationOpts = useMemo(() => [
    { value: "", label: t("storage.all", lang) },
    ...ORIENTATION_VALUES.map((v) => ({ value: v, label: v })),
  ], [lang]);

  const roomOpts = useMemo(() => [
    { value: "", label: t("storage.all", lang) },
    ...ROOM_OPTIONS.map((v) => ({ value: String(v), label: `${v}${t("storage.roomSep", lang)}` })),
  ], [lang]);

  const districtOpts = [
    { value: "", label: t("storage.allDistricts", lang) },
    ...DISTRICTS.map((d) => ({ value: String(d.id), label: d.name })),
  ];

  const handleSort = (key: string, dir: "asc" | "desc") => {
    setSortKey(key);
    setSortDir(dir);
    updateFilters({ sort_by: key, order: dir } as any);
  };

  const handleReset = () => {
    setSortKey("id");
    setSortDir("desc");
    updateFilters({
      district_id: undefined,
      listing_type: undefined,
      min_price: undefined, max_price: undefined,
      min_unit_price: undefined, max_unit_price: undefined,
      min_area: undefined, max_area: undefined,
      room_count: undefined, decoration: undefined,
      orientation: undefined, keyword: undefined,
      sort_by: "id", order: "desc",
    });
  };

  const location = useLocation();
  useEffect(() => {
    if (location.pathname === "/storage") reload();
  }, [location.pathname]); // eslint-disable-line

  const toggleSortDir = () => {
    const next = sortDir === "desc" ? "asc" : "desc";
    setSortDir(next);
    updateFilter("order", next as any);
  };

  const columns: Column<Listing>[] = [
    {
      key: "_row", header: "#", width: "50px",
      render: (_r, idx) => (
        <span className="text-[var(--color-text-tertiary)] tabular-nums">
          {(filters.page! - 1) * (filters.page_size ?? 30) + idx + 1}
        </span>
      ),
    },
    {
      key: "title", header: t("storage.columns.title", lang), width: "180px",
      render: (r) => (
        <span className="truncate max-w-[180px] block" title={r.title ?? ""}>
          {r.listing_type === "court_auction" && (
            <span className="inline-block mr-1 px-1 rounded text-[10px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
              {lang === "zh" ? "法拍" : "Auct"}
            </span>
          )}
          {r.title || "-"}
        </span>
      ),
    },
    {
      key: "community_name", header: t("storage.columns.community", lang), width: "120px",
      render: (r) => r.community_name || "-",
    },
    {
      key: "total_price", header: t("storage.columns.totalPrice", lang),
      sortable: true, width: "90px",
      render: (r) => r.total_price != null ? <span className="font-medium">{r.total_price}{t("storage.priceUnit", lang)}</span> : "-",
    },
    {
      key: "unit_price", header: t("storage.columns.unitPrice", lang),
      sortable: true, width: "100px",
      render: (r) => r.unit_price != null ? <span className="font-medium">{r.unit_price.toLocaleString()}</span> : "-",
    },
    {
      key: "area", header: t("storage.columns.area", lang),
      sortable: true, width: "80px",
      render: (r) => r.area != null ? `${r.area}㎡` : "-",
    },
    {
      key: "roomLayout", header: t("storage.columns.roomLayout", lang), width: "70px",
      render: (r) => {
        const parts = [r.room_count, r.hall_count, r.bathroom_count].filter((x) => x != null);
        return parts.length > 0 ? parts.join(t("storage.roomSep", lang)) : "-";
      },
    },
    { key: "floor_level", header: t("storage.columns.floorLevel", lang), width: "70px" },
    { key: "orientation", header: t("storage.columns.orientation", lang), width: "60px" },
    { key: "decoration", header: t("storage.columns.decoration", lang), width: "60px" },
    { key: "status", header: t("storage.columns.status", lang), width: "60px" },
  ];

  return (
    <div className="h-full flex flex-col gap-8">

      {/* 筛选栏 */}
      <div
        className="shrink-0 rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] px-4 py-3 border border-[var(--color-border-light)]"
        style={{ boxShadow: "var(--elevation-1)" }}
      >
        {/* 第一行：区县、装修、朝向、户型、操作 */}
        <div className="flex items-center gap-3 flex-wrap">
          <Select
            label={t("storage.district", lang)}
            value={filters.district_id != null ? String(filters.district_id) : ""}
            onChange={(e) => updateFilter("district_id", e.target.value ? Number(e.target.value) : undefined)}
            options={districtOpts}
          />
          <Select
            label={t("storage.decoration", lang)}
            value={filters.decoration ?? ""}
            onChange={(e) => updateFilter("decoration", e.target.value || undefined)}
            options={decorationOpts}
          />
          <Select
            label={t("storage.orientation", lang)}
            value={filters.orientation ?? ""}
            onChange={(e) => updateFilter("orientation", e.target.value || undefined)}
            options={orientationOpts}
          />
          <Select
            label={t("storage.roomCount", lang)}
            value={filters.room_count != null ? String(filters.room_count) : ""}
            onChange={(e) => updateFilter("room_count", e.target.value ? Number(e.target.value) : undefined)}
            options={roomOpts}
          />
          <Select
            label={lang === "zh" ? "类型" : "Type"}
            value={filters.listing_type ?? ""}
            onChange={(e) => updateFilter("listing_type", e.target.value || undefined)}
            options={[
              { value: "", label: LISTING_TYPE_OPTS[lang][""] },
              { value: "regular", label: LISTING_TYPE_OPTS[lang].regular },
              { value: "court_auction", label: LISTING_TYPE_OPTS[lang].court_auction },
            ]}
          />
          <Input
            label={t("storage.minUnitPrice", lang)} placeholder="0" className="w-28"
            value={filters.min_unit_price != null ? String(filters.min_unit_price) : ""}
            onChange={(e) => updateFilter("min_unit_price", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <Input
            label={t("storage.maxUnitPrice", lang)} placeholder={t("storage.unlimited", lang)} className="w-28"
            value={filters.max_unit_price != null ? String(filters.max_unit_price) : ""}
            onChange={(e) => updateFilter("max_unit_price", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <div className="flex gap-1 ml-auto">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleSortDir}
              title={sortDir === "desc" ? (lang === "zh" ? "当前: 降序 — 点击切换升序" : "Descending — click to switch") : (lang === "zh" ? "当前: 升序 — 点击切换降序" : "Ascending — click to switch")}
            >
              <ArrowUpDown size={14} />
              {sortDir === "desc" ? "↓" : "↑"}
            </Button>
            <Button variant="ghost" size="sm" onClick={handleReset}>
              <RotateCcw size={14} /> {t("storage.reset", lang)}
            </Button>
            <Button variant="ghost" size="sm" onClick={reload}>
              <RefreshCw size={14} /> {t("storage.refresh", lang)}
            </Button>
          </div>
        </div>
        {/* 第二行：总价、面积、搜索 */}
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          <Input
            label={t("storage.minPrice", lang)} placeholder="0" className="w-24"
            value={filters.min_price != null ? String(filters.min_price) : ""}
            onChange={(e) => updateFilter("min_price", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <Input
            label={t("storage.maxPrice", lang)} placeholder={t("storage.unlimited", lang)} className="w-24"
            value={filters.max_price != null ? String(filters.max_price) : ""}
            onChange={(e) => updateFilter("max_price", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <Input
            label={t("storage.minArea", lang)} placeholder="0" className="w-24"
            value={filters.min_area != null ? String(filters.min_area) : ""}
            onChange={(e) => updateFilter("min_area", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <Input
            label={t("storage.maxArea", lang)} placeholder={t("storage.unlimited", lang)} className="w-24"
            value={filters.max_area != null ? String(filters.max_area) : ""}
            onChange={(e) => updateFilter("max_area", e.target.value ? Number(e.target.value) : undefined)}
            type="number"
          />
          <Input
            label={t("storage.keyword", lang)} className="w-32"
            value={filters.keyword ?? ""}
            onChange={(e) => updateFilter("keyword", e.target.value || undefined)}
            placeholder={t("storage.keywordPlaceholder", lang)}
          />
        </div>
      </div>

      {/* 表格 */}
      <div
        className="flex-1 min-h-0 rounded-[var(--radius-lg)] bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border-light)] overflow-hidden"
        style={{ boxShadow: "var(--elevation-1)" }}
      >
        <Table
          columns={columns}
          data={data}
          rowKey={(r) => r.id}
          loading={loading}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
          page={filters.page ?? 1}
          pageSize={filters.page_size ?? 30}
          total={total}
          onPageChange={setPage}
          emptyText={t("storage.noData", lang)}
        />
      </div>
    </div>
  );
}
