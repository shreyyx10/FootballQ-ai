"use client";

import { useState } from "react";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Loading";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlayerCard } from "@/components/football/PlayerCard";
import { scoutQuery } from "@/lib/api";
import type { ScoutResponse } from "@/lib/api";
import { scoutQueryRequestSchema } from "@/lib/schemas";
import { sanitizeQueryInput } from "@/lib/security";
import { MAX_QUERY_LENGTH, SAMPLE_SCOUT_QUERIES } from "@/lib/constants";
import { titleCase } from "@/lib/utils";

const confidenceTone: Record<string, "accent" | "warning" | "danger"> = {
  High: "accent",
  Medium: "warning",
  Low: "danger",
};

export default function ScoutPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [result, setResult] = useState<ScoutResponse | null>(null);

  async function runQuery(text: string) {
    const candidate = sanitizeQueryInput(text);
    const parsed = scoutQueryRequestSchema.safeParse({ query: candidate });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid query.");
      return;
    }

    setValidationError(null);
    setError(null);
    setLoading(true);
    setResult(null);

    const res = await scoutQuery(parsed.data);
    setLoading(false);

    if (res.ok) {
      setResult(res.data);
    } else {
      setError(res.error);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void runQuery(query);
  }

  function handleSample(sample: string) {
    setQuery(sample);
    void runQuery(sample);
  }

  return (
    <Container className="py-12 sm:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <Badge tone="accent" className="mb-3">
          Multi-agent workflow
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">Q Scout</h1>
        <p className="mt-3 text-foreground-muted">
          Ask a scouting question in plain English. A query classifier, stats
          and similarity agents, an SQL-backed RAG retriever, and a
          recommendation agent work together to ground the answer in the
          sample dataset - with a concise workflow summary and no hidden
          chain-of-thought.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mx-auto mt-8 max-w-3xl">
        <label htmlFor="scout-query" className="sr-only">
          Scouting question
        </label>
        <textarea
          id="scout-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          maxLength={MAX_QUERY_LENGTH}
          placeholder="e.g. Find me a young winger who can dribble past defenders"
          className="w-full resize-none rounded-lg border border-border bg-background-surface px-4 py-3 text-sm text-foreground placeholder:text-foreground-subtle focus-ring focus:border-accent/50"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-foreground-subtle">
            {query.length}/{MAX_QUERY_LENGTH} characters
          </span>
          <Button type="submit" disabled={loading || query.trim().length === 0}>
            {loading ? "Thinking..." : "Ask Q Scout"}
          </Button>
        </div>
        {validationError && (
          <p className="mt-2 text-sm text-danger">{validationError}</p>
        )}
      </form>

      <div className="mx-auto mt-6 max-w-3xl">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-foreground-subtle">
          Try a sample question
        </p>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_SCOUT_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => handleSample(sample)}
              disabled={loading}
              className="rounded-full border border-border bg-background-surface px-3 py-1.5 text-xs text-foreground-muted transition-colors hover:border-accent/40 hover:text-accent focus-ring disabled:opacity-50"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto mt-10 max-w-4xl space-y-6">
        {loading && <LoadingState label="Running the multi-agent workflow..." />}
        {error && <ErrorState message={error} />}

        {result && (
          <>
            <Card>
              <div className="mb-3 flex items-center justify-between gap-3">
                <CardHeader title="Answer" className="mb-0" />
                <Badge tone={confidenceTone[result.confidence_level] ?? "neutral"}>
                  Confidence: {result.confidence_level}
                </Badge>
              </div>
              <p className="text-sm leading-7 text-foreground">{result.answer}</p>
            </Card>

            {result.recommended_players.length > 0 && (
              <Card>
                <CardHeader
                  title="Recommended players"
                  description="Players surfaced by the stats, similarity, comparison, or tactical-fit agents for this query."
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  {result.recommended_players.map((p) => (
                    <PlayerCard key={p.player_id} player={p} />
                  ))}
                </div>
              </Card>
            )}

            {result.supporting_statistics.length > 0 && (
              <Card>
                <CardHeader
                  title="Supporting statistics"
                  description="Key metrics behind the recommendation."
                />
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-foreground-muted">
                        <th className="py-2 pr-4 font-medium">Player</th>
                        {Object.keys(result.supporting_statistics[0])
                          .filter((k) => k !== "player_id" && k !== "player_name")
                          .map((key) => (
                            <th key={key} className="py-2 pr-4 font-medium">
                              {titleCase(key)}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.supporting_statistics.map((row) => (
                        <tr key={String(row.player_id)} className="border-b border-border/50">
                          <td className="py-2 pr-4 font-medium text-foreground">
                            {String(row.player_name)}
                          </td>
                          {Object.entries(row)
                            .filter(([k]) => k !== "player_id" && k !== "player_name")
                            .map(([key, value]) => (
                              <td key={key} className="py-2 pr-4 text-foreground-muted">
                                {value === null || value === undefined ? "-" : String(value)}
                              </td>
                            ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            <div className="grid gap-6 sm:grid-cols-2">
              <Card>
                <CardHeader title="Retrieved context" description="SQL RAG retriever output" />
                <ul className="space-y-2 text-sm text-foreground-muted">
                  {result.retrieved_context_summary.map((line, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-accent">&bull;</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </Card>

              <Card>
                <CardHeader title="Workflow summary" description="Concise agent-by-agent summary" />
                <ol className="space-y-2 text-sm text-foreground-muted">
                  {result.workflow_summary.map((line, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="font-mono text-xs text-accent">{String(i + 1).padStart(2, "0")}</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ol>
              </Card>
            </div>

            {result.limitations.length > 0 && (
              <Card className="border-warning/30 bg-warning/5">
                <CardHeader title="Limitations" />
                <ul className="space-y-2 text-sm text-foreground-muted">
                  {result.limitations.map((line, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-warning">&bull;</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}
      </div>
    </Container>
  );
}
