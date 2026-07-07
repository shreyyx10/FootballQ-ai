"use client";

import { useState } from "react";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Loading";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlayerSelect } from "@/components/football/PlayerSelect";
import { ScoreGauge } from "@/components/football/ScoreGauge";
import { getTacticalFit } from "@/lib/api";
import type { TacticalFitResponse } from "@/lib/api";
import { tacticalFitRequestSchema } from "@/lib/schemas";
import { SAMPLE_TEAMS } from "@/lib/constants";

export default function TacticalFitPage() {
  const [player, setPlayer] = useState<string[]>([]);
  const [team, setTeam] = useState<string>(SAMPLE_TEAMS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [result, setResult] = useState<TacticalFitResponse | null>(null);

  async function handleAssess() {
    const parsed = tacticalFitRequestSchema.safeParse({
      player_id: player[0],
      team_name: team,
    });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Select a player and team.");
      return;
    }

    setValidationError(null);
    setError(null);
    setLoading(true);
    setResult(null);

    const res = await getTacticalFit(parsed.data);
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
          Tactical Fit Agent
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">
          Tactical fit explorer
        </h1>
        <p className="mt-3 text-foreground-muted">
          Assess how well a player&apos;s statistical profile aligns with a
          club&apos;s pressing intensity, possession style, formation, and
          stated player requirements - with an explainable 0-100 fit score.
        </p>
      </div>

      <Card className="mx-auto mt-8 max-w-3xl">
        <PlayerSelect
          label="Player"
          value={player}
          onChange={setPlayer}
          maxSelected={1}
          helpText="Search by player name, club, or position."
        />

        <div className="mt-4">
          <label htmlFor="team" className="mb-1.5 block text-sm font-medium text-foreground">
            Team
          </label>
          <select
            id="team"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-ring focus:border-accent/50"
          >
            {SAMPLE_TEAMS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {validationError && (
          <p className="mt-2 text-sm text-danger">{validationError}</p>
        )}

        <Button onClick={handleAssess} disabled={loading || player.length === 0} className="mt-4">
          {loading ? "Assessing..." : "Assess tactical fit"}
        </Button>
      </Card>

      <div className="mx-auto mt-10 max-w-4xl space-y-6">
        {loading && <LoadingState label="Scoring tactical fit..." />}
        {error && <ErrorState message={error} />}

        {result && (
          <>
            <Card className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
              <ScoreGauge score={result.fit_score} label="Fit score" size={120} />
              <div className="flex-1 text-center sm:text-left">
                <h2 className="text-xl font-semibold text-foreground">
                  {result.player.player_name} &rarr; {result.team.team_name}
                </h2>
                <p className="mt-1 text-sm text-foreground-muted">
                  {result.player.position} - {result.player.club}
                </p>
                <p className="mt-3 text-sm leading-7 text-foreground">{result.explanation}</p>
              </div>
            </Card>

            <div className="grid gap-6 sm:grid-cols-2">
              <Card>
                <CardHeader title="Strengths" />
                <ul className="space-y-2 text-sm text-foreground-muted">
                  {result.strengths.map((s, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-accent">&bull;</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card>
                <CardHeader title="Risks" />
                <ul className="space-y-2 text-sm text-foreground-muted">
                  {result.risks.map((r, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-warning">&bull;</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>

            <Card>
              <CardHeader
                title={`${result.team.team_name} tactical profile`}
                description="Team profile used for this assessment"
              />
              <dl className="grid gap-4 text-sm sm:grid-cols-2">
                {Object.entries(result.team)
                  .filter(([key]) => key !== "team_name")
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt className="text-xs uppercase tracking-wide text-foreground-subtle">
                        {key.replace(/_/g, " ")}
                      </dt>
                      <dd className="mt-0.5 text-foreground-muted">{String(value)}</dd>
                    </div>
                  ))}
              </dl>
            </Card>
          </>
        )}
      </div>
    </Container>
  );
}
