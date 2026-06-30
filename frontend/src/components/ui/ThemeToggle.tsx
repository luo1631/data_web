import { Sun, Moon } from "lucide-react";
import { useThemeStore } from "../../stores/useThemeStore";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore();
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="p-2 rounded hover:bg-white/10 transition-colors"
      title={theme === "light" ? "切换暗色主题" : "切换亮色主题"}
    >
      {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
    </button>
  );
}
