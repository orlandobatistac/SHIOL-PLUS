from fastapi.testclient import TestClient


def test_predictions_by_draw_date_with_matches_and_prizes(fastapi_app):
    client = TestClient(fastapi_app)
    # This will compute matches vs powerball_draws and format with prize totals
    resp = client.get(
        "/api/v1/predictions/by-draw/2025-09-03",
        params={"min_matches": 0, "limit": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["draw_date"] == "2025-09-03"
    assert "winning_numbers" in data and "predictions" in data
    # At least one prediction exists for seeded date
    assert data["total_predictions"] >= 1


def test_predictions_public_predictions_only(fastapi_app):
    client = TestClient(fastapi_app)
    resp = client.get(
        "/api/v1/predictions/public/predictions-only/2025-09-01",
        params={"limit": 10},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["draw_date"] == "2025-09-01"
    assert payload["total_predictions"] >= 1
    assert all("numbers" in p for p in payload["predictions"])


def test_draws_recent_legacy_table(fastapi_app):
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/draws/recent", params={"limit": 2})
    # draw_router.recent queries 'draws' table; our fixture created one
    assert resp.status_code == 200
    recent = resp.json()
    assert isinstance(recent, list)
    assert len(recent) >= 1
    assert set(recent[0].keys()) == {"draw_date", "winning_numbers", "powerball"}
