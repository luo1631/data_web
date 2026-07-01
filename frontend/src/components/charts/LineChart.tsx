// ECharts 封装 — 折线图组件

import ReactECharts from "echarts-for-react";
import { useThemeStore } from "../../stores/useThemeStore";

interface Props {
  title?: string;
  xData: string[];
  series: { name: string; data: (number | undefined)[]; color?: string; lineStyle?: "solid" | "dashed" | "dotted" }[];
  height?: number;
  smooth?: boolean;
}

export default function LineChart({ title, xData, series, height = 300, smooth = true }: Props) {
  const resolved = useThemeStore((s) => s.resolved);
  const isDark = resolved === "dark";

  const option = {
    title: title ? { text: title, left: "center", textStyle: { fontSize: 13, color: isDark ? "#e0e0e0" : "#333" } } : undefined,
    tooltip: { trigger: "axis" as const },
    legend: series.length > 1 ? { bottom: 0, textStyle: { color: isDark ? "#aaa" : "#666", fontSize: 11 } } : undefined,
    grid: { left: 10, right: 20, top: title ? 35 : 10, bottom: series.length > 1 ? 30 : 5, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: xData,
      axisLabel: { rotate: xData.length > 12 ? 30 : 0, fontSize: 10, color: isDark ? "#999" : "#666" },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { color: isDark ? "#999" : "#666" },
    },
    series: series.map((s) => ({
      name: s.name,
      type: "line" as const,
      data: s.data,
      smooth,
      connectNulls: true,
      itemStyle: { color: s.color },
      lineStyle: { width: 2, type: s.lineStyle ?? "solid" },
    })),
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height }} />;
}
