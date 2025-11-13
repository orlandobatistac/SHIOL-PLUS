from fastapi.testclient import TestClient


def test_ticket_health_endpoint(fastapi_app):
    client = TestClient(fastapi_app)
    r = client.get("/api/v1/ticket/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def test_ticket_preview_rejects_non_image(fastapi_app):
    client = TestClient(fastapi_app)
    # Send a text file pretending to be uploaded; content-type text/plain should be rejected
    files = {"file": ("test.txt", b"hello", "text/plain")}
    r = client.post("/api/v1/ticket/preview", files=files)
    assert r.status_code == 400
    body = r.json()
    assert "Invalid file type" in body["detail"]
