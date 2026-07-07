"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { APP_NAME, NAV_LINKS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Container } from "./Container";

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <Container className="flex h-16 items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight text-foreground focus-ring rounded"
          onClick={() => setOpen(false)}
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 text-accent">
            <span className="text-sm font-bold">Q</span>
          </span>
          <span>
            {APP_NAME.replace(" AI", "")}
            <span className="text-accent"> AI</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors focus-ring",
                  active
                    ? "text-accent"
                    : "text-foreground-muted hover:text-foreground"
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <Link
          href="/scout"
          className="hidden rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-opacity hover:opacity-90 focus-ring md:inline-flex"
        >
          Try Q Scout
        </Link>

        <button
          type="button"
          aria-label="Toggle navigation menu"
          aria-expanded={open}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-foreground-muted focus-ring md:hidden"
          onClick={() => setOpen((v) => !v)}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            aria-hidden="true"
          >
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </Container>

      {open && (
        <div className="border-t border-border/60 bg-background md:hidden">
          <Container className="flex flex-col gap-1 py-3">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors focus-ring",
                    active
                      ? "bg-background-elevated text-accent"
                      : "text-foreground-muted hover:bg-background-elevated hover:text-foreground"
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
            <Link
              href="/scout"
              onClick={() => setOpen(false)}
              className="mt-2 rounded-md bg-accent px-3 py-2 text-center text-sm font-semibold text-background"
            >
              Try Q Scout
            </Link>
          </Container>
        </div>
      )}
    </header>
  );
}
