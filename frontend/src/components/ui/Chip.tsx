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
        "px-3 py-1 rounded-full text-xs font-medium transition-colors border",
        active
          ? "bg-[var(--color-primary)] text-[var(--color-text-white)] border-[var(--color-primary)]"
          : "bg-transparent text-[var(--color-text)] border-[var(--color-accent)] hover:bg-[var(--color-accent)]",
        className,
      )}
    >
      {label}
    </button>
  );
}
