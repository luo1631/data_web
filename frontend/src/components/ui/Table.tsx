import clsx from "clsx";

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (row: T) => React.ReactNode;
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

  return (
    <div className="overflow-x-auto rounded border border-[var(--color-accent)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--color-accent)]/50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(
                  "px-3 py-2 text-left font-medium whitespace-nowrap",
                  col.sortable && "cursor-pointer select-none hover:opacity-70",
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
              <td colSpan={columns.length} className="px-3 py-12 text-center opacity-40">
                加载中...
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-12 text-center opacity-40">
                {emptyText}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={rowKey(row)}
                className={clsx(
                  "border-t border-[var(--color-accent)]/50 transition-colors",
                  onRowClick && "cursor-pointer hover:bg-[var(--color-accent)]/30",
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2 whitespace-nowrap">
                    {col.render ? col.render(row) : String((row as any)[col.key] ?? "-")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* 分页器 */}
      {total > pageSize && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--color-accent)] text-xs">
          <span className="opacity-60">
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
    </div>
  );
}

function PageBtn({ onClick, disabled, label }: { onClick: () => void; disabled: boolean; label: string }) {
  return (
    <button
      type="button"
      className="px-2 py-0.5 rounded border border-[var(--color-accent)] hover:bg-[var(--color-accent)] disabled:opacity-30 disabled:cursor-not-allowed"
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
