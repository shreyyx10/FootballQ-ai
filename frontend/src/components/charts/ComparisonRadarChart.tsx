"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { ComparisonRow } from "@/lib/api";
import type { Player } from "@/lib/schemas";

const RADAR_METRICS = [
  "goals",
  "assists",
  "xg",
  "xag",
  "progressive_carries_per90",
  "shot_creating_actions_per90",
  "tackles_per90",
  "pass_completion_pct",
];

const COLORS = ["#22C55E", "#38BDF8", "#FBBF24", "#F472B6", "#A78BFA"];

/**
 * Renders a radar chart comparing players across a curated set of metrics.
 * Each metric is independently scaled to 0-100 across the compared players
 * so metrics with very different ranges (e.g. goals vs pass completion %)
 * remain visually comparable. The underlying raw values are shown in the
 * comparison table elsewhere on the page.
 */
export function ComparisonRadarChart({
  players,
  comparisonTable,
}: {
  players: Player[];
  comparisonTable: ComparisonRow[];
}) {
  const rowsByMetric = new Map(comparisonTable.map((row) => [row.metric, row]));

  const data = RADAR_METRICS.map((metric) => {
    const row = rowsByMetric.get(metric);
    const label = row?.label ?? metric;
    const values = players.map((p) => {
      const v = row?.[p.player_id];
      return typeof v === "number" ? v : 0;
    });
    const max = Math.max(...values, 0.0001);

    const entry: Record<string, string | number> = { metric: label };
    players.forEach((p, i) => {
      entry[p.player_name] = max > 0 ? Math.round((values[i] / max) * 100) : 0;
    });
    return entry;
  });

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#1E293B" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: "#94A3B8", fontSize: 11 }}
          />
          {players.map((p, i) => (
            <Radar
              key={p.player_id}
              name={p.player_name}
              dataKey={p.player_name}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.18}
              strokeWidth={2}
            />
          ))}
          <Legend
            wrapperStyle={{ fontSize: 12, color: "#94A3B8" }}
          />
          <Tooltip
            contentStyle={{
              background: "#0B1120",
              border: "1px solid #1E293B",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#E5E7EB" }}
          />
        </RadarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-center text-xs text-foreground-subtle">
        Each axis is scaled relative to the highest value among the compared
        players for visual comparison. See the table below for exact figures.
      </p>
    </div>
  );
}
