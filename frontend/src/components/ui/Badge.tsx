import { cn } from "@/lib/utils";

type Tone = "accent" | "neutral" | "warning" | "danger";

const toneClasses: Record<Tone, string> = {
  accent: "bg-accent/10 text-accent border-accent/30",
  neutral: "bg-background-elevated text-foreground-muted border-border",
  warning: "bg-warning/10 text-warning border-warning/30",
  danger: "bg-danger/10 text-danger border-danger/30",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
