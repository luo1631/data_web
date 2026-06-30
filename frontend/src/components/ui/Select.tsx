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
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs font-medium opacity-60">{label}</label>}
      <select
        className={clsx(
          "rounded border border-[var(--color-accent)] bg-[var(--color-bg)] px-3 py-1.5 text-sm",
          "focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30",
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
