"use client";

import { useEffect, useMemo, useState } from "react";
import { getPlayers } from "@/lib/api";
import type { Player } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/Loading";

interface PlayerSelectProps {
  label: string;
  /** Currently selected player_id(s). */
  value: string[];
  onChange: (value: string[]) => void;
  /** Maximum number of players that can be selected. */
  maxSelected?: number;
  /** Player IDs to exclude from the list (e.g. already selected elsewhere). */
  exclude?: string[];
  helpText?: string;
}

/**
 * A searchable player picker backed by GET /api/players. Supports both
 * single-select (maxSelected = 1) and multi-select usage across the
 * Compare, Similarity, and Tactical Fit pages.
 */
export function PlayerSelect({
  label,
  value,
  onChange,
  maxSelected = 1,
  exclude = [],
  helpText,
}: PlayerSelectProps) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getPlayers().then((res) => {
      if (!mounted) return;
      if (res.ok) {
        setPlayers(res.data.players);
        setError(null);
      } else {
        setError(res.error);
      }
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    const excludeSet = new Set(exclude);
    const q = query.trim().toLowerCase();
    return players
      .filter((p) => !excludeSet.has(p.player_id))
      .filter((p) => {
        if (!q) return true;
        return (
          p.player_name.toLowerCase().includes(q) ||
          (p.club ?? "").toLowerCase().includes(q) ||
          (p.position ?? "").toLowerCase().includes(q)
        );
      })
      .slice(0, 12);
  }, [players, query, exclude]);

  const selectedPlayers = useMemo(
    () => players.filter((p) => value.includes(p.player_id)),
    [players, value]
  );

  function toggle(playerId: string) {
    if (value.includes(playerId)) {
      onChange(value.filter((id) => id !== playerId));
      return;
    }
    if (maxSelected === 1) {
      onChange([playerId]);
      setQuery("");
      return;
    }
    if (value.length >= maxSelected) return;
    onChange([...value, playerId]);
    setQuery("");
  }

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-foreground">
        {label}
      </label>
      {helpText && (
        <p className="mb-2 text-xs text-foreground-muted">{helpText}</p>
      )}

      {selectedPlayers.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {selectedPlayers.map((p) => (
            <button
              key={p.player_id}
              type="button"
              onClick={() => toggle(p.player_id)}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/20 focus-ring"
            >
              {p.player_name}
              <span aria-hidden="true">&times;</span>
            </button>
          ))}
        </div>
      )}

      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            maxSelected === 1
              ? "Search for a player by name, club, or position..."
              : `Search players (up to ${maxSelected})...`
          }
          disabled={maxSelected > 1 && value.length >= maxSelected && query === ""}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-foreground-subtle focus-ring focus:border-accent/50"
        />

        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Spinner className="h-4 w-4" />
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-danger">{error}</p>}

      {query && !loading && (
        <div className="mt-2 max-h-64 overflow-y-auto rounded-md border border-border bg-background-surface">
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-sm text-foreground-muted">
              No players found.
            </p>
          ) : (
            filtered.map((p) => {
              const selected = value.includes(p.player_id);
              return (
                <button
                  key={p.player_id}
                  type="button"
                  onClick={() => toggle(p.player_id)}
                  className={cn(
                    "flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-background-elevated focus-ring",
                    selected && "bg-accent/10 text-accent"
                  )}
                >
                  <span>
                    <span className="font-medium">{p.player_name}</span>
                    <span className="ml-2 text-foreground-muted">
                      {p.position} - {p.club}
                    </span>
                  </span>
                  {selected && <span aria-hidden="true">&#10003;</span>}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
