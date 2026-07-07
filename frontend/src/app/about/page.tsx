import type { Metadata } from "next";
import { Container } from "@/components/layout/Container";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { APP_NAME, GITHUB_REPO_URL } from "@/lib/constants";

export const metadata: Metadata = {
  title: "About & Security",
  description:
    "About FootballQ AI: project background, technology stack, security-conscious controls for a public demo, and known limitations.",
};

const SECURITY_CONTROLS = [
  "All API inputs are validated with Pydantic models before any business logic runs.",
  "All database queries use parameterised SQL - never string concatenation or f-strings with user input.",
  "CORS is restricted to an explicit ALLOWED_ORIGINS allowlist.",
  "Best-effort in-memory rate limiting on every endpoint.",
  "A Safety Agent screens scout queries for prompt-injection-style patterns and flags them in the response.",
  "Error responses never include stack traces, exception messages, or secrets.",
  "No secrets are committed to the repository - all credentials are environment variables.",
  "Security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) are set on every response.",
];

const LIMITATIONS = [
  "The dataset is a small, illustrative sample of well-known players - not a comprehensive or current scouting database.",
  "Mock LLM mode produces template-based narratives; enabling a real LLM may change tone but not the underlying statistics.",
  "Rate limiting is in-memory and per-instance - it is a best-effort guard, not a substitute for an API gateway.",
  "Tactical fit and similarity scores are heuristic and explainable, not machine-learning predictions.",
];

export default function AboutPage() {
  return (
    <Container className="py-12 sm:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <Badge tone="accent" className="mb-3">
          Portfolio project
        </Badge>
        <h1 className="text-3xl font-bold text-foreground sm:text-4xl">About {APP_NAME}</h1>
        <p className="mt-3 text-foreground-muted">
          {APP_NAME} is a free, open portfolio project demonstrating how a
          multi-agent AI workflow, SQL-backed retrieval, and explainable
          scoring models can be combined into a usable football scouting
          assistant - built entirely on free-tier cloud services.
        </p>
      </div>

      <Card className="mx-auto mt-10 max-w-3xl">
        <CardHeader title="Technology stack" />
        <div className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <h3 className="font-semibold text-foreground">Frontend</h3>
            <p className="mt-1 text-foreground-muted">
              Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts,
              Zod - deployed on Vercel Hobby.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Backend</h3>
            <p className="mt-1 text-foreground-muted">
              Python Azure Functions (Consumption plan), Pydantic, pyodbc -
              deployed via the Azure Functions free grant.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Database</h3>
            <p className="mt-1 text-foreground-muted">
              Azure SQL Database free offer, with an in-memory local seed
              data store as a zero-config fallback.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-foreground">AI / RAG</h3>
            <p className="mt-1 text-foreground-muted">
              Mock-LLM mode by default, SQL-backed keyword retrieval, and an
              optional real-LLM / Qdrant layer - both disabled unless
              explicitly configured.
            </p>
          </div>
        </div>
      </Card>

      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader
          title="Security-conscious controls"
          description="Built with security-conscious controls for a public demo - not claimed to be unhackable"
        />
        <ul className="space-y-2 text-sm text-foreground-muted">
          {SECURITY_CONTROLS.map((item, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-accent">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm leading-7 text-foreground-muted">
          This project is built with security-conscious controls appropriate
          for a public, free-tier demo. No system is unhackable, and this site
          should not be used to store or process sensitive personal data.
          Issues can be reported via the repository&apos;s security policy.
        </p>
      </Card>

      <Card className="mx-auto mt-8 max-w-3xl">
        <CardHeader title="Known limitations" />
        <ul className="space-y-2 text-sm text-foreground-muted">
          {LIMITATIONS.map((item, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-warning">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="mx-auto mt-10 max-w-3xl text-center">
        <ButtonLink href={GITHUB_REPO_URL} variant="secondary" external>
          View source on GitHub
        </ButtonLink>
      </div>
    </Container>
  );
}
