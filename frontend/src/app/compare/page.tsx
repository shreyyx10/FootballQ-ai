"use client";

import { useState } from "react";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Loading";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlayerSelect } from "@/components/football/PlayerSelect";
import { ComparisonRadarChart } from "@/components/charts/ComparisonRadarChart";
import { comparePlayers } from "@/lib/api";
import type { ComparisonResponse } from "@/lib/api";
import { comparePlayersSchema } from "@/lib/schemas";
import { formatNumber } from "@/lib/utils";

export default function ComparePage() {
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [result, setResult] = useState<ComparisonResponse | null>(null);

  async function handleCompare() {
    const parsed = comparePlayersSchema.safeParse({ player_ids: selected });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid selection.");
      return;
    }

    setValidationError(null);
    setError(null);
    setLoading(true);
    setResult(null);

    const res = await comparePlayers(parsed.data);
    setLoading(false);

    if (res.ok) {
      setResult(res.data);
    } else {
      setError(res.error);
    }
  }

  return (
    <Container className="py-12 sm:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <Badge tone="accent" className="mb-3">
          Comparison Agent
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">
          Compare players
        </h1>
        <p className="mt-3 text-foreground-muted">
          Select 2-5 players to compare across goals, expected output,
          progression, and defensive metrics. Differences are highlighted and
          explained with a radar chart and a written summary.
        </p>
      </div>

      <Card className="mx-auto mt-8 max-w-3xl">
        <PlayerSelect
          label="Players to compare"
          value={selected}
          onChange={setSelected}
          maxSelected={5}
          helpText="Choose between 2 and 5 players."
        />
        {validationError && (
          <p className="mt-2 text-sm text-danger">{validationError}</p>
        )}
        <Button
          onClick={handleCompare}
          disabled={loading || selected.length < 2}
          className="mt-4"
        >
          {loading ? "Comparing..." : "Compare players"}
        </Button>
      </Card>

      <div className="mx-auto mt-10 max-w-5xl space-y-6">
        {loading && <LoadingState label="Building comparison..." />}
        {error && <ErrorState message={error} />}

        {result && (
          <>
            <Card>
              <CardHeader title="Summary" />
              <p className="text-sm leading-7 text-foreground">{result.summary}</p>
            </Card>

            <Card>
              <CardHeader
                title="Radar overview"
                description="Each axis is scaled relative to the highest value among the compared players."
              />
              <ComparisonRadarChart players={result.players} comparisonTable={result.comparison_table} />
            </Card>

            <Card>
              <CardHeader title="Comparison table" />
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-foreground-muted">
                      <th className="py-2 pr-4 font-medium">Metric</th>
                      {result.players.map((p) => (
                        <th key={p.player_id} className="py-2 pr-4 font-medium">
                          {p.player_name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparison_table.map((row) => (
                      <tr key={row.metric} className="border-b border-border/50">
                        <td className="py-2 pr-4 font-medium text-foreground">{row.label}</td>
                        {result.players.map((p) => {
                          const value = row[p.player_id];
                          const isLeader = row.leader === p.player_id;
                          return (
                            <td
                              key={p.player_id}
                              className={
                                isLeader
                                  ? "py-2 pr-4 font-semibold text-accent"
                                  : "py-2 pr-4 text-foreground-muted"
                              }
                            >
                              {typeof value === "number" ? formatNumber(value, 2) : "-"}
                              {isLeader && <span className="ml-1">&#9650;</span>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="grid gap-6 sm:grid-cols-2">
              <Card>
                <CardHeader title="Strengths" description="Metrics where each player leads the group" />
                <div className="space-y-4">
                  {result.strengths.map((s) => (
                    <div key={s.player_id}>
                      <p className="text-sm font-semibold text-foreground">{s.player_name}</p>
                      {s.leading_metrics.length > 0 ? (
                        <ul className="mt-1 flex flex-wrap gap-1.5">
                          {s.leading_metrics.map((m) => (
                            <li key={m}>
                              <Badge tone="accent">{m}</Badge>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1 text-xs text-foreground-subtle">
                          No standout leading metrics in this group.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <CardHeader title="Areas to develop" description="Metrics where each player trails the group" />
                <div className="space-y-4">
                  {result.weaknesses.map((w) => (
                    <div key={w.player_id}>
                      <p className="text-sm font-semibold text-foreground">{w.player_name}</p>
                      {w.trailing_metrics.length > 0 ? (
                        <ul className="mt-1 flex flex-wrap gap-1.5">
                          {w.trailing_metrics.map((m) => (
                            <li key={m}>
                              <Badge tone="warning">{m}</Badge>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1 text-xs text-foreground-subtle">
                          No significant trailing metrics in this group.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </>
        )}
      </div>
    </Container>
  );
}
