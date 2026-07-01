import clsx from "clsx";

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (row: T, rowIndex: number) => React.ReactNode;
  width?: string;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  onSort?: (key: string, dir: "asc" | "desc") => void;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  emptyText?: string;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function Table<T>({
  columns, data, rowKey, loading, onRowClick, onSort,
  sortKey, sortDir, emptyText = "暂无数据",
  page, pageSize, total, onPageChange,
}: Props<T>) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const items = data ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 表体 — 可滚动（含 sticky 表头） */}
      <div className="flex-1 min-h-0 overflow-auto">
        <table className="w-full text-sm" style={{ minWidth: columns.reduce((s, c) => s + (c.width ? parseInt(c.width) : 80), 0) }}>
          <thead className="sticky top-0 z-10">
            <tr className="bg-[var(--color-brand)]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx(
                    "px-3 py-2 text-left font-medium text-[var(--color-text-inverse)] whitespace-nowrap text-xs uppercase tracking-wider",
                    col.sortable && "cursor-pointer select-none hover:bg-[var(--color-brand-hover)] transition-colors",
                  )}
                  style={col.width ? { width: col.width } : undefined}
                  onClick={() => {
                    if (!col.sortable || !onSort) return;
                    const dir = sortKey === col.key && sortDir === "asc" ? "desc" : "asc";
                    onSort(col.key, dir);
                  }}
                >
                  <span className="flex items-center gap-1">
                    {col.header}
                    {col.sortable && sortKey === col.key && (
                      <span>{sortDir === "asc" ? "↑" : "↓"}</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-12 text-center text-[var(--color-text-secondary)]">
                  加载中...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-12 text-center text-[var(--color-text-secondary)]">
                  {emptyText}
                </td>
              </tr>
            ) : (
              items.map((row, idx) => (
                <tr
                  key={rowKey(row)}
                  className={clsx(
                    "border-t border-[var(--color-border-light)] transition-colors",
                    idx % 2 === 1 && "bg-[var(--color-accent-bg)]/40",
                    onRowClick && "cursor-pointer hover:bg-[var(--color-accent-bg)]/70",
                  )}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-3 py-2 whitespace-nowrap">
                      {col.render ? col.render(row, idx) : String((row as any)[col.key] ?? "-")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 分页器 — 固定在底部 */}
      {total > pageSize && (
        <div className="shrink-0 flex items-center justify-between px-3 py-2 border-t border-[var(--color-border-light)] text-xs text-[var(--color-text-secondary)]">
          <span>
            共 {total} 条，第 {page}/{totalPages} 页
          </span>
          <div className="flex gap-1">
            <PageBtn onClick={() => onPageChange(1)} disabled={page <= 1} label="«" />
            <PageBtn onClick={() => onPageChange(page - 1)} disabled={page <= 1} label="‹" />
            <PageBtn onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} label="›" />
            <PageBtn onClick={() => onPageChange(totalPages)} disabled={page >= totalPages} label="»" />
          </div>
        </div>
      )}

      {/* 小型分页器（总条数 ≤ 一页时显示） */}
      {total <= pageSize && total > 0 && (
        <div className="shrink-0 text-xs text-[var(--color-text-tertiary)] px-3 py-1.5 border-t border-[var(--color-border-light)] text-center">
          共 {total} 条
        </div>
      )}
    </div>
  );
}

function PageBtn({ onClick, disabled, label }: { onClick: () => void; disabled: boolean; label: string }) {
  return (
    <button
      type="button"
      className={clsx(
        "px-2.5 py-1 rounded-[var(--radius-sm)] border border-[var(--color-border)]",
        "hover:bg-[var(--color-accent-bg)] active:bg-[var(--color-brand)] active:text-[var(--color-text-inverse)]",
        "disabled:opacity-30 disabled:cursor-not-allowed",
        "transition-colors duration-[var(--duration-fast)]",
      )}
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
