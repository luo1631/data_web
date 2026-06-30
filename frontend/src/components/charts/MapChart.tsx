// ECharts 封装 — 重庆地图组件
// 数据格式: [{name: "渝北区", value: 14865}, ...]
// GeoJSON 从 /chongqing.json 加载并注册到 ECharts

import { useState, useEffect } from "react";
import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import { useThemeStore } from "../../stores/useThemeStore";
import Spinner from "../ui/Spinner";

interface Props {
  title?: string;
  data: { name: string; value: number }[];
  height?: number;
}

const MAP_NAME = "chongqing";

export default function MapChart({ title, data, height = 500 }: Props) {
  const { theme } = useThemeStore();
  const isDark = theme === "dark";
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
        if (!cancelled) setGeoLoaded(true); // 即使失败也显示，去掉 spinner
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

  // 计算 max 用于颜色映射（min 固定为 0 以增强对比度）
  const maxVal = Math.max(...data.map((d) => d.value), 1);

  const option = {
    title: title ? {
      text: title, left: "center",
      textStyle: { fontSize: 14, color: isDark ? "#e0e0e0" : "#333" },
    } : undefined,
    tooltip: {
      trigger: "item" as const,
      formatter: (p: any) => {
        const v = p.value;
        return `${p.name}<br/>均价: ${v != null ? v.toLocaleString() : "-"} 元/㎡`;
      },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      left: 10,
      bottom: 20,
      text: ["高", "低"],
      inRange: {
        color: isDark
          ? ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#e94560"]
          : ["#e8f5e9", "#c8e6c9", "#81c784", "#4caf50", "#1b5e20"],
      },
      calculable: true,
      textStyle: { color: isDark ? "#aaa" : "#666" },
    },
    series: [{
      type: "map" as const,
      map: MAP_NAME,
      roam: true,
      zoom: 1.15,
      center: [107.05, 30.05],           // 重庆地理中心
      label: {
        show: true,
        fontSize: 8,
        color: isDark ? "#ccc" : "#333",
      },
      emphasis: {
        label: { show: true, fontSize: 11, fontWeight: "bold" },
        itemStyle: { areaColor: isDark ? "#533483" : "#ffd54f" },
      },
      itemStyle: {
        borderColor: isDark ? "#444" : "#fff",
        borderWidth: 1,
      },
      data: data.map((d) => ({
        name: d.name,
        value: d.value,
      })),
    }],
    backgroundColor: "transparent",
  };

  return <ReactECharts option={option} style={{ height }} />;
}
