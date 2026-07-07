"""
Player comparison engine for /api/compare.

Builds a side-by-side comparison table across the standard metric set,
identifies the per-metric leader, and produces simple strengths/weaknesses
summaries for each player relative to the others being compared.
"""

from __future__ import annotations

from typing import Any, Optional

from .similarity import METRIC_LABELS, SIMILARITY_METRICS

# Metrics where a LOWER value is generally "better" defensively is not
# applicable here - all comparison metrics in our schema are "higher is
# better" for the purposes of a simple leader calculation.
COMPARISON_METRICS = SIMILARITY_METRICS + ["minutes", "market_value_million"]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_comparison(players: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the comparison_table, metric_differences, strengths and weaknesses."""

    comparison_table: list[dict[str, Any]] = []
    for metric in COMPARISON_METRICS:
        label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        row: dict[str, Any] = {"metric": metric, "label": label}
        values: dict[str, Optional[float]] = {}
        for player in players:
            value = _safe_float(player.get(metric))
            values[player["player_id"]] = value
            row[player["player_id"]] = value

        # Determine leader (highest value), ignoring missing values
        present = {pid: v for pid, v in values.items() if v is not None}
        if present:
            leader_id = max(present, key=lambda pid: present[pid])
            # Only mark a leader if values actually differ
            if len(set(present.values())) > 1:
                row["leader"] = leader_id
            else:
                row["leader"] = None
        else:
            row["leader"] = None

        comparison_table.append(row)

    # Metric differences: for 2-player comparisons, show the absolute and
    # percentage difference. For 3+ players, show the range (max - min).
    metric_differences: list[dict[str, Any]] = []
    for row in comparison_table:
        values = [row[p["player_id"]] for p in players if row.get(p["player_id"]) is not None]
        if len(values) < 2:
            continue
        diff = max(values) - min(values)
        if diff == 0:
            continue
        metric_differences.append({
            "metric": row["metric"],
            "label": row["label"],
            "difference": round(diff, 3),
            "leader": row["leader"],
        })

    # Sort by largest relative difference first (simple heuristic)
    metric_differences.sort(key=lambda d: d["difference"], reverse=True)

    # Strengths / weaknesses per player: metrics where they lead vs trail
    strengths: list[dict[str, Any]] = []
    weaknesses: list[dict[str, Any]] = []
    for player in players:
        pid = player["player_id"]
        leads = [row["label"] for row in comparison_table if row.get("leader") == pid]
        trails = []
        for row in comparison_table:
            present = {p["player_id"]: row.get(p["player_id"]) for p in players if row.get(p["player_id"]) is not None}
            if len(present) < 2:
                continue
            if pid in present and present[pid] == min(present.values()) and row.get("leader") and row.get("leader") != pid:
                trails.append(row["label"])

        strengths.append({
            "player_id": pid,
            "player_name": player.get("player_name"),
            "leading_metrics": leads[:6],
        })
        weaknesses.append({
            "player_id": pid,
            "player_name": player.get("player_name"),
            "trailing_metrics": trails[:6],
        })

    summary = _build_summary(players, comparison_table)

    return {
        "players": players,
        "comparison_table": comparison_table,
        "metric_differences": metric_differences[:8],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "summary": summary,
    }


def _build_summary(players: list[dict[str, Any]], comparison_table: list[dict[str, Any]]) -> str:
    names = [p.get("player_name", "Unknown") for p in players]
    if len(names) == 2:
        intro = f"{names[0]} and {names[1]} are compared across {len(comparison_table)} statistical categories."
    else:
        intro = f"{', '.join(names[:-1])} and {names[-1]} are compared across {len(comparison_table)} statistical categories."

    lead_counts: dict[str, int] = {p["player_id"]: 0 for p in players}
    for row in comparison_table:
        if row.get("leader") in lead_counts:
            lead_counts[row["leader"]] += 1

    top_player_id = max(lead_counts, key=lambda pid: lead_counts[pid]) if lead_counts else None
    top_player = next((p for p in players if p["player_id"] == top_player_id), None)

    if top_player and lead_counts[top_player_id] > 0:
        tail = (
            f" {top_player.get('player_name')} leads in the most individual categories "
            f"({lead_counts[top_player_id]} of {len(comparison_table)}), though the right "
            f"choice depends on the tactical role and system being considered."
        )
    else:
        tail = " The players are closely matched across most statistical categories."

    return intro + tail
