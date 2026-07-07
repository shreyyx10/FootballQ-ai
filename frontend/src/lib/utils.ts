/** Lightweight className joiner (avoids pulling in clsx/tailwind-merge). */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

/** Format a number with a fixed number of decimals, gracefully handling null/undefined. */
export function formatNumber(
  value: number | null | undefined,
  decimals = 1
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(decimals);
}

/** Format a market value in millions as e.g. "€85.0m". */
export function formatMarketValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `€${value.toFixed(1)}m`;
}

/** Convert snake_case metric keys into Title Case labels as a fallback. */
export function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
