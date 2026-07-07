/**
 * Zod schemas mirroring the backend Pydantic models in
 * api/shared/schemas.py. Used to validate user input client-side before
 * calling the API, giving fast feedback and an extra layer of defence on
 * top of the server-side validation (which remains the source of truth).
 */

import { z } from "zod";
import { MAX_PLAYER_IDS, MAX_QUERY_LENGTH } from "./constants";

/** Mirrors api/shared/security.py PLAYER_ID_PATTERN. */
export const playerIdSchema = z
  .string()
  .min(1, "Player ID is required")
  .max(50, "Player ID is too long")
  .regex(/^[a-zA-Z0-9_-]+$/, "Invalid player ID format");

/** Mirrors api/shared/security.py SAFE_TEXT_PATTERN (used for team names). */
export const teamNameSchema = z
  .string()
  .min(1, "Team name is required")
  .max(100, "Team name is too long")
  .regex(/^[\w\s\-'.,?!]+$/u, "Team name contains invalid characters");

/** Mirrors ComparePlayersRequest. */
export const comparePlayersSchema = z
  .object({
    player_ids: z
      .array(playerIdSchema)
      .min(2, "Select at least 2 players to compare")
      .max(MAX_PLAYER_IDS, `You can compare up to ${MAX_PLAYER_IDS} players`),
  })
  .refine(
    (data) => new Set(data.player_ids).size === data.player_ids.length,
    { message: "Players must be unique", path: ["player_ids"] }
  );

export type ComparePlayersInput = z.infer<typeof comparePlayersSchema>;

/** Mirrors SimilarityFilters. */
export const similarityFiltersSchema = z.object({
  position: z.string().max(100).optional(),
  age_min: z.number().int().min(14).max(50).optional(),
  age_max: z.number().int().min(14).max(50).optional(),
  minutes_min: z.number().int().min(0).max(6000).optional(),
  league: z.string().max(150).optional(),
});

/** Mirrors SimilarityRequest. */
export const similarityRequestSchema = z.object({
  reference_player_id: playerIdSchema.max(50),
  filters: similarityFiltersSchema.optional(),
  top_n: z.number().int().min(1).max(20).default(5),
});

export type SimilarityInput = z.infer<typeof similarityRequestSchema>;

/** Mirrors TacticalFitRequest. */
export const tacticalFitRequestSchema = z.object({
  player_id: playerIdSchema.max(50),
  team_name: teamNameSchema,
});

export type TacticalFitInput = z.infer<typeof tacticalFitRequestSchema>;

/** Mirrors ScoutQueryRequest. */
export const scoutQueryRequestSchema = z.object({
  query: z
    .string()
    .trim()
    .min(1, "Please enter a question")
    .max(MAX_QUERY_LENGTH, `Query must be ${MAX_QUERY_LENGTH} characters or fewer`),
});

export type ScoutQueryInput = z.infer<typeof scoutQueryRequestSchema>;

/** Mirrors PlayerQueryParams (used for the /players list filters). */
export const playerQueryParamsSchema = z.object({
  position: z.string().max(100).optional(),
  league: z.string().max(150).optional(),
  club: z.string().max(150).optional(),
  age_min: z.number().int().min(14).max(50).optional(),
  age_max: z.number().int().min(14).max(50).optional(),
  minutes_min: z.number().int().min(0).max(6000).optional(),
});

export type PlayerQueryParamsInput = z.infer<typeof playerQueryParamsSchema>;

/**
 * Shared "player" shape returned by the API. Kept intentionally loose
 * (numbers may be null for missing stats) - the API is the source of truth
 * for exact fields.
 */
export const playerSchema = z
  .object({
    player_id: z.string(),
    player_name: z.string(),
    age: z.number().nullable().optional(),
    nationality: z.string().nullable().optional(),
    club: z.string().nullable().optional(),
    league: z.string().nullable().optional(),
    position: z.string().nullable().optional(),
    minutes: z.number().nullable().optional(),
    goals: z.number().nullable().optional(),
    assists: z.number().nullable().optional(),
    market_value_million: z.number().nullable().optional(),
    preferred_foot: z.string().nullable().optional(),
  })
  .catchall(z.unknown());

export type Player = z.infer<typeof playerSchema>;
