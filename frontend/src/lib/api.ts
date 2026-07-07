/**
 * Typed client for the FootballQ AI Azure Functions API.
 *
 * All requests go to NEXT_PUBLIC_API_BASE_URL (see constants.ts). Every
 * function returns a discriminated `ApiResult<T>` so callers can render a
 * friendly error state instead of throwing - the public demo should never
 * show a raw stack trace or unhandled exception to a visitor.
 */

import { API_BASE_URL } from "./constants";
import type {
  ComparePlayersInput,
  Player,
  PlayerQueryParamsInput,
  ScoutQueryInput,
  SimilarityInput,
  TacticalFitInput,
} from "./schemas";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

export interface HealthResponse {
  status: string;
  service: string;
  mode: string;
}

export interface PlayersResponse {
  players: Player[];
  count: number;
}

export interface PlayerResponse {
  player: Player;
}

export interface MetricComparison {
  metric: string;
  label: string;
  reference_value: number | null;
  candidate_value: number | null;
  normalised_difference: number;
}

export interface SimilarPlayerResult {
  player: Player;
  similarity_score: number;
  closest_metrics: MetricComparison[];
  biggest_differences: MetricComparison[];
}

export interface SimilarityResponse {
  reference_player: Player;
  similar_players: SimilarPlayerResult[];
  method: string;
  explanation: string;
}

export interface ComparisonRow {
  metric: string;
  label: string;
  leader: string | null;
  [playerId: string]: string | number | null;
}

export interface ComparisonResponse {
  players: Player[];
  comparison_table: ComparisonRow[];
  metric_differences: {
    metric: string;
    label: string;
    difference: number;
    leader: string | null;
  }[];
  strengths: { player_id: string; player_name: string; leading_metrics: string[] }[];
  weaknesses: { player_id: string; player_name: string; trailing_metrics: string[] }[];
  summary: string;
}

export interface TacticalFitResponse {
  player: Player;
  team: Record<string, unknown> & { team_name: string };
  fit_score: number;
  strengths: string[];
  risks: string[];
  explanation: string;
}

export interface ScoutResponse {
  answer: string;
  recommended_players: Player[];
  supporting_statistics: Record<string, unknown>[];
  retrieved_context_summary: string[];
  workflow_summary: string[];
  confidence_level: "Low" | "Medium" | "High" | string;
  limitations: string[];
}

const DEFAULT_TIMEOUT_MS = 20_000;

async function request<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number }
): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    init?.timeoutMs ?? DEFAULT_TIMEOUT_MS
  );

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      signal: controller.signal,
      cache: "no-store",
    });

    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = null;
    }

    if (!res.ok) {
      const errBody = body as ApiErrorBody | null;
      const message =
        errBody?.error?.message ||
        "The FootballQ AI API returned an unexpected error. Please try again.";
      return { ok: false, error: message, status: res.status };
    }

    return { ok: true, data: body as T };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return {
        ok: false,
        error:
          "The request took too long to respond. The free-tier API may be cold-starting - please try again in a moment.",
      };
    }
    return {
      ok: false,
      error:
        "Could not reach the FootballQ AI API. Please check your connection and try again.",
    };
  } finally {
    clearTimeout(timeout);
  }
}

export function getHealth(): Promise<ApiResult<HealthResponse>> {
  return request<HealthResponse>("/health");
}

export function getPlayers(
  params: PlayerQueryParamsInput = {}
): Promise<ApiResult<PlayersResponse>> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return request<PlayersResponse>(`/players${query ? `?${query}` : ""}`);
}

export function getPlayer(playerId: string): Promise<ApiResult<PlayerResponse>> {
  return request<PlayerResponse>(`/players/${encodeURIComponent(playerId)}`);
}

export function comparePlayers(
  payload: ComparePlayersInput
): Promise<ApiResult<ComparisonResponse>> {
  return request<ComparisonResponse>("/compare", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSimilarity(
  payload: SimilarityInput
): Promise<ApiResult<SimilarityResponse>> {
  return request<SimilarityResponse>("/similarity", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTacticalFit(
  payload: TacticalFitInput
): Promise<ApiResult<TacticalFitResponse>> {
  return request<TacticalFitResponse>("/tactical-fit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function scoutQuery(
  payload: ScoutQueryInput
): Promise<ApiResult<ScoutResponse>> {
  return request<ScoutResponse>("/scout", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: 30_000,
  });
}
