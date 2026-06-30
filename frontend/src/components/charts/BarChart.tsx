// ECharts 封装 — 柱状图组件

import ReactECharts from "echarts-for-react";
import { useThemeStore } from "../../stores/useThemeStore";

interface Props {
  title?: string;
  xData: string[];
  series: { name: string; data: number[]; color?: string }[];
  height?: number;
  horizontal?: boolean;
  stacked?: boolean;
}

export default function BarChart({ title, xData, series, height = 300, horizontal = false, stacked = false }: Props) {
  const { theme } = useThemeStore();
  const isDark = theme === "dark";

  const option = {
    title: title ? { text: title, left: "center", textStyle: { fontSize: 13, color: isDark ? "#e0e0e0" : "#333" } } : undefined,
    tooltip: { trigger: "axis" as const },
    legend: series.length > 1 ? { bottom: 0, textStyle: { color: isDark ? "#aaa" : "#666", fontSize: 11 } } : undefined,
    grid: { left: 10, right: 20, top: title ? 35 : 10, bottom: series.length > 1 ? 30 : 5, containLabel: true },
    xAxis: horizontal ? {
      type: "value" as const,
      axisLabel: { color: isDark ? "#999" : "#666" },
    } : {
      type: "category" as const,
      data: xData,
      axisLabel: { rotate: xData.length > 8 ? 30 : 0, fontSize: 10, color: isDark ? "#999" : "#666" },
    },
    yAxis: horizontal ? {
      type: "category" as const,
      data: xData,
      axisLabel: { fontSize: 10, color: isDark ? "#999" : "#666" },
    } : {
      type: "value" as const,
      axisLabel: { color: isDark ? "#999" : "#666" },
    },
    series: series.map((s) => ({
      name: s.name,
      type: "bar" as const,
      data: s.data,
      itemStyle: { color: s.color },
      stack: stacked ? "total" : undefined,
    })),
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height }} />;
}
