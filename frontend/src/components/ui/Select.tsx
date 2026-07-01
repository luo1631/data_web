import { type SelectHTMLAttributes } from "react";
import clsx from "clsx";

interface Option {
  value: string;
  label: string;
}

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  options: Option[];
  placeholder?: string;
  label?: string;
}

export default function Select({
  options,
  placeholder,
  label,
  className,
  ...rest
}: Props) {
  return (
    <div className="flex items-center gap-1.5">
      {label && (
        <label className="text-xs font-medium text-[var(--color-text-secondary)] whitespace-nowrap">
          {label}
        </label>
      )}
      <select
        className={clsx(
          "w-full rounded-[var(--radius-xs)] border border-[var(--color-border)]",
          "bg-[var(--color-surface)] text-[var(--color-text-primary)]",
          "px-2.5 py-1.5 text-sm",
          "hover:border-[var(--color-brand)]/50",
          "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand)]/30 focus:border-[var(--color-brand)]",
          "disabled:opacity-40 disabled:bg-[var(--color-accent-bg)]",
          "transition-all duration-[var(--duration-fast)]",
          className,
        )}
        {...rest}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
