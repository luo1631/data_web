import { NavLink } from "react-router-dom";
import { Settings, Sun, Moon, SunMoon, Download, Database, BarChart3, Home } from "lucide-react";
import { useThemeStore } from "../../stores/useThemeStore";
import { t } from "../../i18n";

const NAV_KEYS: { to: string; key: string; icon: typeof Download }[] = [
  { to: "/crawl", key: "crawl", icon: Download },
  { to: "/storage", key: "storage", icon: Database },
  { to: "/analysis", key: "analysis", icon: BarChart3 },
];

const themeCycle: Record<string, { next: string; icon: typeof Sun; title: (l: string) => string }> = {
  light: {
    next: "dark",
    icon: Moon,
    title: (l) => l === "zh" ? "切换暗色主题" : "Switch to dark",
  },
  dark: {
    next: "system",
    icon: Sun,
    title: (l) => l === "zh" ? "跟随系统" : "Follow system",
  },
  system: {
    next: "light",
    icon: SunMoon,
    title: (l) => l === "zh" ? "切换亮色主题" : "Switch to light",
  },
};

interface NavbarProps {
  onOpenSettings: () => void;
}

export default function Navbar({ onOpenSettings }: NavbarProps) {
  const theme = useThemeStore((s) => s.theme);
  const lang = useThemeStore((s) => s.lang);
  const setTheme = useThemeStore((s) => s.setTheme);
  const setLang = useThemeStore((s) => s.setLang);

  const cycle = themeCycle[theme];
  const ThemeIcon = cycle.icon;

  return (
    <nav className="grid grid-cols-3 items-center h-14 px-6 shrink-0 bg-[var(--color-surface)] border-b border-[var(--color-border)]" style={{ boxShadow: "var(--elevation-1)" }}>
      {/* 左侧: Logo */}
      <div className="flex items-center gap-2 text-[var(--color-brand)]">
        <Home size={20} strokeWidth={2} />
        <span className="text-base font-semibold tracking-tight">DataWeb</span>
      </div>

      {/* 中间: 导航链接 */}
      <div className="flex items-center justify-center gap-1">
        {NAV_KEYS.map(({ to, key, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3.5 py-1.5 rounded-[var(--radius-sm)] text-sm font-medium transition-all duration-[var(--duration-fast)] ease-[var(--ease-out)] ${
                isActive
                  ? "bg-[var(--color-brand)] text-[var(--color-text-inverse)]"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-bg)] hover:text-[var(--color-text-primary)]"
              }`
            }
          >
            <Icon size={16} />
            <span>{t(`nav.${key}`, lang)}</span>
          </NavLink>
        ))}
      </div>

      {/* 右侧: 语言 / 主题 / 设置 */}
      <div className="flex items-center justify-end gap-1">
        <button
          type="button"
          onClick={() => setLang(lang === "zh" ? "en" : "zh")}
          className="px-2.5 py-1.5 rounded-[var(--radius-sm)] text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-bg)] hover:text-[var(--color-text-primary)] transition-colors duration-[var(--duration-fast)]"
        >
          {lang === "zh" ? "En" : "Ch"}
        </button>
        <button
          type="button"
          onClick={() => setTheme(cycle.next as "light" | "dark" | "system")}
          className="p-2 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-bg)] hover:text-[var(--color-text-primary)] transition-colors duration-[var(--duration-fast)]"
          title={cycle.title(lang)}
        >
          <ThemeIcon size={17} />
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          className="p-2 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-bg)] hover:text-[var(--color-text-primary)] transition-colors duration-[var(--duration-fast)]"
          title={t("nav.settings", lang)}
        >
          <Settings size={17} />
        </button>
      </div>
    </nav>
  );
}
