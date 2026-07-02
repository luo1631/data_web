// ECharts 封装 — 散点图组件

import ReactECharts from "echarts-for-react";
import { useThemeStore } from "../../stores/useThemeStore";

interface Props {
  title?: string;
  data: { x: number; y: number; cluster_id: number }[];
  clusters?: { id: number; label: string }[];
  height?: number;
}

// Shopify 衍生色系
const CLUSTER_COLORS = ["#1e2c31", "#3d5a62", "#6b838a", "#9dabad", "#bdbdca"];

export default function ScatterChart({ title, data, clusters = [], height = 350 }: Props) {
  const resolved = useThemeStore((s) => s.resolved);
  const isDark = resolved === "dark";

  const clusterMap = new Map(clusters.map((c) => [c.id, { name: c.label, data: [] as number[][] }]));

  for (const pt of data) {
    if (!clusterMap.has(pt.cluster_id)) {
      clusterMap.set(pt.cluster_id, { name: `聚类${pt.cluster_id}`, data: [] });
    }
    clusterMap.get(pt.cluster_id)!.data.push([pt.x, pt.y]);
  }

  const option = {
    title: title ? { text: title, left: "center", textStyle: { fontSize: 13, color: isDark ? "#e0e0e0" : "#333" } } : undefined,
    tooltip: { trigger: "item" as const, formatter: (p: any) => `${p.seriesName}<br/>(${p.value[0].toFixed(2)}, ${p.value[1].toFixed(2)})` },
    legend: { bottom: 0, textStyle: { color: isDark ? "#aaa" : "#666", fontSize: 10 } },
    grid: { left: 15, right: 25, top: title ? 30 : 8, bottom: 32, containLabel: true },
    xAxis: { type: "value" as const, axisLabel: { fontSize: 10, color: isDark ? "#999" : "#666" } },
    yAxis: { type: "value" as const, axisLabel: { fontSize: 10, color: isDark ? "#999" : "#666" } },
    series: Array.from(clusterMap.entries()).map(([_id, s], i) => ({
      name: s.name,
      type: "scatter" as const,
      data: s.data,
      symbolSize: 4,
      itemStyle: { color: CLUSTER_COLORS[i % CLUSTER_COLORS.length], opacity: 0.6 },
    })),
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height: height > 0 ? height : "100%" }} />;
}
