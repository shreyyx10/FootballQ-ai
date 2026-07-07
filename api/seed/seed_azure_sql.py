"""
Seed script for the PostgreSQL database (Neon/Supabase free tier).

(File name is historical - this originally targeted Azure SQL.)

Usage:
    1. Apply `schema.sql` first: python -m seed.apply_schema (from api/).
    2. Set the DATABASE_URL environment variable locally
       (do NOT commit this value).
    3. Run from api/: python -m seed.seed_azure_sql

This script reads the bundled sample data files and inserts them using
parameterised queries only. It is safe to re-run - it clears existing rows
from the relevant tables before inserting.

Requires: psycopg (pip install "psycopg[binary]").
"""

from __future__ import annotations

import csv
import json
import os
import sys

SEED_DIR = os.path.dirname(os.path.abspath(__file__))


def get_connection():
    import psycopg

    conn_str = os.environ.get("DATABASE_URL", "") or os.environ.get("AZURE_SQL_CONNECTION_STRING", "")
    if not conn_str:
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("Set it temporarily in your shell session - do not commit it.")
        sys.exit(1)
    return psycopg.connect(conn_str, connect_timeout=30)


def seed_players(cursor) -> int:
    csv_path = os.path.join(SEED_DIR, "sample_players.csv")
    cursor.execute("DELETE FROM ScoutingNotes")
    cursor.execute("DELETE FROM Players")

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """
                INSERT INTO Players (
                    player_id, player_name, age, nationality, club, league, position,
                    minutes, goals, assists, xg, xag, shots_per90, key_passes_per90,
                    progressive_passes_per90, progressive_carries_per90,
                    successful_takeons_per90, shot_creating_actions_per90,
                    tackles_per90, interceptions_per90, pressures_per90,
                    pass_completion_pct, market_value_million, preferred_foot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    row["player_id"], row["player_name"], int(row["age"]), row["nationality"],
                    row["club"], row["league"], row["position"], int(row["minutes"]),
                    int(row["goals"]), int(row["assists"]), float(row["xg"]), float(row["xag"]),
                    float(row["shots_per90"]), float(row["key_passes_per90"]),
                    float(row["progressive_passes_per90"]), float(row["progressive_carries_per90"]),
                    float(row["successful_takeons_per90"]), float(row["shot_creating_actions_per90"]),
                    float(row["tackles_per90"]), float(row["interceptions_per90"]),
                    float(row["pressures_per90"]), float(row["pass_completion_pct"]),
                    float(row["market_value_million"]), row["preferred_foot"],
                ],
            )
            count += 1
    return count


def seed_scouting_notes(cursor) -> int:
    json_path = os.path.join(SEED_DIR, "sample_scouting_notes.json")
    with open(json_path, encoding="utf-8") as f:
        notes = json.load(f)

    count = 0
    for note in notes:
        cursor.execute(
            """
            INSERT INTO ScoutingNotes (
                player_id, player_name, profile_summary, strengths, weaknesses,
                tactical_notes, role_fit, risk_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                note["player_id"],
                note["player_name"],
                note["profile_summary"],
                json.dumps(note["strengths"], ensure_ascii=False),
                json.dumps(note["weaknesses"], ensure_ascii=False),
                note["tactical_notes"],
                note["role_fit"],
                note["risk_notes"],
            ],
        )
        count += 1
    return count


def seed_team_profiles(cursor) -> int:
    json_path = os.path.join(SEED_DIR, "sample_team_profiles.json")
    with open(json_path, encoding="utf-8") as f:
        teams = json.load(f)

    cursor.execute("DELETE FROM TeamProfiles")
    count = 0
    for team in teams:
        cursor.execute(
            """
            INSERT INTO TeamProfiles (
                team_name, tactical_style, formation, pressing_intensity,
                possession_style, player_requirements
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                team["team_name"], team["tactical_style"], team["formation"],
                team["pressing_intensity"], team["possession_style"], team["player_requirements"],
            ],
        )
        count += 1
    return count


def main() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        players = seed_players(cursor)
        notes = seed_scouting_notes(cursor)
        teams = seed_team_profiles(cursor)
        conn.commit()
        print(f"Seeded {players} players, {notes} scouting notes, {teams} team profiles.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
