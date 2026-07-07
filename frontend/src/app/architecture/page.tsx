import type { Metadata } from "next";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export const metadata: Metadata = {
  title: "Architecture",
  description:
    "How FootballQ AI is built: a Next.js frontend on Vercel, a Python Azure Functions API, Azure SQL with a local-seed fallback, SQL-backed RAG, and a LangGraph-inspired multi-agent workflow.",
};

const LAYERS = [
  {
    name: "Frontend",
    detail: "Next.js 14 (App Router) + TypeScript + Tailwind CSS + Recharts + Zod, deployed on Vercel Hobby.",
  },
  {
    name: "API",
    detail: "Python Azure Functions (Consumption plan), Pydantic request validation, CORS allowlist, rate limiting.",
  },
  {
    name: "Agent workflow",
    detail: "Query Classifier, Stats, Similarity, Comparison, Tactical Fit, Recommendation, and Safety agents implemented as plain Python functions.",
  },
  {
    name: "RAG retrieval",
    detail: "SQL-backed keyword retrieval over ScoutingNotes and TeamProfiles - no embeddings or vector DB required.",
  },
  {
    name: "Data layer",
    detail: "Azure SQL free offer (SQL Server-compatible), with an in-memory local seed data store as a zero-config fallback.",
  },
];

const AGENTS = [
  { name: "Query Classifier", role: "Identifies the query type and extracts entities (players, teams, positions, styles)." },
  { name: "Stats Agent", role: "Filters and ranks players from the dataset based on parsed constraints." },
  { name: "SQL RAG Retriever", role: "Retrieves relevant scouting notes and team profiles via weighted keyword search." },
  { name: "Similarity Agent", role: "Computes normalised weighted-Euclidean similarity scores between players." },
  { name: "Comparison Agent", role: "Builds the side-by-side comparison table, strengths, and weaknesses." },
  { name: "Tactical Fit Agent", role: "Scores positional, pressing, possession, and output alignment with a team." },
  { name: "Recommendation Agent", role: "Assembles the final narrative, confidence level, and limitations." },
  { name: "Safety Agent", role: "Screens input for prompt-injection or unsafe patterns and adds limitations - never blocks the football request." },
];

export default function ArchitecturePage() {
  return (
    <Container className="py-12 sm:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <Badge tone="accent" className="mb-3">
          System design
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">Architecture</h1>
        <p className="mt-3 text-foreground-muted">
          FootballQ AI is designed to run entirely on free tiers, with a
          mock-LLM mode enabled by default and explainable, deterministic
          scoring logic everywhere a number is shown to a user.
        </p>
      </div>

      {/* Layered diagram */}
      <Card className="mx-auto mt-10 max-w-3xl">
        <CardHeader title="Request flow" description="From browser to data, top to bottom" />
        <div className="space-y-3">
          {LAYERS.map((layer, i) => (
            <div key={layer.name} className="flex items-start gap-4">
              <div className="flex flex-col items-center">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/15 text-sm font-bold text-accent">
                  {i + 1}
                </div>
                {i < LAYERS.length - 1 && <div className="mt-1 h-8 w-px bg-border" />}
              </div>
              <div className="rounded-lg border border-border bg-background-elevated px-4 py-3 flex-1">
                <h3 className="font-semibold text-foreground">{layer.name}</h3>
                <p className="mt-1 text-sm text-foreground-muted">{layer.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Agent workflow */}
      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader
          title="LangGraph-inspired agent workflow"
          description="Implemented as modular Python functions to avoid the cold-start cost of a full graph runtime on Azure Functions Consumption plan"
        />
        <div className="grid gap-3 sm:grid-cols-2">
          {AGENTS.map((agent) => (
            <div key={agent.name} className="rounded-lg border border-border bg-background-elevated p-4">
              <h3 className="text-sm font-semibold text-accent">{agent.name}</h3>
              <p className="mt-1 text-sm text-foreground-muted">{agent.role}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-foreground-muted">
          Every <code className="rounded bg-background px-1 py-0.5 text-xs">/api/scout</code> response
          includes a concise <code className="rounded bg-background px-1 py-0.5 text-xs">workflow_summary</code>
          listing what each agent did - the underlying chain-of-thought is
          never exposed.
        </p>
      </Card>

      {/* RAG */}
      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader
          title="Retrieval-augmented generation (RAG)"
          description="SQL-backed by default, optional Qdrant layer"
        />
        <p className="text-sm leading-7 text-foreground-muted">
          By default, the RAG retriever extracts keywords (player names, team
          names, positions, tactical style terms) from a query and runs a
          weighted keyword search over the <code className="rounded bg-background px-1 py-0.5 text-xs">ScoutingNotes</code> and{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">TeamProfiles</code> tables - no embeddings or
          vector database are required. If <code className="rounded bg-background px-1 py-0.5 text-xs">ENABLE_QDRANT=true</code> is set and a
          Qdrant URL is configured, an optional semantic search layer can be
          added on top; if Qdrant is unavailable for any reason, retrieval
          silently falls back to the SQL keyword method.
        </p>
      </Card>

      {/* Data layer */}
      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader
          title="Data layer"
          description="Azure SQL free offer with a local-seed fallback"
        />
        <p className="text-sm leading-7 text-foreground-muted">
          The API reads from Azure SQL when{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">AZURE_SQL_CONNECTION_STRING</code> is configured,
          using parameterised queries only. If the connection string is not
          set, or any database call fails, the API transparently falls back
          to an in-memory data store seeded from the same sample CSV/JSON
          files used to populate Azure SQL - so the public demo always works,
          even before the database is provisioned.
        </p>
      </Card>

      {/* LLM mode */}
      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader
          title="LLM mode"
          description="Mock by default, optional real LLM"
        />
        <p className="text-sm leading-7 text-foreground-muted">
          With <code className="rounded bg-background px-1 py-0.5 text-xs">USE_MOCK_LLM=true</code> (the default), all
          narrative text is generated by deterministic template functions
          based on the computed statistics - no API key required. Setting{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">ENABLE_REAL_LLM=true</code> and providing an{" "}
          <code className="rounded bg-background px-1 py-0.5 text-xs">OPENAI_API_KEY</code> allows an optional real LLM
          call to enhance the narrative; if that call fails or is disabled,
          the mock-generated text is used as a safe fallback.
        </p>
      </Card>
    </Container>
  );
}
