import clsx from "clsx";

interface Props {
  label: string;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}

export default function Chip({ label, active = false, onClick, className }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "px-3 py-1 rounded-[var(--radius-pill)] text-xs font-medium",
        "transition-all duration-[var(--duration-fast)] ease-[var(--ease-out)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand)]/30",
        active
          ? "bg-[var(--color-brand)] text-[var(--color-text-inverse)] border border-[var(--color-brand)]"
          : "bg-[var(--color-accent-bg)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-border)] hover:text-[var(--color-text-primary)]",
        className,
      )}
    >
      {label}
    </button>
  );
}
