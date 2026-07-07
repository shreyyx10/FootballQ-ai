"""Tests for the FBref pipeline's transform layer (api/pipeline/transform.py).

These tests use small synthetic DataFrames with the *flattened* column
names that `fbref_scraper.flatten_columns()` produces - no network access
or live FBref data is required, so this suite runs in CI like the rest of
the backend tests.
"""

import pandas as pd

from pipeline.transform import (
    generate_player_id,
    slugify,
    transform_match_logs,
    transform_player_season_stats,
    transform_players,
    transform_team_stats,
)


def _player_row(**overrides):
    row = {
        "Player": "Test Player",
        "Nation": "es ESP",
        "Pos": "FW",
        "Squad": "Barcelona",
        "Comp": "es La Liga",
        "Age": "24-103",
        "Born": "2000",
        "90s": "30.0",
        "Min": "2700",
        "Gls": "10",
        "Ast": "5",
        "xG": "9.5",
        "xAG": "4.5",
        "Sh/90": "3.2",
        "Cmp%": "85.1",
        "KP": "90",
        "PrgP": "150",
        "PrgC": "60",
        "Succ": "45",
        "Tkl": "30",
        "Int": "15",
        "SCA90": "4.1",
    }
    row.update(overrides)
    return row


# -----------------------------------------------------------------------------
# transform_players
# -----------------------------------------------------------------------------

def test_transform_players_basic_mapping():
    df = pd.DataFrame([_player_row()])
    rows = transform_players(df)

    assert len(rows) == 1
    row = rows[0]

    assert row["player_name"] == "Test Player"
    assert row["age"] == 24
    assert row["nationality"] == "ESP"
    assert row["club"] == "Barcelona"
    assert row["league"] == "La Liga"
    assert row["position"] == "FW"
    assert row["minutes"] == 2700
    assert row["goals"] == 10
    assert row["assists"] == 5
    assert row["xg"] == 9.5
    assert row["xag"] == 4.5
    assert row["shots_per90"] == 3.2
    assert row["pass_completion_pct"] == 85.1
    assert row["shot_creating_actions_per90"] == 4.1


def test_transform_players_per90_division():
    df = pd.DataFrame([_player_row(KP="90", PrgP="150", PrgC="60", Succ="45", Tkl="30", Int="15", **{"90s": "30.0"})])
    row = transform_players(df)[0]

    assert row["key_passes_per90"] == 3.0
    assert row["progressive_passes_per90"] == 5.0
    assert row["progressive_carries_per90"] == 2.0
    assert row["successful_takeons_per90"] == 1.5
    assert row["tackles_per90"] == 1.0
    assert row["interceptions_per90"] == 0.5


def test_transform_players_missing_90s_leaves_per90_none():
    df = pd.DataFrame([_player_row(**{"90s": None})])
    row = transform_players(df)[0]

    assert row["key_passes_per90"] is None
    assert row["progressive_passes_per90"] is None


def test_transform_players_unscraped_fields_are_none():
    df = pd.DataFrame([_player_row()])
    row = transform_players(df)[0]

    assert row["pressures_per90"] is None
    assert row["market_value_million"] is None
    assert row["preferred_foot"] is None


def test_transform_players_missing_goals_assists_default_to_zero():
    df = pd.DataFrame([_player_row(Gls=None, Ast=None)])
    row = transform_players(df)[0]

    assert row["goals"] == 0
    assert row["assists"] == 0


def test_transform_players_empty_dataframe():
    assert transform_players(pd.DataFrame()) == []


def test_transform_players_league_name_override():
    # Single-league pages may have no/inconsistent "Comp" column - the
    # caller-supplied league name should win.
    df = pd.DataFrame([_player_row(Comp="eng Championship")])
    row = transform_players(df, league_name_override="Championship")[0]
    assert row["league"] == "Championship"

    df_no_comp = pd.DataFrame([_player_row(Comp=None)])
    row = transform_players(df_no_comp, league_name_override="Eredivisie")[0]
    assert row["league"] == "Eredivisie"


def test_transform_players_skips_blank_player_rows():
    df = pd.DataFrame([_player_row(Player="")])
    assert transform_players(df) == []


# -----------------------------------------------------------------------------
# transform_player_season_stats
# -----------------------------------------------------------------------------

def _season_player_row(**overrides):
    row = _player_row(**overrides)
    # Goalkeeping (keepers + keepersadv)
    row.setdefault("GA90", "0.9")
    row.setdefault("Save%", "71.5")
    row.setdefault("CS%", "35.0")
    row.setdefault("PSxG", "12.3")
    # Playing time
    row.setdefault("Starts", "28")
    row.setdefault("Mn/MP", "85.7")
    row.setdefault("Min%", "90.0")
    # Misc
    row.setdefault("CrdY", "4")
    row.setdefault("CrdR", "1")
    row.setdefault("Fls", "30")
    row.setdefault("Fld", "45")
    row.setdefault("Off", "9")
    row.setdefault("Won%", "55.5")
    row.setdefault("Recov", "120")
    return row


def test_transform_player_season_stats_basic_mapping():
    df = pd.DataFrame([_season_player_row()])
    rows = transform_player_season_stats(df, "2025-2026")

    assert len(rows) == 1
    row = rows[0]

    # Identity + existing per-90 fields carry over
    assert row["player_name"] == "Test Player"
    assert row["season"] == "2025-2026"
    assert row["league"] == "La Liga"
    assert row["club"] == "Barcelona"
    assert row["goals"] == 10
    assert row["xg"] == 9.5
    assert row["shot_creating_actions_per90"] == 4.1
    assert row["key_passes_per90"] == 3.0

    # Goalkeeping
    assert row["gk_goals_against_per90"] == 0.9
    assert row["gk_save_pct"] == 71.5
    assert row["gk_clean_sheet_pct"] == 35.0
    assert row["gk_psxg"] == 12.3

    # Playing time
    assert row["starts"] == 28
    assert row["minutes_per_match"] == 85.7
    assert row["minutes_pct"] == 90.0

    # Misc (direct)
    assert row["yellow_cards"] == 4
    assert row["red_cards"] == 1
    assert row["aerials_won_pct"] == 55.5

    # Misc (per-90, divided by "90s" = 30.0)
    assert row["fouls_committed_per90"] == 1.0
    assert row["fouls_drawn_per90"] == 1.5
    assert row["offsides_per90"] == 0.3
    assert row["ball_recoveries_per90"] == 4.0


def test_transform_player_season_stats_missing_new_columns_are_none():
    # A DataFrame with only the existing columns (no gk/playing-time/misc) -
    # new fields should be None rather than raising.
    df = pd.DataFrame([_player_row()])
    row = transform_player_season_stats(df, "2025-2026")[0]

    assert row["gk_goals_against_per90"] is None
    assert row["starts"] is None
    assert row["yellow_cards"] is None
    assert row["fouls_committed_per90"] is None


def test_transform_player_season_stats_league_name_override():
    df = pd.DataFrame([_season_player_row(Comp=None)])
    row = transform_player_season_stats(df, "2025-2026", league_name_override="Championship")[0]
    assert row["league"] == "Championship"


def test_transform_player_season_stats_empty_dataframe():
    assert transform_player_season_stats(pd.DataFrame(), "2025-2026") == []


def test_transform_player_season_stats_skips_blank_player_rows():
    df = pd.DataFrame([_season_player_row(Player="")])
    assert transform_player_season_stats(df, "2025-2026") == []


# -----------------------------------------------------------------------------
# player_id generation
# -----------------------------------------------------------------------------

def test_generate_player_id_is_deterministic():
    id1 = generate_player_id("Lamine Yamal", "2007", "Barcelona")
    id2 = generate_player_id("Lamine Yamal", "2007", "Barcelona")
    assert id1 == id2
    assert id1.startswith("fb_lamine_yamal")


def test_generate_player_id_differs_for_different_players():
    id1 = generate_player_id("Player A", "2000", "Team")
    id2 = generate_player_id("Player B", "2000", "Team")
    assert id1 != id2


def test_slugify():
    assert slugify("Lamine Yamal") == "lamine_yamal"
    assert slugify("  Multiple   Spaces ") == "multiple_spaces"


# -----------------------------------------------------------------------------
# transform_team_stats
# -----------------------------------------------------------------------------

def test_transform_team_stats_basic_mapping():
    df = pd.DataFrame([
        {
            "Squad": "Barcelona",
            "Comp": "es La Liga",
            "MP": "10",
            "Gls": "25",
            "GA": "8",
            "xG": "22.5",
            "xGA": "9.1",
            "Poss": "61.2",
        }
    ])
    rows = transform_team_stats(df, "2025-2026")

    assert len(rows) == 1
    row = rows[0]
    assert row["team_name"] == "Barcelona"
    assert row["league"] == "La Liga"
    assert row["season"] == "2025-2026"
    assert row["matches_played"] == 10
    assert row["goals_for"] == 25
    assert row["goals_against"] == 8
    assert row["xg"] == 22.5
    assert row["xga"] == 9.1
    assert row["possession_pct"] == 61.2


def test_transform_team_stats_empty_dataframe():
    assert transform_team_stats(pd.DataFrame(), "2025-2026") == []


def test_transform_team_stats_league_name_override():
    df = pd.DataFrame([
        {
            "Squad": "Leeds United",
            "Comp": None,
            "MP": "10",
            "Gls": "12",
            "GA": "9",
            "xG": "11.0",
            "xGA": "10.2",
            "Poss": "55.0",
        }
    ])
    rows = transform_team_stats(df, "2025-2026", league_name_override="Championship")
    assert rows[0]["league"] == "Championship"


# -----------------------------------------------------------------------------
# transform_match_logs
# -----------------------------------------------------------------------------

def test_transform_match_logs_keeps_only_played_matches():
    df = pd.DataFrame([
        {
            "Date": "2026-01-10",
            "Comp": "La Liga",
            "Venue": "Home",
            "Opponent": "Real Madrid",
            "Result": "W",
            "GF": "3",
            "GA": "1",
            "xG": "2.5",
            "xGA": "1.1",
            "Poss": "58.0",
        },
        {
            # Future fixture - no result yet
            "Date": "2026-06-20",
            "Comp": "La Liga",
            "Venue": "Away",
            "Opponent": "Sevilla",
            "Result": "",
            "GF": "",
            "GA": "",
            "xG": "",
            "xGA": "",
            "Poss": "",
        },
    ])

    rows = transform_match_logs(df, "Barcelona", "2025-2026")

    assert len(rows) == 1
    row = rows[0]
    assert row["team_name"] == "Barcelona"
    assert row["season"] == "2025-2026"
    assert row["match_date"] == "2026-01-10"
    assert row["competition"] == "La Liga"
    assert row["venue"] == "Home"
    assert row["opponent"] == "Real Madrid"
    assert row["result"] == "W"
    assert row["goals_for"] == 3
    assert row["goals_against"] == 1
    assert row["xg"] == 2.5
    assert row["xga"] == 1.1
    assert row["possession_pct"] == 58.0


def test_transform_match_logs_empty_dataframe():
    assert transform_match_logs(pd.DataFrame(), "Barcelona", "2025-2026") == []
