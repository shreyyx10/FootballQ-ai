"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SimilarPlayerResult } from "@/lib/api";

export function SimilarityBarChart({ results }: { results: SimilarPlayerResult[] }) {
  const data = results.map((r) => ({
    name: r.player.player_name,
    score: r.similarity_score,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 24, right: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fill: "#94A3B8", fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            tick={{ fill: "#E5E7EB", fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              background: "#0B1120",
              border: "1px solid #1E293B",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#E5E7EB" }}
            formatter={(value: number) => [`${value}/100`, "Similarity"]}
          />
          <Bar dataKey="score" fill="#22C55E" radius={[0, 4, 4, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
