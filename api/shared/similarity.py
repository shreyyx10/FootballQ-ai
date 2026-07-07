"""
Explainable player similarity engine.

Computes a 0-100 similarity score between a reference player and a pool of
candidate players using normalised, weighted Euclidean distance over a set
of per-90 and output metrics. Also returns the metrics where the players
are closest and most different, so the result can be explained to a user.

Design notes:
- Metrics are min-max normalised across the comparison pool (reference +
  candidates) so the score is meaningful regardless of each metric's scale
  (e.g. goals vs pass_completion_pct).
- Missing values are imputed with the pool's mean for that metric to avoid
  skewing the comparison or causing division-by-zero errors.
- If a metric has zero variance across the pool (max == min), it is excluded
  from the distance calculation for that comparison (it carries no
  discriminative information) - this avoids division by zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Metrics used for similarity comparisons (must exist in the Players table)
SIMILARITY_METRICS: list[str] = [
    "goals",
    "assists",
    "xg",
    "xag",
    "shots_per90",
    "key_passes_per90",
    "progressive_passes_per90",
    "progressive_carries_per90",
    "successful_takeons_per90",
    "shot_creating_actions_per90",
    "tackles_per90",
    "interceptions_per90",
    "pressures_per90",
    "pass_completion_pct",
]

# Human-readable labels for explanations
METRIC_LABELS: dict[str, str] = {
    "goals": "Goals",
    "assists": "Assists",
    "xg": "Expected Goals (xG)",
    "xag": "Expected Assists (xAG)",
    "shots_per90": "Shots per 90",
    "key_passes_per90": "Key Passes per 90",
    "progressive_passes_per90": "Progressive Passes per 90",
    "progressive_carries_per90": "Progressive Carries per 90",
    "successful_takeons_per90": "Successful Take-Ons per 90",
    "shot_creating_actions_per90": "Shot-Creating Actions per 90",
    "tackles_per90": "Tackles per 90",
    "interceptions_per90": "Interceptions per 90",
    "pressures_per90": "Pressures per 90",
    "pass_completion_pct": "Pass Completion %",
}


@dataclass
class MetricComparison:
    metric: str
    label: str
    reference_value: Optional[float]
    candidate_value: Optional[float]
    normalised_difference: float  # 0 (identical) - 1 (max different)


@dataclass
class SimilarityResult:
    player: dict[str, Any]
    similarity_score: float
    closest_metrics: list[MetricComparison]
    biggest_differences: list[MetricComparison]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_normalisation_ranges(
    pool: list[dict[str, Any]], metrics: list[str]
) -> dict[str, tuple[float, float, float]]:
    """Return {metric: (min, max, mean)} computed over the comparison pool."""
    ranges: dict[str, tuple[float, float, float]] = {}
    for metric in metrics:
        values = [v for p in pool if (v := _safe_float(p.get(metric))) is not None]
        if not values:
            ranges[metric] = (0.0, 0.0, 0.0)
            continue
        ranges[metric] = (min(values), max(values), sum(values) / len(values))
    return ranges


def _normalise(value: Optional[float], metric_range: tuple[float, float, float]) -> Optional[float]:
    min_v, max_v, mean_v = metric_range
    if value is None:
        value = mean_v
    if max_v == min_v:
        return None  # zero variance - exclude this metric from distance
    return (value - min_v) / (max_v - min_v)


def compute_similarity(
    reference_player: dict[str, Any],
    candidates: list[dict[str, Any]],
    metrics: Optional[list[str]] = None,
    top_n: int = 5,
) -> list[SimilarityResult]:
    """Rank `candidates` by similarity to `reference_player`.

    Returns up to `top_n` SimilarityResult objects, sorted by descending
    similarity score (0-100).
    """
    metrics = metrics or SIMILARITY_METRICS

    # Exclude the reference player itself from candidates if present
    ref_id = reference_player.get("player_id")
    pool_candidates = [c for c in candidates if c.get("player_id") != ref_id]
    if not pool_candidates:
        return []

    # Build normalisation ranges across reference + all candidates
    full_pool = [reference_player] + pool_candidates
    ranges = _build_normalisation_ranges(full_pool, metrics)

    # Determine usable metrics (non-zero variance)
    usable_metrics = [m for m in metrics if ranges[m][1] != ranges[m][0]]

    results: list[SimilarityResult] = []
    for candidate in pool_candidates:
        comparisons: list[MetricComparison] = []
        squared_diffs: list[float] = []

        for metric in metrics:
            ref_raw = _safe_float(reference_player.get(metric))
            cand_raw = _safe_float(candidate.get(metric))
            ref_norm = _normalise(ref_raw, ranges[metric])
            cand_norm = _normalise(cand_raw, ranges[metric])

            if ref_norm is None or cand_norm is None:
                # Zero-variance metric - no discriminative value, skip from distance
                diff = 0.0
            else:
                diff = abs(ref_norm - cand_norm)
                squared_diffs.append(diff ** 2)

            comparisons.append(
                MetricComparison(
                    metric=metric,
                    label=METRIC_LABELS.get(metric, metric),
                    reference_value=ref_raw,
                    candidate_value=cand_raw,
                    normalised_difference=round(diff, 4),
                )
            )

        if usable_metrics:
            # Weighted Euclidean distance, normalised to [0, 1] by dividing by
            # sqrt(number of usable metrics) - the maximum possible distance
            # when every normalised dimension differs by 1.
            distance = (sum(squared_diffs) ** 0.5) / (len(usable_metrics) ** 0.5)
        else:
            distance = 0.0

        similarity_score = round(max(0.0, min(1.0, 1.0 - distance)) * 100, 1)

        # Only consider usable metrics for "closest"/"biggest difference" explanations
        explainable = [c for c in comparisons if c.metric in usable_metrics]
        closest = sorted(explainable, key=lambda c: c.normalised_difference)[:3]
        biggest = sorted(explainable, key=lambda c: c.normalised_difference, reverse=True)[:3]

        results.append(
            SimilarityResult(
                player=candidate,
                similarity_score=similarity_score,
                closest_metrics=closest,
                biggest_differences=biggest,
            )
        )

    results.sort(key=lambda r: r.similarity_score, reverse=True)
    return results[:top_n]


def metric_comparison_to_dict(comparison: MetricComparison) -> dict[str, Any]:
    return {
        "metric": comparison.metric,
        "label": comparison.label,
        "reference_value": comparison.reference_value,
        "candidate_value": comparison.candidate_value,
        "normalised_difference": comparison.normalised_difference,
    }


def similarity_result_to_dict(result: SimilarityResult) -> dict[str, Any]:
    return {
        "player": result.player,
        "similarity_score": result.similarity_score,
        "closest_metrics": [metric_comparison_to_dict(c) for c in result.closest_metrics],
        "biggest_differences": [metric_comparison_to_dict(c) for c in result.biggest_differences],
    }
