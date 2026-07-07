"""
Tactical fit engine for /api/tactical-fit.

Produces an explainable 0-100 fit score for how well a player's statistical
profile aligns with a team's tactical identity (pressing intensity,
possession style, formation and stated player requirements).

This is a heuristic, explainable scoring model - not a machine-learning
model - so every component of the score can be explained to the user.
"""

from __future__ import annotations

from typing import Any, Optional

PRESSING_WEIGHT = {
    "very high": 1.0,
    "high": 0.85,
    "medium-high": 0.7,
    "medium": 0.5,
    "low-medium": 0.4,
    "low": 0.25,
}

POSSESSION_WEIGHT = {
    "possession-heavy, short combinations": 1.0,
    "possession-heavy with positional rotations and overloads": 1.0,
    "possession-heavy with structured build-up and overloads on the ball-near side": 0.95,
    "possession-heavy with high pressing triggers": 0.9,
    "mixed - controlled possession with quick vertical transitions": 0.7,
    "balanced - controlled possession with explosive transitions": 0.65,
}


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(value: Optional[float], pool: list[Optional[float]]) -> float:
    """Return the percentile rank (0-1) of `value` within `pool`. Missing values ignored."""
    clean_pool = [v for v in pool if v is not None]
    if value is None or not clean_pool:
        return 0.5  # neutral if data is missing
    if max(clean_pool) == min(clean_pool):
        return 0.5
    below_or_equal = sum(1 for v in clean_pool if v <= value)
    return below_or_equal / len(clean_pool)


def _pressing_weight(intensity: Optional[str]) -> float:
    if not intensity:
        return 0.5
    return PRESSING_WEIGHT.get(intensity.strip().lower(), 0.5)


def _possession_weight(style: Optional[str]) -> float:
    if not style:
        return 0.5
    return POSSESSION_WEIGHT.get(style.strip().lower(), 0.6)


def _position_alignment(player: dict[str, Any], team: dict[str, Any]) -> tuple[float, str]:
    """Score 0-1 for how well the player's position matches the team's stated requirements."""
    position = (player.get("position") or "").lower()
    requirements = (team.get("player_requirements") or "").lower()

    # Map position to keyword fragments that might appear in requirements text
    position_keywords = {
        "winger": ["winger", "wide forward", "wide players", "wide attacker"],
        "striker": ["striker", "number 9", "centre-forward", "central striker", "penalty-box"],
        "attacking midfielder": ["attacking midfield", "number 10", "creative", "between the lines"],
        "central midfielder": ["central midfield", "midfield trio", "midfielders", "central midfielders"],
        "defensive midfielder": ["defensive midfield", "holding midfield", "deep-lying", "pivot", "ball-winning"],
        "full-back": ["full-back", "full back", "wing-back", "attacking full-back", "inverted full-back"],
        "centre-back": ["centre-back", "centre back", "defenders", "back line"],
    }

    keywords = position_keywords.get(position, [])
    if not keywords:
        return 0.5, "no explicit positional requirement found"

    matches = [kw for kw in keywords if kw in requirements]
    if matches:
        return 1.0, f"matches stated requirement for '{matches[0]}'"
    return 0.35, f"no direct match found for '{position}' in stated requirements"


def compute_tactical_fit(
    player: dict[str, Any],
    team: dict[str, Any],
    league_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute a 0-100 tactical fit score and supporting explanation."""

    pressing_w = _pressing_weight(team.get("pressing_intensity"))
    possession_w = _possession_weight(team.get("possession_style"))

    # Build percentile pools across the league sample
    pool = league_pool or [player]

    pressures_pct = _percentile(_safe_float(player.get("pressures_per90")), [_safe_float(p.get("pressures_per90")) for p in pool])
    tackles_pct = _percentile(_safe_float(player.get("tackles_per90")), [_safe_float(p.get("tackles_per90")) for p in pool])
    pressing_score = pressing_w * ((pressures_pct + tackles_pct) / 2)

    pass_pct = _percentile(_safe_float(player.get("pass_completion_pct")), [_safe_float(p.get("pass_completion_pct")) for p in pool])
    prog_pass_pct = _percentile(_safe_float(player.get("progressive_passes_per90")), [_safe_float(p.get("progressive_passes_per90")) for p in pool])
    possession_score = possession_w * ((pass_pct + prog_pass_pct) / 2)

    position_alignment, position_explanation = _position_alignment(player, team)

    xg_pct = _percentile(_safe_float(player.get("xg")), [_safe_float(p.get("xg")) for p in pool])
    xag_pct = _percentile(_safe_float(player.get("xag")), [_safe_float(p.get("xag")) for p in pool])
    sca_pct = _percentile(_safe_float(player.get("shot_creating_actions_per90")), [_safe_float(p.get("shot_creating_actions_per90")) for p in pool])
    output_score = (xg_pct + xag_pct + sca_pct) / 3

    # Weighted blend -> 0-100
    raw_score = (
        pressing_score * 25
        + possession_score * 25
        + position_alignment * 30
        + output_score * 20
    )
    fit_score = round(min(100.0, max(0.0, raw_score)), 1)

    strengths: list[str] = []
    risks: list[str] = []

    if position_alignment >= 0.8:
        strengths.append(f"Positional profile {position_explanation} for {team.get('team_name')}.")
    else:
        risks.append(f"Positional profile {position_explanation} for {team.get('team_name')}.")

    if pressing_score >= 0.6 * pressing_w and pressing_w >= 0.5:
        strengths.append(
            f"Pressing output (pressures/tackles per 90) ranks in the top "
            f"{round((1 - (pressures_pct + tackles_pct) / 2) * 100)}% of the sample, "
            f"suiting {team.get('team_name')}'s {team.get('pressing_intensity', 'stated').lower()} pressing intensity."
        )
    elif pressing_w >= 0.7:
        risks.append(
            f"Pressing output may be below the level required for {team.get('team_name')}'s "
            f"{(team.get('pressing_intensity') or 'high').lower()} pressing demands."
        )

    if possession_score >= 0.6 * possession_w and possession_w >= 0.6:
        strengths.append(
            f"Passing profile (completion % and progressive passes) aligns well with "
            f"{team.get('team_name')}'s {(team.get('possession_style') or 'possession-based').lower()} approach."
        )
    elif possession_w >= 0.6 and possession_score < 0.4:
        risks.append(
            f"Passing/possession metrics may need development to match "
            f"{team.get('team_name')}'s possession-heavy style."
        )

    if output_score >= 0.7:
        strengths.append("Strong underlying output (xG, xAG, shot-creating actions) relative to the sample.")
    elif output_score <= 0.3:
        risks.append("Underlying output (xG, xAG, shot-creating actions) is comparatively modest for this profile.")

    explanation = (
        f"{player.get('player_name')} ({player.get('position')}) was assessed against {team.get('team_name')}'s "
        f"{team.get('formation', 'system')} ({team.get('tactical_style', 'tactical identity')}). "
        f"The fit score of {fit_score}/100 reflects positional alignment, pressing output relative to the team's "
        f"{(team.get('pressing_intensity') or 'stated').lower()} pressing intensity, passing profile relative to its "
        f"{(team.get('possession_style') or 'possession').lower()} style, and overall attacking/creative output."
    )

    return {
        "fit_score": fit_score,
        "strengths": strengths or ["No standout statistical strengths identified for this specific tactical profile."],
        "risks": risks or ["No major tactical risks identified based on available statistics."],
        "explanation": explanation,
        "components": {
            "pressing_alignment": round(pressing_score, 2),
            "possession_alignment": round(possession_score, 2),
            "position_alignment": round(position_alignment, 2),
            "output_alignment": round(output_score, 2),
        },
    }
