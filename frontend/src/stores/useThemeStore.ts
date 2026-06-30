import { create } from "zustand";

type Theme = "light" | "dark";
type Lang = "zh" | "en";

interface ThemeState {
  theme: Theme;
  lang: Lang;
  toggleTheme: () => void;
  toggleLang: () => void;
}

const applyTheme = (theme: Theme) => {
  document.documentElement.classList.toggle("dark", theme === "dark");
};

const getInitialTheme = (): Theme => {
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const getInitialLang = (): Lang => {
  return (localStorage.getItem("lang") as Lang) || "zh";
};

const initialTheme = getInitialTheme();
applyTheme(initialTheme);

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: initialTheme,
  lang: getInitialLang(),

  toggleTheme: () => {
    const next = get().theme === "light" ? "dark" : "light";
    localStorage.setItem("theme", next);
    applyTheme(next);
    set({ theme: next });
  },

  toggleLang: () => {
    const next = get().lang === "zh" ? "en" : "zh";
    localStorage.setItem("lang", next);
    set({ lang: next });
  },
}));
