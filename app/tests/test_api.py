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


from pathlib import Path

import pytest

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
HAS_ARTIFACT = (MODELS_DIR / "category_cascade.joblib").exists() and (
    MODELS_DIR / "e5-small-en-ru"
).exists()


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_analyze_endpoint_returns_correction_and_categories():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", json={"query": "кока кола"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["original"] == "кока кола"
    assert "corrected" in body
    assert len(body["words"]) == 2
    assert len(body["categories"]) == 3
    assert body["categories"][0]["score"] >= body["categories"][1]["score"]
    assert all("subcategory" in c for c in body["categories"])


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_analyze_rejects_empty_query():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", json={"query": ""})
    assert resp.status_code == 422


ESCI_PARENT = Path(__file__).resolve().parents[2] / "esci"
HAS_ESCI = (ESCI_PARENT / "esci_classifier_module" / "predict_esci.py").exists()


@pytest.mark.skipif(not (HAS_ARTIFACT and HAS_ESCI), reason="нет артефакта категории или модуля ESCI")
def test_products_endpoint_returns_grid():
    with TestClient(app) as client:
        resp = client.post("/api/products", json={"query": "малако"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"]
    assert isinstance(body["products"], list)
    assert len(body["products"]) <= 16
    assert body["scanned"] <= 60
    assert isinstance(body["reached_cap"], bool)
    for p in body["products"]:
        assert "item_name" in p
