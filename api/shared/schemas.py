"""
Pydantic schemas for request validation and response shaping.

All API inputs are validated through these models before any business
logic or database access occurs. Validation errors result in safe JSON
error responses (see shared/security.py) - never raw stack traces.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .security import (
    MAX_PLAYER_IDS,
    MAX_QUERY_LENGTH,
    is_valid_player_id,
    is_valid_team_name,
)


# -----------------------------------------------------------------------------
# /api/players
# -----------------------------------------------------------------------------

class PlayerQueryParams(BaseModel):
    position: Optional[str] = Field(default=None, max_length=100)
    league: Optional[str] = Field(default=None, max_length=150)
    club: Optional[str] = Field(default=None, max_length=150)
    age_min: Optional[int] = Field(default=None, ge=14, le=50)
    age_max: Optional[int] = Field(default=None, ge=14, le=50)
    minutes_min: Optional[int] = Field(default=None, ge=0, le=6000)

    @field_validator("position", "league", "club")
    @classmethod
    def _strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


# -----------------------------------------------------------------------------
# /api/compare
# -----------------------------------------------------------------------------

class ComparePlayersRequest(BaseModel):
    player_ids: list[str] = Field(min_length=2, max_length=MAX_PLAYER_IDS)

    @field_validator("player_ids")
    @classmethod
    def _validate_player_ids(cls, value: list[str]) -> list[str]:
        for player_id in value:
            if not is_valid_player_id(player_id):
                raise ValueError(f"Invalid player_id format: {player_id!r}")
        if len(set(value)) != len(value):
            raise ValueError("player_ids must not contain duplicates")
        return value


# -----------------------------------------------------------------------------
# /api/similarity
# -----------------------------------------------------------------------------

class SimilarityFilters(BaseModel):
    position: Optional[str] = Field(default=None, max_length=100)
    age_max: Optional[int] = Field(default=None, ge=14, le=50)
    age_min: Optional[int] = Field(default=None, ge=14, le=50)
    minutes_min: Optional[int] = Field(default=None, ge=0, le=6000)
    league: Optional[str] = Field(default=None, max_length=150)


class SimilarityRequest(BaseModel):
    reference_player_id: str = Field(max_length=50)
    filters: Optional[SimilarityFilters] = None
    top_n: int = Field(default=5, ge=1, le=20)

    @field_validator("reference_player_id")
    @classmethod
    def _validate_reference_player_id(cls, value: str) -> str:
        if not is_valid_player_id(value):
            raise ValueError(f"Invalid reference_player_id format: {value!r}")
        return value


# -----------------------------------------------------------------------------
# /api/tactical-fit
# -----------------------------------------------------------------------------

class TacticalFitRequest(BaseModel):
    player_id: str = Field(max_length=50)
    team_name: str = Field(max_length=100)

    @field_validator("player_id")
    @classmethod
    def _validate_player_id(cls, value: str) -> str:
        if not is_valid_player_id(value):
            raise ValueError(f"Invalid player_id format: {value!r}")
        return value

    @field_validator("team_name")
    @classmethod
    def _validate_team_name(cls, value: str) -> str:
        value = value.strip()
        if not is_valid_team_name(value):
            raise ValueError(f"Invalid team_name: {value!r}")
        return value


# -----------------------------------------------------------------------------
# /api/scout
# -----------------------------------------------------------------------------

class ScoutQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value
