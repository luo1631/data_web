import { NavLink } from "react-router-dom";
import { Settings, Globe, Sun, Moon, Download, Database, BarChart3 } from "lucide-react";
import { useThemeStore } from "../../stores/useThemeStore";

const navItems = [
  { to: "/crawl", label: "数据爬取", icon: Download },
  { to: "/storage", label: "数据存储", icon: Database },
  { to: "/analysis", label: "数据分析", icon: BarChart3 },
];

interface NavbarProps {
  onOpenSettings: () => void;
}

export default function Navbar({ onOpenSettings }: NavbarProps) {
  const { theme, lang, toggleTheme, toggleLang } = useThemeStore();

  return (
    <nav className="flex items-center justify-between h-14 px-4 border-b shrink-0 bg-[var(--color-primary)] text-[var(--color-text-inverse)] border-[var(--color-accent)]">
      {/* 左侧：设置 */}
      <button
        type="button"
        onClick={onOpenSettings}
        className="p-2 rounded hover:opacity-80 transition-opacity"
        title="设置"
      >
        <Settings size={20} />
      </button>

      {/* 中间：导航 */}
      <div className="flex items-center gap-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-4 py-2 rounded text-sm font-medium transition-colors ${
                isActive ? "bg-white/20" : "hover:bg-white/10"
              }`
            }
          >
            <Icon size={16} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      {/* 右侧：语言 + 主题切换 */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleLang}
          className="flex items-center gap-1 px-2 py-1 rounded text-sm hover:bg-white/10 transition-colors"
        >
          <Globe size={16} />
          <span>{lang === "zh" ? "En" : "中"}</span>
        </button>
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded hover:bg-white/10 transition-colors"
          title={theme === "light" ? "切换暗色主题" : "切换亮色主题"}
        >
          {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </nav>
  );
}
