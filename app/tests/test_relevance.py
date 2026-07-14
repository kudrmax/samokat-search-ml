from pathlib import Path

import pytest

from backend.pipeline.relevance import RelevanceClassifier

ESCI_PARENT = Path(__file__).resolve().parents[2] / "esci"
HAS_MODULE = (ESCI_PARENT / "esci_classifier_module" / "predict_esci.py").exists()


def test_missing_module_raises(tmp_path):
    with pytest.raises(RuntimeError, match="esci_classifier_module"):
        RelevanceClassifier(tmp_path)


@pytest.mark.skipif(not HAS_MODULE, reason="нет модуля ESCI")
def test_exact_and_irrelevant():
    clf = RelevanceClassifier(ESCI_PARENT)
    assert clf.is_exact("малако", "Молоко Домик в деревне 3.2%, 900 мл") is True
    assert clf.is_exact("малако", "Кроссовки Nike беговые") is False
