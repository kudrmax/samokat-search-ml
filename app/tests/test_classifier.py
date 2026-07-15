from pathlib import Path

import pytest

from backend.models import CategoryScore
from backend.pipeline.classifier import CategoryClassifier, preprocess_query

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
HAS_ARTIFACT = (MODELS_DIR / "category_cascade.joblib").exists() and (
    MODELS_DIR / "e5-small-en-ru"
).exists()


def test_preprocess_lowercases_and_strips_punct():
    assert preprocess_query("Кока-Кола 2л!!!") == "кока-кола л"


def test_preprocess_keeps_spaces_and_hyphen():
    assert preprocess_query("сок  апельсин-манго") == "сок  апельсин-манго"


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_predict_top_returns_three_sorted():
    clf = CategoryClassifier(MODELS_DIR)
    result = clf.predict_top("кока кола", k=3)
    assert len(result) == 3
    assert all(isinstance(c, CategoryScore) for c in result)
    assert result[0].score >= result[1].score >= result[2].score
    # каскад: у каждой категории есть подкатегория (строка или None)
    assert all(c.subcategory is None or isinstance(c.subcategory, str) for c in result)


def test_missing_artifacts_raise(tmp_path):
    with pytest.raises(RuntimeError, match="train_classifier"):
        CategoryClassifier(tmp_path)
