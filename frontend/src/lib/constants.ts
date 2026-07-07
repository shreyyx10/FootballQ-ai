/**
 * App-wide constants for FootballQ AI.
 *
 * All values that may change between environments are read from
 * NEXT_PUBLIC_* environment variables (see .env.example at the repo root).
 * Sensible fallbacks are provided so local development and CI builds work
 * without a configured backend.
 */

export const APP_NAME =
  process.env.NEXT_PUBLIC_APP_NAME?.trim() || "FootballQ AI";

export const APP_TAGLINE =
  "Ask smarter football questions. Discover better players.";

export const APP_ENVIRONMENT =
  process.env.NEXT_PUBLIC_ENVIRONMENT?.trim() || "production";

/**
 * Base URL for the Azure Functions API, e.g.
 * https://footballq-ai-api.azurewebsites.net/api
 *
 * Falls back to a relative "/api" path during local development/build so
 * the app does not hardcode "localhost" anywhere in source control. When
 * this is unset in production, API calls will fail gracefully and the UI
 * shows a configuration notice instead of a broken request.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "/api";

export const IS_API_CONFIGURED = API_BASE_URL !== "/api";

export const GITHUB_REPO_URL = "https://github.com/your-username/footballq-ai";

export const LIVE_SITE_URL = "https://footballq-ai.vercel.app";

/** Site navigation used by the header/footer. */
export const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/scout", label: "Q Scout" },
  { href: "/compare", label: "Compare" },
  { href: "/similarity", label: "Similarity" },
  { href: "/tactical-fit", label: "Tactical Fit" },
  { href: "/architecture", label: "Architecture" },
  { href: "/about", label: "About" },
] as const;

/** Mirrors api/shared/security.py MAX_QUERY_LENGTH. */
export const MAX_QUERY_LENGTH = 500;

/** Mirrors api/shared/security.py MAX_PLAYER_IDS. */
export const MAX_PLAYER_IDS = 5;

/** Sample queries shown on the Q Scout page to help users get started. */
export const SAMPLE_SCOUT_QUERIES = [
  "Find me a young winger who can dribble past defenders",
  "Compare Pedri and Jude Bellingham",
  "Which players are similar to Erling Haaland?",
  "Which midfielders fit Barcelona's tactical style?",
  "Generate a scouting report on Florian Wirtz",
  "Find undervalued strikers under 24",
] as const;

/** Team names available for the tactical fit explorer (sample dataset). */
export const SAMPLE_TEAMS = [
  "Barcelona",
  "Manchester City",
  "Arsenal",
  "Real Madrid",
  "Liverpool",
  "Bayern Munich",
] as const;
