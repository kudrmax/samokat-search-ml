from fastapi.testclient import TestClient

from backend.main import app


def test_correct_endpoint_returns_words():
    with TestClient(app) as client:
        resp = client.post("/api/correct", json={"query": "крсовки молоко"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["original"] == "крсовки молоко"
    assert body["corrected"] == "кроссовки молоко"
    assert body["words"][0] == {
        "original": "крсовки",
        "corrected": "кроссовки",
        "changed": True,
    }
    assert body["words"][1]["changed"] is False


def test_correct_endpoint_rejects_empty_query():
    with TestClient(app) as client:
        resp = client.post("/api/correct", json={"query": ""})
    assert resp.status_code == 422


def test_root_serves_html():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
