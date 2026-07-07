"""Tests for the SQL-backed RAG retriever and keyword extraction."""

from shared.database import LocalSeedDataStore
from shared.rag_retriever import extract_keywords, retrieve_context


def test_extract_keywords_matches_player_by_last_name():
    store = LocalSeedDataStore()
    players = store.get_players()
    teams = store.get_team_profiles()

    keywords = extract_keywords("Tell me about Bellingham's strengths", players, teams)
    assert "Jude Bellingham" in keywords["player_names"]


def test_extract_keywords_matches_position_group():
    store = LocalSeedDataStore()
    players = store.get_players()
    teams = store.get_team_profiles()

    keywords = extract_keywords("Which midfielders fit a possession-based system?", players, teams)
    assert "Midfielder" in keywords["position_groups"]
    assert "possession" in keywords["styles"]


def test_extract_keywords_matches_team_name():
    store = LocalSeedDataStore()
    players = store.get_players()
    teams = store.get_team_profiles()

    keywords = extract_keywords("Would this player fit Barcelona's tactical style?", players, teams)
    assert "Barcelona" in keywords["team_names"]


def test_retrieve_context_returns_scouting_note_for_named_player():
    result = retrieve_context("Give me a scouting report on Pedri")
    assert result["method"] in {"sql_keyword", "qdrant"}
    assert result["scouting_notes"], "expected at least one scouting note"
    names = [n.get("player_name") for n in result["scouting_notes"]]
    assert "Pedri" in names
    assert any("Pedri" in line for line in result["retrieved_context_summary"])


def test_retrieve_context_falls_back_when_nothing_matches():
    result = retrieve_context("zzzzzz nonsense query with no matches")
    assert result["retrieved_context_summary"]
    # Falls back to the "no closely matching" message when nothing is found
    assert isinstance(result["scouting_notes"], list)
    assert isinstance(result["team_profiles"], list)


def test_search_scouting_notes_local_seed_fallback():
    store = LocalSeedDataStore()
    notes = store.search_scouting_notes(["Pedri"], limit=5)
    assert notes
    assert any(n.get("player_name") == "Pedri" for n in notes)
