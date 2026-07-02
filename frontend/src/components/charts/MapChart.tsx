// ECharts 封装 — 重庆地图组件 (增强版)
// 数据格式: [{name: "渝北区", value: 14865, count: 34}, ...]

import { useState, useEffect } from "react";
import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import { useThemeStore } from "../../stores/useThemeStore";
import Spinner from "../ui/Spinner";

interface Props {
  title?: string;
  data: { name: string; value: number; count?: number }[];
  height?: number;
  lang?: string;
}

const MAP_NAME = "chongqing";

export default function MapChart({ title, data, height = 500, lang = "zh" }: Props) {
  const resolved = useThemeStore((s) => s.resolved);
  const isDark = resolved === "dark";
  const [geoLoaded, setGeoLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch("/chongqing.json");
        const geoJson = await resp.json();
        if (!cancelled) {
          echarts.registerMap(MAP_NAME, geoJson as any);
          setGeoLoaded(true);
        }
      } catch {
        if (!cancelled) setGeoLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!geoLoaded) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <Spinner />
      </div>
    );
  }

  const maxVal = Math.max(...data.map((d) => d.value), 1);
  const avgLabel = lang === "zh" ? "均价" : "Avg";
  const unit = lang === "zh" ? "元/㎡" : "¥/㎡";
  const countLabel = lang === "zh" ? "在售" : "Active";
  const highLabel = lang === "zh" ? "高" : "High";
  const lowLabel = lang === "zh" ? "低" : "Low";

  // 亮色渐变：cream → 灰青 → 中青 → 深青 (from canvas to brand)
  const lightColors = ["#f5f2eb", "#9dadb2", "#6b838a", "#3d5a62", "#1e2c31"];
  // 暗色渐变：黑 → 深青 → 中青 → 灰青 → 冷灰
  const darkColors = ["#0a0a0a", "#1e2c31", "#3d5a62", "#6b838a", "#9dadb2"];

  const option = {
    title: title ? {
      text: title, left: "center", top: 6,
      textStyle: { fontSize: 15, fontWeight: "bold", color: isDark ? "#e0e0e0" : "#333" },
    } : undefined,
    tooltip: {
      trigger: "item" as const,
      backgroundColor: isDark ? "rgba(30,30,40,0.94)" : "rgba(255,255,255,0.94)",
      borderColor: isDark ? "#555" : "#ddd",
      textStyle: { fontSize: 13, color: isDark ? "#eee" : "#333" },
      formatter: (p: any) => {
        const v = p.value;
        const cnt = p.data?.count;
        if (v == null || v === 0) return `<b>${p.name}</b><br/>${avgLabel}: --`;
        let html = `<b>${p.name}</b><br/>${avgLabel}: <b>${v.toLocaleString()}</b> ${unit}`;
        if (cnt != null) html += `<br/>${countLabel}: ${cnt} ${lang === "zh" ? "套" : "units"}`;
        return html;
      },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      left: 12,
      bottom: 24,
      text: [highLabel, lowLabel],
      inRange: { color: isDark ? darkColors : lightColors },
      calculable: true,
      orient: "horizontal" as const,
      itemWidth: 14,
      itemHeight: 140,
      textStyle: {
        color: isDark ? "#aaa" : "#666",
        fontSize: 11,
      },
      handleStyle: { borderColor: isDark ? "#888" : "#999" },
    },
    series: [{
      type: "map" as const,
      map: MAP_NAME,
      roam: true,
      zoom: 1.18,
      center: [107.15, 30.2],
      scaleLimit: { min: 1, max: 4 },
      label: {
        show: true,
        fontSize: 9,
        color: isDark ? "#ccc" : "#333",
        textBorderColor: isDark ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.6)",
        textBorderWidth: 2,
      },
      emphasis: {
        label: { show: true, fontSize: 13, fontWeight: "bold", color: "#fff", textBorderColor: "#000", textBorderWidth: 1 },
        itemStyle: { areaColor: isDark ? "#6b838a" : "#3d5a62", shadowBlur: 12, shadowColor: "rgba(0,0,0,0.3)" },
      },
      select: {
        label: { show: true, fontSize: 12, fontWeight: "bold" },
        itemStyle: { areaColor: isDark ? "#6b838a" : "#3d5a62" },
      },
      itemStyle: {
        borderColor: isDark ? "#555" : "#fff",
        borderWidth: 1.2,
        borderRadius: 2,
      },
      data: data.map((d) => ({
        name: d.name,
        value: d.value,
        count: (d as any).count,
      })),
    }],
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height: height > 0 ? height : "100%" }} />;
}
