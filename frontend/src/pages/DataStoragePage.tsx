import { useState } from "react";
import { RotateCcw } from "lucide-react";
import Button from "../components/ui/Button";
import Select from "../components/ui/Select";
import Table, { type Column } from "../components/ui/Table";
import { useThemeStore } from "../stores/useThemeStore";
import { useListings } from "../hooks/useListings";
import { useDistricts } from "../hooks/useAnalytics";
import { t } from "../i18n";
import type { Listing } from "../types/common";

const DECORATION_OPTS = [
  { value: "", label: "全部" },
  { value: "毛坯", label: "毛坯" },
  { value: "简装", label: "简装" },
  { value: "精装", label: "精装" },
  { value: "豪装", label: "豪装" },
];

const ORIENTATION_OPTS = [
  { value: "", label: "全部" },
  { value: "南", label: "南" },
  { value: "北", label: "北" },
  { value: "南北", label: "南北" },
  { value: "东南", label: "东南" },
  { value: "西南", label: "西南" },
];

export default function DataStoragePage() {
  const { lang } = useThemeStore();
  const { districts } = useDistricts();
  const { data, total, loading, filters, updateFilter, updateFilters, setPage } = useListings();
  const [sortKey, setSortKey] = useState("last_updated_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const districtOpts = [
    { value: "", label: t("storage.allDistricts", lang) },
    ...districts.map((d) => ({ value: String(d.id), label: d.name })),
  ];

  const handleSort = (key: string, dir: "asc" | "desc") => {
    setSortKey(key);
    setSortDir(dir);
    updateFilters({ sort_by: key, order: dir } as any);
  };

  const handleReset = () => {
    setSortKey("last_updated_at");
    setSortDir("desc");
    updateFilters({
      district_id: undefined,
      min_price: undefined, max_price: undefined,
      min_area: undefined, max_area: undefined,
      room_count: undefined, decoration: undefined,
      orientation: undefined, keyword: undefined,
      sort_by: "last_updated_at", order: "desc",
    });
  };

  const columns: Column<Listing>[] = [
    { key: "external_id", header: t("storage.columns.id", lang), width: "100px" },
    {
      key: "title", header: t("storage.columns.title", lang), width: "200px",
      render: (r) => (
        <span className="truncate max-w-[200px] block" title={r.title ?? ""}>
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
      render: (r) => r.total_price != null ? `${r.total_price}万` : "-",
    },
    {
      key: "unit_price", header: t("storage.columns.unitPrice", lang),
      sortable: true, width: "100px",
      render: (r) => r.unit_price != null ? r.unit_price.toLocaleString() : "-",
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
        return parts.length > 0 ? parts.join("室") : "-";
      },
    },
    { key: "floor_level", header: t("storage.columns.floorLevel", lang), width: "70px" },
    { key: "orientation", header: t("storage.columns.orientation", lang), width: "60px" },
    { key: "decoration", header: t("storage.columns.decoration", lang), width: "60px" },
    {
      key: "listing_date", header: t("storage.columns.listingDate", lang),
      sortable: true, width: "100px",
      render: (r) => r.listing_date ?? "-",
    },
    { key: "status", header: t("storage.columns.status", lang), width: "60px" },
  ];

  return (
    <div className="h-full flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">{t("storage.title", lang)}</h1>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-end gap-3 rounded border border-[var(--color-accent)] p-3">
        <Select
          label={t("storage.district", lang)}
          value={filters.district_id != null ? String(filters.district_id) : ""}
          onChange={(e) => updateFilter("district_id", e.target.value ? Number(e.target.value) : undefined)}
          options={districtOpts}
        />
        <InputField
          label={t("storage.minPrice", lang)}
          value={filters.min_price != null ? String(filters.min_price) : ""}
          onChange={(v) => updateFilter("min_price", v ? Number(v) : undefined)}
          type="number"
        />
        <InputField
          label={t("storage.maxPrice", lang)}
          value={filters.max_price != null ? String(filters.max_price) : ""}
          onChange={(v) => updateFilter("max_price", v ? Number(v) : undefined)}
          type="number"
        />
        <InputField
          label={t("storage.minArea", lang)}
          value={filters.min_area != null ? String(filters.min_area) : ""}
          onChange={(v) => updateFilter("min_area", v ? Number(v) : undefined)}
          type="number"
        />
        <InputField
          label={t("storage.maxArea", lang)}
          value={filters.max_area != null ? String(filters.max_area) : ""}
          onChange={(v) => updateFilter("max_area", v ? Number(v) : undefined)}
          type="number"
        />
        <InputField
          label={t("storage.roomCount", lang)}
          value={filters.room_count != null ? String(filters.room_count) : ""}
          onChange={(v) => updateFilter("room_count", v ? Number(v) : undefined)}
          type="number"
          className="w-16"
        />
        <Select
          label={t("storage.decoration", lang)}
          value={filters.decoration ?? ""}
          onChange={(e) => updateFilter("decoration", e.target.value || undefined)}
          options={DECORATION_OPTS}
        />
        <Select
          label={t("storage.orientation", lang)}
          value={filters.orientation ?? ""}
          onChange={(e) => updateFilter("orientation", e.target.value || undefined)}
          options={ORIENTATION_OPTS}
        />
        <InputField
          label={t("storage.keyword", lang)}
          value={filters.keyword ?? ""}
          onChange={(v) => updateFilter("keyword", v || undefined)}
          placeholder="小区名/标题..."
        />
        <Button variant="ghost" size="sm" onClick={handleReset}>
          <RotateCcw size={14} /> {t("storage.reset", lang)}
        </Button>
      </div>

      {/* 表格 */}
      <div className="flex-1 min-h-0">
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

      <div className="text-xs opacity-40">
        {t("storage.totalRecords", lang, { total })}
      </div>
    </div>
  );
}

function InputField({
  label, value, onChange, type = "text", placeholder, className = "w-24",
}: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; className?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium opacity-60">{label}</label>
      <input
        type={type} value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`rounded border border-[var(--color-accent)] bg-[var(--color-bg)] px-2 py-1.5 text-sm ${className}`}
      />
    </div>
  );
}
