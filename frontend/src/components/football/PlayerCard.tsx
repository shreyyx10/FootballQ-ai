import type { Player } from "@/lib/schemas";
import { Badge } from "@/components/ui/Badge";
import { formatMarketValue } from "@/lib/utils";

export function PlayerCard({ player }: { player: Player }) {
  return (
    <div className="rounded-lg border border-border bg-background-elevated p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="font-semibold text-foreground">{player.player_name}</h4>
          <p className="text-sm text-foreground-muted">
            {player.position} - {player.club}
          </p>
        </div>
        {player.age != null && <Badge>{player.age} yrs</Badge>}
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-foreground-muted sm:grid-cols-4">
        <div>
          <dt className="uppercase tracking-wide text-foreground-subtle">League</dt>
          <dd className="mt-0.5 text-foreground">{player.league ?? "-"}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-foreground-subtle">Minutes</dt>
          <dd className="mt-0.5 text-foreground">{player.minutes ?? "-"}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-foreground-subtle">Goals</dt>
          <dd className="mt-0.5 text-foreground">{player.goals ?? "-"}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-foreground-subtle">Assists</dt>
          <dd className="mt-0.5 text-foreground">{player.assists ?? "-"}</dd>
        </div>
      </dl>

      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-foreground-subtle">
          {player.nationality ?? ""} {player.preferred_foot ? `- ${player.preferred_foot} foot` : ""}
        </span>
        <span className="font-medium text-accent">
          {formatMarketValue(player.market_value_million as number | null | undefined)}
        </span>
      </div>
    </div>
  );
}
