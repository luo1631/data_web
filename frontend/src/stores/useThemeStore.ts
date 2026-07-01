import { create } from "zustand";
import { useEffect } from "react";

type ThemePref = "light" | "dark" | "system";
type Lang = "zh" | "en";

interface ThemeState {
  theme: ThemePref;           // 用户偏好
  resolved: "light" | "dark"; // 实际生效的主题
  lang: Lang;
  setTheme: (t: ThemePref) => void;
  setLang: (l: Lang) => void;
}

function resolveTheme(pref: ThemePref): "light" | "dark" {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref;
}

function applyDarkClass(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

const stored = (localStorage.getItem("theme") as ThemePref) || "system";
const storedLang = (localStorage.getItem("lang") as Lang) || "zh";

const initialResolved = resolveTheme(stored);
applyDarkClass(initialResolved === "dark");

export const useThemeStore = create<ThemeState>((set) => ({
  theme: stored,
  resolved: initialResolved,
  lang: storedLang,

  setTheme: (t) => {
    localStorage.setItem("theme", t);
    const r = resolveTheme(t);
    applyDarkClass(r === "dark");
    set({ theme: t, resolved: r });
  },

  setLang: (l) => {
    localStorage.setItem("lang", l);
    set({ lang: l });
  },
}));

/** 监听系统主题变化（仅在 theme === "system" 时生效） */
export function useSystemThemeListener() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const r = resolveTheme("system");
      applyDarkClass(r === "dark");
      useThemeStore.setState({ resolved: r });
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);
}
