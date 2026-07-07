import { cn } from "@/lib/utils";

/**
 * Circular 0-100 score gauge used for similarity scores and tactical fit
 * scores. Implemented as an inline SVG so it has no chart-library
 * dependency for a simple visual.
 */
export function ScoreGauge({
  score,
  label,
  size = 96,
}: {
  score: number;
  label?: string;
  size?: number;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  const colorClass =
    clamped >= 70
      ? "text-accent"
      : clamped >= 40
        ? "text-warning"
        : "text-danger";

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={8}
            className="text-border"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={cn("transition-all duration-700", colorClass)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-foreground">{clamped.toFixed(0)}</span>
        </div>
      </div>
      {label && (
        <p className="mt-2 text-center text-xs text-foreground-muted">{label}</p>
      )}
    </div>
  );
}
