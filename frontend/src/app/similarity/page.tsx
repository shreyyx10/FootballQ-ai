"use client";

import { useState } from "react";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Loading";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlayerSelect } from "@/components/football/PlayerSelect";
import { PlayerCard } from "@/components/football/PlayerCard";
import { SimilarityBarChart } from "@/components/charts/SimilarityBarChart";
import { getSimilarity } from "@/lib/api";
import type { SimilarityResponse } from "@/lib/api";
import { similarityRequestSchema } from "@/lib/schemas";
import { formatNumber } from "@/lib/utils";

export default function SimilarityPage() {
  const [reference, setReference] = useState<string[]>([]);
  const [topN, setTopN] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [result, setResult] = useState<SimilarityResponse | null>(null);

  async function handleFind() {
    const parsed = similarityRequestSchema.safeParse({
      reference_player_id: reference[0],
      top_n: topN,
    });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Select a reference player.");
      return;
    }

    setValidationError(null);
    setError(null);
    setLoading(true);
    setResult(null);

    const res = await getSimilarity(parsed.data);
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
          Similarity Agent
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">
          Find similar players
        </h1>
        <p className="mt-3 text-foreground-muted">
          Pick a reference player to find statistically similar profiles
          using a normalised, weighted Euclidean distance model. Every match
          shows a 0-100 similarity score plus the metrics where the two
          players are most alike and most different.
        </p>
      </div>

      <Card className="mx-auto mt-8 max-w-3xl">
        <PlayerSelect
          label="Reference player"
          value={reference}
          onChange={setReference}
          maxSelected={1}
          helpText="Search by player name, club, or position."
        />

        <div className="mt-4">
          <label htmlFor="top-n" className="mb-1.5 block text-sm font-medium text-foreground">
            Number of results: {topN}
          </label>
          <input
            id="top-n"
            type="range"
            min={1}
            max={20}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            className="w-full accent-accent"
          />
        </div>

        {validationError && (
          <p className="mt-2 text-sm text-danger">{validationError}</p>
        )}

        <Button onClick={handleFind} disabled={loading || reference.length === 0} className="mt-4">
          {loading ? "Searching..." : "Find similar players"}
        </Button>
      </Card>

      <div className="mx-auto mt-10 max-w-5xl space-y-6">
        {loading && <LoadingState label="Computing similarity scores..." />}
        {error && <ErrorState message={error} />}

        {result && (
          <>
            <Card>
              <CardHeader title="Reference player" />
              <PlayerCard player={result.reference_player} />
              <p className="mt-4 text-sm leading-7 text-foreground-muted">{result.explanation}</p>
              <p className="mt-2 text-xs text-foreground-subtle">
                Method: <span className="font-mono">{result.method}</span>
              </p>
            </Card>

            <Card>
              <CardHeader title="Similarity scores" />
              <SimilarityBarChart results={result.similar_players} />
            </Card>

            <div className="space-y-4">
              {result.similar_players.map((r) => (
                <Card key={r.player.player_id}>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-foreground">{r.player.player_name}</h3>
                        <Badge tone="accent">{r.similarity_score}/100</Badge>
                      </div>
                      <p className="mt-1 text-sm text-foreground-muted">
                        {r.player.position} - {r.player.club}
                      </p>

                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
                            Closest metrics
                          </p>
                          <ul className="mt-1 space-y-1 text-sm text-foreground-muted">
                            {r.closest_metrics.map((m) => (
                              <li key={m.metric}>
                                {m.label}: {formatNumber(m.reference_value)} vs{" "}
                                {formatNumber(m.candidate_value)}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
                            Biggest differences
                          </p>
                          <ul className="mt-1 space-y-1 text-sm text-foreground-muted">
                            {r.biggest_differences.map((m) => (
                              <li key={m.metric}>
                                {m.label}: {formatNumber(m.reference_value)} vs{" "}
                                {formatNumber(m.candidate_value)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
      </div>
    </Container>
  );
}
