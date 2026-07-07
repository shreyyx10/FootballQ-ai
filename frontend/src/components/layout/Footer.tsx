import Link from "next/link";
import { APP_NAME, GITHUB_REPO_URL, NAV_LINKS } from "@/lib/constants";
import { Container } from "./Container";

export function Footer() {
  return (
    <footer className="border-t border-border/60 bg-background-surface">
      <Container className="flex flex-col gap-8 py-12 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 text-accent">
              <span className="text-sm font-bold">Q</span>
            </span>
            <span>
              {APP_NAME.replace(" AI", "")}
              <span className="text-accent"> AI</span>
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-foreground-muted">
            A free, open portfolio project demonstrating a multi-agent
            football scouting assistant. All data is sample data for
            demonstration only - not for real recruitment decisions.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-8 text-sm sm:grid-cols-3">
          <div>
            <h3 className="font-medium text-foreground">Explore</h3>
            <ul className="mt-3 space-y-2 text-foreground-muted">
              {NAV_LINKS.slice(1).map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="hover:text-accent focus-ring rounded">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-medium text-foreground">Project</h3>
            <ul className="mt-3 space-y-2 text-foreground-muted">
              <li>
                <Link href="/architecture" className="hover:text-accent focus-ring rounded">
                  Architecture
                </Link>
              </li>
              <li>
                <Link href="/about" className="hover:text-accent focus-ring rounded">
                  About &amp; Security
                </Link>
              </li>
              <li>
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="hover:text-accent focus-ring rounded"
                >
                  Source code
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium text-foreground">Free-tier demo</h3>
            <ul className="mt-3 space-y-2 text-foreground-muted">
              <li>Vercel Hobby (frontend)</li>
              <li>Azure Functions Consumption (API)</li>
              <li>Azure SQL free offer (database)</li>
            </ul>
          </div>
        </div>
      </Container>

      <Container className="border-t border-border/60 py-6 text-xs text-foreground-subtle">
        <p>
          &copy; {new Date().getFullYear()} {APP_NAME}. Built as a portfolio
          project. No real player data is used for transfer or scouting
          decisions.
        </p>
      </Container>
    </footer>
  );
}
