import { useState } from "react";
import { Outlet } from "react-router-dom";
import { X } from "lucide-react";
import Navbar from "./Navbar";

export default function AppLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="flex flex-col h-full">
      <Navbar onOpenSettings={() => setSettingsOpen(true)} />

      <div className="flex flex-1 overflow-hidden relative">
        {/* 主内容区 */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>

        {/* 设置抽屉（左侧滑出） */}
        {settingsOpen && (
          <div className="fixed inset-0 z-40">
            {/* 遮罩 */}
            <div
              className="absolute inset-0 bg-black/30"
              onClick={() => setSettingsOpen(false)}
            />
            {/* 抽屉面板 */}
            <aside className="absolute left-0 top-0 h-full w-[50vw] min-w-[360px] p-6 shadow-xl overflow-y-auto bg-[var(--color-primary-bg)] text-[var(--color-text)]">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">设置</h2>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(false)}
                  className="p-1 rounded hover:opacity-70"
                  title="关闭设置"
                  aria-label="关闭设置"
                >
                  <X size={20} />
                </button>
              </div>
              <p className="text-sm opacity-60">设置面板（后续实现）</p>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
