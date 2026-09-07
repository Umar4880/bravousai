"use client";

import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface DataChartRendererProps {
  content: string;
}

const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#a4de6c", "#d0ed57"];

export function DataChartRenderer({ content }: DataChartRendererProps) {
  const chartData = useMemo(() => {
    try {
      const parsed = JSON.parse(content);
      
      // Expected format:
      // {
      //   "type": "bar" | "line" | "pie",
      //   "labels": ["A", "B", "C"],
      //   "datasets": [
      //     { "name": "Series 1", "data": [1, 2, 3] },
      //     { "name": "Series 2", "data": [4, 5, 6] }
      //   ]
      // }
      
      const type = parsed.type || "bar";
      const labels = parsed.labels || [];
      const datasets = parsed.datasets || [];
      
      const data = labels.map((label: string, index: number) => {
        const item: any = { name: label };
        datasets.forEach((ds: any) => {
          item[ds.name] = ds.data[index];
        });
        return item;
      });
      
      return { type, data, datasets, labels };
    } catch (e) {
      console.error("Failed to parse chart data:", e);
      return null;
    }
  }, [content]);

  if (!chartData) {
    return (
      <div className="chart-error">
        <p>Failed to parse chart data.</p>
        <pre>{content}</pre>
      </div>
    );
  }

  const { type, data, datasets } = chartData;

  const renderChart = () => {
    if (type === "pie") {
      // For pie chart, usually there is only one dataset
      const pieData = data.map((item: any) => ({
        name: item.name,
        value: item[datasets[0]?.name] || 0,
      }));
      
      return (
        <PieChart>
          <Tooltip />
          <Legend />
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
          >
            {pieData.map((entry: any, index: number) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      );
    }

    if (type === "line") {
      return (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          {datasets.map((ds: any, index: number) => (
            <Line
              key={ds.name}
              type="monotone"
              dataKey={ds.name}
              stroke={COLORS[index % COLORS.length]}
              activeDot={{ r: 8 }}
            />
          ))}
        </LineChart>
      );
    }

    // Default to Bar chart
    return (
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Legend />
        {datasets.map((ds: any, index: number) => (
          <Bar key={ds.name} dataKey={ds.name} fill={COLORS[index % COLORS.length]} />
        ))}
      </BarChart>
    );
  };

  return (
    <div className="data-chart-container" style={{ width: "100%", height: 400, marginTop: "1rem", marginBottom: "1rem" }}>
      <ResponsiveContainer width="100%" height="100%">
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
}
