import { Sun, Moon, SunMoon } from "lucide-react";
import { useThemeStore } from "../../stores/useThemeStore";

const icons = {
  light: Sun,
  dark: Moon,
  system: SunMoon,
} as const;

const nextMap = { light: "dark", dark: "system", system: "light" } as const;

export default function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const Icon = icons[theme];

  return (
    <button
      type="button"
      onClick={() => setTheme(nextMap[theme])}
      className="p-2 rounded hover:bg-white/10 transition-colors"
      title={
        theme === "light" ? "切换暗色主题"
        : theme === "dark" ? "跟随系统"
        : "切换亮色主题"
      }
    >
      <Icon size={18} />
    </button>
  );
}
