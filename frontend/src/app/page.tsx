import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Container } from "@/components/layout/Container";
import { APP_NAME, APP_TAGLINE } from "@/lib/constants";

const FEATURES = [
  {
    title: "Q Scout",
    href: "/scout",
    description:
      "Ask natural-language scouting questions and get an explainable answer assembled by a multi-agent workflow - recommended players, supporting stats, and retrieved context, with no hidden reasoning.",
  },
  {
    title: "Player Comparison",
    href: "/compare",
    description:
      "Put up to five players side-by-side across goals, expected output, progression, and defensive metrics, with a radar chart and a clear strengths/weaknesses breakdown.",
  },
  {
    title: "Similarity Engine",
    href: "/similarity",
    description:
      "Find statistically similar players using a normalised, weighted Euclidean distance model - with the closest and most different metrics explained for every match.",
  },
  {
    title: "Tactical Fit",
    href: "/tactical-fit",
    description:
      "Score how well a player's profile aligns with a club's pressing intensity, possession style, and positional needs - with an explainable 0-100 fit score.",
  },
];

const WORKFLOW_STEPS = [
  {
    name: "Query Classifier",
    description: "Reads your question and identifies the type of scouting task.",
  },
  {
    name: "Stats & Similarity Agents",
    description: "Filter, rank, and compare players from the sample dataset.",
  },
  {
    name: "SQL RAG Retriever",
    description: "Pulls relevant scouting notes and team profiles for context.",
  },
  {
    name: "Recommendation & Safety Agents",
    description: "Assemble a clear answer and screen for unsafe input - no hidden chain-of-thought.",
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-grid">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-background-surface" />
        <Container className="relative py-24 sm:py-32">
          <div className="mx-auto max-w-3xl text-center animate-fade-in-up">
            <Badge tone="accent" className="mb-4">
              Free, open multi-agent scouting demo
            </Badge>
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-6xl">
              {APP_NAME}
            </h1>
            <p className="mt-4 text-lg text-foreground-muted sm:text-xl">
              {APP_TAGLINE}
            </p>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-foreground-muted sm:text-base">
              Ask a question in plain English and a transparent multi-agent
              workflow - query classification, statistical analysis, SQL-backed
              retrieval, and explainable recommendations - turns it into a
              grounded scouting answer drawn from a sample player dataset.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <ButtonLink href="/scout" size="lg">
                Try Q Scout
              </ButtonLink>
              <ButtonLink href="/compare" variant="secondary" size="lg">
                Compare Players
              </ButtonLink>
              <ButtonLink href="/architecture" variant="ghost" size="lg">
                View Architecture
              </ButtonLink>
            </div>
          </div>
        </Container>
      </section>

      {/* Features */}
      <section className="py-20">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
              Four ways to explore the dataset
            </h2>
            <p className="mt-3 text-foreground-muted">
              Every tool runs on the same sample dataset and the same
              explainable scoring logic - no black-box predictions.
            </p>
          </div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2">
            {FEATURES.map((feature) => (
              <Card key={feature.href} className="flex flex-col">
                <h3 className="text-lg font-semibold text-foreground">
                  {feature.title}
                </h3>
                <p className="mt-2 flex-1 text-sm leading-6 text-foreground-muted">
                  {feature.description}
                </p>
                <ButtonLink href={feature.href} variant="secondary" className="mt-4 self-start">
                  Open {feature.title}
                </ButtonLink>
              </Card>
            ))}
          </div>
        </Container>
      </section>

      {/* How it works */}
      <section className="border-t border-border/60 bg-background-surface py-20">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
              How the agent workflow works
            </h2>
            <p className="mt-3 text-foreground-muted">
              A LangGraph-inspired pipeline of small, single-purpose agents.
              Every response includes a concise workflow summary - never the
              underlying chain-of-thought.
            </p>
          </div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {WORKFLOW_STEPS.map((step, i) => (
              <div key={step.name} className="rounded-xl border border-border bg-background p-5">
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-sm font-bold text-accent">
                  {i + 1}
                </div>
                <h3 className="font-semibold text-foreground">{step.name}</h3>
                <p className="mt-2 text-sm text-foreground-muted">{step.description}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 text-center">
            <ButtonLink href="/architecture" variant="ghost">
              See the full architecture &rarr;
            </ButtonLink>
          </div>
        </Container>
      </section>

      {/* Free demo note */}
      <section className="py-16">
        <Container>
          <div className="mx-auto max-w-3xl rounded-xl border border-accent/20 bg-accent/5 p-6 text-center sm:p-8">
            <h2 className="text-lg font-semibold text-foreground">
              Built entirely on free tiers
            </h2>
            <p className="mt-2 text-sm leading-6 text-foreground-muted">
              {APP_NAME} runs on Vercel Hobby, Azure Functions Consumption, and
              the Azure SQL free offer, with a mock-LLM mode enabled by
              default - no API keys or paid services are required to run this
              demo. All player data is illustrative sample data and should not
              be used for real recruitment decisions.
            </p>
          </div>
        </Container>
      </section>
    </>
  );
}
