import { useState, useEffect, useRef } from "react";
import { Outlet } from "react-router-dom";
import { X, Monitor, Sun, Moon } from "lucide-react";
import Navbar from "./Navbar";
import Select from "../ui/Select";
import Input from "../ui/Input";
import { useThemeStore } from "../../stores/useThemeStore";
import { useSettingsStore } from "../../stores/useSettingsStore";

const PAGE_SIZE_OPTIONS = [
  { value: "20", label: "20 条/页" },
  { value: "30", label: "30 条/页" },
  { value: "50", label: "50 条/页" },
  { value: "100", label: "100 条/页" },
];

export default function AppLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="flex flex-col h-full">
      <Navbar onOpenSettings={() => setSettingsOpen(true)} />

      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>

      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

/* ── 设置抽屉（单 useEffect 状态机，无竞态） ── */
function SettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [visible, setVisible] = useState(false);   // DOM 是否挂载
  const [animating, setAnimating] = useState(false); // 动画是否播放中
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current != null) clearTimeout(timerRef.current);

    if (open) {
      setVisible(true);
      timerRef.current = window.setTimeout(() => setAnimating(true), 16);
    } else if (visible) {
      setAnimating(false);
      timerRef.current = window.setTimeout(() => setVisible(false), 300);
    }

    return () => { if (timerRef.current != null) clearTimeout(timerRef.current); };
  }, [open, visible]);

  const handleClose = () => onClose();

  if (!visible) return null;

  const overlayCls =
    "absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-300" +
    (animating ? " opacity-100" : " opacity-0");

  const drawerCls =
    "absolute right-0 top-0 h-full w-[380px] overflow-y-auto bg-[var(--color-surface)] text-[var(--color-text-primary)] border-l border-[var(--color-border)] transition-transform duration-300 ease-[var(--ease-out)]" +
    (animating ? " translate-x-0" : " translate-x-full");

  return (
    <div className="fixed inset-0 z-40">
      <div className={overlayCls} onClick={handleClose} />
      <aside className={drawerCls} style={{ boxShadow: "var(--elevation-2)" }}>
        <SettingsContent onClose={handleClose} />
      </aside>
    </div>
  );
}

/* ── 设置内容 ── */
function SettingsContent({ onClose }: { onClose: () => void }) {
  const theme = useThemeStore((s) => s.theme);
  const lang = useThemeStore((s) => s.lang);
  const setTheme = useThemeStore((s) => s.setTheme);
  const setLang = useThemeStore((s) => s.setLang);

  const defaultMaxPages = useSettingsStore((s) => s.defaultMaxPages);
  const defaultPageSize = useSettingsStore((s) => s.defaultPageSize);
  const setDefaultMaxPages = useSettingsStore((s) => s.setDefaultMaxPages);
  const setDefaultPageSize = useSettingsStore((s) => s.setDefaultPageSize);

  const zh = lang === "zh";

  return (
    <>
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-light)]">
        <h2 className="text-lg font-semibold">{zh ? "设置" : "Settings"}</h2>
        <button
          type="button" onClick={onClose}
          className="p-1.5 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-bg)] hover:text-[var(--color-text-primary)] transition-colors"
          aria-label={zh ? "关闭" : "Close"}
        >
          <X size={18} />
        </button>
      </div>

      <div className="p-6 space-y-8">
        {/* 外观 */}
        <Section title={zh ? "外观" : "Appearance"}>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-2">
                {zh ? "主题模式" : "Theme"}
              </label>
              <div className="grid grid-cols-3 gap-2">
                {([
                  { value: "light" as const, icon: Sun, label: zh ? "亮色" : "Light" },
                  { value: "dark" as const, icon: Moon, label: zh ? "暗色" : "Dark" },
                  { value: "system" as const, icon: Monitor, label: zh ? "跟随系统" : "System" },
                ]).map(({ value, icon: Icon, label }) => (
                  <button
                    key={value} type="button"
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-[var(--radius-md)] border transition-all duration-[var(--duration-fast)] ${
                      theme === value
                        ? "border-[var(--color-brand)] bg-[var(--color-brand)]/10 text-[var(--color-brand)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
                    }`}
                    onClick={() => setTheme(value)}
                  >
                    <Icon size={20} />
                    <span className="text-xs">{label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--color-text-secondary)] block mb-2">
                {zh ? "语言" : "Language"}
              </label>
              <div className="flex gap-2">
                {[
                  { value: "zh" as const, label: "中文" },
                  { value: "en" as const, label: "English" },
                ].map(({ value, label }) => (
                  <button
                    key={value} type="button"
                    className={`px-4 py-2 rounded-[var(--radius-sm)] border text-sm font-medium transition-all duration-[var(--duration-fast)] ${
                      lang === value
                        ? "border-[var(--color-brand)] bg-[var(--color-brand)]/10 text-[var(--color-brand)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
                    }`}
                    onClick={() => setLang(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Section>

        {/* 数据获取 */}
        <Section title={zh ? "数据获取" : "Data Fetching"}>
          <Input
            label={zh ? "默认每区县页数" : "Default pages"}
            type="number" min={5} max={100} step={5}
            className="w-full"
            value={defaultMaxPages}
            onChange={(e) => setDefaultMaxPages(Number(e.target.value))}
          />
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1.5">
            {zh ? "每次开始爬取时自动填入该值" : "Auto-fills when starting a new crawl"}
          </p>
        </Section>

        {/* 数据显示 */}
        <Section title={zh ? "数据显示" : "Display"}>
          <Select
            label={zh ? "默认每页条数" : "Default rows"}
            value={String(defaultPageSize)}
            onChange={(e) => setDefaultPageSize(Number(e.target.value))}
            options={PAGE_SIZE_OPTIONS}
          />
        </Section>

        {/* 关于 */}
        <Section title={zh ? "关于" : "About"}>
          <div className="space-y-2 text-xs text-[var(--color-text-secondary)]">
            <AboutRow label="DataWeb" value="v0.1.0" />
            <AboutRow label={zh ? "技术栈" : "Stack"} value="React 19 + Vite 8 + Tailwind 4" />
            <AboutRow label="ECharts" value="v6" />
            <AboutRow label="Zustand" value="v5" />
            <AboutRow label={zh ? "后端 API" : "API"} value="/api/v1" />
          </div>
        </Section>
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-3">{title}</h3>
      {children}
    </div>
  );
}

function AboutRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[var(--color-text-tertiary)]">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
