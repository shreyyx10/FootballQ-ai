/**
 * Frontend security helpers.
 *
 * These provide defence-in-depth on top of the backend's own validation
 * (api/shared/security.py and api/shared/schemas.py), which remains the
 * source of truth. Nothing here should be relied upon as the sole
 * protection - all inputs are re-validated server-side.
 */

import { MAX_QUERY_LENGTH } from "./constants";

/**
 * Strip characters that have no legitimate use in a football scouting
 * query and could indicate markup/script injection in rendered output.
 * This does not attempt to detect prompt injection (that is the backend
 * Safety Agent's job) - it only guards against unsafe characters reaching
 * the DOM via dangerouslySetInnerHTML-free rendering paths.
 */
export function sanitizeQueryInput(value: string): string {
  return value.replace(/[<>]/g, "").slice(0, MAX_QUERY_LENGTH);
}

/** Basic email-shaped check, used only for optional contact/feedback forms. */
export function isLikelyEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Returns true if a string is empty or only whitespace, used to disable
 * submit buttons rather than sending empty queries to the API.
 */
export function isBlank(value: string): boolean {
  return value.trim().length === 0;
}

/**
 * Truncates a string for safe display (e.g. in error toasts) without
 * leaking overly long user input back into the UI.
 */
export function truncateForDisplay(value: string, maxLength = 200): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength)}...`;
}

/**
 * A small allowlist used to validate that an external link the UI renders
 * (e.g. "View on GitHub") points somewhere expected, reducing the risk of
 * accidentally rendering an attacker-controlled href from config.
 */
const ALLOWED_LINK_HOSTS = new Set([
  "github.com",
  "vercel.app",
  "azurewebsites.net",
  "azure.microsoft.com",
  "vercel.com",
]);

export function isAllowedExternalHost(url: string): boolean {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:") return false;
    return Array.from(ALLOWED_LINK_HOSTS).some(
      (host) => parsed.hostname === host || parsed.hostname.endsWith(`.${host}`)
    );
  } catch {
    return false;
  }
}
