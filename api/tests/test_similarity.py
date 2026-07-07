"""Tests for player loading and the similarity engine."""

from shared.database import LocalSeedDataStore
from shared.similarity import SIMILARITY_METRICS, compute_similarity


def test_local_seed_store_loads_players():
    store = LocalSeedDataStore()
    players = store.get_players()
    assert len(players) >= 30
    # Spot-check a known player and basic field typing
    yamal = store.get_player("p001")
    assert yamal is not None
    assert yamal["player_name"]
    assert isinstance(yamal["age"], int)
    assert isinstance(yamal["xg"], float)


def test_get_player_unknown_returns_none():
    store = LocalSeedDataStore()
    assert store.get_player("does-not-exist") is None


def test_compute_similarity_returns_ranked_results_within_range():
    store = LocalSeedDataStore()
    players = store.get_players()
    reference = store.get_player("p001")  # Lamine Yamal

    results = compute_similarity(reference, players, top_n=5)

    assert 1 <= len(results) <= 5
    # Reference player must not appear in its own results
    assert all(r.player["player_id"] != "p001" for r in results)
    # Scores are within the documented 0-100 range
    for r in results:
        assert 0.0 <= r.similarity_score <= 100.0
    # Results sorted descending by similarity score
    scores = [r.similarity_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_compute_similarity_explains_closest_and_biggest_differences():
    store = LocalSeedDataStore()
    players = store.get_players()
    reference = store.get_player("p001")

    results = compute_similarity(reference, players, top_n=3)
    assert results, "expected at least one similarity result"

    top = results[0]
    assert top.closest_metrics, "expected closest_metrics to be populated"
    assert top.biggest_differences, "expected biggest_differences to be populated"
    for comparison in top.closest_metrics + top.biggest_differences:
        assert comparison.metric in SIMILARITY_METRICS
        assert 0.0 <= comparison.normalised_difference <= 1.0


def test_compute_similarity_respects_top_n():
    store = LocalSeedDataStore()
    players = store.get_players()
    reference = store.get_player("p001")

    results = compute_similarity(reference, players, top_n=2)
    assert len(results) == 2


def test_compute_similarity_handles_empty_candidates():
    store = LocalSeedDataStore()
    reference = store.get_player("p001")
    assert compute_similarity(reference, [], top_n=5) == []
