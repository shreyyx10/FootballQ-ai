import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { APP_NAME, APP_TAGLINE, LIVE_SITE_URL } from "@/lib/constants";
import "@/styles/globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(LIVE_SITE_URL),
  title: {
    default: `${APP_NAME} - ${APP_TAGLINE}`,
    template: `%s | ${APP_NAME}`,
  },
  description:
    "FootballQ AI is a multi-agent football scouting assistant. Ask natural-language questions, compare players, find similar profiles, and assess tactical fit - powered by a transparent, explainable agent workflow.",
  keywords: [
    "football scouting",
    "AI scouting assistant",
    "player comparison",
    "player similarity",
    "tactical fit analysis",
    "FootballQ AI",
  ],
  openGraph: {
    title: `${APP_NAME} - ${APP_TAGLINE}`,
    description:
      "Ask natural-language football scouting questions and get explainable, data-driven answers from a multi-agent AI workflow.",
    url: LIVE_SITE_URL,
    siteName: APP_NAME,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: `${APP_NAME} - ${APP_TAGLINE}`,
    description: APP_TAGLINE,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground antialiased">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
