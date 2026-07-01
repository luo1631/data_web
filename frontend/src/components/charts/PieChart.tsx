// ECharts 封装 — 饼图组件

import ReactECharts from "echarts-for-react";
import { useThemeStore } from "../../stores/useThemeStore";

interface Props {
  title?: string;
  data: { name: string; value: number }[];
  height?: number;
  roseType?: boolean;
}

// Shopify 衍生色系: 深青 → 中青 → 灰青 → 冷灰 → 浅紫灰 → 暖灰 → 浅灰 → 中灰
const COLORS = ["#1e2c31", "#3d5a62", "#6b838a", "#9dabad", "#bdbdca", "#9797a2", "#d4d4d8", "#71717a"];

export default function PieChart({ title, data, height = 280, roseType = false }: Props) {
  const resolved = useThemeStore((s) => s.resolved);
  const isDark = resolved === "dark";

  const option = {
    title: title ? { text: title, left: "center", textStyle: { fontSize: 13, color: isDark ? "#e0e0e0" : "#333" } } : undefined,
    tooltip: { trigger: "item" as const },
    legend: { bottom: 0, textStyle: { color: isDark ? "#aaa" : "#666", fontSize: 10 } },
    series: [{
      type: "pie" as const,
      radius: roseType ? ["20%", "70%"] : "60%",
      center: ["50%", "48%"],
      roseType: roseType ? "area" as const : undefined,
      itemStyle: { borderRadius: 4, borderColor: isDark ? "#1a1a1d" : "#fff", borderWidth: 2 },
      label: { formatter: "{b}\n{d}%", fontSize: 10 },
      data,
      color: COLORS,
    }],
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height }} />;
}
