import { type InputHTMLAttributes } from "react";
import clsx from "clsx";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({ label, className, ...rest }: Props) {
  return (
    <div className="flex items-center gap-1.5">
      {label && (
        <label className="text-xs font-medium text-[var(--color-text-secondary)] whitespace-nowrap">
          {label}
        </label>
      )}
      <input
        className={clsx(
          "w-full rounded-[var(--radius-xs)] border border-[var(--color-border)]",
          "bg-[var(--color-surface)] text-[var(--color-text-primary)]",
          "px-2.5 py-1.5 text-sm",
          "placeholder-[var(--color-text-tertiary)]",
          "hover:border-[var(--color-brand)]/50",
          "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand)]/30 focus:border-[var(--color-brand)]",
          "transition-all duration-[var(--duration-fast)]",
          className,
        )}
        {...rest}
      />
    </div>
  );
}
